/* Time helpers. The API stores epoch seconds + the client's tz offset, so all
   display formatting stays local without a timezone library. */

export const MINUTE = 60;
export const HOUR = 3600;
export const DAY = 86_400;

/** Minutes to add to UTC to get local wall time (e.g. -300 for EST). */
export function localTzOffsetMin(atUtc: number = Math.floor(Date.now() / 1000)): number {
  const local = new Date(atUtc * 1000);
  return Math.round(-local.getTimezoneOffset());
}

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" });
const weekdayFmt = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const monthDayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export function formatClock(atUtc: number): string {
  return timeFmt.format(new Date(atUtc * 1000));
}

export function formatDay(atUtc: number): string {
  return dayFmt.format(new Date(atUtc * 1000));
}

export function weekdayLabel(isoDay: string): string {
  return weekdayFmt.format(new Date(`${isoDay}T12:00:00`));
}

export function monthDayLabel(isoDay: string): string {
  return monthDayFmt.format(new Date(`${isoDay}T12:00:00`));
}

/** "just now", "12m ago", "3h ago", "Mar 4" */
export function relativeLabel(atUtc: number, nowUtc: number = Math.floor(Date.now() / 1000)): string {
  const delta = nowUtc - atUtc;
  if (delta < 90) return "just now";
  if (delta < HOUR * 6) return `${Math.round(delta / MINUTE)}m ago`;
  if (delta < DAY) return `${Math.round(delta / HOUR)}h ago`;
  if (delta < DAY * 7) return `${Math.round(delta / DAY)}d ago`;
  return monthDayLabel(new Date(atUtc * 1000).toISOString().slice(0, 10));
}

export interface TimeChip {
  label: string;
  offsetSeconds: number | null;
}

/** Retroactive logging strip: Now, -15m, -1h, -3h, Custom. */
export const TIME_CHIPS: TimeChip[] = [
  { label: "Now", offsetSeconds: 0 },
  { label: "-15m", offsetSeconds: -15 * MINUTE },
  { label: "-1h", offsetSeconds: -HOUR },
  { label: "-3h", offsetSeconds: -3 * HOUR },
  { label: "Custom", offsetSeconds: null },
];

export function toLocalInputValue(atUtc: number): string {
  const date = new Date(atUtc * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function fromLocalInputValue(value: string): number {
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? Math.floor(Date.now() / 1000) : Math.floor(parsed / 1000);
}

export function describeMetric(item: {
  event_type: string;
  sets_done: number | null;
  reps_done: number | null;
  duration_sec: number | null;
  duration_min: number | null;
  primary_metric: number | null;
  severity: number | null;
  intensity: number | null;
  severity_default?: number | null;
}): string {
  const parts: string[] = [];
  if (item.event_type === "exercise" && item.sets_done === 0) {
    // "Did not do it today" is a record of keeping track, not a dose of zero.
    parts.push("skipped");
  } else if (item.sets_done != null && item.reps_done != null) {
    parts.push(`${item.sets_done}×${item.reps_done}`);
  } else if (item.reps_done != null) {
    parts.push(`${item.reps_done} reps`);
  } else if (item.sets_done != null) {
    parts.push(`${item.sets_done} sets`);
  }
  if (item.duration_sec != null) parts.push(`${item.duration_sec}s`);
  if (item.duration_min != null) parts.push(`${item.duration_min} min`);
  if (item.event_type === "symptom" && item.severity != null) {
    // The row knows whether that number was chosen or left on the drawer's
    // default, and history says which — otherwise the log reads as a measurement
    // that was never made.
    parts.push(
      item.severity_default === 1
        ? `severity ${item.severity}/10 (default)`
        : `severity ${item.severity}/10`,
    );
  }
  if (item.event_type === "exercise" && item.primary_metric != null)
    parts.push(`effort ${item.primary_metric}/10`);
  if (item.event_type === "context" && item.intensity != null) parts.push(`${item.intensity}/10`);
  return parts.join(" · ");
}
