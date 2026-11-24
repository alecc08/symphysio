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
from ..deps import AuthedUser, LocaleDep, get_db
from ..i18n import t_or
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
    # Written, not chosen: 1 when the severity on that row is the drawer's default
    # rather than a number the person picked. A physio reading the CSV has to be
    # able to tell those apart, and the file has to be explainable without this
    # repository next to it.
    "severity_default",
    "note",
)
METRIC_NAMES = {"exercise": "effort_rpe", "symptom": "severity", "context": "intensity"}

# Static text, never built from request data: only the `?`-placeholder WHERE clauses move.
PLAN_FEED_SELECT = (
    "SELECT id, kind, text, occurred_at_utc, logged_at_utc, tz_offset_min FROM plan_events"
)


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


async def _plan_rows(
    db: Database, user_id: str, since: int | None, until: int | None
) -> list[dict[str, Any]]:
    """Plan events in the same date window as the log rows, for the CSV feed."""
    where = ["user_id = ?"]
    params: list[Any] = [user_id]
    if since is not None:
        where.append("occurred_at_utc >= ?")
        params.append(since)
    if until is not None:
        where.append("occurred_at_utc <= ?")
        params.append(until)
    sql = (
        PLAN_FEED_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY occurred_at_utc DESC"
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
        _safe(row["severity_default"]),
        _safe(row["note"]),
    ]


def _plan_csv_row(row: dict[str, Any]) -> list[str]:
    """A plan event in the same flat time-series, mapped onto existing columns.

    `definition` and `category` carry the plan kind and `note` carries the text,
    rather than adding two always-empty columns: whoever opens this in a
    spreadsheet gets one table to sort by date, and docs/API.md states the
    mapping so the file explains itself without this repository next to it.
    """
    local = int(row["occurred_at_utc"]) + int(row["tz_offset_min"] or 0) * 60
    return [
        _safe("plan"),
        _safe(row["id"]),
        _safe(row["kind"]),
        "",
        _safe(row["occurred_at_utc"]),
        _safe(_iso(row["occurred_at_utc"])),
        _safe(_iso(local)),
        _safe(row["tz_offset_min"]),
        _safe(row["logged_at_utc"]),
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        _safe(row["kind"]),
        "",
        _safe(row["text"]),
    ]


def _header(locale: str) -> list[str]:
    """The column names, in the language of the account that asked.

    Only the header is translated. The *values* — `exercise`, `pelvic_floor`,
    `relief`, `1`/`0` — stay the machine-readable vocabulary docs/API.md documents,
    because a script or a spreadsheet formula that keys off `event_type == "exercise"`
    must keep working whichever language the button was in. The one column that is
    already in the person's language is `definition`: those are their own rows.

    A column with no translation entry prints its own name rather than an empty
    cell, so adding a column without a translation costs nothing here and a test
    in tests/test_i18n.py is what actually fails.
    """
    return [t_or(f"csv.{column}", locale, column) for column in CSV_COLUMNS]


@router.get("/csv")
async def export_csv(
    user: AuthedUser,
    db: DbDep,
    locale: LocaleDep,
    from_: Annotated[int | None, Query(ge=0, alias="from")] = None,
    to: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    rows = await _rows(db, user["id"], from_, to)
    plans = await _plan_rows(db, user["id"], from_, to)
    buffer = io.StringIO()
    # UTF-8 BOM: without it Excel reads the file as Windows-1252 and a French
    # header row arrives as `gravitÃ©`. This file is opened in a spreadsheet, and
    # the accents are the point. Readers that do not want a BOM skip it or ignore
    # it; every real one handles it.
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_header(locale))
    # One chronological table, not two sections: a clinician sorts it by date and
    # sees "she changed the programme" between the symptom rows that stepped.
    merged = [{**row, "event_type": "plan"} for row in plans] + list(rows)
    merged.sort(key=lambda item: (int(item["occurred_at_utc"]), str(item["id"])), reverse=True)
    for row in merged:
        writer.writerow(_plan_csv_row(row) if row["event_type"] == "plan" else _csv_row(row))
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
        # 2 = plan_events and severity_default joined the dump. Anything reading
        # these files should be able to tell which shape it has.
        "schema_version": 2,
        "exported_at_utc": now_utc(),
        "user": {
            "id": user_id,
            "email": user["email"],
            "profile_key": user.get("profile_key"),
            # The two preferences, so a file analysed years later says what
            # language its `definition` names were written in and what "local"
            # meant to the person logging it.
            "locale": user.get("locale"),
            "timezone": user.get("timezone"),
        },
        "definitions": definitions,
        "logs": logs,
        # Not a log type: the appointment/programme-change layer that explains a
        # trend step. Kept separate for the same reason it is out of the view.
        "plan_events": await db.rows(
            "SELECT * FROM plan_events WHERE user_id = ? ORDER BY occurred_at_utc DESC",
            (user_id,),
        ),
        "timeline": await _rows(db, user_id, from_, to),
    }
