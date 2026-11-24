/* The page an emailed confirmation link lands on: /verify#token=…
 *
 * The token travels in the URL *fragment*, which the browser never sends to the
 * server, so no access log anywhere can hold it. It is lifted out of the address
 * bar before anything else runs anyway, because a URL can end up in browser
 * history or a screenshot. A link that still carries `?token=` (an older mail) is
 * read too.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import { CheckIcon } from "./icons/Ui";
import { BrandMark } from "./icons/Tile";
import { LanguageToggle } from "./LanguageToggle";
import { useI18n } from "../i18n";
import { useSession } from "../state/session";

type State =
  | { kind: "working" }
  | { kind: "done"; message: string }
  | { kind: "failed"; message: string; resendable: boolean };

const WORKING: State = { kind: "working" };

/** The token, from `#token=…` (what the mail sends) or `?token=…` (an older one). */
function tokenFromUrl(): string | null {
  const hash = window.location.hash.replace(/^#/, "");
  const fromHash = new URLSearchParams(hash).get("token");
  return fromHash ?? new URLSearchParams(window.location.search).get("token");
}

export function VerifyPage({ onDone }: { onDone?: () => void }) {
  const { reload, user } = useSession();
  const { t } = useI18n();
  const [state, setState] = useState<State>(WORKING);
  const started = useRef(false);

  const finish = useCallback(() => {
    if (onDone) {
      onDone();
      return;
    }
    window.location.assign("/");
  }, [onDone]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = tokenFromUrl();
    // Drop the token from the visible URL before anything else happens.
    window.history.replaceState({}, "", "/verify");
    if (!token) {
      setState({ kind: "failed", message: t("verify.incomplete"), resendable: Boolean(user) });
      return;
    }
    void (async () => {
      try {
        await api.verifyEmail(token);
        setState({ kind: "done", message: t("verify.done") });
        // The in-app banner should disappear without a manual refresh.
        void reload();
      } catch (error) {
        setState({
          kind: "failed",
          message: error instanceof ApiError ? error.message : t("verify.unreachable"),
          resendable: Boolean(user),
        });
      }
    })();
  }, [reload, user]);

  const resend = useCallback(async () => {
    try {
      await api.resendVerification();
      setState({ kind: "done", message: t("verify.newLinkSent") });
    } catch (error) {
      setState({
        kind: "failed",
        message: error instanceof ApiError ? error.message : t("verify.sendFailed"),
        resendable: false,
      });
    }
  }, []);

  return (
    <main className="app-shell mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 pb-10">
      <div className="rounded-3xl border border-line bg-card p-6">
        <div className="flex items-center gap-3">
          <span className="text-physio-ink">
            <BrandMark className="h-9 w-9" />
          </span>
          <div>
            <p className="text-lg font-extrabold tracking-tight">{t("verify.title")}</p>
            <p className="text-sm text-muted">{t("app.name")}</p>
          </div>
        </div>

        {state.kind === "working" ? (
          <p className="animate-pulse mt-6 text-sm font-semibold text-muted">{t("verify.working")}</p>
        ) : null}

        {state.kind === "done" ? (
          <>
            <p className="mt-6 flex items-center gap-2 text-base font-bold">
              <span className="text-physio-ink">
                <CheckIcon className="h-5 w-5" />
              </span>
              {state.message}
            </p>
            <p className="mt-2 text-sm text-muted">{t("verify.doneBody")}</p>
            <button
              type="button"
              onClick={finish}
              className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
            >
              {t("verify.open", { name: t("app.name") })}
            </button>
          </>
        ) : null}

        {state.kind === "failed" ? (
          <>
            <p className="mt-6 text-sm font-semibold text-symptom-ink">{state.message}</p>
            <p className="mt-2 text-sm text-muted">{t("verify.oldLink")}</p>
            {state.resendable ? (
              <button
                type="button"
                onClick={() => void resend()}
                className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
              >
                {t("verify.sendNew")}
              </button>
            ) : null}
            <button
              type="button"
              onClick={finish}
              className="mt-3 h-12 w-full rounded-2xl border border-line bg-card px-4 text-base font-bold"
            >
              {t("verify.backToLog")}
            </button>
          </>
        ) : null}
      </div>

      {/* Same reason as the reset page: this arrives by email, possibly on a device
          that speaks a different language than the one the mail was written in. */}
      <div className="mt-4 flex justify-center">
        <LanguageToggle />
      </div>
    </main>
  );
}
