"""The association maths: session windows, matched baselines, what may be printed.

Pure Python — no SQL, no FastAPI, no reading the clock. Every time boundary is
passed in, which is what makes the null testable: the checked-in probe
(`scripts/probes/lag_null.py`) pushes independent random logs through this module
and asserts **zero** findings. The SQL it replaced printed 374 of 400 candidate
pairs as findings at this diary's real density, and 400 of 400 at eight logs a day
(docs/INSIGHTS_PLAN.md §1.1). That is the failure mode this file exists to avoid.

The design in one paragraph: each exposure log is a *session*, and it is a hit
when ≥1 symptom log lands inside `[t + min, t + max]`. The comparison is not "how
often symptoms happen overall" but "how often they happen in windows of the same
length, at the same time of day, on days when X did not happen" — placed ±1 to ±3
days from each session. Time-of-day is a real effect here (there is a
time-of-day card), so an unmatched baseline would fake a lag out of mornings.
Then the Wilson interval, which is what survives small N honestly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

from .events import Event, exposures

DAY_SECONDS = 86_400
Z_95 = 1.96

# Verdict vocabulary is fixed and non-medical. Nothing here is diagnosis or
# advice: the app describes this person's diary and stops.
WORTH_A_LOOK = "worth a look"
LOOKS_LIKE_CHANCE = "looks like chance"
NOTHING_FOUND = "nothing found"
TOO_RARE = "seen too rarely to tell"
VERDICTS = (WORTH_A_LOOK, LOOKS_LIKE_CHANCE, NOTHING_FOUND, TOO_RARE)

# Why the gate stopped a pair, so the card can say the true reason rather than
# "not enough data" when the real answer is "you do this every day, so there is
# no comparable day to compare it with".
GATE_SESSIONS = "too_few_sessions"
GATE_HITS = "too_few_hits"
GATE_WINDOWS = "no_comparable_windows"

MIN_SESSIONS = 5  # a pair below this is not a pair, it is an anecdote
MIN_HITS = 3
MIN_LOGS_PER_DEFINITION = 5  # candidate filter, to hold multiplicity down
CONTROL_OFFSETS = (-3, -2, -1, 1, 2, 3)  # same hour-of-day, ±days, never the same day
MAX_FINDINGS = 8
FAMILY_ALPHA = 0.05  # one 5% false positive across the *whole* card, not per pair
MAX_Z = 4.5          # stops the correction demanding impossible data


def adjusted_z(pairs_examined: int, alpha: float = FAMILY_ALPHA) -> float:
    """Widen the interval as more pairs are examined.

    Looking at 60 pairs and reporting the most extreme is not 60 independent 5 %
    questions — it is one question with roughly a 95 % chance of producing a
    spurious "extreme" pair. This is the guard in docs/INSIGHTS_PLAN.md §2.3: the
    per-pair level becomes alpha / pairs, so the card as a whole still only makes
    a false claim about one time in twenty. No p-value is ever printed; the
    correction exists to decide what is allowed to be printed.
    """
    if pairs_examined <= 1:
        return Z_95
    per_pair = alpha / pairs_examined
    return min(MAX_Z, NormalDist().inv_cdf(1.0 - per_pair / 2.0))


def wilson_bounds(successes: int, trials: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval: the interval that behaves at small n and p at 0 or 1.

    The normal approximation ("plus or minus 1.96 standard deviations") collapses to a
    zero-width interval when every session hit or none did, which at n=6 is common —
    and a zero-width
    interval is how a diary of six entries gets to print a confident claim.
    """
    if trials <= 0:
        return 0.0, 0.0
    phat = successes / trials
    z2 = z * z
    scale = 1.0 + z2 / trials
    centre = (phat + z2 / (2.0 * trials)) / scale
    half = (
        z
        * math.sqrt(phat * (1.0 - phat) / trials + z2 / (4.0 * trials * trials))
        / scale
    )
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True)
class Window:
    label: str
    min_hours: float
    max_hours: float

    @property
    def seconds(self) -> tuple[int, int]:
        return int(self.min_hours * 3600), int(self.max_hours * 3600)

    def as_dict(self) -> dict[str, object]:
        return {"label": self.label, "min_hours": self.min_hours, "max_hours": self.max_hours}


@dataclass(frozen=True)
class Finding:
    """Everything the card prints, and nothing it does not print.

    The Wilson bounds are here because the caller ranks and gates on them, not
    because they belong on screen: the UI shows counts, the baseline next to the
    finding, and one fixed verdict word (docs/INSIGHTS_PLAN.md §2.2).
    """

    exposure_kind: str
    exposure_id: str
    exposure_name: str
    symptom_id: str
    symptom_name: str
    sessions: int
    hits: int
    control_windows: int
    control_hits: int
    p_exposed: float
    p_baseline: float
    relative_risk: float | None
    exposed_low: float
    exposed_high: float
    baseline_low: float
    baseline_high: float
    verdict: str
    gate: str  # "" when a verdict was reached
    avg_severity: float | None
    default_severity_hits: int

    def as_dict(self) -> dict[str, object]:
        return {
            "exposure_kind": self.exposure_kind,
            "exposure_id": self.exposure_id,
            "exposure_name": self.exposure_name,
            "symptom_id": self.symptom_id,
            "symptom_name": self.symptom_name,
            "sessions": self.sessions,
            "hits": self.hits,
            "control_windows": self.control_windows,
            "control_hits": self.control_hits,
            "rate_exposed": round(self.p_exposed, 3),
            "rate_baseline": round(self.p_baseline, 3),
            "relative_risk": round(self.relative_risk, 2)
            if self.relative_risk is not None
            else None,
            "verdict": self.verdict,
            "gate": self.gate,
            "avg_severity": self.avg_severity,
            "default_severity_hits": self.default_severity_hits,
        }


@dataclass(frozen=True)
class Analysis:
    """Findings plus the honesty fields around them: what was examined to get here."""

    window: Window
    findings: list[Finding]
    pairs_examined: int
    eligible_exposures: int
    eligible_symptoms: int
    skipped_sessions: int  # logged as "did not do it"; never an exposure
    days_covered: int

    def as_dict(self) -> dict[str, object]:
        return {
            "window": {
                "label": self.window.label,
                "min_hours": self.window.min_hours,
                "max_hours": self.window.max_hours,
            },
            "findings": [finding.as_dict() for finding in self.findings],
            "pairs_examined": self.pairs_examined,
            "pairs_shown": len(self.findings),
            "eligible_exposures": self.eligible_exposures,
            "eligible_symptoms": self.eligible_symptoms,
            "skipped_sessions": self.skipped_sessions,
            "days_covered": self.days_covered,
        }


def _contains(times: Sequence[int], start: int, end: int) -> bool:
    """Any sorted value inside [start, end]? Binary search, since this runs per window."""
    low, high = 0, len(times)
    while low < high:
        mid = (low + high) // 2
        if times[mid] < start:
            low = mid + 1
        else:
            high = mid
    return low < len(times) and times[low] <= end


def _control_windows(
    sessions: Sequence[Event],
    busy_days: set[int],
    window: Window,
    range_start: int,
    range_end: int,
) -> list[tuple[int, int]]:
    """Same hour-of-day, on days this exposure did not happen.

    For each session: the same clock time 1 to 3 days either side, skipping any day with a
    log
    of that same definition, and never the session's own day — a symptom at 21:00
    might be the session's own effect, so a window that can hold it is not a
    control. Windows are de-duplicated, because two sessions at the same hour
    offer the same control day twice.

    Every window must fit inside the range it was sampled from. Without that,
    windows past the end of the record are guaranteed misses and drag the
    baseline down, which manufactures exactly the finding this module is meant to
    refuse.
    """
    low_seconds, high_seconds = window.seconds
    placed: set[tuple[int, int]] = set()
    for session in sessions:
        local = session.local_seconds
        day = local // DAY_SECONDS
        second_of_day = local % DAY_SECONDS
        for offset in CONTROL_OFFSETS:
            control_day = day + offset
            if control_day in busy_days:
                continue
            base = control_day * DAY_SECONDS + second_of_day
            start, end = base + low_seconds, base + high_seconds
            if start < range_start or end > range_end:
                continue
            placed.add((start, end))
    return sorted(placed)


def _pair(
    exposure_kind: str,
    exposure_id: str,
    exposure_name: str,
    symptom_id: str,
    symptom_name: str,
    sessions: Sequence[Event],
    symptom_times: Sequence[int],
    symptom_logs: Sequence[Event],
    window: Window,
    range_start: int,
    range_end: int,
    z: float = Z_95,
) -> Finding:
    """One (exposure, symptom) pair: counts, matched baseline, Wilson bounds, verdict."""
    busy_days = {event.local_seconds // DAY_SECONDS for event in sessions}
    hits = 0
    default_hits = 0
    severity_sum = 0
    severity_n = 0
    for session in sessions:
        local = session.local_seconds
        start = local + window.seconds[0]
        end = local + window.seconds[1]
        if _contains(symptom_times, start, end):
            hits += 1
            for log in symptom_logs:
                if start <= log.local_seconds <= end:
                    if log.severity is not None:
                        severity_sum += log.severity
                        severity_n += 1
                    if log.severity_default:
                        default_hits += 1

    controls = _control_windows(sessions, busy_days, window, range_start, range_end)
    control_hits = sum(1 for start, end in controls if _contains(symptom_times, start, end))

    sessions_n, controls_n = len(sessions), len(controls)
    exposed_low, exposed_high = wilson_bounds(hits, sessions_n, z)
    baseline_low, baseline_high = wilson_bounds(control_hits, controls_n, z)
    p_exposed = hits / sessions_n if sessions_n else 0.0
    p_baseline = control_hits / controls_n if controls_n else 0.0
    # The printed ratio compares rates; the verdict compares *intervals*, which is
    # the conservative version of the same question and the reason a pair of
    # six-entry anecdotes cannot win.
    # No ratio when there is nothing to compare against. Printing 99.0 or "∞" for
    # a zero baseline is how a small diary invents a huge effect.
    relative_risk = p_exposed / p_baseline if p_baseline > 0 else None
    gate = ""
    if sessions_n < MIN_SESSIONS:
        gate = GATE_SESSIONS
    elif hits < MIN_HITS:
        gate = GATE_HITS
    elif controls_n < MIN_SESSIONS:
        gate = GATE_WINDOWS
    if gate:
        verdict = TOO_RARE
    elif exposed_low > baseline_high:
        verdict = WORTH_A_LOOK
    elif exposed_high < baseline_low:
        verdict = NOTHING_FOUND
    else:
        verdict = LOOKS_LIKE_CHANCE

    return Finding(
        exposure_kind=exposure_kind,
        exposure_id=exposure_id,
        exposure_name=exposure_name,
        symptom_id=symptom_id,
        symptom_name=symptom_name,
        sessions=sessions_n,
        hits=hits,
        control_windows=controls_n,
        control_hits=control_hits,
        p_exposed=p_exposed,
        p_baseline=p_baseline,
        relative_risk=relative_risk,
        exposed_low=exposed_low,
        exposed_high=exposed_high,
        baseline_low=baseline_low,
        baseline_high=baseline_high,
        verdict=verdict,
        gate=gate,
        avg_severity=round(severity_sum / severity_n, 1) if severity_n else None,
        default_severity_hits=default_hits,
    )


def analyse(
    events: Sequence[Event],
    *,
    window: Window,
    range_start: int,
    range_end: int,
    exposure_kinds: Sequence[str] = ("exercise", "context"),
    min_logs: int = MIN_LOGS_PER_DEFINITION,
    limit: int = MAX_FINDINGS,
) -> Analysis:
    """Every candidate pair in the range, then the handful worth printing.

    Candidates are definitions with at least `min_logs` logs on both sides. That
    is the multiplicity control: it is not the number of pairs that makes a diary
    invent patterns, it is the number of pairs *examined*, so the set of examined
    pairs is kept small by data quality rather than by picking a favourite.
    """
    symptoms: dict[str, list[Event]] = {}
    for event in events:
        if event.kind == "symptom":
            symptoms.setdefault(event.def_id, []).append(event)

    candidates: dict[tuple[str, str], list[Event]] = {}
    for kind in exposure_kinds:
        by_def: dict[str, list[Event]] = {}
        for event in exposures(list(events), kind):
            by_def.setdefault(event.def_id, []).append(event)
        for def_id, logs in by_def.items():
            if len(logs) >= min_logs:
                candidates[(kind, def_id)] = sorted(logs, key=lambda item: item.local_seconds)

    eligible_symptoms = {
        def_id: logs for def_id, logs in symptoms.items() if len(logs) >= min_logs
    }

    z = adjusted_z(len(candidates) * len(eligible_symptoms))
    findings: list[Finding] = []
    for (kind, exposure_id), sessions in candidates.items():
        for symptom_id, logs in eligible_symptoms.items():
            symptom_times = sorted(log.local_seconds for log in logs)
            findings.append(
                _pair(
                    exposure_kind=kind,
                    exposure_id=exposure_id,
                    exposure_name=sessions[0].name,
                    symptom_id=symptom_id,
                    symptom_name=logs[0].name,
                    sessions=sessions,
                    symptom_times=symptom_times,
                    symptom_logs=logs,
                    window=window,
                    range_start=range_start,
                    range_end=range_end,
                    z=z,
                )
            )

    # Ranked by the conservative margin, not the point estimate: a chance pair at
    # a dense logging rate has a lower bound sitting near its baseline, so it
    # sorts itself to the bottom instead of needing a p-value to remove it.
    findings.sort(key=lambda item: (item.exposed_low - item.baseline_high, item.hits), reverse=True)
    shown = [item for item in findings if item.verdict != TOO_RARE][:limit]

    return Analysis(
        window=window,
        findings=shown,
        pairs_examined=len(candidates) * len(eligible_symptoms),
        eligible_exposures=len(candidates),
        eligible_symptoms=len(eligible_symptoms),
        skipped_sessions=sum(1 for event in events if event.is_skipped_session),
        days_covered=len({event.local_seconds // DAY_SECONDS for event in events}),
    )
