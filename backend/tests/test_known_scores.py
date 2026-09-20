from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pretty_midi
from music21 import converter, note

from app.melody import track_melody
from app.piano import PianoNote, merge_unisons
from app.score import midi_to_musicxml

SAMPLE_RATE = 16000
BPM = 120


# Concert-pitch ground truth for public-domain tunes.
# Durations are in quarter-note beats at 120 BPM.
TWINKLE = {
    "name": "小星星",
    "pitches": [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60],
    "beats": [1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2],
    "key": "C major",
}
ODE = {
    "name": "欢乐颂",
    "pitches": [64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62],
    "beats": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 0.5, 2],
    "key": "C major",
}
MARY = {
    "name": "玛丽有只小羊羔",
    "pitches": [64, 62, 60, 62, 64, 64, 64, 62, 62, 62, 64, 67, 67],
    "beats": [1] * 13,
    "key": "C major",
}
SCALE = {
    "name": "C 大调音阶",
    "pitches": [60, 62, 64, 65, 67, 69, 71, 72],
    "beats": [1] * 8,
    "key": "C major",
}


def _events(piece: dict) -> list[tuple[int, float, float]]:
    beat = 60.0 / BPM
    start = 0.0
    events = []
    for pitch, quarters in zip(piece["pitches"], piece["beats"]):
        events.append((pitch, start, quarters * beat * 0.88))
        start += quarters * beat
    return events


def _render_wav(path: Path, events: list[tuple[int, float, float]]) -> Path:
    length = max(start + duration for _, start, duration in events) + 0.3
    samples = np.zeros(int(length * SAMPLE_RATE), dtype=np.float32)
    for midi, start, duration in events:
        freq = 440.0 * (2 ** ((midi - 69) / 12))
        begin = int((start + 0.02) * SAMPLE_RATE)
        end = int((start + duration - 0.03) * SAMPLE_RATE)
        count = max(0, end - begin)
        t = np.arange(count) / SAMPLE_RATE
        env = np.minimum(t / 0.012, 1.0) * np.minimum(t[::-1] / 0.03, 1.0)
        samples[begin:end] += (np.sin(2 * np.pi * freq * t) * env * 0.4).astype(np.float32)
    peak = float(np.max(np.abs(samples)) or 1.0)
    pcm = (np.clip(samples / peak, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return path


def _write_midi(path: Path, events: list[tuple[int, float, float]]) -> Path:
    parsed = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    instrument = pretty_midi.Instrument(program=0)
    for pitch, start, duration in events:
        instrument.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + duration)
        )
    parsed.instruments.append(instrument)
    path.parent.mkdir(parents=True, exist_ok=True)
    parsed.write(str(path))
    return path


def _score_pitches(xml_path: Path) -> list[int]:
    score = converter.parse(str(xml_path))
    values = []
    for item in score.parts[0].flatten().notes:
        if getattr(item, "tie", None) is not None and item.tie.type in {"stop", "continue"}:
            continue
        if isinstance(item, note.Note):
            values.append(item.pitch.midi)
    return values


def _score_durations(xml_path: Path) -> list[float]:
    score = converter.parse(str(xml_path))
    return [
        float(item.quarterLength)
        for item in score.parts[0].flatten().notes
        if isinstance(item, note.Note)
        and not (getattr(item, "tie", None) and item.tie.type in {"stop", "continue"})
    ]


def _pair(tmp_path: Path, piece: dict) -> tuple[Path, Path]:
    events = _events(piece)
    stem = piece["name"]
    return (
        _write_midi(tmp_path / f"{stem}.mid", events),
        _render_wav(tmp_path / f"{stem}.wav", events),
    )


def test_merge_unisons_keeps_repeated_quarters():
    notes = [
        PianoNote(midi=60, start=0.0, duration=0.44, velocity=88),
        PianoNote(midi=60, start=0.5, duration=0.44, velocity=86),
        PianoNote(midi=67, start=1.0, duration=0.44, velocity=90),
    ]
    merged = merge_unisons(notes)
    assert [item.midi for item in merged] == [60, 60, 67]


def test_twinkle_audio_matches_known_score(tmp_path: Path):
    midi_path, wav_path = _pair(tmp_path, TWINKLE)
    assert [item.midi for item in track_melody(wav_path, 55, 84)] == TWINKLE["pitches"]
    xml_path = tmp_path / "twinkle-flute.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, TWINKLE["name"], "flute", wav_path=wav_path)
    assert result["key"] == TWINKLE["key"]
    assert result["bpm"] == BPM
    assert _score_pitches(xml_path) == TWINKLE["pitches"]
    assert _score_durations(xml_path)[:6] == [1.0] * 6


def test_twinkle_midi_and_bb_sax_match_known_score(tmp_path: Path):
    midi_path, wav_path = _pair(tmp_path, TWINKLE)
    concert = tmp_path / "twinkle-midi.musicxml"
    midi_to_musicxml(midi_path, concert, TWINKLE["name"], "flute")
    assert _score_pitches(concert) == TWINKLE["pitches"]

    sax = tmp_path / "twinkle-sax.musicxml"
    result = midi_to_musicxml(midi_path, sax, TWINKLE["name"], "soprano_sax", wav_path=wav_path)
    assert result["key"].startswith("D")
    assert _score_pitches(sax) == [pitch + 2 for pitch in TWINKLE["pitches"]]


def test_ode_to_joy_audio_matches_known_score(tmp_path: Path):
    midi_path, wav_path = _pair(tmp_path, ODE)
    xml_path = tmp_path / "ode.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, ODE["name"], "flute", wav_path=wav_path)
    assert result["key"] == ODE["key"]
    assert _score_pitches(xml_path) == ODE["pitches"]


def test_mary_audio_matches_known_score(tmp_path: Path):
    midi_path, wav_path = _pair(tmp_path, MARY)
    xml_path = tmp_path / "mary.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, MARY["name"], "flute", wav_path=wav_path)
    assert result["key"] == MARY["key"]
    assert _score_pitches(xml_path) == MARY["pitches"]
    assert _score_durations(xml_path) == [1.0] * len(MARY["pitches"])


def test_c_major_scale_audio_writes_alto_sax(tmp_path: Path):
    midi_path, wav_path = _pair(tmp_path, SCALE)
    xml_path = tmp_path / "scale-alto.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, SCALE["name"], "alto_sax", wav_path=wav_path)
    assert result["key"].startswith("A")
    assert "minor" not in result["key"].lower()
    assert _score_pitches(xml_path) == [pitch + 9 for pitch in SCALE["pitches"]]


def test_piano_known_twinkle_keeps_both_hands(tmp_path: Path):
    beat = 60.0 / BPM
    melody = TWINKLE["pitches"]
    bass = [48, 48, 43, 43, 41, 41, 43, 41, 41, 36, 36, 43, 43, 48]
    events = []
    cursor = 0.0
    for high, low, quarters in zip(melody, bass, TWINKLE["beats"]):
        duration = quarters * beat * 0.88
        events.append((high, cursor, duration))
        events.append((low, cursor, duration))
        cursor += quarters * beat
    midi_path = _write_midi(tmp_path / "twinkle-piano.mid", events)
    xml_path = tmp_path / "twinkle-piano.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, TWINKLE["name"], "piano")
    score = converter.parse(str(xml_path))
    parts = list(score.parts)
    assert len(parts) == 2
    right = [item.pitch.midi for item in parts[0].flatten().notes if isinstance(item, note.Note)]
    left = [item.pitch.midi for item in parts[1].flatten().notes if isinstance(item, note.Note)]
    assert right == melody
    assert set(bass).issubset(set(left))
    assert result["key"].startswith("C")
