#!/usr/bin/env python3
"""Preflight a deployment: prove the two things docs claim about the running image.

1. **Two accounts cannot see each other.** Rows are addressed by UUID and every
   query is filtered by `user_id`, which is easy to write and easy to get wrong in
   one handler, so it is checked over HTTP against the image you are about to run,
   not against the source you read.
2. **The login limiter keys on an address the caller does not control** — the
   socket peer, unless that peer is inside `SYMPHYSIO_TRUSTED_PROXIES`.

Run it twice against the same container, from two source addresses, so both sides
of the rule are measured:

    # the container is on two networks: a plain one, and an "edge" one whose
    # gateway sits inside SYMPHYSIO_TRUSTED_PROXIES
    docker network create --subnet 172.20.0.0/24 edge
    docker run -d --name preflight --network bridge \
      --read-only --tmpfs /tmp:rw,size=64m,mode=1777 \
      --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges \
      -v preflight-data:/data \
      -e SYMPHYSIO_COOKIE_SECURE=0 -e SYMPHYSIO_TRUSTED_PROXIES=172.20.0.0/24 \
      -e SYMPHYSIO_RATE_LIMIT_ATTEMPTS=2 <image>
    docker network connect edge preflight
    python3 scripts/preflight.py http://<bridge-ip>:8000 untrusted
    python3 scripts/preflight.py http://<edge-ip>:8000     trusted

It writes: registers two throwaway accounts, and burns the login budget with
rotating `X-Forwarded-For`. Point it at a throwaway instance, never at someone's
live data — the accounts and the failures are real. Exit code is non-zero if any
check fails. Measured against `ghcr.io/alecc08/symphysio@sha256:b686dea4…` (0.1.2):
all checks pass in both modes; on 0.1.1 the `untrusted` run reported
`[401, 401, 401]` instead of a lockout, which is the hole 0.1.2 closes.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1].rstrip("/")
MODE = sys.argv[2] if len(sys.argv) > 2 else "untrusted"
API = BASE + "/api/v1"
NOW = int(time.time())
TS = f"{NOW}{time.time_ns() % 1000:03d}"
FAILURES = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got!r} want {want!r}")


class Client:
    def __init__(self):
        self.cj = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            API + path, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        for name, value in (headers or {}).items():
            req.add_header(name, value)
        csrf = next((c.value for c in self.cj if c.name == "symphysio_csrf"), None)
        if csrf and method != "GET" and not any(k.lower() == "x-csrf-token" for k in (headers or {})):
            req.add_header("X-CSRF-Token", csrf)
        try:
            with self.opener.open(req, timeout=15) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw.decode(errors="replace")[:200]


def text_of(payload):
    return json.dumps(payload) if not isinstance(payload, str) else payload


def isolation():
    a, b = Client(), Client()
    sa, _ = a.call("POST", "/auth/register", {"email": f"a{TS}@example.com", "password": PASS})
    sb, _ = b.call("POST", "/auth/register", {"email": f"b{TS}@example.com", "password": PASS})
    check("A registered", sa, 201)
    check("B registered", sb, 201)

    defs = a.call("GET", "/catalog/exercises")[1] or []
    ex = defs[0]["id"] if defs else "none"
    bdefs = b.call("GET", "/catalog/exercises")[1] or []
    bex = bdefs[0]["id"] if bdefs else "none"
    sym = (a.call("GET", "/catalog/symptoms")[1] or [{}])[0].get("id", "none")
    _, log = a.call("POST", "/logs/exercises", {"exercise_id": ex, "occurred_at_utc": NOW, "tz_offset_min": -300, "effort_rpe": 4})
    _, slog = a.call(
        "POST",
        "/logs/symptoms",
        {"symptom_id": sym, "severity": 5, "occurred_at_utc": NOW, "tz_offset_min": -300, "note": SECRET},
    )
    log_id, slog_id, def_id = log["id"], slog["id"], defs[1]["id"] if len(defs) > 1 else ex

    check("B timeline is empty", len((b.call("GET", "/timeline")[1] or {}).get("items", [])), 0)
    check("B cannot patch A's exercise", b.call("PATCH", f"/logs/exercise/{log_id}", {"note": "hacked"})[0], 404)
    check("B cannot delete A's symptom", b.call("DELETE", f"/logs/symptom/{slog_id}")[0], 404)
    check("B cannot edit A's definition", b.call("PATCH", f"/catalog/exercises/{def_id}", {"name": "stolen"})[0], 404)
    check("B cannot log against A's definition", b.call("POST", "/logs/exercises", {"exercise_id": ex, "occurred_at_utc": NOW, "tz_offset_min": 0})[0], 404)
    check("B's export has no secret", SECRET in text_of(b.call("GET", "/export/json")[1]), False)
    check("A's export has the secret", SECRET in text_of(a.call("GET", "/export/json")[1]), True)
    check("B analytics sees nothing", (b.call("GET", "/analytics/summary?days=30")[1] or {}).get("totals", {}).get("exercises"), 0)
    check("A still sees its own row", len((a.call("GET", "/timeline")[1] or {}).get("items", [])), 2)
    check("bad CSRF token is refused", b.call("POST", "/logs/exercises", {"exercise_id": bex, "occurred_at_utc": NOW, "tz_offset_min": 0}, {"X-CSRF-Token": "wrong"})[0], 403)


def limiter():
    c = Client()
    if MODE == "untrusted":
        codes = [c.call("POST", "/auth/login", {"email": f"guess{n}@example.com", "password": "nope-nope-nope"}, {"X-Forwarded-For": f"9.9.9.{n}"})[0] for n in range(1, 4)]
        check("rotating XFF cannot escape the lockout", codes[-1], 429)
    else:
        c1 = Client()
        one = [c1.call("POST", "/auth/login", {"email": f"v1a{n}@example.com", "password": "nope-nope-nope"}, {"X-Forwarded-For": "198.51.100.7"})[0] for n in range(1, 4)]
        check("visitor 1 burns its own budget", one, [401, 401, 429])
        check("visitor 2 is untouched", c1.call("POST", "/auth/login", {"email": "v2a@example.com", "password": "nope-nope-nope"}, {"X-Forwarded-For": "203.0.113.5"})[0], 401)


PASS = f"correct-horse-battery-{TS}"
SECRET = f"private-note-{TS}"
isolation()
limiter()
print("MODE", MODE, "FAILURES", FAILURES or "none")
sys.exit(1 if FAILURES else 0)
