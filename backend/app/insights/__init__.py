"""Insights: the maths behind what the app is allowed to claim.

Split so the parts that decide *what to print* are pure Python with no FastAPI,
no SQL and no clock: they can be unit-tested, and a null can be *asserted* —
that random data produces no findings. That assertion is the reason this package
exists; the query it replaced printed 374 findings out of 400 candidate pairs on
independent random logs (see docs/INSIGHTS_PLAN.md §1.1).

* `events.py`      — one query per range, all of a user's logs as typed events
* `association.py` — session windows, matched baselines, Wilson bounds, verdicts
* `rollup.py`      — gap-filled daily/weekly series with adherence
* `sufficiency.py` — the coverage gate every card shares
"""

from __future__ import annotations

from .association import (
    Analysis,
    Finding,
    Window,
    analyse,
    wilson_bounds,
)
from .events import Event, exposures, load_events
from .rollup import DailyPoint, series
from .sufficiency import Coverage, coverage

__all__ = [
    "Analysis",
    "Coverage",
    "DailyPoint",
    "Event",
    "Finding",
    "Window",
    "analyse",
    "coverage",
    "exposures",
    "load_events",
    "series",
    "wilson_bounds",
]
