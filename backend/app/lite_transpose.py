"""Share the notation engine locally and on Vercel.

The previous XML walker assumed 120 BPM, fixed divisions and one sequential
voice, corrupting multi-staff scores. music21 does not require torch/librosa.
"""
from pathlib import Path


def detect_written_key_lite(path: Path) -> str:
    from .transpose import detect_written_key, load_score

    return detect_written_key(load_score(path))


def transpose_score_file_lite(
    source: Path,
    xml_path: Path,
    midi_path: Path,
    from_key: str,
    to_key: str,
    title: str | None = None,
) -> dict:
    from .transpose import transpose_score_file

    return transpose_score_file(source, xml_path, midi_path, from_key, to_key, title)
