/* Retroactive timestamp strip: logging late should not wreck lag analysis. */

import { useState } from "react";

import { useI18n } from "../i18n";
import { formatters, fromLocalInputValue, toLocalInputValue } from "../lib/time";
import { relativeLabel, timeChips } from "../lib/timeLabels";

export function TimeChips({
  value,
  onChange,
}: {
  value: number;
  onChange: (utcSeconds: number) => void;
}) {
  const { t, tag } = useI18n();
  const [customOpen, setCustomOpen] = useState(false);
  const now = Math.floor(Date.now() / 1000);
  const deltaMinutes = Math.round((now - value) / 60);

  const chipActive = (offsetSeconds: number | null) =>
    offsetSeconds === null
      ? customOpen
      : offsetSeconds === 0
        ? Math.abs(now - value) < 75
        : Math.abs(value - (now + offsetSeconds)) < 90;

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between text-xs font-semibold text-muted">
        <span>{t("time.when")}</span>
        <span className="tabular-nums">
          {formatters(tag).clock(value)}
          {deltaMinutes > 1 ? ` · ${relativeLabel(value, t, tag)}` : ""}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {timeChips(t).map((chip) => (
          <button
            key={chip.label}
            type="button"
            aria-pressed={chipActive(chip.offsetSeconds)}
            onClick={() => {
              if (chip.offsetSeconds === null) {
                setCustomOpen((open) => !open);
                return;
              }
              setCustomOpen(false);
              onChange(Math.floor(Date.now() / 1000) + chip.offsetSeconds);
            }}
            className={`rounded-full border px-3.5 py-2 text-sm font-semibold ${
              chipActive(chip.offsetSeconds)
                ? "border-physio bg-physio text-white"
                : "border-line bg-canvas text-ink"
            }`}
          >
            {chip.label}
          </button>
        ))}
      </div>
      {customOpen ? (
        <input
          type="datetime-local"
          defaultValue={toLocalInputValue(value)}
          max={toLocalInputValue(now + 60)}
          onChange={(event) => onChange(fromLocalInputValue(event.target.value))}
          className="mt-3 w-full rounded-xl border border-line bg-canvas px-3 py-2.5 text-base"
          aria-label={t("time.customTime")}
        />
      ) : null}
    </div>
  );
}
