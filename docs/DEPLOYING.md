# Deploying

One container. It serves the API **and** the compiled SPA, so there is no CORS
story, no second service, and one port to put behind TLS.

```bash
docker compose up -d --build      # 127.0.0.1:8090
```

Then point your reverse proxy at `http://127.0.0.1:8090`.

## Why localhost-only

The container binds to `127.0.0.1:8090` by default. Sessions use `Secure`
cookies and the CSP sends `upgrade-insecure-requests`, both of which assume
HTTPS; if the app were reachable over plain HTTP on a LAN IP, the cookie would
simply not be sent and login would look broken. TLS is the proxy's job.

**Caddy**

```caddy
symphysio.example.com {
    reverse_proxy 127.0.0.1:8090
}
```

**Traefik** (labels are already in `docker-compose.yml`-style; add these)

```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.symphysio.rule=Host(`symphysio.example.com`)
      - traefik.http.routers.symphysio.entrypoints=websecure
      - traefik.http.routers.symphysio.tls=true
      - traefik.http.services.symphysio.loadbalancer.server.port=8000
    networks: [proxy]
```

**nginx**

```nginx
location / {
    proxy_pass http://127.0.0.1:8090;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;
}
```

`X-Forwarded-For` must be set by the proxy: the auth rate limiter keys on it
(see SECURITY.md).

## Container hardening

The image is multi-stage (`node:24-alpine` builds the SPA, `python:3.12-slim`
runs it) and the runtime stage:

- creates uid `10001` and runs as it — never root;
- keeps the root filesystem read-only; the only writable paths are `/data` and a
  64 MiB `/tmp` tmpfs;
- `cap_drop: ALL`, `no-new-privileges:true`, `pids_limit: 128`, `mem_limit: 384m`;
- has a `HEALTHCHECK` against `/healthz`;
- installs runtime dependencies with `uv sync --frozen --no-dev` from the locked
  `uv.lock`, and runs uvicorn straight from the venv (uv is not in the image at
  runtime).

The compose file mirrors the same flags, so `docker run` and `docker compose`
behave identically.

**`/data` ownership matters.** The image runs as uid 10001, so a bind mount must
be chowned first or the app dies with `unable to open database file`:

```bash
mkdir -p data && sudo chown 10001:10001 data   # then use - ./data:/data
```

The default `docker-compose.yml` uses a **named volume** (`symphysio-data`),
which inherits the right ownership automatically.

## Environment

Everything is an environment variable; there is no config file and nothing secret
is baked into the image. See `.env.example`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SYPHYSIO_DATA_DIR` | `./data` | where the SQLite file lives; in the image, `/data` |
| `SYPHYSIO_DB_PATH` | `$DATA_DIR/symphysio.sqlite` | explicit database path |
| `SYPHYSIO_STATIC_DIR` | `../frontend/dist` | compiled SPA; the image bakes `/app/static` |
| `SYPHYSIO_MIGRATIONS_DIR` | `./migrations` | forward-only `.sql` files |
| `SYPHYSIO_COOKIE_SECURE` | `1` | `Secure` on both cookies; set `0` only for plain-HTTP dev on a non-localhost origin |
| `SYPHYSIO_SESSION_TTL_DAYS` | `30` | session lifetime (rolled forward at half-life) |
| `SYPHYSIO_MAX_BODY_BYTES` | `262144` | request body cap, enforced before parsing |
| `SYPHYSIO_RATE_LIMIT` | `1` | `0` disables auth rate limiting (dev only) |
| `SYPHYSIO_RATE_LIMIT_ATTEMPTS` | `10` | attempts per window, per IP and per email |
| `SYPHYSIO_RATE_LIMIT_WINDOW` | `900` | sliding window, seconds |
| `SYPHYSIO_RATE_LIMIT_LOCKOUT` | `900` | lockout after the window fills, seconds |
| `RESEND_API_KEY` | unset | Resend key; with a sender and a public URL, email switches on |
| `SYPHYSIO_EMAIL_FROM` | unset | `From:` on confirmation mail, e.g. `Symphysio <confirm@mail.example.org>` |
| `SYPHYSIO_EMAIL_REPLY_TO` | unset | optional `Reply-To:` |
| `SYPHYSIO_PUBLIC_URL` | unset | absolute origin used **only** for the link host, e.g. `https://symphysio.example.org` |
| `SYPHYSIO_MAIL_BACKEND` | `resend` if configured, else `null` | `resend`, `outbox` (write `.eml` files to the data dir, never send) or `null` |
| `SYPHYSIO_EMAIL_TTL_SECONDS` | `86400` | how long a confirmation link works (floor 300) |
| `SYPHYSIO_EMAIL_SENDS_PER_HOUR` | `3` | per-account send budget, counted in the database |
| `SYPHYSIO_REQUIRE_EMAIL_VERIFICATION` | `0` | `1` blocks sign-in until the link is clicked; the server refuses to start with `1` and no email configured |

## Outbound email (optional)

Nothing needs it. With no `RESEND_API_KEY` the mail backend is `null`, every
account is created confirmed, and a homelab running on a LAN with no route to the
internet behaves exactly as it did before this feature.

To turn it on with Resend:

1. **Verify a domain** in the Resend dashboard (not just the shared
   `onboarding@resend.dev` address — that one only mails your own account).
2. **Publish the SPF and DKIM records** Resend shows you. SPF: a `TXT` record at
   the sending domain containing `v=spf1 include:amazonses.com ~all`. DKIM: the
   three-`TXT`-record set under `_resend._domainkey` (or the key selector they
   show). Resend also offers a DMARC report address; a
   `_dmarc` `TXT` record with `p=none` is enough to start seeing failures.
   Skip this and your confirmation mail lands in spam, which looks identical to
   the feature being broken.
3. **Create an API key** and put it in the environment as `RESEND_API_KEY`
   (`docker-compose.yml` reads it from the host environment; it is not
   committed).
4. Set `SYPHYSIO_EMAIL_FROM` to an address on that domain and
   `SYPHYSIO_PUBLIC_URL` to the origin your phone actually reaches. The link host
   comes from this variable, never from the request's `Host` header, so a reverse
   proxy in front does not change what lands in the mail.
5. Leave `SYPHYSIO_REQUIRE_EMAIL_VERIFICATION=0` unless you specifically want the
   hard gate. The soft default is deliberate: a postnatal user whose
   confirmation mail went to spam should not be locked out of their diary.

Developing without sending anything:

```bash
SYPHYSIO_MAIL_BACKEND=outbox \
SYPHYSIO_PUBLIC_URL=https://symphysio.test \
RESEND_API_KEY=dev_never_real \
SYPHYSIO_EMAIL_FROM='Symphysio <confirm@example.org>' \
uvicorn app.main:app
```

`outbox` writes each message into the data directory as `outbox/<id>.eml` and
logs the path, which is what the Playwright flow in `docs/ROADMAP.md` follows to
click a real link. It never touches the network. `null` accepts the send and
drops it, which is the right setting for tests.

## One worker, on purpose

The rate limiter and the SQLite write lock live in one process, and SQLite is a
file inside the container. Start exactly one uvicorn worker:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000      # no --workers
```

Want more than one process? Move the limiter to Redis and move SQLite to a real
server (or Postgres) first. Until then, one worker comfortably handles a single
person tapping a phone.

## Without Docker

```bash
cd backend && uv sync --frozen
SYPHYSIO_DATA_DIR=/var/lib/symphysio uv run uvicorn app.main:app --port 8090
```

Build the SPA first (`cd frontend && npm ci && npm run build`), or point
`SYPHYSIO_STATIC_DIR` at a checkout of `frontend/dist`. Under systemd, run as a
dedicated user and give it only the data directory:

```ini
[Service]
User=symphysio
Group=symphysio
Environment=SYPHYSIO_DATA_DIR=/var/lib/symphysio
ExecStart=/usr/local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090
ProtectSystem=strict
ReadWritePaths=/var/lib/symphysio
PrivateTmp=true
NoNewPrivileges=true
```

## Upgrading

Migrations run automatically at startup, in filename order, and are recorded in
`schema_migrations`. Take a backup first (see BACKUPS.md), then:

```bash
git pull && docker compose up -d --build
```

Roll back by restoring the pre-upgrade backup and starting the previous image.
Rolling back *code* after a migration has run is only safe if the migration was
additive — that is why migrations are never edited after release.

## Verifying a deployment

```bash
curl -fsS https://symphysio.example.com/healthz          # {"status":"ok"}
curl -sSD- -o /dev/null https://symphysio.example.com/ | grep -i content-security-policy
docker compose ps                                        # healthy
docker compose logs --since 5m | grep -i error
```

Then in a phone browser: register → log two exercises with a `-1h` chip → Undo
one → check Insights shows the lag panel and the daily bars.

## PWA notes

- `/manifest.webmanifest` and `/sw.js` must be served from the origin root —
  they are, by the app itself, not by the proxy.
- The service worker caches only the app shell. API responses are never cached:
  a stale number in a health diary is worse than an error message.
- `npm run build` regenerates hashed asset names, so an app update rolls out on
  the next visit instead of sticking in the cache.
