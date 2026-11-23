"""The password policy: length first, no famous passwords, no email reuse.

There is no breached-password corpus here on purpose: at this scale a 20 000-entry
data file is a maintenance liability (it once went missing from every clone and
image because of a .gitignore pattern) while a user who wants
"correcthorsebattery" is free to have it. What this file does check is the cheap
stuff that catches real mistakes: too short, all one character, a keyboard run,
or the account's own email address.
"""

from __future__ import annotations

from app.password_policy import MAX_LENGTH, MIN_LENGTH, check_password

EMAIL = "someone@example.com"


def test_a_short_password_is_rejected():
    assert any("12 characters" in problem for problem in check_password(EMAIL, "tenchars!!"))


def test_the_famous_ones_are_rejected_even_though_they_are_long_enough():
    for password in ("password1234", "123456789012", "welcome123456"):
        assert check_password(EMAIL, password), password


def test_a_password_containing_the_email_is_rejected():
    problems = check_password(EMAIL, "someone-diary-2026")
    assert any("email" in problem.lower() for problem in problems)


def test_runs_and_single_character_passwords_are_rejected():
    assert check_password(EMAIL, "aaaaaaaaaaaa")
    assert check_password(EMAIL, "qwertyuiop12")
    assert check_password(EMAIL, "000000000000")


def test_a_long_random_passphrase_is_accepted():
    assert check_password(EMAIL, "sunlit-origami-42") == []
    assert check_password(EMAIL, "x" * (MAX_LENGTH + 1)), "over-long passwords must fail"
    assert len("sunlit-origami-42") >= MIN_LENGTH
