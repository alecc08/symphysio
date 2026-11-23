"""Catalog CRUD: seeding, archiving instead of deleting, ordering, conflicts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import catalog_ids, csrf_headers, register


def _h(client: TestClient) -> dict[str, str]:
    return csrf_headers(client)


def test_defaults_are_seeded_per_kind(client: TestClient) -> None:
    register(client)
    assert len(catalog_ids(client, "exercises")) == 10
    assert len(catalog_ids(client, "symptoms")) == 10
    contexts = catalog_ids(client, "contexts")
    assert len(contexts) == 16
    assert {item["category"] for item in contexts} == {"relief", "trigger"}
    relief = client.get("/api/v1/catalog/contexts", params={"category": "relief"}).json()
    assert len(relief) == 8
    assert all(item["is_archived"] is False for item in relief)


def test_create_update_and_archive(client: TestClient) -> None:
    register(client)
    created = client.post(
        "/api/v1/catalog/exercises",
        json={"name": "Deep Neck Flexion", "body_region": "neck", "default_reps": 8},
        headers=_h(client),
    )
    assert created.status_code == 201
    definition_id = created.json()["id"]
    assert created.json()["sort_order"] == 10

    patched = client.patch(
        f"/api/v1/catalog/exercises/{definition_id}",
        json={"default_reps": 12, "body_region": "upper_back"},
        headers=_h(client),
    )
    assert patched.status_code == 200
    assert patched.json()["default_reps"] == 12
    assert patched.json()["body_region"] == "upper_back"

    archived = client.patch(
        f"/api/v1/catalog/exercises/{definition_id}",
        json={"is_archived": True},
        headers=_h(client),
    )
    assert archived.status_code == 200 and archived.json()["is_archived"] is True
    visible = client.get("/api/v1/catalog/exercises").json()
    assert definition_id not in {item["id"] for item in visible}
    with_archived = client.get(
        "/api/v1/catalog/exercises", params={"include_archived": True}
    ).json()
    assert definition_id in {item["id"] for item in with_archived}


def test_duplicate_names_conflict_case_insensitively(client: TestClient) -> None:
    register(client)
    first = client.post("/api/v1/catalog/symptoms", json={"name": "Zap Pain"}, headers=_h(client))
    assert first.status_code == 201
    second = client.post("/api/v1/catalog/symptoms", json={"name": "zap pain"}, headers=_h(client))
    assert second.status_code == 409


def test_cannot_touch_another_users_catalog(client: TestClient) -> None:
    register(client)
    definition_id = catalog_ids(client)[0]["id"]
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    register(client, email="other@example.com")
    other_ids = {item["id"] for item in catalog_ids(client)}
    assert definition_id not in other_ids
    stolen = client.patch(
        f"/api/v1/catalog/exercises/{definition_id}",
        json={"name": "Hijacked"},
        headers=_h(client),
    )
    assert stolen.status_code == 404


def test_reorder_persists(client: TestClient) -> None:
    register(client)
    items = catalog_ids(client, "symptoms")
    order = [item["id"] for item in items][::-1]
    result = client.post(
        "/api/v1/catalog/symptoms/reorder", json={"ids": order}, headers=_h(client)
    )
    assert result.status_code == 200
    assert result.json()["updated"] == len(order)
    assert [item["id"] for item in catalog_ids(client, "symptoms")] == order


def test_suggestions_exclude_what_you_already_have(client: TestClient) -> None:
    register(client)
    suggestions = client.get("/api/v1/catalog/symptoms/suggestions").json()
    seeded = {item["name"] for item in catalog_ids(client, "symptoms")}
    names = {item["name"] for item in suggestions}
    assert "Postpartum Bleeding" in names
    assert not (seeded & names), "suggestions must not repeat existing presets"

    created = client.post(
        "/api/v1/catalog/symptoms",
        json={"name": "Postpartum Bleeding", "default_region": "lower_belly"},
        headers=_h(client),
    )
    assert created.status_code == 201
    after = {item["name"] for item in client.get("/api/v1/catalog/symptoms/suggestions").json()}
    assert "Postpartum Bleeding" not in after


def test_suggestions_for_each_kind(client: TestClient) -> None:
    register(client)
    exercises = client.get("/api/v1/catalog/exercises/suggestions").json()
    contexts = client.get("/api/v1/catalog/contexts/suggestions").json()
    assert exercises and all("default_sets" in item for item in exercises)
    assert {"relief", "trigger"} <= {item["category"] for item in contexts}
    assert client.get("/api/v1/catalog/unknown/suggestions").status_code == 404


def test_suggestions_post_back_unchanged(client: TestClient) -> None:
    """The suggestion payload is a create payload: models are extra='forbid'."""
    register(client)
    for kind in ("exercises", "symptoms", "contexts"):
        suggestion = client.get(f"/api/v1/catalog/{kind}/suggestions").json()[0]
        created = client.post(f"/api/v1/catalog/{kind}", json=suggestion, headers=_h(client))
        assert created.status_code == 201, (kind, created.text)
