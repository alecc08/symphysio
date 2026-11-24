"""Password policy: at least 12 characters, and not one of the famous ones.

Length is what actually holds up against offline cracking, so there are no
symbol or capitalisation mandates — rule soup just pushes people to write their
passwords down. A weak password chosen by the user is their own risk; the small
inline list below is not a security boundary, it only catches the handful of
passwords that appear in every breach corpus and would otherwise sail past a
length check. It is deliberately twelve entries and no data file.
"""

from __future__ import annotations

import re

from .i18n import DEFAULT_LOCALE, t

MIN_LENGTH = 12
MAX_LENGTH = 128

# Long enough to clear MIN_LENGTH, famous enough to be guessed instantly.
_COMMON = frozenset(
    {
        "password1234",
        "password12345",
        "password123456",
        "passw0rd1234",
        "abc123456789",
        "qwertyuiop123",
        "123456789012",
        "iloveyou12345",
        "letmein123456",
        "welcome123456",
        "admin12345678",
        "changeme123456",
    }
)

_REPEAT_RUN = re.compile(r"(.)\1{5,}")
_KEYBOARD_RUN = re.compile(r"(?i)(qwert|asdfg|zxcvb|123456|654321)")


def check_password(email: str, password: str, locale: str = DEFAULT_LOCALE) -> list[str]:
    """Return human-readable problems; an empty list means the password is OK.

    The rules are one language and the sentences another: the checks below are
    unchanged in every case, only the wording follows the account's locale, so a
    French account is not asked to decode an English reason for a rejected
    password. English is the default, which is what every caller predating the
    preference passes.
    """
    problems: list[str] = []
    lowered = password.lower()
    if len(password) < MIN_LENGTH:
        problems.append(t("pw.too_short", locale, limit=MIN_LENGTH))
    if len(password) > MAX_LENGTH:
        problems.append(t("pw.too_long", locale, limit=MAX_LENGTH))
    if password != password.strip():
        problems.append(t("pw.whitespace", locale))
    if lowered in _COMMON:
        problems.append(t("pw.common", locale))
    if email:
        local = email.split("@", 1)[0].lower()
        if local and (local in lowered or lowered in local):
            problems.append(t("pw.in_email", locale))
        domain = email.split("@", 1)[-1].split(".", 1)[0].lower()
        if len(domain) >= 4 and domain in lowered:
            problems.append(t("pw.in_domain", locale))
    if _REPEAT_RUN.search(password) or _KEYBOARD_RUN.search(password):
        problems.append(t("pw.repetitive", locale))
    if len(set(password)) <= 3:
        problems.append(t("pw.few_distinct", locale))
    return problems
