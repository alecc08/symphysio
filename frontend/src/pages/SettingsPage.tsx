/* Settings: account, quick-tap catalog, exports. No nested menus. */

import { useEffect } from "react";

import { api, exportHref } from "../api/client";
import { CatalogManager } from "../components/CatalogManager";
import { CloseIcon, DownloadIcon, LogoutIcon } from "../components/icons/Ui";
import { useCatalog } from "../state/catalog";
import { useSession } from "../state/session";
import { useToast } from "../state/toast";
import { formatDay } from "../lib/time";

export function SettingsPage({ onClose }: { onClose: () => void }) {
  const session = useSession();
  const catalog = useCatalog();
  const toast = useToast();
  const setIncludeArchived = catalog.setIncludeArchived;

  // Archived presets are only ever shown inside Settings.
  useEffect(() => () => setIncludeArchived(false), [setIncludeArchived]);

  return (
    <div className="px-4 pb-24 pt-2">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold tracking-tight">Settings</h1>
        <button
          type="button"
          onClick={onClose}
          aria-label="Return to Log"
          className="rounded-full border border-line bg-card p-2 text-muted"
        >
          <CloseIcon className="h-5 w-5" />
        </button>
      </div>

      <section className="mt-4 rounded-2xl border border-line bg-card p-4">
        <h2 className="text-sm font-extrabold">Account</h2>
        <p className="mt-1.5 text-sm text-muted">
          {session.user?.email} · joined {formatDay(session.user?.created_at_utc ?? 0)}
        </p>
        {session.user && !session.user.is_verified ? (
          <p className="mt-2 text-xs font-semibold text-physio-ink">
            This email is not confirmed yet. Use “Send again” in the strip above — confirmation is
            what makes password recovery possible later.
          </p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void session.logout()}
            className="flex items-center gap-2 rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm font-bold"
          >
            <LogoutIcon className="h-4 w-4" />
            Log out
          </button>
          <button
            type="button"
            onClick={async () => {
              try {
                await api.logoutAll();
                await session.logout();
              } catch {
                toast.show({ label: "Could not sign out other devices" });
              }
            }}
            className="rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm font-bold text-muted"
          >
            Sign out all devices
          </button>
        </div>
      </section>

      <section className="mt-4 rounded-2xl border border-line bg-card p-4">
        <h2 className="text-sm font-extrabold">Your data</h2>
        <p className="mt-1.5 text-sm text-muted">
          One SQLite file on your own server. Export everything for your physiotherapist, in the
          format they prefer.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={exportHref("csv")}
            className="flex items-center gap-2 rounded-xl bg-physio px-3.5 py-2.5 text-sm font-bold text-white"
          >
            <DownloadIcon className="h-4 w-4" />
            Export CSV
          </a>
          <a
            href={exportHref("json")}
            className="flex items-center gap-2 rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm font-bold"
          >
            <DownloadIcon className="h-4 w-4" />
            Export JSON
          </a>
        </div>
      </section>

      <section className="mt-4">
        <h2 className="mb-2 text-sm font-extrabold">Quick-tap buttons</h2>
        <CatalogManager kinds={["exercises", "symptoms", "contexts"]} />
      </section>

      <p className="mt-5 text-xs leading-relaxed text-muted">
        Archived presets disappear from the Log grid but keep every past entry attached. Nothing is
        ever hard-deleted except the log entries you delete in History.
      </p>
    </div>
  );
}
