"""One-click exports for physiotherapists or offline analysis.

CSV is one flat time-series file (spreadsheet friendly); JSON is a full,
typed dump of definitions + logs.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from ..db import Database
from ..deps import AuthedUser, get_db
from ..ids import now_utc
from .logs import TIMELINE_SELECT

router = APIRouter(prefix="/export", tags=["export"])
DbDep = Annotated[Database, Depends(get_db)]

CSV_COLUMNS = (
    "event_type",
    "id",
    "definition",
    "definition_id",
    "occurred_at_utc",
    "occurred_utc",
    "local_time",
    "tz_offset_min",
    "logged_at_utc",
    "metric",
    "metric_name",
    "sets_done",
    "reps_done",
    "duration_sec",
    "duration_min",
    "severity",
    "pain_during",
    "intensity",
    "body_region",
    "category",
    "note",
)
METRIC_NAMES = {"exercise": "effort_rpe", "symptom": "severity", "context": "intensity"}


def _iso(value: int | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(int(value), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe(value: Any) -> str:
    """Stringify, guarding against spreadsheet formula injection."""
    if value is None:
        return ""
    text = str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


async def _rows(db: Database, user_id: str, since: int | None, until: int | None) -> list[dict]:
    where = ["v.user_id = ?"]
    params: list[Any] = [user_id]
    if since is not None:
        where.append("v.occurred_at_utc >= ?")
        params.append(since)
    if until is not None:
        where.append("v.occurred_at_utc <= ?")
        params.append(until)
    sql = (
        TIMELINE_SELECT
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY v.occurred_at_utc DESC, v.id DESC"
    )
    return await db.rows(sql, params)


def _filename(stem: str, suffix: str) -> str:
    return f"symphysio-{stem}-{datetime.now(UTC).strftime('%Y%m%d')}.{suffix}"


def _csv_row(row: dict[str, Any]) -> list[str]:
    kind = str(row["event_type"])
    local = int(row["occurred_at_utc"]) + int(row["tz_offset_min"] or 0) * 60
    return [
        _safe(kind),
        _safe(row["id"]),
        _safe(row["definition_name"]),
        _safe(row["def_id"]),
        _safe(row["occurred_at_utc"]),
        _safe(_iso(row["occurred_at_utc"])),
        _safe(_iso(local)),
        _safe(row["tz_offset_min"]),
        _safe(row["logged_at_utc"]),
        _safe(row["primary_metric"]),
        _safe(METRIC_NAMES.get(kind, "")),
        _safe(row["sets_done"]),
        _safe(row["reps_done"]),
        _safe(row["duration_sec"]),
        _safe(row["duration_min"]),
        _safe(row["severity"]),
        _safe(row["pain_during"]),
        _safe(row["intensity"]),
        _safe(row["body_region"]),
        _safe(row["category"]),
        _safe(row["note"]),
    ]


@router.get("/csv")
async def export_csv(
    user: AuthedUser,
    db: DbDep,
    from_: Annotated[int | None, Query(ge=0, alias="from")] = None,
    to: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    rows = await _rows(db, user["id"], from_, to)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(_csv_row(row))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_filename("timeline", "csv")}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/json")
async def export_json(
    user: AuthedUser,
    db: DbDep,
    from_: Annotated[int | None, Query(ge=0, alias="from")] = None,
    to: Annotated[int | None, Query(ge=0)] = None,
) -> dict[str, Any]:
    user_id = user["id"]
    definitions = {
        "exercises": await db.rows(
            "SELECT * FROM exercise_definitions WHERE user_id = ? ORDER BY sort_order", (user_id,)
        ),
        "symptoms": await db.rows(
            "SELECT * FROM symptom_definitions WHERE user_id = ? ORDER BY sort_order", (user_id,)
        ),
        "contexts": await db.rows(
            "SELECT * FROM context_definitions WHERE user_id = ? ORDER BY sort_order", (user_id,)
        ),
    }
    logs = {
        "exercises": await db.rows(
            "SELECT * FROM exercise_logs WHERE user_id = ? ORDER BY occurred_at_utc DESC",
            (user_id,),
        ),
        "symptoms": await db.rows(
            "SELECT * FROM symptom_logs WHERE user_id = ? ORDER BY occurred_at_utc DESC",
            (user_id,),
        ),
        "contexts": await db.rows(
            "SELECT * FROM context_logs WHERE user_id = ? ORDER BY occurred_at_utc DESC",
            (user_id,),
        ),
    }
    return {
        "app": "symphysio",
        "schema_version": 1,
        "exported_at_utc": now_utc(),
        "user": {"id": user_id, "email": user["email"]},
        "definitions": definitions,
        "logs": logs,
        "timeline": await _rows(db, user_id, from_, to),
    }
