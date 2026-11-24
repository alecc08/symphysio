"""The null. Random diaries must produce no findings — that is the whole point.

docs/INSIGHTS_PLAN.md §1.1 is the post-mortem: the query this package replaced
printed 374 of 400 candidate pairs as findings on *independent* random logs at
this diary's real density, and 400 of 400 at eight logs a day, because it counted
coincidences inside a time window and called the count a correlation.

So this file is not "a test", it is the definition of done for the maths. It runs
`analyse()` over seeded independent processes — exercise/trigger logs and symptom
logs drawn from unrelated distributions, at three densities, five seeds each — and
asserts that not one pair is ever verdicted `worth a look`.
"""

# ruff: noqa: S311  -- a seeded PRNG builds reproducible diaries; nothing here is a secret
from __future__ import annotations

import random

import pytest
from app.insights.association import (
    WORTH_A_LOOK,
    Analysis,
    Window,
    analyse,
)
from app.insights.events import Event

DAY = 86_400
RANGE_DAYS = 180
BASE_UTC = 1_700_000_000 - RANGE_DAYS * DAY

WINDOW = Window(label="1-6 h", min_hours=1.0, max_hours=6.0)


def _event(kind: str, def_id: str, name: str, at: int, category: str = "") -> Event:
    return Event(
        kind=kind,
        def_id=def_id,
        name=name,
        category=category,
        occurred_at_utc=at,
        tz_offset_min=-300,
        sets_done=3 if kind == "exercise" else None,
        effort=5 if kind == "exercise" else None,
        severity=5 if kind == "symptom" else None,
        severity_default=False,
    )


def _random_diary(rng: random.Random, per_day: float) -> list[Event]:
    """Two independent processes. Nothing here is *from* anything else.

    Symptoms get their own time-of-day shape (mornings), because that is what real
    diaries look like and an unmatched baseline turns that shape into a fake lag —
    which is exactly the bug this test has to catch.
    """
    events: list[Event] = []
    exercises = [f"ex{i}" for i in range(8)]
    symptoms = [f"sy{i}" for i in range(8)]
    for day in range(RANGE_DAYS):
        for name in exercises:
            if rng.random() < per_day / len(exercises):
                at = BASE_UTC + day * DAY + rng.randrange(7 * 3600, 21 * 3600)
                events.append(_event("exercise", name, name.replace("ex", "Ex "), at))
        for name in symptoms:
            if rng.random() < per_day / len(symptoms):
                hour = rng.choices(range(24), weights=[6 if h < 11 else 2 for h in range(24)])[0]
                at = BASE_UTC + day * DAY + hour * 3600 + rng.randrange(3600)
                events.append(_event("symptom", name, name.replace("sy", "Sy "), at))
    return events


@pytest.mark.parametrize("per_day", [1.0, 3.0, 8.0])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_independent_random_diaries_produce_no_findings(per_day: float, seed: int) -> None:
    rng = random.Random(seed * 1_000 + int(per_day))
    events = _random_diary(rng, per_day)
    analysis: Analysis = analyse(
        events,
        window=WINDOW,
        range_start=BASE_UTC,
        range_end=BASE_UTC + RANGE_DAYS * DAY,
    )
    claimed = [item for item in analysis.findings if item.verdict == WORTH_A_LOOK]
    assert not claimed, (
        f"seed={seed} per_day={per_day}: {len(claimed)} false finding(s): "
        + "; ".join(
            f"{item.exposure_name}+{item.symptom_name} {item.hits}/{item.sessions} "
            f"vs {item.control_hits}/{item.control_windows}"
            for item in claimed
        )
    )


def test_the_null_still_reports_what_it_examined() -> None:
    """A quiet "nothing found" is only honest if it says how much it looked at."""
    rng = random.Random(99)
    events = _random_diary(rng, 8.0)
    analysis = analyse(
        events,
        window=WINDOW,
        range_start=BASE_UTC,
        range_end=BASE_UTC + RANGE_DAYS * DAY,
    )
    assert analysis.pairs_examined > 0
    assert analysis.days_covered == RANGE_DAYS + 1  # day 0 through day RANGE_DAYS
    assert all(item.verdict != WORTH_A_LOOK for item in analysis.findings)
