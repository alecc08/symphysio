-- 002: email verification (confirmation links, and later password resets).
--
-- Tokens follow the same discipline as sessions (001): a 256-bit random token
-- goes to the user, and only its SHA-256 digest is ever stored.
--
-- Accounts that already exist were created before this feature existed and were
-- never asked to confirm anything, so the column defaults to 1 and they stay
-- usable; the register endpoint writes an explicit 0 when email is configured.

ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN verified_at_utc INTEGER;

CREATE TABLE email_verifications (
    id              TEXT PRIMARY KEY,              -- UUIDv7
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,          -- sha256(token); the token itself is never stored
    purpose         TEXT NOT NULL CHECK (purpose IN ('confirm_email', 'password_reset')),
    created_at_utc  INTEGER NOT NULL,
    expires_at_utc  INTEGER NOT NULL,
    used_at_utc     INTEGER                        -- set when consumed (single use)
);

CREATE INDEX idx_email_verif_user ON email_verifications(user_id, purpose, expires_at_utc);
