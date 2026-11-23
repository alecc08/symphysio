/* Catalog manager: rename, add, reorder, remove and restore the quick-tap buttons. */

import { useEffect, useState } from "react";

import { ApiError, api, type CatalogKind } from "../api/client";
import type {
  ContextDefinition,
  ExerciseDefinition,
  Suggestion,
  SymptomDefinition,
} from "../api/types";
import { presetBody, type PresetInput } from "../lib/presets";
import { useCatalog } from "../state/catalog";
import { useToast } from "../state/toast";
import { ChevronDownIcon, ChevronUpIcon, PlusIcon } from "./icons/Ui";

type Definition = ExerciseDefinition | SymptomDefinition | ContextDefinition;

const KIND_LABEL: Record<CatalogKind, string> = {
  exercises: "Physio presets",
  symptoms: "Symptom presets",
  contexts: "Relief & trigger presets",
};

function subtitleFor(item: Definition): string {
  const exercise = item as ExerciseDefinition;
  const pieces: string[] = [];
  if (exercise.default_sets != null) pieces.push(`${exercise.default_sets} sets`);
  if (exercise.default_reps != null) pieces.push(`${exercise.default_reps} reps`);
  if (exercise.default_sec != null) pieces.push(`${exercise.default_sec}s`);
  const region = (item as { body_region?: string | null }).body_region;
  if (region) pieces.push(region.replaceAll("_", " "));
  const category = (item as ContextDefinition).category;
  if (category) pieces.push(category);
  return pieces.join(" · ");
}

export function CatalogManager({ kinds }: { kinds: CatalogKind[] }) {
  const catalog = useCatalog();
  const toast = useToast();

  const rowsFor = (kind: CatalogKind): Definition[] =>
    kind === "exercises"
      ? catalog.exercises
      : kind === "symptoms"
        ? catalog.symptoms
        : catalog.contexts;

  async function move(kind: CatalogKind, index: number, direction: -1 | 1) {
    const rows = rowsFor(kind);
    const target = index + direction;
    if (target < 0 || target >= rows.length) return;
    const ids = rows.map((row) => row.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await catalog.reorder(kind, ids);
  }

  async function archive(kind: CatalogKind, item: Definition) {
    try {
      await catalog.patch(kind, item.id, { is_archived: !item.is_archived });
      toast.show({ label: item.is_archived ? `Restored: ${item.name}` : `Archived: ${item.name}` });
    } catch (error) {
      toast.show({ label: error instanceof ApiError ? error.message : "Could not update" });
    }
  }

  async function rename(kind: CatalogKind, item: Definition, name: string) {
    if (!name.trim() || name.trim() === item.name) return;
    try {
      await catalog.patch(kind, item.id, { name: name.trim() });
    } catch (error) {
      toast.show({ label: error instanceof ApiError ? error.message : "Could not rename" });
    }
  }

  return (
    <div className="space-y-5">
      <label className="flex items-center gap-2 text-sm font-semibold text-muted">
        <input
          type="checkbox"
          checked={catalog.includeArchived}
          onChange={(event) => catalog.setIncludeArchived(event.target.checked)}
        />
        Show archived presets
      </label>
      {kinds.map((kind) => (
        <section key={kind} className="rounded-2xl border border-line bg-card p-4">
          <h3 className="text-sm font-extrabold">{KIND_LABEL[kind]}</h3>
          <ul className="mt-3 space-y-2">
            {rowsFor(kind).map((item, index) => (
              <li key={item.id} className="flex items-center gap-2">
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => void move(kind, index, -1)}
                    disabled={index === 0}
                    aria-label={`Move ${item.name} up`}
                    className="grid h-6 w-6 place-items-center rounded-md border border-line bg-card text-muted transition-colors hover:text-ink disabled:opacity-25"
                  >
                    <ChevronUpIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void move(kind, index, 1)}
                    disabled={index === rowsFor(kind).length - 1}
                    aria-label={`Move ${item.name} down`}
                    className="grid h-6 w-6 place-items-center rounded-md border border-line bg-card text-muted transition-colors hover:text-ink disabled:opacity-25"
                  >
                    <ChevronDownIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
                <input
                  defaultValue={item.name}
                  onBlur={(event) => void rename(kind, item, event.target.value)}
                  aria-label={`Name of ${item.name}`}
                  className={`min-w-0 flex-1 rounded-lg border border-transparent bg-canvas px-2.5 py-2 text-sm font-semibold ${
                    item.is_archived ? "text-muted line-through" : ""
                  }`}
                />
                <span className="hidden text-xs text-muted sm:block">{subtitleFor(item)}</span>
                <button
                  type="button"
                  onClick={() => void archive(kind, item)}
                  aria-label={`${item.is_archived ? "Restore" : "Remove"} ${item.name}`}
                  className="rounded-lg px-2.5 py-2 text-xs font-bold text-muted hover:bg-canvas"
                >
                  {item.is_archived ? "Restore" : "Remove"}
                </button>
              </li>
            ))}
          </ul>
          <AddRow kind={kind} />
        </section>
      ))}
    </div>
  );
}

function AddRow({ kind }: { kind: CatalogKind }) {
  const catalog = useCatalog();
  const toast = useToast();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"relief" | "trigger">("relief");
  const [sets, setSets] = useState("3");
  const [reps, setReps] = useState("10");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api
      .suggestions(kind)
      .then((list) => setSuggestions(list.slice(0, 8)))
      .catch(() => setSuggestions([]));
  }, [kind]);

  async function add(input: PresetInput) {
    const trimmed = input.name.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await catalog.create(
        kind,
        presetBody(kind, input, {
          sets: Number(sets) || null,
          reps: Number(reps) || null,
          category,
        }),
      );
      setName("");
      toast.show({ label: `Added: ${trimmed}` });
    } catch (error) {
      toast.show({ label: error instanceof ApiError ? error.message : "Could not add" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      <div className="flex gap-2">
        {kind === "contexts" ? (
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value as "relief" | "trigger")}
            aria-label="Context category"
            className="rounded-lg border border-line bg-canvas px-2 py-2 text-sm font-semibold"
          >
            <option value="relief">relief</option>
            <option value="trigger">trigger</option>
          </select>
        ) : null}
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void add({ name });
          }}
          placeholder="New preset name"
          maxLength={80}
          className="min-w-0 flex-1 rounded-lg border border-line bg-canvas px-2.5 py-2 text-sm"
        />
        <button
          type="button"
          onClick={() => void add({ name })}
          disabled={busy || !name.trim()}
          className="flex items-center gap-1 rounded-lg bg-physio px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
        >
          <PlusIcon className="h-4 w-4" />
          Add
        </button>
      </div>

      {kind === "exercises" ? (
        <div className="mt-2 flex items-center gap-2 text-xs text-muted">
          <span>Dose</span>
          <input
            value={sets}
            onChange={(event) => setSets(event.target.value.replace(/\D/g, "").slice(0, 2))}
            aria-label="Default sets"
            inputMode="numeric"
            className="w-12 rounded-lg border border-line bg-canvas px-2 py-1.5 text-center text-sm font-semibold"
          />
          <span>sets ×</span>
          <input
            value={reps}
            onChange={(event) => setReps(event.target.value.replace(/\D/g, "").slice(0, 3))}
            aria-label="Default reps"
            inputMode="numeric"
            className="w-14 rounded-lg border border-line bg-canvas px-2 py-1.5 text-center text-sm font-semibold"
          />
          <span>reps</span>
        </div>
      ) : null}

      {suggestions.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold text-muted">Suggested — tap to add</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.name}
                type="button"
                onClick={() => void add(suggestion)}
                className="rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-semibold"
              >
                + {suggestion.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
