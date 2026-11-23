/* Insights: counts, trends and the exercise -> symptom lag table. */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { LagResponse, Summary, TimeOfDay } from "../api/types";
import { DailyBars, HourBars, SeverityTrend } from "../components/Charts";
import { SparkIcon } from "../components/icons/Ui";

const RANGES = [7, 30, 90] as const;
const WINDOWS = [
  { label: "1–6 h", min: 1, max: 6 },
  { label: "1–12 h", min: 1, max: 12 },
  { label: "6–48 h", min: 6, max: 48 },
] as const;

function Card({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-extrabold tracking-tight">{title}</h2>
        {hint ? <span className="text-xs text-muted">{hint}</span> : null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function InsightsPage() {
  const [days, setDays] = useState<number>(30);
  const [lagWindow, setLagWindow] = useState<(typeof WINDOWS)[number]>(WINDOWS[1]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [lag, setLag] = useState<LagResponse | null>(null);
  const [hours, setHours] = useState<TimeOfDay | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    void Promise.all([
      api.summary(days),
      api.lag({ min_hr: lagWindow.min, max_hr: lagWindow.max, days: Math.max(days, 90), min_count: 3 }),
      api.timeOfDay({ days: Math.max(days, 90), event_type: "symptom" }),
    ])
      .then(([summaryData, lagData, hourData]) => {
        setSummary(summaryData);
        setLag(lagData);
        setHours(hourData);
      })
      .catch(() => setError("Could not load insights."));
  }, [days, lagWindow]);

  const totals = summary?.totals;

  return (
    <div className="px-4 pb-24 pt-2">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold tracking-tight">Insights</h1>
        <div className="flex gap-1 rounded-full border border-line bg-card p-1">
          {RANGES.map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setDays(range)}
              aria-pressed={days === range}
              className={`rounded-full px-3 py-1.5 text-xs font-bold ${
                days === range ? "bg-physio text-white" : "text-muted"
              }`}
            >
              {range}d
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="mt-4 text-sm text-symptom-ink">{error}</p> : null}

      <div className="mt-4 grid grid-cols-4 gap-2">
        {[
          { label: "Physio", value: totals?.exercises ?? 0 },
          { label: "Symptoms", value: totals?.symptoms ?? 0 },
          { label: "Avg sev", value: totals?.avg_symptom_severity != null ? totals.avg_symptom_severity.toFixed(1) : "—" },
          { label: "Streak", value: summary?.exercise_streak_days ?? 0 },
        ].map((stat) => (
          <div key={stat.label} className="rounded-2xl border border-line bg-card px-2 py-3 text-center">
            <p className="text-xl font-extrabold tabular-nums">{stat.value}</p>
            <p className="text-[0.65rem] font-semibold text-muted">{stat.label}</p>
          </div>
        ))}
      </div>

      <Card title="Physio sessions per day" hint="local days">
        <DailyBars
          days={summary?.daily ?? []}
          metric="exercises"
          toneClass="bg-physio"
          emptyLabel="Log a few exercises to fill this in."
        />
      </Card>

      <Card title="Average symptom severity" hint="last 14 days">
        <SeverityTrend days={summary?.daily ?? []} />
      </Card>

      <Card
        title="Symptoms that follow an exercise"
        hint={`${lagWindow.label} window`}
      >
        <div className="mb-3 flex gap-1.5">
          {WINDOWS.map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => setLagWindow(option)}
              aria-pressed={lagWindow.label === option.label}
              className={`rounded-full border px-3 py-1.5 text-xs font-bold ${
                lagWindow.label === option.label
                  ? "border-symptom bg-symptom text-white"
                  : "border-line text-muted"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        {lag && lag.pairs.length > 0 ? (
          <ul className="space-y-2">
            {lag.pairs.slice(0, 8).map((pair) => (
              <li key={`${pair.exercise_id}-${pair.symptom_id}`} className="row-enter rounded-xl bg-canvas p-3">
                <p className="flex items-start gap-2 text-sm leading-snug">
                  <SparkIcon className="mt-0.5 h-4 w-4 shrink-0 text-symptom-ink" />
                  <span>
                    <strong>{pair.symptom_name}</strong> appeared{" "}
                    <strong>{pair.post_exercise_occurrences}×</strong> within {lagWindow.label} of{" "}
                    <strong>{pair.exercise_name}</strong> (avg lag {pair.avg_lag_hours} h, avg
                    severity {pair.avg_severity}/10).
                  </span>
                </p>
                {pair.share_of_symptom_logs !== null ? (
                  <p className="mt-1 text-xs text-muted">
                    {Math.round(pair.share_of_symptom_logs * 100)}% of all {pair.symptom_name}{" "}
                    entries in this range
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">
            Nothing crosses the 3-occurrence bar yet in this window. Keep logging — this is the
            table that finds your flares.
          </p>
        )}
      </Card>

      <Card title="When symptoms hit" hint="24 h, local time">
        {hours ? <HourBars data={hours} /> : <p className="text-sm text-muted">Loading…</p>}
      </Card>

      <Card title="Most logged" hint={`last ${days} days`}>
        <div className="grid grid-cols-2 gap-3">
          <TopList title="Exercises" rows={summary?.top_exercises ?? []} />
          <TopList title="Symptoms" rows={summary?.top_symptoms ?? []} withSeverity />
        </div>
      </Card>
    </div>
  );
}

function TopList({
  title,
  rows,
  withSeverity = false,
}: {
  title: string;
  rows: { id: string; name: string; count: number; avg_severity: number | null }[];
  withSeverity?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-bold text-muted">{title}</p>
      {rows.length === 0 ? (
        <p className="mt-1 text-sm text-muted">No entries yet.</p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {rows.slice(0, 5).map((row) => (
            <li key={row.id} className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate font-semibold">{row.name}</span>
              <span className="shrink-0 tabular-nums text-muted">
                {row.count}
                {withSeverity && row.avg_severity !== null ? ` · ${row.avg_severity}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
