from pathlib import Path

import mido
import numpy as np
import pretty_midi
import pytest

from app.melody import segment_frames
from app.piano import PianoNote, estimate_bpm, prepare_piano, quantize_voice
from app.rhythm import BeatGrid, constant_grid, midi_grid, score_grid


def test_midi_eighths_use_encoded_tempo(tmp_path: Path):
    midi = pretty_midi.PrettyMIDI(initial_tempo=90)
    inst = pretty_midi.Instrument(0)
    for i in range(12):
        inst.notes.append(pretty_midi.Note(90, 60 + i % 5, i / 3, i / 3 + .28))
    midi.instruments.append(inst)
    path = tmp_path / "eighths.mid"
    midi.write(str(path))
    events, bpm = prepare_piano(path)
    assert bpm == pytest.approx(90, abs=.01)
    assert [e.onset for e in events] == [i * .5 for i in range(12)]


def test_midi_tempo_change_keeps_quarter_positions(tmp_path):
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.extend([
        mido.MetaMessage("set_tempo", tempo=500000),
        mido.Message("note_on", note=60, velocity=80),
        mido.Message("note_off", note=60, time=480),
        mido.MetaMessage("set_tempo", tempo=1000000),
        mido.Message("note_on", note=62, velocity=80),
        mido.Message("note_off", note=62, time=480),
    ])
    path = tmp_path / "tempo.mid"
    midi.save(str(path))
    grid = midi_grid(path)
    assert [grid.position(t) for t in (0, .5, 1.5)] == pytest.approx([0, 1, 2])
    events, _ = prepare_piano(path)
    assert [e.duration for e in events] == [1., 1.]


def test_monophonic_sixteenths_and_dotted_eighth_survive():
    notes = [PianoNote(60, 0, .375), PianoNote(62, .375, .125), PianoNote(64, .5, .125)]
    events = quantize_voice(notes, 120, grid=constant_grid(120))
    assert [e.onset for e in events] == [0, .75, 1.]
    assert [e.duration for e in events] == [.75, .25, .25]


def test_fast_repeated_sixteenths_remain_separate():
    notes = [PianoNote(60, i / 12, .075) for i in range(8)]
    events = quantize_voice(notes, 180, grid=constant_grid(180))
    assert len(events) == 8
    assert [e.onset for e in events] == [i * .25 for i in range(8)]


def test_early_release_does_not_turn_quarters_into_dotted_eighths():
    notes = [PianoNote(60, i * .5, .4) for i in range(4)]
    events = quantize_voice(notes, 120, grid=constant_grid(120))
    assert [e.duration for e in events] == [1.] * 4


def test_variable_beat_grid_and_extrapolation():
    grid = BeatGrid(np.array([.2, .7, 1.3, 2.]), np.arange(4.), 120, "audio")
    assert grid.position(.95) == pytest.approx(1.4166666667)
    assert grid.position(2.7) == pytest.approx(4.)


def test_chord_attack_spread_does_not_set_tempo():
    notes = [PianoNote(p, i * .5 + j * .01, .4) for i in range(16) for j, p in enumerate([48, 60, 64])]
    assert estimate_bpm(notes) == 120


def test_pitch_segmentation_bridges_dropouts_and_backdates_change():
    times = np.arange(30) * .01
    midis = [60] * 10 + [None] * 2 + [60] * 8 + [62] * 10
    raw = segment_frames(times, midis)
    assert len(raw) == 2
    assert raw[0][1] == pytest.approx(.2)
    assert raw[1][0] == pytest.approx(.2)


def test_repeated_legato_pitch_is_split_at_attack():
    raw = segment_frames(np.arange(40) * .01, [60] * 40, [.2])
    assert [r[0] for r in raw] == pytest.approx([0, .2])


def test_audio_failure_uses_note_timing(tmp_path):
    notes = [PianoNote(60, .7 + i * .5, .4) for i in range(8)]
    grid = score_grid(tmp_path / "unused.mid", notes, tmp_path / "missing.wav")
    assert grid.source == "notes-fallback"
    assert grid.position(.7) == pytest.approx(0)


def test_audio_clicks_find_tempo_with_leading_silence(tmp_path):
    import soundfile as sf
    from app.rhythm import audio_grid

    sr = 22050
    origin = .63
    notes = [PianoNote(60, origin + i * .5, .4) for i in range(24)]
    audio = np.zeros(int((origin + 12.5) * sr))
    attack = np.random.default_rng(4).normal(size=1100) * np.exp(-np.arange(1100) / 150)
    for n in notes:
        start = int(n.start * sr)
        audio[start:start + len(attack)] += attack
    path = tmp_path / "pulse.wav"
    sf.write(str(path), audio, sr)
    grid = audio_grid(path, notes)
    assert grid.source == "audio"
    assert grid.bpm == pytest.approx(120, abs=4)
    positions = np.array([grid.position(n.start) for n in notes])
    assert np.max(np.abs(np.diff(positions)[2:-2] - 1)) < .12
    assert 0 <= positions[0] < 1
