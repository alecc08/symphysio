"""Plan events: appointments, programme changes, medication, goals.

These are the moments that make a trend step for a reason the diary otherwise
cannot show. They are deliberately plain text with a coarse kind — no dosage, no
body site, no clinical structure — because the app's job is to describe this
person's own record, not to model a treatment plan.

They are *not* in `v_unified_timeline`. That view feeds the daily rollup, the
totals and the association maths, each of which assumes the three log types it
was written against; a fourth type in the view would silently change what "how
many symptoms today" means. History merges the two feeds in the client instead,
and the trend cards draw plan events as markers.
"""

# S608 stays enabled repo-wide; this module is exempt because every statement is
# static text with `?` placeholders (the only f-string interpolation is a
# hard-coded column list), and the one built UPDATE uses column names that come
# from a strict model's field set, never from request text.
# ruff: noqa: S608

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db import Database
from ..deps import AuthedUser, get_db
from ..ids import new_id, now_utc
from ..schemas import PlanEventCreate, PlanEventUpdate
from .logs import FUTURE_SKEW_SECONDS

router = APIRouter(tags=["plan"])
DbDep = Annotated[Database, Depends(get_db)]

PLAN_SELECT = "id, kind, text, occurred_at_utc, logged_at_utc, tz_offset_min, created_at_utc"
PLAN_BY_ID = f"SELECT {PLAN_SELECT} FROM plan_events WHERE id = ? AND user_id = ?"


@router.get("/plan-events")
async def list_plan_events(
    user: AuthedUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    from_: Annotated[int | None, Query(ge=0, alias="from")] = None,
    to: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict[str, Any]]:
    """Newest first, optionally bounded by date.

    The date window is the same one the trend cards use, so a card can answer
    "what changed in these 30 days" without a request per marker.
    """
    where = ["user_id = ?"]
    params: list[Any] = [user["id"]]
    if from_ is not None:
        where.append("occurred_at_utc >= ?")
        params.append(from_)
    if to is not None:
        where.append("occurred_at_utc <= ?")
        params.append(to)
    params.append(limit)
    return await db.rows(
        "SELECT "
        + PLAN_SELECT
        + " FROM plan_events WHERE "
        + " AND ".join(where)
        + " ORDER BY occurred_at_utc DESC, id DESC LIMIT ?",
        params,
    )


@router.post("/plan-events", status_code=status.HTTP_201_CREATED)
async def create_plan_event(
    payload: PlanEventCreate, user: AuthedUser, db: DbDep
) -> dict[str, Any]:
    now = now_utc()
    occurred = payload.occurred_at_utc if payload.occurred_at_utc is not None else now
    if occurred > now + FUTURE_SKEW_SECONDS:
        occurred = now  # same clock-skew clamp as the log endpoints
    event_id = new_id()
    await db.execute(
        "INSERT INTO plan_events (id, user_id, kind, text, occurred_at_utc, logged_at_utc,"
        " tz_offset_min, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id,
            user["id"],
            payload.kind,
            payload.text.strip(),
            occurred,
            now,
            payload.tz_offset_min,
            now,
        ),
    )
    row = await db.row(PLAN_BY_ID, (event_id, user["id"]))
    return dict(row or {"id": event_id, "status": "created"})


@router.patch("/plan-events/{event_id}")
async def patch_plan_event(
    event_id: str, payload: PlanEventUpdate, user: AuthedUser, db: DbDep
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to change")
    if updates.get("text") is not None:
        updates["text"] = str(updates["text"]).strip()
    changed = await db.execute(
        "UPDATE plan_events SET "
        + ", ".join(f"{column} = ?" for column in updates)
        + " WHERE id = ? AND user_id = ?",
        [*updates.values(), event_id, user["id"]],
    )
    if not changed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan event not found")
    row = await db.row(PLAN_BY_ID, (event_id, user["id"]))
    return dict(row or {})


@router.delete("/plan-events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_event(event_id: str, user: AuthedUser, db: DbDep) -> None:
    deleted = await db.execute(
        "DELETE FROM plan_events WHERE id = ? AND user_id = ?", (event_id, user["id"])
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan event not found")
