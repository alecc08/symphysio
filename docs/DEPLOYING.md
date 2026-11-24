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

## If this instance is reachable from the internet

Everything above is enough for a LAN or Tailscale install. Exposing it to the
whole internet means four more decisions, all cheap:

1. **Close the front door.** Sign up your own accounts, then set
   `SYMPHYSIO_ALLOW_REGISTRATION=0`. Registration is open by default (the first
   account has to come from somewhere) and a public host gets scanned within
   hours. `POST /auth/register` then answers `403` — after the IP limiter, so
   probing it is not free for the prober.
2. **Tell it where your proxy is**, or the login limiter is theatre in one of two
   directions. With `SYMPHYSIO_TRUSTED_PROXIES` empty, the client address is the
   socket peer — behind Traefik that is the proxy container, so one visitor's typo
   locks out every other visitor. Make it too wide and a caller can forge
   `X-Forwarded-For` and buy an unlimited number of guesses (that was the behaviour
   until the rule existed, and it was measured, not theorised). Name the network
   your proxy actually connects from — for Docker, its own network's CIDR:

   ```bash
   SYMPHYSIO_TRUSTED_PROXIES=172.17.0.0/16     # traefik's docker network, not the LAN
   ```

   Nothing needs masking in the proxy's access log: the confirmation link carries
   its token in a URL fragment, which a browser never sends to a server. The
   container also runs uvicorn with `--no-access-log`.
3. **HSTS at the proxy** (`max-age=31536000; includeSubDomains`). The app sends
   CSP with `upgrade-insecure-requests` but not HSTS, because getting this value
   wrong is a lockout and it belongs with the certificate.
4. **Pin the image tag** — `ghcr.io/alecc08/symphysio:0.1.2`, not `:latest`.
   Migrations are forward-only, so `:latest` moving under you means a rollback
   needs a restore, not a pull (see [RELEASES.md](RELEASES.md)).

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

### 0.3.0 renamed the prefix, and there is no alias

Up to and including 0.2.0 the app read `SYPHYSIO_*` — a misspelling of its own
name, which every deployment file had already quietly corrected to
`SYMPHYSIO_*`. 0.3.0 reads the correct spelling and **only** that one, and
refuses to start if the old one is still in the environment:

```
ValueError: SYPHYSIO_DATA_DIR uses the pre-0.3.0 spelling and is now ignored.
Rename it to SYMPHYSIO_DATA_DIR before starting: an unset SYMPHYSIO_DATA_DIR
would open a new empty database, an unset SYMPHYSIO_TRUSTED_PROXIES would give
every visitor one rate-limit budget, and an unset SYMPHYSIO_ALLOW_REGISTRATION
would open sign-up.
```

That error is the whole design. Silently ignoring a renamed variable is how a
deploy ends up with a fresh empty database where the diary used to be, so the
choice was to make it impossible to start with the old names rather than to
translate them for a release or two. **Deploying 0.3.0 means editing the
`environment:` block in the same change that moves the image**, and nothing else:
the database, the cookies and the API are unaffected.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SYMPHYSIO_DATA_DIR` | `./data` | where the SQLite file lives; in the image, `/data` |
| `SYMPHYSIO_DB_PATH` | `$DATA_DIR/symphysio.sqlite` | explicit database path |
| `SYMPHYSIO_STATIC_DIR` | `../frontend/dist` | compiled SPA; the image bakes `/app/static` |
| `SYMPHYSIO_MIGRATIONS_DIR` | `./migrations` | forward-only `.sql` files |
| `SYMPHYSIO_COOKIE_SECURE` | `1` | `Secure` on both cookies; set `0` only for plain-HTTP dev on a non-localhost origin |
| `SYMPHYSIO_SESSION_TTL_DAYS` | `30` | session lifetime (rolled forward at half-life) |
| `SYMPHYSIO_MAX_BODY_BYTES` | `262144` | request body cap, enforced before parsing |
| `SYMPHYSIO_TRUSTED_PROXIES` | *(empty)* | space or comma separated CIDRs of *your* proxy. Empty means the socket peer is the client address (one shared budget behind a proxy); only then is `X-Forwarded-For` read |
| `SYMPHYSIO_ALLOW_REGISTRATION` | `1` | `0` closes sign-up — `POST /auth/register` answers `403`. Set it to `0` on anything the internet can see, once your own accounts exist |
| `SYMPHYSIO_RATE_LIMIT` | `1` | `0` disables auth rate limiting (dev only) |
| `SYMPHYSIO_RATE_LIMIT_ATTEMPTS` | `10` | attempts per window, per IP and per email |
| `SYMPHYSIO_RATE_LIMIT_WINDOW` | `900` | sliding window, seconds |
| `SYMPHYSIO_RATE_LIMIT_LOCKOUT` | `900` | lockout after the window fills, seconds |
| `RESEND_API_KEY` | unset | Resend key; with a sender and a public URL, email switches on |
| `SYMPHYSIO_EMAIL_FROM` | unset | `From:` on confirmation mail, e.g. `Symphysio <confirm@mail.example.org>` |
| `SYMPHYSIO_EMAIL_REPLY_TO` | unset | optional `Reply-To:` |
| `SYMPHYSIO_PUBLIC_URL` | unset | absolute origin used **only** for the link host, e.g. `https://symphysio.example.org` |
| `SYMPHYSIO_MAIL_BACKEND` | `resend` if configured, else `null` | `resend`, `outbox` (write `.eml` files to the data dir, never send) or `null` |
| `SYMPHYSIO_EMAIL_TTL_SECONDS` | `86400` | how long a confirmation link works (floor 300) |
| `SYMPHYSIO_EMAIL_SENDS_PER_HOUR` | `3` | per-account send budget, counted in the database |
| `SYMPHYSIO_EMAIL_CONFIRMATION` | `optional` | `off` = no confirmation mail at all; `optional` = link + banner, never blocks; `required` = sign-in blocked until clicked (refuses to start with no mail transport) |
| `SYMPHYSIO_DEFAULT_TIMEZONE` | `UTC` | IANA zone for accounts that never chose one in Settings — set it to where your users are (`America/Toronto`). It never overrides an account that did choose, and it never re-derives stored rows. A name `zoneinfo` cannot resolve stops the container at startup rather than quietly meaning UTC |

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
4. Set `SYMPHYSIO_EMAIL_FROM` to an address on that domain and
   `SYMPHYSIO_PUBLIC_URL` to the origin your phone actually reaches. The link host
   comes from this variable, never from the request's `Host` header, so a reverse
   proxy in front does not change what lands in the mail.
5. Choose `SYMPHYSIO_EMAIL_CONFIRMATION`. `optional` (the default) sends the link
   and shows a reminder but never locks anyone out — a postnatal user whose mail
   went to spam should not be shut out of their own diary. `off` skips the whole
   business if you would rather not run outbound mail for this app at all, and
   `required` is there if you want the hard gate.

Developing without sending anything:

```bash
SYMPHYSIO_MAIL_BACKEND=outbox \
SYMPHYSIO_PUBLIC_URL=https://symphysio.test \
RESEND_API_KEY=dev_never_real \
SYMPHYSIO_EMAIL_FROM='Symphysio <confirm@example.org>' \
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
SYMPHYSIO_DATA_DIR=/var/lib/symphysio uv run uvicorn app.main:app --port 8090
```

Build the SPA first (`cd frontend && npm ci && npm run build`), or point
`SYMPHYSIO_STATIC_DIR` at a checkout of `frontend/dist`. Under systemd, run as a
dedicated user and give it only the data directory:

```ini
[Service]
User=symphysio
Group=symphysio
Environment=SYMPHYSIO_DATA_DIR=/var/lib/symphysio
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

Then in a phone browser: register (pick a tracking profile) → log two exercises
with a `-1h` chip → Undo one → check Insights shows the "what follows a session?"
card, the daily bars and the adherence line, and that History shows the plan
event you added.

## PWA notes

- `/manifest.webmanifest` and `/sw.js` must be served from the origin root —
  they are, by the app itself, not by the proxy.
- The service worker caches only the app shell. API responses are never cached:
  a stale number in a health diary is worse than an error message.
- `npm run build` regenerates hashed asset names, so an app update rolls out on
  the next visit instead of sticking in the cache.
