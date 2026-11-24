#!/usr/bin/env python3
"""Does the gap-filled rollup stay cheap on a long diary?

The daily series is built in Python now (`app/insights/rollup.py`), because the
gap-filling and the per-kind breakdown are easier to trust there than in SQL. The
cost question is real: the old chart asked SQLite for a `GROUP BY day`, while the
new one loads every event in the range and walks them. On this app's real account
(6 log rows) that is nothing; on someone who has logged diligently for two years
it is a few thousand rows, and a card that takes two seconds on a phone is a bug
report waiting to happen.

Run it directly:

    uv run --project backend python scripts/probes/rollup_cost.py

It builds a throwaway database, times the query plus the rollup for 90 / 365 /
730-day ranges, and prints the numbers. It fails (exit 1) if the 730-day build
stops being comfortably interactive, so a regression shows up here rather than on
a phone.
"""

from __future__ import annotations

import random
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.insights.events import load_events  # noqa: E402
from app.insights.rollup import adherence, series  # noqa: E402

DAY_SECONDS = 86_400
BASE_UTC = 1_700_000_000
BUDGET_SECONDS = 1.5  # a card on a phone, over a home LAN, on the worst range
EXERCISES = 10
SYMPTOMS = 10
CONTEXTS = 8
DEFINITION_COUNTS = {"exercise": EXERCISES, "symptom": SYMPTOMS, "context": CONTEXTS}


def _build(connection: sqlite3.Connection, days: int, per_day: float) -> int:
    """One account, `per_day` entries a day, for `days` days. Returns the row count."""
    rng = random.Random(4)  # noqa: S311  -- reproducible fixture, not a secret
    connection.execute(
        "INSERT INTO users (id, email, password_hash, created_at_utc) VALUES ('u','p@e','x',?)",
        (BASE_UTC - days * DAY_SECONDS,),
    )
    for kind, table, count in (
        ("exercise", "exercise_definitions", EXERCISES),
        ("symptom", "symptom_definitions", SYMPTOMS),
        ("context", "context_definitions", CONTEXTS),
    ):
        extra_col = ", category" if kind == "context" else ""
        extra_val = ", 'relief'" if kind == "context" else ""
        for index in range(count):
            connection.execute(
                f"INSERT INTO {table} (id, user_id, name{extra_col})"  # noqa: S608 (fixed table list)
                f" VALUES (?, 'u', ?{extra_val})",
                (f"{kind}{index}", f"{kind.title()} {index}"),
            )
    rows = 0
    log_id = 0
    for day in range(days):
        for _ in range(int(per_day)):
            at = BASE_UTC - (days - day) * DAY_SECONDS + rng.randrange(7 * 3600, 21 * 3600)
            kind = rng.choices(["exercise", "symptom", "context"], weights=[4, 3, 3])[0]
            log_id += 1
            index = rng.randrange(0, DEFINITION_COUNTS[kind])
            if kind == "exercise":
                connection.execute(
                    "INSERT INTO exercise_logs (id, user_id, exercise_id, occurred_at_utc,"
                    " logged_at_utc, tz_offset_min, sets_done, effort_rpe)"
                    " VALUES (?, 'u', ?, ?, ?, -300, 3, 5)",
                    (f"l{log_id}", f"exercise{index}", at, at),
                )
            elif kind == "symptom":
                connection.execute(
                    "INSERT INTO symptom_logs (id, user_id, symptom_id, occurred_at_utc,"
                    " logged_at_utc, tz_offset_min, severity)"
                    " VALUES (?, 'u', ?, ?, ?, -300, 5)",
                    (f"l{log_id}", f"symptom{index}", at, at),
                )
            else:
                connection.execute(
                    "INSERT INTO context_logs (id, user_id, context_id, occurred_at_utc,"
                    " logged_at_utc, tz_offset_min, intensity)"
                    " VALUES (?, 'u', ?, ?, ?, -300, 4)",
                    (f"l{log_id}", f"context{index}", at, at),
                )
            rows += 1
    connection.commit()
    return rows


def main() -> int:
    import asyncio
    import tempfile

    print(f"rollup probe: {EXERCISES + SYMPTOMS + CONTEXTS} definitions, 3 logs/day")
    worst = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "probe.sqlite"
        connection = sqlite3.connect(db_path)
        connection.executescript((REPO / "backend/migrations/001_init.sql").read_text())
        plan_sql = REPO / "backend/migrations/003_profiles_and_plan.sql"
        connection.executescript(plan_sql.read_text())
        rows = _build(connection, days=730, per_day=3)
        connection.close()
        print(f"  seeded {rows} log rows over 730 days")
        for days in (90, 365, 730):
            loaded, count, rolled = asyncio.run(_run(db_path, days))
            total = loaded + rolled
            worst = max(worst, total)
            print(
                f"  {days:>4} days: {count:>5} events, load {loaded:.3f}s,"
                f" rollup {rolled:.3f}s, total {total:.3f}s"
            )
    if worst > BUDGET_SECONDS:
        print(f"FAIL: {worst:.2f}s on the worst range (budget {BUDGET_SECONDS}s)")
        return 1
    print(f"OK: worst range {worst:.2f}s, budget {BUDGET_SECONDS}s")
    return 0


async def _run(db_path: Path, days: int) -> tuple[float, int, float]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    class _Db:
        async def rows(self, sql: str, params: tuple) -> list[sqlite3.Row]:
            return connection.execute(sql, params).fetchall()

    started = time.perf_counter()
    events = await load_events(_Db(), "u", BASE_UTC - days * DAY_SECONDS)
    loaded = time.perf_counter() - started
    started = time.perf_counter()
    points = series(
        events,
        range_start=BASE_UTC - days * DAY_SECONDS,
        range_end=BASE_UTC,
        reference_offset_min=-300,
    )
    adherence(points)
    rolled = time.perf_counter() - started
    connection.close()
    return loaded, len(events), rolled


if __name__ == "__main__":
    raise SystemExit(main())
