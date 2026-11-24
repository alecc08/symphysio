/* "You are offline" strip, shown while the browser itself has no connection.

   The app cannot queue a log locally — an entry the server never accepted is not
   a record, and a queue that silently fills up while a phone roams is worse than
   saying so (see public/offline.html for the same message with no app at all).
   So the strip only explains, it does not offer to save.
*/

import { useEffect, useState } from "react";

import { useI18n } from "../i18n";

export function OfflineBanner() {
  const { t } = useI18n();
  const [offline, setOffline] = useState(() => navigator.onLine === false);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <p
      role="status"
      className="mt-2 rounded-xl border border-symptom/40 bg-symptom-soft px-3 py-2 text-xs font-semibold text-symptom-ink"
    >
      {t("app.offline")}
    </p>
  );
}
