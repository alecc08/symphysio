/* The quick-log drawer. Tile tap -> this sheet -> one more tap = saved.

   Presets are fully user-owned: add one inline (with suggested postnatal names
   offered while you type) or remove one from its corner — both undo-able.
*/

import { useEffect, useMemo, useState } from "react";

import { api, type CatalogKind } from "../api/client";
import type {
  ContextDefinition,
  ExerciseDefinition,
  Suggestion,
  SymptomDefinition,
} from "../api/types";
import { presetBody, type PresetInput } from "../lib/presets";
import { useQuickLog } from "../lib/useQuickLog";
import { useCatalog } from "../state/catalog";
import { useToast } from "../state/toast";
import { Sheet } from "./Sheet";
import { SeverityScale, DurationChips } from "./SeverityScale";
import { TimeChips } from "./TimeChips";
import { CloseIcon, PlusIcon } from "./icons/Ui";

export type SheetKind = "physio" | "symptoms" | "relief" | "triggers";

/** The drawer's starting severity. Loudly labelled in the UI, and stored as
 *  `severity_default = 1` on the row, so it never quietly becomes a measurement. */
const DEFAULT_SEVERITY = 5;

const SHEET_META: Record<
  SheetKind,
  { title: string; subtitle: string; tone: "physio" | "symptom" | "relief" | "trigger"; kind: CatalogKind }
> = {
  physio: { title: "Physio", subtitle: "Tap the exercise you did.", tone: "physio", kind: "exercises" },
  symptoms: {
    title: "Symptoms",
    subtitle: "Pick severity, then the symptom.",
    tone: "symptom",
    kind: "symptoms",
  },
  relief: { title: "Relief / Meds", subtitle: "What you took or tried.", tone: "relief", kind: "contexts" },
  triggers: {
    title: "Triggers / Activity",
    subtitle: "What might have set it off.",
    tone: "trigger",
    kind: "contexts",
  },
};

function doseFor(item: ExerciseDefinition): string {
  const parts: string[] = [];
  if (item.default_sets != null && item.default_reps != null)
    parts.push(`${item.default_sets}×${item.default_reps}`);
  else if (item.default_sets != null) parts.push(`${item.default_sets} sets`);
  else if (item.default_reps != null) parts.push(`${item.default_reps} reps`);
  if (item.default_sec != null) parts.push(`${item.default_sec}s`);
  if (item.body_region) parts.push(item.body_region.replaceAll("_", " "));
  return parts.join(" · ");
}

function subtitleFor(kind: SheetKind, item: { name: string }): string {
  if (kind === "physio") return doseFor(item as ExerciseDefinition);
  if (kind === "symptoms")
    return ((item as SymptomDefinition).body_region ?? "").replaceAll("_", " ");
  return (item as ContextDefinition).category;
}

export function QuickSheet({
  kind,
  onClose,
  onLogged,
}: {
  kind: SheetKind;
  onClose: () => void;
  onLogged: () => void;
}) {
  const catalog = useCatalog();
  const toast = useToast();
  const { log } = useQuickLog(onLogged);
  const meta = SHEET_META[kind];

  const [occurredAt, setOccurredAt] = useState(() => Math.floor(Date.now() / 1000));
  const [severity, setSeverity] = useState<number | null>(null);
  const [durationMin, setDurationMin] = useState<number | null>(null);
  const [effort, setEffort] = useState<number | null>(null);
  const [pain, setPain] = useState<number | null>(null);
  const [intensity, setIntensity] = useState<number | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  // What a tile tap means in the Physio drawer: did it, or did not do it.
  const [skipped, setSkipped] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  useEffect(() => {
    if (!adding) return;
    void api
      .suggestions(meta.kind)
      .then((list) => setSuggestions(list.slice(0, 10)))
      .catch(() => setSuggestions([]));
  }, [adding, meta.kind]);

  const items = useMemo(() => {
    if (kind === "physio") return catalog.exercises;
    if (kind === "symptoms") return catalog.symptoms;
    return catalog.contexts.filter((item: ContextDefinition) =>
      kind === "relief" ? item.category === "relief" : item.category === "trigger",
    );
  }, [kind, catalog]);

  // The most recent symptom entry's number, offered back as one tap. Named in the
  // chip, because "last time" across several symptoms is otherwise a guess.
  const rememberedSeverity = useMemo(() => {
    if (kind !== "symptoms") return null;
    const recent = catalog.symptoms
      .filter((item) => item.last_severity != null && item.last_logged_utc != null)
      .sort((a, b) => (b.last_logged_utc ?? 0) - (a.last_logged_utc ?? 0))[0];
    return recent ? { value: recent.last_severity as number, name: recent.name } : null;
  }, [catalog.symptoms, kind]);

  const accent = {
    physio: "border-physio/25 bg-physio-soft",
    symptoms: "border-symptom/25 bg-symptom-soft",
    relief: "border-relief/25 bg-relief-soft",
    triggers: "border-trigger/25 bg-trigger-soft",
  }[kind];

  async function addPreset(input: PresetInput) {
    const trimmed = input.name.trim();
    if (!trimmed) return;
    try {
      await catalog.create(
        meta.kind,
        // A typed name in the Triggers drawer must become a trigger, not the
        // helper's generic fallback.
        presetBody(meta.kind, input, {
          category: kind === "relief" ? "relief" : "trigger",
        }),
      );
      setNewName("");
      toast.show({ label: `Added: ${trimmed}` });
    } catch (error) {
      toast.show({ label: error instanceof Error ? error.message : "Could not add" });
    }
  }

  async function removePreset(item: { id: string; name: string }) {
    try {
      await catalog.patch(meta.kind, item.id, { is_archived: true });
      toast.show({
        label: `Removed: ${item.name}`,
        undo: () => void catalog.patch(meta.kind, item.id, { is_archived: false }),
      });
    } catch {
      toast.show({ label: "Could not remove" });
    }
  }

  const logItem = async (item: { id: string; name: string }) => {
    const at = occurredAt;
    if (kind === "physio") {
      const ok = await log(
        "exercise",
        {
          exercise_id: item.id,
          // A session you did not do is still a record: it is the difference
          // between "the programme worked" and "the programme stopped", and the
          // association maths leaves these out while adherence keeps counting them.
          sets_done: skipped ? 0 : null,
          reps_done: skipped ? 0 : null,
          effort_rpe: skipped ? null : effort,
          pain_during: skipped ? null : pain,
          occurred_at_utc: at,
        },
        skipped ? `Skipped: ${item.name}` : `Logged: ${item.name}`,
      );
      if (ok) onClose();
      return;
    }
    if (kind === "symptoms") {
      // 5 is the drawer's default, not the person's answer, and the row says which
      // it was: an average that mixes chosen numbers with defaults has to be
      // honest about it, in history, in the export and in every insight built on it.
      const chosen = severity !== null;
      const value = severity ?? DEFAULT_SEVERITY;
      const ok = await log(
        "symptom",
        {
          symptom_id: item.id,
          severity: value,
          severity_default: !chosen,
          duration_min: durationMin,
          occurred_at_utc: at,
        },
        chosen ? `Logged: ${item.name} · ${value}/10` : `Logged: ${item.name} · 5 (default)`,
      );
      if (ok) onClose();
      return;
    }
    const ok = await log(
      "context",
      { context_id: item.id, intensity, occurred_at_utc: at },
      `Logged: ${item.name}`,
    );
    if (ok) onClose();
  };

  return (
    <Sheet title={meta.title} subtitle={meta.subtitle} tone={meta.tone} onClose={onClose}>
      {kind === "symptoms" ? (
        <SeverityScale
          value={severity ?? DEFAULT_SEVERITY}
          onChange={setSeverity}
          isDefault={severity === null}
          last={rememberedSeverity}
        />
      ) : null}
      {kind === "symptoms" ? <DurationChips value={durationMin} onChange={setDurationMin} /> : null}

      {kind === "physio" ? (
        <div className="mt-1">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDetails((open) => !open)}
              aria-expanded={showDetails}
              className="text-sm font-semibold text-muted underline decoration-dotted"
            >
              {showDetails ? "Hide effort & pain" : "Add effort / pain (optional)"}
            </button>
            {/* One control that changes what a tile tap means, rather than a second
                set of tiles: skipping is the common case, and it should not need a
                different place in the UI to be honest about it. */}
            <button
              type="button"
              onClick={() => setSkipped((on) => !on)}
              aria-pressed={skipped}
              className={`rounded-full border px-3 py-1.5 text-xs font-bold ${
                skipped ? "border-trigger bg-trigger text-white" : "border-line text-muted"
              }`}
            >
              Did not do it today
            </button>
          </div>
          {skipped ? (
            <p className="mt-2 text-xs leading-snug text-muted">
              Tapping an exercise will log it as skipped — it still counts as keeping
              track, and it is left out of the “what follows a session” maths.
            </p>
          ) : null}
          {showDetails ? (
            <>
              <SeverityScale value={effort} onChange={setEffort} label="Effort (RPE)" />
              <PainRow value={pain} onChange={setPain} />
            </>
          ) : null}
        </div>
      ) : null}

      {kind === "relief" || kind === "triggers" ? (
        <SeverityScale value={intensity} onChange={setIntensity} label="Intensity (optional)" />
      ) : null}

      <TimeChips value={occurredAt} onChange={setOccurredAt} />

      <div className="mt-5 grid grid-cols-2 gap-2.5">
        {items.map((item) => (
          <div key={item.id} className="relative">
            <button
              type="button"
              onClick={() => void logItem(item)}
              className={`log-tile min-h-[4.5rem] w-full rounded-2xl border px-3 pt-2.5 pb-2.5 text-start ${accent}`}
            >
              <span className="block text-[0.95rem] leading-tight font-bold text-ink">
                {item.name}
              </span>
              <span className="mt-1 block text-xs font-semibold opacity-75">
                {subtitleFor(kind, item)}
              </span>
            </button>
            <button
              type="button"
              onClick={() => void removePreset(item)}
              aria-label={`Remove ${item.name}`}
              className="absolute -top-1.5 -right-1.5 rounded-full border border-line bg-card p-1 text-muted shadow-sm"
            >
              <CloseIcon className="h-3 w-3" />
            </button>
          </div>
        ))}

        <button
          type="button"
          onClick={() => setAdding((open) => !open)}
          aria-expanded={adding}
          className="flex min-h-[4.5rem] items-center justify-center gap-2 rounded-2xl border border-dashed border-line bg-card text-sm font-bold text-muted"
        >
          <PlusIcon className="h-4 w-4" />
          Add preset
        </button>
      </div>

      {adding ? (
        <div className="mt-3 rounded-2xl border border-line bg-canvas p-3">
          <div className="flex gap-2">
            <input
              autoFocus
              value={newName}
              maxLength={80}
              placeholder={kind === "symptoms" ? "e.g. Pressure when standing" : "New preset name"}
              onChange={(event) => setNewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void addPreset({ name: newName });
              }}
              className="min-w-0 flex-1 rounded-lg border border-line bg-card px-2.5 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void addPreset({ name: newName })}
              disabled={!newName.trim()}
              className="rounded-lg bg-physio px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
            >
              Add
            </button>
          </div>
          {suggestions.length > 0 ? (
            <>
              <p className="mt-3 text-xs font-semibold text-muted">Or tap a suggestion</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion.name}
                    type="button"
                    onClick={() => void addPreset(suggestion)}
                    className="rounded-full border border-line bg-card px-3 py-1.5 text-xs font-semibold"
                  >
                    {suggestion.name}
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      <p className="mt-4 text-xs text-muted">
        Presets are yours — add, remove and reorder them here or in Settings. Removed presets keep
        their history.
      </p>
    </Sheet>
  );
}

function PainRow({ value, onChange }: { value: number | null; onChange: (value: number) => void }) {
  return (
    <div className="mt-4">
      <div className="text-xs font-semibold text-muted">Pain during</div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Array.from({ length: 11 }, (_, index) => index).map((number) => (
          <button
            key={number}
            type="button"
            aria-pressed={value === number}
            onClick={() => onChange(value === number ? 0 : number)}
            className={`h-10 w-10 rounded-lg border text-sm font-bold tabular-nums ${
              value === number ? "border-symptom bg-symptom text-white" : "border-line bg-canvas text-muted"
            }`}
          >
            {number}
          </button>
        ))}
      </div>
    </div>
  );
}
