"""Plan events: the appointment/programme-change layer, and what it must not do.

The important negative is the last test: a plan event must not appear in the
unified timeline, because every analytics number is built from that view and a
fourth event type would change them without anyone deciding to.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import csrf_headers, register

BASE = "/api/v1/plan-events"


def _post(client: TestClient, **body: object) -> dict:
    response = client.post(BASE, json=body, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_it_needs_no_definition_and_seeds_nothing(client: TestClient) -> None:
    """A note about an appointment is not a preset; the catalogue is untouched."""
    register(client)
    before = client.get("/api/v1/catalog/exercises").json()
    event = _post(client, kind="appointment", text="Second physio review")
    assert event["kind"] == "appointment"
    assert event["text"] == "Second physio review"
    assert event["occurred_at_utc"] > 0
    assert client.get("/api/v1/catalog/exercises").json() == before


def test_the_five_kinds_are_the_whole_vocabulary(client: TestClient) -> None:
    register(client)
    for kind in ("appointment", "programme_change", "medication", "goal", "note"):
        assert _post(client, kind=kind, text=f"a {kind}")["kind"] == kind
    assert (
        client.post(
            BASE, json={"kind": "diagnosis", "text": "no"}, headers=csrf_headers(client)
        ).status_code
        == 422
    )


def test_text_is_required_and_trimmed(client: TestClient) -> None:
    register(client)
    blank = client.post(BASE, json={"text": "   "}, headers=csrf_headers(client))
    assert blank.status_code == 422, "an empty marker on a chart is noise, not a note"
    assert _post(client, text="  padded  ")["text"] == "padded"


def test_a_backdated_event_keeps_its_date(client: TestClient) -> None:
    register(client)
    moment = 1_700_000_000
    event = _post(client, kind="appointment", text="first review", occurred_at_utc=moment)
    assert event["occurred_at_utc"] == moment
    assert event["logged_at_utc"] > moment, "when it was written stays separate"


def test_the_window_filter_and_ordering(client: TestClient) -> None:
    register(client)
    _post(client, text="old", occurred_at_utc=1_600_000_000)
    _post(client, text="new", occurred_at_utc=1_700_000_000)
    everything = client.get(BASE).json()
    assert [item["text"] for item in everything] == ["new", "old"]
    recent = client.get(BASE, params={"from": 1_650_000_000}).json()
    assert [item["text"] for item in recent] == ["new"]


def test_edit_and_delete(client: TestClient) -> None:
    register(client)
    event = _post(client, kind="note", text="wrote the wrong date")
    patched = client.patch(
        f"{BASE}/{event['id']}",
        json={"kind": "programme_change", "text": "new home programme"},
        headers=csrf_headers(client),
    )
    assert patched.status_code == 200
    assert patched.json()["kind"] == "programme_change"
    assert client.delete(f"{BASE}/{event['id']}", headers=csrf_headers(client)).status_code == 204
    assert client.get(BASE).json() == []
    missing = client.patch(
        f"{BASE}/nope", json={"text": "x"}, headers=csrf_headers(client)
    )
    assert missing.status_code == 404


def test_another_account_cannot_touch_it(client: TestClient) -> None:
    register(client, email="one@example.com")
    event = _post(client, text="mine")
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    register(client, email="two@example.com")
    assert client.get(BASE).json() == []
    assert client.delete(f"{BASE}/{event['id']}", headers=csrf_headers(client)).status_code == 404
    assert client.get(BASE).json() == []


def test_plan_events_are_not_in_the_unified_timeline(client: TestClient) -> None:
    """The analytics view is three log types. Adding a fourth would silently move
    every count, so History merges the feeds in the client instead."""
    register(client)
    _post(client, kind="appointment", text="review")
    timeline = client.get("/api/v1/timeline").json()["items"]
    assert timeline == [], "plan events must not leak into the log feed"
    summary = client.get("/api/v1/analytics/summary").json()["totals"]
    assert summary["exercises"] == 0 and summary["symptoms"] == 0
