# Phase 3 — Insights you can trust, and the presets that feed them

**Status: proposed, not built.** Plan for the last phase of
[REQUIREMENTS.md](../REQUIREMENTS.md) §9 ("Insights & Polish"), plus the
preset-profile request from 2026-11-24 (pick a tracking profile at sign-up).

Written as a plan and not a feature list because the interesting work is *what
the numbers are allowed to claim*: one of the three panels we already ship turns
out to be a noise generator (§1.1). Decisions are recorded in §10.

## 0. What the phase is for

The promise is "click and log, then see what actually correlates". Logging is
done. Making the *seeing* part true needs three things at once:

1. **Data rich enough to answer the question.** Several columns the analytics
   need already exist but the UI never fills them, and the drawer writes a number
   the user never chose.
2. **Maths that separates signal from chance.** Today it does not — §1.1.
3. **A UI that says when it does not know.** Sparse data is the normal state of a
   diary, not an edge case. "A chart that lies is worse than no chart" is already
   a written rule in [DATABASE.md](DATABASE.md); this phase makes it testable.

Every insight this phase adds must clear three gates:

| Gate | Question it answers |
| --- | --- |
| **Chance** | does this happen more often than this person's base rate? |
| **Coverage** | do enough entries exist, and could the *logging rate* alone explain the change? |
| **Recoverability** | can the user open the exact rows the claim is built from? |

An insight that fails the chance or coverage gate renders **nothing** — not a
dimmer number, not a greyed-out chart. §6 is how the rows get opened.

## 1. What exists today

`GET /analytics/summary` (totals, per-day buckets, top-10, streak),
`GET /analytics/lag-correlations` (exercise→symptom range join),
`GET /analytics/time-of-day`. Four UI cards read them. The SQL and the copy have
these problems:

### 1.1 The lag panel prints noise, and it is measurable

`LAG_SQL` (`backend/app/routers/analytics.py:181`) is a bare range join with
`HAVING COUNT(sl.id) >= 3`, ordered by that raw count. There is no comparison to
what the same window catches by accident. Measured — same join, same schema,
data generated as two **independent** processes (exercise timing tells you
nothing about symptom timing), 60 days, 4 exercises × 5 symptoms, 20 seeds:

| density | pairs printed as "findings" | join inflation |
| --- | --- | --- |
| 2.5 exercise + 3 symptom logs/day (today's shape) | **374 of 400** | +2 % |
| 8 + 8 logs/day (a diary someone actually uses) | **400 of 400** | **+50 %** |

At the dense rate one pair accumulates **88** coincidental exercise→symptom pairs
inside a 1–12 h window by chance alone. So `min_count >= 3` is not a significance
bar, it is a density bar: it filters out *sparse*, never *chance*. Reproducer:
`~/scratch/symphysio-plan/probe.py`, to be checked in as
`scripts/probes/lag_null.py` with the null assertion as a test (§8).

The same card also **double counts**: `COUNT(sl.id)` counts one symptom log once
per preceding exercise session, which is where the +50 % comes from. A human
reading "appeared 6× within 1–6 h of Wall Angels" means 6 distinct episodes.

### 1.2 Where the data is thin, and where the charts already lie

| # | Problem | Where | Why it matters for insights |
| --- | --- | --- | --- |
| 1 | The drawer writes **severity 5** when the user never tapped a number | `QuickSheet.tsx:161` `const value = severity ?? 5` | every average severity is contaminated by a value nobody chose; the scale's own word for 5 is "bothersome" |
| 2 | Exercise **dose is never entered**: `sets_done`/`reps_done`/`duration_sec` come from the definition's defaults | `logs.py:154-156`, `QuickSheet.tsx:146-159` | "did the flare follow the hard session or the light one" is unanswerable, and a session you skipped looks identical to one you did |
| 3 | Symptom `duration_min` and `body_region` are optional and unused in real data | prod DB: 0 of 4 symptom logs have a duration; region comes only from the definition default | episode-length is the difference between a twinge and a flare |
| 4 | `note` only exists in the History **edit** drawer, never at log time | `HistoryPage.tsx` `EditSheet` | the free text that explains a flare is written hours later or never |
| 5 | Charts **drop empty days** instead of showing them | `analytics.py:_daily` returns only days with rows; `Charts.tsx` `days.slice(-14)` is the last 14 *logging* days, while the card says "last 14 days" | a 30-day range with 11 logging days draws 11 bars with no gaps; improvement that is really "I stopped logging" looks like recovery |
| 6 | The cards use **different windows** without saying so | `InsightsPage.tsx:41-42` asks for lag/time-of-day at `max(days, 90)` while summary uses `days` | "30d" header above a table computed over 90 days |
| 7 | Only one direction is computed: exercise → symptom | `LAG_SQL` | the actual pelvic-floor question is *trigger → symptom within minutes*, and the second is *did the thing I took help* |
| 8 | Nothing per symptom | every card is an aggregate over all symptoms | averaging a healing perineal pain with a worsening girdle pain gives a flat line that means nothing |
| 9 | No baseline / period comparison | `summary.totals` | "am I better than last month" is the first question of a rehab diary |
| 10 | No **plan-change / appointment** event | schema | PT visits and "she changed the programme" are exactly the moments a trend should step, and they are unrecorded |
| 11 | Recalled entries are not distinguished | `logged_at_utc` exists but no view uses it | a diary filled in on Sunday for the week is weaker evidence and should be marked |
| 12 | The streak's local-day frame reads only `exercise_logs` | `analytics.py:_latest_offset` | an account that logs only symptoms computes the streak in UTC — the same bug class as 0.1.2's streak fix |

---

## 2. The maths, decided once

### 2.1 Unit of analysis: the session-window, not the pair

For a definition pair (X = an exercise or trigger, S = a symptom) and a window
`W = [min_h, max_h]`:

- **exposed**: each X log is a *session*. It is a *hit* if ≥1 S log lands in
  `[t + min, t + max]`. `p_exposed = hits / sessions`.
- **baseline**: *control windows* — every 24 h day in the range contributes one
  window placed at the same local hour as the session, in a day with no X log,
  plus windows placed at random offsets ≥ `max_h` away from any X log. Same
  length, same hour-of-day distribution, so time-of-day (which is a real effect
  in this app — `time-of-day` exists) cannot fake a lag.
- **statistic**: `relative_risk = p_exposed / p_baseline`, and the **Wilson 95 %
  lower bound** of `p_exposed`, floored against `p_baseline`.

Implementation shape (pure functions, no FastAPI, so they are unit-testable and
so a null can be asserted):

```
backend/app/insights/__init__.py
                 events.py      # one query, all logs of one user in a range, as typed events
                 association.py # windows, hits, Wilson bounds, verdicts. no SQL, no dates-from-clock
                 rollup.py      # daily/weekly series, gap-filled, adherence-aware
                 sufficiency.py # the coverage gate, shared by every card
```

Raw SQL stays in `analytics.py`-style modules; the interpretation is Python, not
SQL, because the ranking rule (§2.3) is not something to write in a `HAVING`.

### 2.2 Print three numbers, never one

> **Heaviness / Dragging** followed **9 of 24** Pelvic Floor Lift sessions within
> 1–6 h. On comparable days with no lifts, **2 of 19**. *Likely worth a look.*
> <sub>based on 33 entries · open the rows</sub>

- counts, not percentages alone — small N must *look* small;
- the baseline is always printed next to the finding;
- verdict vocabulary is fixed and non-medical: `worth a look` (lower bound > 1),
  `looks like chance` (interval crosses 1), `seen too rarely to tell` (gate
  failed → nothing renders, replaced by the sufficiency line), `nothing found`
  (enough data, interval at or below 1 — this is a *good* result and must be
  showable, because "the squat is not the problem" is an insight).

### 2.3 Guardrails

- **Minimums, per profile**: ≥ 5 exposed sessions and ≥ 3 hits before a pair is
  eligible at all. Below that the card shows the sufficiency line, not a bar.
- **Multiplicity**: candidate pairs are capped to definitions with ≥ 5 logs, the
  result set is sorted by the Wilson lower bound (the conservative number, not
  the point estimate), capped at 8, and the card states *"8 of 42 pairs
  examined"*. Ranking by the bound is what kills the noise: at the probe's dense
  rate a chance pair's bound sits at ~1. Textbook Bonferroni over 24 pairs asks
  for 99.79 % per pair, and at diary-sized n (7 of 8 against 0 of 17) that bound
  no longer separates anything — the card would be unfalsifiable. The per-pair
  level therefore has a floor of 1 % (`MIN_PER_PAIR_ALPHA`), a judgement call
  whose check is empirical rather than theoretical: with the floor in place
  `scripts/probes/lag_null.py` still finds **zero** claims on independent diaries
  at three densities, while the demo diary's strongest pair (7 of 8 against 0 of
  17) is finally allowed to say so. Without the floor that pair is refused by
  0.003 of interval — the honest description of strict Bonferroni at this n is
  "the card almost never answers".
- **Windows come from the profile** (§5.3), not from a hard-coded trio of chips.
- No p-values, no CI text, no "p < 0.05" anywhere in the UI: the bound exists to
  pick what is *worth printing*, not to be shown as statistics.

### 2.4 Explicitly not computed

p-values surfaced to the user; forecasting ("you'll flare tomorrow"); any
comparison against other users' data (there is no cross-user query in this app —
see SECURITY.md); anything phrased as diagnosis or advice. The app describes
this person's own diary and stops.

---

## 3. Schema — `migrations/003_profiles_and_plan.sql`

```sql
-- which tracking profile seeded this account; drives presets + default windows
ALTER TABLE users ADD COLUMN profile_key TEXT NOT NULL DEFAULT 'postnatal_pelvic';

-- which profile seeded a definition: makes "restore my set" and
-- "why is there a Clamshell in my shoulder diary?" answerable
ALTER TABLE exercise_definitions ADD COLUMN profile_key TEXT;
ALTER TABLE symptom_definitions  ADD COLUMN profile_key TEXT;
ALTER TABLE context_definitions  ADD COLUMN profile_key TEXT;

-- plan timeline: the moments that explain a step change
CREATE TABLE plan_events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN
                        ('appointment','programme_change','medication','goal','note')),
    text            TEXT NOT NULL,          -- "PT: stop breath-holding, add side plank"
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    created_at_utc  INTEGER NOT NULL
);
CREATE INDEX idx_plan_events_time ON plan_events(user_id, occurred_at_utc DESC);

-- severity 5 written by the drawer instead of chosen by the user: recorded, so it
-- can be shown and excluded. See §4.1 (decided 2026-11-24).
ALTER TABLE symptom_logs ADD COLUMN severity_default INTEGER NOT NULL DEFAULT 0;

-- window scans hit (user, definition, time) constantly
CREATE INDEX idx_sym_logs_def_time  ON symptom_logs(user_id, symptom_id, occurred_at_utc DESC);
CREATE INDEX idx_ctx_logs_def_time  ON context_logs(user_id, context_id, occurred_at_utc DESC);
```

Notes on what is deliberately **not** added:
- **No materialised daily rollup.** Row counts are thousands, not millions, and a
  rollup table is a second truth that can drift. Measure before adding (§8 has
  the probe); if `/summary` ever exceeds ~30 ms on a 2-year diary, add it then.
- **No `episode_id`.** Grouping logs into episodes is computed from `duration_min`
  + time order, and storing it would go stale on every edit.
- Migrations follow the repo rule: additive, idempotent-safe, never editing a
  released file.

---

## 4. Data capture — what has to change so the maths has something to eat

**4.1 The severity default has to be visible, not removed** *(decided
2026-11-24: keep the 5, make the default obvious)*. One-tap-anywhere stays — the
drawer's speed is the product. What changes is that the default stops pretending
to be a choice:

- the scale renders 5 with a **dashed outline and the word `default`** (not the
  filled selected style), and the row's right-hand label reads
  `not picked — 5 used`;
- the save toast says `Logged: Heaviness · 5/10 (default)`, so the moment it is
  written it is labelled;
- History and the edit drawer mark the entry with a `default` chip next to the
  number, one tap to change it;
- the DB records it: `symptom_logs.severity_default` (§3), which is the only way
  the label survives past the moment of logging. Insights then print it honestly —
  the sufficiency line gains `4 of 11 severities were the default` — and a
  severity trend card can offer a `only where you chose a number` toggle;
- the remembered-last-severity chip stays: it makes a repeat log one tap *and*
  recorded as chosen.

Existing rows are written as `0` by the migration; prod has 4 symptom logs and
they get checked by hand, so no backfill guess is made in code.

**4.2 Dose, only when it differs from the preset.** Preset tap = "as prescribed"
(the defaults already on the definition). An "adjust dose" row in the drawer's
existing optional-details section writes real `sets_done`/`reps_done`/
`duration_sec`. Additionally, a preset tap with **no** dose (skipped, did not get
to it) is a *missed session* — modelled as an exercise log with
`sets_done = 0` rather than a new table, so the plan-adherence card can count it
without special-casing.

**4.3 Duration at log time, one tap.** `DurationChips` already exist in the
symptom drawer; they stay, and the analytics use them to separate twinge from
flare (§2 windows per profile use duration when present).

**4.4 A note while it is happening.** One-line optional input in the drawer,
below the fold for symptoms. History's multi-line edit stays.

**4.5 `plan_events` entry points.** A one-line "add a note / appointment" in
Settings and a chip in the Physio drawer ("PT visit today"). It is the cheapest
way to get the step-change markers, and it doubles as the diary's narrative spine
in §6.

**4.6 Recalled entries are flagged, not punished.** An entry whose
`logged_at_utc - occurred_at_utc` exceeds 24 h is labelled *recalled* in the
timeline and counted in a coverage figure; the association maths keeps using it
(time accuracy is what matters, not the tap time) but the sufficiency line
reports the share of recalled entries so the user knows how firm a finding is.

---

## 5. Tracking profiles (the sign-up choice)

At registration the user picks what they are tracking; that choice seeds the
catalogue, sets the drawer copy, and sets the **default lag windows**. It is a
starting point, not a cage: every preset stays renameable/archivable, and
Settings can add another profile's presets later without touching history.

### 5.1 Where it lives

- `app/profiles.py` *(not `app/presets/` as first drafted — one module, no
  package, since it is a table and a dataclass)*: a registry
  `PROFILES: dict[key, Profile]` sitting beside the flat
  `seed.EXERCISES/SYMPTOMS/CONTEXTS`, which stays as the seed for accounts that
  predate the field. Each `Profile` carries `label`, `blurb`, the three preset
  lists, and `windows: [(label, min_hr, max_hr), ...]` plus `default_window`.
- `GET /catalog/profiles` → `{key, label, blurb, counts, windows, default_window}`
  — public, and the UI never hard-codes the list, same reasoning as `suggestions`.
- `POST /auth/register` gains `profile: str = "postnatal_pelvic"`, validated
  against the registry; an unknown key is a `422`, and omitting it keeps today's
  behaviour exactly (an old client still works). `"none"` seeds nothing.
- **The picker starts on "Start empty" (decided 2026-11-24)**: nobody gets a
  pelvic-floor diary by accident. The five sets sit beside it as one-tap cards,
  with `postnatal_pelvic` first and its blurb shown, and the empty state's hint
  line names the sets so the choice is discoverable rather than missed. The API
  default stays `postnatal_pelvic` for old clients; the SPA always sends an
  explicit `profile`, so the two never disagree in practice.
- The auth screen gains a horizontal picker of 6 cards **above** the email and
  password fields (one tap, no wizard, no extra step in the sign-up flow).
- `POST /catalog/{kind}/apply_profile` (a later PR): appends a profile's presets
  to an existing account, skipping names that already exist, never archiving
  anything.
- **Non-destructive rule**: changing profile never deletes or archives presets or
  logs. `profile_key` on definitions records origin only.

### 5.2 Why windows belong to the profile

A urine leak after a cough shows up in minutes; delayed soreness after a loading
session shows up 24–48 h later. A single 1–12 h default is wrong for three of
the five profiles, and a wrong window is the quietest way to hide a real
pattern. So each profile ships three window chips and the analytics default to
the profile's middle one.

### 5.3 The five sets

Each profile seeds ~10 exercises, 8–10 symptoms, ~8 relief and ~8 triggers — the
same shape as today's postnatal seed, one tap to log, all editable. Names below
are the preset names, written the way a person would say them on a phone at 8 pm.

The picker is a plain `<select>` — a strip of chips showed one and a half of six
choices at 360 px — so each profile's label is short enough to read inside it
(~20 characters) and the sentence beside it does the explaining. “Pelvic health
after childbirth” truncates to “Pelvic health after childbi”; “After childbirth”
does not.

**1. `postnatal_pelvic` — “After childbirth”** *(default, the focus)*
Today's seed, unchanged, so existing accounts and screenshots do not move.

| | |
| --- | --- |
| Physio | Pelvic Floor Lifts · Pelvic Floor Release · Deep Core Draw-In · Diaphragm Breathing · Glute Bridge · Clamshell · Bird Dog · Supported Squat · Hamstring Stretch · Wall Angels |
| Symptoms | Heaviness / Dragging · Urine Leak · Urgency · Gas or Bowel Leak · Perineal Pain · Scar Pain · Pelvic Girdle Pain · Low Back Pain · Pain with Sex · Belly Domining |
| Relief | Ice Pack · Heat Pack · Sitz Bath · Rest · Ibuprofen · Stool Softener · Pelvic Floor PT · Belly Support |
| Triggers | Heavy Lifting · Cough or Sneeze · Long Standing · Long Sitting · Straining · High-Impact Exercise · Poor Sleep · Carrying Baby |
| Windows | `0–2 h` (leak with a cough/lift) · `1–6 h` (default) · `6–48 h` (next-day flare) |

**2. `bladder_bowel` — “Bladder & bowel”** *(same anatomy, no birth context:
menopause, runners, prostatectomy recovery, chronic urgency)*

| | |
| --- | --- |
| Physio | Pelvic Floor Lifts · Long Hold Contractions · Rapid Flicks · Urge Suppression · Diaphragm Breathing · Timed Voiding Routine · Fluid Timing · Supported Squat · Hip Flexor Stretch · Bowel Posture Reset |
| Symptoms | Urine Leak · Urgency · Frequency · Night Urination · Incomplete Emptying · Gas or Bowel Leak · Constipation · Straining · Urgent Leak Before Toilet · Pressure / Bulge |
| Relief | Pad / Guard · Timed Voiding · Fibre · Hydration · Stool Softener · Pelvic Floor PT · Warm Bath · Bladder Diary |
| Triggers | Cough or Sneeze · Laughing · Running / Jumping · Heavy Lifting · Caffeine · Fluid Before Bed · Alcohol · Long Driving |
| Windows | `0–1 h` (default — this is a minutes-scale story) · `1–6 h` · `6–24 h` |

**3. `low_back_girdle` — “Low back & girdle”**

| | |
| --- | --- |
| Physio | Pelvic Tilt · Cat-Camel · Bird Dog · Glute Bridge · Side Plank (Knees) · Hip Hinge Practice · Deep Core Draw-In · Walking Interval · Piriformis Stretch · Hip Flexor Stretch |
| Symptoms | Low Back Pain · SI / Girdle Pain · Buttock Pain · Leg Numbness or Tingling · Morning Stiffness · Spasm · Numb Thigh · Pain With Rolling Over · Pain Standing on One Leg · Fatigue-Related Soreness |
| Relief | Heat Pack · Ice Pack · Walking · Position Change · Support Belt · Ibuprofen · Massage · Pelvic Floor PT |
| Triggers | Long Sitting · Long Standing · Bending / Lifting · Carrying on One Side · Driving · Poor Sleep · Climbing Stairs · Doing Too Much Too Soon |
| Windows | `0–2 h` (mechanical, immediate) · `1–12 h` (default) · `12–48 h` (next-day stiffness) |

**4. `shoulder_neck` — “Shoulder & neck”** *(the other half of postnatal life:
feeding posture, car seats, one-side carrying, desk)*

| | |
| --- | --- |
| Physio | Wall Angels · Scapular Squeeze · Doorway Pec Stretch · External Rotation · Chin Tuck · Serratus Wall Slide · Band Row · Trap Stretch · Thoracic Extension over Roll · Shoulder Blade Setting |
| Symptoms | Shoulder Pain · Neck Stiffness · Trapezius Ache · Headache · Numbness / Tingling Arm · Pain Lifting Arm · Night Pain Lying on Side · Pinching Reaching Up · Upper Back Soreness |
| Relief | Heat Pack · Ice Pack · Massage · Posture Break · Pillow Support · Ibuprofen · Physio Manual Therapy · Rest from Overhead |
| Triggers | Feeding Posture · Looking Down at Phone · Carrying on One Side · Reaching Overhead · Long Desk Session · Sleeping Position · Carrying the Car Seat · Cold Weather |
| Windows | `0–3 h` (positional, same day) · `3–24 h` (default) · `24–72 h` (delayed soreness) |

**5. `hip_knee` — “Hip & knee”** *(the "when can I run again"
diary: load management, tendons, impact)*

| | |
| --- | --- |
| Physio | Clamshell · Side Plank (Knees) · Step-Down Control · Single-Leg Press · Calf Raise · Hip Hinge Practice · Bridge Marching · Half Squat · Cycling (Easy) · Adductor Squeeze |
| Symptoms | Hip Pinching · Outer Hip Pain · Knee Pain · Kneecap Pain When Descending · IT Band Pain · Tendon Pain (Glute / Patellar) · Swelling · Stiffness After Rest · Giving-Way Feeling · Pain After Running |
| Relief | Ice Pack · Foam Roll · Load Reduction · Cycling Instead · Ibuprofen · Physio Manual Therapy · Sleep Extra · Support Footwear |
| Triggers | Running (Distance) · Running (Speed) · Hills · Stairs · Long Standing · Sitting Long · Skipping a Rest Day · New Footwear · Uneven Ground |
| Windows | `0–24 h` during/after the session (default) · `24–72 h` (tendon reaction) · `0–2 h` (sharp, in-the-moment) |

**And a sixth, non-seeded choice in the picker: "Start empty — I'll add my own."**
For anyone whose problem is not one of the five; they get the same app with no
presets and the `suggestions` pool as the way in. Skipping a profile must not
require inventing a fake diagnosis, and a wrong guess is worse than an empty
diary with a clear "add your first preset" hint.

---

## 6. What the user actually sees

### 6.1 One symptom, whole story (`/insights/symptom/{id}`)

The aggregate cards answer "how is it going overall", which is the least useful
question in a rehab diary. A symptom page is where the value is:

- its own series, gap-filled: **episodes per week**, **mean severity**, **worst
  week**, with plan events drawn as markers on the line;
- **what came before it**: ranked associations from exercises *and* triggers
  (same §2 maths, predictor side = exercise or context);
- **what came after it**: did a relief action precede a shorter/softer episode;
- its own time-of-day and its own weekday pattern (a real thing with childcare
  weeks);
- every one of its rows, tap-through to History.

### 6.2 Trend vs baseline, honestly

`last 7 days` vs `the 28 days before`, per symptom and overall, printed as
`X episodes/week (was Y)` **with the logging rate next to it**:

> Heaviness: 3.1 → 1.4 episodes/week · you logged 6 of 7 days, last month 5 of 7

If the logging rate moved more than the symptom did, the card says the change may
be the diary, not the body, and prints the adherence figures in the same colour.
That is the coverage gate, and it is the single most likely way this app could
accidentally reassure someone wrongly.

### 6.3 The physiotherapist's page

The reason the data exists is a 10-minute appointment. So: **Report** — one
screen, printable, and exportable as one PDF-less artefact that already exists:
JSON/CSV gain `plan_events`; the report page is a print stylesheet over a fixed
6-month window with:

- symptom league table with per-symptom trend arrows and N;
- the top associations *with their counts and baselines* (so the clinician can
  judge them, not take them on faith);
- the plan timeline (appointments, programme changes, meds) against the trend;
- adherence, recalled-entry share, and a "what changed on this date" list.

Print/PDF via the browser (`@media print`), no PDF library, no new dependency —
this is what ROADMAP item 5 wanted ("exported rather than live") and it needs no
share-token machinery yet.

### 6.4 Data sufficiency, as a first-class state

One shared component, driven by `sufficiency.py`, shown wherever a card would
otherwise be empty:

> Insights need about **20 logged days**. You have 6 days, 11 entries. Keep
> tapping — nothing here is judged, and the streak card is not the point.

Rules: never a number without its N; never an empty card without the reason;
never a chart whose x-axis hides the days with nothing in them.

---

## 7. Copy rules (this is a health app, so the words are part of the maths)

| Never | Instead |
| --- | --- |
| "X causes Y", "triggered", "you are improving" | "X came before Y in 9 of 24 cases", "the average of the last 7 days is lower than the 28 before" |
| "streak" as the headline metric of a diary week | "days with entries: 6 of 7" |
| a default that looks like a choice (severity 5, intensity, a silent fallback) | a default labelled as a default — in the control, in the toast, and on the stored row |
| percentages alone | counts, always with the denominator next to them |

No medical advice, no triage language, no "see a doctor if…" walls: the app
describes this diary. One sentence in Settings already says the data stays on the
user's own server; keep that as the whole privacy story.

---

## 8. Tests and measurements, before and after

1. **Null test (the one that matters).** `scripts/probes/lag_null.py` — the
   reproducer from §1.1, checked in, and a pytest that runs the *new*
   `association.py` over the same independent data and asserts **zero eligible
   findings**. This test fails today by design; it is the definition of done for
   §2.
2. **Planted-signal test.** A seeded diary where one exercise really is followed
   by one symptom 60 % of the time within 2–5 h and the rest is noise; assert the
   pair ranks first and its bound clears 1, and that no other pair does.
3. **Wilson/Wilson-floor unit tests** against hand-computed values; control-window
   construction tests (a symptom at 23:00 must not leak across the local-day
   boundary — the class of bug 0.1.2's streak fix was).
4. **Gap-fill tests**: `rollup.py` for a range with missing days returns every
   calendar day in the range, and the chart's first/last labels match the range
   the user selected.
5. **Window-consistency test**: every card on `/insights` is computed over the
   same range the header says, asserted via the response's own `days` echo.
6. **Profile tests**: register with each of the six choices seeds the right counts
   and nothing else; unknown key → `422`; omitted key → today's postnatal set
   byte-for-byte; `apply_profile` never archives or deletes; definitions carry
   `profile_key`.
7. **Perf probe**: `scripts/probes/rollup_cost.py` generates a 2-year dense diary
   (≈15 k logs) and prints `/summary` and `/associations` timings and
   `EXPLAIN QUERY PLAN` output, so the "no materialised rollup" call in §3 stays
   evidence-based instead of a hunch.
8. **Playwright**: the drawer gate (preset inert until severity picked, remember-
   last chip), symptom page, report print view at 360×640 and desktop, and the
   sufficiency state — measured at the four viewports the drawer bug taught us
   about.

---

## 9. Order of work

Small, independently shippable, each one useful on its own and each one testable
against the published image (the 0.1.3 lesson: verify the bytes, not the source).

**Password reset runs as a parallel track** *(decided 2026-11-24)* — `RESET`
below, and it does not touch anything in `insights/`, `profiles.py` or the drawer,
so the two streams cannot collide. Because a release is tagged from `VERSION` on
`main`, merges stay serial whichever stream finishes first: whoever merges gets
the next `0.2.x`.

| PR | Ships | Why this position |
| --- | --- | --- |
| **RESET** | `purpose='password_reset'` (already in the schema), 30-min single-use tokens, "forgotten password" on the auth screen, reset **revokes every session** for the account, per-IP and per-email send limits, no health data in the mail | independent of the phase; the account holds health data and a lost password is currently lost data |
| **A** | profiles registry, `GET /catalog/profiles`, `profile` on register, the sign-up picker (starting on "Start empty"), `profile_key` on users + definitions | biggest user-visible value, zero analytics risk, unblocks sensible presets and windows for everything after |
| **B** | labelled severity default + `severity_default` + remembered-last chip (§4.1), dose adjustment, note at log time, `_latest_offset` fix, per-card range consistency (§1.2 #6) | data quality has to start before the maths runs, or the maths inherits a diary it cannot trust |
| **C** | `insights/` package, `lag_null` probe + null and planted tests, gap-filled rollup, chance-corrected `GET /analytics/associations` replacing the lag card | the heart of the phase, landed with its null test |
| **D** | `plan_events` + entry points, per-symptom page, trend-vs-baseline with adherence printed | needs C's maths |
| **E** | Report view + `@media print` stylesheet only (decided 2026-11-24 — no PDF or HTML export dependency), export covers `plan_events`, sufficiency everywhere, copy pass | the "take it to your physio" payoff |
| **F** | `apply_profile` (add another set later), backup wiring in the lab (`scripts/backup.sh` on a systemd timer — vzdump copies a live SQLite file, see BACKUPS.md), ROADMAP/REQUIREMENTS §9 marked done | housekeeping that should not gate the features |

Still out of this phase, still in ROADMAP: passkeys, web-push reminders,
caregiver share links.

### 9.1 What actually shipped *(2026-11-24)*

**One PR, not six** — decided when the phase was started: the streams turned out
to be small enough that the coordination cost of six branches exceeded the risk
of one. `RESET`, A, B, C, D and E are all in `0.2.0`, in that commit order.

Deviations from the table, all of them smaller than planned:

- **No per-symptom route** (§6.1's `/insights/symptom/{id}`). The trend is a card
  on the Insights page with a `<select>` for the symptom, on the same `/insights`
  URL. A second route and a second page for one card is a thing to maintain, and
  nothing needed deep-linking to it.
- **The profile picker is a `<select>`, not a set of cards.** Six names do not fit
  a phone as cards or as a horizontal strip; the blurb and the counts sit under it.
- **The "skipped session" control is a toggle in the Physio drawer**, not a fifth
  tile.
- **PR F's `apply_profile` did not ship.** Adding a second set to an existing
  account is a handful of rows and no schema, so it stays deferred rather than
  being built under time pressure; a person who wants the hip-and-knee presets
  types them in, or the suggestions pool offers them one tap at a time.
- **§4's dose adjustment and log-time note did not ship** — B landed the
  `severity_default` label, the remembered-last chip and the `_latest_offset` fix,
  which are the parts the maths actually depends on.

---

## 10. Decisions

Answered 2026-11-24, and folded into §3–§9 above:

| Question | Decision |
| --- | --- |
| Severity default | keep the 5, **label it as a default** in the control, the toast, the stored row and the insights (§4.1) — not a gate |
| Profile preselection | the picker **starts on "Start empty"**; the five sets are one tap away, postnatal first with its blurb (§5.1) |
| Password reset vs insights | **in parallel**, as the `RESET` track (§9) |
| Report output | **browser print stylesheet only** — no PDF library, no server-rendered export (§6.3, PR E) |

Assumed unless you say otherwise (both are reversible and small):

- **Missed sessions** are logged as an exercise log with `sets_done = 0`, so
  plan adherence is computable from one table; they are excluded from the
  association maths, since a session you did not do cannot cause a flare.
- **Statistics stay invisible**: counts, the baseline, and the fixed verdict
  words. The Wilson bound decides what gets printed, and is never shown as
  numbers or as a percentage-confidence sentence.

## 11. The thing that actually limits this phase

The live database holds **1 account, 4 symptom logs, 2 exercise logs** — and all
six were written within 80 seconds of each other during sign-up testing. Every
number in §2 needs weeks of entries to mean anything: at the 5-session minimum a
person needs roughly 2 weeks of logging before a single association is eligible.
So the phase comes with two habits, not just code:

1. **Development runs on seeded data**: `scripts/demo_seed.py` against a
   throwaway container gives 24 days of a diary with a planted 2–5 h pattern,
   which is what the null and planted-signal tests in §8 are built on — never
   against the lab's database.
2. **The house account has to log for real** for the first few weeks of 0.2.x,
   otherwise the honest result of the whole phase is an empty card, and the app's
   first useful insight will be the sufficiency message telling you it needs more
   data.

