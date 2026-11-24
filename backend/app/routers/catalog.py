"""Catalog CRUD: the quick-tap buttons.

Definitions are archived rather than hard-deleted so historical logs keep their
foreign keys. Every statement is static text with ``?`` placeholders; the only
"dynamic" choice is which fixed statement we take from a hard-coded mapping, so
no client input ever reaches SQL as an identifier.
"""

# S608 stays enabled repo-wide; this module is exempt because every statement is
# assembled once from the hard-coded KINDS mapping below (never from request data).
# ruff: noqa: S608

from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db import Database
from ..deps import AuthedUser, get_db
from ..ids import new_id
from ..profiles import PROFILES
from ..schemas import (
    ContextDefinitionCreate,
    ContextDefinitionUpdate,
    ExerciseDefinitionCreate,
    ExerciseDefinitionUpdate,
    ProfileOut,
    ReorderRequest,
    SymptomDefinitionCreate,
    SymptomDefinitionUpdate,
    WindowOut,
)
from ..seed import suggestions

router = APIRouter(prefix="/catalog", tags=["catalog"])
DbDep = Annotated[Database, Depends(get_db)]

# Hard-coded per-kind SQL + model mapping (never built from request data).
KINDS: dict[str, dict[str, Any]] = {
    "exercises": {
        "table": "exercise_definitions",
        "select_cols": (
            "id, name, body_region, default_sets, default_reps, default_sec, icon_key,"
            " is_archived, sort_order, profile_key"
        ),
        "create_cols": (
            "name",
            "body_region",
            "default_sets",
            "default_reps",
            "default_sec",
            "icon_key",
            "sort_order",
        ),
        "update_cols": (
            "name",
            "body_region",
            "default_sets",
            "default_reps",
            "default_sec",
            "icon_key",
            "is_archived",
            "sort_order",
        ),
        "create_model": ExerciseDefinitionCreate,
        "update_model": ExerciseDefinitionUpdate,
    },
    "symptoms": {
        "table": "symptom_definitions",
        # `last_severity` / `last_logged_utc` are the number this person last chose
        # for this symptom and when, so the drawer can offer that number back with
        # its name attached instead of silently logging another default 5. Scalar
        # subqueries on purpose: the (user_id, symptom_id, occurred_at_utc DESC)
        # index from 001 makes each one a single seek, at diary-sized catalogs.
        "select_cols": (
            "id, name, default_region AS body_region, icon_key, is_archived, sort_order,"
            " profile_key,"
            " (SELECT severity FROM symptom_logs sl"
            "  WHERE sl.user_id = symptom_definitions.user_id"
            "   AND sl.symptom_id = symptom_definitions.id"
            "  ORDER BY sl.occurred_at_utc DESC LIMIT 1) AS last_severity,"
            " (SELECT occurred_at_utc FROM symptom_logs sl"
            "  WHERE sl.user_id = symptom_definitions.user_id"
            "   AND sl.symptom_id = symptom_definitions.id"
            "  ORDER BY sl.occurred_at_utc DESC LIMIT 1) AS last_logged_utc"
        ),
        "create_cols": ("name", "default_region", "icon_key", "sort_order"),
        "update_cols": ("name", "default_region", "icon_key", "is_archived", "sort_order"),
        "create_model": SymptomDefinitionCreate,
        "update_model": SymptomDefinitionUpdate,
    },
    "contexts": {
        "table": "context_definitions",
        "select_cols": "id, name, category, icon_key, is_archived, sort_order, profile_key",
        "create_cols": ("category", "name", "icon_key", "sort_order"),
        "update_cols": ("name", "icon_key", "is_archived", "sort_order"),
        "create_model": ContextDefinitionCreate,
        "update_model": ContextDefinitionUpdate,
    },
}


def _kind(kind: str) -> dict[str, Any]:
    cfg = KINDS.get(kind)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown catalog kind")
    return cfg


def _out(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["is_archived"] = bool(item.get("is_archived", 0))
    return item


async def _next_sort_order(db: Database, table: str, user_id: str) -> int:
    value = await db.value(
        f"SELECT COALESCE(MAX(sort_order), -1) + 1 FROM {table} WHERE user_id = ?",
        (user_id,),
    )
    return int(value or 0)


async def _list(
    db: Database,
    user_id: str,
    cfg: dict[str, Any],
    *,
    include_archived: bool,
    category: str | None = None,
) -> list[dict[str, Any]]:
    where = ["user_id = ?"]
    params: list[Any] = [user_id]
    if not include_archived:
        where.append("is_archived = 0")
    if category:
        where.append("category = ?")
        params.append(category)
    sql = (
        f"SELECT {cfg['select_cols']} FROM {cfg['table']}"  # literals from KINDS only
        f" WHERE {' AND '.join(where)} ORDER BY is_archived, sort_order, name"
    )
    return [_out(row) for row in await db.rows(sql, params)]


async def _create(db: Database, user_id: str, cfg: dict[str, Any], payload: Any) -> dict[str, Any]:
    data = payload.model_dump()
    columns = cfg["create_cols"]
    if data.get("sort_order") is None:
        data["sort_order"] = await _next_sort_order(db, cfg["table"], user_id)
    placeholders = ", ".join("?" for _ in ("id", "user_id", *columns))
    sql = (
        f"INSERT INTO {cfg['table']} (id, user_id, {', '.join(columns)})"  # literals only
        f" VALUES ({placeholders})"
    )
    definition_id = new_id()
    values = [definition_id, user_id, *[data.get(column) for column in columns]]
    try:
        await db.execute(sql, values)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a catalog item with that name.",
        ) from None
    row = await db.row(
        f"SELECT {cfg['select_cols']} FROM {cfg['table']} WHERE id = ? AND user_id = ?",
        (definition_id, user_id),
    )
    return _out(row or {"id": definition_id})


async def _patch(
    db: Database, user_id: str, cfg: dict[str, Any], definition_id: str, payload: Any
) -> dict[str, Any]:
    columns = cfg["update_cols"]
    table = cfg["table"]
    found = await db.row(
        f"SELECT {', '.join(columns)} FROM {table} WHERE id = ? AND user_id = ?",
        (definition_id, user_id),
    )
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")
    merged = {**found, **payload.model_dump(exclude_unset=True)}
    merged["is_archived"] = 1 if merged.get("is_archived") else 0
    assignments = ", ".join(f"{column} = ?" for column in columns)
    try:
        await db.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ? AND user_id = ?",
            [merged[column] for column in columns] + [definition_id, user_id],
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a catalog item with that name.",
        ) from None
    row = await db.row(
        f"SELECT {cfg['select_cols']} FROM {table} WHERE id = ? AND user_id = ?",
        (definition_id, user_id),
    )
    return _out(row or {})


async def _reorder(db: Database, user_id: str, cfg: dict[str, Any], ids: list[str]) -> int:
    sql = f"UPDATE {cfg['table']} SET sort_order = ? WHERE id = ? AND user_id = ?"
    return await db.executemany(sql, [(index, item, user_id) for index, item in enumerate(ids)])


async def _existing_names(db: Database, user_id: str, table: str) -> set[str]:
    rows = await db.rows(f"SELECT name FROM {table} WHERE user_id = ?", (user_id,))
    return {str(row["name"]) for row in rows}


@router.get("/profiles", response_model=list[ProfileOut])
async def list_profiles() -> list[ProfileOut]:
    """The starting sets offered at sign-up. Public on purpose.

    The picker lives on the sign-up card, so there is no session yet to authorise
    with — and the payload is the same for everyone: names, counts and lag
    windows, never any account data. Ordered as the picker should show them, with
    "Start empty" first.
    """
    return [
        ProfileOut(
            key=profile.key,
            label=profile.label,
            blurb=profile.blurb,
            counts=profile.counts,
            windows=[
                WindowOut(label=label, min_hours=low, max_hours=high)
                for label, low, high in sorted(profile.windows, key=lambda row: (row[1], row[2]))
            ],
            default_window=profile.default_window,
        )
        for profile in PROFILES.values()
    ]


@router.get("/exercises")
async def list_exercises(
    user: AuthedUser, db: DbDep, include_archived: bool = False
) -> list[dict[str, Any]]:
    return await _list(db, user["id"], KINDS["exercises"], include_archived=include_archived)


@router.get("/exercises/suggestions")
async def suggest_exercises(user: AuthedUser, db: DbDep) -> list[dict[str, Any]]:
    return suggestions("exercises", await _existing_names(db, user["id"], "exercise_definitions"))


@router.post("/exercises", status_code=status.HTTP_201_CREATED)
async def create_exercise(payload: ExerciseDefinitionCreate, user: AuthedUser, db: DbDep) -> dict:
    return await _create(db, user["id"], KINDS["exercises"], payload)


@router.patch("/exercises/{definition_id}")
async def patch_exercise(
    definition_id: str, payload: ExerciseDefinitionUpdate, user: AuthedUser, db: DbDep
) -> dict:
    return await _patch(db, user["id"], KINDS["exercises"], definition_id, payload)


@router.post("/exercises/reorder")
async def reorder_exercises(payload: ReorderRequest, user: AuthedUser, db: DbDep) -> dict:
    return {"updated": await _reorder(db, user["id"], KINDS["exercises"], payload.ids)}


@router.get("/symptoms")
async def list_symptoms(
    user: AuthedUser, db: DbDep, include_archived: bool = False
) -> list[dict[str, Any]]:
    return await _list(db, user["id"], KINDS["symptoms"], include_archived=include_archived)


@router.get("/symptoms/suggestions")
async def suggest_symptoms(user: AuthedUser, db: DbDep) -> list[dict[str, Any]]:
    return suggestions("symptoms", await _existing_names(db, user["id"], "symptom_definitions"))


@router.post("/symptoms", status_code=status.HTTP_201_CREATED)
async def create_symptom(payload: SymptomDefinitionCreate, user: AuthedUser, db: DbDep) -> dict:
    return await _create(db, user["id"], KINDS["symptoms"], payload)


@router.patch("/symptoms/{definition_id}")
async def patch_symptom(
    definition_id: str, payload: SymptomDefinitionUpdate, user: AuthedUser, db: DbDep
) -> dict:
    return await _patch(db, user["id"], KINDS["symptoms"], definition_id, payload)


@router.post("/symptoms/reorder")
async def reorder_symptoms(payload: ReorderRequest, user: AuthedUser, db: DbDep) -> dict:
    return {"updated": await _reorder(db, user["id"], KINDS["symptoms"], payload.ids)}


@router.get("/contexts")
async def list_contexts(
    user: AuthedUser,
    db: DbDep,
    include_archived: bool = False,
    category: Annotated[str | None, Query(pattern="^(relief|trigger)$")] = None,
) -> list[dict[str, Any]]:
    return await _list(
        db, user["id"], KINDS["contexts"], include_archived=include_archived, category=category
    )


@router.get("/contexts/suggestions")
async def suggest_contexts(user: AuthedUser, db: DbDep) -> list[dict[str, Any]]:
    return suggestions("contexts", await _existing_names(db, user["id"], "context_definitions"))


@router.post("/contexts", status_code=status.HTTP_201_CREATED)
async def create_context(payload: ContextDefinitionCreate, user: AuthedUser, db: DbDep) -> dict:
    return await _create(db, user["id"], KINDS["contexts"], payload)


@router.patch("/contexts/{definition_id}")
async def patch_context(
    definition_id: str, payload: ContextDefinitionUpdate, user: AuthedUser, db: DbDep
) -> dict:
    return await _patch(db, user["id"], KINDS["contexts"], definition_id, payload)


@router.post("/contexts/reorder")
async def reorder_contexts(payload: ReorderRequest, user: AuthedUser, db: DbDep) -> dict:
    return {"updated": await _reorder(db, user["id"], KINDS["contexts"], payload.ids)}
