"""Password strength policy: >= 12 characters, not on a common-password list.

No arbitrary symbol rules — length and unpredictability are what actually holds
up, and forced symbol soup just pushes people to write passwords down.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

MIN_LENGTH = 12
MAX_LENGTH = 128
DATA_FILE = Path(__file__).resolve().parent / "data" / "common_passwords.txt"

_FALLBACK = frozenset(
    {
        "password",
        "passw0rd",
        "password1",
        "password12",
        "password123",
        "123456",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "iloveyou12",
        "adminadmin",
        "welcome123",
        "abc123abc123",
    }
)

_REPEAT_RUN = re.compile(r"(.)\1{5,}")
_KEYBOARD_RUN = re.compile(r"(?i)(qwert|asdfg|zxcvb|123456|654321)")


@lru_cache(maxsize=1)
def blocklist() -> frozenset[str]:
    if not DATA_FILE.is_file():
        return _FALLBACK
    lines = DATA_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip())


def check_password(email: str, password: str) -> list[str]:
    """Return human-readable problems; an empty list means the password is OK."""
    problems: list[str] = []
    lowered = password.lower()
    if len(password) < MIN_LENGTH:
        problems.append(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Password must be at most {MAX_LENGTH} characters.")
    if password != password.strip():
        problems.append("Password must not start or end with whitespace.")
    if lowered in blocklist():
        problems.append("That password is on a known-breached list. Pick another.")
    if email:
        local = email.split("@", 1)[0].lower()
        if local and (local in lowered or lowered in local):
            problems.append("Password must not contain your email address.")
        domain = email.split("@", 1)[-1].split(".", 1)[0].lower()
        if len(domain) >= 4 and domain in lowered:
            problems.append("Password must not contain your email domain.")
    if _REPEAT_RUN.search(password) or _KEYBOARD_RUN.search(password):
        problems.append("Password is too repetitive or keyboard-sequential.")
    if len(set(password)) <= 3:
        problems.append("Password uses too few distinct characters.")
    return problems
