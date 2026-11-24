"""One query, all of one user's logs in a range, as typed events.

The association maths needs every log of a range in memory at once: matched
baselines ask "was there an X log on *that* day", which cannot be answered from a
per-pair join. At this app's volumes (hundreds to low thousands of rows per user
per year) that is the cheap and correct choice; `scripts/probes/rollup_cost.py`
measures when it would stop being.

The statement is one static UNION ALL. No client text reaches SQL: `user_id` and
`since` are the only parameters and the window arithmetic happens in Python.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db import Database

KINDS = ("exercise", "symptom", "context")

EVENTS_SQL = """
SELECT 'exercise' AS kind,
       el.exercise_id                AS def_id,
       ed.name                       AS name,
       ''                            AS category,
       el.occurred_at_utc            AS occurred_at_utc,
       el.tz_offset_min              AS tz_offset_min,
       el.sets_done                  AS sets_done,
       el.effort_rpe                 AS effort,
       NULL                          AS severity,
       0                             AS severity_default
  FROM exercise_logs el
  JOIN exercise_definitions ed ON ed.id = el.exercise_id
 WHERE el.user_id = ? AND el.occurred_at_utc >= ?
UNION ALL
SELECT 'symptom' AS kind,
       sl.symptom_id                 AS def_id,
       sd.name                       AS name,
       ''                            AS category,
       sl.occurred_at_utc            AS occurred_at_utc,
       sl.tz_offset_min              AS tz_offset_min,
       NULL                          AS sets_done,
       NULL                          AS effort,
       sl.severity                   AS severity,
       sl.severity_default           AS severity_default
  FROM symptom_logs sl
  JOIN symptom_definitions sd ON sd.id = sl.symptom_id
 WHERE sl.user_id = ? AND sl.occurred_at_utc >= ?
UNION ALL
SELECT 'context' AS kind,
       cl.context_id                 AS def_id,
       cd.name                       AS name,
       cd.category                   AS category,
       cl.occurred_at_utc            AS occurred_at_utc,
       cl.tz_offset_min              AS tz_offset_min,
       NULL                          AS sets_done,
       NULL                          AS effort,
       cl.intensity                  AS severity,
       0                             AS severity_default
  FROM context_logs cl
  JOIN context_definitions cd ON cd.id = cl.context_id
 WHERE cl.user_id = ? AND cl.occurred_at_utc >= ?
 ORDER BY occurred_at_utc
"""


@dataclass(frozen=True)
class Event:
    """One logged thing. The three log types share a shape because the maths only
    ever asks "when, which one, and how much"."""

    kind: str
    def_id: str
    name: str
    category: str  # contexts only: "relief" or "trigger"; "" otherwise
    occurred_at_utc: int
    tz_offset_min: int
    sets_done: int | None
    effort: int | None  # exercise `effort_rpe`; the RPE the person chose to log
    severity: int | None
    severity_default: bool

    @property
    def local_seconds(self) -> int:
        """Wall-clock seconds since epoch, for hour-of-day and day boundaries."""
        return self.occurred_at_utc + self.tz_offset_min * 60

    @property
    def is_skipped_session(self) -> bool:
        """An exercise logged with zero sets: a "did not do it" row.

        Skipped sessions are still exercise rows for adherence and history, and
        they are still honest entries. What they are not is an *exposure*: a day
        you did not do the squat cannot be evidence about what the squat does.
        """
        return self.kind == "exercise" and self.sets_done == 0


async def load_events(db: Database, user_id: str, since: int) -> list[Event]:
    rows = await db.rows(EVENTS_SQL, (user_id, since, user_id, since, user_id, since))
    return [
        Event(
            kind=str(row["kind"]),
            def_id=str(row["def_id"]),
            name=str(row["name"]),
            category=str(row["category"] or ""),
            occurred_at_utc=int(row["occurred_at_utc"]),
            tz_offset_min=int(row["tz_offset_min"]),
            sets_done=None if row["sets_done"] is None else int(row["sets_done"]),
            effort=None if row["effort"] is None else int(row["effort"]),
            severity=None if row["severity"] is None else int(row["severity"]),
            severity_default=bool(row["severity_default"]),
        )
        for row in rows
    ]


def logs_of(events: list[Event], kind: str) -> list[Event]:
    return [event for event in events if event.kind == kind]


def exposures(events: list[Event], kind: str) -> list[Event]:
    """Logs that count as an exposure for the association maths.

    Skipped sessions are dropped here, once, rather than in every caller — and
    `kind="context"` deliberately keeps triggers only, because "Ice Pack" is an
    outcome-management choice, not something a symptom can be lagged *from*.
    """
    chosen = [event for event in events if event.kind == kind and not event.is_skipped_session]
    if kind == "context":
        chosen = [event for event in chosen if event.category == "trigger"]
    return chosen
