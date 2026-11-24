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
    assert len(body["daily"]) >= 4
    assert body["daily"][-1]["exercises"] == 1
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


def test_lag_correlations_find_the_pattern(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    body = client.get(
        "/api/v1/analytics/lag-correlations",
        params={"min_hr": 1, "max_hr": 6, "min_count": 3},
    ).json()
    assert body["pairs"], "expected one exercise->symptom pair"
    pair = body["pairs"][0]
    assert pair["exercise_name"] == "Pelvic Floor Lifts"
    assert pair["post_exercise_occurrences"] == 4
    assert pair["avg_lag_hours"] == 2.5
    assert pair["min_lag_hours"] == 2.5 and pair["max_lag_hours"] == 2.5
    assert pair["avg_severity"] == 6.0
    assert pair["share_of_symptom_logs"] == 1.0


def test_lag_correlations_respect_the_window(client: TestClient) -> None:
    register(client)
    _seed_lag_pattern(client)
    body = client.get(
        "/api/v1/analytics/lag-correlations",
        params={"min_hr": 6, "max_hr": 24, "min_count": 1},
    ).json()
    assert body["pairs"] == []


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
