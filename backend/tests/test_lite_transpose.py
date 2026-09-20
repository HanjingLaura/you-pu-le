from pathlib import Path

import pretty_midi

from app.lite_transpose import detect_written_key_lite, transpose_score_file_lite


def _scale_midi(path: Path, pitches: list[int], bpm: float = 120) -> Path:
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


def _scale_xml(path: Path, pitches: list[int], fifths: int = 0) -> Path:
    notes = []
    for midi_number in pitches:
        pc = midi_number % 12
        names = ["C", "C", "D", "E", "E", "F", "F", "G", "A", "A", "B", "B"]
        alters = [0, 1, 0, -1, 0, 0, 1, 0, -1, 0, -1, 0]
        step = names[pc]
        alter = alters[pc]
        octave = midi_number // 12 - 1
        alter_xml = f"<alter>{alter}</alter>" if alter else ""
        notes.append(
            f"<note><pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
            "<duration>2</duration><type>eighth</type></note>"
        )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="3.1"><part-list><score-part id="P1">'
        "<part-name></part-name></score-part></part-list><part id=\"P1\">"
        '<measure number="1"><attributes><divisions>2</divisions>'
        f"<key><fifths>{fifths}</fifths></key>"
        "<time><beats>4</beats><beat-type>4</beat-type></time>"
        "<clef><sign>G</sign><line>2</line></clef></attributes>"
        f"{''.join(notes)}</measure></part></score-partwise>",
        encoding="utf-8",
    )
    return path


def _pitches_from_xml(path: Path) -> list[int]:
    import xml.etree.ElementTree as ET

    values: list[int] = []
    step_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    for pitch in ET.parse(path).getroot().iter():
        if pitch.tag.rsplit("}", 1)[-1] != "pitch":
            continue
        step = alter = octave = None
        for child in pitch:
            name = child.tag.rsplit("}", 1)[-1]
            if name == "step":
                step = child.text
            elif name == "alter" and child.text:
                alter = int(child.text)
            elif name == "octave" and child.text:
                octave = int(child.text)
        if step is None or octave is None:
            continue
        values.append(12 * (octave + 1) + step_pc.get(step, 0) + (alter or 0))
    return values


def test_lite_c_scale_midi_to_g(tmp_path: Path):
    source = _scale_midi(tmp_path / "c.mid", [60, 62, 64, 65, 67, 69, 71, 72])
    result = transpose_score_file_lite(
        source, tmp_path / "score.musicxml", tmp_path / "score.mid", "C", "G", "音阶"
    )
    assert result["semitones"] == 7
    assert _pitches_from_xml(tmp_path / "score.musicxml") == [67, 69, 71, 72, 74, 76, 78, 79]


def test_lite_c_scale_xml_to_f(tmp_path: Path):
    source = _scale_xml(tmp_path / "c.musicxml", [60, 62, 64, 65, 67, 69, 71, 72], 0)
    transpose_score_file_lite(source, tmp_path / "score.musicxml", tmp_path / "score.mid", "C", "F", "音阶")
    assert _pitches_from_xml(tmp_path / "score.musicxml") == [65, 67, 69, 70, 72, 74, 76, 77]
    text = (tmp_path / "score.musicxml").read_text(encoding="utf-8")
    assert "<fifths>-1</fifths>" in text


def test_lite_same_key_keeps_pitches(tmp_path: Path):
    source = _scale_midi(tmp_path / "same.mid", [64, 67, 71])
    result = transpose_score_file_lite(source, tmp_path / "score.musicxml", tmp_path / "score.mid", "E", "E")
    assert result["semitones"] == 0
    assert _pitches_from_xml(tmp_path / "score.musicxml") == [64, 67, 71]


def test_lite_detects_written_g_major(tmp_path: Path):
    source = _scale_xml(tmp_path / "g.musicxml", [67, 69, 71], 1)
    assert detect_written_key_lite(source) == "G"


def test_lite_midi_without_key_signature_stays_c(tmp_path: Path):
    source = _scale_midi(tmp_path / "c.mid", [60, 62, 64, 65, 67, 69, 71, 72])
    assert detect_written_key_lite(source) == "C"
