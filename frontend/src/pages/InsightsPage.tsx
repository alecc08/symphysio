/* Insights: counts, the association card, and one symptom against its own start.

Every card here shares one rule: it says what is missing instead of drawing a
confident shape over two data points. The gate lives on the server
(app/insights/sufficiency.py) and its state arrives with each response.
*/

import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type {
  Associations,
  PlanEvent,
  Summary,
  TimeOfDay,
} from "../api/types";
import { AssociationCard } from "../components/AssociationCard";
import { DailyBars, HourBars, SeverityTrend } from "../components/Charts";
import { PlanEventsCard } from "../components/PlanEventsCard";
import { SymptomTrendCard } from "../components/SymptomTrendCard";
import { useCatalog } from "../state/catalog";
import { useSession } from "../state/session";

const RANGES = [7, 30, 90] as const;

function Card({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
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
  const [summary, setSummary] = useState<Summary | null>(null);
  const [hours, setHours] = useState<TimeOfDay | null>(null);
  const [lag, setLag] = useState<Associations | null>(null);
  const [windowLabel, setWindowLabel] = useState<string | null>(null);
  const [planEvents, setPlanEvents] = useState<PlanEvent[]>([]);
  const [trendId, setTrendId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const { symptoms } = useCatalog();
  const { user } = useSession();

  const load = useCallback(async () => {
    setError(null);
    try {
      const [summaryData, hourData, lagData, events] = await Promise.all([
        api.summary(days),
        api.timeOfDay({ days: Math.max(days, 90), event_type: "symptom" }),
        api.associations({ days: 90, ...(windowLabel ? { window: windowLabel } : {}) }),
        api.planEvents({ limit: 30 }),
      ]);
      setSummary(summaryData);
      setHours(hourData);
      setLag(lagData);
      setPlanEvents(events);
      // The profile's own default window, until the person picks one.
      setWindowLabel((current) => current ?? lagData.window.label);
    } catch {
      setError("Could not load insights.");
    }
  }, [days, windowLabel]);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = summary?.totals;
  const adherence = summary?.adherence;
  const live = symptoms.filter((row) => !row.is_archived);

  // Something has to be picked for the trend card to say anything, and the first
  // symptom in the person's own order is the least surprising default.
  useEffect(() => {
    if (!trendId && live.length > 0) setTrendId(live[0].id);
  }, [live, trendId]);

  return (
    <div className="print-report px-4 pb-24 pt-2">
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

      {/* The appointment use case, with no extra page and no PDF endpoint: this page
          is already the report, and print.css strips the chrome. */}
      <button
        type="button"
        onClick={() => window.print()}
        className="screen-only mt-3 rounded-xl border border-line bg-card px-3 py-2 text-xs font-bold text-muted"
      >
        Print for physio
      </button>
      <div className="print-only mb-3 border-b border-line pb-2">
        <p className="text-base font-extrabold">Symphysio — diary summary</p>
        <p className="text-xs text-muted">
          {user?.email ? `${user.email} · ` : ""}last {days} days ·{" "}
          {new Date().toLocaleDateString()}
        </p>
      </div>

      {error ? <p className="mt-4 text-sm text-symptom-ink">{error}</p> : null}

      <div className="mt-4 grid grid-cols-4 gap-2">
        {[
          { label: "Physio", value: totals?.exercises ?? 0 },
          { label: "Symptoms", value: totals?.symptoms ?? 0 },
          {
            label: "Avg sev",
            value: totals?.avg_symptom_severity != null ? totals.avg_symptom_severity.toFixed(1) : "—",
          },
          { label: "Streak", value: summary?.exercise_streak_days ?? 0 },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-2xl border border-line bg-card px-2 py-3 text-center"
          >
            <p className="text-xl font-extrabold tabular-nums">{stat.value}</p>
            <p className="text-[0.65rem] font-semibold text-muted">{stat.label}</p>
          </div>
        ))}
      </div>
      {totals && totals.severity_defaults > 0 ? (
        <p className="mt-1.5 text-xs text-faint">
          {totals.severity_defaults} of those symptom entries used the default severity, not a
          chosen one — the average mixes both.
        </p>
      ) : null}

      <Card title="Keeping the programme" hint="whole weeks">
        {summary && summary.coverage.state === "none" ? (
          <p className="text-sm text-muted">Nothing logged in these {days} days yet.</p>
        ) : adherence ? (
          <p className="text-sm leading-relaxed">
            Programme done on <strong>{adherence.days_with_exercise}</strong> of{" "}
            <strong>{adherence.days_covered}</strong> days — about{" "}
            <strong>{adherence.adherence_per_week}</strong> sessions a week against a target of{" "}
            {adherence.target_days_per_week}.
            {adherence.sessions_skipped > 0 ? (
              <>
                {" "}
                {adherence.sessions_skipped} session{adherence.sessions_skipped === 1 ? "" : "s"}{" "}
                logged as skipped, which still counts as keeping track.
              </>
            ) : null}
          </p>
        ) : (
          <p className="text-sm text-muted">Loading…</p>
        )}
      </Card>

      {lag && windowLabel ? (
        <AssociationCard data={lag} windowLabel={windowLabel} onWindow={setWindowLabel} />
      ) : (
        <Card title="What follows a session?">
          <p className="text-sm text-muted">Loading…</p>
        </Card>
      )}

      <Card title="One symptom over time" hint="vs its own first 2 weeks">
        {live.length === 0 ? (
          <p className="text-sm text-muted">No symptoms in your list yet.</p>
        ) : (
          <>
            {/* A select, not a strip of chips: ten symptom names do not fit a phone
                and a clipped chip is not a choice. */}
            <label className="mt-1 block text-xs font-semibold text-muted" htmlFor="trend-symptom">
              Which symptom?
            </label>
            <select
              id="trend-symptom"
              value={trendId}
              onChange={(event) => setTrendId(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-base font-semibold"
            >
              {live.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
            {trendId ? <SymptomTrendCard definitionId={trendId} /> : null}
          </>
        )}
      </Card>

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

      <Card title="When symptoms hit" hint="24 h, local time">
        {hours ? <HourBars data={hours} /> : <p className="text-sm text-muted">Loading…</p>}
      </Card>

      <PlanEventsCard events={planEvents} onChanged={() => void load()} />

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
