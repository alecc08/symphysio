# API

Everything the app does is here. JSON only, versioned under `/api/v1`, no
request or response bodies larger than `SYMPHYSIO_MAX_BODY_BYTES` (256 KiB by
default).

## Auth model

Sessions are **cookies**, not bearer tokens:

| Cookie | HttpOnly | Purpose |
| --- | --- | --- |
| `symphysio_session` | yes | opaque 256-bit random token; stored server-side as SHA-256 |
| `symphysio_csrf` | no | random value the SPA echoes in `X-CSRF-Token` |

- Send `credentials: "include"` from the browser; there is no CORS because the
  SPA is served from the same origin.
- A session is valid for `SYMPHYSIO_SESSION_TTL_DAYS` (30) and is **rolled
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

`/api/v1/auth/*` is limited per client IP: `SYMPHYSIO_RATE_LIMIT_ATTEMPTS`
(default 10) attempts per `SYMPHYSIO_RATE_LIMIT_WINDOW` (900 s), then a
`SYMPHYSIO_RATE_LIMIT_LOCKOUT` (900 s) lockout. Login is additionally keyed per
email. Exceeding it returns `429` with `Retry-After`.

## Language and time zone

Two locales ship: `en` (formatted `en-CA`) and `fr` (formatted `fr-CA`). They are
a server concern as well as a UI one, because the server writes words of its own:
the confirmation and reset mails, every `detail` string, the CSV header row.

**Which language a request gets.** `Accept-Language` is parsed with quality
values, skipping subtags this app does not speak (`fr-CA,fr;q=0.9` → French;
`de,en;q=0.8` → English, and an unsupported tag is *not* counted as English).
Nothing about the answer changes except its wording:

| Surface | Whose language wins |
| --- | --- |
| Emails (confirm, reset) | the **account's** `locale` — the person reading the mail is the account |
| `detail` on a failed request | the **request's** `Accept-Language` |
| Failed login, password-reset request and confirm | the request header, **always** |
| CSV header row | the request header |
| Catalog labels at sign-up (`/catalog/profiles`) | the request header |

The last two rows are a security choice, not a translation one. Reading the
stored locale to answer "is this address registered?" would tell an attacker what
language that account had chosen — an account-enumeration side channel worth less
than nothing. So those responses follow the header, and the *mail* they queue
follows the account.

`POST /auth/register` seeds presets in the language it was asked for (header, or
the `locale` field in the body). That is the only moment the choice can be
applied to content: preset names become rows, and rows are the person's data —
switching the language later never renames a symptom someone has been logging
for months. The same rule covers `body_region` tokens and every enum value in the
CSV: the API and the file keep the English token, the UI translates the *label*.

**Time zone.** `users.timezone` holds an IANA name, `null` meaning "never chose",
which is different from "chose UTC". An instance default,
`SYMPHYSIO_DEFAULT_TIMEZONE`, covers everyone who has not chosen — a homelab
where the whole household is in one city. Nothing else about a zone is allowed to
reach the data, so there are two questions and two answers:

- *What does "today" mean on this screen right now?* The account's zone, else the
  `X-Timezone` header on the request (the only thing a signed-out browser can
  offer), else the instance default, else UTC.
- *Which rows fall in the last 30 days?* If the account **or** the deployment has
  named a zone, that zone cuts the range. If neither has — every install that
  existed before 0.3.0 — the old inference stays: the newest `tz_offset_min` this
  account has ever written, because a diary already knows where the person was,
  and falling back to UTC would silently shift their whole history one day over.

Every log row still stores the `tz_offset_min` it was written with, and day
buckets are computed from it. Changing a time zone — or flying to another city —
therefore never rewrites history: tonight's entry lands in the new zone's day,
and last month's stays where it was written. `X-Timezone` is a display hint and
is ignored for a signed-in account's maths; the offset column remains the record.

`GET /auth/preferences` returns `{locale, timezone, effective_timezone,
utc_offset}`; `PATCH` takes any subset, validates the zone against the IANA
database, and answers `422` naming the accepted values rather than accepting a
typo that would silently shift someone's days.


## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/auth/register` | `{email, password, profile?, locale?, timezone?}` → `201` + session cookies + seeded catalog. `profile` is a key from `/catalog/profiles`; `"postnatal_pelvic"` when omitted (old clients), `"none"` seeds nothing; an unknown key is a `422`. `locale` (`en`\|`fr`) decides the language the catalog is seeded in and the language of the confirmation mail; omitted, it comes from `Accept-Language`. `timezone` is optional and deliberately **not** filled in by the SPA from the browser — see Language and time zone |
| `POST` | `/auth/login` | `{email, password}` → `200` + session cookies |
| `POST` | `/auth/logout` | revokes this session, clears cookies → `204` |
| `POST` | `/auth/logout-all` | revokes every session for the user → `204` |
| `GET` | `/auth/me` | current user (including `profile_key`, `locale`, `timezone`), or `401` |
| `GET` | `/auth/preferences` | `{locale, timezone, effective_timezone, utc_offset}` — `timezone` is what the *account* says, `effective_timezone` what the server will actually use |
| `PATCH` | `/auth/preferences` | any subset of `{locale, timezone}`; `timezone: null` means "back to the server default", an unknown zone name → `422` |
| `POST` | `/auth/verify` | `{token}` → `204`; unknown token → `400`, expired or already used → `410` |
| `POST` | `/auth/password-reset/request` | `{email}` → always `202`, whether or not the address exists. Per-IP and per-email limits → `429` + `Retry-After`. The link goes to `{public_url}/reset#token=…`: the token is in the fragment, so it never reaches an access log |
| `POST` | `/auth/password-reset/confirm` | `{token, password}` → `204` and every session is revoked; weak password → `422` **before** the token is spent; used or expired token → `410` |
| `POST` | `/auth/verify/resend` | session required → `202`; email not configured, or the account is already confirmed → `409`; over the send budget → `429` + `Retry-After` |
| `GET` | `/catalog/{kind}` | `kind` ∈ `exercises`, `symptoms`, `contexts`; `?include_archived=true`; contexts also take `?category=relief\|trigger` |
| `GET` | `/catalog/{kind}/suggestions` | preset ideas the user does not already have, shaped as that kind's create body |
| `GET` | `/catalog/profiles` | **public** (sign-up has no session yet): `[{key, label, blurb, counts, windows, default_window}]`, windows sorted smallest first. Names and counts only, never account data |
| `POST` | `/catalog/{kind}` | create → `201` |
| `PATCH` | `/catalog/{kind}/{id}` | rename / dose / `is_archived` / `sort_order` |
| `POST` | `/catalog/{kind}/reorder` | `{ids: […]}` — full permutation of visible rows |
| `POST` | `/logs/exercises` | `{exercise_id, occurred_at_utc?, tz_offset_min, sets_done?, reps_done?, duration_sec?, effort_rpe?, pain_during?, note?}` → `201`. `sets_done: 0` is a *skipped* session: it counts for adherence and is never an exposure |
| `POST` | `/logs/symptoms` | `{symptom_id, severity, severity_default?, duration_min?, body_region?, …}` → `201`. `severity_default: true` means the number was the drawer's 5, not an answer; editing the row clears it |
| `POST` | `/logs/contexts` | `{context_id, intensity?, …}` → `201` |
| `GET` | `/timeline` | merged feed, keyset paged. Deliberately does **not** include plan events — see the note under `/plan-events` |
| `PATCH` | `/logs/{event_type}/{id}` | partial edit; same row, same id |
| `DELETE` | `/logs/{event_type}/{id}` | hard delete (this is the Undo path) → `204` |
| `GET` | `/plan-events` | the appointment layer: `[{id, kind, text, occurred_at_utc, tz_offset_min}]`, `kind` ∈ `appointment`, `programme_change`, `medication`, `goal`, `note` |
| `POST` | `/plan-events` | `{kind, text, occurred_at_utc?, tz_offset_min}` → `201` |
| `PATCH` | `/plan-events/{id}` | partial edit |
| `DELETE` | `/plan-events/{id}` | → `204` |
| `GET` | `/analytics/summary` | `{days}` → totals (with `severity_defaults`), gap-filled `daily` (one point per day, `logged` flag, `exercises_skipped`), `adherence` in whole weeks, `coverage`, top presets, streak |
| `GET` | `/analytics/associations` | `{days, window?, exposure?}` → “what follows a session?”. `window` must be a label the account's profile offers (`422` otherwise) — free-form windows are how you fish a pattern out of noise. Returns `findings` (counts + matched baseline + one fixed verdict word), `gates` (why refused pairs were refused), `pairs_examined`, `coverage` |
| `GET` | `/analytics/symptoms/{definition_id}` | `{days, baseline_days?}` → one symptom against its own first `baseline_days` in the range, with `adherence` beside it. Never a population norm, never another user |
| `GET` | `/analytics/time-of-day` | `{days, event_type}` → 24 buckets in the user's local clock. Descriptive only: it claims no causation |
| `GET` | `/export/csv` | flat time series, `Content-Disposition: attachment`. Includes plan events (mapped to `category`/`note`) and the `severity_default` column. The **header row** is in the request's language and the file starts with a UTF-8 BOM, so Excel opens it with the accents intact; every *value* stays the English token |
| `GET` | `/export/json` | definitions + logs + timeline + `plan_events`, `schema_version: 2` |
| `GET` | `/healthz` | liveness, no auth |

`event_type` ∈ `exercise | symptom | context`.

### Why plan events are not in the timeline view

`plan_events` is a separate table and `v_unified_timeline` deliberately does not
union it: adding it would silently move every count, average and lag number that
view feeds. The History screen merges the two feeds in the client, which is the
only place that needs both.

## Email confirmation

Email is optional. The server only offers it when `RESEND_API_KEY`,
`SYMPHYSIO_EMAIL_FROM` and `SYMPHYSIO_PUBLIC_URL` are all set; with no email
configured every account is born `is_verified: true` and nothing changes.

- `POST /auth/register` queues a confirmation link in the response's background
  task. The link is `{SYMPHYSIO_PUBLIC_URL}/verify#token=…` — a URL **fragment**,
  which a browser never sends to a server, so no access log on the way can record
  a live token. The SPA at `/verify` lifts the token out of the address bar and
  posts it as JSON to `/auth/verify`, so the **API** never has a token in a URL
  either. An older mail that still says `?token=` keeps working.
- `/auth/verify` returns `204` on success. Anything else is a fresh start for the
  user: `400 {"detail": "That confirmation link is not valid."}`,
  `410 "…has expired. Request a new one."`, `410 "…has already been used."`.
  The SPA then offers "send it again", which calls `/auth/verify/resend`.
- `/auth/verify/resend` requires a session (it is the signed-in banner, not a
  public form). Issuing a new link **expires** the previous one, so two inboxes
  never hold two live links.
- `GET /auth/me` carries `is_verified`. The UI's reminder banner keys off it.
- **Off.** `SYMPHYSIO_EMAIL_CONFIRMATION=off`: no confirmation link is ever mailed,
  accounts are born confirmed, and `/auth/verify/resend` answers
  `409 {"detail": "Email confirmation is not enabled on this server."}`. An install
  with no mail transport behaves the same way without being told to.
- **Registration is open by default** and can be closed with
  `SYMPHYSIO_ALLOW_REGISTRATION=0`, after which `POST /auth/register` answers
  `403 {"detail": "Registration is closed on this instance."}`. Close it on
  anything the internet can reach — [DEPLOYING.md](DEPLOYING.md).
- **Soft gate (default).** `SYMPHYSIO_EMAIL_CONFIRMATION=optional`: an unconfirmed
  account works; the only consequence is the banner. Postnatal care should not
  hinge on an email that may never arrive, so this is the default and the
  recommendation.
- **Hard gate.** `SYMPHYSIO_EMAIL_CONFIRMATION=required`: `POST /auth/login` for
  an unconfirmed account answers `403 {"detail": "Confirm your email first — we
  have just sent you a new link."}` and queues a new link in the same response.
  `POST /auth/register` returns the user without session cookies in that mode.
- No health data is ever put in an email: the message carries a link and nothing
  about what is being logged.
- Both messages are written in the **account's** language, chosen at sign-up and
  changeable in Settings. A reset link mailed to an account that reads French
  arrives in French even if the person asked for the link from a browser set to
  English — the mailbox belongs to the account, the browser belongs to whoever is
  sitting in front of it.


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
| `413` | body over `SYMPHYSIO_MAX_BODY_BYTES` |
| `429` | auth rate limit; `Retry-After` header set |
| `500` | unexpected; the traceback goes to the server log, the body stays generic |

Cross-user ids are `404`, never `403` — the resource does not exist as far as
this account is concerned.

Every `detail` string above is one entry in a single table with two languages
(`app/messages.py`), so a French install answers a `429` in French and the
OpenAPI examples stay English. FastAPI's own validation messages are **not**
translated: they name a field and a type, which is the part that has to match the
contract.
