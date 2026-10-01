"""Performance seconds -> score beats, independently of pitch inference.

MIDI tempo maps are authoritative. Audio uses librosa's dynamic programming
beat tracker; octave candidates are compared against grouped note attacks.
No onset-only estimator can uniquely distinguish quarters from eighths.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pretty_midi

log = logging.getLogger("keyprint")


@dataclass
class BeatGrid:
    seconds: np.ndarray
    quarters: np.ndarray
    bpm: float
    source: str

    def position(self, seconds: float) -> float:
        x, y = self.seconds, self.quarters
        if seconds < x[0]:
            return float(y[0] + (seconds - x[0]) * (y[1] - y[0]) / (x[1] - x[0]))
        if seconds > x[-1]:
            return float(y[-1] + (seconds - x[-1]) * (y[-1] - y[-2]) / (x[-1] - x[-2]))
        return float(np.interp(seconds, x, y))


def constant_grid(bpm: float, origin: float = 0.0, source: str = "notes") -> BeatGrid:
    if not np.isfinite(bpm) or bpm <= 0:
        raise ValueError("速度必须是正数。")
    return BeatGrid(np.array([origin, origin + 60 / bpm]), np.array([0., 1.]), float(bpm), source)


def midi_grid(path) -> BeatGrid:
    midi = pretty_midi.PrettyMIDI(str(path))
    times, tempi = midi.get_tempo_changes()
    end = max(float(midi.get_end_time()), float(times[-1]) + 1.)
    seconds = np.append(times, end)
    quarters = np.concatenate(([0.], np.cumsum(np.diff(seconds) * tempi / 60.)))
    return BeatGrid(seconds, quarters, float(tempi[0]), "midi")


def grouped_onsets(notes) -> np.ndarray:
    starts = sorted(float(n.start) for n in notes if np.isfinite(n.start))
    groups: list[list[float]] = []
    for start in starts:
        if groups and start - groups[-1][0] <= .045:
            groups[-1].append(start)
        else:
            groups.append([start])
    return np.array([np.median(group) for group in groups])


def estimate_note_bpm(notes) -> float:
    onsets = grouped_onsets(notes)
    if len(onsets) < 3:
        return 80.
    gaps = np.diff(onsets)
    gaps = gaps[(gaps > .09) & (gaps < 2.)]
    if not len(gaps):
        return 80.
    candidates = set()
    for gap in gaps:
        for subdivision in (.25, .5, 1., 2.):
            bpm = 60 * subdivision / gap
            if 40 <= bpm <= 200:
                candidates.add(round(bpm, 1))
    if not candidates:
        return 80.
    # Use the whole sequence rather than the most frequent single IOI.
    # Prefer quarter-note interpretations when the sequence is ambiguous.
    def cost(bpm):
        beats = gaps * bpm / 60
        legal = np.array([.25, .5, .75, 1., 1.5, 2., 3., 4.])
        distances = np.abs(beats[:, None] - legal)
        indices = distances.argmin(axis=1)
        error = np.minimum(distances.min(axis=1), .5).mean()
        complexity = np.mean(np.abs(np.log2(legal[indices])))
        return error + .035 * complexity
    return float(round(min(candidates, key=lambda bpm: (cost(bpm), abs(bpm - 100)))))


def audio_grid(path, notes, bpm: float | None = None) -> BeatGrid:
    import librosa

    audio, sr = librosa.load(str(path), sr=22050, mono=True)
    fallback = bpm or estimate_note_bpm(notes)
    onsets = grouped_onsets(notes)
    origin = float(onsets[0]) if len(onsets) else 0.
    if not len(audio) or np.max(np.abs(audio)) < 1e-7:
        return constant_grid(fallback, origin, "notes-fallback")
    hop = 256
    envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop)
    if bpm is None:
        estimated = librosa.feature.tempo(onset_envelope=envelope, sr=sr, hop_length=hop)
        base = float(np.asarray(estimated).reshape(-1)[0])
        candidates = [value for value in (base / 2, base, base * 2) if 40 <= value <= 200]
    else:
        candidates = [bpm]
    best = None
    for candidate in candidates:
        _, beats = librosa.beat.beat_track(onset_envelope=envelope, sr=sr,
            hop_length=hop, bpm=candidate, trim=False, units="time", tightness=60)
        if len(beats) < 3:
            continue
        beats = np.asarray(beats, dtype=float)
        grid = BeatGrid(beats, np.arange(len(beats), dtype=float), float(candidate), "audio")
        positions = np.array([grid.position(t) for t in onsets])
        # Frame-based tracking has a small constant attack latency. Correct
        # only the median residual, retaining the detected local tempo curve.
        residual = positions - np.round(positions * 4) / 4
        if len(residual):
            grid.quarters -= float(np.median(residual))
            positions -= float(np.median(residual))
        # There is no reliable downbeat/metre evidence here. Use the first
        # attack as the draft origin rather than writing recording silence.
        grid.quarters -= grid.position(origin)
        centered = residual - np.median(residual) if len(residual) else residual
        error = float(np.mean(np.minimum(np.abs(centered), .125))) if len(residual) else 0.
        # Mild prior resolves some half/double tempo ambiguities; do not
        # claim to infer a musical metre from pitch attack spacing alone.
        cost = error + .015 * abs(np.log2(candidate / fallback))
        if best is None or cost < best[0]:
            best = (cost, grid)
    return best[1] if best else constant_grid(fallback, origin, "notes-fallback")


def score_grid(midi_path, notes, wav_path=None, bpm=None) -> BeatGrid:
    if wav_path is not None:
        try:
            return audio_grid(wav_path, notes, bpm)
        except Exception:
            log.exception("Audio beat tracking failed; using note timing")
            origin = float(grouped_onsets(notes)[0]) if notes else 0.
            return constant_grid(bpm or estimate_note_bpm(notes), origin, "notes-fallback")
    return constant_grid(bpm, source="manual") if bpm is not None else midi_grid(midi_path)
