/* Catalog of quick-tap buttons, shared by the Log grid, History and Settings. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, type CatalogKind } from "../api/client";
import type { ContextDefinition, ExerciseDefinition, SymptomDefinition } from "../api/types";

interface CatalogValue {
  exercises: ExerciseDefinition[];
  symptoms: SymptomDefinition[];
  contexts: ContextDefinition[];
  loading: boolean;
  includeArchived: boolean;
  setIncludeArchived: (value: boolean) => void;
  reload: () => Promise<void>;
  create: (kind: CatalogKind, body: Record<string, unknown>) => Promise<void>;
  patch: (kind: CatalogKind, id: string, body: Record<string, unknown>) => Promise<void>;
  reorder: (kind: CatalogKind, ids: string[]) => Promise<void>;
}

const CatalogContext = createContext<CatalogValue | null>(null);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [exercises, setExercises] = useState<ExerciseDefinition[]>([]);
  const [symptoms, setSymptoms] = useState<SymptomDefinition[]>([]);
  const [contexts, setContexts] = useState<ContextDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [includeArchived, setIncludeArchived] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    const params = includeArchived ? { include_archived: true } : {};
    try {
      const [ex, sy, co] = await Promise.all([
        api.catalog<ExerciseDefinition>("exercises", params),
        api.catalog<SymptomDefinition>("symptoms", params),
        api.catalog<ContextDefinition>("contexts", params),
      ]);
      setExercises(ex);
      setSymptoms(sy);
      setContexts(co);
    } finally {
      setLoading(false);
    }
  }, [includeArchived]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const refreshKind = useCallback(
    async (kind: CatalogKind) => {
      const params = includeArchived ? { include_archived: true } : {};
      if (kind === "exercises") setExercises(await api.catalog<ExerciseDefinition>("exercises", params));
      if (kind === "symptoms") setSymptoms(await api.catalog<SymptomDefinition>("symptoms", params));
      if (kind === "contexts") setContexts(await api.catalog<ContextDefinition>("contexts", params));
    },
    [includeArchived],
  );

  const value = useMemo<CatalogValue>(
    () => ({
      exercises,
      symptoms,
      contexts,
      loading,
      includeArchived,
      setIncludeArchived,
      reload,
      create: async (kind, body) => {
        if (kind === "exercises") await api.createExercise(body);
        else if (kind === "symptoms") await api.createSymptom(body);
        else await api.createContext(body);
        await refreshKind(kind);
      },
      patch: async (kind, id, body) => {
        await api.patchCatalog(kind, id, body);
        await refreshKind(kind);
      },
      reorder: async (kind, ids) => {
        await api.reorderCatalog(kind, ids);
        await refreshKind(kind);
      },
    }),
    [exercises, symptoms, contexts, loading, includeArchived, reload, refreshKind],
  );

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}

export function useCatalog(): CatalogValue {
  const value = useContext(CatalogContext);
  if (!value) throw new Error("useCatalog must be used inside CatalogProvider");
  return value;
}
