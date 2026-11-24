/* The sign-up choice: what are you tracking?

One control, above the fields, no wizard. "Start empty" is the default and the
list comes from `GET /catalog/profiles` — the SPA never hard-codes the sets, so a
new profile appears here without a frontend change.

A native select, not a row of chips: the labels are long ("Low back, SI and
pelvic girdle pain") and on a 360 px screen a horizontal strip shows one and a
half of them, which is worse than no choice at all. The select always fits, and
hands the picking to the phone's own list.

The default matters more than it looks: every preset set is pelvic-flavoured by
history, and someone tracking a shoulder should not get a Clamshell they have to
delete. So the safe default is the empty diary, and the five sets are one tap away.
*/

import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Profile } from "../api/types";
import { useI18n } from "../i18n";
import type { Translate } from "../lib/timeLabels";

/** What the set will seed, counted. Zero counts are left out rather than printed
   and crossed out: the labels come from the server and are already in the
   language the account asked for, so this line only adds the numbers. */
function counts(profile: Profile, t: Translate): string {
  // The "none" blurb already says what happens, so do not say it twice.
  if (profile.key === "none") return t("profile.noneCounts");
  const parts: string[] = [];
  if (profile.counts.exercises)
    parts.push(t("profile.countsPhysio", { count: profile.counts.exercises }));
  if (profile.counts.symptoms)
    parts.push(t("profile.countsSymptoms", { count: profile.counts.symptoms }));
  const contexts = profile.counts.relief + profile.counts.triggers;
  if (contexts) parts.push(t("profile.countsContexts", { count: contexts }));
  return parts.join(" · ");
}

export function ProfilePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (key: string) => void;
}) {
  const { t, locale } = useI18n();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .profiles()
      .then((list) => live && setProfiles(list))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
    // `locale` is a dependency because the labels are the server's words, not
    // this file's: choosing French has to re-ask, or the picker keeps the English
    // set names while everything around it is French.
  }, [locale]);

  if (failed || !profiles) {
    // The API default is the postnatal set, so a picker that cannot load must not
    // silently send nothing: say what will happen instead of hiding the choice.
    return (
      <p className="mt-4 text-xs text-muted">{t("profile.loadFailed")}</p>
    );
  }

  const chosen = profiles.find((profile) => profile.key === value) ?? profiles[0];

  return (
    <div className="mt-4">
      <label className="block text-sm font-semibold" htmlFor="profile">
        {t("profile.label")}
      </label>
      <select
        id="profile"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-base font-semibold"
      >
        {profiles.map((profile) => (
          <option key={profile.key} value={profile.key}>
            {profile.label}
          </option>
        ))}
      </select>
      {/* The reason for the select's one-word label, so the choice is informed and
          the count of what gets seeded is visible without opening anything. */}
      <p className="mt-2 text-xs leading-snug text-muted">
        {chosen.blurb} <span className="text-faint">{counts(chosen, t)}</span>
      </p>
    </div>
  );
}
