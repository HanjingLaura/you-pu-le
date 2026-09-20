from __future__ import annotations

import logging
import re
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from .audio import AudioError, extract_wav
from .download import download_source, validate_url
from .checkpoint import checkpoint_ready, ensure_checkpoint
from .config import ALLOWED_SUFFIXES, MAX_UPLOAD_BYTES, SCORE_SUFFIXES
from .ffmpeg_bin import ffmpeg_executable
from .instruments import DEFAULT_INSTRUMENT, get_instrument, list_instruments
from .jobs import Job, store
from .melody import track_melody, write_notes_midi
from .midi_io import is_midi, to_concert_midi, to_written_midi
from .score import demo_scale_musicxml, midi_to_musicxml
from .transpose import TransposeError, detect_written_key, load_score, read_keys, transpose_score_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("keyprint")


app = FastAPI(title="有谱了", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_JOB_LOCK = threading.Lock()


@app.on_event("startup")
def warmup() -> None:
    ffmpeg_executable()
    threading.Thread(target=_warmup_checkpoint, daemon=True).start()
    threading.Thread(target=_resume_unfinished_jobs, daemon=True).start()


def _warmup_checkpoint() -> None:
    try:
        ensure_checkpoint()
    except Exception:
        log.exception("Checkpoint warmup failed")


def _resume_unfinished_jobs() -> None:
    for job in store.unfinished():
        log.info("Resuming job %s at stage %s", job.id, job.stage)
        threading.Thread(target=run_job, args=(job.id,), daemon=True).start()


@app.get("/")
def root() -> dict:
    return {"ok": True, "name": "有谱了", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict:
    try:
        ffmpeg_path = ffmpeg_executable()
        ffmpeg_ok = True
    except Exception:
        ffmpeg_path = None
        ffmpeg_ok = False
    try:
        from .transcribe import choose_device, model_loaded

        device = choose_device()
        loaded = model_loaded()
    except Exception:
        device = "unavailable"
        loaded = False
    return {
        "ok": ffmpeg_ok,
        "ffmpeg": ffmpeg_ok,
        "ffmpeg_path": ffmpeg_path,
        "device": device,
        "checkpoint_ready": checkpoint_ready(),
        "model_loaded": loaded,
    }


def _parse_instrument(instrument_id: str | None):
    try:
        return get_instrument(instrument_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/instruments")
def instruments() -> dict:
    return {"default": DEFAULT_INSTRUMENT, "items": list_instruments()}


async def _read_upload(file: UploadFile, allowed: set[str], dest: Path) -> Path:
    if not file.filename:
        raise HTTPException(400, "请上传谱子。")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, "请上传 MusicXML 或 MIDI。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = dest.with_suffix(suffix)
    size = 0
    try:
        with path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(400, "文件超过 80MB。")
                handle.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "上传是空文件。")
    return path


@app.post("/key-transpose/inspect")
async def inspect_key_transpose(file: UploadFile = File(...)) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            path = await _read_upload(file, SCORE_SUFFIXES, Path(tmp) / "score")
            key_id = detect_written_key(load_score(path))
        except TransposeError as exc:
            raise HTTPException(400, str(exc)) from exc
    return {"key": key_id}


@app.post("/key-transpose")
async def create_key_transpose(
    file: UploadFile = File(...),
    from_key: str = Form(...),
    to_key: str = Form(...),
) -> dict:
    job = store.create(file.filename or "score", instrument="piano")
    try:
        source = await _read_upload(file, SCORE_SUFFIXES, job.directory / "source")
        result = transpose_score_file(
            source,
            job.directory / "score.musicxml",
            job.directory / "score.mid",
            from_key,
            to_key,
            Path(job.filename).stem,
        )
    except TransposeError as exc:
        store.purge(job.id)
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        store.purge(job.id)
        raise
    except Exception as exc:
        log.exception("Key transpose failed")
        store.purge(job.id)
        raise HTTPException(500, "移调失败，请再试一次。") from exc
    job.key_name = result["key"]
    job.note_count = result["note_count"]
    job.stage = "done"
    job.message = "已移调"
    job.error = None
    store.save(job)
    payload = job.to_dict()
    payload.update({"from_key": result["from_key"], "to_key": result["to_key"]})
    return payload


@app.post("/key-transpose/{job_id}")
def redo_key_transpose(job_id: str, to_key: str = Form(...)) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "找不到这个任务。")
    sources = list(job.directory.glob("source.*"))
    if not sources:
        raise HTTPException(409, "找不到原来的谱。")
    keys = read_keys(job.directory)
    from_key = keys.get("from_key")
    if not from_key:
        raise HTTPException(409, "找不到原来的调。")
    try:
        result = transpose_score_file(
            sources[0],
            job.directory / "score.musicxml",
            job.directory / "score.mid",
            from_key,
            to_key,
            Path(job.filename).stem,
        )
    except TransposeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        log.exception("Key re-transpose failed")
        raise HTTPException(500, "移调失败，请再试一次。") from exc
    job.key_name = result["key"]
    job.note_count = result["note_count"]
    job.stage = "done"
    job.message = "已移调"
    job.error = None
    store.save(job)
    payload = job.to_dict()
    payload.update({"from_key": result["from_key"], "to_key": result["to_key"]})
    return payload


@app.post("/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    instrument: str | None = Form(None),
    source_instrument: str | None = Form(None),
) -> dict:
    spec = _parse_instrument(instrument)
    source_spec = _parse_instrument(source_instrument)
    source_url = url.strip() if url else None
    if file and file.filename:
        filename = file.filename
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(400, "只接受视频、音频或 MIDI：mp4 / mov / webm / wav / mp3 / m4a / flac / mid。")

        job = store.create(
            filename,
            instrument=spec.id,
            source_instrument=source_spec.id,
        )
        upload_path = job.directory / f"source{suffix}"
        size = 0
        try:
            with upload_path.open("wb") as handle:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(400, "文件超过 80MB。请先剪短或压一下。")
                    handle.write(chunk)
            if size == 0:
                raise HTTPException(400, "上传是空文件。")
        except Exception:
            store.purge(job.id)
            raise
    elif source_url:
        try:
            validate_url(source_url)
        except AudioError as exc:
            raise HTTPException(400, str(exc)) from exc
        job = store.create(
            source_url,
            source_url=source_url,
            instrument=spec.id,
            source_instrument=source_spec.id,
        )
    else:
        raise HTTPException(400, "请上传视频 / 音频 / MIDI，或粘贴链接。")

    background_tasks.add_task(run_job, job.id)
    store.save(job)
    return job.to_dict()


@app.get("/demo/musicxml", response_class=PlainTextResponse)
def demo_musicxml(instrument: str | None = None) -> str:
    spec = _parse_instrument(instrument)
    return demo_scale_musicxml(spec.id)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "找不到这个任务。")
    return job.to_dict()


def _download_stem(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem)[:80]
    return cleaned or "score"


@app.get("/jobs/{job_id}/midi")
def download_midi(job_id: str) -> FileResponse:
    job = _require_done(job_id)
    concert = job.directory / "score.mid"
    if not concert.exists():
        raise HTTPException(404, "MIDI 还没生成。")
    spec = get_instrument(job.instrument)
    path = concert
    if spec.write_semitones:
        written = job.directory / "score-written.mid"
        to_written_midi(concert, written, spec.id)
        path = written
    download_name = _download_stem(job.filename) + ".mid"
    return FileResponse(path, filename=download_name, media_type="audio/midi")


@app.get("/jobs/{job_id}/musicxml")
def download_musicxml(job_id: str) -> FileResponse:
    job = _require_done(job_id)
    path = job.directory / "score.musicxml"
    if not path.exists():
        raise HTTPException(404, "乐谱还没生成。")
    download_name = _download_stem(job.filename) + ".musicxml"
    return FileResponse(
        path,
        filename=download_name,
        media_type="application/vnd.recordare.musicxml+xml",
    )


@app.get("/jobs/{job_id}/musicxml-text", response_class=PlainTextResponse)
def musicxml_text(job_id: str) -> str:
    job = _require_done(job_id)
    path = job.directory / "score.musicxml"
    if not path.exists():
        raise HTTPException(404, "乐谱还没生成。")
    return path.read_text(encoding="utf-8")


@app.post("/jobs/{job_id}/rescore")
def rescore_job(job_id: str, instrument: str = Form(...)) -> dict:
    with _JOB_LOCK:
        return _rescore_locked(job_id, instrument)


def _require_done(job_id: str) -> Job:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "找不到这个任务。")
    if job.stage != "done":
        raise HTTPException(409, "任务还没完成。")
    return job


def _rescore_locked(job_id: str, instrument_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "找不到这个任务。")
    midi_path = job.directory / "score.mid"
    if not midi_path.exists():
        raise HTTPException(409, "还没有 MIDI，没法换乐器。")
    previous = (
        job.stage,
        job.message,
        job.error,
        job.instrument,
        job.key_name,
        job.bpm,
        job.note_count,
    )
    spec = _parse_instrument(instrument_id)
    xml_path = job.directory / "score.musicxml"
    wav_path = job.directory / "audio.wav"
    job.instrument = spec.id
    job.stage = "scoring"
    job.message = f"正在排出{spec.name}谱"
    job.error = None
    store.save(job)
    try:
        _prepare_score_midi(job, spec, midi_path, wav_path)
        scored = midi_to_musicxml(midi_path, xml_path, Path(job.filename).stem, spec.id)
        job.key_name = scored["key"]
        job.bpm = scored["bpm"]
        job.note_count = scored["note_count"]
        job.stage = "done"
        job.message = "草稿谱已生成"
        store.save(job)
        return job.to_dict()
    except Exception as exc:
        log.exception("Job %s rescore failed", job.id)
        (
            job.stage,
            job.message,
            job.error,
            job.instrument,
            job.key_name,
            job.bpm,
            job.note_count,
        ) = previous
        store.save(job)
        raise HTTPException(500, "换乐器失败，请再试一次。") from exc


def _prepare_score_midi(job: Job, spec, midi_path: Path, wav_path: Path) -> None:
    if spec.grand:
        piano_path = job.directory / "piano.mid"
        if piano_path.exists():
            if piano_path.resolve() != midi_path.resolve():
                shutil.copy2(piano_path, midi_path)
            return
        if midi_path.exists() and not wav_path.exists():
            return
        if not wav_path.exists():
            if not midi_path.exists():
                raise RuntimeError("没有音频，没法排钢琴谱。")
            return
        from .transcribe import transcribe_wav

        job.stage = "transcribing"
        job.message = "正在识别琴键（这一步最慢）"
        store.save(job)
        transcribed = transcribe_wav(wav_path, piano_path)
        job.note_count = transcribed["note_count"]
        job.pedal_count = transcribed["pedal_count"]
        store.save(job)
        if piano_path.resolve() != midi_path.resolve():
            shutil.copy2(piano_path, midi_path)
        return

    melody_path = job.directory / "melody.mid"
    piano_path = job.directory / "piano.mid"
    if midi_path.exists() and not piano_path.exists() and not melody_path.exists():
        shutil.copy2(midi_path, piano_path)
    if wav_path.exists():
        if not melody_path.exists():
            job.stage = "transcribing"
            job.message = "正在听主旋律"
            store.save(job)
            notes = track_melody(wav_path)
            if notes:
                write_notes_midi(melody_path, notes)
        if melody_path.exists():
            shutil.copy2(melody_path, midi_path)


def run_job(job_id: str) -> None:
    job = store.get(job_id)
    if not job:
        return
    with _JOB_LOCK:
        _run_job_locked(job)


def _run_job_locked(job: Job) -> None:
    try:
        sources = list(job.directory.glob("source.*"))
        if not sources and job.source_url:
            job.stage = "downloading"
            job.message = "正在拉取链接"
            store.save(job)
            sources = [download_source(job.source_url, job.directory)]
        if not sources:
            raise RuntimeError("找不到上传文件。")
        source = sources[0]
        wav_path = job.directory / "audio.wav"
        midi_path = job.directory / "score.mid"
        xml_path = job.directory / "score.musicxml"

        if is_midi(source):
            job.stage = "scoring"
            job.message = "正在按乐器移调"
            store.save(job)
            duration = to_concert_midi(source, midi_path, job.source_instrument)
            job.duration_sec = round(duration, 2)
            store.save(job)
        else:
            if not wav_path.exists():
                job.stage = "extracting"
                job.message = "正在抽出音频"
                store.save(job)
                duration = extract_wav(source, wav_path)
                job.duration_sec = round(duration, 2)
                store.save(job)
            elif job.duration_sec is None:
                job.duration_sec = 0

        spec = get_instrument(job.instrument)
        _prepare_score_midi(job, spec, midi_path, wav_path)
        job.stage = "scoring"
        job.message = f"正在排出{spec.name}谱"
        store.save(job)
        title = Path(job.filename).stem
        scored = midi_to_musicxml(midi_path, xml_path, title, spec.id)
        job.key_name = scored["key"]
        job.bpm = scored["bpm"]
        job.note_count = scored["note_count"]

        job.stage = "done"
        job.message = "草稿谱已生成"
        job.error = None
        store.save(job)
    except AudioError as exc:
        log.warning("Job %s audio error: %s", job.id, exc)
        job.stage = "error"
        job.error = str(exc)
        job.message = "失败"
        store.save(job)
    except Exception as exc:
        log.exception("Job %s failed", job.id)
        job.stage = "error"
        job.error = str(exc)
        job.message = "失败"
        store.save(job)
