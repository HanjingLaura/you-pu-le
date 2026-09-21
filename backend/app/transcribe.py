from __future__ import annotations

import logging
import threading
from functools import lru_cache

import numpy as np

from .checkpoint import ensure_checkpoint
from .config import CHECKPOINT_PATH, SAMPLE_RATE

try:
    import librosa
    import torch
except ImportError as exc:  # pragma: no cover - environment/setup
    raise RuntimeError("扒谱引擎还没装好。需要先安装 torch、librosa。") from exc

log = logging.getLogger("keyprint")
_LOAD_LOCK = threading.Lock()

_orig_torch_load = torch.load


def _torch_load_compat(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_torch_load(*args, **kwargs)


torch.load = _torch_load_compat


def choose_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def _load_transcriptor():
    ensure_checkpoint()
    from piano_transcription_inference import PianoTranscription

    device = choose_device()
    log.info("Loading piano transcription model on %s", device)
    return PianoTranscription(device=device, checkpoint_path=str(CHECKPOINT_PATH))


def model_loaded() -> bool:
    return _load_transcriptor.cache_info().currsize > 0


def transcribe_wav(wav_path, midi_path) -> dict:
    with _LOAD_LOCK:
        transcriptor = _load_transcriptor()

    audio, _ = librosa.load(path=str(wav_path), sr=SAMPLE_RATE, mono=True)
    if audio.size == 0:
        raise RuntimeError("读不到音频数据。")

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.95

    transcribed = transcriptor.transcribe(audio, str(midi_path))
    notes = transcribed.get("est_note_events") or []
    pedals = transcribed.get("est_pedal_events") or []
    if not notes:
        raise RuntimeError("没有识别到钢琴音符。请确认是清晰的纯钢琴独奏。")
    return {"note_count": len(notes), "pedal_count": len(pedals)}
