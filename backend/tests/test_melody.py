from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi

from app.melody import track_melody, write_notes_midi
from app.piano import PianoNote
from app.score import midi_to_musicxml


def _sine_scale(path: Path, pitches: list[int], beat: float = 0.5, sr: int = 16000) -> Path:
    import wave

    length = len(pitches) * beat + 0.2
    samples = np.zeros(int(length * sr), dtype=np.float32)
    for index, midi in enumerate(pitches):
        freq = 440.0 * (2 ** ((midi - 69) / 12))
        begin = int((index * beat + 0.02) * sr)
        end = int(((index + 1) * beat - 0.04) * sr)
        t = np.arange(max(0, end - begin)) / sr
        env = np.minimum(t / 0.01, 1.0) * np.minimum((t[::-1] / 0.02), 1.0)
        samples[begin:end] += (np.sin(2 * np.pi * freq * t) * env * 0.35).astype(np.float32)
    peak = np.max(np.abs(samples)) or 1.0
    pcm = (np.clip(samples / peak, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())
    return path


def test_pyin_recovers_sine_scale(tmp_path: Path):
    pitches = [60, 62, 64, 65, 67]
    wav_path = _sine_scale(tmp_path / "scale.wav", pitches)
    found = [item.midi for item in track_melody(wav_path, 55, 80)]
    assert found
    assert max(found) - min(found) <= 8
    for pitch in pitches:
        assert any(abs(item - pitch) <= 1 for item in found)


def test_melody_midi_writes_single_line(tmp_path: Path):
    notes = [
        PianoNote(midi=60, start=0.0, duration=0.4),
        PianoNote(midi=64, start=0.5, duration=0.4),
    ]
    midi_path = write_notes_midi(tmp_path / "melody.mid", notes, bpm=120)
    parsed = pretty_midi.PrettyMIDI(str(midi_path))
    written = [item.pitch for item in parsed.instruments[0].notes]
    assert written == [60, 64]


def test_wav_scoring_stays_monophonic(tmp_path: Path):
    pitches = [67, 65, 64, 62]
    wav_path = _sine_scale(tmp_path / "tune.wav", pitches)
    dummy = pretty_midi.PrettyMIDI()
    dummy.instruments.append(pretty_midi.Instrument(program=0))
    midi_path = tmp_path / "dummy.mid"
    dummy.write(str(midi_path))
    xml_path = tmp_path / "tune.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "小曲", "flute", wav_path=wav_path)
    assert result["note_count"] >= 3
    from music21 import chord, converter, note

    score = converter.parse(str(xml_path))
    notes = list(score.parts[0].flatten().notes)
    assert notes
    assert not any(isinstance(item, chord.Chord) for item in notes)
    assert all(isinstance(item, note.Note) for item in notes)
