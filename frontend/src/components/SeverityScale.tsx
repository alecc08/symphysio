/* Severity 1-10 pill bar. One tap picks; colours ramp from calm to urgent. */

import { ClockIcon } from "./icons/Ui";

const WORDS: Record<number, string> = {
  1: "barely there",
  2: "mild",
  3: "mild",
  4: "noticeable",
  5: "bothersome",
  6: "bothersome",
  7: "hard",
  8: "hard",
  9: "severe",
  10: "severe",
};

function toneFor(value: number): string {
  if (value <= 3) return "bg-physio-soft text-physio-ink border-physio";
  if (value <= 6) return "bg-trigger-soft text-trigger-ink border-trigger";
  return "bg-symptom-soft text-symptom-ink border-symptom";
}

export function SeverityScale({
  value,
  onChange,
  label = "Severity",
  isDefault = false,
  last,
}: {
  value: number | null;
  onChange: (value: number) => void;
  label?: string;
  /** True when `value` is the drawer's default rather than a number the person
   *  chose. The number on the row is then labelled, not left to look like a
   *  measurement — an average of defaults is not a measurement. */
  isDefault?: boolean;
  /** `{ value, name }` from the last time this was logged, offered as one tap. */
  last?: { value: number; name: string } | null;
}) {
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between text-xs font-semibold text-muted">
        <span>{label}</span>
        <span>{value ? `${value}/10 · ${WORDS[value]}` : "tap a number"}</span>
      </div>
      {isDefault ? (
        <p className="mt-1 text-xs leading-snug text-faint">
          5 is the default, not your answer. Tap the number that fits — entries logged
          on the default are marked in your history.
        </p>
      ) : null}
      {last && last.value !== value ? (
        <button
          type="button"
          onClick={() => onChange(last.value)}
          className="mt-2 rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-bold text-muted"
        >
          Like last time: {last.value}/10 {last.name}
        </button>
      ) : null}
      {/* 5 x 2, not one row of ten: at 390 px a single row gives ~30 px-wide
          targets, and this is the control people hit with a thumb mid-flare. */}
      <div className="mt-2 grid grid-cols-5 gap-1.5">
        {Array.from({ length: 10 }, (_, index) => index + 1).map((number) => (
          <button
            key={number}
            type="button"
            onClick={() => onChange(number)}
            aria-label={`${label} ${number} of 10`}
            aria-pressed={value === number}
            className={`h-11 rounded-lg border text-base font-bold tabular-nums transition-transform ${
              value === number
                ? // A default left sitting on the scale is not an answer the person
                  // gave, so it is drawn with a dashed edge: the row still shows 5,
                  // but it never looks like a chosen number.
                  `${toneFor(number)} border-2 scale-105 ${isDefault ? "border-dashed" : ""}`
                : "border-line bg-canvas text-muted"
            }`}
          >
            {number}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Optional duration quick-pick (symptom episodes). */
export function DurationChips({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (minutes: number | null) => void;
}) {
  const options = [
    { label: "10m", minutes: 10 },
    { label: "1h", minutes: 60 },
    { label: "half day", minutes: 240 },
    { label: "all day", minutes: 720 },
  ];
  return (
    <div className="mt-4">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-muted">
        <ClockIcon className="h-4 w-4" />
        <span>How long</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={value === option.minutes}
            onClick={() => onChange(value === option.minutes ? null : option.minutes)}
            className={`rounded-full border px-3.5 py-2 text-sm font-semibold ${
              value === option.minutes
                ? "border-symptom bg-symptom text-white"
                : "border-line bg-canvas text-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
