/* Mirrors the API contract in docs/API.md. */

export type EventCategory = "relief" | "trigger";
export type EventType = "exercise" | "symptom" | "context";

export interface User {
  id: string;
  email: string;
  created_at_utc: number;
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
}

export interface SymptomDefinition {
  id: string;
  name: string;
  body_region: string | null;
  icon_key: string;
  is_archived: boolean;
  sort_order: number;
}

export interface ContextDefinition {
  id: string;
  name: string;
  category: EventCategory;
  icon_key: string;
  is_archived: boolean;
  sort_order: number;
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
}

export interface TimelinePage {
  items: TimelineItem[];
  next_before: number | null;
}

export interface SummaryDaily {
  day: string;
  exercises: number;
  symptoms: number;
  contexts: number;
  avg_symptom_severity: number | null;
  avg_effort: number | null;
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
  };
  daily: SummaryDaily[];
  top_exercises: { id: string; name: string; count: number; avg_severity: number | null }[];
  top_symptoms: { id: string; name: string; count: number; avg_severity: number | null }[];
  exercise_streak_days: number;
}

export interface LagPair {
  exercise_id: string;
  exercise_name: string;
  symptom_id: string;
  symptom_name: string;
  post_exercise_occurrences: number;
  avg_lag_hours: number;
  min_lag_hours: number;
  max_lag_hours: number;
  avg_severity: number;
  exercise_occurrences: number;
  symptom_logs_in_range: number;
  share_of_symptom_logs: number | null;
}

export interface LagResponse {
  min_hours: number;
  max_hours: number;
  days: number;
  min_count: number;
  pairs: LagPair[];
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
