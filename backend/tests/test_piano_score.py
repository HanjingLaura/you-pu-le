from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi
from music21 import converter, note

from app.piano import PianoNote, assign_hands, estimate_bpm, load_notes, to_events
from app.score import midi_to_musicxml


FIX = Path(__file__).resolve().parent / "fixtures"
FIX.mkdir(exist_ok=True)


def _write_midi(path: Path, events: list[tuple[int, float, float]], bpm: float = 80) -> Path:
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=0)
    for pitch, start, duration in events:
        inst.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + duration)
        )
    midi.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(path))
    return path


def _hands(path: Path, bpm: float = 80):
    return to_events(load_notes(path), bpm)


def _staff_pitches(xml_path: Path) -> tuple[list[int], list[int]]:
    score = converter.parse(str(xml_path))
    parts = list(score.parts)
    assert len(parts) == 2
    right = [item.pitch.midi for item in parts[0].flatten().notes if isinstance(item, note.Note)]
    right += [p.midi for item in parts[0].flatten().notes if not isinstance(item, note.Note) for p in item.pitches]
    left = [item.pitch.midi for item in parts[1].flatten().notes if isinstance(item, note.Note)]
    left += [p.midi for item in parts[1].flatten().notes if not isinstance(item, note.Note) for p in item.pitches]
    return sorted(right), sorted(left)


def test_two_hand_scale_keeps_left_below_right(tmp_path: Path):
    events = []
    beat = 0.75
    for index, (low, high) in enumerate(zip([48, 50, 52, 53, 55, 57, 59, 60], [60, 62, 64, 65, 67, 69, 71, 72])):
        start = index * beat
        events.append((low, start, 0.6))
        events.append((high, start, 0.6))
    midi_path = _write_midi(tmp_path / "scale.mid", events)
    grouped = _hands(midi_path)
    left = [p for ev in grouped if ev.hand == "left" for p in ev.pitches]
    right = [p for ev in grouped if ev.hand == "right" for p in ev.pitches]
    assert min(right) >= 60
    assert max(left) <= 60
    assert 48 in left and 72 in right


def test_melody_crossing_c4_stays_in_right_hand(tmp_path: Path):
    events = []
    melody = [67, 65, 64, 62, 60, 59, 57, 55]
    bass = [48, 43, 48, 43, 48, 43, 48, 43]
    for index, (high, low) in enumerate(zip(melody, bass)):
        start = index * 0.5
        events.append((high, start, 0.45))
        events.append((low, start, 0.45))
    midi_path = _write_midi(tmp_path / "crossing.mid", events, bpm=120)
    grouped = _hands(midi_path, bpm=120)
    right = [p for ev in grouped if ev.hand == "right" for p in ev.pitches]
    left = [p for ev in grouped if ev.hand == "left" for p in ev.pitches]
    assert set(melody).issubset(set(right))
    assert set(bass).issubset(set(left))
    assert 55 in right
    assert 59 not in left


def test_lh_octave_c4_stays_left(tmp_path: Path):
    events = [
        (48, 0.0, 1.0),
        (60, 0.0, 1.0),
        (64, 0.0, 1.0),
        (67, 0.0, 1.0),
        (48, 1.0, 1.0),
        (60, 1.0, 1.0),
        (65, 1.0, 1.0),
        (69, 1.0, 1.0),
    ]
    midi_path = _write_midi(tmp_path / "octave.mid", events)
    grouped = _hands(midi_path)
    first_left = next(ev for ev in grouped if ev.hand == "left" and ev.onset == 0)
    first_right = next(ev for ev in grouped if ev.hand == "right" and ev.onset == 0)
    assert 48 in first_left.pitches
    assert 60 in first_left.pitches
    assert 64 in first_right.pitches
    assert 67 in first_right.pitches


def test_alberti_and_melody_known_score(tmp_path: Path):
    events = []
    alberti = [48, 55, 52, 55]
    melody = [64, 62, 60, 62, 64, 64, 64]
    for index, pitch in enumerate(alberti * 2):
        events.append((pitch, index * 0.25, 0.22))
    for index, pitch in enumerate(melody):
        events.append((pitch, index * 0.5, 0.45))
    midi_path = _write_midi(tmp_path / "alberti.mid", events, bpm=80)
    xml_path = tmp_path / "alberti.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "小星星片段")
    right, left = _staff_pitches(xml_path)
    assert set(melody).issubset(set(right))
    assert set(alberti).issubset(set(left))
    assert result["instrument"] == "piano"
    assert "C" in result["key"] or result["key"].startswith("C")


def test_bach_style_broken_chord_right_hand(tmp_path: Path):
    pattern = [60, 64, 67, 72, 76, 67, 72, 76]
    events = [(36, 0.0, 2.0)]
    for index, pitch in enumerate(pattern):
        events.append((pitch, index * 0.25, 0.22))
    midi_path = _write_midi(tmp_path / "prelude.mid", events, bpm=80)
    grouped = _hands(midi_path)
    right = [p for ev in grouped if ev.hand == "right" for p in ev.pitches]
    left = [p for ev in grouped if ev.hand == "left" for p in ev.pitches]
    assert set(pattern).issubset(set(right))
    assert 36 in left
    assert 60 not in left


def test_assign_hands_prefers_gap_over_c4():
    notes = [
        PianoNote(midi=47, start=0.0, duration=0.5),
        PianoNote(midi=51, start=0.0, duration=0.5),
        PianoNote(midi=54, start=0.0, duration=0.5),
        PianoNote(midi=66, start=0.0, duration=0.5),
        PianoNote(midi=70, start=0.0, duration=0.5),
    ]
    assigned = assign_hands(notes)
    left = {item.midi for item in assigned if item.hand == "left"}
    right = {item.midi for item in assigned if item.hand == "right"}
    assert left == {47, 51, 54}
    assert right == {66, 70}


def test_known_score_matches_synthesized_audio_pitches(tmp_path: Path):
    melody = [64, 62, 60, 62, 64, 64, 64]
    bass = [48, 48, 48, 48, 48, 48, 48]
    events = []
    for index, (high, low) in enumerate(zip(melody, bass)):
        start = index * 0.5
        events.append((high, start, 0.4))
        events.append((low, start, 0.4))
    midi_path = _write_midi(tmp_path / "known.mid", events, bpm=120)
    wav_path = tmp_path / "known.wav"
    _render_sine_wav(events, wav_path, bpm=120)
    recovered = _pitches_from_wav(wav_path, starts=[index * 0.5 for index in range(len(melody))])
    for expected_high, expected_low, found in zip(melody, bass, recovered):
        assert expected_low in found or expected_low - 12 in found
        assert expected_high in found or any(abs(item - expected_high) <= 1 for item in found)
    xml_path = tmp_path / "known.musicxml"
    midi_to_musicxml(midi_path, xml_path, "对照")
    right, left = _staff_pitches(xml_path)
    assert set(melody).issubset(set(right))
    assert 48 in left


def _render_sine_wav(events: list[tuple[int, float, float]], path: Path, bpm: float, sr: int = 16000) -> None:
    import wave

    length = max(start + duration for _, start, duration in events) + 0.4
    samples = np.zeros(int(length * sr), dtype=np.float32)
    for pitch, start, duration in events:
        freq = 440.0 * (2 ** ((pitch - 69) / 12))
        begin = int(start * sr)
        end = int((start + duration) * sr)
        t = np.arange(end - begin) / sr
        env = np.minimum(t / 0.01, 1.0) * np.exp(-t * 2.2)
        tone = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
        samples[begin:end] += (tone * env * 0.22).astype(np.float32)
    peak = np.max(np.abs(samples)) or 1.0
    pcm = (np.clip(samples / peak, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


def _pitches_from_wav(path: Path, starts: list[float], sr: int = 16000) -> list[set[int]]:
    import wave

    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
        assert handle.getframerate() == sr
    found = []
    for start in starts:
        begin = int((start + 0.05) * sr)
        end = int((start + 0.35) * sr)
        chunk = audio[begin:end]
        if chunk.size < 256:
            found.append(set())
            continue
        mag = np.abs(np.fft.rfft(chunk * np.hanning(chunk.size)))
        freqs = np.fft.rfftfreq(chunk.size, 1 / sr)
        peaks = np.argsort(mag)[-6:]
        midis = set()
        for idx in peaks:
            freq = freqs[idx]
            if freq < 40 or freq > 2000:
                continue
            midi = int(round(69 + 12 * np.log2(freq / 440.0)))
            if 36 <= midi <= 84:
                midis.add(midi)
        found.append(midis)
    return found


def test_bpm_from_known_pulse():
    notes = [PianoNote(midi=60, start=index * 0.5, duration=0.4) for index in range(8)]
    bpm = estimate_bpm(notes)
    assert 100 <= bpm <= 140


def test_c_major_scale_known_key_and_hands(tmp_path: Path):
    events = []
    for index, (low, high) in enumerate(zip([48, 50, 52, 53, 55, 57, 59, 60], [60, 62, 64, 65, 67, 69, 71, 72])):
        start = index * 0.5
        events.append((low, start, 0.4))
        events.append((high, start, 0.4))
    midi_path = _write_midi(tmp_path / "c-major.mid", events, bpm=120)
    xml_path = tmp_path / "c-major.musicxml"
    result = midi_to_musicxml(midi_path, xml_path, "C 大调音阶")
    right, left = _staff_pitches(xml_path)
    assert set([60, 62, 64, 65, 67, 69, 71, 72]).issubset(set(right))
    assert set([48, 50, 52, 53, 55, 57, 59]).issubset(set(left))
    assert result["key"].startswith("C")
    assert "minor" not in result["key"].lower()
