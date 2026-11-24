/* The words around the timestamps: "3 h ago", "skipped", "severity 5/10 (default)".

   Split out of `time.ts` because these need the dictionary, and keeping the
   arithmetic file free of it means the file with the date maths has exactly one
   reason to change. `describeMetric` prints what a row *measured*, and the
   wording matters clinically: a severity left on the drawer's default is not a
   number the person chose, and history says which (see docs/INSIGHTS_PLAN.md).
*/

import type { MessageKey } from "../i18n/en";
import { DAY, HOUR, MINUTE, formatters } from "./time";

export type Translate = (key: MessageKey, params?: Record<string, string | number>) => string;

/** "just now", "12 min", "3 h", "22 avr." — the same ladder in either language. */
export function relativeLabel(
  atUtc: number,
  t: Translate,
  tag: string,
  nowUtc: number = Math.floor(Date.now() / 1000),
): string {
  const delta = nowUtc - atUtc;
  if (delta < 90) return t("time.justNow");
  if (delta < HOUR * 6) return t("time.minutesAgo", { count: Math.round(delta / MINUTE) });
  if (delta < DAY) return t("time.hoursAgo", { count: Math.round(delta / HOUR) });
  if (delta < DAY * 7) return t("time.daysAgo", { count: Math.round(delta / DAY) });
  return formatters(tag).monthDay(new Date(atUtc * 1000).toISOString().slice(0, 10));
}

export interface TimeChip {
  label: string;
  offsetSeconds: number | null;
}

/** Retroactive logging strip: Now, -15m, -1h, -3h, Custom. */
export function timeChips(t: Translate): TimeChip[] {
  return [
    { label: t("time.now"), offsetSeconds: 0 },
    { label: t("time.minus15m"), offsetSeconds: -15 * MINUTE },
    { label: t("time.minus1h"), offsetSeconds: -HOUR },
    { label: t("time.minus3h"), offsetSeconds: -3 * HOUR },
    { label: t("time.custom"), offsetSeconds: null },
  ];
}

export interface MetricRow {
  event_type: string;
  sets_done: number | null;
  reps_done: number | null;
  duration_sec: number | null;
  duration_min: number | null;
  primary_metric: number | null;
  severity: number | null;
  intensity: number | null;
  severity_default?: number | null;
}

/** One line describing what a log entry recorded, in the reader's language. */
export function describeMetric(item: MetricRow, t: Translate): string {
  const parts: string[] = [];
  if (item.event_type === "exercise" && item.sets_done === 0) {
    // "Did not do it today" is a record of keeping track, not a dose of zero.
    parts.push(t("metric.skipped"));
  } else if (item.sets_done != null && item.reps_done != null) {
    parts.push(t("metric.setsReps", { sets: item.sets_done, reps: item.reps_done }));
  } else if (item.reps_done != null) {
    parts.push(t("metric.reps", { count: item.reps_done }));
  } else if (item.sets_done != null) {
    parts.push(t("metric.sets", { count: item.sets_done }));
  }
  if (item.duration_sec != null) parts.push(t("metric.seconds", { count: item.duration_sec }));
  if (item.duration_min != null) parts.push(t("metric.minutes", { count: item.duration_min }));
  if (item.event_type === "symptom" && item.severity != null) {
    parts.push(
      item.severity_default === 1
        ? t("metric.severityDefault", { score: item.severity })
        : t("metric.severity", { score: item.severity }),
    );
  }
  if (item.event_type === "exercise" && item.primary_metric != null) {
    parts.push(t("metric.effort", { score: item.primary_metric }));
  }
  if (item.event_type === "context" && item.intensity != null) {
    parts.push(t("metric.intensity", { score: item.intensity }));
  }
  return parts.join(" · ");
}
