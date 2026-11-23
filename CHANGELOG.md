# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version of record is the [`VERSION`](VERSION) file — see
[docs/RELEASES.md](docs/RELEASES.md) for how a release is cut and what the
numbers mean here.

## [Unreleased]

Nothing beyond the current release. The next items are designed first, in
[docs/ROADMAP.md](docs/ROADMAP.md).

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

[Unreleased]: https://github.com/alecc08/symphysio/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/alecc08/symphysio/releases/tag/v0.1.1
[0.1.0]: https://github.com/alecc08/symphysio/releases/tag/v0.1.0
