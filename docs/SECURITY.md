# Security

Threat model, in the order the data actually gets at risk:

1. **Someone else's phone/laptop gets the session cookie.**
2. **A malicious page tries to make your browser write to the API (CSRF).**
3. **Someone sprays the login endpoint.**
4. **A stored XSS turns the diary into a script host.**
5. **The database file is copied off disk** (backup theft, a compromised host).
6. **SQL injection through a query parameter.**

## Sessions

- 256-bit opaque token (`secrets.token_urlsafe(32)`), stored as
  `sha256(token)` in `sessions.token_hash`. The cookie value is never persisted,
  so a stolen DB cannot be replayed.
- Cookie flags: `HttpOnly` (no script can read it), `Secure` (HTTPS only, on by
  default via `SYPHYSIO_COOKIE_SECURE=1`), `SameSite=Lax` (not sent on
  cross-site POSTs, which kills most CSRF without a token dance), `Path=/`.
- TTL `SYPHYSIO_SESSION_TTL_DAYS` (30 days). A session whose age passes half its
  life is rolled forward — one new row, old row revoked — inside the same
  response that authenticated it. Rolling is capped per request; there is no
  refresh token to steal.
- `POST /auth/logout` revokes one session; `/auth/logout-all` revokes all rows
  for the user (the "someone else has my phone" button in Settings).
- Expiry is enforced at authentication time; rows are deleted when a session is
  revoked or rolled, and `Database.prune_sessions()` sweeps leftovers at startup.
  An abandoned device therefore cannot accumulate live sessions.

## CSRF

Double-submit, enforced by middleware before routing:

- A state-changing `/api/v1` request that carries the session cookie must also
  send `X-CSRF-Token` equal to the **non**-HttpOnly `symphysio_csrf` cookie.
- `/auth/login` and `/auth/register` are exempt: no session exists to protect,
  and requiring a token there would break a fresh browser.
- Both sides are compared with `hmac.compare_digest`.
- `SameSite=Lax` already blocks cross-site *writes*; the token is the second
  layer, and it also protects subdomain/legacy-browser cases.

## Rate limiting

`/api/v1/auth/*` only — the read endpoints are the user's own device.

- Sliding window per client IP: `SYPHYSIO_RATE_LIMIT_ATTEMPTS` (10) per
  `SYPHYSIO_RATE_LIMIT_WINDOW` (900 s) → then `SYPHYSIO_RATE_LIMIT_LOCKOUT`
  (900 s) of `429` with `Retry-After`.
- Login is additionally keyed by email, so a bot rotating IPs still cannot grind
  one account.
- Every rejected sign-up is charged to the limiter: weak password, an address
  that already exists, or registration being closed. That matters more than it
  looks — registration is the only unauthenticated endpoint that pays for an
  Argon2id hash (64 MiB of work per attempt), so an unmetered `/auth/register`
  is a cheap way to spend a home server's CPU and memory. (It was exactly that
  until the router started recording these failures: the window was checked but
  never filled, so `429` could not happen.)
- In-process and per-worker: run **one** uvicorn worker (see DEPLOYING.md). Put
  the limiter in Redis if you ever need more than one process.
- The client key is the **socket peer**, unless that peer is one of
  `SYPHYSIO_TRUSTED_PROXIES`; only then is `X-Forwarded-For` read, and only down
  to the right-most entry that is not itself a proxy of ours. Behind Traefik that
  peer is the proxy container, so the list has to name its network — leave it
  empty and every visitor shares one budget.
- That is not decoration. Before the rule existed, the header was believed
  whenever it was present, measured against the published image with
  `ATTEMPTS=1`: a failed login, then a second carrying `X-Forwarded-For: 9.9.9.9`,
  answered `401`. One header per request and the per-IP budget never ran out.

## Registration

- Open by default — the first account has to come from somewhere, and a home
  server on a LAN has no strangers to keep out.
- `SYPHYSIO_ALLOW_REGISTRATION=0` closes it: `POST /auth/register` answers `403`.
  The refusal is charged to the IP limiter like any other rejected attempt, so
  scanning a closed door costs the same budget as hammering an open one. Any
  instance the internet can see should run closed once its own accounts exist —
  [DEPLOYING.md](DEPLOYING.md) has the checklist.
- Accepted for now: registration reveals whether an address already has an
  account (`409` vs `201`). Closing registration removes that surface for
  strangers; fixing it properly means always creating a pending account and
  letting the mail decide.

## Email confirmation tokens

The same shape as sessions, because the threat is the same: a long random value
in flight, only its SHA-256 digest at rest.

- 256-bit token (`secrets.token_urlsafe(32)`), stored as `sha256(token)` in
  `email_verifications.token_hash`, TTL `SYPHYSIO_EMAIL_TTL_SECONDS` (24 h),
  single use (`used_at_utc`).
- The link is `{SYPHYSIO_PUBLIC_URL}/verify#token=…`, with the token in a URL
  **fragment**. A browser never sends the part after `#` to any server, so no
  access log — uvicorn's, Traefik's, a CDN's — can hold a live token. It used to
  be `?token=`, and it was logged: `GET /verify?token=…` appeared in uvicorn's
  request line. The SPA still understands a query-string link, so a mail from an
  older release keeps working.
- The API receives the token as JSON in a POST body, and the SPA erases it from
  the address bar before anything else runs, so it does not sit in browser history
  or a `Referer` either.
- Lookup is by digest, so a forged token matches no row: guessing is bounded by
  the IP counter on `/auth/*`, not by a per-account budget an attacker can probe
  to enumerate accounts.
- The link host comes from `SYPHYSIO_PUBLIC_URL`, never from the request's
  `Host` header, so a poisoned header cannot mail an attacker-controlled domain
  to your users.
- **Send budget:** `SYPHYSIO_EMAIL_SENDS_PER_HOUR` (3) per account, counted from
  the database rather than memory, so it survives a restart and cannot be
  restarted into bypassing. Resending expires the previous row instead of
  deleting it, so old rows keep counting and no second live link escapes.
- **No health data in email.** `app/emails.py` carries a link and nothing else:
  no symptom names, no counts, no entry dates, no images or tracking pixels.
  The HTML part is escaped and hand-built — no templating engine in the
  dependency set.
- Sends are background tasks after the response, so a slow or dead mail provider
  cannot hang or fail a sign-up. A failed send leaves the account usable in soft
  mode and the banner offers a resend.
- **Admin can opt out entirely:** `SYPHYSIO_EMAIL_CONFIRMATION=off` mails nothing,
  shows no banner and gates nothing, even when a transport is configured.
- **Refused configuration:** `SYPHYSIO_EMAIL_CONFIRMATION=required` without
  email configured aborts startup rather than creating accounts nobody can
  unlock.

## Passwords

- Argon2id, `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4`, 32-byte hash,
  16-byte salt (argon2-cffi defaults, pinned in `app/security.py` so a library
  upgrade cannot silently weaken them).
- `password_needs_rehash` is checked on login; a stronger parameter set later
  means the hash is rewritten on the next successful login.
- Policy (`app/password_policy.py`): ≥ 12 characters, ≤ 128, not the email
  address or its domain, no 6+ character repeat runs, no keyboard runs, and a
  dozen famous 12+-character passwords refused by name. No symbol/uppercase
  mandates and no breached-password corpus: length is what holds up, rule soup
  pushes people to write passwords down, and a weak password someone chose on
  purpose is their own decision — the list of common passwords was a 164 KB
  data file with a generator script, and it once shipped missing from every
  clone and image because a `.gitignore` pattern ate it.
- Input is truncated at 1024 bytes before hashing (argon2-cffi rejects
  oversized inputs; a 1 MiB password would be a cheap DoS).
- Timing: login runs Argon2 verification against a **dummy hash** when the email
  does not exist, so response time does not reveal which emails are registered.
  Registration *does* answer `409` for an existing email — an accepted trade-off
  for a self-hosted diary (no account harvesting at scale), noted here so nobody
  mistakes it for an oversight.

## Injection

- **No ORM, no string SQL.** Every query is a literal in `app/routers/*.py` with
  `?` placeholders; parameters are always bound.
- The few places where a table/column name is interpolated (`catalog.py`'s
  `KINDS`, `analytics.py`'s `_top` spec, `logs.py`'s `TIMELINE_SELECT`) draw from
  hard-coded Python dictionaries keyed by validated `Literal`/pattern-checked
  values — never from request text. Those lines carry an explicit `# noqa: S608`
  so a reviewer sees the reason rather than a bare f-string.
- Ids are treated as opaque strings (≤ 36 chars); user-supplied `event_type` and
  `category` are regex-constrained by Pydantic before they reach SQL.
- Request bodies are capped at `SYPHYSIO_MAX_BODY_BYTES` **before** parsing
  (`limit_body` middleware, checks `Content-Length`).
- All request models are `strict=True, extra="forbid"`: no coercion surprises
  (`"1"` where an int was expected) and no smuggled fields reaching a row.

## Output and headers

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
  img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none';
  base-uri 'self'; form-action 'self'; frame-ancestors 'none'; frame-src 'none';
  upgrade-insecure-requests
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Cache-Control: no-store
```

- `script-src 'self'` with **no `unsafe-inline`**: the SPA ships no inline
  scripts, the manifest and the service worker are same-origin files, and chart
  geometry is set from JS (`.style.height`), never a `style=` attribute, so
  `style-src 'self'` holds too. A stored-note-into-DOM XSS is structurally
  impossible: notes are rendered as React text nodes, and React 19 has no
  `dangerouslySetInnerHTML` path in this codebase.
- `Cache-Control: no-store` on every response: a symptom diary must not sit in a
  shared machine's HTTP cache. Static assets are hashed filenames, so
  no-store costs little; if that matters, exempt `/assets/*` in the proxy.
- Free-text (`note`, preset `name`) is length-capped and stored raw — escaping
  happens at render time, which is the only layer that knows the output context.
- `X-Frame-Options: DENY` + `frame-ancestors 'none'`: no click-jacking a log
  entry.

## Container

- Runs as uid `10001`, non-root, `no-new-privileges`, `cap_drop ALL`,
  `read_only: true` root filesystem, `pids_limit`, `mem_limit`.
- Only `/data` (the SQLite file) and a small `/tmp` tmpfs are writable, so a
  compromise of the process cannot install persistence on disk.
- No secrets in the image or in git; configuration is environment variables
  only. Logging is deliberately thin: uvicorn starts with `--no-access-log`, and
  no application log writes tokens, password hashes or notes. Traffic logging
  belongs at the reverse proxy — and since the confirmation token travels in a
  fragment, there is nothing left there to mask.

## Deliberate gaps

| Gap | Why, and what would close it |
| --- | --- |
| Single-worker rate limiting | homelab scale; move the window to Redis for multiple workers |
| No WebAuthn passkeys | planned; would remove the password path entirely |
| No at-rest encryption of the SQLite file | relies on LUKS/zfs encryption at the host; SQLCipher would be the in-app answer |
| Registration reveals existing emails | `POST /auth/register` answers `409` for a taken address; email verification now exists, so the remaining fix is to always create a pending account and let the mail decide, plus hashed-user lookup |
| No 2FA | passkeys first; TOTP would need recovery codes, which is a bigger support surface |
