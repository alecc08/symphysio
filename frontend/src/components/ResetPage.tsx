/* The page an emailed reset link lands on: /reset#token=…
 *
 * Same token discipline as /verify: the token rides in the URL *fragment*, which
 * the browser never sends to a server, and it is lifted out of the address bar
 * before anything else runs. Unlike confirmation, this one needs a second input —
 * the new password — because the whole point is to hand the account back.
 */

import { useCallback, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import { CheckIcon } from "./icons/Ui";
import { LanguageToggle } from "./LanguageToggle";
import { BrandMark } from "./icons/Tile";
import { useI18n } from "../i18n";
import { useSession } from "../state/session";

type State =
  | { kind: "form" }
  | { kind: "working" }
  | { kind: "done" }
  | { kind: "failed"; message: string };

function tokenFromUrl(): string | null {
  const hash = window.location.hash.replace(/^#/, "");
  const fromHash = new URLSearchParams(hash).get("token");
  return fromHash ?? new URLSearchParams(window.location.search).get("token");
}

export function ResetPage({ onDone }: { onDone?: () => void }) {
  const { reload } = useSession();
  const { t } = useI18n();
  const token = useRef<string | null>(null);
  const [password, setPassword] = useState("");
  const [state, setState] = useState<State>({ kind: "form" });

  // Read the token once, then erase it from the visible URL: a URL can end up in
  // browser history, a screenshot, or a shared tab.
  if (token.current === null) {
    token.current = tokenFromUrl();
    window.history.replaceState({}, "", "/reset");
  }

  const finish = useCallback(() => {
    if (onDone) {
      onDone();
      return;
    }
    window.location.assign("/");
  }, [onDone]);

  const submit = useCallback(async () => {
    if (!token.current) return;
    setState({ kind: "working" });
    try {
      await api.confirmPasswordReset(token.current, password);
      setState({ kind: "done" });
      // The server revoked every session, including this browser's, so the client
      // has to stop believing it is signed in.
      void reload();
    } catch (error) {
      setState({
        kind: "failed",
        message:
          error instanceof ApiError
            ? error.message
            : t("reset.unreachable"),
      });
    }
  }, [password, reload, t]);

  return (
    <main className="app-shell mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 pb-10">
      <div className="rounded-3xl border border-line bg-card p-6">
        <div className="flex items-center gap-3">
          <span className="text-physio-ink">
            <BrandMark className="h-9 w-9" />
          </span>
          <div>
            <p className="text-lg font-extrabold tracking-tight">{t("reset.title")}</p>
            <p className="text-sm text-muted">{t("app.name")}</p>
          </div>
        </div>

        {state.kind === "failed" ? (
          <>
            <p className="mt-6 text-sm font-semibold text-symptom-ink">{state.message}</p>
            <p className="mt-2 text-sm text-muted">{t("reset.linkAdvice", { minutes: 30 })}</p>
            <button
              type="button"
              onClick={finish}
              className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
            >
              {t("reset.backToSignIn")}
            </button>
          </>
        ) : null}

        {state.kind === "done" ? (
          <>
            <p className="mt-6 flex items-center gap-2 text-base font-bold">
              <span className="text-physio-ink">
                <CheckIcon className="h-5 w-5" />
              </span>
              {t("reset.changed")}
            </p>
            <p className="mt-2 text-sm text-muted">{t("reset.changedBody")}</p>
            <button
              type="button"
              onClick={finish}
              className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
            >
              {t("auth.logIn")}
            </button>
          </>
        ) : null}

        {state.kind === "form" || state.kind === "working" ? (
          token.current ? (
            <>
              <label className="mt-6 block text-xs font-semibold text-muted" htmlFor="password">
                {t("reset.newPassword")}
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                value={password}
                maxLength={256}
                onChange={(event) => setPassword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void submit();
                }}
                className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3 py-3 text-base"
              />
              <p className="mt-1.5 text-xs text-muted">{t("auth.passwordHint", { count: 12 })}</p>
              <button
                type="button"
                onClick={() => void submit()}
                disabled={state.kind === "working" || password.length < 12}
                className="mt-5 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white disabled:opacity-50"
              >
                {state.kind === "working" ? t("reset.changing") : t("reset.change")}
              </button>
            </>
          ) : (
            <>
              <p className="mt-6 text-sm font-semibold text-symptom-ink">{t("reset.incomplete")}</p>
              <p className="mt-2 text-sm text-muted">{t("reset.incompleteBody")}</p>
              <button
                type="button"
                onClick={finish}
                className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
              >
                {t("reset.backToSignIn")}
              </button>
            </>
          )
        ) : null}
      </div>

      {/* The mail arrived in one language and this browser speaks another, so the
          choice has to be on the page the link lands on, not only on the sign-in
          screen behind it. */}
      <div className="mt-4 flex justify-center">
        <LanguageToggle />
      </div>
    </main>
  );
}
