from __future__ import annotations

from pathlib import Path

import pretty_midi
from music21 import chord, clef, converter, note

from app.midi_io import to_concert_midi, to_written_midi
from app.piano import PianoEvent, PianoNote, extract_melody
from app.score import _trim_leading_measures, detect_key, display_title, midi_to_musicxml


def _write_midi(path: Path, pitches: list[int], bpm: float = 80) -> Path:
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=0)
    for index, pitch in enumerate(pitches):
        inst.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=index * 0.5, end=index * 0.5 + 0.4)
        )
    midi.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(path))
    return path


def _part_pitches(xml_path: Path) -> list[int]:
    score = converter.parse(str(xml_path))
    part = list(score.parts)[0]
    values: list[int] = []
    for item in part.flatten().notes:
        if getattr(item, "tie", None) is not None and item.tie.type in {"stop", "continue"}:
            continue
        if isinstance(item, note.Note):
            values.append(item.pitch.midi)
        else:
            values.extend(p.midi for p in item.pitches)
    return values


def test_written_alto_sax_converts_to_concert(tmp_path: Path):
    written = _write_midi(tmp_path / "alto-written.mid", [60])
    concert = tmp_path / "alto-concert.mid"
    to_concert_midi(written, concert, "alto_sax")
    parsed = pretty_midi.PrettyMIDI(str(concert))
    assert parsed.instruments[0].notes[0].pitch == 51


def test_concert_c_writes_d_for_bb_clarinet(tmp_path: Path):
    midi_path = _write_midi(tmp_path / "concert.mid", [60])
    xml_path = tmp_path / "clarinet.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "移调", "clarinet_bb")
    assert result["instrument"] == "clarinet_bb"
    assert 62 in _part_pitches(xml_path)


def test_piano_midi_stays_concert(tmp_path: Path):
    source = _write_midi(tmp_path / "piano.mid", [64, 67])
    dest = tmp_path / "concert.mid"
    to_concert_midi(source, dest, "piano")
    parsed = pretty_midi.PrettyMIDI(str(dest))
    assert [item.pitch for item in parsed.instruments[0].notes] == [64, 67]


def test_c_major_scale_writes_a_major_for_alto_sax(tmp_path: Path):
    concert = [60, 62, 64, 65, 67, 69, 71, 72]
    midi_path = _write_midi(tmp_path / "c-scale.mid", concert, bpm=120)
    xml_path = tmp_path / "alto.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "移调", "alto_sax")
    assert result["instrument"] == "alto_sax"
    assert result["key"].startswith("A")
    assert "minor" not in result["key"].lower()
    assert _part_pitches(xml_path) == [69, 71, 73, 74, 76, 78, 80, 81]


def test_alto_written_to_clarinet_written(tmp_path: Path):
    written = _write_midi(tmp_path / "alto.mid", [60, 62])
    concert = tmp_path / "concert.mid"
    to_concert_midi(written, concert, "alto_sax")
    xml_path = tmp_path / "clarinet.musicxml"
    midi_to_musicxml(concert, xml_path, "换乐器", "clarinet_bb")
    assert _part_pitches(xml_path) == [53, 55]


def test_scoring_does_not_mutate_concert_midi(tmp_path: Path):
    midi_path = _write_midi(tmp_path / "concert.mid", [60, 64, 67])
    before = [item.pitch for item in pretty_midi.PrettyMIDI(str(midi_path)).instruments[0].notes]
    midi_to_musicxml(midi_path, tmp_path / "out.musicxml", "不变", "clarinet_bb")
    after = [item.pitch for item in pretty_midi.PrettyMIDI(str(midi_path)).instruments[0].notes]
    assert before == after == [60, 64, 67]


def test_written_midi_keeps_concert_source(tmp_path: Path):
    concert = _write_midi(tmp_path / "concert.mid", [60])
    dest = tmp_path / "written.mid"
    to_written_midi(concert, dest, "alto_sax")
    assert pretty_midi.PrettyMIDI(str(dest)).instruments[0].notes[0].pitch == 69
    assert pretty_midi.PrettyMIDI(str(concert)).instruments[0].notes[0].pitch == 60


def test_detect_key_prefers_major_for_c_scale():
    key = detect_key([60, 62, 64, 65, 67, 69, 71, 72])
    assert key.tonic.midi % 12 == 0
    assert key.mode == "major"


def _write_simultaneous(path: Path, pitches: list[int], bpm: float = 80) -> Path:
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=0)
    for pitch in pitches:
        inst.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=0.0, end=0.5))
    midi.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(path))
    return path


def test_non_piano_drops_chords_and_keeps_melody(tmp_path: Path):
    midi_path = _write_simultaneous(tmp_path / "chord.mid", [48, 64, 67])
    xml_path = tmp_path / "flute.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "单音", "flute")
    score = converter.parse(str(xml_path))
    assert len(list(score.parts)) == 1
    assert any(isinstance(item, clef.TrebleClef) for item in score.parts[0].flatten().getElementsByClass(clef.Clef))
    assert not any(isinstance(item, chord.Chord) for item in score.parts[0].flatten().notes)
    assert _part_pitches(xml_path) == [67]
    assert result["note_count"] == 1


def test_cello_uses_treble_clef(tmp_path: Path):
    midi_path = _write_midi(tmp_path / "cello.mid", [48, 50, 52])
    xml_path = tmp_path / "cello.musicxml"
    midi_to_musicxml(midi_path, xml_path, "大提琴", "cello")
    score = converter.parse(str(xml_path))
    clefs = list(score.parts[0].flatten().getElementsByClass(clef.Clef))
    assert clefs
    assert all(isinstance(item, clef.TrebleClef) for item in clefs)


def test_ugly_filename_becomes_draft_title():
    assert display_title("v0200fg10000dagm2ifog65lchoooj3g.mp4") == "草稿谱"
    assert display_title("小星星") == "小星星"


def test_trim_leading_measures_keeps_bar_position():
    events = [
        PianoEvent(onset=8.5, duration=0.5, pitches=[72], hand="melody"),
        PianoEvent(onset=9.0, duration=1.0, pitches=[74], hand="melody"),
    ]
    trimmed = _trim_leading_measures(events)
    assert [event.onset for event in trimmed] == [0.5, 1.0]


def test_extract_melody_prefers_continuous_line():
    notes = [
        PianoNote(midi=72, start=0.0, duration=0.4, velocity=88),
        PianoNote(midi=84, start=0.02, duration=0.08, velocity=50),
        PianoNote(midi=48, start=0.03, duration=0.09, velocity=40),
        PianoNote(midi=74, start=0.5, duration=0.4, velocity=86),
        PianoNote(midi=86, start=0.51, duration=0.08, velocity=48),
        PianoNote(midi=76, start=1.0, duration=0.4, velocity=90),
        PianoNote(midi=79, start=1.5, duration=0.4, velocity=87),
    ]
    melody = extract_melody(notes, 60, 84)
    assert [item.midi for item in melody] == [72, 74, 76, 79]


def test_score_xml_has_no_chrome_or_illegal_durations(tmp_path: Path):
    midi_path = _write_midi(tmp_path / "line.mid", [60, 62, 64, 65], bpm=120)
    xml_path = tmp_path / "line.musicxml"
    midi_to_musicxml(midi_path, xml_path, "v0200fg10000dagm2ifog65lchoooj3g.mp4", "flute")
    xml = xml_path.read_text(encoding="utf-8")
    assert "<work-title>草稿谱</work-title>" in xml
    assert "Music21" not in xml
    assert "长笛" not in xml
    assert "<movement-title>" not in xml
    assert "tuplet" not in xml
    assert "time-modification" not in xml
    score = converter.parse(str(xml_path))
    legal = {0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0}
    for item in score.parts[0].flatten().notesAndRests:
        assert float(item.quarterLength) in legal


def test_monophonic_line_has_no_overlapping_notes(tmp_path: Path):
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    for pitch, start, end in ((60, 0.0, 1.2), (64, 0.1, 0.8), (67, 0.15, 0.9), (72, 0.6, 1.4)):
        inst.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=end))
    midi.instruments.append(inst)
    midi_path = tmp_path / "overlap.mid"
    midi.write(str(midi_path))
    xml_path = tmp_path / "overlap.musicxml"
    midi_to_musicxml(midi_path, xml_path, "v0200fg10000dagm2ifog65lchoooj3g", "soprano_sax")
    xml = xml_path.read_text(encoding="utf-8")
    assert "<work-title>草稿谱</work-title>" in xml
    assert "v0200fg10000" not in xml
    score = converter.parse(str(xml_path))
    notes = [item for item in score.parts[0].flatten().notes]
    assert notes
    assert not any(isinstance(item, chord.Chord) for item in notes)
    cursor = 0.0
    for item in notes:
        assert item.offset + 1e-6 >= cursor
        cursor = item.offset + float(item.quarterLength)


def test_piano_keeps_grand_staff_and_both_hands(tmp_path: Path):
    events = []
    for index, (low, high) in enumerate(zip([48, 50, 52, 53], [64, 65, 67, 69])):
        start = index * 0.5
        events.append((low, start, 0.4))
        events.append((high, start, 0.4))
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    for pitch, start, duration in events:
        inst.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + duration))
    midi.instruments.append(inst)
    midi_path = tmp_path / "piano.mid"
    midi.write(str(midi_path))
    xml_path = tmp_path / "piano.musicxml"
    midi_to_musicxml(midi_path, xml_path, "钢琴")
    score = converter.parse(str(xml_path))
    parts = list(score.parts)
    assert len(parts) == 2
    right_clefs = list(parts[0].flatten().getElementsByClass(clef.Clef))
    left_clefs = list(parts[1].flatten().getElementsByClass(clef.Clef))
    assert any(isinstance(item, clef.TrebleClef) for item in right_clefs)
    assert any(isinstance(item, clef.BassClef) for item in left_clefs)
    right = [item.pitch.midi for item in parts[0].flatten().notes if isinstance(item, note.Note)]
    left = [item.pitch.midi for item in parts[1].flatten().notes if isinstance(item, note.Note)]
    assert set([64, 65, 67, 69]).issubset(set(right))
    assert set([48, 50, 52, 53]).issubset(set(left))
