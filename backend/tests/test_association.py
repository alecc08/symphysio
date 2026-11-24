"""The association maths: a planted signal is found, and a false one is not.

Pure arithmetic over synthetic diaries — no database, no clock. The time
boundaries are arguments, which is what lets a test put the end of the record
exactly where a naive baseline would break.
"""

from __future__ import annotations

from app.insights.association import (
    LOOKS_LIKE_CHANCE,
    NOTHING_FOUND,
    WORTH_A_LOOK,
    Window,
    analyse,
)
from app.insights.events import Event

DAY = 86_400
BASE_UTC = 1_700_000_000
RANGE_DAYS = 120
RANGE_START = BASE_UTC
RANGE_END = BASE_UTC + RANGE_DAYS * DAY
WINDOW = Window(label="1-6 h", min_hours=1.0, max_hours=6.0)


def _log(
    kind: str,
    def_id: str,
    at: int,
    *,
    sets_done: int | None = 3,
    severity: int | None = 5,
    severity_default: bool = False,
    category: str = "",
) -> Event:
    return Event(
        kind=kind,
        def_id=def_id,
        name=f"{kind}:{def_id}",
        category=category,
        occurred_at_utc=at,
        tz_offset_min=0,
        sets_done=sets_done if kind == "exercise" else None,
        effort=6 if kind == "exercise" else None,
        severity=severity if kind == "symptom" else None,
        severity_default=severity_default,
    )


def _diary(days: int, follow: int, lag_hours: float, every: int = 2) -> list[Event]:
    """X at 09:00 every `every` days; S follows on `follow` of those days.

    Every other day, not every day: a daily exposure leaves no *comparable* day to
    build a baseline from, and the maths says so (see the no-comparable-days test).
    """
    events: list[Event] = []
    for day in range(days):
        if day % every:
            continue
        at = BASE_UTC + day * DAY + 9 * 3600
        events.append(_log("exercise", "squat", at))
        if day // every < follow:
            events.append(_log("symptom", "heaviness", at + int(lag_hours * 3600)))
    return events


def _only(event_list: list[Event], verdict: str) -> list[str]:
    return [
        f"{item.exposure_name}->{item.symptom_name}"
        for item in event_list
        if item.verdict == verdict
    ]


def test_a_planted_lag_is_found_and_named() -> None:
    analysis = analyse(
        _diary(days=60, follow=16, lag_hours=3.0),
        window=WINDOW,
        range_start=RANGE_START,
        range_end=RANGE_END,
    )
    assert len(analysis.findings) == 1
    finding = analysis.findings[0]
    assert (finding.exposure_name, finding.symptom_name) == ("exercise:squat", "symptom:heaviness")
    assert finding.verdict == WORTH_A_LOOK
    # The card prints counts, never a percentage on its own.
    assert finding.hits == 16 and finding.sessions == 30
    assert finding.control_windows > 0 and finding.control_hits == 0


def test_the_same_pair_below_three_hits_is_refused() -> None:
    """Six logs, two of them following the session: examined, and refused.

    The gate is a count, not a threshold on a ratio, so it cannot be argued around
    by a small denominator.
    """
    events: list[Event] = [
        _log("exercise", "squat", BASE_UTC + day * DAY + 9 * 3600) for day in range(0, 60, 2)
    ]
    for day in range(0, 60, 2):
        # Two of them land inside the 1-6 h window, four land in the evening.
        hour = 12 if day < 4 else 20
        events.append(_log("symptom", "heaviness", BASE_UTC + day * DAY + hour * 3600))
    analysis = analyse(events, window=WINDOW, range_start=RANGE_START, range_end=RANGE_END)
    assert analysis.pairs_examined == 1, "the pair was examined..."
    assert analysis.findings == [], "...and correctly refused: 2 hits is not a pattern"


def test_a_lag_outside_the_window_is_not_found() -> None:
    """30 h later is a different question than 1-6 h later."""
    analysis = analyse(
        _diary(days=60, follow=30, lag_hours=30.0),
        window=WINDOW,
        range_start=RANGE_START,
        range_end=RANGE_END,
    )
    assert _only(analysis.findings, WORTH_A_LOOK) == []


def test_a_morning_rhythm_alone_is_not_a_finding() -> None:
    """The false positive this whole module exists to refuse.

    Symptoms at 10:00 every day, exercise at 09:00 on some days. Every exposure
    window "catches" a symptom (p_exposed = 1.0), and every control window does
    too — so the matched baseline says what actually happened: nothing.
    """
    events: list[Event] = []
    for day in range(90):
        if day % 3 == 0:
            events.append(_log("exercise", "squat", BASE_UTC + day * DAY + 9 * 3600))
        events.append(_log("symptom", "stiffness", BASE_UTC + day * DAY + 10 * 3600))
    analysis = analyse(
        events, window=WINDOW, range_start=RANGE_START, range_end=RANGE_END
    )
    assert _only(analysis.findings, WORTH_A_LOOK) == []
    finding = analysis.findings[0]
    assert finding.hits == finding.sessions == 30  # every window "catches" a symptom
    # ...and so does essentially every control window, which is the whole point.
    assert finding.control_hits >= finding.control_windows - 1
    assert finding.verdict in {LOOKS_LIKE_CHANCE, NOTHING_FOUND}


def test_a_daily_exposure_says_why_it_cannot_tell() -> None:
    """No comparable day, so no claim — and the card gets to say that specifically.

    Someone who squats every single day has no "days without squats" to compare
    against. Reporting `worth a look` there would be a lie built on an empty
    baseline; the gate reports `no_comparable_windows` instead.
    """
    analysis = analyse(
        _diary(days=60, follow=20, lag_hours=3.0, every=1),
        window=WINDOW,
        range_start=RANGE_START,
        range_end=RANGE_END,
    )
    assert analysis.findings == []
    assert analysis.pairs_examined == 1
    # ...and the refusal is explained, not hidden: the reason is the finding here.
    assert analysis.gates == [{"gate": "no_comparable_windows", "pairs": 1}]
