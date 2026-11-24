"""Tracking profiles: the preset sets offered when an account is created.

Each profile is a starting catalogue (physio presets, symptom presets, relief and
trigger presets) plus the lag windows that make sense for it. Two decisions are
baked in here and worth stating, because they are the ones that could be
undone badly later:

* **A profile is a seed, not a cage.** Everything it creates is an ordinary
  definition row: renameable, archivable, deletable. `profile_key` on a
  definition records where a row came from and nothing else — no behaviour keys
  off it.
* **The windows belong to the profile.** A urine leak after a cough is a
  minutes-scale signal; delayed soreness after a loading session is 24-72 h. One
  global default hides the pattern for most of the profiles, and a wrong window
  is the quietest way to lose a real one.

The list is deliberately short. Five sets is what can be kept honest by one
maintainer; a wrong preset set is worse than an empty diary, which is why `none`
("start empty") is a first-class choice and the one the sign-up screen selects.
"""

from __future__ import annotations

from dataclasses import dataclass

# (name, body_region, default_sets, default_reps, default_sec)
ExerciseRow = tuple[str, str, int | None, int | None, int | None]
# (name, default_region)
SymptomRow = tuple[str, str]
# (category, name)
ContextRow = tuple[str, str]
# (label, min_hours, max_hours)
WindowRow = tuple[str, float, float]

DEFAULT_WINDOWS: tuple[WindowRow, ...] = (
    ("0-2 h", 0.0, 2.0),
    ("1-6 h", 1.0, 6.0),
    ("6-48 h", 6.0, 48.0),
)


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    blurb: str
    exercises: tuple[ExerciseRow, ...] = ()
    symptoms: tuple[SymptomRow, ...] = ()
    contexts: tuple[ContextRow, ...] = ()
    windows: tuple[WindowRow, ...] = DEFAULT_WINDOWS
    default_window: str = "1-6 h"

    @property
    def counts(self) -> dict[str, int]:
        return {
            "exercises": len(self.exercises),
            "symptoms": len(self.symptoms),
            "relief": sum(1 for category, _ in self.contexts if category == "relief"),
            "triggers": sum(1 for category, _ in self.contexts if category == "trigger"),
        }


POSTNATAL_PELVIC = Profile(
    key="postnatal_pelvic",
    label="Pelvic health after childbirth",
    blurb=(
        "Heaviness, leakage, scar and girdle pain, and the physio that rebuilds "
        "the pelvic floor. What this app was written for."
    ),
    exercises=(
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
    ),
    symptoms=(
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
    ),
    contexts=(
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
    ),
)

# Same anatomy, no birth context: menopause, running, prostatectomy recovery,
# chronic urgency. The windows are minutes-scale, because "leak within an hour of
# the coffee" is a different signal from "sore the next day".
BLADDER_BOWEL = Profile(
    key="bladder_bowel",
    label="Leakage, urgency and bowel control",
    blurb=(
        "Bladder and bowel symptoms without a recent birth - after menopause, "
        "running, prostate surgery, or urgency that just arrived."
    ),
    windows=(
        ("0-1 h", 0.0, 1.0),
        ("1-6 h", 1.0, 6.0),
        ("6-24 h", 6.0, 24.0),
    ),
    default_window="0-1 h",
    exercises=(
        ("Pelvic Floor Lifts", "pelvic_floor", 3, 10, 5),
        ("Long Hold Contractions", "pelvic_floor", 3, 5, 10),
        ("Rapid Flicks", "pelvic_floor", 3, 10, 1),
        ("Urge Suppression", "bladder", 3, 5, 60),
        ("Diaphragm Breathing", "ribcage", 2, None, 60),
        ("Timed Voiding Routine", "bladder", None, None, None),
        ("Fluid Timing", "bladder", None, None, None),
        ("Supported Squat", "pelvic_floor", 2, 8, None),
        ("Hip Flexor Stretch", "hip_flexors", 2, None, 30),
        ("Bowel Posture Reset", "bowel", 2, 5, 30),
    ),
    symptoms=(
        ("Urine Leak", "bladder"),
        ("Urgency", "bladder"),
        ("Frequency", "bladder"),
        ("Night Urination", "bladder"),
        ("Incomplete Emptying", "bladder"),
        ("Gas or Bowel Leak", "bowel"),
        ("Constipation", "bowel"),
        ("Straining", "bowel"),
        ("Leak Before Reaching the Toilet", "bladder"),
        ("Pressure / Bulge", "pelvic_floor"),
    ),
    contexts=(
        ("relief", "Pad or Guard"),
        ("relief", "Timed Voiding"),
        ("relief", "Fibre"),
        ("relief", "Hydration"),
        ("relief", "Stool Softener"),
        ("relief", "Pelvic Floor PT"),
        ("relief", "Warm Bath"),
        ("relief", "Bladder Diary"),
        ("trigger", "Cough or Sneeze"),
        ("trigger", "Laughing"),
        ("trigger", "Running or Jumping"),
        ("trigger", "Heavy Lifting"),
        ("trigger", "Caffeine"),
        ("trigger", "Fluids Before Bed"),
        ("trigger", "Alcohol"),
        ("trigger", "Long Driving"),
    ),
)

LOW_BACK_GIRDLE = Profile(
    key="low_back_girdle",
    label="Low back, SI and pelvic girdle pain",
    blurb=(
        "Back and pelvic-ring pain, with the load and posture events that set it "
        "off and the positions that settle it."
    ),
    windows=(
        ("0-2 h", 0.0, 2.0),
        ("1-12 h", 1.0, 12.0),
        ("12-48 h", 12.0, 48.0),
    ),
    default_window="1-12 h",
    exercises=(
        ("Pelvic Tilt", "pelvic_floor", 3, 10, 5),
        ("Cat-Camel", "spine", 2, 10, None),
        ("Bird Dog", "core", 3, 8, None),
        ("Glute Bridge", "hips", 3, 12, None),
        ("Side Plank (Knees)", "obliques", 2, None, 20),
        ("Hip Hinge Practice", "hips", 3, 10, None),
        ("Deep Core Draw-In", "lower_belly", 3, 10, None),
        ("Walking Interval", "whole_body", 1, None, 900),
        ("Piriformis Stretch", "hips", 3, None, 30),
        ("Hip Flexor Stretch", "hip_flexors", 3, None, 30),
    ),
    symptoms=(
        ("Low Back Pain", "lower_back"),
        ("SI / Girdle Pain", "si_joint"),
        ("Buttock Pain", "hips"),
        ("Leg Numbness or Tingling", "leg"),
        ("Morning Stiffness", "lower_back"),
        ("Spasm", "lower_back"),
        ("Numb Thigh", "leg"),
        ("Pain Rolling Over in Bed", "si_joint"),
        ("Pain Standing on One Leg", "hips"),
        ("Soreness After Standing", "lower_back"),
    ),
    contexts=(
        ("relief", "Heat Pack"),
        ("relief", "Ice Pack"),
        ("relief", "Walking"),
        ("relief", "Position Change"),
        ("relief", "Support Belt"),
        ("relief", "Ibuprofen"),
        ("relief", "Massage"),
        ("relief", "Pelvic Floor PT"),
        ("trigger", "Long Sitting"),
        ("trigger", "Long Standing"),
        ("trigger", "Bending and Lifting"),
        ("trigger", "Carrying on One Side"),
        ("trigger", "Driving"),
        ("trigger", "Poor Sleep"),
        ("trigger", "Climbing Stairs"),
        ("trigger", "Doing Too Much Too Soon"),
    ),
)

SHOULDER_NECK = Profile(
    key="shoulder_neck",
    label="Shoulder, neck and carrying posture",
    blurb=(
        "Shoulder and neck pain - feeding posture, one-side carrying, desk "
        "hours - and the small strength work that holds the shoulder blade."
    ),
    windows=(
        ("0-3 h", 0.0, 3.0),
        ("3-24 h", 3.0, 24.0),
        ("24-72 h", 24.0, 72.0),
    ),
    default_window="3-24 h",
    exercises=(
        ("Wall Angels", "upper_back", 2, 10, None),
        ("Scapular Squeeze", "shoulder", 3, 10, 5),
        ("Doorway Pec Stretch", "chest", 3, None, 30),
        ("External Rotation", "shoulder", 3, 12, None),
        ("Chin Tuck", "neck", 3, 10, 5),
        ("Serratus Wall Slide", "shoulder", 2, 10, None),
        ("Band Row", "upper_back", 3, 12, None),
        ("Trapezius Stretch", "neck", 3, None, 30),
        ("Thoracic Extension over Roll", "spine", 2, 10, None),
        ("Shoulder Blade Setting", "shoulder", 2, 10, 10),
    ),
    symptoms=(
        ("Shoulder Pain", "shoulder"),
        ("Neck Stiffness", "neck"),
        ("Trapezius Ache", "neck"),
        ("Headache", "head"),
        ("Numbness or Tingling in the Arm", "arm"),
        ("Pain Lifting the Arm", "shoulder"),
        ("Night Pain Lying on the Side", "shoulder"),
        ("Pinching Reaching Up", "shoulder"),
        ("Upper Back Soreness", "upper_back"),
        ("Weak Grip Feeling", "arm"),
    ),
    contexts=(
        ("relief", "Heat Pack"),
        ("relief", "Ice Pack"),
        ("relief", "Massage"),
        ("relief", "Posture Break"),
        ("relief", "Pillow Support"),
        ("relief", "Ibuprofen"),
        ("relief", "Manual Therapy"),
        ("relief", "Rest from Overhead"),
        ("trigger", "Feeding Posture"),
        ("trigger", "Looking Down at the Phone"),
        ("trigger", "Carrying on One Side"),
        ("trigger", "Reaching Overhead"),
        ("trigger", "Long Desk Session"),
        ("trigger", "Sleeping Position"),
        ("trigger", "Carrying the Car Seat"),
        ("trigger", "Cold Weather"),
    ),
)

HIP_KNEE = Profile(
    key="hip_knee",
    label="Hip, knee and returning to running",
    blurb=(
        "Load management for hip and knee pain: what you ran or lifted, how it "
        "reacted, and when the reaction came."
    ),
    windows=(
        ("0-24 h", 0.0, 24.0),
        ("24-72 h", 24.0, 72.0),
        ("0-2 h", 0.0, 2.0),
    ),
    default_window="0-24 h",
    exercises=(
        ("Clamshell", "hips", 3, 12, None),
        ("Side Plank (Knees)", "obliques", 2, None, 20),
        ("Step-Down Control", "knee", 3, 10, None),
        ("Single-Leg Press", "hips", 3, 10, None),
        ("Calf Raise", "ankles", 3, 15, None),
        ("Hip Hinge Practice", "hips", 3, 10, None),
        ("Bridge Marching", "hips", 2, 10, None),
        ("Half Squat", "knee", 2, 12, None),
        ("Easy Cycling", "whole_body", 1, None, 1200),
        ("Adductor Squeeze", "hips", 3, 12, 5),
    ),
    symptoms=(
        ("Hip Pinching", "hips"),
        ("Outer Hip Pain", "hips"),
        ("Knee Pain", "knee"),
        ("Kneecap Pain on Stairs", "knee"),
        ("IT Band Pain", "leg"),
        ("Tendon Pain", "hips"),
        ("Swelling", "knee"),
        ("Stiffness After Rest", "hips"),
        ("Giving-Way Feeling", "knee"),
        ("Pain After Running", "leg"),
    ),
    contexts=(
        ("relief", "Ice Pack"),
        ("relief", "Foam Roll"),
        ("relief", "Load Reduction"),
        ("relief", "Cycling Instead"),
        ("relief", "Ibuprofen"),
        ("relief", "Manual Therapy"),
        ("relief", "Extra Sleep"),
        ("relief", "Supportive Footwear"),
        ("trigger", "Running Distance"),
        ("trigger", "Running Speed"),
        ("trigger", "Hills"),
        ("trigger", "Stairs"),
        ("trigger", "Long Standing"),
        ("trigger", "Sitting Long"),
        ("trigger", "Skipped Rest Day"),
        ("trigger", "New Footwear"),
    ),
)


PROFILES: dict[str, Profile] = {
    # "Start empty" first: it is what the sign-up screen selects.
    "none": Profile(
        key="none",
        label="Start empty",
        blurb="No presets. Add your own, or tap a suggestion while you type.",
    ),
    "postnatal_pelvic": POSTNATAL_PELVIC,
    "bladder_bowel": BLADDER_BOWEL,
    "low_back_girdle": LOW_BACK_GIRDLE,
    "shoulder_neck": SHOULDER_NECK,
    "hip_knee": HIP_KNEE,
}

# What an old client gets when it sends no profile at all. The SPA always sends
# one, so this only matters to scripts and to clients predating the feature.
DEFAULT_PROFILE = "postnatal_pelvic"


def get_profile(key: str) -> Profile | None:
    return PROFILES.get(key)


def windows_for(key: str) -> tuple[WindowRow, ...]:
    profile = PROFILES.get(key)
    return profile.windows if profile else DEFAULT_WINDOWS
