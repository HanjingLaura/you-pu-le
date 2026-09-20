from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi

from .piano import PianoNote, merge_unisons

SAMPLE_RATE = 16000
HOP_LENGTH = 160
FRAME_LENGTH = 1024
MIN_NOTE_SEC = 0.07
HOLD_FRAMES = 3


def track_melody(wav_path, low: int | None = None, high: int | None = None) -> list[PianoNote]:
    import librosa

    audio, sr = librosa.load(path=str(wav_path), sr=SAMPLE_RATE, mono=True)
    if audio.size == 0:
        return []

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.95

    fmin = librosa.note_to_hz("C2")
    fmax = librosa.note_to_hz("C7")
    if low is not None:
        fmin = max(fmin, float(librosa.midi_to_hz(max(24, low - 7))))
    if high is not None:
        fmax = min(fmax, float(librosa.midi_to_hz(min(108, high + 7))))
    if fmax <= fmin:
        fmin, fmax = librosa.note_to_hz("C2"), librosa.note_to_hz("C7")

    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio,
        fmin=fmin,
        fmax=fmax,
        sr=sr,
        hop_length=HOP_LENGTH,
        frame_length=FRAME_LENGTH,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=HOP_LENGTH)

    midis: list[int | None] = []
    for freq, voiced, prob in zip(f0, voiced_flag, voiced_probs):
        if bool(voiced) and np.isfinite(freq) and (prob is None or float(prob) >= 0.18):
            midis.append(int(round(float(librosa.hz_to_midi(float(freq))))))
        else:
            midis.append(None)

    raw: list[list[float]] = []
    current: list[float] | None = None
    pending: int | None = None
    pending_count = 0
    for time, midi in zip(times, midis):
        if midi is None:
            if current is not None:
                current[1] = float(time)
                if current[1] - current[0] >= MIN_NOTE_SEC:
                    raw.append(current)
                current = None
            pending = None
            pending_count = 0
            continue
        if current is None:
            current = [float(time), float(time), float(midi)]
            continue
        if midi == int(current[2]):
            current[1] = float(time)
            pending = None
            pending_count = 0
            continue
        pending_count = pending_count + 1 if pending == midi else 1
        pending = midi
        if pending_count >= HOLD_FRAMES:
            current[1] = float(time)
            if current[1] - current[0] >= MIN_NOTE_SEC:
                raw.append(current)
            current = [float(time), float(time), float(midi)]
            pending = None
            pending_count = 0
        else:
            current[1] = float(time)
    if current is not None and current[1] - current[0] >= MIN_NOTE_SEC:
        raw.append(current)

    notes = [
        PianoNote(
            midi=int(item[2]),
            start=float(item[0]),
            duration=float(item[1] - item[0]),
            velocity=84,
            hand="melody",
        )
        for item in raw
    ]
    return apply_range(merge_unisons(notes), low, high)


def apply_range(notes: list[PianoNote], low: int | None, high: int | None) -> list[PianoNote]:
    if low is None or high is None:
        return notes
    adjusted: list[PianoNote] = []
    for item in notes:
        midi = item.midi
        if low <= midi <= high:
            pass
        elif low <= midi - 12 <= high:
            midi -= 12
        elif low <= midi + 12 <= high:
            midi += 12
        elif midi < low - 7 or midi > high + 7:
            continue
        else:
            while midi < low:
                midi += 12
            while midi > high:
                midi -= 12
        adjusted.append(
            PianoNote(
                midi=midi,
                start=item.start,
                duration=item.duration,
                velocity=item.velocity,
                hand="melody",
            )
        )
    return adjusted


def write_notes_midi(path: Path, notes: list[PianoNote], bpm: float = 80) -> Path:
    parsed = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    instrument = pretty_midi.Instrument(program=0)
    for item in notes:
        end = item.start + max(0.05, item.duration)
        instrument.notes.append(
            pretty_midi.Note(
                velocity=int(max(1, min(127, item.velocity))),
                pitch=int(max(0, min(127, item.midi))),
                start=float(item.start),
                end=float(end),
            )
        )
    parsed.instruments.append(instrument)
    path.parent.mkdir(parents=True, exist_ok=True)
    parsed.write(str(path))
    return path
