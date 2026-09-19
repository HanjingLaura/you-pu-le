from __future__ import annotations

from pathlib import Path

import pretty_midi
from music21 import converter, note

from app.midi_io import to_concert_midi
from app.score import midi_to_musicxml


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
