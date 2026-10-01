from __future__ import annotations

import logging
from pathlib import Path

from music21 import converter, interval, key as keymod
from music21 import metadata, note, pitch, stream

from .keys import KEY_TONICS, TransposeError, semitones_between, write_keys
from .score import _clean_musicxml, display_title

log = logging.getLogger("keyprint")

_PC_TO_ID = {
    0: "C",
    1: "Db",
    2: "D",
    3: "Eb",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "Ab",
    9: "A",
    10: "Bb",
    11: "B",
}


def parse_key(key_id: str) -> keymod.Key:
    tonic = KEY_TONICS.get((key_id or "").strip())
    if not tonic:
        raise TransposeError("请选择原调和要移到的调。")
    return keymod.Key(tonic)


def canonical_key_id(value) -> str:
    try:
        pc = int(value.tonic.pitchClass)
    except Exception:
        try:
            pc = int(value.asKey("major").tonic.pitchClass)
        except Exception:
            return "C"
    return _PC_TO_ID.get(pc % 12, "C")


def load_score(path: Path):
    try:
        parsed = converter.parse(str(path))
    except Exception as exc:
        raise TransposeError("读不了这份谱。请上传 MusicXML 或 MIDI。") from exc
    if isinstance(parsed, stream.Opus):
        if not parsed.scores:
            raise TransposeError("这份谱是空的。")
        parsed = parsed.scores[0]
    if parsed is None:
        raise TransposeError("读不了这份谱。请上传 MusicXML 或 MIDI。")
    return parsed


def detect_written_key(score) -> str:
    flat = score.flatten()
    for item in flat.getElementsByClass(keymod.Key):
        return canonical_key_id(item)
    for item in flat.getElementsByClass(keymod.KeySignature):
        try:
            return canonical_key_id(item.asKey("major"))
        except Exception:
            continue
    return "C"


def _interval(from_key: keymod.Key, to_key: keymod.Key) -> interval.Interval:
    source = pitch.Pitch(from_key.tonic.name + "4")
    target = pitch.Pitch(to_key.tonic.name + "4")
    distance = (target.midi - source.midi) % 12
    if distance > 6:
        distance -= 12
    while target.midi - source.midi > distance:
        target.octave -= 1
    while target.midi - source.midi < distance:
        target.octave += 1
    return interval.Interval(source, target)


def _count_notes(score) -> int:
    return sum(1 for item in score.flatten().notes if isinstance(item, (note.Note, note.Unpitched)) or item.pitches)


def _ensure_key(score, target: keymod.Key) -> None:
    parts = list(getattr(score, "parts", []) or [])
    if not parts:
        score.insert(0, target)
        return
    for part in parts:
        existing = list(part.recurse().getElementsByClass((keymod.Key, keymod.KeySignature)))
        if existing:
            continue
        import copy
        part.insert(0, copy.deepcopy(target))


def transpose_midi(source: Path, dest: Path, semitones: int) -> None:
    """Change pitches without re-quantizing timing or losing MIDI metadata."""
    import mido

    midi = mido.MidiFile(str(source))
    for track in midi.tracks:
        for message in track:
            if message.type in {"note_on", "note_off", "polytouch"} and message.channel != 9:
                value = message.note + semitones
                if not 0 <= value <= 127:
                    raise TransposeError("移调后有音符超出 MIDI 音域，请选择更近的目标调。")
                message.note = value
            elif message.type == "key_signature":
                shifted = keymod.Key(message.key).transpose(semitones)
                name = shifted.tonic.name.replace("-", "b")
                suffix = "m" if shifted.mode == "minor" else ""
                try:
                    message.key = name + suffix
                except ValueError:
                    message.key = _PC_TO_ID[shifted.tonic.pitchClass] + suffix
    dest.parent.mkdir(parents=True, exist_ok=True)
    midi.save(str(dest))


def transpose_score_file(
    source: Path,
    xml_path: Path,
    midi_path: Path,
    from_key: str,
    to_key: str,
    title: str | None = None,
) -> dict:
    source_key = parse_key(from_key)
    target_key = parse_key(to_key)
    score = load_score(source)
    step = _interval(source_key, target_key)
    if step.semitones:
        score.transpose(step, inPlace=True)
    for item in score.recurse().notes:
        if isinstance(item, note.Unpitched):
            continue
        if any(not 0 <= p.ps <= 127 for p in item.pitches):
            raise TransposeError("移调后有音符超出 MIDI 音域，请选择更近的目标调。")
    _ensure_key(score, target_key)
    if score.metadata is None:
        score.insert(0, metadata.Metadata())
    score.metadata.title = display_title(title)
    score.metadata.composer = ""
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(xml_path))
    _clean_musicxml(xml_path)
    midi_path.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in {".mid", ".midi"}:
        transpose_midi(source, midi_path, semitones_between(from_key, to_key))
    else:
        score.write("midi", fp=str(midi_path))
    write_keys(xml_path.parent, from_key, to_key)
    return {
        "from_key": from_key,
        "to_key": to_key,
        "key": str(target_key),
        "note_count": _count_notes(score),
        "semitones": int(step.semitones),
    }
