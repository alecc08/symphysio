"""One language rule for everything the server says out loud.

Three things leave this server as words: the error text in an API response, the
emails (confirmation and password reset), and the CSV column headers a
physiotherapist opens. Before this module each of them was an English string
literal at its call site, which is how a French account ended up with a French
app full of English errors.

The rules, in the order they are tried:

1. **The signed-in user's ``users.locale``.** Authoritative when there is a
   session: it is what the person chose in Settings, it follows them to another
   device, and it is what the password-reset mail uses — that flow looks the
   account up by address anyway, so the preference is already in hand.
2. **The request's ``Accept-Language``.** Covers the unauthenticated requests
   that still produce words: sign-up (whose confirmation mail is queued inside
   the request) and the password-reset request from someone who cannot sign in.
   The SPA sends this header itself from its own toggle, so a browser whose
   *browser* language is something else does not get an English email.
3. **English**, which is also the fallback for any missing key: an untranslated
   string answers in English rather than crashing a login.

Nothing here is medical text — it is interface copy. ``tests/test_i18n.py``
asserts every key carries both languages, so "fully translated" is a checked
property rather than an intention.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from .messages import EN, FR, MESSAGES

LOCALES: tuple[str, ...] = (EN, FR)
DEFAULT_LOCALE = EN

# `fr`, `fr-CA`, `fr-CA;q=0.9`, `fr_FR` all mean French; everything else in a
# Quebec deployment means English. Tags are matched on the primary subtag only,
# deliberately: no content negotiation by region, because the only difference
# between fr-CA and fr-FR here is a spelling we do not get to argue about.
_TAG = re.compile(r"^([a-z]{2,3})(?:[-_][a-z0-9-]+)?$", re.IGNORECASE)


def normalize(raw: object) -> str:
    """Any locale-ish value (`fr`, `fr-CA`, `FR_ca`) to a supported code, or ``en``.

    Never raises: this is applied to client-supplied strings, and a bad locale
    is a cosmetic problem, not a reason to fail a request. A stray `;q=…` tail is
    tolerated, because the field is sometimes filled in from a header.
    """
    if not isinstance(raw, str):
        return DEFAULT_LOCALE
    tag = raw.strip().partition(";")[0].strip()
    match = _TAG.match(tag)
    if match is None:
        return DEFAULT_LOCALE
    return FR if match.group(1).lower() == FR else DEFAULT_LOCALE


def _primary(raw: str) -> str | None:
    """The primary subtag of a supported language, or None if it is not one we have.

    A browser that asks for `de` first must not be read as asking for English:
    ignoring an unsupported tag is what lets `de, fr;q=0.8` mean French.
    """
    tag = raw.strip().partition(";")[0].strip()
    match = _TAG.match(tag)
    if match is None:
        return None
    subtag = match.group(1).lower()
    return subtag if subtag in LOCALES else None


def negotiate(header: str | None) -> str:
    """Pick a supported language from an ``Accept-Language`` header.

    Quality values are respected (``fr;q=0.8, en;q=0.9`` picks English), because
    ignoring them is how a browser set to "French then English" silently gets
    served the wrong one. Languages this app does not have are skipped rather
    than counted as English. A missing or unparsable header is English.
    """
    if not header:
        return DEFAULT_LOCALE
    ranked: list[tuple[float, int, str]] = []
    for position, entry in enumerate(header.split(",")):
        tag, _, params = entry.strip().partition(";")
        code = _primary(tag)
        if code is None:
            continue
        quality = 1.0
        for parameter in params.split(";"):
            name, _, value = parameter.strip().partition("=")
            if name.lower() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        # `position` breaks ties the way the header states them: earlier wins.
        ranked.append((quality, -position, code))
    for quality, _, code in sorted(ranked, reverse=True):
        if quality > 0:
            return code
    return DEFAULT_LOCALE


def resolve(*, user_locale: object = None, header: str | None = None) -> str:
    """The documented precedence: account, then header, then English."""
    if user_locale is not None:
        candidate = normalize(user_locale)
        if isinstance(user_locale, str) and user_locale.strip():
            return candidate
    return negotiate(header)


def t(key: str, locale: object = DEFAULT_LOCALE, **params: object) -> str:
    """Translate ``key`` for ``locale``, substituting ``{name}`` placeholders.

    A missing key or a missing column returns whatever exists rather than
    raising: a 401 whose message crashes is worse than a 401 in the wrong
    language. ``tests/test_i18n.py`` is what keeps the table complete.
    """
    entry = MESSAGES.get(key)
    if entry is None:
        return key.format(**params) if params else key
    text = entry.get(normalize(locale)) or entry.get(EN) or key
    return text.format(**params) if params else text


def t_or(key: str, locale: object, fallback: str) -> str:
    """``t`` with an explicit answer for a key that does not exist.

    Used by the CSV header, where the column name *is* the sensible fallback: a
    column added without a translation prints its own name instead of an empty
    header cell, and tests/test_i18n.py is what makes adding the translation
    mandatory rather than optional.
    """
    if key not in MESSAGES:
        return fallback
    return t(key, locale)


def language_name(locale: object) -> str:
    """The language written in its own language, for a language picker."""
    return "Français" if normalize(locale) == FR else "English"


def from_headers(headers: object, user: dict | None = None) -> str:
    """``resolve`` with the two header lookups done, for a request-shaped object.

    Works with Starlette's ``Headers`` and a plain dict, which is what keeps the
    call sites in the routers one line each.
    """
    header = headers.get("accept-language") if isinstance(headers, Mapping) else None
    return resolve(user_locale=(user or {}).get("locale"), header=header)
