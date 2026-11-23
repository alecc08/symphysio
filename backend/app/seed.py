"""Default catalogs plus a suggestion pool.

The app's primary use is the postnatal window: pelvic floor symptoms and the
physio that rebuilds it. Seed defaults are therefore postnatal-oriented, and
`SUGGESTIONS` holds the longer list of things people commonly want to add later
(heaviness variants, feeding-posture aches, carry-and-lift triggers...).

Nothing here is prescriptive or medical advice — every preset can be renamed,
reordered or removed in Settings, and new ones can be typed in.
"""

from __future__ import annotations

from typing import Any

from .db import Database
from .ids import new_id

# Seeded at signup: name, body_region, default_sets, default_reps, default_sec
EXERCISES: tuple[tuple[str, str, int | None, int | None, int | None], ...] = (
    ("Pelvic Floor Lifts", "pelvic_floor", 3, 10, 5),
    ("Pelvic Floor Release", "pelvic_floor", 2, 10, 5),
    ("Deep Core Draw-In", "lower_belly", 3, 10, None),
    ("Diaphragm Breathing", "ribcage", 2, None, 60),
    ("Glute Bridge", "hips", 3, 12, None),
    ("Clamshell", "hips", 3, 12, None),
    ("Bird Dog", "core", 2, 8, None),
    ("Supported Squat", "pelvic_floor", 2, 8, None),
    ("Hamstring Stretch", "hamstrings", 3, None, 30),
    ("Wall Angels", "upper_back", 2, 10, None),
)

# Seeded at signup: name, default_region
SYMPTOMS: tuple[tuple[str, str], ...] = (
    ("Heaviness / Dragging", "pelvic_floor"),
    ("Urine Leak", "pelvic_floor"),
    ("Urgency", "bladder"),
    ("Gas or Bowel Leak", "bowel"),
    ("Perineal Pain", "perineum"),
    ("Scar Pain", "c_section_scar"),
    ("Pelvic Girdle Pain", "si_joint"),
    ("Low Back Pain", "lower_back"),
    ("Pain with Sex", "pelvic_floor"),
    ("Belly Domining", "lower_belly"),
)

# Seeded at signup: category, name
CONTEXTS: tuple[tuple[str, str], ...] = (
    ("relief", "Ice Pack"),
    ("relief", "Heat Pack"),
    ("relief", "Sitz Bath"),
    ("relief", "Rest"),
    ("relief", "Ibuprofen"),
    ("relief", "Stool Softener"),
    ("relief", "Pelvic Floor PT"),
    ("relief", "Belly Support"),
    ("trigger", "Heavy Lifting"),
    ("trigger", "Cough or Sneeze"),
    ("trigger", "Long Standing"),
    ("trigger", "Long Sitting"),
    ("trigger", "Straining"),
    ("trigger", "High-Impact Exercise"),
    ("trigger", "Poor Sleep"),
    ("trigger", "Carrying Baby"),
)

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


async def seed_catalog(db: Database, user_id: str) -> None:
    await db.executemany(
        "INSERT INTO exercise_definitions"
        " (id, user_id, name, body_region, default_sets, default_reps, default_sec, sort_order)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, name, region, sets, reps, sec, index)
            for index, (name, region, sets, reps, sec) in enumerate(EXERCISES)
        ],
    )
    await db.executemany(
        "INSERT INTO symptom_definitions (id, user_id, name, default_region, sort_order)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, name, region, index)
            for index, (name, region) in enumerate(SYMPTOMS)
        ],
    )
    await db.executemany(
        "INSERT INTO context_definitions (id, user_id, category, name, sort_order)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (new_id(), user_id, category, name, index)
            for index, (category, name) in enumerate(CONTEXTS)
        ],
    )


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
