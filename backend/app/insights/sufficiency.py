"""The coverage gate: when a card must say "not yet" instead of showing a number.

Every insights card shares this, because the failure mode is per-card: one card
quietly shows a bar built on two entries while another says "keep logging", and
the app stops being trustworthy. The thresholds are counts, not rates — with a
denominator this small a rate is a coin flip with decimals on it.

Three states, and the copy that goes with them lives in the UI; what is decided
here is *which* state, once, for every card.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

MIN_DAYS_FOR_ANY_CARD = 7  # under a week of entries: describe, do not analyse
MIN_LOGS_FOR_A_CLAIM = 15  # entries before any card may compare two things
MIN_PAIRS_FOR_ASSOCIATION = 1  # needs >=5 logs on both sides of at least one pair


@dataclass(frozen=True)
class Coverage:
    state: str  # "enough" | "thin" | "none"
    days_covered: int
    days_requested: int
    symptom_logs: int
    exercise_logs: int
    eligible_pairs: int

    @property
    def association_allowed(self) -> bool:
        return self.state == "enough"

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "days_covered": self.days_covered,
            "days_requested": self.days_requested,
            "symptom_logs": self.symptom_logs,
            "exercise_logs": self.exercise_logs,
            "eligible_pairs": self.eligible_pairs,
        }


def coverage(
    *,
    symptom_logs: int,
    exercise_logs: int,
    days_covered: int,
    days_requested: int,
    eligible_pairs: int,
    context_logs: int = 0,
    pairs_required: bool = True,
) -> Coverage:
    """One verdict for every card, from the counts the card actually has.

    `pairs_required` is False for the cards that never compare two definitions —
    a symptom against its own earlier weeks needs entries, not definition pairs,
    and leaving the pair rule on would make that card say "not enough" forever.
    """
    total = symptom_logs + exercise_logs + context_logs
    if total == 0 or days_covered < 2:
        state = "none"
    elif (
        days_covered < MIN_DAYS_FOR_ANY_CARD
        or symptom_logs < MIN_LOGS_FOR_A_CLAIM
        or (pairs_required and eligible_pairs < MIN_PAIRS_FOR_ASSOCIATION)
    ):
        state = "thin"
    else:
        state = "enough"
    return Coverage(
        state=state,
        days_covered=days_covered,
        days_requested=days_requested,
        symptom_logs=symptom_logs,
        exercise_logs=exercise_logs,
        eligible_pairs=eligible_pairs,
    )


def eligible_pair_count(
    exposure_log_counts: Iterable[int], symptom_log_counts: Iterable[int], min_logs: int = 5
) -> int:
    """How many (exposure, symptom) pairs even have the minimum data.

    The card prints "N of M pairs examined"; M comes from here, so the number has
    to be computable without running the whole join.
    """
    exposures = sum(1 for count in exposure_log_counts if count >= min_logs)
    symptoms = sum(1 for count in symptom_log_counts if count >= min_logs)
    return exposures * symptoms
