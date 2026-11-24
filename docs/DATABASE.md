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
        ├── email_verifications
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

### Preferences are account columns, not request state

`004_preferences.sql` adds two columns, both additive and neither rewriting
anything:

```sql
ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'en';
ALTER TABLE users ADD COLUMN timezone TEXT;
```

- `locale` is `en` or `fr` (Québec French). The default is `en` because that is
  what every account before 0.3.0 was seeded with — the default describes
  history, exactly like `profile_key` in 003, not what new accounts should get.
- `timezone` is an IANA name and **nullable**, where `NULL` means "this account
  never chose". That is not the same as choosing UTC, and the difference is what
  lets `SYMPHYSIO_DEFAULT_TIMEZONE` apply to accounts that never saw the setting.
- Neither column is indexed. Nothing asks "all French accounts"; both are read as
  part of the one-row session lookup that already exists.

The zone is a **frame**, not a re-derivation. It answers "which calendar day is
today" and "what does a 30-day range mean" when the diary itself cannot answer —
an empty range, or a range with no rows in it. Rows keep the offset they were
written with, so changing a zone (or moving house) never moves a stored day,
hour bucket or lag window. Re-deriving last March from tonight's zone would
redraw the insights without anyone touching the data, which is the one thing this
app is supposed to make hard.


## What follows a session: no join in SQL

The card used to be one range join:

```sql
FROM exercise_logs el
JOIN symptom_logs sl
  ON sl.user_id = el.user_id
 AND sl.occurred_at_utc BETWEEN el.occurred_at_utc + :min_s AND el.occurred_at_utc + :max_s
GROUP BY exercise, symptom
HAVING COUNT(sl.id) >= :min_count
```

That answers "does the symptom ever appear after the exercise", which at diary
sizes is nearly always yes. Measured on seeded **independent** diaries (nothing
causally linked): 1 spurious pair at 1 log/day, 67 at 3/day, 100 at 8/day — on a
24-pair card that is a full screen of invented patterns. It was replaced in 0.2.0;
`GET /analytics/lag-correlations` now 404s and a test asserts that, so nothing
quietly keeps calling it.

What runs instead (`app/insights/`):

```sql
SELECT ... FROM exercise_logs  WHERE user_id = ? AND occurred_at_utc >= ?
UNION ALL ... symptom_logs ...
UNION ALL ... context_logs ...
```

One indexed read per kind (`idx_ex_logs_time`, `idx_sym_logs_time`,
`idx_ctx_logs_time` — all `(user_id, occurred_at_utc DESC)`), then the pairing in
Python: each session is compared with **matched** control windows at the same
hour-of-day on days without that exposure, and a pair is only printed when the
Wilson interval of the exposed rate sits entirely above the control's. The maths
is in `association.py`; `scripts/probes/lag_null.py` re-runs the comparison on
independent data and fails if the new code ever claims a pattern there.

The window (`min_hr`, `max_hr`) is a parameter, not a hard-coded 24 h, because
pelvic-floor response lag is genuinely individual: leaking after a heavy lift
shows up in minutes, girdle-pain flares after a long day show up the next
morning. It is no longer free-form: the choices come from the account's tracking
profile, because letting someone slide a window until a pattern appears is how a
chart lies.

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

## Confirmation tokens at rest

`002_email_verification.sql` adds `users.is_verified` / `users.verified_at_utc`
and one table, with the same discipline as sessions:

```sql
CREATE TABLE email_verifications (
  id              TEXT PRIMARY KEY,              -- UUIDv7
  user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash      TEXT NOT NULL UNIQUE,          -- sha256(token), never the token
  purpose         TEXT NOT NULL CHECK (purpose IN ('confirm_email', 'password_reset')),
  created_at_utc  INTEGER NOT NULL,
  expires_at_utc  INTEGER NOT NULL,
  used_at_utc     INTEGER                        -- set when consumed (single use)
);
CREATE INDEX idx_email_verif_user ON email_verifications(user_id, purpose, expires_at_utc);
```

- Rows are looked up **by digest**, so a wrong token matches nothing at all —
  there is no row to burn a guess budget against, and the router's IP counter is
  the only bound on guessing.
- `used_at_utc` makes a link single use; an already-used link is a `410`, not a
  silent success.
- Requesting a new link **expires** the outstanding rows instead of deleting
  them, so the per-hour send budget (`SYMPHYSIO_EMAIL_SENDS_PER_HOUR`) cannot be
  dodged by asking for resends, and two inboxes never hold two live links.
- `is_verified` defaults to **1** so accounts created before the feature exist
  stay usable; `register` writes an explicit 0 when email is configured.
- The `purpose` column exists for the password-reset flow that has not been built
  yet; nothing writes `password_reset` today.
- Rows are junk once consumed or expired. `main.py` calls `prune_verifications`
  at startup, which deletes every used row and every row past its expiry.

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
