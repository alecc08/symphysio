/* Time helpers, in the language being displayed.

   The API stores epoch seconds plus the tz offset the device reported at that
   instant, so display formatting stays local without a timezone library — see
   docs/DATABASE.md.

   What was wrong here: every `Intl` formatter was built with `undefined` as the
   locale, meaning "whatever this browser says". A French app in an en-US browser
   printed "Mon, 23 nov." — half one language, half the other — and 03/11/2026
   read as March 11 to one person and November 3 to another. Every formatter now
   takes the app's tag (`fr-CA` / `en-CA`), because the date format is part of the
   translation. `en-CA` rather than `en-US` on purpose: it keeps the day first,
   which is what a Canadian reading English expects.
*/

export const MINUTE = 60;
export const HOUR = 3600;
export const DAY = 86_400;

/** Minutes to add to UTC to get local wall time (e.g. -300 for EST). */
export function localTzOffsetMin(atUtc: number = Math.floor(Date.now() / 1000)): number {
  const local = new Date(atUtc * 1000);
  return Math.round(-local.getTimezoneOffset());
}

export interface Formatters {
  clock: (atUtc: number) => string;
  day: (atUtc: number) => string;
  weekday: (isoDay: string) => string;
  monthDay: (isoDay: string) => string;
  /** `Nov 23, 2026` / `23 nov. 2026` — the printed report needs the year. */
  date: (atUtc: number) => string;
}

// One set per language, built once: `Intl.DateTimeFormat` is not cheap and these
// run over every row of a 200-entry history list.
const FORMATTERS = new Map<string, Formatters>();

export function formatters(tag: string): Formatters {
  const cached = FORMATTERS.get(tag);
  if (cached) return cached;
  const clock = new Intl.DateTimeFormat(tag, { hour: "numeric", minute: "2-digit" });
  const day = new Intl.DateTimeFormat(tag, { weekday: "short", month: "short", day: "numeric" });
  const weekday = new Intl.DateTimeFormat(tag, { weekday: "short" });
  const monthDay = new Intl.DateTimeFormat(tag, { month: "short", day: "numeric" });
  const date = new Intl.DateTimeFormat(tag, { year: "numeric", month: "short", day: "numeric" });
  const built: Formatters = {
    clock: (atUtc) => clock.format(new Date(atUtc * 1000)),
    day: (atUtc) => day.format(new Date(atUtc * 1000)),
    weekday: (isoDay) => weekday.format(new Date(`${isoDay}T12:00:00`)),
    monthDay: (isoDay) => monthDay.format(new Date(`${isoDay}T12:00:00`)),
    date: (atUtc) => date.format(new Date(atUtc * 1000)),
  };
  FORMATTERS.set(tag, built);
  return built;
}

/** Numbers are part of the translation too: `fr-CA` writes -1,2 and `en-CA`
 *  writes -1.2, and a clinical number printed with the wrong separator is read
 *  as a different number. */
const NUMBER_FORMATS = new Map<string, Intl.NumberFormat>();

export function formatNumber(value: number, tag: string, maxFractionDigits = 1): string {
  const key = `${tag}:${maxFractionDigits}`;
  const cached = NUMBER_FORMATS.get(key);
  if (cached) return cached.format(value);
  const built = new Intl.NumberFormat(tag, { maximumFractionDigits: maxFractionDigits });
  NUMBER_FORMATS.set(key, built);
  return built.format(value);
}

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
