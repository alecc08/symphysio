"""Daily rollup, gap-filled and adherence-aware.

Two rules the sparse `GROUP BY` version got wrong:

* **Every day in the range is present**, logging or not. A chart that only shows
  days with entries draws a line through the gaps and reads as continuity; a
  fortnight of no entries then looks like a sudden change on the day logging
  resumed.
* **A skipped session is still a session.** `sets_done = 0` counts towards
  adherence and towards "did you do your programme this week", and towards
  nothing in the association maths (`events.exposures` drops it).

Computed from the log rows every time rather than from a rollup table: at this
app's volumes that is milliseconds, and a second copy of the truth is a thing
that can drift.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from .events import Event

DAY_SECONDS = 86_400


def _day_label(day_index: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=day_index)).isoformat()


@dataclass(frozen=True)
class DailyPoint:
    day: str
    exercises: int
    exercises_skipped: int
    symptoms: int
    contexts: int
    avg_symptom_severity: float | None
    avg_effort: float | None
    # The average over the rows where the number was actually chosen. Printed
    # beside the plain average when the two disagree, so a week of defaults is
    # visible instead of silently pulling the line to 5.
    avg_chosen_severity: float | None
    severity_defaults: int
    logged: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "day": self.day,
            "exercises": self.exercises,
            "exercises_skipped": self.exercises_skipped,
            "symptoms": self.symptoms,
            "contexts": self.contexts,
            "avg_symptom_severity": self.avg_symptom_severity,
            "avg_effort": self.avg_effort,
            "avg_chosen_severity": self.avg_chosen_severity,
            "severity_defaults": self.severity_defaults,
            "logged": self.logged,
        }


def series(
    events: Sequence[Event],
    *,
    range_start: int,
    range_end: int,
    reference_offset_min: int,
) -> list[DailyPoint]:
    """One point per local day from `range_start` to `range_end`.

    Each event is bucketed by *its own* offset, so an entry made on a trip lands
    on the day the person experienced it. The gaps are cut in one reference frame —
    the offset of the most recent entry, which is what "today" means for the
    person looking at the chart.
    """
    buckets: dict[int, list[Event]] = {}
    for event in events:
        buckets.setdefault(event.local_seconds // DAY_SECONDS, []).append(event)

    first = (range_start + reference_offset_min * 60) // DAY_SECONDS
    last = (range_end + reference_offset_min * 60) // DAY_SECONDS
    points: list[DailyPoint] = []
    for index in range(first, last + 1):
        rows = buckets.get(index, [])
        symptoms = [row for row in rows if row.kind == "symptom"]
        exercises = [row for row in rows if row.kind == "exercise"]
        chosen = [
            row.severity
            for row in symptoms
            if row.severity is not None and not row.severity_default
        ]
        scored = [row.severity for row in symptoms if row.severity is not None]
        efforts = [row.effort for row in exercises if row.effort is not None]
        points.append(
            DailyPoint(
                day=_day_label(index),
                exercises=len(exercises),
                exercises_skipped=sum(1 for row in exercises if row.is_skipped_session),
                symptoms=len(symptoms),
                contexts=sum(1 for row in rows if row.kind == "context"),
                avg_symptom_severity=round(sum(scored) / len(scored), 2) if scored else None,
                avg_effort=round(sum(efforts) / len(efforts), 2) if efforts else None,
                avg_chosen_severity=round(sum(chosen) / len(chosen), 2) if chosen else None,
                severity_defaults=sum(1 for row in symptoms if row.severity_default),
                logged=bool(rows),
            )
        )
    return points


def adherence(points: Sequence[DailyPoint], target_days_per_week: int = 3) -> dict[str, object]:
    """Did the programme happen, counted in whole weeks, gaps included.

    Deliberately not a streak: streaks reward a run and punish a rest day, which
    is the wrong shape for a rehab diary where resting is part of the plan.
    """
    active = [point for point in points if point.logged]
    days = len(points)
    weeks = max(1, days // 7)
    did = sum(1 for point in points if point.exercises - point.exercises_skipped > 0)
    sessions_done = sum(max(0, point.exercises - point.exercises_skipped) for point in points)
    skipped = sum(point.exercises_skipped for point in points)
    return {
        "days_covered": days,
        "days_with_any_log": len(active),
        "days_with_exercise": did,
        "target_days_per_week": target_days_per_week,
        "weeks": weeks,
        "sessions_done": sessions_done,
        "sessions_skipped": skipped,
        "adherence_per_week": round(did / weeks, 2),
    }
