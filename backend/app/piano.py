from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pretty_midi

SPLIT_CENTER = 60
ONSET_WINDOW = 0.045
MIN_GAP = 7
HAND_SPAN = 16
MIN_DURATION = 0.05


@dataclass
class PianoNote:
    midi: int
    start: float
    duration: float
    velocity: int = 80
    hand: str = "right"


@dataclass
class PianoEvent:
    onset: float
    duration: float
    pitches: list[int]
    hand: str


def load_notes(midi_path) -> list[PianoNote]:
    parsed = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[PianoNote] = []
    for inst in parsed.instruments:
        if inst.is_drum:
            continue
        for item in inst.notes:
            duration = item.end - item.start
            if duration <= 0.02:
                continue
            notes.append(
                PianoNote(
                    midi=int(item.pitch),
                    start=float(item.start),
                    duration=float(duration),
                    velocity=int(item.velocity),
                )
            )
    notes.sort(key=lambda item: (item.start, item.midi))
    return notes


def estimate_bpm(notes: list[PianoNote]) -> float:
    if len(notes) < 4:
        return 80.0
    onsets = np.array(sorted({round(item.start, 4) for item in notes}), dtype=float)
    if onsets.size < 3:
        return 80.0
    iois = np.diff(onsets)
    iois = iois[(iois > 0.12) & (iois < 1.6)]
    if iois.size == 0:
        return 80.0
    spread = float(np.percentile(iois, 75) - np.percentile(iois, 25))
    if spread < 0.08:
        beat = float(np.median(iois))
    else:
        hist, edges = np.histogram(iois, bins=18)
        beat = float((edges[int(np.argmax(hist))] + edges[int(np.argmax(hist)) + 1]) / 2)
    bpm = 60.0 / beat
    while bpm < 52:
        bpm *= 2
    while bpm > 168:
        bpm /= 2
    return float(max(52, min(168, round(bpm))))


def _group_onsets(notes: list[PianoNote]) -> list[list[PianoNote]]:
    groups: list[list[PianoNote]] = []
    for item in notes:
        if groups and abs(item.start - groups[-1][0].start) <= ONSET_WINDOW:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _mean(values: list[int]) -> float:
    return sum(values) / len(values)


def _split_index(stack: list[PianoNote], lh_center: float, rh_center: float) -> int:
    ordered = sorted(stack, key=lambda item: item.midi)
    if len(ordered) == 1:
        pitch = ordered[0].midi
        left_dist = abs(pitch - lh_center)
        right_dist = abs(pitch - rh_center)
        if abs(left_dist - right_dist) < 2:
            return 0 if pitch >= SPLIT_CENTER else 1
        return 0 if right_dist <= left_dist else 1

    best_i = 0
    best_cost = None
    for index in range(len(ordered) + 1):
        left = ordered[:index]
        right = ordered[index:]
        if left and (max(item.midi for item in left) - min(item.midi for item in left) > HAND_SPAN):
            continue
        if right and (max(item.midi for item in right) - min(item.midi for item in right) > HAND_SPAN):
            continue
        cost = 0.0
        if left:
            cost += abs(_mean([item.midi for item in left]) - lh_center)
        else:
            cost += 8
        if right:
            cost += abs(_mean([item.midi for item in right]) - rh_center)
        else:
            cost += 8
        if left and right:
            gap = right[0].midi - left[-1].midi
            if gap >= MIN_GAP:
                cost -= min(12, gap)
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_i = index
    return best_i


def _peel_bass_octave(ordered: list[PianoNote]) -> tuple[list[PianoNote], list[PianoNote]]:
    if (
        len(ordered) >= 3
        and ordered[1].midi - ordered[0].midi == 12
        and ordered[0].midi <= 52
    ):
        return [ordered[0], ordered[1]], ordered[2:]
    return [], ordered


def assign_hands(notes: list[PianoNote]) -> list[PianoNote]:
    if not notes:
        return []
    lh_center = 50.0
    rh_center = 70.0
    assigned: list[PianoNote] = []
    for stack in _group_onsets(notes):
        ordered = sorted(stack, key=lambda item: item.midi)
        peeled, remain = _peel_bass_octave(ordered)
        if remain:
            index = _split_index(remain, lh_center, rh_center)
            left = peeled + remain[:index]
            right = remain[index:]
        else:
            left, right = peeled, []
        for item in left:
            item.hand = "left"
            assigned.append(item)
        for item in right:
            item.hand = "right"
            assigned.append(item)
        if left:
            lh_center = 0.65 * lh_center + 0.35 * _mean([item.midi for item in left])
        if right:
            rh_center = 0.65 * rh_center + 0.35 * _mean([item.midi for item in right])
    return assigned


def _clip_durations(notes: list[PianoNote]) -> None:
    by_hand: dict[str, list[PianoNote]] = {}
    for item in notes:
        by_hand.setdefault(item.hand, []).append(item)
    for hand_notes in by_hand.values():
        hand_notes.sort(key=lambda item: (item.start, item.midi))
        for index, item in enumerate(hand_notes):
            next_starts = [
                other.start
                for other in hand_notes[index + 1 :]
                if other.start > item.start + 0.01
            ]
            if not next_starts:
                continue
            limit = next_starts[0] - item.start
            if limit <= 0:
                continue
            item.duration = max(MIN_DURATION, min(item.duration, limit))


def _snap(value: float) -> float:
    grids = (0.0625, 1 / 12, 0.125, 1 / 6, 0.25, 1 / 3, 0.5, 0.75, 1.0, 1.5, 2.0)
    best = 0.0
    best_err = None
    for step in grids:
        snapped = round(value / step) * step
        err = abs(value - snapped)
        if best_err is None or err < best_err - 1e-9 or (abs(err - best_err) < 1e-9 and step >= 0.125):
            best_err = err
            best = snapped
    return max(0.0, round(best * 48) / 48)


def _snap_duration(value: float) -> float:
    for simple in (0.25, 0.5, 1.0, 1.5, 2.0):
        if abs(value - simple) <= 0.2:
            return simple
    snapped = _snap(value)
    return max(0.0625, snapped)


def to_events(notes: list[PianoNote], bpm: float) -> list[PianoEvent]:
    assigned = assign_hands(notes)
    _clip_durations(assigned)
    beat = 60.0 / bpm
    buckets: dict[tuple[str, float], PianoEvent] = {}
    for item in assigned:
        onset = _snap(item.start / beat)
        duration = _snap_duration(item.duration / beat)
        key = (item.hand, onset)
        event = buckets.get(key)
        if event is None:
            buckets[key] = PianoEvent(onset=onset, duration=duration, pitches=[item.midi], hand=item.hand)
        else:
            if item.midi not in event.pitches:
                event.pitches.append(item.midi)
            event.duration = max(event.duration, duration)
    events = list(buckets.values())
    for event in events:
        event.pitches.sort()
    events.sort(key=lambda item: (item.onset, 0 if item.hand == "right" else 1))
    return events


def prepare_piano(midi_path, bpm: float | None = None) -> tuple[list[PianoEvent], float]:
    notes = load_notes(midi_path)
    tempo = bpm or estimate_bpm(notes)
    return to_events(notes, tempo), tempo


def quantize_voice(notes: list[PianoNote], bpm: float) -> list[PianoEvent]:
    voiced = [
        PianoNote(
            midi=item.midi,
            start=item.start,
            duration=item.duration,
            velocity=item.velocity,
            hand="melody",
        )
        for item in notes
    ]
    _clip_durations(voiced)
    beat = 60.0 / bpm
    buckets: dict[float, PianoEvent] = {}
    for item in voiced:
        onset = _snap(item.start / beat)
        duration = _snap_duration(item.duration / beat)
        event = buckets.get(onset)
        if event is None:
            buckets[onset] = PianoEvent(onset=onset, duration=duration, pitches=[item.midi], hand="melody")
        else:
            if item.midi not in event.pitches:
                event.pitches.append(item.midi)
            event.duration = max(event.duration, duration)
    events = list(buckets.values())
    for event in events:
        event.pitches.sort()
    events.sort(key=lambda item: item.onset)
    return events
