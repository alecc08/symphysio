/* The illustration set.

   Four glyphs, one per log kind. The rule for this set is **obvious before it is
   clever**: each glyph should be nameable in one word by someone who has never
   opened the app. An earlier abstract set ("hammock lifting a load" for physio,
   a body map with a pelvic flare for symptoms) looked designed but read as a
   cup, a balloon and a pair of right feet, so it was replaced.

   Duotone: a soft-filled body (fill-opacity .16-.18) plus currentColor strokes
   at 2 (primary) / 1.3 (detail, ~55 % opacity), so the set inherits the tile's
   accent colour and stays a family. Candidates were rendered at 88 px and 44 px
   on light and dark tint chips before anything was chosen.
*/

type IconProps = { className?: string };

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

const soft = { fill: "currentColor", fillOpacity: 0.16 } as const;
const solid = { fill: "currentColor", stroke: "none" } as const;
const detail = { strokeWidth: 1.3, opacity: 0.55 } as const;

/* --------------------------------------------------------------- brand mark */

/** Product mark: the pelvic hammock supporting a load, with a lift chevron. */
export function BrandMark({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} className={className}>
      <path {...base} {...soft} d="M5 8.5v2.2c0 4 3 6.8 7 6.8s7-2.8 7-6.8V8.5" />
      <circle {...base} {...solid} cx="12" cy="11.8" r="1.8" />
      <path {...base} d="M9 21l3-3 3 3" />
    </svg>
  );
}

/* -------------------------------------------------------------- tile heroes */

/** Physio: a dumbbell being lifted — exercise, and progressive loading. */
export function PhysioHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <rect {...base} {...soft} x="6" y="15" width="7.5" height="16" rx="2.6" />
      <rect {...base} {...soft} x="34.5" y="15" width="7.5" height="16" rx="2.6" />
      <path {...base} strokeWidth={2.6} d="M13.5 23h21" />
      <path {...base} {...detail} d="M9.75 18.5v9M38.25 18.5v9" />
      <path {...base} d="M24 45V35M19 39.5 24 34.5l5 5" />
    </svg>
  );
}

/** Symptoms: a body with a pain bolt where it hurts. */
export function SymptomHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <circle {...base} {...soft} cx="24" cy="8" r="4.4" />
      <path
        {...base}
        {...soft}
        d="M17.5 15c-3 2-4.6 5.3-4.6 9 0 3 .9 5.4 2.2 7-1.4 3.9-.7 7.6 1.7 10.4 2.8 3.2 15.8 3.2 18.6 0 2.4-2.8 3.1-6.5 1.7-10.4 1.3-1.6 2.2-4 2.2-7 0-3.7-1.6-7-4.6-9z"
      />
      <path {...base} {...solid} d="M24 22l-7 11h4.8L20 43l9.6-12.5H24.6z" />
    </svg>
  );
}

/** Relief / meds: a thermometer with a snowflake — heat and cold therapy. */
export function ReliefHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path {...base} {...soft} d="M17.5 8a4 4 0 0 1 8 0v17.6a6.2 6.2 0 1 1-8 0z" />
      <path {...base} strokeWidth={2.2} d="M21.5 13.5v15" />
      <circle {...base} {...solid} cx="21.5" cy="34" r="3.1" />
      <path {...base} {...detail} d="M28 13h4.5M28 18.5h4.5M28 24h4.5" />
      <path {...base} strokeWidth={1.6} d="M38 33h8M42 29v8M39.2 30.2l5.6 5.6M44.8 30.2l-5.6 5.6" />
    </svg>
  );
}

/** Triggers: activity — a left and a right footprint landing on the pelvic floor. */
export function TriggerHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} strokeWidth={1.8} className={className}>
      <path
        {...base}
        strokeWidth={1.8}
        fill="currentColor"
        fillOpacity={0.2}
        d="M15 5c3 0 4.9 2.5 4.9 6.2 0 3.2-.8 4.9-2.1 7-1.1 1.6-1.5 2.8-1.7 4.7-.2 1.7-1.1 2.6-2.6 2.6-1.9 0-3-1.2-3-3.2 0-2.1.4-3.6 1.3-5.7.6-1.7.8-3.2.8-5.3C12.6 6.6 13.3 5 15 5z"
      />
      <path
        {...base}
        strokeWidth={1.8}
        fill="currentColor"
        fillOpacity={0.2}
        d="M33 15c-3 0-4.9 2.5-4.9 6.2 0 3.2.8 4.9 2.1 7 1.1 1.6 1.5 2.8 1.7 4.7.2 1.7 1.1 2.6 2.6 2.6 1.9 0 3-1.2 3-3.2 0-2.1-.4-3.6-1.3-5.7-.6-1.7-.8-3.2-.8-5.3C35.4 16.6 34.7 15 33 15z"
      />
      <circle {...base} {...solid} cx="18.6" cy="4.4" r="1.5" opacity={0.55} />
      <circle {...base} {...solid} cx="29.4" cy="14.4" r="1.5" opacity={0.55} />
      <path {...base} strokeWidth={2} {...soft} d="M7 38.5c0 4 7 6.5 17 6.5s17-2.5 17-6.5" />
      <path {...base} {...detail} d="M9 33.5h5M34 33.5h5" />
    </svg>
  );
}

/* ------------------------------------------------- compact 24x24 (nav, chips) */

export function PhysioIcon({ className = "w-5 h-5" }: IconProps) {
  return <BrandMark className={className} />;
}

export function SymptomIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={1.9} className={className}>
      <circle {...base} {...soft} cx="12" cy="4.5" r="2.4" />
      <path
        {...base}
        {...soft}
        d="M8.7 8.4c-1.6 1.1-2.4 2.8-2.4 4.7 0 1.6.5 2.8 1.2 3.6-.8 2.1-.4 4.1 1 5.7 1.4 1.7 6.8 1.7 8.8 0 1.2-1.6 1.8-3.6 1-5.7.7-.8 1.2-2 1.2-3.6 0-1.9-.8-3.6-2.4-4.7z"
      />
      <path {...base} {...solid} d="M12.6 9.4 8.4 15.7h2.7l-1 5.3 4.9-6.6h-2.6z" />
    </svg>
  );
}

export function ReliefIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={1.9} className={className}>
      <path {...base} {...soft} d="M8.5 4a3.2 3.2 0 0 1 6.4 0v11.4a5 5 0 1 1-6.4 0z" />
      <path {...base} strokeWidth={2} d="M11.7 8v8" />
      <circle {...base} {...solid} cx="11.7" cy="18.6" r="2.4" />
      <path {...base} {...detail} d="M17 8h3.5M17 12h3.5" />
    </svg>
  );
}

export function TriggerIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={1.7} className={className}>
      <path
        {...base}
        strokeWidth={1.7}
        fill="currentColor"
        fillOpacity={0.2}
        d="M7.6 3c1.9 0 3.1 1.6 3.1 4 0 2-.5 3.1-1.3 4.4-.7 1-1 1.8-1.1 3-.1 1.1-.7 1.7-1.6 1.7-1.2 0-1.9-.8-1.9-2 0-1.4.3-2.3.8-3.7.4-1.1.5-2 .5-3.4 0-2.3.4-4 1.5-4z"
      />
      <path
        {...base}
        strokeWidth={1.7}
        fill="currentColor"
        fillOpacity={0.2}
        d="M16.4 8.6c-1.9 0-3.1 1.6-3.1 4 0 2 .5 3.1 1.3 4.4.7 1 1 1.8 1.1 3 .1 1.1.7 1.7 1.6 1.7 1.2 0 1.9-.8 1.9-2 0-1.4-.3-2.3-.8-3.7-.4-1.1-.5-2-.5-3.4 0-2.3-.4-4-1.5-4z"
      />
      <path {...base} strokeWidth={1.9} {...soft} d="M3.5 20c0 2 3.8 3.2 8.5 3.2s8.5-1.2 8.5-3.2" />
    </svg>
  );
}
