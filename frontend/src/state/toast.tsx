/* Undo toast: one bottom pill, 5 seconds, no confirmation dialogs anywhere. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { CheckDrawIcon, UndoIcon } from "../components/icons/Ui";

export interface ToastOptions {
  label: string;
  undo?: () => void | Promise<void>;
  tone?: "physio" | "symptom" | "relief" | "trigger" | "danger";
}

interface ToastValue {
  show: (options: ToastOptions) => void;
  dismiss: () => void;
}

const ToastContext = createContext<ToastValue | null>(null);
const LIFETIME_MS = 5000;

const toneClasses: Record<NonNullable<ToastOptions["tone"]>, string> = {
  physio: "bg-physio text-white",
  symptom: "bg-symptom text-white",
  relief: "bg-relief text-white",
  trigger: "bg-trigger text-white",
  danger: "bg-ink text-canvas",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<(ToastOptions & { key: number }) | null>(null);
  const timer = useRef<number | null>(null);

  const dismiss = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    setToast(null);
  }, []);

  const show = useCallback(
    (options: ToastOptions) => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      setToast({ ...options, key: Date.now() });
      timer.current = window.setTimeout(dismiss, LIFETIME_MS);
    },
    [dismiss],
  );

  useEffect(() => () => void (timer.current !== null && window.clearTimeout(timer.current)), []);

  const value = useMemo<ToastValue>(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast ? (
        <div
          className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+5.25rem)] z-50 flex justify-center px-4"
          role="status"
          aria-live="polite"
        >
          <div
            key={toast.key}
            className={`toast-enter pointer-events-auto flex max-w-full items-center gap-3 rounded-full py-2.5 pe-2 ps-4 shadow-lg ${
              toneClasses[toast.tone ?? "danger"]
            }`}
          >
            <CheckDrawIcon className="h-5 w-5 shrink-0" />
            <span className="truncate text-sm font-semibold">{toast.label}</span>
            {toast.undo ? (
              <button
                type="button"
                onClick={() => {
                  void toast.undo?.();
                  dismiss();
                }}
                className="flex items-center gap-1.5 rounded-full bg-black/15 px-3 py-1.5 text-sm font-bold"
              >
                <UndoIcon className="h-4 w-4" />
                Undo
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
