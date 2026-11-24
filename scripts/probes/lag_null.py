#!/usr/bin/env python3
"""The null probe, as a script: does the maths stay quiet on a random diary?

Run it directly (`uv run python scripts/probes/lag_null.py`) when you change the
association maths. `backend/tests/test_insights_null.py` asserts the same thing in
CI at three densities; this script goes wider — more seeds, both the pure maths
and the SQL that used to answer this question — and prints the numbers, because a
regression here is invisible: the old query did not look broken, it looked busy.

Exit code 0 = the maths stayed quiet; 1 = at least one false finding.
"""

from __future__ import annotations

import random
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.insights.association import WORTH_A_LOOK, Window, analyse  # noqa: E402
from app.insights.events import Event  # noqa: E402

DAY_SECONDS = 86_400
RANGE_DAYS = 240
BASE_UTC = 1_700_000_000 - RANGE_DAYS * DAY_SECONDS
EXERCISES = 10
SYMPTOMS = 10
WINDOW = Window(label="1-6 h", min_hours=1.0, max_hours=6.0)

# The query that shipped in 0.1.x, kept here so the comparison is reproducible
# rather than a story told in a plan document.
OLD_LAG_SQL = """
SELECT ed.id, ed.name, sd.id, sd.name, COUNT(sl.id) AS hits
FROM exercise_logs el
JOIN exercise_definitions ed ON ed.id = el.exercise_id
JOIN symptom_logs sl
  ON sl.user_id = el.user_id
 AND sl.occurred_at_utc BETWEEN (el.occurred_at_utc + ?) AND (el.occurred_at_utc + ?)
JOIN symptom_definitions sd ON sd.id = sl.symptom_id
WHERE el.user_id = ? AND el.occurred_at_utc >= ?
GROUP BY ed.id, sd.id
HAVING COUNT(sl.id) >= ?
"""


def _diary(rng: random.Random, per_day: float) -> list[Event]:
    """Two unrelated processes, each with a realistic morning shape."""
    events: list[Event] = []
    for day in range(RANGE_DAYS):
        for index in range(EXERCISES):
            if rng.random() < per_day / EXERCISES:
                at = BASE_UTC + day * DAY_SECONDS + rng.randrange(7 * 3600, 21 * 3600)
                events.append(
                    Event(
                        kind="exercise",
                        def_id=f"ex{index}",
                        name=f"Ex {index}",
                        category="",
                        occurred_at_utc=at,
                        tz_offset_min=-300,
                        sets_done=3,
                        effort=5,
                        severity=None,
                        severity_default=False,
                    )
                )
        for index in range(SYMPTOMS):
            if rng.random() < per_day / SYMPTOMS:
                hour = rng.choices(range(24), weights=[6 if h < 11 else 2 for h in range(24)])[0]
                at = BASE_UTC + day * DAY_SECONDS + hour * 3600 + rng.randrange(3600)
                events.append(
                    Event(
                        kind="symptom",
                        def_id=f"sy{index}",
                        name=f"Sy {index}",
                        category="",
                        occurred_at_utc=at,
                        tz_offset_min=-300,
                        sets_done=None,
                        effort=None,
                        severity=5,
                        severity_default=False,
                    )
                )
    return events


def _old_query_findings(events: list[Event], min_count: int = 3) -> int:
    """What the 0.1.x endpoint would have printed for the same diary."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.sqlite"
        connection = sqlite3.connect(db)
        connection.executescript((REPO / "backend/migrations/001_init.sql").read_text())
        connection.execute("INSERT INTO users (id, email, password_hash, created_at_utc)"
                           " VALUES ('u', 'p@example.com', 'x', ?)", (BASE_UTC,))
        for index in range(EXERCISES):
            connection.execute(
                "INSERT INTO exercise_definitions (id, user_id, name) VALUES (?, 'u', ?)",
                (f"ex{index}", f"Ex {index}"),
            )
        for index in range(SYMPTOMS):
            connection.execute(
                "INSERT INTO symptom_definitions (id, user_id, name) VALUES (?, 'u', ?)",
                (f"sy{index}", f"Sy {index}"),
            )
        for event in events:
            if event.kind == "exercise":
                connection.execute(
                    "INSERT INTO exercise_logs (id, user_id, exercise_id, occurred_at_utc,"
                    " logged_at_utc, tz_offset_min, sets_done) VALUES (?, 'u', ?, ?, ?, ?, 3)",
                    (f"{event.def_id}@{event.occurred_at_utc}", event.def_id, event.occurred_at_utc,
                     event.occurred_at_utc, event.tz_offset_min),
                )
            else:
                connection.execute(
                    "INSERT INTO symptom_logs (id, user_id, symptom_id, occurred_at_utc,"
                    " logged_at_utc, tz_offset_min, severity) VALUES (?, 'u', ?, ?, ?, ?, 5)",
                    (f"{event.def_id}@{event.occurred_at_utc}", event.def_id, event.occurred_at_utc,
                     event.occurred_at_utc, event.tz_offset_min),
                )
        connection.commit()
        cursor = connection.execute(
            OLD_LAG_SQL,
            (int(WINDOW.min_hours * 3600), int(WINDOW.max_hours * 3600), "u", BASE_UTC, min_count),
        )
        return len(cursor.fetchall())


def main() -> int:
    print(f"null probe: {RANGE_DAYS} days, {EXERCISES} exercises x {SYMPTOMS} symptoms")
    bad = 0
    for per_day in (1.0, 3.0, 8.0):
        old_total = 0
        false_claims = 0
        runs = 5
        for seed in range(runs):
            rng = random.Random(seed * 977 + int(per_day * 10))  # noqa: S311
            events = _diary(rng, per_day)
            result = analyse(
                events,
                window=WINDOW,
                range_start=BASE_UTC,
                range_end=BASE_UTC + RANGE_DAYS * DAY_SECONDS,
            )
            claims = [item for item in result.findings if item.verdict == WORTH_A_LOOK]
            false_claims += len(claims)
            if seed == 0:
                old_total = _old_query_findings(events)
        print(
            f"  {per_day:>4} logs/day: new maths claims {false_claims} of "
            f"{runs} diaries; old query printed {old_total or '-'} pairs for one of them"
        )
        bad += false_claims
    if bad:
        print(f"FAIL: {bad} finding(s) on independent data")
        return 1
    print("OK: no findings on independent data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
