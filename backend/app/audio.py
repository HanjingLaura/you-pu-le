from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .config import MAX_DURATION_SEC, SAMPLE_RATE
from .ffmpeg_bin import ffmpeg_executable

DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class AudioError(ValueError):
    pass


def probe_duration_seconds(path: Path) -> float | None:
    proc = subprocess.run(
        [ffmpeg_executable(), "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    match = DURATION_RE.search(proc.stderr or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_wav(source: Path, wav_path: Path) -> float:
    duration = probe_duration_seconds(source)
    if duration is not None and duration > MAX_DURATION_SEC + 1:
        raise AudioError(f"音频超过 {MAX_DURATION_SEC // 60} 分钟，请先剪到 1-3 分钟。")

    wav_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg_executable(),
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "wav",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 or not wav_path.exists():
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
        raise AudioError("抽音频失败。请确认文件里有声音轨道。\n" + "\n".join(detail))

    wav_duration = probe_duration_seconds(wav_path)
    if wav_duration is not None and wav_duration > MAX_DURATION_SEC + 1:
        wav_path.unlink(missing_ok=True)
        raise AudioError(f"音频超过 {MAX_DURATION_SEC // 60} 分钟，请先剪到 1-3 分钟。")
    if wav_duration is not None and wav_duration < 1:
        raise AudioError("音频太短，至少需要 1 秒的钢琴演奏。")
    return wav_duration or duration or 0.0
