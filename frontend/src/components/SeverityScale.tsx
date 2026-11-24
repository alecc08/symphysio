/* Severity 1-10 pill bar. One tap picks; colours ramp from calm to urgent. */

import type { MessageKey } from "../i18n/en";
import { useI18n } from "../i18n";
import { ClockIcon } from "./icons/Ui";

/** Score -> the word a person would use. Keys, not strings: the wording is part
 *  of the translation, and a score without a word is worse than no word at all. */
const WORDS: Record<number, MessageKey> = {
  1: "severity.barely",
  2: "severity.mild",
  3: "severity.mild",
  4: "severity.noticeable",
  5: "severity.bothersome",
  6: "severity.bothersome",
  7: "severity.hard",
  8: "severity.hard",
  9: "severity.severe",
  10: "severity.severe",
};

function toneFor(value: number): string {
  if (value <= 3) return "bg-physio-soft text-physio-ink border-physio";
  if (value <= 6) return "bg-trigger-soft text-trigger-ink border-trigger";
  return "bg-symptom-soft text-symptom-ink border-symptom";
}

export function SeverityScale({
  value,
  onChange,
  labelKey = "severity.label",
  isDefault = false,
  last,
}: {
  value: number | null;
  onChange: (value: number) => void;
  labelKey?: MessageKey;
  /** True when `value` is the drawer's default rather than a number the person
   *  chose. The number on the row is then labelled, not left to look like a
   *  measurement — an average of defaults is not a measurement. */
  isDefault?: boolean;
  /** `{ value, name }` from the last time this was logged, offered as one tap. */
  last?: { value: number; name: string } | null;
}) {
  const { t } = useI18n();
  const label = t(labelKey);
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between text-xs font-semibold text-muted">
        <span>{label}</span>
        <span>{value ? `${value}/10 · ${t(WORDS[value])}` : t("severity.tap")}</span>
      </div>
      {isDefault && labelKey === "severity.label" ? (
        <p className="mt-1 text-xs leading-snug text-faint">{t("severity.defaultNote")}</p>
      ) : null}
      {last && last.value !== value ? (
        <button
          type="button"
          onClick={() => onChange(last.value)}
          className="mt-2 rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-bold text-muted"
        >
          {t("severity.likeLast", { score: last.value, name: last.name })}
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
            aria-label={t("severity.aria", { label, number })}
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
  const { t } = useI18n();
  const options: { label: string; minutes: number }[] = [
    { label: t("duration.tenMinutes"), minutes: 10 },
    { label: t("duration.oneHour"), minutes: 60 },
    { label: t("duration.halfDay"), minutes: 240 },
    { label: t("duration.allDay"), minutes: 720 },
  ];
  return (
    <div className="mt-4">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-muted">
        <ClockIcon className="h-4 w-4" />
        <span>{t("duration.label")}</span>
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
