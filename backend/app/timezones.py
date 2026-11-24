"""Time zones: one account-level truth, without rewriting what was logged.

The diary stores `occurred_at_utc` (epoch seconds) plus the `tz_offset_min` the
device reported *at that instant*, and every local bucket — "morning stiffness",
"today", the streak — is cut with `occurred_at_utc + tz_offset_min * 60`. That
was the deliberate choice in docs/DATABASE.md: an offset survives a phone
crossing a border, and the server needs no tz database.

What it never gave anyone:

* **A default.** With no rows yet there is no offset, and
  `analytics._latest_offset` answered 0 — UTC. A person in Montreal starting an
  account saw "today" flip at 19:00.
* **A floor.** The offset is client input: a laptop whose zone is wrong writes
  wrong local buckets, silently, forever.
* **A label.** Nothing in the API said what "local" meant.

So the account now carries an IANA zone (`users.timezone`, nullable), and
`SYMPHYSIO_DEFAULT_TIMEZONE` gives an instance one for accounts that never chose.
What does **not** change: rows keep the offset they were written with. Re-deriving
history from today's zone would move last March's day bucket, which is the one
thing an insights app must not do.

The list of zones is deliberately short and validated by `zoneinfo`, not by that
list alone: `users.timezone` accepts any name the system knows, and the picker
shows the short list plus the device's own zone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Empty string means "this account has not chosen", which is different from
# "the account chose UTC" and lets the instance default apply.
UNSET = ""

#: Offered in the picker, in the order they read on a phone. Deliberately the
#: Americas plus a handful, because the list is a convenience, not a whitelist:
#: the server accepts any zone `zoneinfo` resolves.
SUPPORTED_TIMEZONES: tuple[str, ...] = (
    "America/Toronto",
    "America/Winnipeg",
    "America/Edmonton",
    "America/Vancouver",
    "America/Halifax",
    "America/St_Johns",
    "America/Montreal",
    "America/New_York",
    "America/Phoenix",
    "America/Mexico_City",
    "America/Bogota",
    "Atlantic/Reykjavik",
    "Europe/Paris",
    "UTC",
)

FALLBACK = "UTC"


def normalize_timezone(raw: object) -> str | None:
    """A zone name to its IANA spelling, or ``None`` when it is not a zone.

    ``None`` and ``""`` both mean "unset" and are returned as ``UNSET`` so a
    caller can tell "clear it" from "invalid".
    """
    if raw is None:
        return UNSET
    if not isinstance(raw, str):
        return None
    candidate = raw.strip()
    if not candidate:
        return UNSET
    try:
        ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return candidate


def header_timezone(header: str | None) -> str:
    """The ``X-Timezone`` the SPA sends while nobody is signed in.

    Trusted the same way the client's `tz_offset_min` has always been trusted:
    it only ever chooses the language-neutral shape of a display, never a
    permission, and it is ignored completely for a signed-in account.
    """
    if not header:
        return UNSET
    return normalize_timezone(header) or UNSET


def effective(
    user_timezone: object = None, header: str | None = None, default: str = FALLBACK
) -> str:
    """Account zone, then the request's header, then the instance default.

    The instance default exists because one server usually has one country: an
    account that never picked anything still gets Montreal rather than UTC.
    """
    stored = normalize_timezone(user_timezone)
    if stored:
        return stored
    from_request = header_timezone(header)
    if from_request:
        return from_request
    return normalize_timezone(default) or FALLBACK


def has_zone_setting(user_timezone: object = None, default: str = FALLBACK) -> bool:
    """Whether a real zone is configured, on the account or on the instance.

    This exists for one caller: the analytics endpoints, which for years inferred
    "local" from the newest row's `tz_offset_min` because nothing else knew. That
    inference is still the fallback when nobody has configured anything, and is
    ignored the moment either the account or the deployment has said where it is.
    An account that explicitly chose UTC counts as having said so.
    """
    return bool(normalize_timezone(user_timezone)) or (
        normalize_timezone(default) != FALLBACK and bool(normalize_timezone(default))
    )


def offset_minutes(zone: str, at_utc: int) -> int:
    """The zone's offset from UTC at an instant — DST included.

    Used for "what is today in that zone right now", never to rewrite a row:
    each row already carries the offset its device saw at its own instant.
    """
    try:
        info = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        info = UTC  # type: ignore[assignment]
    stamp = datetime.fromtimestamp(int(at_utc), UTC).astimezone(info)
    return round(stamp.utcoffset().total_seconds() / 60) if stamp.utcoffset() else 0


def utc_offset_label(zone: str, at_utc: int | None = None) -> str:
    """A human label like ``UTC-5`` / ``UTC+2:30`` for the Settings row."""
    moment = at_utc if at_utc is not None else int(datetime.now(UTC).timestamp())
    minutes = offset_minutes(zone, moment)
    sign = "-" if minutes < 0 else "+"
    hours, minutes_left = divmod(abs(minutes), 60)
    tail = f":{minutes_left:02d}" if minutes_left else ""
    return f"UTC{sign}{hours}{tail}"


def local_wall_clock(zone: str, at_utc: int) -> datetime:
    """An aware datetime in that zone — what a "local day" boundary means here."""
    try:
        info: timezone | ZoneInfo = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        info = UTC
    return datetime.fromtimestamp(int(at_utc), UTC).astimezone(info)


def day_start_utc(zone: str, at_utc: int) -> int:
    """The instant local midnight began, on the local day containing ``at_utc``.

    DST-safe by construction: the zone is asked what midnight meant on that date,
    so a day that is 23 hours long is 23 hours long. This is only ever used for
    "what is today / this week *now*"; rows keep the offset they were written
    with, which is what keeps last March's day bucket from moving.
    """
    local = local_wall_clock(zone, at_utc)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())
