/* One shared "log it now, offer Undo" path for every tap-to-log surface. */

import { useCallback } from "react";

import { ApiError, api } from "../api/client";
import type { EventType } from "../api/types";
import { useToast } from "../state/toast";
import { localTzOffsetMin } from "./time";

const toneByType = { exercise: "physio", symptom: "symptom", context: "relief" } as const;

export interface QuickLogger {
  log: (
    event: "exercise" | "symptom" | "context",
    body: Record<string, unknown>,
    label: string,
  ) => Promise<boolean>;
  remove: (type: EventType, id: string, label: string) => Promise<void>;
}

export function useQuickLog(onLogged?: () => void): QuickLogger {
  const toast = useToast();

  const log = useCallback(
    async (event: "exercise" | "symptom" | "context", body: Record<string, unknown>, label: string) => {
      const payload = { ...body, tz_offset_min: localTzOffsetMin() };
      try {
        const created =
          event === "exercise"
            ? await api.logExercise(payload)
            : event === "symptom"
              ? await api.logSymptom(payload)
              : await api.logContext(payload);
        toast.show({
          label,
          tone: toneByType[event],
          undo: () => void api.deleteLog(event, created.id).then(() => onLogged?.()),
        });
        onLogged?.();
        return true;
      } catch (error) {
        toast.show({
          label: error instanceof ApiError ? error.message : "Could not save — try again",
          tone: "danger",
        });
        return false;
      }
    },
    [toast, onLogged],
  );

  const remove = useCallback(
    async (type: EventType, id: string, label: string) => {
      try {
        await api.deleteLog(type, id);
        toast.show({ label, tone: "danger" });
        onLogged?.();
      } catch {
        toast.show({ label: "Could not delete", tone: "danger" });
      }
    },
    [toast, onLogged],
  );

  return { log, remove };
}
