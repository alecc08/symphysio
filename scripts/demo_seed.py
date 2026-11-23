"""Seed a plausible postnatal pelvic-floor diary, for screenshots and for trying it out.

Point it at a throwaway instance and it fills three weeks of data with a shape on
purpose: practice is steady, load events (the car seat, carrying the baby) cluster
on certain days, and "Heaviness / Dragging" tends to arrive 2-5 hours after one of
those — so the lag panel has something real to find and severity trends gently
downward. The README and docs/media screenshots came from exactly this seed.

    SYPHYSIO_DATA_DIR=$(mktemp -d) SYPHYSIO_MAIL_BACKEND=null \
      SYPHYSIO_COOKIE_SECURE=0 uv run uvicorn app.main:app --port 8011
    python3 scripts/demo_seed.py            # then open http://127.0.0.1:8011

Running it twice against the same database doubles the data rather than failing,
which is fine for a demo install.
"""

import os
import random
from datetime import UTC, datetime, timedelta

import httpx

random.seed(7)
BASE = os.environ.get("SYPHYSIO_DEMO_URL", "http://127.0.0.1:8011") + "/api/v1"
# The demo account's credentials. Overridable so the script can point at any
# install; the defaults are invented and are the one value gitleaks is told to
# ignore (see .gitleaks.toml) - they guard a throwaway account full of made-up
# logs, and the screenshots in this repo are built on them.
EMAIL = os.environ.get("SYPHYSIO_DEMO_EMAIL", "demo@symphysio.example")
PASSPHRASE = os.environ.get("SYPHYSIO_DEMO_PASSPHRASE", "sunlit-origami-42")
client = httpx.Client(base_url=BASE, timeout=30)

# Register on a fresh install, log in on one that has been seeded already.
if client.post("/auth/register", json={"email": EMAIL, "password": PASSPHRASE}).status_code == 409:
    client.post("/auth/login", json={"email": EMAIL, "password": PASSPHRASE})
if "symphysio_session" not in client.cookies:
    raise SystemExit(f"could not sign in to {BASE}")
csrf = client.cookies.get("symphysio_csrf", "")

ids = {}
for path in ("/catalog/exercises", "/catalog/symptoms", "/catalog/contexts"):
    for row in client.get(path).json():
        ids[row["name"]] = row["id"]

now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
start = now - timedelta(days=23)


def at(day: int, hour: int, minute: int = 0) -> int:
    return int((start + timedelta(days=day, hours=hour, minutes=minute)).timestamp())


def post(path: str, kind: str, name: str, when: int, **extra) -> None:
    body = {f"{kind}_id": ids[name], "occurred_at_utc": when, "tz_offset_min": -240, **extra}
    response = client.post(path, json=body,
                           headers={"X-CSRF-Token": client.cookies.get("symphysio_csrf", "")})
    assert response.status_code in (200, 201), (name, response.text)


routine = ["Pelvic Floor Lifts", "Diaphragm Breathing", "Deep Core Draw-In",
           "Glute Bridge", "Clamshell", "Bird Dog"]

for day in range(24):
    week = day // 7
    # practice: twice a day most days, a little less variety as it settles in
    for slot, hour in ((0, 8), (1, 20)):
        name = routine[(day * 2 + slot) % min(6, 3 + week)]
        post("/logs/exercises", "exercise", name, at(day, hour),
             sets_done=random.choice([3, 3, 5]), reps_done=random.choice([8, 10, 12]),
             effort_rpe=random.choice([3, 4, 5]), pain_during=random.choice([0, 0, 0, 1]))

    # load events: the everyday stuff that stresses a healing pelvic floor
    post("/logs/contexts", "context", "Carrying Baby", at(day, 10, 20), intensity=random.choice([4, 6, 7]))
    if day % 3 == 1:
        post("/logs/contexts", "context", "Heavy Lifting", at(day, 15, 10),
             intensity=random.choice([6, 7, 8]), note="car seat in and out of the car")
    if day % 4 == 2:
        post("/logs/contexts", "context", "Long Standing", at(day, 17), intensity=5)
    if day % 5 == 3:
        post("/logs/contexts", "context", "Cough or Sneeze", at(day, 21, 30), intensity=4)
    if day % 6 == 0:
        post("/logs/contexts", "context", "Straining", at(day, 7, 40), intensity=5)

    # symptoms, mostly 2-5 h after a load event, easing as the weeks go on
    chance = [0.9, 0.8, 0.6, 0.4][min(week, 3)]
    if random.random() < chance:
        lag = random.randint(2, 5)
        post("/logs/symptoms", "symptom", "Heaviness / Dragging", at(day, 15 + lag // 2, 30),
             severity=random.choice([4, 5, 5, 6]) - week // 2, body_region="low pelvis",
             duration_min=random.choice([30, 60, 120]))
    if day % 4 == 1 and week < 3:
        post("/logs/symptoms", "symptom", "Urine Leak", at(day, 11, 15),
             severity=random.choice([3, 4]), duration_min=5, note="sneezed")
    if day % 7 in (2, 5) and week < 2:
        post("/logs/symptoms", "symptom", "Low Back Pain", at(day, 19, 45),
             severity=random.choice([4, 5]), body_region="lower back", duration_min=180)
    if day < 6:
        post("/logs/symptoms", "symptom", "Perineal Pain", at(day, 13),
             severity=random.choice([5, 6]), duration_min=90)

    # what actually helps
    if day % 2 == 0:
        post("/logs/contexts", "context", "Heat Pack", at(day, 21, 15), intensity=3)
    if day % 3 == 0:
        post("/logs/contexts", "context", "Rest", at(day, 14), intensity=4)
    if day % 7 == 4:
        post("/logs/contexts", "context", "Pelvic Floor PT", at(day, 16), intensity=5,
             note="checked the draw-in, told to stop holding my breath")
    if day % 5 == 2:
        post("/logs/contexts", "context", "Belly Support", at(day, 9, 30), intensity=4)

for path in ("/catalog/exercises", "/catalog/symptoms", "/catalog/contexts"):
    kind = path.split("/")[-1]
    print(f"{kind}: {len(client.get(path).json())} presets")
print("daily rows:", len(client.get("/analytics/summary", params={"days": 30}).json().get("daily", [])))
print(f"sign in at {BASE.rsplit('/api', 1)[0]} with {EMAIL} / {PASSPHRASE}")
