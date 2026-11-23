"""Quick logging, retroactive timestamps, the unified timeline and Undo."""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient

from .conftest import catalog_ids, csrf_headers, register

NOW = int(time.time())


def _h(client: TestClient) -> dict[str, str]:
    return csrf_headers(client)


def _first(client: TestClient, kind: str) -> dict[str, Any]:
    return catalog_ids(client, kind)[0]


def test_exercise_log_uses_definition_defaults(client: TestClient) -> None:
    register(client)
    exercise = _first(client, "exercises")  # Pelvic Floor Lifts: 3 sets x 10 reps
    response = client.post(
        "/api/v1/logs/exercises",
        json={"exercise_id": exercise["id"], "tz_offset_min": -300},
        headers=_h(client),
    )
    assert response.status_code == 201
    created = response.json()
    assert created["event_type"] == "exercise"
    item = client.get("/api/v1/timeline").json()["items"][0]
    assert item["definition_name"] == exercise["name"]
    assert item["sets_done"] == 3 and item["reps_done"] == 10
    assert item["tz_offset_min"] == -300
    assert abs(item["occurred_at_utc"] - NOW) < 120


def test_symptom_log_requires_severity_1_to_10(client: TestClient) -> None:
    register(client)
    symptom = _first(client, "symptoms")
    missing = client.post(
        "/api/v1/logs/symptoms", json={"symptom_id": symptom["id"]}, headers=_h(client)
    )
    assert missing.status_code == 422
    for bad in (0, 11):
        response = client.post(
            "/api/v1/logs/symptoms",
            json={"symptom_id": symptom["id"], "severity": bad},
            headers=_h(client),
        )
        assert response.status_code == 422
    ok = client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": symptom["id"], "severity": 7, "body_region": "neck"},
        headers=_h(client),
    )
    assert ok.status_code == 201


def test_retroactive_timestamps_are_honoured(client: TestClient) -> None:
    register(client)
    context = catalog_ids(client, "contexts")[0]
    three_hours_ago = NOW - 3 * 3600
    created = client.post(
        "/api/v1/logs/contexts",
        json={"context_id": context["id"], "occurred_at_utc": three_hours_ago},
        headers=_h(client),
    )
    assert created.status_code == 201
    items = client.get("/api/v1/timeline").json()["items"]
    assert items[0]["occurred_at_utc"] == three_hours_ago
    assert items[0]["category"] == "relief"


def test_future_timestamps_are_clamped_to_now(client: TestClient) -> None:
    register(client)
    symptom = _first(client, "symptoms")
    client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": symptom["id"], "severity": 3, "occurred_at_utc": NOW + 7_200},
        headers=_h(client),
    )
    item = client.get("/api/v1/timeline").json()["items"][0]
    assert item["occurred_at_utc"] <= NOW + 5


def test_timeline_filters_and_paging(client: TestClient) -> None:
    register(client)
    exercise = _first(client, "exercises")
    for hours in (0, 2, 4, 26):
        client.post(
            "/api/v1/logs/exercises",
            json={"exercise_id": exercise["id"], "occurred_at_utc": NOW - hours * 3600},
            headers=_h(client),
        )
    page = client.get("/api/v1/timeline", params={"limit": 3}).json()
    assert len(page["items"]) == 3
    assert page["next_before"] is not None
    rest = client.get(
        "/api/v1/timeline", params={"limit": 3, "before": page["next_before"]}
    ).json()
    assert len(rest["items"]) == 1
    assert rest["next_before"] is None
    yesterday = client.get(
        "/api/v1/timeline", params={"from": NOW - 2 * 86_400, "to": NOW - 25 * 3600}
    ).json()
    assert len(yesterday["items"]) == 1
    only_symptoms = client.get("/api/v1/timeline", params={"event_type": "symptom"}).json()
    assert only_symptoms["items"] == []


def test_undo_deletes_and_second_delete_is_404(client: TestClient) -> None:
    register(client)
    symptom = _first(client, "symptoms")
    created = client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": symptom["id"], "severity": 5},
        headers=_h(client),
    ).json()
    log_id = created["id"]
    deleted = client.delete(f"/api/v1/logs/symptom/{log_id}", headers=_h(client))
    assert deleted.status_code == 204
    assert client.get("/api/v1/timeline").json()["items"] == []
    assert client.delete(f"/api/v1/logs/symptom/{log_id}", headers=_h(client)).status_code == 404


def test_edit_a_log_entry(client: TestClient) -> None:
    register(client)
    symptom = _first(client, "symptoms")
    log_id = client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": symptom["id"], "severity": 2, "note": "mild"},
        headers=_h(client),
    ).json()["id"]
    patched = client.patch(
        f"/api/v1/logs/symptom/{log_id}",
        json={"severity": 9, "note": "worse after walk"},
        headers=_h(client),
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["severity"] == 9 and body["note"] == "worse after walk"
    assert client.get("/api/v1/timeline").json()["items"][0]["primary_metric"] == 9


def test_logging_against_unknown_or_archived_definition(client: TestClient) -> None:
    register(client)
    symptom = _first(client, "symptoms")
    unknown = client.post(
        "/api/v1/logs/symptoms", json={"symptom_id": "nope", "severity": 5}, headers=_h(client)
    )
    assert unknown.status_code == 404
    client.patch(
        f"/api/v1/catalog/symptoms/{symptom['id']}",
        json={"is_archived": True},
        headers=_h(client),
    )
    archived = client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": symptom["id"], "severity": 5},
        headers=_h(client),
    )
    assert archived.status_code == 409
