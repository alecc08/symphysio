# API

Everything the app does is here. JSON only, versioned under `/api/v1`, no
request or response bodies larger than `SYPHYSIO_MAX_BODY_BYTES` (256 KiB by
default).

## Auth model

Sessions are **cookies**, not bearer tokens:

| Cookie | HttpOnly | Purpose |
| --- | --- | --- |
| `symphysio_session` | yes | opaque 256-bit random token; stored server-side as SHA-256 |
| `symphysio_csrf` | no | random value the SPA echoes in `X-CSRF-Token` |

- Send `credentials: "include"` from the browser; there is no CORS because the
  SPA is served from the same origin.
- A session is valid for `SYPHYSIO_SESSION_TTL_DAYS` (30) and is **rolled
  forward** at half its life, so an actively used phone never gets logged out
  mid-log.
- Expired or revoked sessions return `401 {"detail": "…"}`. There are no
  refresh tokens to leak.

### CSRF rule

Any state-changing request (`POST`/`PATCH`/`DELETE`) to `/api/v1/...` **that
carries a session cookie** must send `X-CSRF-Token` equal to the
`symphysio_csrf` cookie. `/auth/login` and `/auth/register` are exempt (no
session to protect yet). A safe `GET` with a session but no CSRF cookie mints a
fresh one, so the SPA can always recover.

### Rate limiting

`/api/v1/auth/*` is limited per client IP: `SYPHYSIO_RATE_LIMIT_ATTEMPTS`
(default 10) attempts per `SYPHYSIO_RATE_LIMIT_WINDOW` (900 s), then a
`SYPHYSIO_RATE_LIMIT_LOCKOUT` (900 s) lockout. Login is additionally keyed per
email. Exceeding it returns `429` with `Retry-After`.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/auth/register` | `{email, password}` → `201` + session cookies + seeded catalog |
| `POST` | `/auth/login` | `{email, password}` → `200` + session cookies |
| `POST` | `/auth/logout` | revokes this session, clears cookies → `204` |
| `POST` | `/auth/logout-all` | revokes every session for the user → `204` |
| `GET` | `/auth/me` | current user, or `401` |
| `POST` | `/auth/verify` | `{token}` → `204`; unknown token → `400`, expired or already used → `410` |
| `POST` | `/auth/verify/resend` | session required → `202`; email not configured, or the account is already confirmed → `409`; over the send budget → `429` + `Retry-After` |
| `GET` | `/catalog/{kind}` | `kind` ∈ `exercises`, `symptoms`, `contexts`; `?include_archived=true`; contexts also take `?category=relief\|trigger` |
| `GET` | `/catalog/{kind}/suggestions` | preset ideas the user does not already have, shaped as that kind's create body |
| `POST` | `/catalog/{kind}` | create → `201` |
| `PATCH` | `/catalog/{kind}/{id}` | rename / dose / `is_archived` / `sort_order` |
| `POST` | `/catalog/{kind}/reorder` | `{ids: […]}` — full permutation of visible rows |
| `POST` | `/logs/exercises` | `{exercise_id, occurred_at_utc?, tz_offset_min, sets_done?, reps_done?, duration_sec?, effort_rpe?, pain_during?, note?}` → `201` |
| `POST` | `/logs/symptoms` | `{symptom_id, severity, duration_min?, body_region?, …}` → `201` |
| `POST` | `/logs/contexts` | `{context_id, intensity?, …}` → `201` |
| `GET` | `/timeline` | merged feed, keyset paged |
| `PATCH` | `/logs/{event_type}/{id}` | partial edit; same row, same id |
| `DELETE` | `/logs/{event_type}/{id}` | hard delete (this is the Undo path) → `204` |
| `GET` | `/analytics/summary` | `{days}` → totals, daily series, top presets, streak |
| `GET` | `/analytics/lag-correlations` | `{min_hr, max_hr, days, min_count, limit}` |
| `GET` | `/analytics/time-of-day` | `{days, event_type}` → 24 buckets in the user's local clock |
| `GET` | `/export/csv` | flat time series, `Content-Disposition: attachment` |
| `GET` | `/export/json` | definitions + logs + timeline + schema version |
| `GET` | `/healthz` | liveness, no auth |

`event_type` ∈ `exercise | symptom | context`.

## Email confirmation

Email is optional. The server only offers it when `RESEND_API_KEY`,
`SYPHYSIO_EMAIL_FROM` and `SYPHYSIO_PUBLIC_URL` are all set; with no email
configured every account is born `is_verified: true` and nothing changes.

- `POST /auth/register` queues a confirmation link in the response's background
  task. The link is `{SYPHYSIO_PUBLIC_URL}/verify?token=…`; the SPA at `/verify`
  lifts the token out of the address bar and posts it as JSON to `/auth/verify`,
  so the **API** never has a token in a URL. The page navigation itself does
  carry it, which is why the image starts uvicorn with `--no-access-log` and why
  your proxy should mask the `token` parameter (DEPLOYING.md).
- `/auth/verify` returns `204` on success. Anything else is a fresh start for the
  user: `400 {"detail": "That confirmation link is not valid."}`,
  `410 "…has expired. Request a new one."`, `410 "…has already been used."`.
  The SPA then offers "send it again", which calls `/auth/verify/resend`.
- `/auth/verify/resend` requires a session (it is the signed-in banner, not a
  public form). Issuing a new link **expires** the previous one, so two inboxes
  never hold two live links.
- `GET /auth/me` carries `is_verified`. The UI's reminder banner keys off it.
- **Off.** `SYPHYSIO_EMAIL_CONFIRMATION=off`: no confirmation link is ever mailed,
  accounts are born confirmed, and `/auth/verify/resend` answers
  `409 {"detail": "Email confirmation is not enabled on this server."}`. An install
  with no mail transport behaves the same way without being told to.
- **Registration is open by default** and can be closed with
  `SYPHYSIO_ALLOW_REGISTRATION=0`, after which `POST /auth/register` answers
  `403 {"detail": "Registration is closed on this instance."}`. Close it on
  anything the internet can reach — [DEPLOYING.md](DEPLOYING.md).
- **Soft gate (default).** `SYPHYSIO_EMAIL_CONFIRMATION=optional`: an unconfirmed
  account works; the only consequence is the banner. Postnatal care should not
  hinge on an email that may never arrive, so this is the default and the
  recommendation.
- **Hard gate.** `SYPHYSIO_EMAIL_CONFIRMATION=required`: `POST /auth/login` for
  an unconfirmed account answers `403 {"detail": "Confirm your email first — we
  have just sent you a new link."}` and queues a new link in the same response.
  `POST /auth/register` returns the user without session cookies in that mode.
- No health data is ever put in an email: the message carries a link and nothing
  about what is being logged.


## Catalog kinds are not interchangeable

The create models are strict (`extra = "forbid"`) and use different field names:

```jsonc
// POST /catalog/exercises
{ "name": "Pelvic Floor Lifts", "body_region": "pelvic_floor",
  "default_sets": 3, "default_reps": 10, "default_sec": null }

// POST /catalog/symptoms
{ "name": "Heaviness / Dragging", "default_region": "pelvic_floor" }

// POST /catalog/contexts
{ "name": "Sitz Bath", "category": "relief" }
```

`GET /catalog/{kind}/suggestions` returns rows in exactly those shapes, so a
suggestion can be `POST`ed back unchanged — that is asserted by
`tests/test_catalog.py::test_suggestions_post_back_unchanged`.

Definitions are never deleted: `PATCH {"is_archived": true}` hides them from
the picker while their logs stay queryable. Names are unique per user
(case-insensitive), so a duplicate create is a `409`.

## Logging semantics

- `occurred_at_utc` is **when it happened**, not when you tapped. Omit it and the
  server uses `now`. The quick-log drawer sends `-15m / -1h / -3h / custom`
  offsets so a late entry still lands at the right time — the lag analysis
  depends on this.
- `tz_offset_min` is the client's offset from UTC at that instant (±840), which
  is what makes "symptoms cluster in the afternoon" possible without guessing a
  timezone.
- Exercise dose falls back to the definition's defaults when the body omits
  `sets_done`/`reps_done`/`duration_sec`.
- Symptom `severity` is 1–10 and required; `pain_during` is 0–10.

### Timeline paging

```
GET /timeline?limit=50&before=1795439076&event_type=symptom&from=…&to=…
→ { "items": [ … ], "next_before": 1795400001 | null }
```

Pass `next_before` back as `before` for the next (older) page. `limit` ≤ 500.

## Errors

FastAPI's shape, always `{"detail": …}`:

| Status | When |
| --- | --- |
| `401` | missing/expired/revoked session |
| `403` | CSRF header missing or not equal to the CSRF cookie |
| `404` | unknown id, unknown `kind`, or an id belonging to another user |
| `409` | duplicate definition name for this user |
| `422` | validation (strict types, ranges, unknown fields) |
| `413` | body over `SYPHYSIO_MAX_BODY_BYTES` |
| `429` | auth rate limit; `Retry-After` header set |
| `500` | unexpected; the traceback goes to the server log, the body stays generic |

Cross-user ids are `404`, never `403` — the resource does not exist as far as
this account is concerned.
