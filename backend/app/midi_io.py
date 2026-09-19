from __future__ import annotations

import shutil
from pathlib import Path

import pretty_midi

from .instruments import get_instrument


def is_midi(path: Path) -> bool:
    return path.suffix.lower() in {".mid", ".midi"}


def to_concert_midi(source: Path, dest: Path, source_instrument: str) -> float:
    spec = get_instrument(source_instrument)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)

    parsed = pretty_midi.PrettyMIDI(str(dest))
    shift = spec.write_semitones
    if shift:
        for inst in parsed.instruments:
            if inst.is_drum:
                continue
            for item in inst.notes:
                item.pitch = int(max(0, min(127, item.pitch - shift)))
        parsed.write(str(dest))
    return float(parsed.get_end_time())
