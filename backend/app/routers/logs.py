"""Fast single-payload event logging, the unified timeline feed, and Undo.

Every write returns the row id immediately so the UI can offer "Undo" (which is
just ``DELETE /logs/{type}/{id}``) without a confirmation dialog.
"""

from __future__ import annotations

from json import JSONDecodeError
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from ..db import Database
from ..deps import AuthedUser, LocaleDep, get_db
from ..i18n import t
from ..ids import new_id, now_utc
from ..schemas import (
    ContextLogCreate,
    ContextLogUpdate,
    ExerciseLogCreate,
    ExerciseLogUpdate,
    SymptomLogCreate,
    SymptomLogUpdate,
)
from ..schemas import EventType as EventTypeLiteral

router = APIRouter(tags=["logs"])
DbDep = Annotated[Database, Depends(get_db)]
FUTURE_SKEW_SECONDS = 3600

DEF_TABLES = {
    "exercise": "exercise_definitions",
    "symptom": "symptom_definitions",
    "context": "context_definitions",
}
LOG_TABLES = {"exercise": "exercise_logs", "symptom": "symptom_logs", "context": "context_logs"}
DEF_COLUMNS = {"exercise": "exercise_id", "symptom": "symptom_id", "context": "context_id"}

SELECT_LOG = {
    "exercise": (
        "SELECT sets_done, reps_done, duration_sec, effort_rpe, pain_during, note,"
        " occurred_at_utc FROM exercise_logs WHERE id = ? AND user_id = ?"
    ),
    "symptom": (
        "SELECT body_region, severity, duration_min, note, occurred_at_utc, severity_default"
        " FROM symptom_logs WHERE id = ? AND user_id = ?"
    ),
    "context": (
        "SELECT intensity, note, occurred_at_utc FROM context_logs WHERE id = ? AND user_id = ?"
    ),
}

UPDATE_LOG = {
    "exercise": (
        "UPDATE exercise_logs SET sets_done = ?, reps_done = ?, duration_sec = ?, effort_rpe = ?,"
        " pain_during = ?, note = ?, occurred_at_utc = ? WHERE id = ? AND user_id = ?"
    ),
    "symptom": (
        "UPDATE symptom_logs SET body_region = ?, severity = ?, duration_min = ?, note = ?,"
        " occurred_at_utc = ?, severity_default = ? WHERE id = ? AND user_id = ?"
    ),
    "context": (
        "UPDATE context_logs SET intensity = ?, note = ?, occurred_at_utc = ?"
        " WHERE id = ? AND user_id = ?"
    ),
}

EDIT_COLUMNS = {
    "exercise": (
        "sets_done",
        "reps_done",
        "duration_sec",
        "effort_rpe",
        "pain_during",
        "note",
        "occurred_at_utc",
    ),
    "symptom": (
        "body_region",
        "severity",
        "duration_min",
        "note",
        "occurred_at_utc",
        "severity_default",
    ),
    "context": ("intensity", "note", "occurred_at_utc"),
}

INSERTS = {
    "exercise": (
        "INSERT INTO exercise_logs (id, user_id, exercise_id, occurred_at_utc, logged_at_utc,"
        " tz_offset_min, sets_done, reps_done, duration_sec, effort_rpe, pain_during, note)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ),
    "symptom": (
        "INSERT INTO symptom_logs (id, user_id, symptom_id, body_region, occurred_at_utc,"
        " logged_at_utc, tz_offset_min, severity, duration_min, note, severity_default)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ),
    "context": (
        "INSERT INTO context_logs (id, user_id, context_id, occurred_at_utc, logged_at_utc,"
        " tz_offset_min, intensity, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    ),
}

DEF_SELECT = {
    "exercise": "id, is_archived, default_sets, default_reps, default_sec",
    "symptom": "id, is_archived, default_region",
    "context": "id, is_archived",
}


async def _require_definition(
    db: Database, user_id: str, kind: str, definition_id: str, locale: str
) -> dict:
    row = await db.row(
        f"SELECT {DEF_SELECT[kind]} FROM {DEF_TABLES[kind]} WHERE id = ? AND user_id = ?",  # noqa: S608
        (definition_id, user_id),
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t(
                "err.unknown_definition",
                locale,
                kind=t(f"kind.{kind}", locale),
                definition_id=definition_id,
            ),
        )
    if row["is_archived"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("err.archived_definition", locale, kind=t(f"kind.{kind}", locale)),
        )
    return row


def _occurred(payload: Any) -> int:
    """Client-supplied timestamp, defaulting to now and clamping clock skew."""
    now = now_utc()
    value = payload.occurred_at_utc if payload.occurred_at_utc is not None else now
    if value > now + FUTURE_SKEW_SECONDS:
        value = now
    return value


def _created(log_id: str, kind: str) -> dict[str, Any]:
    return {"id": log_id, "event_type": kind, "status": "created"}


async def _load_log(
    db: Database, user_id: str, kind: str, log_id: str, locale: str
) -> dict[str, Any]:
    row = await db.row(SELECT_LOG[kind], (log_id, user_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=t("err.log_not_found", locale)
        )
    row["id"] = log_id
    row["event_type"] = kind
    return row


def _pick(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


@router.post("/logs/exercises", status_code=status.HTTP_201_CREATED)
async def log_exercise(
    payload: ExerciseLogCreate, user: AuthedUser, db: DbDep, locale: LocaleDep
) -> dict[str, Any]:
    definition = await _require_definition(
        db, user["id"], "exercise", payload.exercise_id, locale
    )
    sets_done = _pick(payload.sets_done, definition.get("default_sets"))
    reps_done = _pick(payload.reps_done, definition.get("default_reps"))
    duration_sec = _pick(payload.duration_sec, definition.get("default_sec"))
    log_id = new_id()
    await db.execute(
        INSERTS["exercise"],
        (
            log_id,
            user["id"],
            payload.exercise_id,
            _occurred(payload),
            now_utc(),
            payload.tz_offset_min,
            sets_done,
            reps_done,
            duration_sec,
            payload.effort_rpe,
            payload.pain_during,
            payload.note,
        ),
    )
    return _created(log_id, "exercise")


@router.post("/logs/symptoms", status_code=status.HTTP_201_CREATED)
async def log_symptom(
    payload: SymptomLogCreate, user: AuthedUser, db: DbDep, locale: LocaleDep
) -> dict[str, Any]:
    definition = await _require_definition(
        db, user["id"], "symptom", payload.symptom_id, locale
    )
    log_id = new_id()
    await db.execute(
        INSERTS["symptom"],
        (
            log_id,
            user["id"],
            payload.symptom_id,
            _pick(payload.body_region, definition.get("default_region")),
            _occurred(payload),
            now_utc(),
            payload.tz_offset_min,
            payload.severity,
            payload.duration_min,
            payload.note,
            int(payload.severity_default),
        ),
    )
    return _created(log_id, "symptom")


@router.post("/logs/contexts", status_code=status.HTTP_201_CREATED)
async def log_context(
    payload: ContextLogCreate, user: AuthedUser, db: DbDep, locale: LocaleDep
) -> dict[str, Any]:
    await _require_definition(db, user["id"], "context", payload.context_id, locale)
    log_id = new_id()
    await db.execute(
        INSERTS["context"],
        (
            log_id,
            user["id"],
            payload.context_id,
            _occurred(payload),
            now_utc(),
            payload.tz_offset_min,
            payload.intensity,
            payload.note,
        ),
    )
    return _created(log_id, "context")


TIMELINE_SELECT = """
SELECT v.id, v.event_type, v.def_id, v.occurred_at_utc, v.tz_offset_min, v.primary_metric,
       v.note,
       COALESCE(ed.name, sd.name, cd.name) AS definition_name,
       COALESCE(el.logged_at_utc, sl.logged_at_utc, cl.logged_at_utc) AS logged_at_utc,
       el.sets_done, el.reps_done, el.duration_sec, el.pain_during,
       sl.body_region, sl.severity, sl.duration_min, sl.severity_default,
       cd.category, cl.intensity
FROM v_unified_timeline v
LEFT JOIN exercise_definitions ed ON ed.id = v.def_id AND ed.user_id = v.user_id
LEFT JOIN symptom_definitions sd ON sd.id = v.def_id AND sd.user_id = v.user_id
LEFT JOIN context_definitions cd ON cd.id = v.def_id AND cd.user_id = v.user_id
LEFT JOIN exercise_logs el ON el.id = v.id AND el.user_id = v.user_id
LEFT JOIN symptom_logs sl ON sl.id = v.id AND sl.user_id = v.user_id
LEFT JOIN context_logs cl ON cl.id = v.id AND cl.user_id = v.user_id
"""

UPDATE_MODELS = {
    "exercise": ExerciseLogUpdate,
    "symptom": SymptomLogUpdate,
    "context": ContextLogUpdate,
}


@router.get("/timeline")
async def timeline(
    user: AuthedUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    before: Annotated[int | None, Query(ge=0)] = None,
    from_: Annotated[int | None, Query(ge=0, alias="from")] = None,
    to: Annotated[int | None, Query(ge=0)] = None,
    event_type: Annotated[str | None, Query(pattern="^(exercise|symptom|context)$")] = None,
) -> dict[str, Any]:
    where = ["v.user_id = ?"]
    params: list[Any] = [user["id"]]
    if event_type:
        where.append("v.event_type = ?")
        params.append(event_type)
    if from_ is not None:
        where.append("v.occurred_at_utc >= ?")
        params.append(from_)
    if to is not None:
        where.append("v.occurred_at_utc <= ?")
        params.append(to)
    if before is not None:
        where.append("v.occurred_at_utc < ?")
        params.append(before)
    sql = (
        TIMELINE_SELECT
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY v.occurred_at_utc DESC, v.id DESC LIMIT ?"
    )
    params.append(limit + 1)
    rows = await db.rows(sql, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    return {
        "items": items,
        "next_before": items[-1]["occurred_at_utc"] if has_more and items else None,
    }


@router.patch("/logs/{event_type}/{log_id}")
async def patch_log(
    event_type: EventTypeLiteral,
    log_id: str,
    request: Request,
    user: AuthedUser,
    db: DbDep,
    locale: LocaleDep,
) -> dict[str, Any]:
    model = UPDATE_MODELS[event_type]
    try:
        payload = model.model_validate(await request.json())
    except (ValidationError, JSONDecodeError):
        raise HTTPException(
            status_code=422, detail=t("err.bad_update", locale)
        ) from None
    columns = EDIT_COLUMNS[event_type]
    found = await db.row(SELECT_LOG[event_type], (log_id, user["id"]))
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=t("err.log_not_found", locale)
        )
    merged = {**found, **payload.model_dump(exclude_unset=True)}
    if event_type == "symptom" and "severity" in payload.model_dump(exclude_unset=True):
        # A hand-edited number is a chosen number. History edits are exactly how a
        # default becomes a measurement, so the flag clears here and nowhere else.
        merged["severity_default"] = 0
    await db.execute(
        UPDATE_LOG[event_type],
        [merged[column] for column in columns] + [log_id, user["id"]],
    )
    return await _load_log(db, user["id"], event_type, log_id, locale)


@router.delete("/logs/{event_type}/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    event_type: EventTypeLiteral, log_id: str, user: AuthedUser, db: DbDep, locale: LocaleDep
) -> None:
    deleted = await db.execute(
        f"DELETE FROM {LOG_TABLES[event_type]} WHERE id = ? AND user_id = ?",  # noqa: S608
        (log_id, user["id"]),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=t("err.log_not_found", locale)
        )
