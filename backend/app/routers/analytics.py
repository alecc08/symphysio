"""Insights endpoints: daily counts, exercise→symptom lag correlations, hour-of-day.

All buckets use ``occurred_at_utc + tz_offset_min * 60`` so "morning stiffness"
groups by the user's local time-of-day without needing a timezone database.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from ..db import Database
from ..deps import AuthedUser, get_db
from ..ids import now_utc

router = APIRouter(prefix="/analytics", tags=["analytics"])
DbDep = Annotated[Database, Depends(get_db)]
DAY_SECONDS = 86_400


def _since(days: int) -> int:
    return now_utc() - days * DAY_SECONDS


def _day_label(day_index: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=day_index)).isoformat()


async def _daily(db: Database, user_id: str, since: int) -> list[dict[str, Any]]:
    rows = await db.rows(
        """
        SELECT CAST((occurred_at_utc + tz_offset_min * 60) / 86400 AS INTEGER) AS day_index,
               event_type,
               COUNT(*) AS count,
               AVG(primary_metric) AS avg_metric
        FROM v_unified_timeline
        WHERE user_id = ? AND occurred_at_utc >= ?
        GROUP BY day_index, event_type
        """,
        (user_id, since),
    )
    buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        index = int(row["day_index"])
        bucket = buckets.setdefault(
            index,
            {
                "day": _day_label(index),
                "exercises": 0,
                "symptoms": 0,
                "contexts": 0,
                "avg_symptom_severity": None,
                "avg_effort": None,
            },
        )
        kind = row["event_type"]
        bucket[f"{kind}s" if kind != "exercise" else "exercises"] = int(row["count"])
        if kind == "symptom":
            bucket["avg_symptom_severity"] = round(float(row["avg_metric"] or 0), 2)
        elif kind == "exercise":
            bucket["avg_effort"] = round(float(row["avg_metric"] or 0), 2)
    return [buckets[key] for key in sorted(buckets)]


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
    return totals


async def _top(db: Database, user_id: str, since: int, kind: str, limit: int) -> list[dict]:
    spec = {
        "exercise": (
            "exercise_logs",
            "exercise_definitions",
            "exercise_id",
            "name",
            "COUNT(*) AS count, NULL AS avg_severity",
        ),
        "symptom": (
            "symptom_logs",
            "symptom_definitions",
            "symptom_id",
            "name",
            "COUNT(*) AS count, ROUND(AVG(l.severity), 1) AS avg_severity",
        ),
    }[kind]
    log_table, def_table, def_column, _, metrics = spec
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
        """
        SELECT DISTINCT CAST((occurred_at_utc + tz_offset_min * 60) / 86400 AS INTEGER) AS day_index
        FROM exercise_logs WHERE user_id = ? AND occurred_at_utc >= ?
        """,
        (user_id, since),
    )
    days = {int(row["day_index"]) for row in rows}
    if not days:
        return 0
    latest = max(days)
    if now_utc() // DAY_SECONDS - latest > 1:
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
    return {
        "days": days,
        "since_utc": since,
        "generated_at_utc": now_utc(),
        "totals": await _totals(db, user["id"], since),
        "daily": await _daily(db, user["id"], since),
        "top_exercises": await _top(db, user["id"], since, "exercise", 10),
        "top_symptoms": await _top(db, user["id"], since, "symptom", 10),
        "exercise_streak_days": await _streak(db, user["id"], since),
    }


LAG_SQL = """
SELECT
    ed.id AS exercise_id,
    ed.name AS exercise_name,
    sd.id AS symptom_id,
    sd.name AS symptom_name,
    COUNT(sl.id) AS post_exercise_occurrences,
    ROUND(AVG((sl.occurred_at_utc - el.occurred_at_utc) / 3600.0), 1) AS avg_lag_hours,
    ROUND(MIN((sl.occurred_at_utc - el.occurred_at_utc) / 3600.0), 1) AS min_lag_hours,
    ROUND(MAX((sl.occurred_at_utc - el.occurred_at_utc) / 3600.0), 1) AS max_lag_hours,
    ROUND(AVG(sl.severity), 1) AS avg_severity,
    COUNT(DISTINCT el.id) AS exercise_occurrences
FROM exercise_logs el
JOIN exercise_definitions ed ON ed.id = el.exercise_id
JOIN symptom_logs sl
  ON sl.user_id = el.user_id
 AND sl.occurred_at_utc BETWEEN (el.occurred_at_utc + ?) AND (el.occurred_at_utc + ?)
JOIN symptom_definitions sd ON sd.id = sl.symptom_id
WHERE el.user_id = ? AND el.occurred_at_utc >= ?
GROUP BY ed.id, sd.id
HAVING COUNT(sl.id) >= ?
ORDER BY post_exercise_occurrences DESC, avg_lag_hours ASC
LIMIT ?
"""


@router.get("/lag-correlations")
async def lag_correlations(
    user: AuthedUser,
    db: DbDep,
    min_hr: Annotated[float, Query(ge=0, le=168)] = 1.0,
    max_hr: Annotated[float, Query(ge=0.25, le=720)] = 12.0,
    days: Annotated[int, Query(ge=1, le=730)] = 90,
    min_count: Annotated[int, Query(ge=1, le=1000)] = 3,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    if max_hr <= min_hr:
        max_hr = min_hr + 1
    min_seconds = int(min_hr * 3600)
    max_seconds = int(max_hr * 3600)
    since = _since(days)
    rows = await db.rows(LAG_SQL, (min_seconds, max_seconds, user["id"], since, min_count, limit))
    for row in rows:
        logged = await db.value(
            "SELECT COUNT(*) FROM symptom_logs WHERE user_id = ? AND symptom_id = ?"
            " AND occurred_at_utc >= ?",
            (user["id"], row["symptom_id"], since),
        )
        total = int(logged or 0)
        hits = int(row["post_exercise_occurrences"])
        row["symptom_logs_in_range"] = total
        row["share_of_symptom_logs"] = round(hits / total, 2) if total else None
    return {
        "min_hours": min_hr,
        "max_hours": max_hr,
        "days": days,
        "min_count": min_count,
        "pairs": rows,
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
