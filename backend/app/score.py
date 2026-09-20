from __future__ import annotations

import copy
import logging
import re
from pathlib import Path

from music21 import chord, clef, instrument, key as keymod
from music21 import layout, metadata, meter, note, pitch, stream, tempo

from .instruments import (
    DEFAULT_INSTRUMENT,
    InstrumentSpec,
    get_instrument,
    music21_instrument,
)
from .melody import track_melody
from .piano import PianoEvent, estimate_bpm, fit_duration, load_notes, prepare_piano, quantize_voice

log = logging.getLogger("keyprint")

_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_MINOR = (0, 2, 3, 5, 7, 8, 10)
_UGLY_TITLE = re.compile(r"(?:\d{5,}|[a-f0-9]{12,}|v\d{3,})", re.IGNORECASE)


def display_title(title: str | None) -> str:
    stem = Path(title or "").stem.strip()
    if not stem or len(stem) > 18 or _UGLY_TITLE.search(stem):
        return "草稿谱"
    return stem


def _fold_midi(value: int, low: int | None, high: int | None) -> int:
    if low is None or high is None:
        return value
    folded = value
    while folded < low:
        folded += 12
    while folded > high:
        folded -= 12
    return max(low, min(high, folded))


def _written_key(detected_key, spec: InstrumentSpec):
    if not spec.write_semitones:
        return detected_key
    try:
        return detected_key.transpose(spec.write_semitones)
    except Exception:
        return detected_key


def _key_from_pc(pc: int, mode: str) -> keymod.Key:
    name = pitch.Pitch(midi=60 + (pc % 12)).name
    return keymod.Key(name, mode)


def _fits_mode(unique: set[int], tonic: int, intervals: tuple[int, ...]) -> bool:
    scale = {(tonic + step) % 12 for step in intervals}
    return bool(unique) and unique <= scale


def detect_key(midis: list[int]):
    if not midis:
        return keymod.Key("C")
    unique = {value % 12 for value in midis}
    bass = min(midis) % 12
    if _fits_mode(unique, bass, _MAJOR):
        return _key_from_pc(bass, "major")
    if _fits_mode(unique, bass, _MINOR):
        return _key_from_pc(bass, "minor")

    probe = stream.Stream()
    for index, midi_number in enumerate(midis[:64]):
        probe.insert(index * 0.5, note.Note(midi_number, quarterLength=0.5))
    try:
        analyzed = probe.analyze("key")
    except Exception:
        analyzed = keymod.Key("C")
    if analyzed.mode == "minor":
        relative = (analyzed.tonic.midi + 3) % 12
        if _fits_mode(unique, relative, _MAJOR):
            return _key_from_pc(relative, "major")
    return analyzed


def midi_to_musicxml(
    midi_path: Path,
    xml_path: Path,
    title: str,
    instrument_id: str = DEFAULT_INSTRUMENT,
    wav_path: Path | None = None,
) -> dict:
    spec = get_instrument(instrument_id)
    heading = display_title(title)

    if spec.grand:
        events, bpm = prepare_piano(midi_path)
        detected_key = detect_key([pitch for event in events for pitch in event.pitches])
        score = _piano_score(events, detected_key, bpm, heading)
        note_count = sum(len(event.pitches) for event in events)
    else:
        notes = []
        if wav_path and Path(wav_path).exists():
            try:
                notes = track_melody(wav_path, spec.sounding_low, spec.sounding_high)
            except Exception as exc:
                log.warning("melody tracker failed, using MIDI: %s", exc)
        if not notes:
            notes = load_notes(midi_path)
        bpm = estimate_bpm(notes) if notes else 80.0
        events = _trim_leading_measures(quantize_voice(notes, bpm, spec.sounding_low, spec.sounding_high))
        detected_key = detect_key([pitch for event in events for pitch in event.pitches])
        score = _single_staff_from_events(events, detected_key, bpm, heading, spec)
        note_count = len(events)

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(xml_path))
    _clean_musicxml(xml_path)

    return {
        "key": str(_written_key(detected_key, spec)),
        "time_signature": "4/4",
        "bpm": bpm,
        "note_count": note_count,
        "instrument": spec.id,
    }


def _piano_score(events, detected_key, bpm: float, title: str) -> stream.Score:
    time_signature = meter.TimeSignature("4/4")
    right = stream.Part(id="P1")
    left = stream.Part(id="P2")
    right.partName = ""
    left.partName = ""
    right.partAbbreviation = ""
    left.partAbbreviation = ""

    for part in (right, left):
        piano = instrument.Piano()
        piano.instrumentName = ""
        piano.instrumentAbbreviation = ""
        part.insert(0, piano)
        part.insert(0, copy.deepcopy(detected_key))
        part.insert(0, copy.deepcopy(time_signature))
        part.insert(0, tempo.MetronomeMark(number=bpm))

    right.insert(0, clef.TrebleClef())
    left.insert(0, clef.BassClef())

    right_events = [event for event in events if event.hand == "right"]
    left_events = [event for event in events if event.hand == "left"]
    _write_events(right, right_events, _piano_element)
    _write_events(left, left_events, _piano_element)
    _finish_part(right)
    _finish_part(left)

    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = title or "草稿谱"
    score.metadata.composer = None
    score.metadata.movementName = None
    score.insert(0, right)
    score.insert(0, left)
    score.insert(0, layout.StaffGroup([right, left], name="Piano", symbol="brace"))
    return score


def _piano_element(event) -> note.NotRest:
    pitches = [pitch.Pitch(midi=value) for value in event.pitches]
    if len(pitches) == 1:
        return note.Note(pitches[0])
    return chord.Chord(pitches)


def _written_melody_pitch(event, spec: InstrumentSpec) -> pitch.Pitch | None:
    if not event.pitches:
        return None
    folded = _fold_midi(event.pitches[0], spec.sounding_low, spec.sounding_high)
    return pitch.Pitch(midi=folded + spec.write_semitones)


def _single_staff_from_events(events, detected_key, bpm: float, title: str, spec: InstrumentSpec) -> stream.Score:
    part = stream.Part(id="P1")
    part.partName = ""
    part.partAbbreviation = ""
    inst = music21_instrument(spec)
    inst.instrumentName = ""
    inst.instrumentAbbreviation = ""
    part.insert(0, inst)
    part.insert(0, copy.deepcopy(_written_key(detected_key, spec)))
    part.insert(0, meter.TimeSignature("4/4"))
    part.insert(0, tempo.MetronomeMark(number=bpm))
    part.insert(0, clef.TrebleClef())

    def melody_element(event):
        written = _written_melody_pitch(event, spec)
        if written is None:
            return note.Rest()
        return note.Note(written)

    _write_events(part, events, melody_element)
    _finish_part(part)

    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = title or "草稿谱"
    score.metadata.composer = None
    score.metadata.movementName = None
    score.insert(0, part)
    return score


def _trim_leading_measures(events: list) -> list:
    if not events:
        return events
    shift = int(events[0].onset // 4) * 4
    if shift <= 0:
        return events
    return [
        PianoEvent(
            onset=event.onset - shift,
            duration=event.duration,
            pitches=list(event.pitches),
            hand=event.hand,
        )
        for event in events
    ]


def _rest_pieces(length: float) -> list[float]:
    remain = max(0.0, round(length * 4) / 4)
    pieces: list[float] = []
    while remain >= 0.25 - 1e-9:
        piece = fit_duration(remain)
        if piece <= 0:
            break
        pieces.append(piece)
        remain = round((remain - piece) * 4) / 4
    return pieces


def _append_rests(part, length: float) -> None:
    for quarter_length in _rest_pieces(length):
        rest = note.Rest()
        rest.quarterLength = quarter_length
        part.append(rest)


def _write_events(part, events, element_for) -> None:
    cursor = 0.0
    for event in events:
        if event.onset < cursor - 0.001:
            continue
        if event.onset > cursor + 0.001:
            _append_rests(part, event.onset - cursor)
            cursor = event.onset
        placed = element_for(event)
        if isinstance(placed, note.Rest):
            continue
        legal = fit_duration(max(0.25, float(event.duration)))
        if legal <= 0:
            continue
        placed.quarterLength = legal
        part.append(placed)
        cursor = event.onset + placed.quarterLength
    leftover = (4.0 - (cursor % 4.0)) % 4.0
    if leftover >= 0.25 - 1e-9:
        _append_rests(part, leftover)


def _finish_part(part) -> None:
    try:
        part.makeMeasures(inPlace=True)
    except Exception as exc:
        log.warning("makeMeasures skipped: %s", exc)
        return
    try:
        part.makeBeams(inPlace=True)
    except Exception as exc:
        log.warning("makeBeams skipped: %s", exc)
    try:
        part.makeAccidentals(inPlace=True)
    except Exception as exc:
        log.warning("makeAccidentals skipped: %s", exc)


def _clean_musicxml(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<creator type=\"composer\">.*?</creator>\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"<movement-title>.*?</movement-title>\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"<part-name>.*?</part-name>", "<part-name></part-name>", text)
    text = re.sub(r"<part-abbreviation>.*?</part-abbreviation>", "<part-abbreviation></part-abbreviation>", text)
    text = re.sub(r"<instrument-name>.*?</instrument-name>", "<instrument-name></instrument-name>", text)
    text = re.sub(r"<instrument-abbreviation>.*?</instrument-abbreviation>", "<instrument-abbreviation></instrument-abbreviation>", text)
    path.write_text(text, encoding="utf-8")


def demo_scale_musicxml(instrument_id: str = DEFAULT_INSTRUMENT) -> str:
    spec = get_instrument(instrument_id)
    if spec.grand:
        right = stream.Part(id="P1")
        left = stream.Part(id="P2")
        right.partName = "钢琴"
        left.partName = "钢琴"
        for part in (right, left):
            part.insert(0, instrument.Piano())
            part.insert(0, keymod.Key("C"))
            part.insert(0, meter.TimeSignature("4/4"))
            part.insert(0, tempo.MetronomeMark(number=96))
        right.insert(0, clef.TrebleClef())
        left.insert(0, clef.BassClef())
        treble = [60, 62, 64, 65, 67, 69, 71, 72]
        bass = [48, 50, 52, 53, 55, 57, 59, 60]
        for index, midi_number in enumerate(treble):
            right.insert(index * 0.5, note.Note(midi_number, quarterLength=0.5))
        for index, midi_number in enumerate(bass):
            left.insert(index * 0.5, note.Note(midi_number, quarterLength=0.5))
        score = stream.Score()
        score.insert(0, metadata.Metadata())
        score.metadata.title = "C 大调音阶"
        score.metadata.composer = "有谱了 示例 · 钢琴"
        score.insert(0, right)
        score.insert(0, left)
        score.insert(0, layout.StaffGroup([right, left], name="Piano", symbol="brace"))
    else:
        part = stream.Part(id="P1")
        part.partName = spec.name
        written_key = keymod.Key("C").transpose(spec.write_semitones) if spec.write_semitones else keymod.Key("C")
        part.insert(0, music21_instrument(spec))
        part.insert(0, written_key)
        part.insert(0, meter.TimeSignature("4/4"))
        part.insert(0, tempo.MetronomeMark(number=96))
        part.insert(0, clef.TrebleClef())
        concert = [60, 62, 64, 65, 67, 69, 71, 72]
        for index, midi_number in enumerate(concert):
            folded = _fold_midi(midi_number, spec.sounding_low, spec.sounding_high)
            part.insert(index * 0.5, note.Note(folded + spec.write_semitones, quarterLength=0.5))
        score = stream.Score()
        score.insert(0, metadata.Metadata())
        score.metadata.title = f"{written_key} 音阶"
        score.metadata.composer = f"有谱了 示例 · {spec.name}（{spec.key_label}）"
        score.insert(0, part)

    written = score.write("musicxml")
    return Path(str(written)).read_text(encoding="utf-8")
