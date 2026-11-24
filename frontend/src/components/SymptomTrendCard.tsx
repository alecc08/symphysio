/* One symptom, against its own starting point.

The comparison is with the same person's first `baseline_days` of the window —
never another user and never a population norm. There is no cross-user query in
this app, and a norm would be advice wearing a chart.

Adherence is printed beside the trend on purpose: "less pain" and "less
programme" look identical on a line, and the honest reading needs both.
*/

import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { SymptomTrend } from "../api/types";
import { useI18n } from "../i18n";
import { formatNumber, formatters } from "../lib/time";

function Compare({
  label,
  value,
  unit,
  tag,
}: {
  label: string;
  value: number | null;
  unit: string;
  tag: string;
}) {
  return (
    <div className="rounded-xl bg-canvas px-2 py-2 text-center">
      <p className="text-base font-extrabold tabular-nums">
        {value === null ? "—" : `${formatNumber(value, tag)}${unit}`}
      </p>
      <p className="text-[0.65rem] font-semibold text-muted">{label}</p>
    </div>
  );
}

export function SymptomTrendCard({ definitionId }: { definitionId: string }) {
  const { t, tag } = useI18n();
  const fmt = formatters(tag);
  const [data, setData] = useState<SymptomTrend | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api
      .symptomTrend(definitionId, { days: 90 })
      .then(setData)
      .catch(() => setError(t("trend.loadFailed")));
    // `t` is deliberately not a dependency: the fetch is keyed to the symptom,
    // and re-fetching because the language changed would throw away the answer
    // the person is already reading. The error text re-renders from `error`.
  }, [definitionId]);

  if (error) return <p className="mt-3 text-sm text-symptom-ink">{error}</p>;
  if (!data) return <p className="mt-3 text-sm text-muted">{t("app.loading")}</p>;

  const start = data.baseline.avg_severity;
  const now = data.recent.avg_severity;
  const delta = start !== null && now !== null ? Math.round((now - start) * 10) / 10 : null;

  // One line saying what is missing, so three dashes never stand in for an answer.
  // "It has no starting point yet" and "there is no diary at all" are different
  // situations and the card should not blur them.
  let missing: string | null = null;
  if (start === null && now === null) {
    missing = t("trend.noneInWindow", { days: data.days });
  } else if (start === null) {
    missing = t("trend.noBaseline", { days: data.baseline_days });
  } else if (now === null) {
    missing = t("trend.noRecent", { days: data.baseline_days });
  }

  return (
    <div>
      <p className="text-sm leading-snug">
        <strong>{data.definition.name}</strong> ·{" "}
        {t("trend.comparedWith", { days: data.days, baseline: data.baseline_days })}
      </p>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Compare
          label={t("trend.firstDays", { days: data.baseline_days })}
          value={start}
          unit=""
          tag={tag}
        />
        <Compare label={t("trend.since")} value={now} unit="" tag={tag} />
        <Compare
          label={t("trend.change")}
          value={delta}
          unit={
            delta === null ? "" : delta > 0 ? t("trend.unitWorse") : delta < 0 ? t("trend.unitBetter") : ""
          }
          tag={tag}
        />
      </div>

      <p className="mt-3 text-sm text-muted">
        {t("trend.adherenceLogged", {
          withLog: data.adherence.days_with_any_log,
          covered: data.adherence.days_covered,
        })}{" "}
        {t("trend.adherenceProgramme", { days: data.adherence.days_with_exercise })}
        {data.adherence.sessions_skipped > 0
          ? t("trend.skipped", { count: data.adherence.sessions_skipped })
          : ""}
        {t("trend.adherenceWhy")}
      </p>

      {data.severity_defaults > 0 ? (
        <p className="mt-2 text-xs text-muted">{t("trend.defaultsNote", { count: data.severity_defaults })}</p>
      ) : null}

      {data.plan_events.length > 0 ? (
        <ul className="mt-3 space-y-1">
          {data.plan_events.map((event) => (
            <li key={event.id} className="text-xs text-muted">
              <span className="font-bold tabular-nums text-ink">
                {fmt.day(event.occurred_at_utc)}
              </span>{" "}
              — {event.text}
            </li>
          ))}
        </ul>
      ) : null}

      {missing ? (
        <p className="mt-3 text-sm text-muted">{missing}</p>
      ) : data.sufficiency !== "enough" ? (
        <p className="mt-3 text-sm text-muted">{t("trend.tooFew")}</p>
      ) : null}
    </div>
  );
}
