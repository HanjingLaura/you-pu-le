from __future__ import annotations

from dataclasses import dataclass

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
    from .rhythm import estimate_note_bpm

    return estimate_note_bpm(notes)


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
    from bisect import bisect_right

    by_hand: dict[str, list[PianoNote]] = {}
    for item in notes:
        by_hand.setdefault(item.hand, []).append(item)
    for hand_notes in by_hand.values():
        hand_notes.sort(key=lambda item: (item.start, item.midi))
        starts = sorted({item.start for item in hand_notes})
        for item in hand_notes:
            index = bisect_right(starts, item.start + 0.01)
            if index == len(starts):
                continue
            limit = starts[index] - item.start
            if limit <= 0:
                continue
            item.duration = max(MIN_DURATION, min(item.duration, limit))


LEGAL_DURATIONS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
MIN_MELODY_DURATION = 0.07
MIN_MELODY_VELOCITY = 30
MELODY_ONSET_WINDOW = 0.09


def _snap(value: float) -> float:
    return max(0.0, round(value * 4) / 4)


def _notation_duration(value: float) -> float:
    # A performed quarter commonly releases slightly before the next beat.
    # Prefer a nearby legal duration above the release, while preserving
    # exact dotted durations and clipping against the following attack.
    choices = [duration for duration in LEGAL_DURATIONS if -.03 <= duration - value <= .25]
    if choices:
        return choices[0]
    return min(LEGAL_DURATIONS, key=lambda duration: abs(duration - value))


def fit_duration(value: float, limit: float | None = None) -> float:
    cap = value if limit is None else min(value, limit)
    options = [item for item in LEGAL_DURATIONS if item <= cap + 1e-9]
    return options[-1] if options else 0.0


def clip_events(events: list[PianoEvent], monophonic: bool = False) -> list[PianoEvent]:
    grouped: dict[str, list[PianoEvent]] = {}
    for event in events:
        grouped.setdefault(event.hand, []).append(event)
    cleaned: list[PianoEvent] = []
    for group in grouped.values():
        group.sort(key=lambda item: item.onset)
        line: list[PianoEvent] = []
        for event in group:
            if event.duration <= 0 or not event.pitches:
                continue
            if line and event.onset <= line[-1].onset + (0.2 if monophonic else 1e-6):
                previous = line[-1]
                if monophonic:
                    previous.pitches = [pick_melody(previous.pitches + event.pitches)]
                else:
                    previous.pitches = sorted(set(previous.pitches + event.pitches))
                previous.duration = max(previous.duration, event.duration, event.onset + event.duration - previous.onset)
                continue
            line.append(
                PianoEvent(
                    onset=event.onset,
                    duration=event.duration,
                    pitches=list(event.pitches),
                    hand=event.hand,
                )
            )
        for index, event in enumerate(line):
            gap = line[index + 1].onset - event.onset if index + 1 < len(line) else None
            event.duration = min(4.0, max(0.25, _snap(event.duration)))
            if gap is not None:
                event.duration = fit_duration(event.duration, gap)
            if event.duration < 0.25:
                continue
            if monophonic:
                event.pitches = [pick_melody(event.pitches)]
            cleaned.append(event)
    cleaned.sort(key=lambda item: (item.onset, 0 if item.hand == "right" else 1))
    return cleaned


def to_events(notes: list[PianoNote], bpm: float, grid=None) -> list[PianoEvent]:
    assigned = assign_hands(notes)
    _clip_durations(assigned)
    beat = 60.0 / bpm
    buckets: dict[tuple[str, float], PianoEvent] = {}
    for item in assigned:
        position = grid.position(item.start) if grid is not None else item.start / beat
        end = grid.position(item.start + item.duration) if grid is not None else (item.start + item.duration) / beat
        onset = _snap(position)
        duration = _notation_duration(end - position)
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
    return clip_events(events)


def prepare_piano(midi_path, bpm: float | None = None, wav_path=None) -> tuple[list[PianoEvent], float]:
    notes = load_notes(midi_path)
    from .rhythm import score_grid

    grid = score_grid(midi_path, notes, wav_path, bpm)
    return to_events(notes, grid.bpm, grid), grid.bpm


def merge_unisons(notes: list[PianoNote], gap: float = 0.14, fragment: float = 0.18) -> list[PianoNote]:
    merged: list[PianoNote] = []
    for item in sorted(notes, key=lambda note: (note.start, note.midi)):
        if (
            merged
            and item.midi == merged[-1].midi
            and item.start <= merged[-1].start + merged[-1].duration + gap
            and (item.duration < fragment or merged[-1].duration < fragment)
        ):
            end = max(merged[-1].start + merged[-1].duration, item.start + item.duration)
            merged[-1].duration = end - merged[-1].start
            merged[-1].velocity = max(merged[-1].velocity, item.velocity)
            continue
        merged.append(
            PianoNote(
                midi=item.midi,
                start=item.start,
                duration=item.duration,
                velocity=item.velocity,
                hand=item.hand,
            )
        )
    return merged


def pick_melody(pitches: list[int], low: int | None = None, high: int | None = None) -> int:
    unique = sorted(set(pitches))
    if not unique:
        raise ValueError("没有音可写。")
    if low is None or high is None:
        return unique[-1]
    in_range = [value for value in unique if low <= value <= high]
    return (in_range or unique)[-1]


def extract_melody(notes: list[PianoNote], low: int | None = None, high: int | None = None, onset_window: float = MELODY_ONSET_WINDOW) -> list[PianoNote]:
    usable: list[PianoNote] = []
    for item in notes:
        if item.duration < MIN_MELODY_DURATION or item.velocity < MIN_MELODY_VELOCITY:
            continue
        midi = item.midi
        if low is not None and high is not None:
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
        usable.append(
            PianoNote(
                midi=midi,
                start=item.start,
                duration=item.duration,
                velocity=item.velocity,
                hand="melody",
            )
        )
    if not usable:
        usable = [
            PianoNote(
                midi=item.midi,
                start=item.start,
                duration=item.duration,
                velocity=item.velocity,
                hand="melody",
            )
            for item in notes
            if item.duration >= 0.04
        ]

    usable.sort(key=lambda item: (item.start, -item.velocity, -item.duration))
    groups: list[list[PianoNote]] = []
    for item in usable:
        if groups and item.start - groups[-1][0].start <= onset_window:
            groups[-1].append(item)
        else:
            groups.append([item])

    melody: list[PianoNote] = []
    previous: int | None = None
    for group in groups:
        best_by_pitch: dict[int, tuple[float, PianoNote]] = {}
        for item in group:
            energy = item.velocity * min(item.duration, 0.45)
            current = best_by_pitch.get(item.midi)
            if current is None or energy > current[0]:
                best_by_pitch[item.midi] = (energy, item)
        candidates = [pair[1] for pair in best_by_pitch.values()]

        def cost(item: PianoNote) -> tuple[float, int]:
            energy = item.velocity * min(item.duration, 0.5)
            leap = 0 if previous is None else abs(item.midi - previous)
            if leap > 12:
                leap_pen = 40 + (leap - 12) * 6
            elif leap > 7:
                leap_pen = 12 + (leap - 7) * 4
            else:
                leap_pen = leap * 1.2
            return (-energy + leap_pen, -item.midi if previous is None else 0)

        chosen = min(candidates, key=cost)
        if previous is not None and abs(chosen.midi - previous) >= 16 and chosen.velocity < 70:
            continue
        melody.append(chosen)
        previous = chosen.midi

    # Separate MIDI attacks are repeated notes, including fast repetitions.
    # Frame dropouts are handled in the audio tracker before this stage.
    return melody


def quantize_voice(notes: list[PianoNote], bpm: float, low: int | None = None, high: int | None = None, grid=None) -> list[PianoEvent]:
    voiced = extract_melody(notes, low, high, onset_window=min(MELODY_ONSET_WINDOW, 60 / bpm / 8))
    _clip_durations(voiced)
    beat = 60.0 / bpm
    buckets: dict[float, PianoEvent] = {}
    for item in voiced:
        position = grid.position(item.start) if grid is not None else item.start / beat
        end = grid.position(item.start + item.duration) if grid is not None else (item.start + item.duration) / beat
        onset = _snap(position)
        duration = _notation_duration(end - position)
        event = buckets.get(onset)
        if event is None:
            buckets[onset] = PianoEvent(onset=onset, duration=duration, pitches=[item.midi], hand="melody")
        else:
            if item.midi not in event.pitches:
                event.pitches.append(item.midi)
            event.duration = max(event.duration, duration)
    events = []
    for event in buckets.values():
        event.pitches = [pick_melody(event.pitches, low, high)]
        events.append(event)
    return clip_events(events, monophonic=True)
