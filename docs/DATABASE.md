# Database

One SQLite file. WAL mode. Forward-only `.sql` migrations. Raw parameterized
SQL, no ORM. That combination is deliberate: the product's whole value is one
query that joins exercises to later symptoms, and a query you can read is a
query you can trust.

```
/data/symphysio.sqlite      (+ -wal, -shm)
```

Pragmas, applied on every connect (`app/db.py`):

```sql
PRAGMA journal_mode = WAL;      -- readers never block the single writer
PRAGMA synchronous = NORMAL;    -- safe with WAL, ~10x faster than FULL
PRAGMA foreign_keys = ON;       -- off by default in SQLite; never rely on default
PRAGMA busy_timeout = 5000;     -- one writer at a time, wait rather than error
```

## Shape

```
users ──┬── sessions
        ├── exercise_definitions ──┐
        ├── symptom_definitions  ──┼── exercise_logs / symptom_logs / context_logs
        └── context_definitions  ──┘
                     v_unified_timeline (VIEW over the three log tables)
```

Every row carries `user_id`, and every query filters on it. That is the second
line of defence after the session check: a handler cannot accidentally read
another account's row because it forgot a join, because the filter is a
positional parameter it always passes.

### Why three log tables instead of one

`exercise_logs`, `symptom_logs` and `context_logs` have different payloads
(dose vs severity vs category). One table would push those into a JSON blob, and
then the lag query has to parse JSON in SQL. The `v_unified_timeline` view gives
the History feed and the exports a single union with a normalised
`primary_metric` column, so the read side is still one query.

| Column | Meaning |
| --- | --- |
| `occurred_at_utc` | epoch seconds **when it happened** — the analytical clock |
| `logged_at_utc` | epoch seconds when it was typed in — audit only, never used for maths |
| `tz_offset_min` | client offset from UTC at that instant (±840) |

Local day = `(occurred_at_utc + tz_offset_min * 60) / 86400` as an integer day
index. That is how daily counts, the streak, and hour-of-day buckets are
computed: **a symptom logged at 11 pm is on the day the user experienced it**,
even if the server is on UTC and the phone flew across a timezone. Storing a
timezone name would have been nicer and would have required the client to know
the tz database; an offset at the moment of the event is enough because nobody
cares about historical DST for a symptom diary.

## The lag query

```sql
FROM exercise_logs el
JOIN symptom_logs sl
  ON sl.user_id = el.user_id
 AND sl.occurred_at_utc BETWEEN el.occurred_at_utc + :min_s AND el.occurred_at_utc + :max_s
GROUP BY exercise, symptom
HAVING COUNT(sl.id) >= :min_count
```

It is a plain range join, so it needs the right index and nothing exotic:
`idx_ex_logs_time (user_id, occurred_at_utc DESC)` narrows the exercise side and
`idx_sym_logs_time (user_id, occurred_at_utc DESC)` narrows the symptom range.
`min_count` (default 3) keeps a 2-observation "correlation" out of the UI — a
chart that lies is worse than no chart.

The window (`min_hr`, `max_hr`) is a parameter, not a hard-coded 24 h, because
pelvic-floor response lag is genuinely individual: leaking after a heavy lift
shows up in minutes, girdle-pain flares after a long day show up the next
morning.

## Definitions are archived, never deleted

```sql
CREATE UNIQUE INDEX uq_ex_def_name ON exercise_definitions(user_id, name COLLATE NOCASE);
```

- `is_archived = 1` hides a preset from the picker. Its logs stay, so deleting a
  preset cannot rewrite last month's chart.
- `sort_order` is per user and is rewritten in one transaction by
  `POST /catalog/{kind}/reorder` — the tile you tap most should be first.
- Unique names are case-insensitive per user, which is what makes "add again by
  accident" a `409` instead of two identical buttons.
- `icon_key` exists on definitions but the UI ignores it: the icon comes from the
  event kind, so a renamed preset never needs an icon.

## Ids and ordering

Ids are **UUIDv7** (`app/ids.py`): time-ordered, so primary-key inserts stay
append-only in the B-tree (random UUIDv4s cause page splitting), ids sort in the
same order as time for keyset paging, and nothing about the account is
guessable. Python 3.14's `uuid.uuid7` is used when available; a compatible
fallback covers 3.12/3.13.

## Sessions at rest

```sql
CREATE TABLE sessions (
  token_hash   TEXT PRIMARY KEY,   -- sha256(token), never the token
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at_utc INTEGER NOT NULL,
  created_at_utc INTEGER NOT NULL
);
```

A stolen database file therefore does not hand over usable session cookies: the
hash is unsalted but the input is 256 bits of randomness, so there is nothing to
brute-force. Passwords are Argon2id (see SECURITY.md).

## Migrations

`migrations/NNN_name.sql`, applied in filename order by a tiny runner at startup,
each inside its own transaction, recorded in `schema_migrations`:

```sql
CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, applied_at_utc INTEGER NOT NULL);
```

Rules: a migration must be idempotent-safe against a fresh install, must never
edit an already-released file, and must be additive where possible (SQLite's
`ALTER TABLE` is limited, so a rebuild-and-copy table is fine — but never
inside the same release that reads it).

## What is deliberately not here

- **No soft-delete column on logs.** Undo deletes. If you want to remove an entry
  permanently, that is what the `DELETE` endpoint is for; a `deleted_at` column
  would make every analytics query lie unless it remembered the predicate.
- **No FTS.** A diary of a few thousand rows does not need full-text search;
  timeline filters do the job.
- **No JSON columns for custom fields.** Custom presets are rows, not schemas.
