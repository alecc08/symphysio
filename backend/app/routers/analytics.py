"""Insights endpoints: what the diary says about itself.

All buckets use ``occurred_at_utc + tz_offset_min * 60`` so "morning stiffness"
groups by the user's local time-of-day without needing a timezone database.

The interpretation itself lives in `app/insights/` (pure, unit-tested, with a
checked-in null). This module only decides which range and which lag window to
hand it, and shapes the answer for the client. The old `lag-correlations`
endpoint is gone: it counted coincidences inside a window and printed the count
as a finding — see docs/INSIGHTS_PLAN.md §1.1 and `tests/test_insights_null.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db import Database
from ..deps import AuthedUser, get_db
from ..ids import now_utc
from ..insights.association import Window, analyse
from ..insights.events import Event, load_events
from ..insights.rollup import adherence, series
from ..insights.sufficiency import coverage, eligible_pair_count
from ..profiles import PROFILES

router = APIRouter(prefix="/analytics", tags=["analytics"])
DbDep = Annotated[Database, Depends(get_db)]
DAY_SECONDS = 86_400
ExposureKind = Annotated[str, Query(pattern="^(exercise|context|both)$")]


def _since(days: int) -> int:
    return now_utc() - days * DAY_SECONDS


def _day_label(day_index: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=day_index)).isoformat()


def _profile_windows(profile_key: str) -> list[Window]:
    profile = PROFILES.get(profile_key) or PROFILES["none"]
    return [
        Window(label=label, min_hours=low, max_hours=high) for label, low, high in profile.windows
    ]


def _choose_window(windows: list[Window], wanted: str | None, default: str) -> Window:
    """The profile's windows are the only ones offered.

    Free-form windows are how you fish for a pattern: the same diary shows a
    different "correlation" for every pair of numbers you try, so the choices are
    the ones the profile ships with, and the card says which one is in use.
    """
    if wanted is None:
        wanted = default
    for window in windows:
        if window.label == wanted:
            return window
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unknown window; try one of " + ", ".join(item.label for item in windows),
    )


async def _latest_offset(db: Database, user_id: str) -> int:
    """The offset the most recent entry used, whichever kind it was.

    Reading only `exercise_logs` used to make "today" wrong for anyone whose
    latest entry was a symptom — which, for a week of resting, is most weeks.
    """
    row = await db.row(
        "SELECT tz_offset_min FROM v_unified_timeline WHERE user_id = ?"
        " ORDER BY occurred_at_utc DESC LIMIT 1",
        (user_id,),
    )
    return int(row["tz_offset_min"]) if row else 0


async def _totals(db: Database, user_id: str, since: int) -> dict[str, Any]:
    rows = await db.rows(
        """
        SELECT event_type, COUNT(*) AS count, AVG(primary_metric) AS avg_metric,
               MAX(primary_metric) AS max_metric
        FROM v_unified_timeline
        WHERE user_id = ? AND occurred_at_utc >= ?
        GROUP BY event_type
        """,
        (user_id, since),
    )
    totals = {
        "exercises": 0,
        "symptoms": 0,
        "contexts": 0,
        "avg_symptom_severity": None,
        "worst_symptom_severity": None,
        "avg_effort": None,
    }
    names = {"exercise": "exercises", "symptom": "symptoms", "context": "contexts"}
    for row in rows:
        key = names[str(row["event_type"])]
        totals[key] = int(row["count"])
        if row["event_type"] == "symptom":
            totals["avg_symptom_severity"] = round(float(row["avg_metric"] or 0), 2)
            totals["worst_symptom_severity"] = row["max_metric"]
        elif row["event_type"] == "exercise" and row["avg_metric"] is not None:
            totals["avg_effort"] = round(float(row["avg_metric"]), 2)
    # How much of the severity on display was chosen at all. Printed next to the
    # average, because an average of defaults is not a measurement.
    defaults = await db.value(
        "SELECT COUNT(*) FROM symptom_logs WHERE user_id = ? AND occurred_at_utc >= ?"
        " AND severity_default = 1",
        (user_id, since),
    )
    totals["severity_defaults"] = int(defaults or 0)
    return totals


async def _top(db: Database, user_id: str, since: int, kind: str, limit: int) -> list[dict]:
    spec = {
        "exercise": (
            "exercise_logs",
            "exercise_definitions",
            "exercise_id",
            "COUNT(*) AS count, NULL AS avg_severity",
        ),
        "symptom": (
            "symptom_logs",
            "symptom_definitions",
            "symptom_id",
            "COUNT(*) AS count, ROUND(AVG(l.severity), 1) AS avg_severity",
        ),
    }[kind]
    log_table, def_table, def_column, metrics = spec
    sql = (  # all fragments come from the hard-coded spec mapping above
        f"SELECT d.id, d.name, {metrics}"  # noqa: S608
        f" FROM {log_table} l JOIN {def_table} d ON d.id = l.{def_column}"
        " WHERE l.user_id = ? AND l.occurred_at_utc >= ?"
        " GROUP BY d.id, d.name"
        " ORDER BY count DESC, d.name ASC"
        " LIMIT ?"
    )
    return await db.rows(sql, (user_id, since, limit))


async def _streak(db: Database, user_id: str, since: int) -> int:
    rows = await db.rows(
        "SELECT DISTINCT CAST((occurred_at_utc + tz_offset_min * 60) / 86400 AS INTEGER)"
        " AS day_index FROM exercise_logs WHERE user_id = ? AND occurred_at_utc >= ?",
        (user_id, since),
    )
    days = {int(row["day_index"]) for row in rows}
    if not days:
        return 0
    latest = max(days)
    # "Today" has to be today *in the frame the buckets were cut in*. Comparing a
    # local day index against a UTC one reports a broken streak for anyone west of
    # UTC during the hours when the two calendars disagree: measured for UTC-5 at
    # 19:50 EST (= 00:50 UTC the next day), where four evenings in a row answered 0.
    offset = await _latest_offset(db, user_id)
    if (now_utc() + offset * 60) // DAY_SECONDS - latest > 1:
        return 0  # streak broke: nothing logged today or yesterday
    streak = 0
    while latest - streak in days:
        streak += 1
    return streak


@router.get("/summary")
async def summary(
    user: AuthedUser,
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    since = _since(days)
    offset = await _latest_offset(db, user["id"])
    events = await load_events(db, user["id"], since)
    points = series(
        events,
        range_start=since,
        range_end=now_utc(),
        reference_offset_min=offset,
    )
    counts = _per_definition(events)
    gate = coverage(
        symptom_logs=sum(1 for event in events if event.kind == "symptom"),
        exercise_logs=sum(1 for event in events if event.kind == "exercise"),
        context_logs=sum(1 for event in events if event.kind == "context"),
        days_covered=len({point.day for point in points if point.logged}),
        days_requested=days,
        eligible_pairs=eligible_pair_count(
            counts["exercise"] + counts["context"], counts["symptom"]
        ),
    )
    return {
        "days": days,
        "since_utc": since,
        "generated_at_utc": now_utc(),
        "totals": await _totals(db, user["id"], since),
        "daily": [point.as_dict() for point in points],
        "adherence": adherence(points),
        "coverage": gate.as_dict(),
        "top_exercises": await _top(db, user["id"], since, "exercise", 10),
        "top_symptoms": await _top(db, user["id"], since, "symptom", 10),
        "exercise_streak_days": await _streak(db, user["id"], since),
    }


def _per_definition(events: Sequence[Event]) -> dict[str, list[int]]:
    """Log counts per definition, per kind — the candidate filter, counted once."""
    out: dict[str, list[int]] = {"exercise": [], "symptom": [], "context": []}
    per: dict[tuple[str, str], int] = {}
    for event in events:
        per[(event.kind, event.def_id)] = per.get((event.kind, event.def_id), 0) + 1
    for kind, _def_id in per:
        out[kind].append(per[(kind, _def_id)])
    return out


@router.get("/associations")
async def associations(
    user: AuthedUser,
    db: DbDep,
    days: Annotated[int, Query(ge=7, le=730)] = 90,
    window: Annotated[str | None, Query(max_length=40)] = None,
    exposure: ExposureKind = "both",
) -> dict[str, Any]:
    """"What follows X?" — counts, a matched baseline, and a fixed verdict word.

    The lag windows come from the account's tracking profile, not from the client:
    a urine leak after a cough and soreness 48 h after loading are different
    questions, and each profile ships the three windows that fit it. A client may
    *choose* among them, never invent one — free-form windows are how you fish a
    pattern out of noise.
    """
    profile = PROFILES.get(str(user.get("profile_key") or ""), None) or PROFILES["none"]
    windows = _profile_windows(profile.key)
    chosen = _choose_window(windows, window, profile.default_window)
    since = _since(days)
    events = await load_events(db, user["id"], since)
    kinds = ("exercise", "context") if exposure == "both" else (exposure,)
    analysis = analyse(
        events,
        window=chosen,
        range_start=since,
        range_end=now_utc(),
        exposure_kinds=kinds,
    )
    counts = _per_definition(events)
    gate = coverage(
        symptom_logs=sum(1 for event in events if event.kind == "symptom"),
        exercise_logs=sum(1 for event in events if event.kind == "exercise"),
        context_logs=sum(1 for event in events if event.kind == "context"),
        days_covered=analysis.days_covered,
        days_requested=days,
        eligible_pairs=eligible_pair_count(
            counts["exercise"] + counts["context"], counts["symptom"]
        ),
    )
    shown = analysis.findings if gate.association_allowed else []
    return {
        "days": days,
        "generated_at_utc": now_utc(),
        "profile_key": profile.key,
        "windows": [item.as_dict() for item in windows],
        "window": chosen.as_dict(),
        "exposure": exposure,
        "coverage": gate.as_dict(),
        "sufficiency": gate.state,
        "pairs_examined": analysis.pairs_examined,
        "pairs_shown": len(shown),
        "skipped_sessions": analysis.skipped_sessions,
        "days_covered": analysis.days_covered,
        "findings": [item.as_dict() for item in shown],
    }


HOUR_SQL = """
SELECT CAST(((occurred_at_utc + tz_offset_min * 60) / 3600) % 24 AS INTEGER) AS hour_local,
       COUNT(*) AS count, AVG(primary_metric) AS avg_metric
FROM v_unified_timeline
WHERE user_id = ? AND event_type = ? AND occurred_at_utc >= ?
GROUP BY hour_local
ORDER BY hour_local
"""


@router.get("/time-of-day")
async def time_of_day(
    user: AuthedUser,
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=730)] = 90,
    event_type: Annotated[str, Query(pattern="^(exercise|symptom|context)$")] = "symptom",
) -> dict[str, Any]:
    """Kept, because it is the one card that needs no baseline to be honest: it
    describes when things happen, and never claims one thing follows another."""
    since = _since(days)
    rows = await db.rows(HOUR_SQL, (user["id"], event_type, since))
    counts = {int(row["hour_local"]): row for row in rows}
    return {
        "days": days,
        "event_type": event_type,
        "hours": [
            {
                "hour": hour,
                "count": int(counts[hour]["count"]) if hour in counts else 0,
                "avg_metric": round(float(counts[hour]["avg_metric"]), 2)
                if hour in counts and counts[hour]["avg_metric"] is not None
                else None,
            }
            for hour in range(24)
        ],
    }


@router.get("/symptoms/{definition_id}")
async def symptom_trend(
    definition_id: str,
    user: AuthedUser,
    db: DbDep,
    days: Annotated[int, Query(ge=7, le=730)] = 90,
    baseline_days: Annotated[int, Query(ge=3, le=90)] = 14,
) -> dict[str, Any]:
    """One symptom: how often, how hard, and how that compares with its own start.

    The comparison is with *the same person's earlier weeks*, never with another
    user or a population norm — there is no cross-user query in this app, and a
    norm would be advice wearing a chart. Adherence is printed alongside because
    "less pain" and "less programme" look identical on a line.
    """
    found = await db.row(
        "SELECT id, name, is_archived FROM symptom_definitions WHERE id = ? AND user_id = ?",
        (definition_id, user["id"]),
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Unknown symptom definition")

    since = _since(days)
    offset = await _latest_offset(db, user["id"])
    events = await load_events(db, user["id"], since)
    # Only this symptom's rows count as symptoms here; the exercise rows ride
    # along so the same rollup produces honest adherence next to the trend.
    scoped = [
        event
        for event in events
        if (event.kind == "symptom" and event.def_id == definition_id) or event.kind == "exercise"
    ]
    points = series(
        scoped, range_start=since, range_end=now_utc(), reference_offset_min=offset
    )
    head = [point for point in points[:baseline_days] if point.symptoms]
    tail = [point for point in points[baseline_days:] if point.symptoms]

    def _mean(rows: list[Any], key: str) -> float | None:
        values = [getattr(row, key) for row in rows if getattr(row, key) is not None]
        return round(sum(values) / len(values), 2) if values else None

    plans = await db.rows(
        "SELECT id, kind, text, occurred_at_utc, tz_offset_min FROM plan_events"
        " WHERE user_id = ? AND occurred_at_utc >= ? ORDER BY occurred_at_utc",
        (user["id"], since),
    )
    logged = [point for point in points if point.symptoms]
    gate = coverage(
        symptom_logs=sum(point.symptoms for point in points),
        exercise_logs=sum(point.exercises for point in points),
        days_covered=len(logged),
        days_requested=days,
        eligible_pairs=0,
    )
    return {
        "definition": {
            "id": found["id"],
            "name": found["name"],
            "is_archived": bool(found["is_archived"]),
        },
        "days": days,
        "baseline_days": baseline_days,
        "generated_at_utc": now_utc(),
        "daily": [point.as_dict() for point in points],
        "baseline": {
            "avg_severity": _mean(head, "avg_symptom_severity"),
            "logs_per_day": _mean(head, "symptoms"),
            "days": len(head),
        },
        "recent": {
            "avg_severity": _mean(tail, "avg_symptom_severity"),
            "logs_per_day": _mean(tail, "symptoms"),
            "days": len(tail),
        },
        "severity_defaults": sum(point.severity_defaults for point in points),
        "adherence": adherence(points),
        "plan_events": plans,
        "coverage": gate.as_dict(),
        "sufficiency": gate.state,
        "first_logged_day": min((point.day for point in logged), default=None),
    }
