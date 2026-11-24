-- Symphysio 003: tracking profiles, the labelled severity default, plan events.
--
-- All additive. No released file is edited, no column dropped, and nothing here
-- is read by a code path that shipped before it.

-- 1. Which tracking profile an account started from. The column default is the
-- postnatal set because every existing account was seeded from it: the default
-- describes history, not policy. New accounts choose explicitly, and `none`
-- means "I started empty".
ALTER TABLE users ADD COLUMN profile_key TEXT NOT NULL DEFAULT 'postnatal_pelvic';

-- Which set seeded a given preset, so "restore my set" and "why is there a
-- Clamshell in this shoulder diary" are both answerable. Nullable: a preset the
-- user typed themselves has no origin.
ALTER TABLE exercise_definitions ADD COLUMN profile_key TEXT;
ALTER TABLE symptom_definitions  ADD COLUMN profile_key TEXT;
ALTER TABLE context_definitions  ADD COLUMN profile_key TEXT;

-- 2. The severity the drawer writes when nobody picked a number. `severity`
-- stays NOT NULL - every chart uses it, and a nullable metric silently shrinks
-- the N of every average. The row says instead whether the number was chosen,
-- which is what lets the UI label it and the insights disclose it. Existing rows
-- are 0 ("chosen"): the handful of logs in any live install get checked by hand
-- rather than guessed at by a migration.
ALTER TABLE symptom_logs ADD COLUMN severity_default INTEGER NOT NULL DEFAULT 0;

-- 3. Plan events: the moments that explain a step change in a trend.
--
-- A rehab diary has events that are none of exercise / symptom / context: an
-- appointment, "she changed the programme", a new medication. Without them a
-- trend steps for no recorded reason, and the one question worth asking - "what
-- changed around the 14th?" - has no answer. Short text, no structure: structure
-- would tempt the app into giving advice.
CREATE TABLE plan_events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN
                        ('appointment', 'programme_change', 'medication', 'goal', 'note')),
    text            TEXT NOT NULL,
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    created_at_utc  INTEGER NOT NULL
);
CREATE INDEX idx_plan_events_time ON plan_events(user_id, occurred_at_utc DESC);

-- 4. No new log indexes. 001 already has `(user_id, <def>_id, occurred_at_utc
-- DESC)` on all three log tables, which is exactly the shape the association
-- scans want; adding a second copy would only slow every insert. Checked with
-- scripts/probes/rollup_cost.py rather than assumed.

-- Deliberately absent: no materialised daily rollup. Row counts here are
-- thousands, and a rollup table is a second truth that can drift against the
-- logs. scripts/probes/rollup_cost.py measures the cost of computing it on a
-- dense two-year diary, so that decision can be revisited with numbers.
