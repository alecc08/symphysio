# Architecture

One process, one file, one image. The whole product is a FastAPI app that serves
a JSON API under `/api/v1` and a compiled React bundle everywhere else.

```
 browser (PWA, installable)
        │  fetch(credentials: "include")
        ▼
 ┌───────────────────────────── FastAPI process (uvicorn, single worker) ─────┐
 │ middleware: csrf_guard → limit_body → harden(security headers)             │
 │ routes:   /api/v1/{auth,catalog,logs,timeline,analytics,export}           │
 │ static:   /  /assets/*  /manifest.webmanifest  /sw.js  (StaticFiles)      │
 │ state:    app.state.db (aiosqlite, WAL) · app.state.rate_limiter          │
 └───────────────────────────────────────────┬───────────────────────────────┘
                                             │ parameterized SQL only
                                             ▼
                                  /data/symphysio.sqlite  (WAL)
```

## Request path

1. **`harden`** (outermost) adds `Content-Security-Policy`, `X-Content-Type-Options`,
   `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP and
   `Cache-Control: no-store` to every response.
2. **`limit_body`** rejects anything whose `Content-Length` exceeds
   `SYPHYSIO_MAX_BODY_BYTES` before the body is read or parsed.
3. **`csrf_guard`** requires the `X-CSRF-Token` header to match the readable
   `symphysio_csrf` cookie for state-changing `/api/v1` calls that carry a
   session cookie (`/auth/login` and `/auth/register` are exempt). On a safe
   `GET` it will also mint a CSRF cookie for a session that lost one, so the SPA
   can always bootstrap.
4. **Routing** resolves the session cookie → `sessions.token_hash` → user row.
   Handlers receive the user dict via the `AuthedUser` dependency.
5. **SQLite** access goes through `app/db.py`, which owns the single shared
   connection, its write lock, the pragmas and the migration runner.

## Module map

| Module | Responsibility |
| --- | --- |
| `app/main.py` | App factory, middleware order, security headers, static SPA serving, `/healthz` |
| `app/settings.py` | Environment-only configuration (no config files, no secrets in source) |
| `app/db.py` | aiosqlite connection, `PRAGMA` set, forward-only migrations, query helpers, write lock |
| `app/security.py` | Argon2id hashing, opaque token → SHA-256 storage, cookie issue/clear, CSRF compare |
| `app/ratelimit.py` | Sliding-window auth rate limiter (per process) |
| `app/password_policy.py` | ≥12 chars, breached-password blocklist, no email reuse, no runs |
| `app/ids.py` | UUIDv7 ids (time-ordered, index-friendly) + clock |
| `app/seed.py` | default catalogs written at signup, plus the suggestion pool |
| `app/schemas.py` | Pydantic v2 strict models (`strict=True`, `extra="forbid"`) |
| `app/routers/auth.py` | register / login / logout / logout-all / me |
| `app/routers/catalog.py` | Preset CRUD, archive instead of delete, reorder |
| `app/routers/logs.py` | Fast log writes, unified timeline, edit, delete (= Undo) |
| `app/routers/analytics.py` | Daily summary, lag correlations, hour-of-day |
| `app/routers/export.py` | CSV (flat time series) and JSON (full dump) |

## Frontend structure

```
src/
  api/client.ts        fetch wrapper: cookies + CSRF header, typed ApiError
  api/types.ts         mirrors docs/API.md
  state/session.tsx    whoami / login / register / logout
  state/catalog.tsx    presets, add/patch/reorder, archived visibility
  state/toast.tsx      one Undo pill, 5 s
  lib/time.ts          local-day labels, relative time
  lib/presets.ts       one place that builds a per-kind create body (the three
                       kinds share no field names, so this is not inlined twice)
  lib/useQuickLog.ts   POST + Undo pill + refresh, shared by every drawer
  pages/               LogPage (grid), HistoryPage, InsightsPage, SettingsPage, AuthPage
  components/          Sheet, QuickSheet, TimeChips, SeverityScale, Charts,
                       CatalogManager, BottomNav, icons/{Tile,Ui}
  styles/animations.css  transform/opacity/dashoffset only
```

No client-side router: three tabs plus a settings overlay, so the URL never
needs history rewriting and the static server stays trivial. Everything above
the API is display state — the database is the only source of truth.

## Deliberate constraints

- **Single worker.** The rate limiter and the DB write lock are in-process.
  Scaling out means moving the limiter to a shared store; the SQLite file would
  also need to leave the container. Documented in DEPLOYING.md.
- **No ORM.** Raw SQL with `?` placeholders keeps the query surface auditable and
  keeps the lag-correlation query readable (it is the product's reason to exist).
- **No chart library.** The Insights charts are a few SVG rects/paths, sized in
  JS so the CSP can keep `style-src 'self'`.
- **No service-worker caching of API responses.** An offline-looking number is
  worse than an error. The worker only caches the shell for navigation.
