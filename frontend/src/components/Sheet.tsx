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
      {/* The panel used to be as tall as its content and bottom-anchored, so a full
          sheet grew off the top of the screen instead of scrolling: measured on a
          390x664 phone (a 390x844 viewport minus browser chrome) the Symptoms drawer
          was 986px tall, 322px of it above the fold, and **zero** of the ten severity
          pills on screen — the score you have to pick was unreachable. Same for any
          drawer with enough presets. Height is capped to the viewport and only the
          body scrolls, so the title and the controls above the list stay reachable. */}
      <div className="sheet-enter app-shell relative flex max-h-[88dvh] w-full max-w-lg flex-col rounded-t-3xl bg-card pb-[calc(env(safe-area-inset-bottom)+1rem)] shadow-2xl">
        <div className="flex shrink-0 items-center justify-between px-5 pt-4">
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
        <div className="shrink-0 px-5 pt-1 pb-4">
          <h2 className="text-lg font-bold tracking-tight">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-sm text-muted">{subtitle}</p> : null}
        </div>
        {/* min-h-0 is what makes the flex child actually scroll instead of growing
            the panel; overscroll-contain stops the page behind the backdrop from
            rubber-banding when you hit the end of the list. */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5">{children}</div>
      </div>
    </div>
  );
}
