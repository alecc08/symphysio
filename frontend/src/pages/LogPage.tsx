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

function plural(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

export function LogPage() {
  const catalog = useCatalog();
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
          <h1 className="text-2xl font-extrabold tracking-tight">Log</h1>
          <p className="text-sm text-muted">
            {count("exercises") + count("symptoms") + count("contexts") > 0
              ? `${plural(count("exercises"), "exercise")} · ${plural(
                  count("symptoms"),
                  "symptom",
                )} · ${plural(count("contexts"), "context")} today`
              : "Nothing logged yet today"}
            {streak > 1 ? ` · ${streak}-day streak` : ""}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3">
        <Tile
          label="Physio"
          caption={`${catalog.exercises.length} presets`}
          className="border-physio/25 bg-physio-soft"
          accentClass="text-physio-ink"
          hero={<PhysioHero className="h-11 w-11" />}
          onClick={() => setSheet("physio")}
        />
        <Tile
          label="Symptoms"
          caption={`${catalog.symptoms.length} presets`}
          className="border-symptom/25 bg-symptom-soft"
          accentClass="text-symptom-ink"
          hero={<SymptomHero className="h-11 w-11" />}
          onClick={() => setSheet("symptoms")}
        />
        <Tile
          label="Relief / Meds"
          caption="Ice, heat, sitz bath, PT"
          className="border-relief/25 bg-relief-soft"
          accentClass="text-relief-ink"
          hero={<ReliefHero className="h-11 w-11" />}
          onClick={() => setSheet("relief")}
        />
        <Tile
          label="Triggers"
          caption="Lifting, coughing, standing"
          className="border-trigger/25 bg-trigger-soft"
          accentClass="text-trigger-ink"
          hero={<TriggerHero className="h-11 w-11" />}
          onClick={() => setSheet("triggers")}
        />
      </div>

      <p className="mt-5 text-sm leading-relaxed text-muted">
        One tap opens the drawer, the next tap saves it. Late entry? Use the{" "}
        <span className="font-semibold text-ink">-1h / -3h</span> chips so the correlation maths
        stays honest.
      </p>

      {sheet ? (
        <QuickSheet kind={sheet} onClose={() => setSheet(null)} onLogged={refresh} />
      ) : null}
    </div>
  );
}
