/* Mirrors the API contract in docs/API.md. */

export type EventCategory = "relief" | "trigger";
export type EventType = "exercise" | "symptom" | "context";

export interface User {
  id: string;
  email: string;
  created_at_utc: number;
  /** False only when this install sends confirmation emails and the link is unspent. */
  is_verified: boolean;
  /** The tracking set the account started from; "none" means it started empty.
   *  Provenance only — changing it later rewrites no history. */
  profile_key: string;
  /** "en" or "fr". The server keeps it because it also decides the language of
   *  the emails and of its own error messages, which no browser setting reaches. */
  locale: string;
  /** IANA zone, or null when this account has never chosen one — which is not the
   *  same as choosing UTC: it means the instance default applies. */
  timezone: string | null;
}

/** GET/PATCH /auth/preferences: what the account holds, and what is in use. */
export interface Preferences {
  locale: string;
  timezone: string | null;
  effective_timezone: string;
  /** `UTC-5` today, `UTC-4` in summer: a zone name alone never says which. */
  utc_offset: string;
}

export interface AuthResponse {
  user: User;
}

export interface ExerciseDefinition {
  id: string;
  name: string;
  body_region: string | null;
  default_sets: number | null;
  default_reps: number | null;
  default_sec: number | null;
  icon_key: string;
  is_archived: boolean;
  sort_order: number;
  /** Which sign-up profile seeded this preset, or null if the person typed it.
   *  Origin only: no behaviour depends on it. */
  profile_key: string | null;
}

export interface SymptomDefinition {
  id: string;
  name: string;
  body_region: string | null;
  icon_key: string;
  is_archived: boolean;
  sort_order: number;
  /** Which sign-up profile seeded this preset, or null if the person typed it.
   *  Origin only: no behaviour depends on it. */
  profile_key: string | null;
  /** The severity last logged for this symptom, and when: the drawer offers that
   *  number back rather than logging another silent default. */
  last_severity: number | null;
  last_logged_utc: number | null;
}

export interface ContextDefinition {
  id: string;
  name: string;
  category: EventCategory;
  icon_key: string;
  is_archived: boolean;
  sort_order: number;
  /** Which sign-up profile seeded this preset, or null if the person typed it.
   *  Origin only: no behaviour depends on it. */
  profile_key: string | null;
}

export interface Suggestion {
  name: string;
  // Exercises use body_region; symptoms use default_region; contexts use category.
  // A suggestion is shaped exactly like the create payload for its kind, so the
  // client posts it back unchanged (the API models forbid extra fields).
  body_region?: string | null;
  default_region?: string | null;
  category?: EventCategory;
  default_sets?: number | null;
  default_reps?: number | null;
  default_sec?: number | null;
}

export interface CreatedLog {
  id: string;
  event_type: EventType;
  status: string;
}

export interface TimelineItem {
  id: string;
  event_type: EventType;
  def_id: string;
  definition_name: string | null;
  occurred_at_utc: number;
  tz_offset_min: number;
  logged_at_utc: number | null;
  primary_metric: number | null;
  note: string | null;
  sets_done: number | null;
  reps_done: number | null;
  duration_sec: number | null;
  pain_during: number | null;
  body_region: string | null;
  severity: number | null;
  duration_min: number | null;
  category: EventCategory | null;
  intensity: number | null;
  /** 1 when this severity is the drawer's default rather than a chosen number.
   *  History labels it, and an average that mixes the two is honest about it. */
  severity_default: number | null;
}

export interface TimelinePage {
  items: TimelineItem[];
  next_before: number | null;
}

export interface SummaryDaily {
  day: string;
  exercises: number;
  /** Sessions logged as "did not do it" (sets_done = 0). They count for adherence
   *  and never for the association maths. */
  exercises_skipped: number;
  symptoms: number;
  contexts: number;
  avg_symptom_severity: number | null;
  avg_effort: number | null;
  /** The average over rows where the number was actually chosen. */
  avg_chosen_severity: number | null;
  severity_defaults: number;
  logged: boolean;
}

export interface Adherence {
  days_covered: number;
  days_with_any_log: number;
  days_with_exercise: number;
  target_days_per_week: number;
  weeks: number;
  sessions_done: number;
  sessions_skipped: number;
  adherence_per_week: number;
}

export interface Summary {
  days: number;
  since_utc: number;
  generated_at_utc: number;
  totals: {
    exercises: number;
    symptoms: number;
    contexts: number;
    avg_symptom_severity: number | null;
    worst_symptom_severity: number | null;
    avg_effort: number | null;
    /** Symptom rows whose severity was the drawer's default, not a chosen number. */
    severity_defaults: number;
  };
  daily: SummaryDaily[];
  adherence: Adherence;
  coverage: Coverage;
  top_exercises: { id: string; name: string; count: number; avg_severity: number | null }[];
  top_symptoms: { id: string; name: string; count: number; avg_severity: number | null }[];
  exercise_streak_days: number;
}

export interface ProfileCounts {
  exercises: number;
  symptoms: number;
  relief: number;
  triggers: number;
}

export interface LagWindow {
  label: string;
  min_hours: number;
  max_hours: number;
}

export interface Profile {
  key: string;
  label: string;
  blurb: string;
  counts: ProfileCounts;
  windows: LagWindow[];
  default_window: string;
}

export interface PlanEvent {
  id: string;
  kind: "appointment" | "programme_change" | "medication" | "goal" | "note";
  text: string;
  occurred_at_utc: number;
  logged_at_utc: number;
  tz_offset_min: number;
  created_at_utc?: number;
}

/** What the association maths may say. Four fixed words — the server owns the
 *  vocabulary, the UI only ever gives it a colour. */
/** Four fixed words, owned by the server. The UI gives them a colour and never
 *  rewrites them, and no interval or p-value is ever shown. */
export type Verdict =
  | "worth a look"
  | "looks like chance"
  | "nothing found"
  | "seen too rarely to tell";

export interface Finding {
  exposure_kind: EventType;
  exposure_id: string;
  exposure_name: string;
  symptom_id: string;
  symptom_name: string;
  sessions: number;
  hits: number;
  control_windows: number;
  control_hits: number;
  rate_exposed: number;
  rate_baseline: number;
  relative_risk: number | null;
  verdict: Verdict;
  /** Why a pair was refused, so the card can say the true reason: `too_few_sessions`,
   *  `too_few_hits`, `no_comparable_windows`, or "" when it reached a verdict. */
  gate: string;
  avg_severity: number | null;
  default_severity_hits: number;
}

export interface Coverage {
  state: "enough" | "thin" | "none";
  days_covered: number;
  days_requested: number;
  symptom_logs: number;
  exercise_logs: number;
  eligible_pairs: number;
}

export interface GateCount {
  gate: "too_few_sessions" | "too_few_hits" | "no_comparable_windows";
  pairs: number;
}

export interface Associations {
  days: number;
  generated_at_utc: number;
  profile_key: string;
  windows: LagWindow[];
  window: LagWindow;
  exposure: "exercise" | "context" | "both";
  coverage: Coverage;
  sufficiency: Coverage["state"];
  pairs_examined: number;
  pairs_shown: number;
  skipped_sessions: number;
  days_covered: number;
  findings: Finding[];
  /** Why refused pairs were refused, counted. The honest version of "no data". */
  gates: GateCount[];
}

export interface SymptomTrend {
  definition: { id: string; name: string; is_archived: boolean };
  days: number;
  baseline_days: number;
  generated_at_utc: number;
  daily: SummaryDaily[];
  baseline: { avg_severity: number | null; logs_per_day: number | null; days: number };
  recent: { avg_severity: number | null; logs_per_day: number | null; days: number };
  severity_defaults: number;
  adherence: {
    days_covered: number;
    days_with_any_log: number;
    days_with_exercise: number;
    target_days_per_week: number;
    weeks: number;
    sessions_done: number;
    sessions_skipped: number;
    adherence_per_week: number;
  };
  plan_events: PlanEvent[];
  coverage: Coverage;
  sufficiency: Coverage["state"];
  first_logged_day: string | null;
}

export interface TimeOfDay {
  days: number;
  event_type: EventType;
  hours: { hour: number; count: number; avg_metric: number | null }[];
}

export interface CatalogKindTables {
  exercises: ExerciseDefinition[];
  symptoms: SymptomDefinition[];
  contexts: ContextDefinition[];
}
