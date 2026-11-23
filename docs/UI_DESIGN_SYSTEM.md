# UI design system

The product is a **tap target with a database behind it**, so the design system
optimises for: one thumb, one hand, in profile, in daylight, while holding a
baby. Everything else is secondary.

## The interaction contract

| Surface | Contract |
| --- | --- |
| Log | 2 taps to record anything: tile → preset. Optional detail is always behind an explicit control, never in the way. |
| Every write | an Undo pill for 5 s that reverses it (client-side re-`POST` for deletes, `DELETE` for creates) |
| Every quick-log drawer | a `Now / -15m / -1h / -3h / Custom` time strip, because a late entry with the wrong timestamp corrupts the lag analysis |
| Presets | add, remove, reorder, restore — from the drawer *and* Settings, never locked behind an admin screen |
| Numbers | every chart states its window and its units; a chart with too little data says so instead of drawing something confident |

## Palette

Tokens live in `src/index.css` under `@theme` (Tailwind 4). Dark mode re-declares
the same custom properties under `prefers-color-scheme: dark`, so no class
juggling and no flash.

| Token | Light | Dark | Used for |
| --- | --- | --- | --- |
| `canvas` | `#f8fafc` | `#0b1220` | page |
| `card` | `#ffffff` | `#172033` | sheets, cards, inputs |
| `ink` | `#0f172a` | `#e8eefc` | text |
| `muted` | `#64748b` | `#93a4c2` | captions, secondary |
| `line` | `#e2e8f0` | `#273349` | hairlines, empty bars |
| `physio` | `#0d9488` | `#0d9488` | Physio fills, primary buttons |
| `symptom` | `#e11d48` | `#e11d48` | Symptom fills, severity ≥ 7 |
| `relief` | `#4f46e5` | `#4f46e5` | Relief/Meds fills |
| `trigger` | `#d97706` | `#d97706` | Trigger fills |
| `physio-ink` … `trigger-ink` | same hues | brightened (`#2dd4bf`, `#fb7185`, `#818cf8`, `#fbbf24`) | **icon line-art and text accents** |
| `*-soft` | pale tint | deep tint | tile and chip backgrounds |

The `-ink` pair exists because a mid-tone accent on a deep tint is unreadable in
dark mode while the same accent must stay dark-on-pale in light mode. Keeping one
token for both meant brightening `physio` and breaking the white text on
`bg-physio` buttons, so fills and line-art got separate tokens.

Rules:

- Four domains, four hues, used consistently: teal = exercise, rose = symptom,
  indigo = relief, amber = trigger. A user should be able to read the History
  feed by colour alone.
- Never more than one hue per surface; the tile carries its own tint plus border
  (`bg-physio-soft` + `border-physio/25`).
- Severity drives colour: 1–3 teal, 4–6 amber, 7–10 rose.

## Tiles

```
┌─ rounded-tile (1.25rem), border/25, tint background, p-4 ─┐
│ Label            text-lg font-extrabold tracking-tight ink │
│                                                         │
│ caption                    hero icon 44px, domain hue     │
│ text-xs font-semibold muted                               │
└─────────────────────────────────────────────────────────┘
min-height 124px · active: scale(0.96), shadow removed
```

Home is a 2×2 grid: Physio, Symptoms, Relief/Meds, Triggers. Four tiles is the
whole logging vocabulary; anything else is a preset inside one of them.

## Iconography

`src/components/icons/`: hand-written SVG, no icon library, no emoji.

**The rule is that a glyph must be nameable in one word by someone who has never
opened the app.** An earlier set was thematic but abstract — a pelvic "hammock
lifting a load" for physio, a body map with a pelvic flare for symptoms — and in
user testing it read as a cup, a balloon, a sparkle and a pair of right feet. It
was replaced. What ships now:

| Kind | Glyph | Why it wins |
| --- | --- | --- |
| Physio | dumbbell with an upward arrow | "exercise, and it gets heavier" — no teaching needed, and progressive loading is the actual concept |
| Symptoms | body silhouette with a lightning bolt over the sore area | body + bolt is already the universal shorthand for pain; the silhouette is filled so it survives at 44 px |
| Relief / Meds | thermometer with a snowflake | heat **and** cold therapy in one shape; a heat pack alone read as an inhaler, a pill-and-thermometer pair read as a pharmacy logo |
| Triggers | a left and a right footprint, walking | "activity you did" — mirrored on purpose (two same-curve feet read as two right feet), and the toe dots are what turn a blob into a foot |

Craft rules that keep the four a family:

- **Duotone**: a soft-filled body (`fill: currentColor; fill-opacity .16–.2`) plus
  `currentColor` strokes at 2 (primary) and 1.3 (detail at ~55 % opacity).
- **Canvas**: heroes on 48×48, compact variants on 24×24, brand mark on 24×24.
- **`currentColor` only.** No hex inside the glyphs, so dark mode, hover and
  active states are one class change.
- **Detail layers are allowed to be decorative, shapes are not.** Thin inner
  arcs are fine; a shape that only makes sense with a legend is not.
- **Geometry is reviewed as pixels, not as paths.** Candidates go on a board
  rendered at 88 px and 44 px on light *and* dark tint chips — that is where the
  abstract set was rejected and where "two right feet" was caught.
- **Compact icons are re-drawn, not shrunk.** The 24 px versions drop the detail
  layer, thicken strokes and keep only the parts that survive; a scaled-down hero
  loses the toe dots and the snowflake, which is the whole point of the glyph.
- **The brand mark is the exception, not a fifth tile icon** (`BrandMark`, and the
  same geometry in `public/icons/brandmark*.svg`): a heart, the Rod of Asclepius
  standing inside it, a forearm crutch leaning in from the right to hold it up,
  and a plaster across the upper left. **Two colours, no gradient**: one green and
  white, the green being the UI's own `--color-physio` and the manifest's
  `theme_color`. It is not `currentColor`, because the plaster is a knockout and
  the trick only reads if both sides of the heart are known colours. What looks
  like a third colour is the page showing through the plaster — light theme reads
  green + white, dark theme reads green + near-black, with no second asset.
- **The mark is one object, not clipart.** The plaster is cut clean *through* the
  heart — inside the heart's silhouette it is negative space with its pad left
  standing, outside it is painted in the heart's own colour. That single rule is
  what binds rod, crutch and heart into one shape instead of four stickers. The
  crutch carries a halo stroke in the heart's colour: invisible inside, an edge
  that keeps the thin parts alive where the crutch leaves the heart.
- **The rod is not hand drawn.** It is the U+2695 glyph geometry from Twemoji
  (CC-BY 4.0, see `docs/CREDITS.md`), scaled onto the heart. Drawn-from-scratch
  attempts read as a fence or an eel; the glyph is proven at emoji sizes.
- PNG icon sizes (512, maskable 512, 192, apple-touch 180), `favicon.svg`,
  `app-icon.svg`, `brandmark.svg`, `brandmark-reversed.svg` and the TS geometry
  the app renders all come from **`scripts/gen_brand_assets.py`** — one geometry,
  run it and every artifact moves together. The favicon is the tile rather than
  the bare mark, because a 16 px heart loses the rod entirely while a knocked-out
  heart on a tile still reads.
- Icons are used **redundantly with colour and text**: the History feed prints the
  kind glyph next to the entry, so the feed is readable without relying on the
  hue alone.

## Motion

`src/styles/animations.css` — five named animations, nothing else.

| Class | What | Duration |
| --- | --- | --- |
| `log-tile` | press: `scale(.96)` + shadow | 140 ms |
| `animate-check-draw` | tick stroke draw on save | 280 ms |
| `sheet-enter` | quick-log drawer rise | 220 ms |
| `toast-enter` / `row-enter` | Undo pill, feed rows | 180 / 160 ms |
| `bar-grow` | chart bars `scaleY(.05 → 1)` | 260 ms |

Easing is one curve, `cubic-bezier(.16,1,.3,1)` (or `.22,1,.36,1` for the press)
— everything arrives with a decelerating settle. Only `transform`, `opacity` and
`stroke-dashoffset` are animated: no layout properties, so animation never
reflows a list you are trying to tap. `prefers-reduced-motion: reduce` disables
all of it and resets the transforms.

**CSP constraint:** the app runs `style-src 'self'` with no `unsafe-inline`, so
React must not emit `style="…"` attributes. Chart bar heights are therefore
applied through the DOM API in an effect (`node.style.height = …`), not as an
inline style. Anything that needs a computed geometry goes through a ref.

## Type and metrics

- Font: the system stack (`-apple-system, … Inter, Segoe UI`), no webfont — one
  less thing to download on a hotel connection, and it matches the OS chrome of
  the home-screen icon.
- Scale: `text-2xl` page title, `text-lg` tile label, default body, `text-xs`
  captions and chips. Tabular numerals (`tabular-nums`) on anything numeric so
  severity grids do not jitter.
- Radii: `--radius-tile: 1.25rem` for tiles, `rounded-2xl` for chips/sheet,
  `rounded-full` for pill buttons.
- Touch targets ≥ 44 px: severity buttons are `h-11` and share the row width,
  chips are `py-2`, the bottom nav is icon + label with safe-area padding.
- Layout is `max-w-lg` centred; the same build is used at 390×844 and on a
  desktop browser without a second design.

## States

- **Loading**: one pulsing "Loading Symphysio…" line; no spinners inside tiles.
- **Empty**: every list explains what to log rather than showing a blank card.
- **Error**: an inline rose message from the API's `detail`, never a toast storm;
  the toast area holds only one Undo pill at a time.
- **Offline**: the service worker serves the shell, and the offline page says the
  network is missing rather than pretending the data is there. API responses are
  never cached, so a stale number is structurally impossible.
- **Unauthenticated**: the auth screen *is* the register screen — one form, one
  button, with the password rules shown as you type.

## Accessibility

- Every control is a real `<button>`/`<input>`; toggles expose `aria-pressed`,
  drawers expose `aria-expanded`, icons are `aria-hidden` with the label on the
  control ("Remove Scar Pain", "Edit Stiffness").
- `:focus-visible` draws a 2 px teal outline with a 2 px offset — visible on
  keyboard, invisible to touch.
- The drawer traps Escape (closes), and the backdrop is a button with an
  `aria-label`.
- Severity is ten large buttons (1–10; the optional pain-during scale runs 0–10),
  not a slider: a slider is hard to set precisely one-handed and exposes no value
  to a screen reader.
- Colour is never the only signal: severity also prints the number, domains print
  their label.
- Contrast: text tokens are ≥ 4.5:1 in both modes; the `-ink` accents exist in
  part to keep icon strokes ≥ 3:1 against the dark tints.
