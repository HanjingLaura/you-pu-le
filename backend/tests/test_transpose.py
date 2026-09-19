from __future__ import annotations

from pathlib import Path

import pretty_midi
from music21 import converter, note

from app.midi_io import to_concert_midi, to_written_midi
from app.score import detect_key, midi_to_musicxml


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
