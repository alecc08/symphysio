/* Labels for the enum values the API stores.

   The values themselves are fixed English tokens — `relief`, `trigger`,
   `programme_change` — and they are *not* translated in the database or the
   export, because they are the API's vocabulary, not prose. Only the label shown
   to a person is. An unrecognised token prints itself rather than an empty
   string: a new kind on the server should look odd in the UI, not invisible.

   Kept separate from the pages so History and the quick-log drawer agree.
*/

import type { MessageKey } from "../i18n/en";
import type { Translate } from "./timeLabels";

const CATEGORY_KEYS: Record<string, MessageKey> = {
  relief: "category.relief",
  trigger: "category.trigger",
};

const PLAN_KIND_KEYS: Record<string, MessageKey> = {
  appointment: "plan.kind.appointment",
  programme_change: "plan.kind.programme_change",
  medication: "plan.kind.medication",
  goal: "plan.kind.goal",
  note: "plan.kind.note",
};

export function categoryLabel(category: string, t: Translate): string {
  const key = CATEGORY_KEYS[category];
  return key ? t(key) : category;
}

export function planKindLabel(kind: string, t: Translate): string {
  const key = PLAN_KIND_KEYS[kind];
  return key ? t(key) : kind.replace("_", " ");
}

const VERDICT_KEYS: Record<string, MessageKey> = {
  "worth a look": "verdict.worthALook",
  "looks like chance": "verdict.looksLikeChance",
  "nothing found": "verdict.nothingFound",
  "seen too rarely to tell": "verdict.tooRare",
};

const GATE_KEYS: Record<string, MessageKey> = {
  too_few_sessions: "gate.tooFewSessions",
  too_few_hits: "gate.tooFewHits",
  no_comparable_windows: "gate.noComparableWindows",
};

/** The four verdict words and the three gate reasons are the server's vocabulary
 *  (app/insights/association.py) and arrive as fixed English tokens; the API
 *  contract stays English and only the display label is translated. An unknown
 *  token prints itself: a new verdict on the server must be visible, not blank. */
export function verdictLabel(verdict: string, t: Translate): string {
  const key = VERDICT_KEYS[verdict];
  return key ? t(key) : verdict;
}

export function gateLabel(gate: string, t: Translate): string {
  const key = GATE_KEYS[gate];
  return key ? t(key) : t("assoc.gateUnknown");
}

/** The body regions the shipped presets use (app/profiles.py). They are stored as
 *  snake_case tokens, so they translate like the other enum values — but the
 *  column is free text, so a region someone typed by hand ("left knee") falls
 *  through to the readable form of what they wrote rather than being dropped. */
const REGION_KEYS: Record<string, MessageKey> = {
  ankles: "region.ankles",
  arm: "region.arm",
  bladder: "region.bladder",
  bowel: "region.bowel",
  c_section_scar: "region.c_section_scar",
  chest: "region.chest",
  core: "region.core",
  hamstrings: "region.hamstrings",
  head: "region.head",
  hip_flexors: "region.hip_flexors",
  hips: "region.hips",
  knee: "region.knee",
  leg: "region.leg",
  lower_back: "region.lower_back",
  lower_belly: "region.lower_belly",
  neck: "region.neck",
  obliques: "region.obliques",
  pelvic_floor: "region.pelvic_floor",
  perineum: "region.perineum",
  ribcage: "region.ribcage",
  shoulder: "region.shoulder",
  si_joint: "region.si_joint",
  spine: "region.spine",
  upper_back: "region.upper_back",
  whole_body: "region.whole_body",
};

export function regionLabel(region: string, t: Translate): string {
  const key = REGION_KEYS[region];
  return key ? t(key) : humanizeToken(region);
}

/** `lower_back` -> `lower back`. Body regions are free text the presets invent, so
 *  they are de-snake-cased, not translated: like a preset name, they are the
 *  person's data and a language switch must not rewrite them. */
export function humanizeToken(value: string): string {
  return value.replaceAll("_", " ");
}
