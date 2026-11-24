/* Dependency-free charts. Bar heights are set in JS (not a style attribute) so
   the app can keep a strict `style-src 'self'` Content-Security-Policy. */

import { useEffect, useRef } from "react";

import type { SummaryDaily, TimeOfDay } from "../api/types";
import { useI18n } from "../i18n";
import { formatters } from "../lib/time";

function Bar({
  ratio,
  toneClass,
  title,
  minHeightPx = 3,
}: {
  ratio: number;
  toneClass: string;
  title: string;
  minHeightPx?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    node.style.height = `${Math.max(4, Math.min(100, ratio * 100))}%`;
    node.style.minHeight = `${minHeightPx}px`;
  }, [ratio, minHeightPx]);
  return <div ref={ref} title={title} className={`bar-grow rounded-t-sm ${toneClass}`} />;
}

export function DailyBars({
  days,
  metric,
  toneClass,
  emptyLabel,
}: {
  days: SummaryDaily[];
  metric: "exercises" | "symptoms" | "contexts";
  toneClass: string;
  emptyLabel: string;
}) {
  const { t, tag } = useI18n();
  const fmt = formatters(tag);
  const recent = days.slice(-14);
  if (recent.length === 0) return <p className="text-sm text-muted">{emptyLabel}</p>;
  const max = Math.max(1, ...recent.map((day) => day[metric]));
  const total = recent.reduce((sum, day) => sum + day[metric], 0);
  return (
    <div>
      <div className="flex h-28 items-end gap-1">
        {recent.map((day) => (
          <div key={day.day} className="flex h-full flex-1 flex-col justify-end">
            <Bar
              ratio={day[metric] / max}
              toneClass={day[metric] > 0 ? toneClass : "bg-line"}
              title={`${day.day}: ${day[metric]}`}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[0.65rem] font-semibold text-muted">
        <span>{fmt.monthDay(recent[0].day)}</span>
        <span>{t("charts.totalPeak", { total: total, max: max })}</span>
        <span>{fmt.monthDay(recent[recent.length - 1].day)}</span>
      </div>
    </div>
  );
}

export function SeverityTrend({ days }: { days: SummaryDaily[] }) {
  const { t } = useI18n();
  const points = days.slice(-14).map((day) => ({ day: day.day, value: day.avg_symptom_severity }));
  const drawn = points.filter((point) => point.value !== null) as { day: string; value: number }[];
  if (drawn.length < 2) {
    return <p className="text-sm text-muted">{t("charts.severityEmpty")}</p>;
  }
  const width = 280;
  const height = 72;
  const step = width / Math.max(1, drawn.length - 1);
  const path = drawn
    .map((point, index) => {
      const x = index * step;
      const y = height - (point.value / 10) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-20 w-full"
        role="img"
        aria-label={t("charts.severityAria")}
      >
        <path d={`${path} L${width} ${height} L0 ${height} Z`} className="fill-symptom/10" />
        <path
          d={path}
          className="fill-none stroke-symptom"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <p className="mt-1.5 text-[0.65rem] font-semibold text-muted">
        {t("charts.severityScale", { count: drawn.length })}
      </p>
    </div>
  );
}

export function HourBars({ data }: { data: TimeOfDay }) {
  const { t } = useI18n();
  const max = Math.max(1, ...data.hours.map((hour) => hour.count));
  const busiest = data.hours.reduce(
    (best, hour) => (hour.count > best.count ? hour : best),
    data.hours[0],
  );
  return (
    <div>
      <div className="flex h-20 items-end gap-[3px]">
        {data.hours.map((hour) => (
          <div key={hour.hour} className="flex h-full flex-1 flex-col justify-end">
            <Bar
              ratio={hour.count / max}
              toneClass={hour.count > 0 ? "bg-trigger" : "bg-line"}
              minHeightPx={2}
              title={t("charts.hourTitle", {
                hour: String(hour.hour).padStart(2, "0"),
                count: hour.count,
              })}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[0.65rem] font-semibold text-muted">
        <span>00</span>
        <span>
          {busiest.count > 0
            ? t("charts.busiest", { hour: String(busiest.hour).padStart(2, "0") })
            : t("charts.noData")}
        </span>
        <span>23</span>
      </div>
    </div>
  );
}
