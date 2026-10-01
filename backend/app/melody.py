from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi

from .piano import PianoNote

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

    # Cover the low brass and high violin ranges supported by the app.
    # C2..C7 silently excluded tuba fundamentals and violin high notes.
    fmin = librosa.note_to_hz("C1")
    fmax = librosa.note_to_hz("C8")
    if low is not None:
        fmin = max(fmin, float(librosa.midi_to_hz(max(24, low - 7))))
    if high is not None:
        fmax = min(fmax, float(librosa.midi_to_hz(min(108, high + 7))))
    if fmax <= fmin:
        fmin, fmax = librosa.note_to_hz("C1"), librosa.note_to_hz("C8")

    frame_length = max(FRAME_LENGTH, 2 ** int(np.ceil(np.log2(4 * sr / fmin))))

    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio,
        fmin=fmin,
        fmax=fmax,
        sr=sr,
        hop_length=HOP_LENGTH,
        frame_length=frame_length,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=HOP_LENGTH)

    midis: list[int | None] = []
    for freq, voiced, prob in zip(f0, voiced_flag, voiced_probs):
        if bool(voiced) and np.isfinite(freq) and (prob is None or float(prob) >= 0.18):
            midis.append(int(round(float(librosa.hz_to_midi(float(freq))))))
        else:
            midis.append(None)

    # Spectral flux can peak at note releases, especially on high notes.
    # Repetition splitting requires a rise in energy, not a change of timbre.
    from scipy.ndimage import gaussian_filter1d

    rms = librosa.feature.rms(
        y=audio, frame_length=max(2 * HOP_LENGTH, frame_length // 2), hop_length=HOP_LENGTH,
    )[0]
    # A 20 ms energy window alone oscillates at low fundamentals. Smooth
    # across frames so waveform cycles are not treated as note re-attacks.
    rms = gaussian_filter1d(rms, sigma=3)
    attack_strength = np.maximum(np.diff(rms, prepend=0.), 0.)
    attack_strength[attack_strength < float(np.max(attack_strength)) * .1] = 0.
    attacks = librosa.onset.onset_detect(
        onset_envelope=attack_strength, sr=sr, hop_length=HOP_LENGTH, units="time",
    )
    raw = segment_frames(times, midis, attacks)

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
    return apply_range(notes, low, high)


def segment_frames(times, midis, attacks=()) -> list[list[float]]:
    """Debounce pitch changes without adding HOLD_FRAMES of onset latency.

    Bridge at most two missing frames; genuine re-attacks split repeated notes
    even if pYIN remains voiced throughout the attack.
    """
    if len(times) == 0:
        return []
    step = HOP_LENGTH / SAMPLE_RATE
    attack_frames = {int(np.argmin(np.abs(np.asarray(times) - t))) for t in attacks}
    raw = []
    current = None
    pending = None
    pending_count = missing = 0

    def finish(end):
        if current is not None and end - current[0] >= MIN_NOTE_SEC:
            raw.append([current[0], end, current[2]])

    for index, (time, midi) in enumerate(zip(times, midis)):
        time = float(time)
        if midi is None:
            missing += 1
            pending = None
            pending_count = 0
            if current is not None and missing > 2:
                finish(time - (missing - 1) * step)
                current = None
            continue
        missing = 0
        if current is None:
            current = [time, time + step, float(midi)]
            continue
        if midi == int(current[2]):
            if index in attack_frames and time - current[0] >= MIN_NOTE_SEC:
                finish(time)
                current = [time, time + step, float(midi)]
            else:
                current[1] = time + step
            pending = None
            pending_count = 0
            continue
        pending_count = pending_count + 1 if pending == midi else 1
        pending = midi
        if pending_count >= HOLD_FRAMES:
            boundary = time - (HOLD_FRAMES - 1) * step
            finish(boundary)
            current = [boundary, time + step, float(midi)]
            pending = None
            pending_count = 0
    if current is not None:
        finish(current[1])
    return raw


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
