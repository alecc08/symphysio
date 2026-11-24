/* Language and time zone, the two account-level choices.

   Both are stored on the account rather than only on the device, and for the same
   reason: the server has to know them too, because they decide what language an
   email and a failed request are written in, and what instant counts as "today".
   A device setting reaches neither.

   The time zone is deliberately *not* taken from the device automatically. The
   device fills the starting point of the picker, but the account only changes when
   the person chooses — a laptop carried to another city should not move the day
   boundaries of a diary, and an account that never chose keeps the instance
   default (docs/API.md).
*/

import { useEffect, useMemo, useState } from "react";

import { ApiError, api, deviceTimezone } from "../api/client";
import type { Preferences } from "../api/types";
import { useI18n } from "../i18n";
import { useToast } from "../state/toast";
import { LanguageToggle } from "./LanguageToggle";

/** Offered as a scale rather than the ~400 IANA names: everyone on this server
 *  lives in one of these, and a searchable list of every zone is a worse control
 *  than a short one plus the zone this device actually reports (added below when
 *  it is not already here). */
const ZONES = [
  "America/Toronto",
  "America/Halifax",
  "America/Winnipeg",
  "America/Edmonton",
  "America/Vancouver",
  "America/Mexico_City",
  "Europe/Paris",
  "UTC",
];

/** The select's value is never a real zone: it says which rule the account uses. */
const SERVER_DEFAULT = "";
const THIS_DEVICE = "__device__";

export function PreferencesCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    api
      .preferences()
      .then(setPrefs)
      .catch(() => setFailed(t("settings.prefsFailed")));
  }, [t]);

  const device = deviceTimezone();
  const zones = useMemo(() => {
    const effective = prefs?.effective_timezone;
    const extra = effective && !ZONES.includes(effective) ? [effective] : [];
    return [...ZONES, ...extra];
  }, [prefs?.effective_timezone]);

  const current = prefs?.timezone;
  const selectValue = current === null ? SERVER_DEFAULT : current === device ? THIS_DEVICE : current;

  async function save(timezone: string | null) {
    if (!timezone || timezone === SERVER_DEFAULT) {
      // Back to "never chose": the instance default applies, which is what an
      // account with no preference means (app/timezones.py).
      await patch({ timezone: null });
    } else {
      await patch({ timezone: timezone === THIS_DEVICE ? device : timezone });
    }
  }

  async function patch(body: { timezone?: string | null }) {
    try {
      setPrefs(await api.patchPreferences(body));
      toast.show({ label: t("settings.prefsSaved"), tone: "physio" });
    } catch (error) {
      toast.show({
        label: error instanceof ApiError ? error.message : t("settings.prefsFailed"),
        tone: "danger",
      });
    }
  }

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <h2 className="text-sm font-extrabold">{t("settings.prefs")}</h2>
      <p className="mt-1.5 text-sm text-muted">{t("settings.prefsNote")}</p>

      <div className="mt-3">
        <LanguageToggle compact />
      </div>

      <label className="mt-4 block text-xs font-semibold text-muted" htmlFor="timezone">
        {t("settings.timezone")}
      </label>
      <select
        id="timezone"
        value={selectValue}
        disabled={!prefs}
        onChange={(event) => void save(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-base font-semibold disabled:opacity-60"
      >
        <option value={SERVER_DEFAULT}>{t("settings.timezoneServerDefault")}</option>
        <option value={THIS_DEVICE}>
          {t("settings.timezoneDeviceChoice")} — {device}
        </option>
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone}
          </option>
        ))}
      </select>

      {failed ? <p className="mt-2 text-xs text-symptom-ink">{failed}</p> : null}
      {prefs ? (
        <p className="mt-2 text-xs text-muted">
          {t("settings.timezoneEffective", {
            zone: prefs.effective_timezone,
            offset: prefs.utc_offset,
          })}{" "}
          {t("settings.timezoneHelp")}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">{t("app.loading")}</p>
      )}
    </section>
  );
}
