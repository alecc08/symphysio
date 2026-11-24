/* Home grid: four thumb-reachable tiles. Two taps to log anything. */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Summary } from "../api/types";
import { useCatalog } from "../state/catalog";
import {
  PhysioHero,
  ReliefHero,
  SymptomHero,
  TriggerHero,
} from "../components/icons/Tile";
import { QuickSheet, type SheetKind } from "../components/QuickSheet";
import { useI18n } from "../i18n";

interface TileProps {
  label: string;
  caption: string;
  className: string;
  accentClass: string;
  hero: React.ReactNode;
  onClick: () => void;
}

function Tile({ label, caption, className, accentClass, hero, onClick }: TileProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`log-tile flex min-h-[124px] flex-col justify-between rounded-tile border p-4 text-start shadow-sm active:shadow-none ${className}`}
    >
      <span className="text-lg leading-tight font-extrabold tracking-tight text-ink">{label}</span>
      <span className="flex items-end justify-between gap-2">
        <span className="text-xs font-semibold text-muted">{caption}</span>
        <span className={accentClass}>{hero}</span>
      </span>
    </button>
  );
}

function localDayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** What the relief/trigger tiles say about themselves.

Hard-coding "Ice, heat, sitz bath, PT" was a postnatal assumption: a hip-and-knee
or shoulder account gets no sitz bath in its presets, and the tile then advertises
something the person cannot log. The first few real presets are the honest caption,
and they follow whatever the person adds or removes.

   The names print as written: they are the person's own rows, and lower-casing
   them would mangle a French name, which keeps its capital. */
function presetCaption(rows: { name: string }[], empty: string): string {
  if (rows.length === 0) return empty;
  return rows
    .slice(0, 3)
    .map((row) => row.name)
    .join(", ");
}

export function LogPage() {
  const catalog = useCatalog();
  const { t } = useI18n();
  const [sheet, setSheet] = useState<SheetKind | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);

  const refresh = () => {
    void api
      .summary(7)
      .then(setSummary)
      .catch(() => undefined);
  };

  useEffect(refresh, []);

  const today = summary?.daily.find((entry) => entry.day === localDayIso());
  const count = (key: "exercises" | "symptoms" | "contexts") => today?.[key] ?? 0;
  const streak = summary?.exercise_streak_days ?? 0;

  return (
    <div className="px-4 pb-24 pt-2">
      <header className="mb-4 flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">{t("log.title")}</h1>
          <p className="text-sm text-muted">
            {count("exercises") + count("symptoms") + count("contexts") > 0
              ? t("log.todaySummary", {
                  exercises: count("exercises"),
                  symptoms: count("symptoms"),
                  contexts: count("contexts"),
                })
              : t("log.nothingToday")}
            {streak > 1 ? ` · ${t("log.streak", { count: streak })}` : ""}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3">
        <Tile
          label={t("tile.physio")}
          caption={t("log.presets", { count: catalog.exercises.length })}
          className="border-physio/25 bg-physio-soft"
          accentClass="text-physio-ink"
          hero={<PhysioHero className="h-11 w-11" />}
          onClick={() => setSheet("physio")}
        />
        <Tile
          label={t("tile.symptoms")}
          caption={t("log.presets", { count: catalog.symptoms.length })}
          className="border-symptom/25 bg-symptom-soft"
          accentClass="text-symptom-ink"
          hero={<SymptomHero className="h-11 w-11" />}
          onClick={() => setSheet("symptoms")}
        />
        <Tile
          label={t("tile.relief")}
          caption={presetCaption(
            catalog.contexts.filter((row) => row.category === "relief"),
            t("log.addYourOwn"),
          )}
          className="border-relief/25 bg-relief-soft"
          accentClass="text-relief-ink"
          hero={<ReliefHero className="h-11 w-11" />}
          onClick={() => setSheet("relief")}
        />
        <Tile
          label={t("tile.triggers")}
          caption={presetCaption(
            catalog.contexts.filter((row) => row.category === "trigger"),
            t("log.addYourOwn"),
          )}
          className="border-trigger/25 bg-trigger-soft"
          accentClass="text-trigger-ink"
          hero={<TriggerHero className="h-11 w-11" />}
          onClick={() => setSheet("triggers")}
        />
      </div>

      <p className="mt-5 text-sm leading-relaxed text-muted">
        {t("log.hintBefore")} <span className="font-semibold text-ink">{t("log.hintChips")}</span>{" "}
        {t("log.hintAfter")}
      </p>

      {sheet ? (
        <QuickSheet kind={sheet} onClose={() => setSheet(null)} onLogged={refresh} />
      ) : null}
    </div>
  );
}
