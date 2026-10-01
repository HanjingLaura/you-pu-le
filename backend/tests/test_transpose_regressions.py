from pathlib import Path

import mido
import pretty_midi
import pytest
from music21 import converter, key, meter, note, stream, tempo

from app.keys import TransposeError, semitones_between
from app.lite_transpose import transpose_score_file_lite
from app.transpose import transpose_midi, transpose_score_file


def test_nearest_interval():
    assert semitones_between("C", "B") == -1
    assert semitones_between("B", "C") == 1
    assert semitones_between("C", "G") == -5


def test_midi_preserves_tempo_drums_controls_and_ticks(tmp_path: Path):
    midi = mido.MidiFile(ticks_per_beat=960)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.extend([
        mido.MetaMessage("set_tempo", tempo=750000),
        mido.MetaMessage("key_signature", key="C"),
        mido.Message("control_change", control=64, value=127),
        mido.Message("note_on", channel=0, note=60, velocity=80),
        mido.Message("note_on", channel=9, note=36, velocity=100),
        mido.Message("note_off", channel=0, note=60, time=720),
        mido.MetaMessage("set_tempo", tempo=500000),
        mido.Message("note_off", channel=9, note=36, time=240),
    ])
    source = tmp_path / "source.mid"
    dest = tmp_path / "dest.mid"
    midi.save(str(source))
    transpose_midi(source, dest, -1)
    result = mido.MidiFile(str(dest))
    assert result.ticks_per_beat == 960
    for before, after in zip(midi.tracks[0], result.tracks[0]):
        assert before.time == after.time
        if before.type in {"note_on", "note_off"} and before.channel != 9:
            assert after.note == before.note - 1
        elif before.type == "key_signature":
            assert after.key == "B"
        else:
            assert before == after


def test_out_of_range_does_not_clamp(tmp_path):
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(0)
    inst.notes.append(pretty_midi.Note(90, 0, 0, 1))
    midi.instruments.append(inst)
    source = tmp_path / "source.mid"
    midi.write(str(source))
    with pytest.raises(TransposeError):
        transpose_midi(source, tmp_path / "out.mid", -1)


@pytest.mark.parametrize("engine", [transpose_score_file, transpose_score_file_lite])
def test_xml_parts_ties_and_tempo_survive(engine, tmp_path):
    score = stream.Score()
    for index, pitch in enumerate([60, 48]):
        part = stream.Part(id=f"P{index}")
        part.insert(0, key.Key("C"))
        part.insert(0, meter.TimeSignature("3/4"))
        part.insert(0, tempo.MetronomeMark(number=90))
        part.insert(0, note.Note(pitch, quarterLength=4))
        score.insert(0, part)
    source = tmp_path / "source.musicxml"
    score.write("musicxml", fp=str(source))
    dest = tmp_path / "dest.musicxml"
    midi_path = tmp_path / "out.mid"
    engine(source, dest, midi_path, "C", "B")
    result = converter.parse(str(dest))
    assert len(result.parts) == 2
    for part, expected in zip(result.parts, [59, 47]):
        assert {n.pitch.midi for n in part.recurse().notes} == {expected}
        assert sum(float(n.quarterLength) for n in part.recurse().notes) == 4
        assert any(n.tie is not None for n in part.recurse().notes)
        signatures = list(part.recurse().getElementsByClass(key.KeySignature))
        assert len(signatures) == 1 and signatures[0].sharps == 5
    parsed = pretty_midi.PrettyMIDI(str(midi_path))
    assert parsed.get_tempo_changes()[1][0] == pytest.approx(90, abs=.01)
    assert {n.start for inst in parsed.instruments for n in inst.notes} == {0.}
