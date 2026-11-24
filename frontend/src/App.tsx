import { useEffect, useState } from "react";

import { BottomNav, type Tab } from "./components/BottomNav";
import { EmailBanner } from "./components/EmailBanner";
import { OfflineBanner } from "./components/OfflineBanner";
import { I18nProvider, useI18n } from "./i18n";
import { GearIcon } from "./components/icons/Ui";
import { BrandMark } from "./components/icons/Tile";
import { ResetPage } from "./components/ResetPage";
import { VerifyPage } from "./components/VerifyPage";
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
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("log");
  const [settingsOpen, setSettingsOpen] = useState(false);
  // The emailed confirmation link lands on /verify; the API route of the same
  // name is POST-only, so this only ever sees the SPA path.
  const [verifying, setVerifying] = useState(
    () => window.location.pathname.replace(/\/+$/, "") === "/verify",
  );
  // /reset#token=… from the password-reset mail. Checked before the auth branch
  // because someone using a reset link is, by definition, not signed in.
  const [resetting, setResetting] = useState(
    () => window.location.pathname.replace(/\/+$/, "") === "/reset",
  );

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
        <p className="animate-pulse text-sm font-semibold">
          {t("app.loadingNamed", { name: t("app.name") })}
        </p>
      </div>
    );
  }

  if (verifying) {
    return (
      <VerifyPage
        onDone={() => {
          // Leave the SPA path, not just the state: a tab that stays on /verify
          // would show the log screen at a URL that means something else.
          window.history.replaceState({}, "", "/");
          setVerifying(false);
        }}
      />
    );
  }

  if (resetting) {
    return (
      <ResetPage
        onDone={() => {
          window.history.replaceState({}, "", "/");
          setResetting(false);
        }}
      />
    );
  }

  if (!user) return <AuthPage />;

  return (
    <CatalogProvider>
      <div className="app-shell mx-auto min-h-dvh max-w-lg">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-2 backdrop-blur">
          <span className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <BrandMark className="h-5 w-5" />
            {t("app.name")}
          </span>
          <button
            type="button"
            onClick={() => setSettingsOpen((open) => !open)}
            aria-label={settingsOpen ? t("settings.close") : t("settings.open")}
            aria-pressed={settingsOpen}
            className={`rounded-full border p-2 ${
              settingsOpen ? "border-physio bg-physio text-white" : "border-line bg-card text-muted"
            }`}
          >
            <GearIcon className="h-5 w-5" />
          </button>
        </header>

        <EmailBanner />

        <OfflineBanner />

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
  // I18nProvider is outermost on purpose: `SessionProvider` adopts the account's
  // language as soon as it learns who is signed in, and the sign-in screen needs
  // the device's own choice before there is any session at all.
  return (
    <I18nProvider>
      <SessionProvider>
        <ToastProvider>
          <Shell />
        </ToastProvider>
      </SessionProvider>
    </I18nProvider>
  );
}
