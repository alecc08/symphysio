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
import { formatDay } from "../lib/time";

function Compare({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div className="rounded-xl bg-canvas px-2 py-2 text-center">
      <p className="text-base font-extrabold tabular-nums">
        {value === null ? "—" : `${value}${unit}`}
      </p>
      <p className="text-[0.65rem] font-semibold text-muted">{label}</p>
    </div>
  );
}

export function SymptomTrendCard({ definitionId }: { definitionId: string }) {
  const [data, setData] = useState<SymptomTrend | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api
      .symptomTrend(definitionId, { days: 90 })
      .then(setData)
      .catch(() => setError("Could not load this symptom's trend."));
  }, [definitionId]);

  if (error) return <p className="mt-3 text-sm text-symptom-ink">{error}</p>;
  if (!data) return <p className="mt-3 text-sm text-muted">Loading…</p>;

  const start = data.baseline.avg_severity;
  const now = data.recent.avg_severity;
  const delta = start !== null && now !== null ? Math.round((now - start) * 10) / 10 : null;

  // One line saying what is missing, so three dashes never stand in for an answer.
  // "It has no starting point yet" and "there is no diary at all" are different
  // situations and the card should not blur them.
  let missing: string | null = null;
  if (start === null && now === null) {
    missing = `Nothing logged for this symptom in the last ${data.days} days.`;
  } else if (start === null) {
    missing = `No entries in its first ${data.baseline_days} here, so there is no starting point to compare against yet.`;
  } else if (now === null) {
    missing = `Nothing logged since its first ${data.baseline_days} days — that itself is a result.`;
  }

  return (
    <div>
      <p className="text-sm leading-snug">
        <strong>{data.definition.name}</strong> · last {data.days} days, compared with
        its first {data.baseline_days}.
      </p>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Compare label={`first ${data.baseline_days} days`} value={start} unit="" />
        <Compare label="since" value={now} unit="" />
        <Compare
          label="change"
          value={delta}
          unit={delta === null ? "" : delta > 0 ? " worse" : delta < 0 ? " better" : ""}
        />
      </div>

      <p className="mt-3 text-sm text-muted">
        Logged on {data.adherence.days_with_any_log} of {data.adherence.days_covered} days.
        Programme done on {data.adherence.days_with_exercise} days
        {data.adherence.sessions_skipped > 0
          ? `, logged as skipped on ${data.adherence.sessions_skipped} session${data.adherence.sessions_skipped === 1 ? "" : "s"}`
          : ""}
        . A trend is only a trend if the programme happened — that is why this line is here.
      </p>

      {data.severity_defaults > 0 ? (
        <p className="mt-2 text-xs text-muted">
          {data.severity_defaults} of these entries used the default severity rather than a
          chosen number.
        </p>
      ) : null}

      {data.plan_events.length > 0 ? (
        <ul className="mt-3 space-y-1">
          {data.plan_events.map((event) => (
            <li key={event.id} className="text-xs text-muted">
              <span className="font-bold tabular-nums text-ink">
                {formatDay(event.occurred_at_utc)}
              </span>{" "}
              — {event.text}
            </li>
          ))}
        </ul>
      ) : null}

      {missing ? (
        <p className="mt-3 text-sm text-muted">{missing}</p>
      ) : data.sufficiency !== "enough" ? (
        <p className="mt-3 text-sm text-muted">
          Too few entries in this window for the comparison above to mean much.
        </p>
      ) : null}
    </div>
  );
}
