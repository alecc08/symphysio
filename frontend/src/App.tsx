import { useEffect, useState } from "react";

import { BottomNav, type Tab } from "./components/BottomNav";
import { GearIcon } from "./components/icons/Ui";
import { BrandMark } from "./components/icons/Tile";
import { AuthPage } from "./pages/AuthPage";
import { HistoryPage } from "./pages/HistoryPage";
import { InsightsPage } from "./pages/InsightsPage";
import { LogPage } from "./pages/LogPage";
import { SettingsPage } from "./pages/SettingsPage";
import { CatalogProvider } from "./state/catalog";
import { SessionProvider, useSession } from "./state/session";
import { ToastProvider } from "./state/toast";

function Shell() {
  const { user, ready } = useSession();
  const [tab, setTab] = useState<Tab>("log");
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Every sign-in starts on a clean Log screen: the overlay and tab choices are
  // per-visit state, not per-account state.
  const userId = user?.id ?? null;
  useEffect(() => {
    setSettingsOpen(false);
    setTab("log");
  }, [userId]);

  if (!ready) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-muted">
        <p className="animate-pulse text-sm font-semibold">Loading Symphysio…</p>
      </div>
    );
  }

  if (!user) return <AuthPage />;

  return (
    <CatalogProvider>
      <div className="app-shell mx-auto min-h-dvh max-w-lg">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-2 backdrop-blur">
          <span className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span className="text-physio-ink">
              <BrandMark className="h-5 w-5" />
            </span>
            Symphysio
          </span>
          <button
            type="button"
            onClick={() => setSettingsOpen((open) => !open)}
            aria-label={settingsOpen ? "Close settings" : "Open settings"}
            aria-pressed={settingsOpen}
            className={`rounded-full border p-2 ${
              settingsOpen ? "border-physio bg-physio text-white" : "border-line bg-card text-muted"
            }`}
          >
            <GearIcon className="h-5 w-5" />
          </button>
        </header>

        <main>
          {settingsOpen ? (
            <SettingsPage onClose={() => setSettingsOpen(false)} />
          ) : tab === "log" ? (
            <LogPage />
          ) : tab === "history" ? (
            <HistoryPage />
          ) : (
            <InsightsPage />
          )}
        </main>

        {settingsOpen ? null : <BottomNav value={tab} onChange={setTab} />}
      </div>
    </CatalogProvider>
  );
}

export function App() {
  return (
    <SessionProvider>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </SessionProvider>
  );
}
