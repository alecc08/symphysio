# Roadmap

Not built yet. Each item is written as a design sketch so the shape is decided
before the code exists — the interesting decisions are the schema and the
failure modes, not the API call.

---

## 1. Email confirmation via Resend (next)

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
              └─► 204; the SPA strips ?token= from the URL with history.replaceState
```

The link is `https://<host>/verify?token=…`, handled by the SPA (a tiny
`VerifyPage`) rather than a server-rendered page — one less templating surface,
and the app already has to render this state anyway.

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
SYPHYSIO_REQUIRE_EMAIL_VERIFICATION=0   # 1 = block login until confirmed
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
SYPHYSIO_REQUIRE_EMAIL_VERIFICATION=0
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
- The token appears in a URL the user clicks, which means it can appear in a
  proxy access log. Mitigations: single use, 24 h TTL, `Referrer-Policy:
  no-referrer` (already set), and the SPA removing it from history immediately.

### Tests

- Unit: token is stored hashed; expired/used tokens are rejected; resend
  invalidates the previous token; the rate limits trip.
- Integration: register → outbox has exactly one message → `POST /auth/verify`
  returns 204 and `is_verified = 1`; second use returns `410`.
- Playwright: register, pull the link out of the test outbox endpoint, click it,
  assert the banner disappears and the URL no longer carries `?token=`.
- No test ever calls Resend. `ResendMailer` is covered by a stubbed transport.

### Also unlocked by the same plumbing

`password_reset` is a `purpose` value in the same table and the same mailer — the
next item after confirmation, and it needs an out-of-band channel for exactly the
same reason.

---

## 2. Password reset

Same table, `purpose = 'password_reset'`, 30-minute tokens, and a rule that the
reset link logs the old sessions out. Needs email first, which is why it sits
behind item 1.

## 3. WebAuthn passkeys

Already scoped in REQUIREMENTS.md (Phase 3). Removes the password path for the
people who never want to type one; email confirmation is what makes passkey
recovery possible, so it also sits behind item 1.

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
