"""aiosqlite access layer: one connection, WAL pragmas, forward-only migrations.

Every query goes through parameterized SQL with ``?`` placeholders. There is no
ORM and no string interpolation of identifiers anywhere in the app.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

import aiosqlite

from .ids import now_utc
from .settings import Settings

logger = logging.getLogger("symphysio.db")

PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA foreign_keys = ON;",
    "PRAGMA busy_timeout = 5000;",
)


class Database:
    """Small wrapper around a single shared aiosqlite connection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    # -- lifecycle ---------------------------------------------------------

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("database is not connected")
        return self._conn

    async def connect(self) -> None:
        if self._conn is not None:
            return
        db_path = self._settings.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(db_path), isolation_level=None)
        conn.row_factory = aiosqlite.Row
        for pragma in PRAGMAS:
            await conn.execute(pragma)
        self._conn = conn
        await self.migrate()
        await self.prune_sessions()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # -- migrations --------------------------------------------------------

    async def migrate(self) -> None:
        """Apply every unapplied ``migrations/*.sql`` in filename order."""
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name          TEXT PRIMARY KEY,
                applied_at_utc INTEGER NOT NULL
            )
            """
        )
        cursor = await self.conn.execute("SELECT name FROM schema_migrations")
        applied = {row["name"] for row in await cursor.fetchall()}
        migrations_dir = self._settings.migrations_dir
        if not migrations_dir.is_dir():
            raise FileNotFoundError(f"migrations directory not found: {migrations_dir}")
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.name in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            async with self._write_lock:
                try:
                    await self.conn.executescript(sql)
                    await self.conn.execute(
                        "INSERT INTO schema_migrations (name, applied_at_utc) VALUES (?, ?)",
                        (path.name, now_utc()),
                    )
                except sqlite3.Error:
                    logger.exception("migration %s failed", path.name)
                    raise
            logger.info("applied migration %s", path.name)

    # -- query helpers -----------------------------------------------------

    async def rows(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(sql, tuple(params))
        try:
            return [dict(row) for row in await cursor.fetchall()]
        finally:
            await cursor.close()

    async def row(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        cursor = await self.conn.execute(sql, tuple(params))
        try:
            found = await cursor.fetchone()
            return dict(found) if found is not None else None
        finally:
            await cursor.close()

    async def value(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cursor = await self.conn.execute(sql, tuple(params))
        try:
            found = await cursor.fetchone()
            return found[0] if found is not None else None
        finally:
            await cursor.close()

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a single write statement; returns rowcount."""
        async with self._write_lock:
            cursor = await self.conn.execute(sql, tuple(params))
            try:
                return cursor.rowcount
            finally:
                await cursor.close()

    async def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> int:
        async with self._write_lock:
            cursor = await self.conn.executemany(sql, [tuple(item) for item in seq])
            try:
                return cursor.rowcount
            finally:
                await cursor.close()

    async def script(self, sql: str) -> None:
        async with self._write_lock:
            await self.conn.executescript(sql)

    async def transaction(self) -> AsyncIterator[None]:
        """``BEGIN IMMEDIATE`` … ``COMMIT`` (or ROLLBACK on error)."""
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            else:
                await self.conn.execute("COMMIT")

    # -- maintenance -------------------------------------------------------

    async def prune_sessions(self) -> int:
        return await self.execute("DELETE FROM sessions WHERE expires_at_utc < ?", (now_utc(),))
