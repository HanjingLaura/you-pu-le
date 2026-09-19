from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .config import DATA_DIR
from .instruments import DEFAULT_INSTRUMENT

Stage = Literal[
    "queued",
    "downloading",
    "extracting",
    "transcribing",
    "scoring",
    "done",
    "error",
]


@dataclass
class Job:
    id: str
    filename: str
    stage: Stage = "queued"
    message: str = "排队中"
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_sec: float | None = None
    note_count: int | None = None
    pedal_count: int | None = None
    key_name: str | None = None
    bpm: float | None = None
    source_url: str | None = None
    instrument: str = DEFAULT_INSTRUMENT
    source_instrument: str = DEFAULT_INSTRUMENT

    @property
    def directory(self) -> Path:
        path = DATA_DIR / self.id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "stage": self.stage,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "duration_sec": self.duration_sec,
            "note_count": self.note_count,
            "pedal_count": self.pedal_count,
            "key_name": self.key_name,
            "bpm": self.bpm,
            "instrument": self.instrument,
            "source_instrument": self.source_instrument,
            "midi_url": f"/jobs/{self.id}/midi" if self.stage == "done" else None,
            "musicxml_url": f"/jobs/{self.id}/musicxml" if self.stage == "done" else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            id=data["id"],
            filename=data.get("filename") or "source",
            stage=data.get("stage") or "queued",
            message=data.get("message") or "",
            error=data.get("error"),
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
            duration_sec=data.get("duration_sec"),
            note_count=data.get("note_count"),
            pedal_count=data.get("pedal_count"),
            key_name=data.get("key_name"),
            bpm=data.get("bpm"),
            source_url=data.get("source_url"),
            instrument=data.get("instrument") or DEFAULT_INSTRUMENT,
            source_instrument=data.get("source_instrument") or DEFAULT_INSTRUMENT,
        )


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    def _meta_path(self, job_id: str) -> Path:
        return DATA_DIR / job_id / "job.json"

    def _write(self, job: Job) -> None:
        payload = job.to_dict()
        payload["source_url"] = job.source_url
        path = self._meta_path(job.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _recover(self, job: Job) -> Job:
        directory = DATA_DIR / job.id
        xml_path = directory / "score.musicxml"
        midi_path = directory / "score.mid"
        if xml_path.exists():
            job.stage = "done"
            job.message = "草稿谱已生成"
            job.error = None
        return job

    def _load_from_disk(self) -> None:
        if not DATA_DIR.exists():
            return
        for folder in DATA_DIR.iterdir():
            if not folder.is_dir():
                continue
            job = self._read_folder(folder)
            if job:
                self._jobs[job.id] = job
                self._write(job)

    def _read_folder(self, folder: Path) -> Job | None:
        meta = folder / "job.json"
        if meta.exists():
            try:
                return self._recover(Job.from_dict(json.loads(meta.read_text(encoding="utf-8"))))
            except Exception:
                pass
        xml_path = folder / "score.musicxml"
        midi_path = folder / "score.mid"
        if not xml_path.exists() and not midi_path.exists():
            return None
        sources = list(folder.glob("source.*"))
        done = xml_path.exists()
        return Job(
            id=folder.name,
            filename=sources[0].name if sources else "source",
            stage="done" if done else "scoring",
            message="草稿谱已生成" if done else "正在排谱",
        )

    def create(
        self,
        filename: str,
        source_url: str | None = None,
        instrument: str = DEFAULT_INSTRUMENT,
        source_instrument: str = DEFAULT_INSTRUMENT,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            filename=filename,
            source_url=source_url,
            instrument=instrument,
            source_instrument=source_instrument,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._write(job)
        return job

    def save(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
        self._write(job)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            cached = self._jobs.get(job_id)
        if cached:
            return cached
        meta = self._meta_path(job_id)
        folder = DATA_DIR / job_id
        if meta.exists():
            job = self._recover(Job.from_dict(json.loads(meta.read_text(encoding="utf-8"))))
        else:
            job = self._read_folder(folder) if folder.is_dir() else None
            if not job:
                return None
        with self._lock:
            self._jobs[job.id] = job
        self._write(job)
        return job

    def unfinished(self) -> list[Job]:
        with self._lock:
            return [
                job
                for job in self._jobs.values()
                if job.stage not in {"done", "error"}
            ]


store = JobStore()
