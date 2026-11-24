"""Strict Pydantic v2 request/response models.

``strict=True`` + ``extra="forbid"`` means the API rejects loosely typed or
unexpected payloads at the boundary instead of coercing them.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .profiles import DEFAULT_PROFILE, PROFILES

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Reject absurd epochs rather than trusting client clocks.
MIN_EPOCH = 946_684_800  # 2000-01-01T00:00:00Z
TZ_OFFSET_LIMIT = 840  # UTC+14
EventCategory = Literal["relief", "trigger"]
EventType = Literal["exercise", "symptom", "context"]

Email = Annotated[str, Field(min_length=5, max_length=254)]
Name = Annotated[str, Field(min_length=1, max_length=80)]
Region = Annotated[str, Field(min_length=1, max_length=60)]
Note = Annotated[str, Field(max_length=500)]
IconKey = Annotated[str, Field(min_length=1, max_length=40)]
Severity = Annotated[int, Field(ge=1, le=10)]
Pain = Annotated[int, Field(ge=0, le=10)]
Count = Annotated[int, Field(ge=0, le=10_000)]
Seconds = Annotated[int, Field(ge=0, le=86_400)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


# -- auth ------------------------------------------------------------------


class RegisterRequest(StrictModel):
    email: Email
    password: Annotated[str, Field(min_length=8, max_length=256)]
    # Which preset set to seed the account with, or "none" to start empty. The
    # default is the postnatal set so a client predating the feature behaves
    # exactly as before; the SPA always sends an explicit choice.
    profile: Annotated[str, Field(min_length=1, max_length=40)] = DEFAULT_PROFILE

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_RE.match(cleaned):
            raise ValueError("invalid email address")
        return cleaned

    @field_validator("profile")
    @classmethod
    def _profile_exists(cls, value: str) -> str:
        key = value.strip().lower()
        if key not in PROFILES:
            # Named list: a typo like "pelvic" should say what was possible.
            raise ValueError(
                "unknown profile; choose one of " + ", ".join(sorted(PROFILES)) + " or omit it"
            )
        return key


class LoginRequest(StrictModel):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=256)]

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_RE.match(cleaned):
            raise ValueError("invalid email address")
        return cleaned


class VerifyRequest(StrictModel):
    """A confirmation token posted by the SPA from the emailed link."""

    token: Annotated[str, Field(min_length=20, max_length=512)]


class PasswordResetRequest(StrictModel):
    email: Email

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_RE.match(cleaned):
            raise ValueError("invalid email address")
        return cleaned


class PasswordResetConfirm(StrictModel):
    """The token from the emailed link, plus the new password, in one POST.

    The password is checked before the token is consumed, so a rejected password
    does not burn a single-use link — and the response cannot be used to tell a
    valid token from an invalid one, because a weak password fails either way.
    """

    token: Annotated[str, Field(min_length=20, max_length=512)]
    password: Annotated[str, Field(min_length=8, max_length=256)]


class UserOut(StrictModel):
    id: str
    email: str
    created_at_utc: int
    is_verified: bool
    # The tracking set the account started from ("none" if it started empty).
    # Not a setting: changing it later does not rewrite history, so it is shown
    # as provenance, and the label comes from GET /catalog/profiles.
    profile_key: str = DEFAULT_PROFILE


class AuthOut(StrictModel):
    user: UserOut


# -- catalog ---------------------------------------------------------------


class WindowOut(StrictModel):
    """One lag window a profile offers: "soreness 1-6 h after the session"."""

    label: str
    min_hours: float
    max_hours: float


class ProfileOut(StrictModel):
    """A starting set, as the sign-up picker needs to show it.

    `counts` rather than the name lists: the picker shows "10 presets · 16
    triggers" instead of a wall of text, and the API stays one small payload.
    """

    key: str
    label: str
    blurb: str
    counts: dict[str, int]
    windows: list[WindowOut]
    default_window: str


class ExerciseDefinitionCreate(StrictModel):
    name: Name
    body_region: Region | None = None
    default_sets: Count | None = None
    default_reps: Count | None = None
    default_sec: Seconds | None = None
    icon_key: IconKey = "physio"
    sort_order: int | None = None


class ExerciseDefinitionUpdate(StrictModel):
    name: Name | None = None
    body_region: Region | None = None
    default_sets: Count | None = None
    default_reps: Count | None = None
    default_sec: Seconds | None = None
    icon_key: IconKey | None = None
    is_archived: bool | None = None
    sort_order: int | None = None


class SymptomDefinitionCreate(StrictModel):
    name: Name
    default_region: Region | None = None
    icon_key: IconKey = "symptom"
    sort_order: int | None = None


class SymptomDefinitionUpdate(StrictModel):
    name: Name | None = None
    default_region: Region | None = None
    icon_key: IconKey | None = None
    is_archived: bool | None = None
    sort_order: int | None = None


class ContextDefinitionCreate(StrictModel):
    category: EventCategory
    name: Name
    icon_key: IconKey = "context"
    sort_order: int | None = None


class ContextDefinitionUpdate(StrictModel):
    name: Name | None = None
    icon_key: IconKey | None = None
    is_archived: bool | None = None
    sort_order: int | None = None


# -- logging ---------------------------------------------------------------


class _LogShared(StrictModel):
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None
    tz_offset_min: Annotated[int, Field(ge=-TZ_OFFSET_LIMIT, le=TZ_OFFSET_LIMIT)] = 0
    note: Note | None = None


class ExerciseLogCreate(_LogShared):
    exercise_id: Annotated[str, Field(min_length=1, max_length=36)]
    sets_done: Count | None = None
    reps_done: Count | None = None
    duration_sec: Seconds | None = None
    effort_rpe: Severity | None = None
    pain_during: Pain | None = None


class ExerciseLogUpdate(StrictModel):
    sets_done: Count | None = None
    reps_done: Count | None = None
    duration_sec: Seconds | None = None
    effort_rpe: Severity | None = None
    pain_during: Pain | None = None
    note: Note | None = None
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None


class SymptomLogCreate(_LogShared):
    symptom_id: Annotated[str, Field(min_length=1, max_length=36)]
    body_region: Region | None = None
    severity: Severity
    # True when the client filled the number in because the scale had to hold
    # *something*, not because the person chose it. It never changes the value or
    # how it is averaged; it lets the UI and the insights say "this 5 was the
    # default" instead of presenting an unchosen number as a measurement.
    severity_default: bool = False
    duration_min: Annotated[int, Field(ge=0, le=100_000)] | None = None


class SymptomLogUpdate(StrictModel):
    body_region: Region | None = None
    severity: Severity | None = None
    duration_min: Annotated[int, Field(ge=0, le=100_000)] | None = None
    note: Note | None = None
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None


class ContextLogCreate(_LogShared):
    context_id: Annotated[str, Field(min_length=1, max_length=36)]
    intensity: Severity | None = None


class ContextLogUpdate(StrictModel):
    intensity: Severity | None = None
    note: Note | None = None
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None


class LogOut(StrictModel):
    id: str
    event_type: EventType
    status: str = "created"


# -- plan events -----------------------------------------------------------

# Coarse on purpose. Dosage, body site or clinician structure would turn a note
# ("she changed the programme") into a medical record this app has no business
# validating or interpreting. `PLAN_KINDS` is derived from the Literal so the
# CHECK constraint in 003, the API and the picker labels cannot drift apart.
PlanKind = Literal["appointment", "programme_change", "medication", "goal", "note"]
PLAN_KINDS: tuple[str, ...] = get_args(PlanKind)


class PlanEventCreate(StrictModel):
    kind: PlanKind = "note"
    text: Annotated[str, Field(min_length=1, max_length=300)]
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None
    tz_offset_min: Annotated[int, Field(ge=-TZ_OFFSET_LIMIT, le=TZ_OFFSET_LIMIT)] = 0

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # `min_length=1` lets "   " through, and a blank marker on a chart is
        # noise with a date attached, not a note.
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class PlanEventUpdate(StrictModel):
    kind: PlanKind | None = None
    text: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    occurred_at_utc: Annotated[int, Field(ge=MIN_EPOCH)] | None = None

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text must not be blank")
        return value


# -- misc ------------------------------------------------------------------


class ReorderRequest(StrictModel):
    ids: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(max_length=500)
