/* Chronological feed with inline edit and delete (delete is Undo-able). */

import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import type { PlanEvent, TimelineItem } from "../api/types";
import { Sheet } from "../components/Sheet";
import { SeverityScale } from "../components/SeverityScale";
import { TimeChips } from "../components/TimeChips";
import { CalendarIcon, ClockIcon, PencilIcon, TrashIcon } from "../components/icons/Ui";
import { PhysioIcon, ReliefIcon, SymptomIcon, TriggerIcon } from "../components/icons/Tile";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";
import { categoryLabel, planKindLabel } from "../lib/enums";
import { formatters } from "../lib/time";
import { describeMetric, relativeLabel } from "../lib/timeLabels";
import { useToast } from "../state/toast";

const FILTERS: { id: string; labelKey: MessageKey }[] = [
  { id: "", labelKey: "filter.all" },
  { id: "exercise", labelKey: "filter.physio" },
  { id: "symptom", labelKey: "filter.symptoms" },
  { id: "context", labelKey: "filter.context" },
];

/** One line in the feed: a log entry, or a plan event sitting between them. */
type FeedRow =
  | { kind: "log"; at: number; item: TimelineItem }
  | { kind: "plan"; at: number; event: PlanEvent };

const dotFor: Record<TimelineItem["event_type"], string> = {
  exercise: "text-physio-ink",
  symptom: "text-symptom-ink",
  context: "text-relief-ink",
};

/* The feed is read by icon *and* colour, so a context entry picks the relief or
   the trigger glyph rather than a generic dot. */
function KindGlyph({ item }: { item: TimelineItem }) {
  const className = "h-5 w-5 shrink-0";
  if (item.event_type === "exercise") return <PhysioIcon className={className} />;
  if (item.event_type === "symptom") return <SymptomIcon className={className} />;
  return item.category === "trigger" ? (
    <TriggerIcon className={className} />
  ) : (
    <ReliefIcon className={className} />
  );
}

export function HistoryPage() {
  const toast = useToast();
  const { t, tag } = useI18n();
  const fmt = formatters(tag);
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [planEvents, setPlanEvents] = useState<PlanEvent[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<TimelineItem | null>(null);

  const load = useCallback(
    async (before?: number) => {
      setLoading(true);
      try {
        const [page, events] = await Promise.all([
          api.timeline({
            limit: 50,
            before,
            ...(filter ? { event_type: filter } : {}),
          }),
          // The appointment layer is deliberately a separate table, and the timeline
          // view deliberately does not know about it (adding plan_events to
          // v_unified_timeline would silently move every analytics number). So the
          // feed is merged here, in the one place that needs both.
          filter ? Promise.resolve([] as PlanEvent[]) : api.planEvents({ limit: 50 }),
        ]);
        setItems((current) => (before ? [...current, ...page.items] : page.items));
        setPlanEvents(events);
        setNextBefore(page.next_before);
      } finally {
        setLoading(false);
      }
    },
    [filter],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo<FeedRow[]>(() => {
    const logs: FeedRow[] = items.map((item) => ({ kind: "log", at: item.occurred_at_utc, item }));
    const events: FeedRow[] = planEvents.map((event) => ({
      kind: "plan",
      at: event.occurred_at_utc,
      event,
    }));
    return [...logs, ...events].sort((a, b) => b.at - a.at);
  }, [items, planEvents]);

  const remove = async (item: TimelineItem) => {
    setItems((current) => current.filter((entry) => entry.id !== item.id));
    try {
      await api.deleteLog(item.event_type, item.id);
      toast.show({
        label: t("history.deleted", { name: item.definition_name ?? t("history.entry") }),
        tone: "danger",
        undo: async () => {
          const body = rebuildBody(item);
          if (item.event_type === "exercise") await api.logExercise(body);
          else if (item.event_type === "symptom") await api.logSymptom(body);
          else await api.logContext(body);
          await load();
        },
      });
    } catch {
      toast.show({ label: t("history.deleteFailed"), tone: "danger" });
      await load();
    }
  };

  return (
    <div className="px-4 pb-24 pt-2">
      <h1 className="text-2xl font-extrabold tracking-tight">{t("history.title")}</h1>
      {/* Wraps rather than scrolls: four filter chips that need a swipe to see are
          worse than two rows, and a clipped chip is not a choice. */}
      <div className="mt-3 flex flex-wrap gap-2">
        {FILTERS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => setFilter(entry.id)}
            aria-pressed={filter === entry.id}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${
              filter === entry.id
                ? "border-physio bg-physio text-white"
                : "border-line bg-card text-muted"
            }`}
          >
            {t(entry.labelKey)}
          </button>
        ))}
      </div>

      <ul className="mt-4 space-y-2">
        {rows.map((row) =>
          row.kind === "plan" ? (
            <li
              key={`plan-${row.event.id}`}
              className="row-enter flex items-center gap-3 rounded-2xl border border-dashed border-physio/40 bg-physio-soft px-4 py-2.5"
            >
              <span className="flex shrink-0 items-center text-physio-ink">
                <CalendarIcon className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.95rem] font-bold text-physio-ink">
                  {row.event.text}
                </p>
                <p className="truncate text-xs text-muted">
                  {fmt.day(row.event.occurred_at_utc)} ·{" "}
                  {relativeLabel(row.event.occurred_at_utc, t, tag)} ·{" "}
                  {t("plan.prefix", { kind: planKindLabel(row.event.kind, t) })}
                </p>
              </div>
            </li>
          ) : (
            <li
              key={row.item.id}
              className="row-enter flex items-center gap-3 rounded-2xl border border-line bg-card px-4 py-3"
            >
              <span className={`flex shrink-0 items-center ${dotFor[row.item.event_type]}`}>
                <KindGlyph item={row.item} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.95rem] font-bold">
                  {row.item.definition_name ?? t("common.unknown")}
                  {row.item.category ? (
                    <span className="ml-2 text-xs font-semibold text-muted">
                      {categoryLabel(row.item.category, t)}
                    </span>
                  ) : null}
                </p>
                <p className="truncate text-xs text-muted">
                  {fmt.day(row.item.occurred_at_utc)} {fmt.clock(row.item.occurred_at_utc)} ·{" "}
                  {relativeLabel(row.item.occurred_at_utc, t, tag)}
                  {describeMetric(row.item, t) ? ` · ${describeMetric(row.item, t)}` : ""}
                </p>
                {row.item.note ? (
                  <p className="mt-1 truncate text-xs text-ink/70">{row.item.note}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => setEditing(row.item)}
                aria-label={t("history.editAria", {
                  name: row.item.definition_name ?? t("history.entry"),
                })}
                className="rounded-lg p-2 text-muted hover:bg-canvas"
              >
                <PencilIcon className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={() => void remove(row.item)}
                aria-label={t("history.deleteAria", {
                  name: row.item.definition_name ?? t("history.entry"),
                })}
                className="rounded-lg p-2 text-muted hover:bg-symptom-soft hover:text-symptom-ink"
              >
                <TrashIcon className="h-5 w-5" />
              </button>
            </li>
          ),
        )}
      </ul>

      {loading && rows.length === 0 ? (
        <p className="mt-6 text-sm text-muted">{t("app.loading")}</p>
      ) : null}
      {!loading && rows.length === 0 ? (
        <p className="mt-6 text-sm text-muted">{t("history.empty")}</p>
      ) : null}

      {nextBefore !== null ? (
        <button
          type="button"
          onClick={() => void load(nextBefore)}
          disabled={loading}
          className="mt-4 w-full rounded-xl border border-line bg-card py-3 text-sm font-bold text-muted disabled:opacity-60"
        >
          {t("history.loadOlder")}
        </button>
      ) : null}

      {editing ? (
        <EditSheet
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}

function rebuildBody(item: TimelineItem): Record<string, unknown> {
  return {
    ...(item.event_type === "exercise"
      ? {
          exercise_id: item.def_id,
          sets_done: item.sets_done,
          reps_done: item.reps_done,
          duration_sec: item.duration_sec,
          effort_rpe: item.primary_metric,
          pain_during: item.pain_during,
        }
      : item.event_type === "symptom"
        ? {
            symptom_id: item.def_id,
            severity: item.severity ?? item.primary_metric ?? 5,
            // Undo restores the row as it was, including whether that number was
            // the person's or the drawer's default.
            severity_default: item.severity_default === 1,
            body_region: item.body_region,
            duration_min: item.duration_min,
          }
        : { context_id: item.def_id, intensity: item.intensity }),
    occurred_at_utc: item.occurred_at_utc,
    note: item.note,
  };
}

function EditSheet({
  item,
  onClose,
  onSaved,
}: {
  item: TimelineItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const { t, tag } = useI18n();
  const fmt = formatters(tag);
  const [metric, setMetric] = useState<number | null>(item.primary_metric);
  const [note, setNote] = useState(item.note ?? "");
  const [occurredAt, setOccurredAt] = useState(item.occurred_at_utc);
  const tone =
    item.event_type === "symptom"
      ? "symptom"
      : item.event_type === "exercise"
        ? "physio"
        : "relief";
  const labelKey: MessageKey =
    item.event_type === "symptom"
      ? "severity.label"
      : item.event_type === "exercise"
        ? "effort.rpe"
        : "intensity.label";

  async function save() {
    try {
      await api.patchLog(item.event_type, item.id, {
        occurred_at_utc: occurredAt,
        note: note.trim() ? note.trim() : null,
        ...(item.event_type === "symptom"
          ? { severity: metric ?? item.severity }
          : item.event_type === "exercise"
            ? { effort_rpe: metric }
            : { intensity: metric }),
      });
      toast.show({ label: t("history.updated"), tone });
      onSaved();
    } catch {
      toast.show({ label: t("history.saveFailed"), tone: "danger" });
    }
  }

  return (
    <Sheet
      title={item.definition_name ?? t("history.editEntry")}
      subtitle={t("history.changesKeepId")}
      tone={tone}
      onClose={onClose}
    >
      <SeverityScale value={metric} onChange={setMetric} labelKey={labelKey} />
      <TimeChips value={occurredAt} onChange={setOccurredAt} />
      <label className="mt-4 block text-xs font-semibold text-muted" htmlFor="note">
        {t("history.note")}
      </label>
      <textarea
        id="note"
        value={note}
        rows={3}
        maxLength={500}
        onChange={(event) => setNote(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3 py-2.5 text-base"
        placeholder={t("history.notePlaceholder")}
      />
      <div className="mt-4 flex items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <ClockIcon className="h-4 w-4" />
          {t("history.loggedOn", {
            day: fmt.day(item.logged_at_utc ?? item.occurred_at_utc),
          })}
        </span>
        <button
          type="button"
          onClick={() => void save()}
          className="ms-auto rounded-xl bg-physio px-5 py-3 text-sm font-bold text-white"
        >
          {t("common.save")}
        </button>
      </div>
    </Sheet>
  );
}
