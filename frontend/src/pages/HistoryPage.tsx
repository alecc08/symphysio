/* Chronological feed with inline edit and delete (delete is Undo-able). */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { TimelineItem } from "../api/types";
import { describeMetric, formatClock, formatDay, relativeLabel } from "../lib/time";
import { useToast } from "../state/toast";
import { Sheet } from "../components/Sheet";
import { SeverityScale } from "../components/SeverityScale";
import { TimeChips } from "../components/TimeChips";
import { ClockIcon, PencilIcon, TrashIcon } from "../components/icons/Ui";
import { PhysioIcon, ReliefIcon, SymptomIcon, TriggerIcon } from "../components/icons/Tile";

const FILTERS = [
  { id: "", label: "All" },
  { id: "exercise", label: "Physio" },
  { id: "symptom", label: "Symptoms" },
  { id: "context", label: "Context" },
] as const;

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
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<TimelineItem | null>(null);

  const load = useCallback(
    async (before?: number) => {
      setLoading(true);
      try {
        const page = await api.timeline({
          limit: 50,
          before,
          ...(filter ? { event_type: filter } : {}),
        });
        setItems((current) => (before ? [...current, ...page.items] : page.items));
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

  const remove = async (item: TimelineItem) => {
    setItems((current) => current.filter((entry) => entry.id !== item.id));
    try {
      await api.deleteLog(item.event_type, item.id);
      toast.show({
        label: `Deleted: ${item.definition_name ?? "entry"}`,
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
      toast.show({ label: "Could not delete", tone: "danger" });
      await load();
    }
  };

  return (
    <div className="px-4 pb-24 pt-2">
      <h1 className="text-2xl font-extrabold tracking-tight">History</h1>
      <div className="mt-3 flex gap-2 overflow-x-auto">
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
            {entry.label}
          </button>
        ))}
      </div>

      <ul className="mt-4 space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="row-enter flex items-center gap-3 rounded-2xl border border-line bg-card px-4 py-3"
          >
            <span className={`flex shrink-0 items-center ${dotFor[item.event_type]}`}>
              <KindGlyph item={item} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[0.95rem] font-bold">
                {item.definition_name ?? "Unknown"}
                {item.category ? (
                  <span className="ml-2 text-xs font-semibold text-muted">{item.category}</span>
                ) : null}
              </p>
              <p className="truncate text-xs text-muted">
                {formatDay(item.occurred_at_utc)} {formatClock(item.occurred_at_utc)} ·{" "}
                {relativeLabel(item.occurred_at_utc)}
                {describeMetric(item) ? ` · ${describeMetric(item)}` : ""}
              </p>
              {item.note ? <p className="mt-1 truncate text-xs text-ink/70">{item.note}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => setEditing(item)}
              aria-label={`Edit ${item.definition_name ?? "entry"}`}
              className="rounded-lg p-2 text-muted hover:bg-canvas"
            >
              <PencilIcon className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={() => void remove(item)}
              aria-label={`Delete ${item.definition_name ?? "entry"}`}
              className="rounded-lg p-2 text-muted hover:bg-symptom-soft hover:text-symptom-ink"
            >
              <TrashIcon className="h-5 w-5" />
            </button>
          </li>
        ))}
      </ul>

      {loading && items.length === 0 ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : null}
      {!loading && items.length === 0 ? (
        <p className="mt-6 text-sm text-muted">Nothing logged in this filter yet.</p>
      ) : null}

      {nextBefore !== null ? (
        <button
          type="button"
          onClick={() => void load(nextBefore)}
          disabled={loading}
          className="mt-4 w-full rounded-xl border border-line bg-card py-3 text-sm font-bold text-muted disabled:opacity-60"
        >
          Load older
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
  const [metric, setMetric] = useState<number | null>(item.primary_metric);
  const [note, setNote] = useState(item.note ?? "");
  const [occurredAt, setOccurredAt] = useState(item.occurred_at_utc);
  const tone = item.event_type === "symptom" ? "symptom" : item.event_type === "exercise" ? "physio" : "relief";
  const label =
    item.event_type === "symptom" ? "Severity" : item.event_type === "exercise" ? "Effort (RPE)" : "Intensity";

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
      toast.show({ label: "Updated", tone });
      onSaved();
    } catch {
      toast.show({ label: "Could not save changes", tone: "danger" });
    }
  }

  return (
    <Sheet title={item.definition_name ?? "Edit entry"} subtitle="Changes keep the original id" tone={tone} onClose={onClose}>
      <SeverityScale value={metric} onChange={setMetric} label={label} />
      <TimeChips value={occurredAt} onChange={setOccurredAt} />
      <label className="mt-4 block text-xs font-semibold text-muted" htmlFor="note">
        Note
      </label>
      <textarea
        id="note"
        value={note}
        rows={3}
        maxLength={500}
        onChange={(event) => setNote(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3 py-2.5 text-base"
        placeholder="What made it better or worse?"
      />
      <div className="mt-4 flex items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <ClockIcon className="h-4 w-4" />
          logged {formatDay(item.logged_at_utc ?? item.occurred_at_utc)}
        </span>
        <button
          type="button"
          onClick={() => void save()}
          className="ms-auto rounded-xl bg-physio px-5 py-3 text-sm font-bold text-white"
        >
          Save
        </button>
      </div>
    </Sheet>
  );
}
