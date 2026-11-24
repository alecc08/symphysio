/* Plan events: the appointment layer.

A trend line steps and the diary cannot say why. This is where "she changed the
programme on the 14th" goes, so the step has a reason next to it. Five coarse
kinds and one line of text — deliberately not a medical record.
*/

import { useCallback, useState } from "react";

import { ApiError, api } from "../api/client";
import type { PlanEvent } from "../api/types";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";
import { planKindLabel } from "../lib/enums";
import { formatters } from "../lib/time";

/** The five kinds, in the form each surface needs: title case on the chips,
 *  lower case inside a sentence. Both come from the dictionary; the `key` stays
 *  the API's own token. */
const KINDS: { key: PlanEvent["kind"]; labelKey: MessageKey }[] = [
  { key: "appointment", labelKey: "plan.chip.appointment" },
  { key: "programme_change", labelKey: "plan.chip.programme_change" },
  { key: "medication", labelKey: "plan.chip.medication" },
  { key: "goal", labelKey: "plan.chip.goal" },
  { key: "note", labelKey: "plan.chip.note" },
];

export function PlanEventsCard({
  events,
  onChanged,
}: {
  events: PlanEvent[];
  onChanged: () => void;
}) {
  const { t, tag } = useI18n();
  const fmt = formatters(tag);
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
      setError(caught instanceof ApiError ? caught.message : t("plan.addFailed"));
    } finally {
      setBusy(false);
    }
  }, [busy, kind, onChanged, t, text]);

  const remove = useCallback(
    async (id: string) => {
      await api.deletePlanEvent(id).catch(() => setError(t("plan.deleteFailed")));
      onChanged();
    },
    [onChanged, t],
  );

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-extrabold tracking-tight">{t("plan.title")}</h2>
        <span className="text-xs text-muted">{t("plan.subtitle")}</span>
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
            {t(option.labelKey)}
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
          placeholder={t("plan.whatChanged")}
          aria-label={t("plan.eventAria")}
          className="min-w-0 flex-1 rounded-xl border border-line bg-canvas px-3 py-2.5 text-sm"
        />
        <button
          type="button"
          onClick={() => void add()}
          disabled={!text.trim() || busy}
          className="rounded-xl bg-physio px-4 py-2.5 text-sm font-extrabold text-white disabled:opacity-50"
        >
          {t("common.add")}
        </button>
      </div>

      {error ? <p className="mt-2 text-xs text-symptom-ink">{error}</p> : null}

      {events.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{t("plan.empty")}</p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {events.map((event) => (
            <li key={event.id} className="row-enter rounded-xl bg-canvas p-3">
              {/* The text is the point, so it gets the whole line; date, kind and
                  delete go underneath, where they cannot squeeze it. */}
              <p className="text-sm leading-snug">{event.text}</p>
              <p className="mt-1.5 flex items-center gap-2 text-xs text-muted">
                <span className="font-bold tabular-nums">{fmt.day(event.occurred_at_utc)}</span>
                <span className="font-bold uppercase text-faint">
                  {planKindLabel(event.kind, t)}
                </span>
                <button
                  type="button"
                  onClick={() => void remove(event.id)}
                  aria-label={t("plan.deleteAria", { text: event.text })}
                  className="ms-auto font-bold text-muted underline"
                >
                  {t("common.delete")}
                </button>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
