# Roadmap

Items marked **built** keep their design sketch: the interesting decisions are
the schema and the failure modes, not the API call, and the sketch is where they
are written down. Current behaviour of built items lives in `API.md`,
`DATABASE.md`, `SECURITY.md` and `DEPLOYING.md`.

---

## 1. Email confirmation via Resend — built

**Built as:** `migrations/002_email_verification.sql`, `app/verification.py`,
`app/mailer.py`, `app/emails.py`, `POST /auth/verify`,
`POST /auth/verify/resend`, `UserOut.is_verified`, the `/verify` SPA route and
the in-app reminder banner. 21 tests in `tests/test_email_verification.py`.

**Where it differs from the sketch below:**

- The consumed row is not "token cleared" — it keeps its digest, records
  `used_at_utc`, and is deleted by `prune_verifications` at startup. One column
  is simpler than a scrubbing rule.
- The per-hour budget counts superseded-but-unused rows, because resending
  **expires** the old row instead of deleting it. Deleting them made resends
  free, which is the obvious way to turn a confirmation email into a spam
  cannon.
- Two dev transports exist that the sketch did not mention:
  `SYPHYSIO_MAIL_BACKEND=outbox` (in-memory list plus a readable `.eml` file
  under `<data dir>/outbox`, never sends) and `null` (drops it). Tests use
  `outbox`.
- Hard-gate login answers `403` **and queues a new link in the same response**.
  Raising `HTTPException` there silently dropped the queued send, so the handler
  returns a `JSONResponse` with the background task attached.
- The hard gate refuses to start without email configured, rather than starting
  and locking everyone out.

The sketch, kept as written:

**Why.** Registration currently trusts the address you type. Confirming it buys
three things at once: the account is reachable (password reset later), the
address was typed correctly, and "I lost my phone" stops being "I lost my data".

**Third party.** [Resend](https://resend.com) — transactional email over a small
JSON HTTP API. Chosen over SMTP because it needs no local mail agent inside a
read-only container, gives delivery events, and keeps the container image free of
`sendmail`/`postfix`.

### Flow

```
register ──► users row (is_verified = 0)
        └─► email_verifications row (token_hash, expires_at = now + 24 h)
        └─► mailer.send(to, confirmation link)      ← Resend, in the background
        └─► 201 + session cookie (you are logged in, but flagged unverified)

link clicked ──► POST /api/v1/auth/verify {token}
              └─► token_hash lookup, not expired, not used
              └─► users.is_verified = 1, verified_at_utc = now
              └─► verification row consumed (used_at_utc set, token cleared)
              └─► 204; the SPA clears the token from the URL with history.replaceState
```

The link is `https://<host>/verify#token=…`, handled by the SPA (a tiny
`VerifyPage`) rather than a server-rendered page — one less templating surface,
and the app already has to render this state anyway. The token sits in a URL
**fragment** because a browser never sends the part after `#` to a server.

### Schema (`migrations/002_email_verification.sql`)

```sql
ALTER TABLE users ADD COLUMN is_verified   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN verified_at_utc INTEGER;

CREATE TABLE email_verifications (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash     TEXT NOT NULL UNIQUE,      -- sha256(token), like sessions
    purpose        TEXT NOT NULL CHECK (purpose IN ('confirm_email','password_reset')),
    created_at_utc INTEGER NOT NULL,
    expires_at_utc INTEGER NOT NULL,
    used_at_utc    INTEGER
);
CREATE INDEX idx_email_verif_user ON email_verifications(user_id, purpose, expires_at_utc);
```

Same token discipline as sessions: 256-bit random token, only its SHA-256 is
stored, single use, 24 h expiry, and an expired row is not reusable — resend
instead.

### Unverified policy: soft, and switchable

Default **soft**: an unverified account can log and log data, with a banner in
Settings ("Confirm your email — needed for password recovery"). A hard gate would
mean a misconfigured SMTP lock a person out of their own recovery diary, which is
the opposite of what this app is for.

```
SYPHYSIO_EMAIL_CONFIRMATION=optional   # off | optional | required
```

Deployments with no email configured at all (`RESEND_API_KEY` unset) stay in
soft mode and say so on the register screen — the app must remain fully usable on
a LAN with no outbound email.

### Sending

- `app/mailer.py` with one interface: `send(to, subject, text, html=None) -> None`.
  Two implementations: `ResendMailer` (`POST https://api.resend.com/emails`,
  `Authorization: Bearer $RESEND_API_KEY`, `httpx.AsyncClient` with a 5 s connect
  / 10 s total timeout) and `ConsoleMailer` (dev: prints the link, and tests read
  it from an in-memory outbox).
- Injection point: `app.state.mailer`, chosen by env — so tests never touch the
  network and never assert on HTML.
- **Fire-and-forget with a logged failure.** Registration returns `201` whether or
  not Resend is reachable; a failed send is logged and the verification row stays
  unused so `POST /api/v1/auth/verify/resend` can retry.
- `Retry-After` respected on Resend `429`; at most one retry; never a retry loop.
- Emails contain **no health data** — no symptom names, no counts, not even the
  app name in a way that reads as medical. Subject: `Confirm your Symphysio
  account`. Plain text plus a minimal HTML part, no tracking pixel, no images.

### Limits and abuse

| Control | Value |
| --- | --- |
| Sends per address | 3 per hour (`email:confirm:<addr>`) |
| Sends per IP | 10 per hour (`ip:confirm:<ip>`) |
| Verify attempts per token | 5, then the row is invalidated |
| Verify attempts per IP | 30 per hour, `429` with `Retry-After` |
| Token TTL | 24 h |

Reuses the existing in-process `RateLimiter` (single-worker constraint already
documented in DEPLOYING.md).

### Environment

```
RESEND_API_KEY=re_xxx                 # unset ⇒ email disabled, app still works
SYPHYSIO_EMAIL_FROM=Symphysio <confirm@yourdomain>   # domain must be verified in Resend
SYPHYSIO_EMAIL_REPLY_TO=              # optional
SYPHYSIO_PUBLIC_URL=https://symphysio.example.com    # absolute link in the email
SYPHYSIO_EMAIL_CONFIRMATION=optional
```

`SYPHYSIO_PUBLIC_URL` is required when email is on: a relative link is useless,
and guessing the host from `Host:` invites a phishable link. Domain DKIM/SPF must
be set in Resend before mail stops landing in spam — that is a deployment step,
recorded in DEPLOYING.md when this lands.

### Secrets hygiene

- `RESEND_API_KEY` never appears in logs, error bodies or the container build
  args; it is only read at runtime from the environment.
- Verification tokens are logged as nothing at all (not even a prefix); emails are
  logged masked (`p…e@example.com`) at `INFO`, full address only at `DEBUG`.
- The token appears in a URL the user clicks, so it is in the fragment
  (`/verify#token=…`), which the browser never sends to a server: no proxy or CDN
  access log can record it. Mitigations that were already there: single use, 24 h
  TTL, `Referrer-Policy: no-referrer`, the SPA removing it from history
  immediately, and the image starting uvicorn with `--no-access-log`.

### Tests

- Unit: token is stored hashed; expired/used tokens are rejected; resend
  invalidates the previous token; the rate limits trip.
- Integration: register → outbox has exactly one message → `POST /auth/verify`
  returns 204 and `is_verified = 1`; second use returns `410`.
- Playwright: register, pull the link out of the test outbox endpoint, click it,
  assert the banner disappears and the URL no longer carries the token.
- No test ever calls Resend. `ResendMailer` is covered by a stubbed transport.

### Also unlocked by the same plumbing

`password_reset` is a `purpose` value in the same table and the same mailer — the
next item after confirmation, and it needs an out-of-band channel for exactly the
same reason.

---

## 2. Password reset (next)

Same table, `purpose = 'password_reset'`, 30-minute tokens, and a rule that the
reset link logs the old sessions out. The plumbing shipped with item 1, so this
is now the shortest path: a new purpose, a "forgotten password" route on the
auth screen, and a session-revoking write.

## 3. WebAuthn passkeys

Already scoped in REQUIREMENTS.md (Phase 3). Removes the password path for the
people who never want to type one; email confirmation is what makes passkey
recovery possible, and that landed with item 1.

## 4. Reminders that respect the point of the app

A gentle daily nudge (Web Push) is worth having; a streak-shaming notification is
not. Before building this, decide the rule: reminders fire only when nothing has
been logged that day, never when the user logged a bad day.

## 5. Multiple caregivers / read-only share

A physiotherapist who can read the timeline for 90 days, as a scoped read-only
token, exported rather than live, is simpler and safer than an account-sharing
model. Start with a "share link for this window" export.

## Explicitly not planned

- Social login (the data is health data; an account must not outsource its
  identity to Google).
- Analytics/tracking of any kind inside the app.
- A hosted multi-tenant mode: one instance per person is the deployment model.
