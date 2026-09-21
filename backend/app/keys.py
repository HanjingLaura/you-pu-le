from __future__ import annotations

import json
from pathlib import Path

KEY_TONICS = {
    "C": "C",
    "Db": "D-",
    "D": "D",
    "Eb": "E-",
    "E": "E",
    "F": "F",
    "F#": "F#",
    "G": "G",
    "Ab": "A-",
    "A": "A",
    "Bb": "B-",
    "B": "B",
}

KEY_PC = {
    "C": 0,
    "Db": 1,
    "D": 2,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "G": 7,
    "Ab": 8,
    "A": 9,
    "Bb": 10,
    "B": 11,
}


class TransposeError(ValueError):
    pass


def require_key(key_id: str) -> str:
    key = (key_id or "").strip()
    if key not in KEY_TONICS:
        raise TransposeError("请选择原调和要移到的调。")
    return key


def semitones_between(from_key: str, to_key: str) -> int:
    return (KEY_PC[require_key(to_key)] - KEY_PC[require_key(from_key)]) % 12


def write_keys(directory: Path, from_key: str, to_key: str) -> None:
    (directory / "keys.json").write_text(
        json.dumps({"from_key": from_key, "to_key": to_key}, ensure_ascii=False),
        encoding="utf-8",
    )


def read_keys(directory: Path) -> dict[str, str]:
    path = directory / "keys.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "from_key": str(payload.get("from_key") or ""),
        "to_key": str(payload.get("to_key") or ""),
    }
