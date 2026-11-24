# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version of record is the [`VERSION`](VERSION) file — see
[docs/RELEASES.md](docs/RELEASES.md) for how a release is cut and what the
numbers mean here.

## [Unreleased]

Tooling only — no application code, so no image change and no version bump.

- **The release job's own image check had never once passed.** `build.yml` verifies
  the image it pushed by starting it with the compose hardening flags — but with no
  `/data` mount, and the app exits 3 when its database path is not writable
  (`sqlite3.OperationalError: unable to open database file`). The push above that
  step succeeded, so `:0.1.1` and `:0.1.2` exist on GHCR while the job that claims to
  have verified them was red every time. Measured by pulling `:0.1.2` and running the
  step's exact flags. It now mounts a named volume like the CI smoke test does, and
  removes it.
- **`scripts/preflight.py`** measures a deployment over HTTP rather than trusting
  these docs: that no account can read, edit or export another's rows, and that the
  login limiter keys on the socket peer unless that peer is a listed proxy. Run
  against 0.1.2 it is clean in both modes; the same script against 0.1.1 answers
  `[401, 401, 401]` where a lockout should be.

## [0.1.3] - 2026-11-24

### Fixed

- **The severity scale was off the top of the screen on a phone.** The quick-log
  drawer is anchored to the bottom of the viewport and was sized to its own content,
  so a drawer taller than the screen grew upward past the top edge — and nothing
  scrolled, because `body` is pinned while the drawer is open. Symptoms is the
  tallest drawer (score scale, duration chips, time chips, then the preset grid),
  and the scale it asks for first was the first thing lost. Measured in Chromium at
  390x664 CSS px — a 390x844 phone once browser chrome is taken off — the panel was
  986 px tall with 322 px above the fold and **none of the ten severity buttons on
  screen**; the drawer showed only the time strip and the presets. At 360x640 even
  the time strip was gone. Any drawer did the same once the account had enough
  presets. The panel is now capped at `88dvh` and its body scrolls, with the title
  and subtitle pinned above it. Re-measured at 360x640, 390x664, 390x844 and
  430x932: the panel is fully on screen in all four, all ten severity buttons are
  visible without scrolling, and the preset list is what scrolls. The History
  edit-entry drawer, which shares `Sheet.tsx`, already fit at those sizes and is
  unchanged.

## [0.1.2] - 2026-11-23

Two holes found by attacking the published image rather than reading the code, and
a streak that disagreed with itself around midnight.

### Fixed

- **The login limiter believed a header the caller controls.** `X-Forwarded-For`
  was used whenever it was present, so every guess could arrive with a new address.
  Measured against `ghcr.io/alecc08/symphysio:0.1.1` with
  `SYPHYSIO_RATE_LIMIT_ATTEMPTS=1`: one failed login, then a second carrying
  `X-Forwarded-For: 9.9.9.9`, answered `401` — not `429`. One header per request
  and the per-IP budget never ran out, on any instance whose port can be reached
  without going through the proxy. The client address is now the **socket peer**,
  and the header is consulted only when that peer is one of the new
  `SYPHYSIO_TRUSTED_PROXIES` CIDRs, and only down to the right-most hop that is not
  itself a listed proxy. Behind Traefik that peer is the proxy container, so the
  list has to name its network — [docs/DEPLOYING.md](docs/DEPLOYING.md) item 2.
  Empty, the default, means "no proxy": right for `uv run uvicorn` on a laptop, and
  one shared budget behind a proxy, which is why deploying behind one is now a
  configuration step rather than an assumption.
- **Confirmation tokens were written into access logs.** The emailed link opened as
  `GET /verify?token=…`, so whoever terminates TLS logged a live token. It is now
  `/verify#token=…`: a fragment is never sent to a server, so there is nothing left
  to mask at Traefik, Caddy or nginx. The SPA still understands a `?token=` link,
  so mail sent by 0.1.0 and 0.1.1 keeps working.
- **An exercise streak read 0 for anyone west of UTC.** Day buckets are cut in the
  user's frame (`occurred_at_utc + tz_offset_min * 60`), but "logged today or
  yesterday?" was asked against UTC. For UTC-5 those calendars disagree for five
  hours a day — the evening, which is when people log — and four evenings in a row
  answered 0. The test suite passed in the morning and failed in the evening, which
  is how this shipped.

### Notes

- Deploying behind a proxy is now an explicit line in `.env.example`,
  `docker-compose.yml` and the DEPLOYING checklist. A `SYPHYSIO_TRUSTED_PROXIES`
  value that is not a valid IP or CIDR stops the container at startup instead of
  quietly dropping the entry.

## [0.1.1] - 2026-11-23

Release tooling only — no application code changed, and the container is the same
apart from the `.github/workflows` files, which are not in the image.

### Fixed

- **A release published no image.** `v0.1.0` got a tag and a GitHub Release but no
  container: `release.yml` ends by dispatching `build.yml` for the tag it created
  (a tag made with `GITHUB_TOKEN` does not fire `on.push.tags`), and
  `workflow_dispatch` had been removed from `build.yml` in order to silence
  zizmor's `cache-poisoning` rule. The dispatch answered HTTP 422 and the release
  half-completed. Dispatch is restored, the ignore comment now explains why the
  rule does not apply here, and the cache stays scoped per ref.
- **The version tag on the image is stated explicitly** (`type=raw` from `VERSION`
  when the ref is a tag). `docker/metadata-action`'s `semver` type is
  event-sensitive and a dispatched run is not a tag push, so `:0.1.0` would have
  depended on an implementation detail.

### Notes

- `ghcr.io/alecc08/symphysio:0.1.0` does not exist and will not be created: the
  tag at that commit carries the broken workflow, and a published tag is never
  moved. **Deploy `0.1.1`** (or `:latest`).

## [0.1.0] - 2026-11-23

The whole of the v1 brief ([REQUIREMENTS.md](REQUIREMENTS.md)): a mobile-first,
installable "click and log" tracker for postnatal pelvic-floor physiotherapy and
symptoms, in one container with one SQLite file and no third-party services.

### Added

- **Log** — four kinds (Physio, Symptoms, Relief/Meds, Triggers). Tap a tile,
  tap a preset, saved; each drawer carries dose / effort / pain / severity /
  duration and a `Now · -15m · -1h · -3h · Custom` time strip, so a late entry
  still lands at the right timestamp. Presets are per user, reorderable, and
  removable in one tap; a suggested-preset pool covers the common postnatal set.
- **Undo** — every write answers with the row it wrote and can be reversed for
  5 seconds; nothing is silently destroyed.
- **History** — one chronological feed across all four kinds, with filters,
  inline edit (severity, note, time) and delete-with-undo.
- **Insights** — daily counts, severity trend, hour-of-day distribution, top
  presets, and exercise→symptom lag correlation over a configurable window. The
  charts are hand-built SVG; no charting dependency.
- **History is durable** — definitions are archived rather than deleted, so old
  logs keep their meaning; the database schema records events, not summaries.
- **Export** — CSV and JSON of everything, one click, in Settings.
- **PWA** — installable on iOS and Android, offline app shell, brand icons and
  a service worker that can be versioned out of cache.
- **Email confirmation (optional)** — a single-use 256-bit token, stored only as
  a SHA-256 digest, 24 h TTL, never in an API URL. `SYPHYSIO_EMAIL_CONFIRMATION`
  is the admin's switch: `optional` (default) mails a link and shows a reminder
  banner but never blocks anyone, `required` gates sign-in, and `off` means this
  app never sends mail at all. With no mail transport configured the app behaves
  as if it were off, so a LAN install stays exactly as it was.
- **Brand mark** — one logo, two colours, generated from a single geometry source
  (`scripts/gen_brand_assets.py`) into the SVGs, the PNG launcher icons, the
  favicon and the React component, so no two copies can disagree.

### Security

- Argon2id password hashing with pinned parameters and rehash-on-login; ≥ 12
  characters, no email reuse, no keyboard runs, no famous passwords.
- Opaque 256-bit session cookies stored as digests, rolled forward at half-life,
  `HttpOnly` / `Secure` / `SameSite=Lax`; sign out one device or all of them.
- Double-submit CSRF on every state-changing `/api/v1` call, in addition to
  `SameSite=Lax`.
- Sliding-window rate limiting on `/api/v1/auth/*`, per IP and per email. Every
  rejected sign-up is charged to it — weak password, an address that exists, or
  registration being closed. Until now the `register:` window was checked but
  never filled, so the one unauthenticated endpoint that pays for an Argon2id
  hash could not answer `429` at all.
- **Sign-up can be closed** with `SYPHYSIO_ALLOW_REGISTRATION=0`, for any install
  the internet can reach once its own accounts exist.
- **No uvicorn access log in the image.** The confirmation link is opened as
  `GET /verify?token=…`, and uvicorn recorded that request line verbatim, putting
  live tokens in `docker logs`. Traffic belongs at the reverse proxy, with the
  `token` parameter masked — [docs/DEPLOYING.md](docs/DEPLOYING.md) says how.
- CSP with no `unsafe-inline` (`script-src 'self'`, `style-src 'self'`),
  `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy` denying camera/mic/geolocation/payment, `no-store` on
  every response.
- Raw parameterized SQL only (no ORM, no string-built queries), strict
  `extra="forbid"` request models, body size capped before parsing.
- Container runs as uid 10001 with `cap_drop ALL`, `no-new-privileges`, a
  read-only root filesystem and only `/data` plus a small `/tmp` writable.

### Tools

- GitHub Actions: tests, lint, `pip-audit` / `npm audit`, a container smoke
  test, secret and workflow scanning, and a weekly re-run of the dependency
  audits ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
- Release automation: merging to `main` with a new `VERSION` publishes a GitHub
  Release and a GHCR image tagged with the version
  ([`release.yml`](.github/workflows/release.yml),
  [`build.yml`](.github/workflows/build.yml)).
- Dependabot for npm, pip, Docker and Actions, with `uv.lock` verified on every
  PR.

[Unreleased]: https://github.com/alecc08/symphysio/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/alecc08/symphysio/releases/tag/v0.1.3
[0.1.2]: https://github.com/alecc08/symphysio/releases/tag/v0.1.2
[0.1.1]: https://github.com/alecc08/symphysio/releases/tag/v0.1.1
[0.1.0]: https://github.com/alecc08/symphysio/releases/tag/v0.1.0
