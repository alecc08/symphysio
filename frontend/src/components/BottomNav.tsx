/* Three tabs only. Settings live behind the top-right gear. */

import type { MessageKey } from "../i18n/en";
import { useI18n } from "../i18n";
import { GridIcon, HistoryIcon, InsightsIcon } from "./icons/Ui";

export type Tab = "log" | "history" | "insights";

const TABS: { id: Tab; labelKey: MessageKey; icon: (className: string) => React.ReactNode }[] = [
  { id: "log", labelKey: "nav.log", icon: (c) => <GridIcon className={c} /> },
  { id: "history", labelKey: "nav.history", icon: (c) => <HistoryIcon className={c} /> },
  { id: "insights", labelKey: "nav.insights", icon: (c) => <InsightsIcon className={c} /> },
];

export function BottomNav({ value, onChange }: { value: Tab; onChange: (tab: Tab) => void }) {
  const { t } = useI18n();
  return (
    <nav aria-label={t("nav.main")} className="app-shell fixed inset-x-0 bottom-0 z-30 mx-auto flex max-w-lg justify-around border-t border-line bg-card/95 px-2 pt-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] backdrop-blur">
      {TABS.map((tab) => {
        const active = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            aria-current={active ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 rounded-xl py-2 text-xs font-bold ${
              active ? "text-physio-ink" : "text-muted"
            }`}
          >
            {tab.icon("h-6 w-6")}
            <span>{t(tab.labelKey)}</span>
          </button>
        );
      })}
    </nav>
  );
}
