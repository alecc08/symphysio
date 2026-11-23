-- Symphysio initial schema (001_init.sql)
-- Analytics-ready design: every log carries occurred_at_utc (epoch seconds, for
-- fast lag arithmetic), logged_at_utc (audits retroactive entries) and
-- tz_offset_min (local time-of-day grouping without a tz database).

-- 1. Users & Sessions
CREATE TABLE users (
    id              TEXT PRIMARY KEY,          -- UUIDv7
    email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    created_at_utc  INTEGER NOT NULL
);

CREATE TABLE sessions (
    token_hash      TEXT PRIMARY KEY,          -- SHA-256 hex of cookie token
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at_utc  INTEGER NOT NULL,
    created_at_utc  INTEGER NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expiry ON sessions(expires_at_utc);

-- 2. Reusable User Catalogs (Definitions)
CREATE TABLE exercise_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,             -- e.g., "Wall Angels", "Glute Bridge"
    body_region     TEXT,                      -- e.g., "lower_back", "neck", "left_knee"
    default_sets    INTEGER,
    default_reps    INTEGER,
    default_sec     INTEGER,                   -- Hold duration or total time
    icon_key        TEXT NOT NULL DEFAULT 'physio',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ex_def_user ON exercise_definitions(user_id, is_archived, sort_order);
CREATE UNIQUE INDEX uq_ex_def_name ON exercise_definitions(user_id, name COLLATE NOCASE);

CREATE TABLE symptom_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,             -- e.g., "Sharp Pain", "Stiffness", "Tingling"
    default_region  TEXT,
    icon_key        TEXT NOT NULL DEFAULT 'symptom',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_sym_def_user ON symptom_definitions(user_id, is_archived, sort_order);
CREATE UNIQUE INDEX uq_sym_def_name ON symptom_definitions(user_id, name COLLATE NOCASE);

CREATE TABLE context_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category        TEXT NOT NULL CHECK (category IN ('relief', 'trigger')),
    name            TEXT NOT NULL,             -- e.g., "Ice Pack", "Ibuprofen", "Long Sitting"
    icon_key        TEXT NOT NULL DEFAULT 'context',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ctx_def_user ON context_definitions(user_id, category, is_archived);
CREATE UNIQUE INDEX uq_ctx_def_name ON context_definitions(user_id, category, name COLLATE NOCASE);

-- 3. Time-Series Event Logs
CREATE TABLE exercise_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id     TEXT NOT NULL REFERENCES exercise_definitions(id),
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    sets_done       INTEGER,
    reps_done       INTEGER,
    duration_sec    INTEGER,
    effort_rpe      INTEGER CHECK (effort_rpe BETWEEN 1 AND 10),
    pain_during     INTEGER CHECK (pain_during BETWEEN 0 AND 10),
    note            TEXT
);
CREATE INDEX idx_ex_logs_time ON exercise_logs(user_id, occurred_at_utc DESC);
CREATE INDEX idx_ex_logs_def  ON exercise_logs(user_id, exercise_id, occurred_at_utc DESC);

CREATE TABLE symptom_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symptom_id      TEXT NOT NULL REFERENCES symptom_definitions(id),
    body_region     TEXT,
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 10),
    duration_min    INTEGER,
    note            TEXT
);
CREATE INDEX idx_sym_logs_time ON symptom_logs(user_id, occurred_at_utc DESC);
CREATE INDEX idx_sym_logs_def  ON symptom_logs(user_id, symptom_id, occurred_at_utc DESC);

CREATE TABLE context_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_id      TEXT NOT NULL REFERENCES context_definitions(id),
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    intensity       INTEGER CHECK (intensity BETWEEN 1 AND 10),
    note            TEXT
);
CREATE INDEX idx_ctx_logs_time ON context_logs(user_id, occurred_at_utc DESC);
CREATE INDEX idx_ctx_logs_def  ON context_logs(user_id, context_id, occurred_at_utc DESC);

-- 4. Unified Timeline View (simplifies History feed & exports)
CREATE VIEW v_unified_timeline AS
SELECT id, user_id, 'exercise' AS event_type, exercise_id AS def_id,
       occurred_at_utc, tz_offset_min, effort_rpe AS primary_metric, note
FROM exercise_logs
UNION ALL
SELECT id, user_id, 'symptom' AS event_type, symptom_id AS def_id,
       occurred_at_utc, tz_offset_min, severity AS primary_metric, note
FROM symptom_logs
UNION ALL
SELECT id, user_id, 'context' AS event_type, context_id AS def_id,
       occurred_at_utc, tz_offset_min, intensity AS primary_metric, note
FROM context_logs;
