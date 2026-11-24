/* Plan events: the appointment layer.

A trend line steps and the diary cannot say why. This is where "she changed the
programme on the 14th" goes, so the step has a reason next to it. Five coarse
kinds and one line of text — deliberately not a medical record.
*/

import { useCallback, useState } from "react";

import { ApiError, api } from "../api/client";
import type { PlanEvent } from "../api/types";
import { formatDay } from "../lib/time";

const KINDS: { key: PlanEvent["kind"]; label: string }[] = [
  { key: "appointment", label: "Appointment" },
  { key: "programme_change", label: "Programme change" },
  { key: "medication", label: "Medication" },
  { key: "goal", label: "Goal" },
  { key: "note", label: "Note" },
];

export function PlanEventsCard({
  events,
  onChanged,
}: {
  events: PlanEvent[];
  onChanged: () => void;
}) {
  const [kind, setKind] = useState<PlanEvent["kind"]>("appointment");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = useCallback(async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createPlanEvent({
        kind,
        text: text.trim(),
        tz_offset_min: -new Date().getTimezoneOffset(),
      });
      setText("");
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save that.");
    } finally {
      setBusy(false);
    }
  }, [busy, kind, onChanged, text]);

  const remove = useCallback(
    async (id: string) => {
      await api.deletePlanEvent(id).catch(() => setError("Could not delete that."));
      onChanged();
    },
    [onChanged],
  );

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-extrabold tracking-tight">Plan events</h2>
        <span className="text-xs text-muted">appointments, changes, medication</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {KINDS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setKind(option.key)}
            aria-pressed={kind === option.key}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold ${
              kind === option.key ? "border-physio bg-physio text-white" : "border-line text-muted"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-2 flex gap-2">
        <input
          value={text}
          maxLength={300}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void add();
            }
          }}
          placeholder="What changed?"
          aria-label="Plan event"
          className="min-w-0 flex-1 rounded-xl border border-line bg-canvas px-3 py-2.5 text-sm"
        />
        <button
          type="button"
          onClick={() => void add()}
          disabled={!text.trim() || busy}
          className="rounded-xl bg-physio px-4 py-2.5 text-sm font-extrabold text-white disabled:opacity-50"
        >
          Add
        </button>
      </div>

      {error ? <p className="mt-2 text-xs text-symptom-ink">{error}</p> : null}

      {events.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          None yet. When your physio changes the programme, note it here — that is the
          one thing that explains a step change in a trend.
        </p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {events.map((event) => (
            <li key={event.id} className="row-enter rounded-xl bg-canvas p-3">
              {/* The text is the point, so it gets the whole line; date, kind and
                  delete go underneath, where they cannot squeeze it. */}
              <p className="text-sm leading-snug">{event.text}</p>
              <p className="mt-1.5 flex items-center gap-2 text-xs text-muted">
                <span className="font-bold tabular-nums">{formatDay(event.occurred_at_utc)}</span>
                <span className="font-bold uppercase text-faint">
                  {event.kind.replace("_", " ")}
                </span>
                <button
                  type="button"
                  onClick={() => void remove(event.id)}
                  aria-label={`Delete plan event: ${event.text}`}
                  className="ms-auto font-bold text-muted underline"
                >
                  Delete
                </button>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
