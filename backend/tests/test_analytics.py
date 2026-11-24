"""Analytics: daily summary, lag correlations, hour-of-day, and exports."""

from __future__ import annotations

import time

import pytest
from app.routers import analytics
from fastapi.testclient import TestClient

from .conftest import catalog_ids, csrf_headers, register

NOW = int(time.time())
DAY = 86_400
# 2026-11-24 00:50 UTC, which is 2026-11-23 19:50 for a user at UTC-5: the two
# calendars name a different "today". The app is asked about streaks in the user's
# frame, so this is the moment the arithmetic used to get wrong.
EST_EVENING = 1_795_481_400
WEST_OF_UTC = -300


def _h(client: TestClient) -> dict[str, str]:
    return csrf_headers(client)


def _seed_lag_pattern(client: TestClient) -> None:
    """4 chin-tuck sessions, each followed 2.5 h later by neck stiffness."""
    exercise = catalog_ids(client, "exercises")[0]
    symptom = catalog_ids(client, "symptoms")[0]
    for day in range(4):
        # +60s keeps each entry strictly inside an N-day window regardless of the
        # few seconds between module import and the request.
        base = NOW - (day + 1) * DAY + 60
        client.post(
            "/api/v1/logs/exercises",
            json={
                "exercise_id": exercise["id"],
                "occurred_at_utc": base,
                "effort_rpe": 4,
                "tz_offset_min": -300,
            },
            headers=_h(client),
        )
        client.post(
            "/api/v1/logs/symptoms",
            json={
                "symptom_id": symptom["id"],
                "severity": 6,
                "occurred_at_utc": base + int(2.5 * 3600),
                "tz_offset_min": -300,
            },
            headers=_h(client),
        )


def test_summary_counts_and_streak(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    body = client.get("/api/v1/analytics/summary", params={"days": 30}).json()
    assert body["totals"]["exercises"] == 4
    assert body["totals"]["symptoms"] == 4
    assert body["totals"]["avg_symptom_severity"] == 6.0
    assert body["top_exercises"][0]["count"] == 4
    assert body["top_exercises"][0]["name"] == "Pelvic Floor Lifts"
    # Gap-filled: one point per day in the window, logged or not, so a chart
    # cannot draw a line across a fortnight of silence.
    assert len(body["daily"]) == 31
    assert body["daily"][-1]["logged"] is False, "today: nothing logged yet"
    assert body["daily"][-2]["exercises"] == 1
    assert sum(1 for day in body["daily"] if day["logged"]) == 4
    assert body["adherence"]["days_with_exercise"] == 4
    assert body["exercise_streak_days"] >= 3


def _log_evenings(client: TestClient, days_ago: list[int], offset_min: int) -> None:
    """One exercise entry on each of the given days back, at the same clock time."""
    exercise = catalog_ids(client, "exercises")[0]
    for day in days_ago:
        client.post(
            "/api/v1/logs/exercises",
            json={
                "exercise_id": exercise["id"],
                "occurred_at_utc": EST_EVENING - day * DAY + 60,
                "effort_rpe": 4,
                "tz_offset_min": offset_min,
            },
            headers=_h(client),
        )


def test_a_streak_counts_when_utc_is_already_a_day_ahead(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Four evenings in a row is a streak of four, whatever UTC calls today.

    The day buckets are cut in the user's frame (`occurred_at_utc +
    tz_offset_min * 60`), so "did they log today or yesterday?" has to be asked in
    that same frame. Asked against UTC it answers 0 for anyone west of UTC for the
    hours each evening that the two calendars disagree - which is when people
    actually log, and the same test then passes the next morning, which is how it
    survived review.
    """
    register(client)
    monkeypatch.setattr(analytics, "now_utc", lambda: EST_EVENING)
    _log_evenings(client, [1, 2, 3, 4], WEST_OF_UTC)
    body = client.get("/api/v1/analytics/summary", params={"days": 30}).json()
    assert body["exercise_streak_days"] == 4


def test_a_real_gap_still_breaks_the_streak(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix is about the frame, not about being generous: three quiet days is 0."""
    register(client)
    monkeypatch.setattr(analytics, "now_utc", lambda: EST_EVENING)
    _log_evenings(client, [3, 4, 5], WEST_OF_UTC)
    body = client.get("/api/v1/analytics/summary", params={"days": 30}).json()
    assert body["exercise_streak_days"] == 0


def test_summary_is_scoped_to_the_window(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    assert client.get("/api/v1/analytics/summary", params={"days": 1}).json()["totals"][
        "exercises"
    ] == 1


def test_the_lag_endpoint_is_gone(client: TestClient) -> None:
    """It printed a count as a finding. Nothing may call it again by accident."""
    register(client)
    assert client.get("/api/v1/analytics/lag-correlations").status_code == 404


def test_associations_answer_the_question_in_words(client: TestClient) -> None:
    """4 sessions, 4 follow-ons: not enough to say anything, and it says so.

    `MIN_SESSIONS`/`MIN_HITS` gate a pair at 5 sessions and 3 hits, so this
    diary — the size of a first week — must come back with no findings and the
    sufficiency state, not with a confident bar.
    """
    register(client)
    _seed_lag_pattern(client)
    body = client.get("/api/v1/analytics/associations", params={"days": 30}).json()
    assert body["findings"] == []
    assert body["sufficiency"] in {"thin", "none"}
    # Not even examined: 4 logs is below the 5-log candidate bar, which is the
    # multiplicity control (docs/INSIGHTS_PLAN.md §2.3), not a courtesy.
    assert body["pairs_examined"] == 0
    assert body["windows"], "the profile supplies the windows"


def test_a_real_pattern_reaches_the_client_through_the_endpoint(client: TestClient) -> None:
    """The end-to-end proof: enough diary, one real lag, and it is named.

    10 sessions every other day; heaviness follows on 7 of them, 3 h later; 10
    background heaviness logs in the evenings, on days with no session, so the
    matched baseline has something honest to compare against.
    """
    register(client)
    exercise = catalog_ids(client, "exercises")[0]
    symptom = catalog_ids(client, "symptoms")[0]
    for day in range(1, 21):
        at = NOW - day * DAY + 9 * 3600
        if day % 2:
            client.post(
                "/api/v1/logs/exercises",
                json={
                    "exercise_id": exercise["id"],
                    "occurred_at_utc": at,
                    "effort_rpe": 5,
                    "tz_offset_min": 0,
                },
                headers=_h(client),
            )
            if day <= 14:
                client.post(
                    "/api/v1/logs/symptoms",
                    json={
                        "symptom_id": symptom["id"],
                        "severity": 7,
                        "occurred_at_utc": at + 3 * 3600,
                        "tz_offset_min": 0,
                    },
                    headers=_h(client),
                )
        else:
            client.post(
                "/api/v1/logs/symptoms",
                json={
                    "symptom_id": symptom["id"],
                    "severity": 4,
                    "occurred_at_utc": at + 11 * 3600,
                    "tz_offset_min": 0,
                },
                headers=_h(client),
            )
    body = client.get("/api/v1/analytics/associations", params={"days": 30}).json()
    assert body["sufficiency"] == "enough", body["coverage"]
    assert body["pairs_examined"] == 1
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["exposure_name"] == "Pelvic Floor Lifts"
    assert finding["symptom_name"] == "Heaviness / Dragging"
    assert finding["sessions"] == 10 and finding["hits"] == 7
    assert finding["control_windows"] > 0
    assert finding["verdict"] == "worth a look"
    # Printed as counts and one fixed word — no interval, no p-value, no advice.
    # The background logs are all in the evening, so no control window (10:00-15:00
    # on a session-free day) catches one: the baseline rate is exactly zero, and a
    # ratio against zero is not printed at all. The card says "7 of 10, against 0
    # of N comparable days", which is the honest version.
    assert finding["control_hits"] == 0
    assert finding["relative_risk"] is None
    assert finding["control_windows"] > 5


def test_associations_offer_only_the_profiles_windows(client: TestClient) -> None:
    register(client)
    body = client.get("/api/v1/analytics/associations", params={"days": 30}).json()
    labels = [item["label"] for item in body["windows"]]
    assert body["window"]["label"] in labels
    invented = client.get(
        "/api/v1/analytics/associations", params={"days": 30, "window": "2-7 h"}
    )
    assert invented.status_code == 422, "free-form windows are how you fish for a pattern"
    assert "0-2 h" in labels and "6-48 h" in labels


def test_associations_start_empty_gets_no_windows_and_no_nothing(client: TestClient) -> None:
    register(client)
    # `none` still has windows (there is no profile to inherit), and with no logs
    # the honest answer is the empty one.
    body = client.get("/api/v1/analytics/associations", params={"days": 30}).json()
    assert body["findings"] == [] and body["pairs_examined"] == 0
    assert body["coverage"]["state"] == "none"


def test_time_of_day_buckets_by_local_hour(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    body = client.get("/api/v1/analytics/time-of-day", params={"days": 30}).json()
    assert len(body["hours"]) == 24
    assert sum(hour["count"] for hour in body["hours"]) == 4


def test_csv_export(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    response = client.get("/api/v1/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment;" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert len(lines) == 9  # header + 8 events
    header = lines[0].split(",")
    assert header[:4] == ["event_type", "id", "definition", "definition_id"]
    assert "Pelvic Floor Lifts" in response.text


def test_json_export_includes_definitions_and_logs(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    body = client.get("/api/v1/export/json").json()
    assert body["app"] == "symphysio"
    assert len(body["logs"]["exercises"]) == 4
    assert len(body["definitions"]["exercises"]) == 10
    assert len(body["timeline"]) == 8


def test_exports_require_authentication(client: TestClient) -> None:
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert client.get("/api/v1/export/csv").status_code == 401
    assert client.get("/api/v1/export/json").status_code == 401
