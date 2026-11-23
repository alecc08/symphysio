#!/usr/bin/env python3
"""The Symphysio brand mark, and everything derived from it.

This file is the single source of truth for the logo. Run it after any change to
the mark and it rewrites

  frontend/public/icons/brandmark.svg            the mark, gradient heart
  frontend/public/icons/brandmark-reversed.svg   the mark, white heart, for dark tiles
  frontend/public/icons/app-icon.svg             the launcher tile
  frontend/public/icons/favicon.svg              the tab icon
  frontend/public/icons/*.png                    512 / 512 maskable / 192 / 180 apple touch
  frontend/src/components/icons/brandmark.ts     the same geometry, used by the in-app mark

What the mark is, in the order you notice it: a heart (care), the Rod of
Asclepius standing inside it (medicine), a forearm crutch leaning in from the
right, holding the heart up, and a plaster across the upper left (the injury).
The plaster is not drawn on top of the heart - it is cut clean through it and
repainted in the heart's own colour where it sticks out, which is what stops the
four parts reading as four separate clipart objects.

The rod is not hand drawn: it is the U+2695 glyph geometry from Twemoji
(https://github.com/twitter/twemoji), CC-BY 4.0, lifted from the three white
shapes of its 36x36 grid and scaled onto the heart. See docs/CREDITS.md.

Needs rsvg-convert for the PNGs.

Usage:  python3 scripts/gen_brand_assets.py
"""

from __future__ import annotations

import math
import re
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "frontend" / "public" / "icons"
TS_OUT = ROOT / "frontend" / "src" / "components" / "icons" / "brandmark.ts"
TWEMOJI_URL = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/svg/2695.svg"
TWEMOJI_LOCAL = Path.home() / "scratch" / "icons" / "2695.svg"

# ------------------------------------------------------------------ palette
#
# Two colours: one green and white. The green is the one the UI already calls
# `--color-physio` and the manifest calls `theme_color`. No gradient, no second
# tone - where the mark looks like it has a third colour, that is the page
# showing through the plaster, which is the whole trick.

GREEN = "#0D9488"
WHITE = "#FFFFFF"

# ----------------------------------------------------------------- geometry

# the heart, in a 24x24 grid
HEART = (
    "M12 22.4C7.2 19.2 3.6 16 3.6 12.1C3.6 8.6 6.1 6.2 8.9 6.2"
    "C10.4 6.2 11.5 7 12 8.1C12.5 7 13.6 6.2 15.1 6.2"
    "C17.9 6.2 20.4 8.6 20.4 12.1C20.4 16 16.8 19.2 12 22.4Z"
)

# the rod: measured bbox of the Twemoji glyph's white shapes, on its 36 grid
ROD_X0, ROD_Y0, ROD_W, ROD_H = 6.958, 2.0, 20.107, 32.0
ROD_CX, ROD_CY = ROD_X0 + ROD_W / 2, ROD_Y0 + ROD_H / 2
ROD_HEIGHT = 11.5  # how tall the rod stands, in the 24 grid
ROD_AT = (11.9, 13.8)  # where its centre goes

# the plaster: centre x, centre y, lean deg, body w/h/r, pad w/h/r
BAND = (5.7, 9.9, -34.0, 6.4, 2.85, 1.42, 3.6, 1.85, 0.62)

# the crutch: centre x, centre y, lean deg, scale, then 24-grid stroke widths
CRUTCH = (18.4, 14.6, -24.0, 0.64)
CRUTCH_PATHS = [
    (0.72, "M-2.7 -6.4H2.7"),  # underarm rest
    (0.50, "M-2.3 -6.4C-2.1 -4.2 -1.8 -2.8 -1.5 -1.6"),  # stay
    (0.50, "M2.3 -6.4C2.1 -4.2 1.8 -2.8 1.5 -1.6"),  # stay
    (0.50, "M-1.9 -1.5H1.9"),  # cuff
    (0.66, "M0 -1.5C0.1 0.6 -0.2 2.4 -0.4 5.4"),  # shaft
    (0.95, "M-0.4 5.4L-0.5 6.6"),  # ferrule
]
HALO = 0.55  # extra girth under the crutch; invisible inside the heart, keeps
# the thin parts alive where the crutch leaves it

MARK_CENTRE = (11.6, 14.3)  # bbox centre of the whole mark, for centring in a tile


def rod_shapes() -> tuple[str, str, str]:
    """head circle, snake path and staff path of Twemoji U+2695, 36 grid."""
    if TWEMOJI_LOCAL.exists():
        src = TWEMOJI_LOCAL.read_text()
    else:
        with urllib.request.urlopen(TWEMOJI_URL, timeout=30) as r:  # noqa: S310
            src = r.read().decode()
        TWEMOJI_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        TWEMOJI_LOCAL.write_text(src)
    head = snake = staff = ""
    for m in re.finditer(r'<(circle|path)\b[^>]*fill="#FFF"[^>]*/>', src):
        tag = m.group(0)
        if tag.startswith("<circle"):
            nums = {k: re.search(rf'{k}="([\d.]+)"', tag).group(1) for k in ("cx", "cy", "r")}
            head = '<circle cx="{cx}" cy="{cy}" r="{r}"/>'.format(**nums)
        else:
            d = re.search('d="([^"]+)"', tag).group(1)
            if d.startswith("M17 19.81"):
                staff = f'<path d="{d}"/>'
            else:
                snake = f'<path d="{d}"/>'
    if not (head and snake and staff):
        raise SystemExit("could not find the three white shapes in the Twemoji glyph")
    return head, snake, staff


def rrect(w: float, h: float, r: float, rot: float, cx: float, cy: float) -> str:
    """A rounded rectangle as absolute path data, rotated about (cx, cy).

    Path data cannot carry a transform and the plaster has to work as a mask, so
    the lean is baked into the coordinates here.
    """
    rad = math.radians(rot)
    cos, sin = math.cos(rad), math.sin(rad)

    def t(px: float, py: float) -> tuple[float, float]:
        return (cx + px * cos - py * sin, cy + px * sin + py * cos)

    x, y = -w / 2, -h / 2
    k = {c: t(*v) for c, v in {
        "a": (x + r, y), "b": (x + w - r, y), "c": (x + w, y + r), "d": (x + w, y + h - r),
        "e": (x + w - r, y + h), "f": (x + r, y + h), "g": (x, y + h - r), "i": (x, y + r),
    }.items()}
    n = lambda c: f"{k[c][0]:.2f} {k[c][1]:.2f}"
    return (
        f"M{n('a')}L{n('b')}A{r} {r} 0 0 1 {n('c')}L{n('d')}A{r} {r} 0 0 1 {n('e')}"
        f"L{n('f')}A{r} {r} 0 0 1 {n('g')}L{n('i')}A{r} {r} 0 0 1 {n('a')}Z"
    )


def crutch_strokes(scale: float, extra: float = 0.0) -> str:
    return "".join(
        f'<path stroke-width="{(w + extra) / scale:.2f}" d="{d}"/>' for w, d in CRUTCH_PATHS
    )


def mark_groups(reversed_: bool, uid: str) -> tuple[str, str]:
    """(defs, body) for the mark.

    Reversed keeps every silhouette identical and only swaps which side of the
    heart is light: the heart goes white, the rod turns deep teal, and the
    plaster paints white where it leaves the heart.
    """
    cut, out = f"cut{uid}", f"out{uid}"
    bx, by, brot, bw, bh, br, pw, ph, pr = BAND
    cx, cy, crot, cs = CRUTCH
    body_hole, pad_hole = rrect(bw, bh, br, brot, bx, by), rrect(pw, ph, pr, brot, bx, by)

    s = ROD_HEIGHT / ROD_H
    rtx, rty = ROD_AT[0] - ROD_CX * s, ROD_AT[1] - ROD_CY * s
    head, snake, staff = rod_shapes()
    tf = f'transform="translate({cx} {cy}) rotate({crot}) scale({cs})"'

    # Two colours, swapped at the heart's edge. The crutch is drawn in the colour
    # of the *heart side* it belongs to, with a halo in the other colour: the halo
    # is invisible where it sits on its own colour and becomes the edge that keeps
    # the thin parts alive where it crosses over.
    heart_fill = WHITE if reversed_ else GREEN
    inner_fill = GREEN if reversed_ else WHITE
    crutch_col = GREEN if reversed_ else WHITE
    halo_col = WHITE if reversed_ else GREEN
    band_col = WHITE if reversed_ else GREEN

    defs = (
        # inside the heart the plaster is cut clean out, the pad left standing
        f'<mask id="{cut}"><rect width="24" height="24" fill="#fff"/>'
        f'<path fill="#000" d="{body_hole}"/><path fill="#fff" d="{pad_hole}"/></mask>'
        # outside the heart it is painted in the heart's own colour, pad punched out
        f'<mask id="{out}"><rect width="24" height="24" fill="#fff"/>'
        f'<path fill="#000" d="{HEART}"/><path fill="#000" d="{pad_hole}"/></mask>'
    )
    body = (
        f'<g mask="url(#{cut})"><path fill="{heart_fill}" d="{HEART}"/>'
        f'<g fill="{inner_fill}"><g transform="translate({rtx:.2f} {rty:.2f}) scale({s:.4f})">'
        f"{head}{snake}{staff}</g></g>"
        f'<g fill="none" stroke-linecap="round" stroke-linejoin="round" {tf}>'
        f'<g stroke="{halo_col}">{crutch_strokes(cs, HALO)}</g>'
        f'<g stroke="{crutch_col}">{crutch_strokes(cs)}</g></g></g>'
        f'<g mask="url(#{out})"><path fill="{band_col}" d="{body_hole}"/></g>'
    )
    return defs, body


def mark_svg(*, reversed_: bool = False, tile: str | None = None, size: int | None = None,
             scale: float = 1.0, uid: str = "b", pretty: bool = False) -> str:
    defs, body = mark_groups(reversed_, uid)
    if tile:
        ox = 12.0 - scale * MARK_CENTRE[0]
        oy = 12.0 - scale * MARK_CENTRE[1]
        body = (
            f'<rect width="24" height="24" rx="5.2" fill="{tile}"/>'
            f'<g transform="translate({ox:.2f} {oy:.2f}) scale({scale:.2f})">{body}</g>'
        )
    dims = f' width="{size}" height="{size}"' if size else ""
    sep = "\n  " if pretty else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"{dims}>'
        f"{sep}<defs>{defs}</defs>{sep}{body}{sep}</svg>"
    )


# ------------------------------------------------------------------ outputs

TS_TEMPLATE = '''/* The brand mark's geometry - generated by scripts/gen_brand_assets.py.

   Do not hand-edit: change the generator and re-run it, so the mark in the app
   and the files under public/icons can never disagree.

   The rod is the U+2695 glyph geometry from Twemoji (https://github.com/twitter/twemoji),
   CC-BY 4.0 - see docs/CREDITS.md.
*/

/** the mark has exactly two colours: one green and white */
export const BRAND_GREEN = %r;
export const BRAND_WHITE = %r;

export const BRAND_HEART =
  %r;

/** the plaster, as a knockout: body first, pad as a hole in the hole */
export const BRAND_BAND_BODY =
  %r;
export const BRAND_BAND_PAD =
  %r;

/** forearm crutch, upright about the origin; the two widths are the stroke and
 *  the halo that keeps the thin parts alive outside the heart, already divided
 *  by the transform scale so they can be used verbatim */
export const BRAND_CRUTCH_TRANSFORM = %r;
export const BRAND_CRUTCH_PATHS = [
%s
] as const;

/** Twemoji U+2695 (CC-BY 4.0), scaled onto the heart */
export const BRAND_ROD_TRANSFORM = %r;
export const BRAND_ROD_HEAD = { cx: %s, cy: %s, r: %s } as const;
export const BRAND_ROD_SNAKE =
  %r;
export const BRAND_ROD_STAFF =
  %r;
'''


def emit_ts() -> None:
    cx, cy, crot, cs = CRUTCH
    s = ROD_HEIGHT / ROD_H
    rtx, rty = ROD_AT[0] - ROD_CX * s, ROD_AT[1] - ROD_CY * s
    head, snake, staff = rod_shapes()
    nums = {k: re.search(rf'{k}="([\d.]+)"', head).group(1) for k in ("cx", "cy", "r")}
    d_of = lambda tag: re.search('d="([^"]+)"', tag).group(1)
    rows = ",\n".join(
        f'  ["{d}", {(w / cs):.2f}, {(w + HALO) / cs:.2f}]' for w, d in CRUTCH_PATHS
    )
    bx, by, brot, bw, bh, br, pw, ph, pr = BAND
    TS_OUT.write_text(
        TS_TEMPLATE
        % (
            GREEN,
            WHITE,
            HEART,
            rrect(bw, bh, br, brot, bx, by),
            rrect(pw, ph, pr, brot, bx, by),
            f"translate({cx:g} {cy:g}) rotate({crot:g}) scale({cs:g})",
            rows,
            f"translate({rtx:.2f} {rty:.2f}) scale({s:.4f})",
            nums["cx"],
            nums["cy"],
            nums["r"],
            d_of(snake),
            d_of(staff),
        )
    )
    print(f"  wrote {TS_OUT.relative_to(ROOT)}")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(f"  wrote {path.relative_to(ROOT)}")


def png(svg: str, size: int, out: Path) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(out), "-"],
        input=svg.encode(),
        check=True,
    )
    print(f"  wrote {out.relative_to(ROOT)}")


def main() -> None:
    print("brand mark:")
    write(ICONS / "brandmark.svg", mark_svg(pretty=True))
    write(ICONS / "brandmark-reversed.svg", mark_svg(reversed_=True, pretty=True))
    write(ICONS / "app-icon.svg", mark_svg(reversed_=True, tile=GREEN, pretty=True))
    # the tab icon is the tile, not the bare mark: at 16 px a solid tile with the
    # heart knocked out of it still reads, a 16 px heart does not
    write(ICONS / "favicon.svg", mark_svg(reversed_=True, tile=GREEN, size=64, pretty=True))
    emit_ts()

    print("icons:")
    png(mark_svg(reversed_=True, tile=GREEN), 512, ICONS / "icon-512.png")
    png(mark_svg(reversed_=True, tile=GREEN, scale=0.64), 512, ICONS / "icon-512-maskable.png")
    png(mark_svg(reversed_=True, tile=GREEN), 192, ICONS / "icon-192.png")
    png(mark_svg(reversed_=True, tile=GREEN), 180, ICONS / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
