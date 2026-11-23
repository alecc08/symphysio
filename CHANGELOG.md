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
  a SHA-256 digest, 24 h TTL, never in a logged URL. `SYPHYSIO_EMAIL_CONFIRMATION`
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
- Sliding-window rate limiting on `/api/v1/auth/*`, per IP and per email.
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

[Unreleased]: https://github.com/alecc08/symphysio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/alecc08/symphysio/releases/tag/v0.1.0
