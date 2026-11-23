/* Bottom sheet for quick-log drawers: slide-up, backdrop, Esc/backdrop to close. */

import { useEffect, type ReactNode } from "react";

import { CloseIcon } from "./icons/Ui";

const toneAccent: Record<string, string> = {
  physio: "bg-physio",
  symptom: "bg-symptom",
  relief: "bg-relief",
  trigger: "bg-trigger",
};

export function Sheet({
  title,
  subtitle,
  tone = "physio",
  onClose,
  children,
}: {
  title: string;
  subtitle?: string;
  tone?: keyof typeof toneAccent;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-[1px]"
      />
      <div className="sheet-enter app-shell relative w-full max-w-lg rounded-t-3xl bg-card pb-[calc(env(safe-area-inset-bottom)+1rem)] shadow-2xl">
        <div className="flex items-center justify-between px-5 pt-4">
          <span className={`h-1.5 w-10 rounded-full ${toneAccent[tone]}`} aria-hidden="true" />
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-muted hover:bg-canvas"
            aria-label="Close drawer"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 pt-1 pb-4">
          <h2 className="text-lg font-bold tracking-tight">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-sm text-muted">{subtitle}</p> : null}
        </div>
        <div className="px-5">{children}</div>
      </div>
    </div>
  );
}
