from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pretty_midi

from .keys import TransposeError, require_key, semitones_between, write_keys

_FIFTHS = {
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "Db": -5,
    "Ab": -4,
    "Eb": -3,
    "Bb": -2,
    "F": -1,
}
_FIFTHS_TO_ID = {value: key for key, value in _FIFTHS.items()}
_STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SPELLINGS = {
    "C": ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"],
    "G": ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"],
    "D": ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
    "A": ["C", "C#", "D", "D#", "E", "E#", "F#", "G", "G#", "A", "A#", "B"],
    "E": ["B#", "C#", "D", "D#", "E", "E#", "F#", "G", "G#", "A", "A#", "B"],
    "B": ["B#", "C#", "D", "D#", "E", "E#", "F#", "F##", "G#", "A", "A#", "B"],
    "F#": ["B#", "C#", "C##", "D#", "E", "E#", "F#", "F##", "G#", "A", "A#", "B"],
    "Db": ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"],
    "Ab": ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "Cb"],
    "Eb": ["C", "Db", "D", "Eb", "Fb", "F", "Gb", "G", "Ab", "A", "Bb", "Cb"],
    "Bb": ["C", "Db", "D", "Eb", "Fb", "F", "Gb", "G", "Ab", "A", "Bb", "Cb"],
    "F": ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"],
}
_DURATION_TYPES = {
    16: "whole",
    12: "half",
    8: "half",
    6: "quarter",
    4: "quarter",
    3: "eighth",
    2: "eighth",
    1: "16th",
}


def _name_to_parts(name: str) -> tuple[str, int]:
    step = name[0]
    rest = name[1:]
    alter = rest.count("#") - rest.count("b")
    return step, alter


def _midi_to_name(midi: int, key_id: str) -> tuple[str, int, int]:
    pc = midi % 12
    octave = midi // 12 - 1
    name = _SPELLINGS.get(key_id, _SPELLINGS["C"])[pc]
    step, alter = _name_to_parts(name)
    return step, alter, octave


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _open_xml(path: Path) -> Path:
    if path.suffix.lower() != ".mxl":
        return path
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if not name.startswith("META-INF/") and name.lower().endswith((".xml", ".musicxml"))
            ]
            if not names:
                raise TransposeError("读不了这份谱。请上传 MusicXML 或 MIDI。")
            dest = path.with_suffix(".musicxml")
            dest.write_bytes(archive.read(names[0]))
            return dest
    except TransposeError:
        raise
    except Exception as exc:
        raise TransposeError("读不了这份谱。请上传 MusicXML 或 MIDI。") from exc


def detect_written_key_lite(path: Path) -> str:
    if path.suffix.lower() in {".mid", ".midi"}:
        return "C"
    try:
        root = ET.parse(_open_xml(path)).getroot()
    except TransposeError:
        raise
    except Exception as exc:
        raise TransposeError("读不了这份谱。请上传 MusicXML 或 MIDI。") from exc
    for node in root.iter():
        if _local(node.tag) == "fifths" and node.text:
            try:
                return _FIFTHS_TO_ID.get(int(node.text), "C")
            except ValueError:
                continue
    return "C"


def _transpose_midi(source: Path, dest: Path, semis: int) -> pretty_midi.PrettyMIDI:
    midi = pretty_midi.PrettyMIDI(str(source))
    for inst in midi.instruments:
        for note in inst.notes:
            note.pitch = max(0, min(127, note.pitch + semis))
    dest.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(dest))
    return midi


def _transpose_xml(source: Path, dest: Path, to_key: str, semis: int) -> int:
    tree = ET.parse(_open_xml(source))
    root = tree.getroot()
    count = 0
    for node in root.iter():
        if _local(node.tag) == "fifths":
            node.text = str(_FIFTHS[to_key])
        if _local(node.tag) != "pitch":
            continue
        step = alter = octave = None
        for child in list(node):
            name = _local(child.tag)
            if name == "step":
                step = child
            elif name == "alter":
                alter = child
            elif name == "octave":
                octave = child
        if step is None or octave is None or not step.text or not octave.text:
            continue
        midi = 12 * (int(octave.text) + 1) + _STEP_PC.get(step.text, 0) + int(
            alter.text if alter is not None and alter.text else 0
        )
        next_step, next_alter, next_octave = _midi_to_name(max(0, min(127, midi + semis)), to_key)
        step.text = next_step
        octave.text = str(next_octave)
        if next_alter:
            if alter is None:
                alter = ET.SubElement(node, "alter")
            alter.text = str(next_alter)
        elif alter is not None:
            node.remove(alter)
        count += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dest, encoding="utf-8", xml_declaration=True)
    return count


def _escape(text: str) -> str:
    return (
        (text or "草稿谱")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _note_xml(step: str, alter: int, octave: int, duration: int, chord: bool) -> str:
    kind = _DURATION_TYPES.get(duration, "quarter")
    alter_xml = f"<alter>{alter}</alter>" if alter else ""
    chord_xml = "<chord/>" if chord else ""
    dotted = "<dot/>" if duration in {12, 6, 3} else ""
    return (
        f"<note>{chord_xml}<pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
        f"<duration>{duration}</duration><type>{kind}</type>{dotted}</note>"
    )


def _rest_xml(duration: int) -> str:
    kind = _DURATION_TYPES.get(duration, "quarter")
    dotted = "<dot/>" if duration in {12, 6, 3} else ""
    return f"<note><rest/><duration>{duration}</duration><type>{kind}</type>{dotted}</note>"


def _split_duration(width: int) -> list[int]:
    parts: list[int] = []
    remain = max(0, width)
    for size in (16, 8, 4, 2, 1):
        while remain >= size:
            parts.append(size)
            remain -= size
    return parts or [1]


def _midi_to_xml(midi: pretty_midi.PrettyMIDI, dest: Path, title: str, key_id: str) -> int:
    events: list[tuple[float, float, int]] = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            events.append((note.start, max(note.end, note.start + 0.05), note.pitch))
    events.sort()
    try:
        bpm = float(midi.estimate_tempo())
    except Exception:
        bpm = 120.0
    if not bpm or bpm < 40 or bpm > 240:
        bpm = 120.0
    beat = 60.0 / bpm
    sixteenth = beat / 4

    def quantize(seconds: float) -> int:
        return max(0, int(round(seconds / sixteenth)))

    grouped: dict[int, list[tuple[int, int]]] = {}
    for start, end, pitch in events:
        start_tick = quantize(start)
        duration = max(1, quantize(end) - start_tick)
        grouped.setdefault(start_tick, []).append((pitch, duration))

    measures: list[str] = []
    cursor = 0
    measure_notes: list[str] = []
    count = 0
    starts = sorted(grouped)
    index = 0
    end_tick = max((start + max(item[1] for item in grouped[start]) for start in starts), default=16)
    end_tick = max(16, ((end_tick + 15) // 16) * 16)

    def flush_measure() -> None:
        nonlocal measure_notes
        number = len(measures) + 1
        attributes = ""
        if number == 1:
            attributes = (
                "<attributes><divisions>4</divisions>"
                f"<key><fifths>{_FIFTHS[key_id]}</fifths></key>"
                "<time><beats>4</beats><beat-type>4</beat-type></time>"
                "<clef><sign>G</sign><line>2</line></clef></attributes>"
            )
        body = "".join(measure_notes) or _rest_xml(16)
        measures.append(f'<measure number="{number}">{attributes}{body}</measure>')
        measure_notes = []

    while cursor < end_tick:
        measure_end = ((cursor // 16) + 1) * 16
        if index < len(starts) and starts[index] == cursor:
            notes = sorted(grouped[starts[index]], key=lambda item: item[0])
            duration = min(max(item[1] for item in notes), measure_end - cursor)
            for chord_index, (pitch, _) in enumerate(notes):
                step, alter, octave = _midi_to_name(pitch, key_id)
                measure_notes.append(_note_xml(step, alter, octave, duration, chord_index > 0))
                count += 1
            index += 1
            cursor += duration
        else:
            next_start = starts[index] if index < len(starts) else end_tick
            gap = min(measure_end, next_start) - cursor
            for part in _split_duration(gap):
                measure_notes.append(_rest_xml(part))
            cursor += gap
        if cursor >= measure_end:
            flush_measure()

    if measure_notes:
        flush_measure()
    if not measures:
        flush_measure()

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="3.1">'
        f"<work><work-title>{_escape(title)}</work-title></work>"
        '<part-list><score-part id="P1"><part-name></part-name></score-part></part-list>'
        f'<part id="P1">{"".join(measures)}</part>'
        "</score-partwise>",
        encoding="utf-8",
    )
    return count


def _xml_to_midi(xml_path: Path, midi_path: Path) -> None:
    root = ET.parse(xml_path).getroot()
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    cursor = 0.0
    last_start = 0.0
    for note in root.iter():
        if _local(note.tag) != "note":
            continue
        is_chord = any(_local(child.tag) == "chord" for child in note)
        is_rest = any(_local(child.tag) == "rest" for child in note)
        duration = 0.5
        step = octave = None
        alter = 0
        for child in note:
            name = _local(child.tag)
            if name == "duration" and child.text:
                duration = max(0.125, int(child.text) * 0.125)
            elif name == "pitch":
                for part in child:
                    part_name = _local(part.tag)
                    if part_name == "step":
                        step = part.text
                    elif part_name == "octave" and part.text:
                        octave = int(part.text)
                    elif part_name == "alter" and part.text:
                        alter = int(part.text)
        start = last_start if is_chord else cursor
        if is_rest:
            cursor += duration
            continue
        if step is None or octave is None:
            continue
        pitch = 12 * (octave + 1) + _STEP_PC.get(step, 0) + alter
        inst.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + duration))
        if not is_chord:
            last_start = start
            cursor = start + duration
    midi.instruments.append(inst)
    midi.write(str(midi_path))


def transpose_score_file_lite(
    source: Path,
    xml_path: Path,
    midi_path: Path,
    from_key: str,
    to_key: str,
    title: str | None = None,
) -> dict:
    require_key(from_key)
    target = require_key(to_key)
    semis = semitones_between(from_key, to_key)
    suffix = source.suffix.lower()
    if suffix in {".mid", ".midi"}:
        midi = _transpose_midi(source, midi_path, semis)
        count = _midi_to_xml(midi, xml_path, title or "草稿谱", target)
    elif suffix in {".musicxml", ".xml", ".mxl"}:
        count = _transpose_xml(source, xml_path, target, semis)
        _xml_to_midi(xml_path, midi_path)
    else:
        raise TransposeError("请上传 MusicXML 或 MIDI。")
    write_keys(xml_path.parent, from_key, to_key)
    return {
        "from_key": from_key,
        "to_key": to_key,
        "key": f"{target} major",
        "note_count": count,
        "semitones": semis,
    }
