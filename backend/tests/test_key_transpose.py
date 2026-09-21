from pathlib import Path

from music21 import converter, key as keymod, meter, note, stream

from app.transpose import detect_written_key, parse_key, transpose_score_file


def _scale_midi(path: Path, pitches: list[int], bpm: float = 120) -> Path:
    import pretty_midi

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


def _scale_xml(path: Path, pitches: list[int], key_name: str = "C") -> Path:
    part = stream.Part(id="P1")
    part.insert(0, keymod.Key(key_name))
    part.insert(0, meter.TimeSignature("4/4"))
    for index, midi_number in enumerate(pitches):
        part.insert(index * 0.5, note.Note(midi_number, quarterLength=0.5))
    score = stream.Score()
    score.insert(0, part)
    score.write("musicxml", fp=str(path))
    return path


def _pitches(xml_path: Path) -> list[int]:
    score = converter.parse(str(xml_path))
    values: list[int] = []
    for item in score.flatten().notes:
        if getattr(item, "tie", None) is not None and item.tie.type in {"stop", "continue"}:
            continue
        if isinstance(item, note.Note):
            values.append(item.pitch.midi)
        else:
            values.extend(p.midi for p in item.pitches)
    return values


def test_parse_key_accepts_twelve_majors():
    assert parse_key("Bb").tonic.pitchClass == 10
    assert parse_key("F#").tonic.pitchClass == 6


def test_c_scale_midi_to_g(tmp_path: Path):
    source = _scale_midi(tmp_path / "c.mid", [60, 62, 64, 65, 67, 69, 71, 72])
    xml_path = tmp_path / "score.musicxml"
    result = transpose_score_file(source, xml_path, tmp_path / "score.mid", "C", "G", "音阶")
    assert result["semitones"] == 7
    assert _pitches(xml_path) == [67, 69, 71, 72, 74, 76, 78, 79]


def test_c_scale_xml_to_f(tmp_path: Path):
    source = _scale_xml(tmp_path / "c.musicxml", [60, 62, 64, 65, 67, 69, 71, 72], "C")
    xml_path = tmp_path / "score.musicxml"
    transpose_score_file(source, xml_path, tmp_path / "score.mid", "C", "F", "音阶")
    assert _pitches(xml_path) == [65, 67, 69, 70, 72, 74, 76, 77]
    keys = list(converter.parse(str(xml_path)).flatten().getElementsByClass(keymod.KeySignature))
    assert keys
    assert keys[0].sharps == -1


def test_same_key_keeps_pitches(tmp_path: Path):
    source = _scale_midi(tmp_path / "same.mid", [64, 67, 71])
    xml_path = tmp_path / "score.musicxml"
    result = transpose_score_file(source, xml_path, tmp_path / "score.mid", "E", "E")
    assert result["semitones"] == 0
    assert _pitches(xml_path) == [64, 67, 71]


def test_detects_written_g_major(tmp_path: Path):
    source = _scale_xml(tmp_path / "g.musicxml", [67, 69, 71], "G")
    score = converter.parse(str(source))
    assert detect_written_key(score) == "G"


def test_midi_without_key_signature_stays_c(tmp_path: Path):
    source = _scale_midi(tmp_path / "c.mid", [60, 62, 64, 65, 67, 69, 71, 72])
    assert detect_written_key(converter.parse(str(source))) == "C"
