-- Symphysio 004: the two account-level preferences — language and time zone.
--
-- Both are additive, neither rewrites anything, and both exist because the
-- server had to guess before: it wrote English error text and English preset
-- names into a French account, and it inferred "local time" from the offset the
-- newest row happened to carry (so an empty diary meant UTC, and a person in
-- Montreal saw "today" roll over at 19:00).

-- 1. Language. `en` is the column default because every existing account was
--    seeded from the English preset sets — the default describes history, not
--    policy, exactly like `profile_key` in 003. New accounts choose explicitly
--    at sign-up; `fr` is Québec French (`fr-CA`, `fr-CA` only: the app's copy is
--    one language and the tag's region is not something the server argues about).
ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'en';

-- 2. Time zone, as an IANA name ("America/Toronto"). Nullable on purpose: NULL
--    means "this account never chose", which is not the same as choosing UTC,
--    and it is what lets an instance default (SYMPHYSIO_DEFAULT_TIMEZONE) apply
--    to accounts that never saw the setting.
--
--    This is a *display and default* choice. Every log row keeps the
--    `tz_offset_min` its device reported at that instant, so no stored local
--    day, hour bucket or lag window moves when someone changes this. Re-deriving
--    last March from today's zone would quietly redraw the insights.
ALTER TABLE users ADD COLUMN timezone TEXT;

-- 3. No index on either column: nothing queries "all French accounts" — they are
--    read as part of the one-row session lookup that already exists.
