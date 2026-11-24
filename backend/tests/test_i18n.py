"""The language rule, checked rather than intended.

Three things here are load-bearing for the rest of the feature:

* **Coverage.** Every key has both languages, every placeholder matches between
  them, and every preset name in every profile has a French spelling. A missing
  translation is a cosmetic bug at runtime — the app answers in English — which is
  exactly the kind of bug that never gets reported and ships for two years.
* **Precedence.** The account's language wins over the header, and a failed login
  deliberately does *not* use the account's language, because that would tell an
  attacker which addresses exist by the language of the reply.
* **What a language switch does not do.** It never rewrites a row that already
  exists. A person's diary vocabulary is theirs, not a view over a dictionary.
"""

from __future__ import annotations

import re

import pytest
from app import seed
from app.deps import account_locale  # noqa: F401  (imported to keep the dep wired)
from app.i18n import EN, FR, MESSAGES, negotiate, normalize, resolve, t
from app.messages import MESSAGES as TABLE
from app.presets_fr import PRESET_NAMES_FR, PROFILE_COPY_FR
from app.profiles import PROFILES
from app.routers.export import CSV_COLUMNS
from fastapi.testclient import TestClient

from .conftest import csrf_headers, register

PLACEHOLDER = re.compile(r"\{(\w+)\}")


# -- the table ------------------------------------------------------------


def test_every_key_has_both_languages() -> None:
    for key, entry in MESSAGES.items():
        assert set(entry) == {EN, FR}, f"{key} is missing a language"
        for code, text in entry.items():
            assert text.strip(), f"{key}/{code} is blank"


def test_the_two_languages_agree_on_their_placeholders() -> None:
    """A French sentence that forgot `{limit}` would raise at request time."""
    for key, entry in MESSAGES.items():
        assert set(PLACEHOLDER.findall(entry[EN])) == set(PLACEHOLDER.findall(entry[FR])), key


def test_the_table_is_the_only_one() -> None:
    assert TABLE is MESSAGES


def test_every_csv_column_is_translated() -> None:
    missing = [column for column in CSV_COLUMNS if f"csv.{column}" not in MESSAGES]
    assert not missing, f"add these to app/messages.py: {missing}"


@pytest.mark.parametrize("locale", [EN, FR])
def test_unknown_keys_answer_with_themselves(locale: str) -> None:
    assert t("nope.not-a-key", locale) == "nope.not-a-key"


# -- negotiating a language ------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("fr", FR),
        ("fr-CA", FR),
        ("fr-CA;q=0.9", FR),
        ("fr_FR", FR),
        ("FR_ca", FR),
        ("en-CA", EN),
        ("en", EN),
        ("", EN),
        ("   ", EN),
        ("not a tag", EN),
        (None, EN),
        (123, EN),
    ],
)
def test_normalize_is_forgiving(raw: object, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, EN),
        ("", EN),
        ("fr-CA,fr;q=0.9,en;q=0.8", FR),
        ("en-CA,fr-CA;q=0.5", EN),
        # Quality order beats listing order: this browser reads English first.
        ("fr-CA;q=0.5,en-CA;q=0.9", EN),
        ("fr-CA;q=0, en;q=0", EN),
        ("*", EN),
        ("de,fr;q=0.8", FR),
        ("de,es", EN),
    ],
)
def test_negotiate_respects_quality_values(header: str | None, expected: str) -> None:
    assert negotiate(header) == expected


def test_the_account_outranks_the_header() -> None:
    assert resolve(user_locale="fr", header="en-CA,en") == FR
    assert resolve(user_locale="en", header="fr-CA") == EN
    assert resolve(user_locale=None, header="fr-CA") == FR
    # An unset preference is not "English": it is "I never chose", which is what
    # lets the header decide.
    assert resolve(user_locale="", header="fr-CA") == FR


# -- presets ---------------------------------------------------------------


def test_every_preset_name_has_a_quebec_french_spelling() -> None:
    """Full French includes the diary vocabulary, not just the buttons.

    A gap here is a French account with one English button in a list of nine,
    which is the sort of thing nobody reports.
    """
    english: set[str] = set()
    for profile in PROFILES.values():
        english.update(name for name, *_rest in profile.exercises)
        english.update(name for name, _region in profile.symptoms)
        english.update(name for _category, name in profile.contexts)
    english.update(name for name, *_rest in seed.SUGGESTED_EXERCISES)
    english.update(name for name, _region in seed.SUGGESTED_SYMPTOMS)
    english.update(name for _category, name in seed.SUGGESTED_CONTEXTS)
    missing = sorted(name for name in english if name not in PRESET_NAMES_FR)
    assert not missing, f"no French spelling for: {missing}"


def test_every_offered_profile_has_french_picker_copy() -> None:
    assert set(PROFILE_COPY_FR) == set(PROFILES)
    for key, (label, blurb) in PROFILE_COPY_FR.items():
        assert label.strip() and blurb.strip(), key
        # The label sits inside a <select> on a 360 px phone.
        assert len(label) <= 28, f"{key} label is {len(label)} characters"


def test_most_preset_names_actually_change_in_french() -> None:
    unchanged = [name for name, french in PRESET_NAMES_FR.items() if french.strip() == name]
    # A handful genuinely are the same word in both languages — "Constipation" and
    # "Massage" are honest translations, not laziness — so this guards the size of
    # the table rather than claiming every entry differs.
    assert len(unchanged) <= 12, f"suspiciously many untranslated entries: {unchanged}"


def test_a_french_account_is_seeded_in_french(client: TestClient) -> None:
    """The choice is made at sign-up because the presets become rows.

    Renaming them later would rewrite a diary, so this is the only moment the
    question can be asked.
    """
    register(client, locale="fr-CA")
    names = [row["name"] for row in client.get("/api/v1/catalog/exercises").json()]
    assert "Relèvements du plancher pelvien" in names
    assert "Pelvic Floor Lifts" not in names
    symptoms = [row["name"] for row in client.get("/api/v1/catalog/symptoms").json()]
    assert "Fuite d'urine" in symptoms
    contexts = [row["name"] for row in client.get("/api/v1/catalog/contexts").json()]
    assert "Compresse chaude" in contexts


def test_the_suggestion_pool_follows_the_account_language(client: TestClient) -> None:
    register(client, locale="fr-CA")
    names = [row["name"] for row in client.get("/api/v1/catalog/exercises/suggestions").json()]
    assert "Pont fessier" not in names, "the postnatal set already has it"
    assert any(name for name in names)
    assert all(name in PRESET_NAMES_FR.values() for name in names)


def test_switching_language_renames_nothing(client: TestClient) -> None:
    register(client, locale="fr-CA")
    before = [row["name"] for row in client.get("/api/v1/catalog/exercises").json()]
    client.patch(
        "/api/v1/auth/preferences", json={"locale": "en"}, headers=csrf_headers(client)
    )
    after = [row["name"] for row in client.get("/api/v1/catalog/exercises").json()]
    assert after == before
    assert client.get("/api/v1/auth/me").json()["user"]["locale"] == EN
