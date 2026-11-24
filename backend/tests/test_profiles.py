"""Tracking profiles: what sign-up seeds, what it must never do to history.

Three things are asserted here, in rough order of how much they cost to get
wrong: seeding is *non-destructive* (a profile never deletes or archives
anything), the API default keeps old clients working byte for byte, and the
picker's data comes from the server so the SPA cannot drift from it.
"""

from __future__ import annotations

from app.profiles import DEFAULT_PROFILE, PROFILES
from fastapi.testclient import TestClient

from .conftest import EMAIL, PASSWORD, catalog_ids, csrf_headers


def _post(client: TestClient, email: str, profile: str | None) -> int:
    body: dict[str, str] = {"email": email, "password": PASSWORD}
    if profile is not None:
        body["profile"] = profile
    return client.post("/api/v1/auth/register", json=body).status_code


def test_an_omitted_profile_seeds_the_postnatal_set(client: TestClient) -> None:
    """Byte-for-byte the old behaviour: a client predating this field is fine."""
    assert _post(client, EMAIL, None) == 201
    assert len(catalog_ids(client, "exercises")) == 10
    assert len(catalog_ids(client, "symptoms")) == 10
    assert len(catalog_ids(client, "contexts")) == 16
    assert client.get("/api/v1/auth/me").json()["user"]["profile_key"] == DEFAULT_PROFILE


def test_starting_empty_seeds_nothing(client: TestClient) -> None:
    assert _post(client, EMAIL, "none") == 201
    for kind in ("exercises", "symptoms", "contexts"):
        assert catalog_ids(client, kind) == []
    assert client.get("/api/v1/auth/me").json()["user"]["profile_key"] == "none"


def test_each_named_profile_seeds_its_own_set(client: TestClient) -> None:
    for key, profile in PROFILES.items():
        if key in (DEFAULT_PROFILE, "none"):
            continue
        email = f"{key}@example.com"
        assert _post(client, email, key) == 201, key
        assert len(catalog_ids(client, "exercises")) == len(profile.exercises), key
        assert len(catalog_ids(client, "symptoms")) == len(profile.symptoms), key
        assert len(catalog_ids(client, "contexts")) == len(profile.contexts), key
        client.post("/api/v1/auth/logout", headers=csrf_headers(client))


def test_an_unknown_profile_is_rejected_not_silently_swallowed(client: TestClient) -> None:
    """A typo must not quietly become "start empty" — the diary would look broken."""
    assert _post(client, EMAIL, "pelvic") == 422
    assert _post(client, EMAIL, "POSTNATAL_PELVIC") == 201  # case is forgiving


def test_the_picker_is_public_and_covers_every_profile(client: TestClient) -> None:
    """The sign-up card has no session yet, so this endpoint cannot require one."""
    response = client.get("/api/v1/catalog/profiles")
    assert response.status_code == 200
    body = response.json()
    assert [item["key"] for item in body] == list(PROFILES)
    assert body[0]["key"] == "none", "the picker starts on Start empty"
    for item in body:
        assert item["label"] and item["blurb"]
        assert set(item["counts"]) == {"exercises", "symptoms", "relief", "triggers"}
        assert item["default_window"] in [window["label"] for window in item["windows"]]


def test_seeded_definitions_record_their_origin(client: TestClient) -> None:
    """`profile_key` answers "why is there a Clamshell in this diary" and nothing
    else — no behaviour may key off it."""
    _post(client, EMAIL, "hip_knee")
    rows = catalog_ids(client, "exercises")
    assert {row["profile_key"] for row in rows} == {"hip_knee"}
    added = client.post(
        "/api/v1/catalog/exercises", json={"name": "My own thing"}, headers=csrf_headers(client)
    )
    assert added.status_code == 201
    assert added.json()["profile_key"] is None


def test_archiving_a_preset_still_works_after_a_profile(client: TestClient) -> None:
    """The non-destructive rule: profiles add rows, they never take them away."""
    _post(client, EMAIL, "bladder_bowel")
    first = catalog_ids(client, "symptoms")[0]
    patched = client.patch(
        f"/api/v1/catalog/symptoms/{first['id']}",
        json={"is_archived": True},
        headers=csrf_headers(client),
    )
    assert patched.status_code == 200
    assert patched.json()["is_archived"] is True
    assert len(catalog_ids(client, "symptoms")) == len(PROFILES["bladder_bowel"].symptoms) - 1
