import type { CatalogKind } from "../api/client";
import type { Suggestion } from "../api/types";

/** Anything the add-preset UI can hand in: a typed name, or a server suggestion. */
export type PresetInput = { name: string } & Omit<Suggestion, "name">;

/**
 * Build a `POST /catalog/{kind}` body.
 *
 * Each kind has its own strict create model (`extra = "forbid"` on the server)
 * and they use different field names — `body_region` + dose for exercises,
 * `default_region` for symptoms, `category` for contexts — so the body is
 * written out per kind instead of merging one bag of fields.
 */
export function presetBody(
  kind: CatalogKind,
  input: PresetInput,
  defaults: {
    sets?: number | null;
    reps?: number | null;
    category?: "relief" | "trigger";
  } = {},
): Record<string, unknown> {
  const name = input.name.trim();
  if (kind === "exercises") {
    // `in` rather than `??`: a suggestion can carry an explicit null (a 30 s
    // stretch has no reps), and that must not silently inherit the default dose.
    return {
      name,
      body_region: input.body_region ?? null,
      default_sets: "default_sets" in input ? input.default_sets : (defaults.sets ?? 3),
      default_reps: "default_reps" in input ? input.default_reps : (defaults.reps ?? 10),
      default_sec: "default_sec" in input ? input.default_sec : null,
    };
  }
  if (kind === "symptoms") {
    return { name, default_region: input.default_region ?? null };
  }
  return { name, category: input.category ?? defaults.category ?? "relief" };
}
