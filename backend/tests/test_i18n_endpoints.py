"""The language of the server's own answers, and of the account's time zone.

These are the parts a browser toggle cannot fix on its own: the email that gets
read on another device, the error text of a request that failed before the SPA
could render anything, and the day boundary the insights are cut on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.i18n import EN, FR
from app.mailer import Message, OutboxMailer
from app.timezones import (
    effective,
    has_zone_setting,
    normalize_timezone,
    offset_minutes,
    utc_offset_label,
)
from fastapi.testclient import TestClient

from .conftest import configure, csrf_headers, register

PASSWORD = "sunlit-origami-42"


def _mail_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> TestClient:
    """A client with email enabled, delivered to an in-memory outbox.

    Not entered: the caller uses `with`, because the app's lifespan is what opens
    the database and builds the mailer.
    """
    configure(
        tmp_path,
        monkeypatch,
        SYMPHYSIO_MAIL_BACKEND="outbox",
        SYMPHYSIO_EMAIL_FROM="Symphysio <confirm@example.org>",
        # email_enabled needs a key even for the outbox: the same three checks
        # decide "can this deployment send mail at all", in every backend.
        RESEND_API_KEY="re_never_used_in_tests",
        **env,
    )
    from app.main import create_app

    return TestClient(create_app())


def _outbox(client: TestClient) -> list[Message]:
    assert isinstance(client.app.state.mailer, OutboxMailer)
    return client.app.state.mailer.outbox


# -- preferences -----------------------------------------------------------


def test_sign_up_records_both_preferences(client: TestClient) -> None:
    body = register(client, locale="fr-CA", timezone="America/Toronto")
    assert body["user"]["locale"] == FR
    assert body["user"]["timezone"] == "America/Toronto"
    assert client.get("/api/v1/auth/me").json()["user"]["locale"] == FR


def test_an_account_that_never_chose_has_no_time_zone_of_its_own(client: TestClient) -> None:
    body = register(client)
    assert body["user"]["locale"] == EN
    # NULL, not "UTC": "never chose" is a different fact from "chose UTC", and it
    # is what lets an instance default apply without overwriting anybody.
    assert body["user"]["timezone"] is None


def test_preferences_report_the_zone_actually_in_use(client: TestClient) -> None:
    register(client, timezone="America/Toronto")
    prefs = client.get("/api/v1/auth/preferences").json()
    assert prefs["timezone"] == "America/Toronto"
    assert prefs["effective_timezone"] == "America/Toronto"
    assert prefs["utc_offset"] in {"UTC-5", "UTC-4"}  # depends on the date, never on UTC


def test_the_instance_default_applies_to_an_account_that_never_chose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One server, one country: nobody has to find the setting for "today" to work."""
    configure(tmp_path, monkeypatch, SYMPHYSIO_DEFAULT_TIMEZONE="America/Toronto")
    from app.main import create_app

    with TestClient(create_app()) as client:
        register(client)
        assert client.get("/api/v1/auth/preferences").json()["effective_timezone"] == (
            "America/Toronto"
        )


def test_an_unparsable_instance_default_refuses_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo here would otherwise mean every account silently gets UTC."""
    configure(tmp_path, monkeypatch, SYMPHYSIO_DEFAULT_TIMEZONE="America/Torronto")
    from app.main import create_app

    with pytest.raises(ValueError, match="SYMPHYSIO_DEFAULT_TIMEZONE"):
        create_app()


def test_a_bad_zone_is_refused_at_sign_up(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "someone@example.com",
            "password": PASSWORD,
            "timezone": "Mars/Phobos",
        },
    )
    assert response.status_code == 422
    assert "time zone" in response.text


def test_preferences_are_independently_updatable(client: TestClient) -> None:
    register(client)
    only_language = client.patch(
        "/api/v1/auth/preferences", json={"locale": "fr"}, headers=csrf_headers(client)
    )
    assert only_language.status_code == 200
    body = only_language.json()
    assert body["locale"] == FR
    assert body["timezone"] is None

    only_zone = client.patch(
        "/api/v1/auth/preferences", json={"timezone": "Europe/Paris"}, headers=csrf_headers(client)
    )
    assert only_zone.json()["locale"] == FR
    assert only_zone.json()["effective_timezone"] == "Europe/Paris"


def test_clearing_the_zone_goes_back_to_the_instance_default(client: TestClient) -> None:
    register(client, timezone="America/Vancouver")
    cleared = client.patch(
        "/api/v1/auth/preferences", json={"timezone": None}, headers=csrf_headers(client)
    )
    assert cleared.json()["timezone"] is None
    assert cleared.json()["effective_timezone"] == "UTC"


def test_preferences_need_not_be_loose(client: TestClient) -> None:
    register(client)
    response = client.patch(
        "/api/v1/auth/preferences",
        json={"timezone": "Not A Zone"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422


def test_preferences_require_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/auth/preferences").status_code == 401


# -- time zones ------------------------------------------------------------


def test_zone_helpers() -> None:
    assert normalize_timezone("America/Toronto") == "America/Toronto"
    assert normalize_timezone("  ") == ""
    assert normalize_timezone(None) == ""
    assert normalize_timezone("Not A Zone") is None
    assert effective(None, None, "UTC") == "UTC"
    assert effective("Europe/Paris", None, "America/Toronto") == "Europe/Paris"
    assert effective(None, "America/Winnipeg", "America/Toronto") == "America/Winnipeg"
    assert effective(None, None, "America/Toronto") == "America/Toronto"
    assert has_zone_setting(None, "UTC") is False
    assert has_zone_setting("UTC", "UTC") is True
    assert has_zone_setting(None, "America/Toronto") is True
    # Montreal is UTC-5 in winter, UTC-4 in summer; both are the same zone name.
    assert utc_offset_label("America/Toronto", 1_764_000_000) == "UTC-5"
    assert utc_offset_label("America/Toronto", 1_780_000_000) == "UTC-4"
    assert offset_minutes("UTC", 0) == 0


def test_a_bad_default_zone_is_refused_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise every account that never chose a zone silently gets UTC."""
    configure(tmp_path, monkeypatch, SYMPHYSIO_DEFAULT_TIMEZONE="Toronto, Ontario")
    from app.main import create_app

    with pytest.raises(ValueError, match="SYMPHYSIO_DEFAULT_TIMEZONE"):
        create_app()


# -- the mail --------------------------------------------------------------


def test_the_confirmation_mail_is_written_in_the_accounts_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _mail_client(tmp_path, monkeypatch, SYMPHYSIO_PUBLIC_URL="https://example.test") as client:
        register(client, email="qq@example.com", locale="fr-CA")
        message = _outbox(client)[0]
        assert message.subject == "Confirmez votre compte Symphysio"
        assert "Confirmez votre courriel" in message.html
        assert "Confirmer le compte" in message.html
        # The invariant the security review keeps asking about, in either
        # language: no health content ever leaves in an email.
        joined = (message.text + message.html).lower()
        for word in ("symptom", "fuite", "douleur", "plancher", "severity"):
            assert word not in joined


def test_an_english_account_still_gets_english_mail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _mail_client(tmp_path, monkeypatch, SYMPHYSIO_PUBLIC_URL="https://example.test") as client:
        register(client, email="en@example.com")
        assert _outbox(client)[0].subject == "Confirm your Symphysio account"


def test_sign_up_with_no_locale_says_which_language_the_mail_should_be(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sign-up has no account to ask yet, so the request answers for it."""
    with _mail_client(tmp_path, monkeypatch, SYMPHYSIO_PUBLIC_URL="https://example.test") as client:
        client.post(
            "/api/v1/auth/register",
            json={"email": "header@example.com", "password": PASSWORD},
            headers={"Accept-Language": "fr-CA,fr;q=0.9"},
        )
        assert _outbox(client)[0].subject == "Confirmez votre compte Symphysio"


def test_the_reset_mail_follows_the_account_not_the_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The person who owns the address chose French; the browser asking may not be theirs."""
    with _mail_client(
        tmp_path,
        monkeypatch,
        SYMPHYSIO_PUBLIC_URL="https://example.test",
        SYMPHYSIO_EMAIL_CONFIRMATION="off",
    ) as client:
        register(client, email="reset@example.com", locale="fr-CA")
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "reset@example.com"},
            headers={"Accept-Language": "en", **csrf_headers(client)},
        )
        assert response.status_code == 202
        assert _outbox(client)[-1].subject == "Réinitialisez votre mot de passe Symphysio"


def test_an_unknown_address_still_answers_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reset endpoint must not reveal, in any language, that the address is new."""
    with _mail_client(
        tmp_path,
        monkeypatch,
        SYMPHYSIO_PUBLIC_URL="https://example.test",
        SYMPHYSIO_EMAIL_CONFIRMATION="off",
    ) as client:
        register(client, email="owner@example.com", locale="fr-CA")
        mine = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "owner@example.com"},
            headers=csrf_headers(client),
        )
        stranger = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nobody@example.com"},
            headers=csrf_headers(client),
        )
        assert mine.status_code == stranger.status_code == 202
        assert mine.content == stranger.content


# -- error text ------------------------------------------------------------


def test_an_unknown_session_answers_in_the_browsers_language(client: TestClient) -> None:
    response = client.get("/api/v1/analytics/summary", headers={"Accept-Language": "fr-CA"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Non authentifié"


def test_a_signed_in_accounts_errors_follow_the_account(client: TestClient) -> None:
    register(client, locale="fr-CA")
    first = client.post(
        "/api/v1/catalog/exercises",
        json={"name": "Exercice maison"},
        headers={"Accept-Language": "en", **csrf_headers(client)},
    )
    assert first.status_code == 201
    duplicate = client.post(
        "/api/v1/catalog/exercises",
        json={"name": "Exercice maison"},
        headers={"Accept-Language": "en", **csrf_headers(client)},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Vous avez déjà un élément de catalogue avec ce nom."


def test_a_weak_password_is_explained_in_the_language_of_the_person_typing_it(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "faible@example.com", "password": "abcabcabc12"},
        headers={"Accept-Language": "fr-CA"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Le mot de passe doit comporter au moins 12 caractères."


def test_a_failed_login_never_replies_in_the_accounts_language(client: TestClient) -> None:
    """Wording is an answer, and this one must not depend on whether the address exists.

    A French account answered in French and an unknown address in English — which
    is an account-enumeration oracle dressed up as a translation.
    """
    register(client, email="francophone@example.com", locale="fr-CA")
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "francophone@example.com", "password": "wrong-password-123"},
        headers={"Accept-Language": "en", **csrf_headers(client)},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Email or password is incorrect."
