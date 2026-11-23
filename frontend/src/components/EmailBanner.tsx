/* "Confirm your email" strip.

Shown only when this install actually asks about email: an account on a server
with no mail configured, or with SYPHYSIO_EMAIL_CONFIRMATION=off, comes back
`is_verified: true`. It is deliberately a strip, not a modal: logging a symptom
while unconfirmed is fine, and nothing about someone's recovery diary should be
held hostage by a mail provider.
*/

import { useCallback, useState } from "react";

import { ApiError, api } from "../api/client";
import { useSession } from "../state/session";
import { useToast } from "../state/toast";
import { ClockIcon } from "./icons/Ui";

export function EmailBanner() {
  const { user } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const resend = useCallback(async () => {
    setBusy(true);
    try {
      await api.resendVerification();
      toast.show({ label: "Confirmation link sent", tone: "physio" });
    } catch (error) {
      toast.show({
        label: error instanceof ApiError ? error.message : "Could not send the link",
        tone: "danger",
      });
    } finally {
      setBusy(false);
    }
  }, [toast]);

  if (!user || user.is_verified) return null;

  return (
    <div className="app-shell mx-auto flex max-w-lg items-center gap-3 border-b border-physio/25 bg-physio-soft px-4 py-2.5">
      <span className="text-physio-ink" aria-hidden="true">
        <ClockIcon className="h-5 w-5" />
      </span>
      <p className="min-w-0 flex-1 text-xs font-semibold">
        Confirm your email — it is the only way back in if you lose this device. We sent a link to{" "}
        <span className="font-extrabold">{user.email}</span>.
      </p>
      <button
        type="button"
        onClick={() => void resend()}
        disabled={busy}
        className="shrink-0 rounded-full border border-physio/30 bg-card px-3 py-1.5 text-xs font-extrabold text-physio-ink disabled:opacity-50"
      >
        {busy ? "Sending…" : "Send again"}
      </button>
    </div>
  );
}
