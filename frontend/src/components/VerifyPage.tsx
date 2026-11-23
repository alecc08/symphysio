/* The page an emailed confirmation link lands on: /verify?token=…
 *
 * The token is lifted out of the URL and posted to the API, then erased from the
 * address bar, because a URL can end up in browser history, a screenshot or a
 * proxy log. The token is single-use anyway, but the page should not sit there
 * displaying it.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import { CheckIcon } from "./icons/Ui";
import { BrandMark } from "./icons/Tile";
import { useSession } from "../state/session";

type State =
  | { kind: "working" }
  | { kind: "done"; message: string }
  | { kind: "failed"; message: string; resendable: boolean };

const WORKING: State = { kind: "working" };

export function VerifyPage({ onDone }: { onDone?: () => void }) {
  const { reload, user } = useSession();
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
    const token = new URLSearchParams(window.location.search).get("token");
    // Drop the token from the visible URL before anything else happens.
    window.history.replaceState({}, "", "/verify");
    if (!token) {
      setState({
        kind: "failed",
        message: "This link is incomplete. Open the confirmation link from your email again.",
        resendable: Boolean(user),
      });
      return;
    }
    void (async () => {
      try {
        await api.verifyEmail(token);
        setState({ kind: "done", message: "Email confirmed." });
        // The in-app banner should disappear without a manual refresh.
        void reload();
      } catch (error) {
        setState({
          kind: "failed",
          message:
            error instanceof ApiError
              ? error.message
              : "Could not reach the server. Check the connection and try again.",
          resendable: Boolean(user),
        });
      }
    })();
  }, [reload, user]);

  const resend = useCallback(async () => {
    try {
      await api.resendVerification();
      setState({ kind: "done", message: "A new link is on its way. Open it on this device." });
    } catch (error) {
      setState({
        kind: "failed",
        message: error instanceof ApiError ? error.message : "Could not send another link.",
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
            <p className="text-lg font-extrabold tracking-tight">Confirm your email</p>
            <p className="text-sm text-muted">Symphysio</p>
          </div>
        </div>

        {state.kind === "working" ? (
          <p className="animate-pulse mt-6 text-sm font-semibold text-muted">Confirming…</p>
        ) : null}

        {state.kind === "done" ? (
          <>
            <p className="mt-6 flex items-center gap-2 text-base font-bold">
              <span className="text-physio-ink">
                <CheckIcon className="h-5 w-5" />
              </span>
              {state.message}
            </p>
            <p className="mt-2 text-sm text-muted">
              Your account can now recover itself if you lose your phone. Nothing else changed —
              your log has been saving the whole time.
            </p>
            <button
              type="button"
              onClick={finish}
              className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
            >
              Open Symphysio
            </button>
          </>
        ) : null}

        {state.kind === "failed" ? (
          <>
            <p className="mt-6 text-sm font-semibold text-symptom-ink">{state.message}</p>
            <p className="mt-2 text-sm text-muted">
              If the link is old, ask for a new one. Old links stop working the moment a new one
              is sent.
            </p>
            {state.resendable ? (
              <button
                type="button"
                onClick={() => void resend()}
                className="mt-6 h-12 w-full rounded-2xl bg-physio px-4 text-base font-extrabold text-white"
              >
                Send a new link
              </button>
            ) : null}
            <button
              type="button"
              onClick={finish}
              className="mt-3 h-12 w-full rounded-2xl border border-line bg-card px-4 text-base font-bold"
            >
              Back to the log
            </button>
          </>
        ) : null}
      </div>
    </main>
  );
}
