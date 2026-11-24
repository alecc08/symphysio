"""Seeding a new account, plus the suggestion pool for the Settings typeahead.

The actual preset sets live in `app/profiles.py`: an account picks one at sign-up
(or `none` to start empty) and `seed_catalog` writes it out as ordinary definition
rows. The postnatal set is still the one the module re-exports as `EXERCISES` /
`SYMPTOMS` / `CONTEXTS`, because that set is also what the suggestion pool is
built around — the app's primary use is the postnatal window.

Nothing here is prescriptive or medical advice — every preset can be renamed,
reordered or removed in Settings, and new ones can be typed in.
"""

from __future__ import annotations

from typing import Any

from .db import Database
from .ids import new_id
from .profiles import DEFAULT_PROFILE, POSTNATAL_PELVIC, PROFILES

# Re-exported from the postnatal profile so the rest of this module (and the
# suggestion pool) can talk about "the usual set" without repeating it.
EXERCISES = POSTNATAL_PELVIC.exercises
SYMPTOMS = POSTNATAL_PELVIC.symptoms
CONTEXTS = POSTNATAL_PELVIC.contexts

# Suggestion pool: offered in Settings -> "Suggested presets", never auto-added.
# exercises: name, body_region, sets, reps, sec;  symptoms: name, region;
# contexts: (category, name)
SUGGESTED_EXERCISES: tuple[tuple[str, str, int | None, int | None, int | None], ...] = (
    ("Ankle Pumps", "ankles", 2, 15, None),
    ("Hip Flexor Stretch", "hip_flexors", 2, None, 30),
    ("Piriformis Stretch", "hips", 2, None, 30),
    ("Supine Marching", "core", 2, 10, None),
    ("Dead Bug (Modified)", "core", 2, 8, None),
    ("Bridge Marching", "hips", 2, 10, None),
    ("Side Plank (Knees)", "obliques", 2, None, 20),
    ("Suitcase Carry (Light)", "obliques", 2, None, 40),
    ("Half-Kneeling Chop", "core", 2, 8, None),
    ("Deep Squat Hold", "pelvic_floor", 2, None, 30),
    ("Calf Raise", "ankles", 3, 15, None),
    ("Shoulder Rolls", "upper_back", 2, 10, None),
    ("Nursing Posture Stretch", "neck", 2, None, 30),
    ("Stair Step-Ups", "hips", 2, 10, None),
)

SUGGESTED_SYMPTOMS: tuple[tuple[str, str], ...] = (
    ("Postpartum Bleeding", "lower_belly"),
    ("Pressure / Bulge", "pelvic_floor"),
    ("Incomplete Bladder Emptying", "bladder"),
    ("Constipation", "bowel"),
    ("Hemorrhoid Pain", "bowel"),
    ("Numbness / Tingling", "perineum"),
    ("Neck & Shoulder Pain", "neck"),
    ("Wrist & Thumb Pain", "wrist"),
    ("Knee Pain", "knee"),
    ("Headache", "head"),
    ("Fatigue", "whole_body"),
    ("Breastfeeding Discomfort", "chest"),
    ("Swelling", "legs"),
    ("Hip Pinching", "hips"),
)

SUGGESTED_CONTEXTS: tuple[tuple[str, str], ...] = (
    ("relief", "Paracetamol"),
    ("relief", "Warm Shower"),
    ("relief", "Support Wear"),
    ("relief", "Nursing Pillow"),
    ("relief", "Fibre"),
    ("relief", "Hydration"),
    ("relief", "Massage"),
    ("relief", "Perineal Spray"),
    ("trigger", "Car Seat Lifting"),
    ("trigger", "Climbing Stairs"),
    ("trigger", "Long Driving"),
    ("trigger", "Feeding Posture"),
    ("trigger", "Return to Exercise Too Soon"),
    ("trigger", "Twin / Multiples Load"),
)


async def seed_catalog(db: Database, user_id: str, profile_key: str = DEFAULT_PROFILE) -> int:
    """Write the chosen profile's presets as ordinary definition rows.

    Returns how many rows were created, which is 0 for `none` — a valid choice,
    not an error. Every row records the profile that seeded it, so Settings can
    later say "restore my set" without guessing.
    """
    profile = PROFILES.get(profile_key) or PROFILES[DEFAULT_PROFILE]
    await db.executemany(
        "INSERT INTO exercise_definitions"
        " (id, user_id, name, body_region, default_sets, default_reps, default_sec, sort_order,"
        "  profile_key)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, name, region, sets, reps, sec, index, profile.key)
            for index, (name, region, sets, reps, sec) in enumerate(profile.exercises)
        ],
    )
    await db.executemany(
        "INSERT INTO symptom_definitions (id, user_id, name, default_region, sort_order,"
        " profile_key)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, name, region, index, profile.key)
            for index, (name, region) in enumerate(profile.symptoms)
        ],
    )
    await db.executemany(
        "INSERT INTO context_definitions (id, user_id, category, name, sort_order, profile_key)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, category, name, index, profile.key)
            for index, (category, name) in enumerate(profile.contexts)
        ],
    )
    return len(profile.exercises) + len(profile.symptoms) + len(profile.contexts)


def suggestions(kind: str, existing_names: set[str]) -> list[dict[str, Any]]:
    """Preset ideas the user does not already have (case-insensitive match).

    Each row is shaped exactly like that kind's create model, so the client can
    POST it back unchanged — the models are `extra="forbid"`, so mixing fields
    between kinds would be rejected.
    """
    taken = {name.casefold() for name in existing_names}
    if kind == "exercises":
        return [
            {
                "name": name,
                "body_region": region,
                "default_sets": sets,
                "default_reps": reps,
                "default_sec": sec,
            }
            for name, region, sets, reps, sec in SUGGESTED_EXERCISES
            if name.casefold() not in taken
        ]
    if kind == "symptoms":
        return [
            {"name": name, "default_region": region}
            for name, region in SUGGESTED_SYMPTOMS
            if name.casefold() not in taken
        ]
    return [
        {"name": name, "category": category}
        for category, name in SUGGESTED_CONTEXTS
        if name.casefold() not in taken
    ]
