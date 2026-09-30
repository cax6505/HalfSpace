"""Deterministic, rule-based segmentation and tagging of StatsBomb possessions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Sequence:
    possession_id: int
    phase_index: int
    tag: str
    events: tuple[dict[str, Any], ...]


def _name(event: dict[str, Any], key: str) -> str:
    value = event.get(key)
    return value.get("name", "") if isinstance(value, dict) else str(value or "")


def _minute(event: dict[str, Any]) -> float:
    return float(event.get("minute", 0)) + float(event.get("second", 0)) / 60


def _tag(events: list[dict[str, Any]]) -> str:
    types = [_name(event, "type") for event in events]
    if any(t in {"Starting XI", "Kick Off", "Corner", "Free Kick", "Penalty", "Throw-in"} for t in types):
        return "set-piece"
    if any(_name(e, "type") == "Ball Recovery" and e.get("counterpress") for e in events):
        return "press-win-trigger"
    first, last = events[0], events[-1]
    start = first.get("location") or [0, 0]
    end = last.get("location") or [0, 0]
    duration = _minute(last) - _minute(first)
    if len(events) <= 8 and duration <= 0.35 and len(start) >= 2 and len(end) >= 2 and end[0] - start[0] >= 30:
        return "counter-attack"
    locations = [e.get("location") for e in events if isinstance(e.get("location"), list) and len(e["location"]) >= 2]
    if any(float(before[0]) < 80 <= float(after[0]) for before, after in zip(locations, locations[1:])):
        return "zone-entry"
    return "build-up"


def segment_possessions(events: list[dict[str, Any]]) -> list[Sequence]:
    """Split each possession at phase changes, then assign one primary rule tag.

    Phases break at a gap over 10 seconds, a restart, or a possession ID change.
    """
    ordered = sorted(events, key=lambda e: e.get("index", 0))
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for event in ordered:
        restart = _name(event, "type") in {"Starting XI", "Kick Off", "Corner", "Free Kick", "Penalty", "Throw-in"}
        gap = current and (_minute(event) - _minute(current[-1])) * 60 > 10
        changed = current and event.get("possession") != current[-1].get("possession")
        if current and (restart or gap or changed):
            groups.append(current)
            current = []
        current.append(event)
    if current:
        groups.append(current)
    result = []
    phase_counts: dict[int, int] = {}
    for group in groups:
        pid = int(group[0].get("possession", 0) or 0)
        phase = phase_counts.get(pid, 0)
        phase_counts[pid] = phase + 1
        result.append(Sequence(pid, phase, _tag(group), tuple(group)))
    return result
