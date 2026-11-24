/* The en/fr switch. Two buttons, not a <select>: the choice is binary and the
   current one should be visible without opening anything.

   The names stay in their own language ("English", "Français"), which is how a
   language picker works when the user may not read the one currently on screen.
   Nothing else about the control is translated except its accessible name.
*/

import { useI18n, type Locale } from "../i18n";

const OPTIONS: { locale: Locale; label: string }[] = [
  { locale: "en", label: "English" },
  { locale: "fr", label: "Français" },
];

export function LanguageToggle({ compact = false }: { compact?: boolean }) {
  const { locale, choose, t } = useI18n();
  return (
    <div
      className="flex items-center gap-2"
      role="group"
      aria-label={t("language.label")}
      data-language-toggle=""
    >
      <div className="flex rounded-xl border border-line bg-canvas p-0.5">
        {OPTIONS.map((option) => {
          const active = locale === option.locale;
          return (
            <button
              key={option.locale}
              type="button"
              onClick={() => choose(option.locale)}
              aria-pressed={active}
              className={`rounded-lg font-bold transition ${
                compact ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm"
              } ${active ? "bg-card text-ink shadow-sm" : "text-muted"}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      {compact ? null : <span className="text-xs text-muted">{t("language.help")}</span>}
    </div>
  );
}
