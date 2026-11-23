/* The illustration set.

   Duotone: each glyph pairs a soft-filled body (`fill-opacity .13`) with
   `currentColor` strokes at three weights, so the set reads as one family and
   inherits colour from the tile (dark mode and active states come free).

   The motifs are pelvic-floor-first rather than generic gym clip-art:
   a hammock lifting a load (physio), a body map with a flare at the pelvic
   floor (symptoms), warmth (relief), and load/impact landing on the hammock
   (triggers). Geometry was checked at 44 px, the size it renders at.
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

const soft = { fill: "currentColor", fillOpacity: 0.13 } as const;
const solid = { fill: "currentColor", stroke: "none" } as const;

/* --------------------------------------------------------------- brand mark */

/** Product mark: the pelvic hammock supporting a load, with a lift chevron. */
export function BrandMark({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} className={className}>
      <path {...base} {...soft} strokeWidth={2} d="M5 8.5v2.2c0 4 3 6.8 7 6.8s7-2.8 7-6.8V8.5" />
      <circle {...base} {...solid} cx="12" cy="11.8" r="1.8" />
      <path {...base} strokeWidth={2} d="M9 21l3-3 3 3" />
    </svg>
  );
}

/* -------------------------------------------------------------- tile heroes */

/** Physio: the hammock lifting, activation arrows radiating from the hips. */
export function PhysioHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path
        {...base}
        {...soft}
        strokeWidth={2}
        d="M8 13c0 13 7 22 16 22s16-9 16-22"
      />
      <path {...base} strokeWidth={1.3} opacity={0.55} d="M15 18.5c0 8 4 13.5 9 13.5s9-5.5 9-13.5" />
      <circle {...base} {...solid} cx="8" cy="13" r="2.1" />
      <circle {...base} {...solid} cx="40" cy="13" r="2.1" />
      <circle {...base} {...solid} cx="24" cy="22" r="3.2" />
      <path {...base} strokeWidth={2} d="M24 45.5v-7.5M19 41l5-5 5 5" />
      <path
        {...base}
        strokeWidth={1.3}
        opacity={0.45}
        d="M5 19.5 2.5 21M43 19.5 45.5 21M6 27.5 3.5 29.5M42 27.5l2.5 2"
      />
    </svg>
  );
}

/** Symptoms: body map with a flare sitting at the pelvic floor. */
export function SymptomHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <circle {...base} {...soft} strokeWidth={2} cx="24" cy="8.5" r="4.2" />
      <path
        {...base}
        {...soft}
        strokeWidth={2}
        d="M15.5 15c-3 2-4.5 5.2-4.5 8.8 0 3 .9 5.3 2.1 6.9-1.3 3.8-.6 7.4 1.7 10.2 2.7 3.1 15.7 3.1 18.4 0 2.3-2.8 3-6.4 1.7-10.2 1.2-1.6 2.1-3.9 2.1-6.9 0-3.6-1.5-6.8-4.5-8.8z"
      />
      <path {...base} strokeWidth={1.3} opacity={0.5} d="M13.5 25c6.8 2.2 14.2 2.2 21 0" />
      <path
        {...base}
        {...solid}
        d="M24 26.5l1.7 4.6 4.6 1.7-4.6 1.7-1.7 4.6-1.7-4.6-4.6-1.7 4.6-1.7z"
      />
      <path
        {...base}
        strokeWidth={1.3}
        opacity={0.4}
        strokeDasharray="2 3.4"
        d="M24 25.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17z"
      />
    </svg>
  );
}

/** Relief / meds: warmth and soothing — a drop over heat waves, plus a spark. */
export function ReliefHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path
        {...base}
        {...soft}
        strokeWidth={2}
        d="M24 6.5c5.4 7 9.2 11.6 9.2 16a9.2 9.2 0 0 1-18.4 0c0-4.4 3.8-9 9.2-16z"
      />
      <path {...base} strokeWidth={1.3} opacity={0.6} d="M20 22.5a4.2 4.2 0 0 0 3.6 3.8" />
      <path {...base} strokeWidth={2} d="M11 33c3-2.6 6.8-2.6 9.8 0M27.2 33c3-2.6 6.8-2.6 9.8 0" />
      <path
        {...base}
        strokeWidth={1.3}
        opacity={0.55}
        d="M11 40.5c3-2.6 6.8-2.6 9.8 0M27.2 40.5c3-2.6 6.8-2.6 9.8 0"
      />
      <path
        {...base}
        {...solid}
        opacity={0.8}
        d="M39 8l1.2 3 3 1.2-3 1.2L39 16l-1.2-2.6-3-1.2 3-1.2z"
      />
    </svg>
  );
}

/** Triggers: activity and load landing on the hammock below. */
export function TriggerHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path
        {...base}
        strokeWidth={2}
        fill="currentColor"
        fillOpacity={0.18}
        d="M15 6c2.8 0 4.6 2.2 4.6 5.6 0 3-.7 4.6-2 6.6-1 1.5-1.4 2.6-1.6 4.4-.2 1.6-1 2.4-2.4 2.4-1.7 0-2.8-1.1-2.8-3 0-2 .4-3.4 1.2-5.4.6-1.6.8-3 .8-5C12.8 7.4 13.4 6 15 6z"
      />
      <path
        {...base}
        strokeWidth={2}
        fill="currentColor"
        fillOpacity={0.18}
        d="M33 14c2.8 0 4.6 2.2 4.6 5.6 0 3-.7 4.6-2 6.6-1 1.5-1.4 2.6-1.6 4.4-.2 1.6-1 2.4-2.4 2.4-1.7 0-2.8-1.1-2.8-3 0-2 .4-3.4 1.2-5.4.6-1.6.8-3 .8-5C30.8 15.4 31.4 14 33 14z"
      />
      <path {...base} {...soft} strokeWidth={2} d="M9 40.5c0 3.6 6.2 6 15 6s15-2.4 15-6" />
      <path {...base} strokeWidth={1.3} opacity={0.5} d="M10.5 35.5h5M32.5 35.5h5" />
    </svg>
  );
}

/* ------------------------------------------------- compact 24x24 (nav, chips) */

export function PhysioIcon({ className = "w-5 h-5" }: IconProps) {
  return <BrandMark className={className} />;
}

export function SymptomIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} className={className}>
      <circle {...base} {...soft} strokeWidth={1.9} cx="12" cy="4.5" r="2.4" />
      <path
        {...base}
        {...soft}
        strokeWidth={1.9}
        d="M7.8 8.5c-1.6 1.1-2.4 2.8-2.4 4.7 0 1.6.5 2.8 1.2 3.6-.8 2.1-.4 4.1 1 5.7 1.4 1.7 6.8 1.7 8.8 0 1.2-1.6 1.8-3.6 1-5.7.7-.8 1.2-2 1.2-3.6 0-1.9-.8-3.6-2.4-4.7z"
      />
      <path {...base} {...solid} d="M12 13.2l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z" />
    </svg>
  );
}

export function ReliefIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} className={className}>
      <path
        {...base}
        {...soft}
        strokeWidth={1.9}
        d="M12 3.5c2.7 3.5 4.6 5.8 4.6 8a4.6 4.6 0 0 1-9.2 0c0-2.2 1.9-4.5 4.6-8z"
      />
      <path {...base} strokeWidth={1.9} d="M5 18.5c1.5-1.3 3.4-1.3 4.9 0M14.1 18.5c1.5-1.3 3.4-1.3 4.9 0" />
    </svg>
  );
}

export function TriggerIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} className={className}>
      <path
        {...base}
        strokeWidth={1.9}
        fill="currentColor"
        fillOpacity={0.18}
        d="M8 3.5c1.4 0 2.3 1.1 2.3 2.8 0 1.5-.3 2.3-1 3.3-.5.8-.7 1.3-.8 2.2-.1.8-.5 1.2-1.2 1.2-.9 0-1.4-.6-1.4-1.5 0-1 .2-1.7.6-2.7.3-.8.4-1.5.4-2.5 0-1.6.3-2.8 1.1-2.8z"
      />
      <path
        {...base}
        strokeWidth={1.9}
        fill="currentColor"
        fillOpacity={0.18}
        d="M16.5 9c1.4 0 2.3 1.1 2.3 2.8 0 1.5-.3 2.3-1 3.3-.5.8-.7 1.3-.8 2.2-.1.8-.5 1.2-1.2 1.2-.9 0-1.4-.6-1.4-1.5 0-1 .2-1.7.6-2.7.3-.8.4-1.5.4-2.5C15.4 10.2 15.7 9 16.5 9z"
      />
      <path {...base} {...soft} strokeWidth={1.9} d="M5 19.5c0 1.4 3 2.4 7 2.4s7-1 7-2.4" />
    </svg>
  );
}
