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

   The brand mark at the bottom is the exception: full colour, generated, and
   documented where it sits.
*/

import { useId } from "react";

import {
  BRAND_BAND_BODY,
  BRAND_BAND_PAD,
  BRAND_CRUTCH_PATHS,
  BRAND_CRUTCH_TRANSFORM,
  BRAND_GREEN,
  BRAND_HEART,
  BRAND_ROD_HEAD,
  BRAND_ROD_SNAKE,
  BRAND_ROD_STAFF,
  BRAND_ROD_TRANSFORM,
  BRAND_WHITE,
} from "./brandmark";

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

/** The product mark: a heart, the Rod of Asclepius standing inside it, a
 *  forearm crutch leaning in from the right to hold it up, and a plaster across
 *  the upper left. The plaster is not painted on top of the heart - it is cut
 *  clean through it and repainted in the heart's own colour where it sticks out,
 *  which is what fuses the four parts into one object.
 *
 *  The numbers are generated: scripts/gen_brand_assets.py writes this set, the
 *  files under public/icons and the launcher PNGs from one geometry, so the
 *  in-app mark can never drift from the app icon. The rod is the U+2695 glyph
 *  geometry from Twemoji, CC-BY 4.0 (docs/CREDITS.md).
 *
 *  It is also the one icon in this file that is not `currentColor`: the plaster
 *  is a knockout, and the trick only reads if both sides of the heart are known
 *  colours - exactly two of them, `BRAND_GREEN` and `BRAND_WHITE`. Mask ids are
 *  per instance, so the mark can appear more than once per page. */
export function BrandMark({ className = "w-5 h-5" }: IconProps) {
  const uid = useId().replace(/:/g, "");
  const cut = `bm-cut-${uid}`;
  const out = `bm-out-${uid}`;
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <defs>
        <mask id={cut}>
          <rect width="24" height="24" fill="#fff" />
          <path fill="#000" d={BRAND_BAND_BODY} />
          <path fill="#fff" d={BRAND_BAND_PAD} />
        </mask>
        <mask id={out}>
          <rect width="24" height="24" fill="#fff" />
          <path fill="#000" d={BRAND_HEART} />
          <path fill="#000" d={BRAND_BAND_PAD} />
        </mask>
      </defs>
      <g mask={`url(#${cut})`}>
        <path fill={BRAND_GREEN} d={BRAND_HEART} />
        <g fill={BRAND_WHITE}>
          <g transform={BRAND_ROD_TRANSFORM}>
            <circle cx={BRAND_ROD_HEAD.cx} cy={BRAND_ROD_HEAD.cy} r={BRAND_ROD_HEAD.r} />
            <path d={BRAND_ROD_SNAKE} />
            <path d={BRAND_ROD_STAFF} />
          </g>
        </g>
        <g
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          transform={BRAND_CRUTCH_TRANSFORM}
        >
          <g stroke={BRAND_GREEN}>
            {BRAND_CRUTCH_PATHS.map(([d, , halo]) => (
              <path key={d} strokeWidth={halo} d={d} />
            ))}
          </g>
          <g stroke={BRAND_WHITE}>
            {BRAND_CRUTCH_PATHS.map(([d, w]) => (
              <path key={d} strokeWidth={w} d={d} />
            ))}
          </g>
        </g>
      </g>
      <g mask={`url(#${out})`}>
        <path fill={BRAND_GREEN} d={BRAND_BAND_BODY} />
      </g>
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

/** Symptoms: a small body with three cartoon pain bolts around it — the visual
 *  shorthand for "something hurts here" that everyone already knows. */
export function SymptomHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path {...base} {...solid} d="M11.5 9.5 6 17.5h3.4L7 23.5l6.6-8.4h-3.7z" />
      <path {...base} {...solid} d="M36.5 9.5 42 17.5h-3.4l2.4 6-6.6-8.4h3.7z" />
      <path {...base} {...solid} opacity={0.85} d="M24 2.5l-4.2 6.4h2.9L20.6 14 26 7.4h-3.1z" />
      <circle {...base} {...soft} cx="24" cy="21" r="3.6" />
      <path
        {...base}
        {...soft}
        d="M18.7 26.6c-2.4 1.6-3.7 4.2-3.7 7.1 0 2.4.7 4.3 1.8 5.5-1.1 3.1-.6 6 1.4 8.2 2.3 2.5 11.3 2.5 13.6 0 1.9-2.2 2.5-5.1 1.4-8.2 1.1-1.2 1.8-3.1 1.8-5.5 0-2.9-1.3-5.5-3.7-7.1z"
      />
    </svg>
  );
}

/** Relief / meds: thermometer and snowflake (heat and cold) plus a pill. */
export function ReliefHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} className={className}>
      <path {...base} {...soft} d="M13 7.5a4 4 0 0 1 8 0v17.6a6.2 6.2 0 1 1-8 0z" />
      <path {...base} strokeWidth={2.2} d="M17 13v15" />
      <circle {...base} {...solid} cx="17" cy="33.5" r="3.1" />
      <path {...base} {...detail} d="M23.5 12.5H28M23.5 18H28" />
      <path {...base} strokeWidth={1.6} d="M35.5 11h9M40 6.5v9M36.8 7.8l6.4 6.4M43.2 7.8l-6.4 6.4" />
      <rect
        {...base}
        x="30"
        y="28"
        width="15"
        height="9"
        rx="4.5"
        transform="rotate(-28 37.5 32.5)"
        fill="currentColor"
        fillOpacity={0.18}
      />
      <path {...base} strokeWidth={1.5} opacity={0.7} d="M33 36.4 42 28.6" />
    </svg>
  );
}

/** Triggers: activity — a left and a right footprint, walking. The toe dots are
 *  what make a blob read as a foot, so they are not optional. */
export function TriggerHero({ className = "w-12 h-12" }: IconProps) {
  return (
    <svg viewBox="0 0 48 48" {...base} strokeWidth={1.7} className={className}>
      <path
        {...base}
        strokeWidth={1.7}
        fill="currentColor"
        fillOpacity={0.2}
        d="M13.2 9.4c2.5 0 4.1 1.9 4.1 4.7 0 2.3-.7 3.6-1.7 5.3-.9 1.4-1.2 2.4-1.4 3.8-.2 1.5-1 2.3-2.2 2.3-1.6 0-2.5-1-2.5-2.6 0-1.7.4-2.8 1.1-4.5.5-1.4.7-2.5.7-4.2 0-2.6.7-4.8 1.9-4.8z"
      />
      <circle {...base} {...solid} cx="17.6" cy="8.2" r="1.5" />
      <circle {...base} {...solid} cx="14.4" cy="6.9" r="1.2" opacity={0.8} />
      <circle {...base} {...solid} cx="11.4" cy="7.4" r="1.05" opacity={0.7} />
      <circle {...base} {...solid} cx="9" cy="8.9" r="0.9" opacity={0.6} />
      <path
        {...base}
        strokeWidth={1.7}
        fill="currentColor"
        fillOpacity={0.2}
        d="M34.8 21.6c-2.5 0-4.1 1.9-4.1 4.7 0 2.3.7 3.6 1.7 5.3.9 1.4 1.2 2.4 1.4 3.8.2 1.5 1 2.3 2.2 2.3 1.6 0 2.5-1 2.5-2.6 0-1.7-.4-2.8-1.1-4.5-.5-1.4-.7-2.5-.7-4.2 0-2.6-.7-4.8-1.9-4.8z"
      />
      <circle {...base} {...solid} cx="30.4" cy="20.4" r="1.5" />
      <circle {...base} {...solid} cx="33.6" cy="19.1" r="1.2" opacity={0.8} />
      <circle {...base} {...solid} cx="36.6" cy="19.6" r="1.05" opacity={0.7} />
      <circle {...base} {...solid} cx="39" cy="21.1" r="0.9" opacity={0.6} />
    </svg>
  );
}

/* ------------------------------------------------- compact 24x24 (nav, chips) */

/* The compact set is not a shrunken hero: at 24 px the small parts vanish, so
   each glyph is re-drawn with fewer elements and heavier strokes. */

export function PhysioIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={2} className={className}>
      <rect {...base} {...soft} x="3" y="7" width="4.4" height="9" rx="1.6" />
      <rect {...base} {...soft} x="16.6" y="7" width="4.4" height="9" rx="1.6" />
      <path {...base} strokeWidth={2.4} d="M7.4 11.5h9.2" />
      <path {...base} d="M12 21.5v-6M9 18l3-3 3 3" />
    </svg>
  );
}

export function SymptomIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={1.9} className={className}>
      <circle {...base} {...soft} cx="12" cy="4.2" r="2.5" />
      <path
        {...base}
        {...soft}
        d="M8.6 7.9c-1.6 1.1-2.4 2.8-2.4 4.7 0 1.6.5 2.8 1.2 3.6-.8 2.1-.4 4.1 1 5.7 1.4 1.7 6.2 1.7 8.4 0 1.3-1.6 1.8-3.6 1-5.7.7-.8 1.2-2 1.2-3.6 0-1.9-.8-3.6-2.4-4.7z"
      />
      <path {...base} {...solid} d="M12.8 8.6 8.2 15.9h3l-1.1 5.5 5.4-7.1h-2.9z" />
    </svg>
  );
}

export function ReliefIcon({ className = "w-5 h-5" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...base} strokeWidth={1.9} className={className}>
      <path {...base} {...soft} d="M8.5 3.6a3.3 3.3 0 0 1 6.6 0v11.2a5.1 5.1 0 1 1-6.6 0z" />
      <path {...base} strokeWidth={2.1} d="M11.8 7.4v8.2" />
      <circle {...base} {...solid} cx="11.8" cy="18.2" r="2.5" />
      <path {...base} {...detail} d="M17.2 7.6H21M17.2 11.6H21" />
      <path {...base} strokeWidth={1.6} d="M17.6 19.6h4.4M19.8 17.4v4.4" />
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
        d="M9.6 6.4c3 0 5 2.4 5 5.9 0 2.9-.8 4.5-2 6.4-1 1.6-1.4 2.8-1.7 4.5-.2 1.7-1.1 2.6-2.5 2.6-1.9 0-3-1.3-3-3.3 0-2.1.5-3.5 1.3-5.5.6-1.6.9-3 .9-5.1 0-3.2.8-5.5 2-5.5z"
      />
      <circle {...base} {...solid} cx="15.2" cy="5.2" r="1.7" />
      <circle {...base} {...solid} cx="11.7" cy="3.9" r="1.35" opacity={0.85} />
      <circle {...base} {...solid} cx="8.3" cy="4.5" r="1.15" opacity={0.7} />
      <path {...base} strokeWidth={1.9} opacity={0.75} d="M18.6 7.6 21 5.2M19.6 11.4h2.8M18.9 15.2l2.1 2.1" />
    </svg>
  );
}
