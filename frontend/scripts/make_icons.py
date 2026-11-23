#!/usr/bin/env python3
"""Render the master app icon SVG into the PNG sizes the PWA manifest needs.

Usage (from frontend/):  python3 scripts/make_icons.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "public" / "icons"
MASTER = ICONS / "app-icon.svg"
SIZES = [
    ("apple-touch-icon.png", 180, False),
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-512-maskable.png", 512, True),
]
FIRST_RECT = re.compile(r"^\s*<rect\b[^>]*/>\s*\n", re.MULTILINE)


def render(target: Path, size: int, maskable: bool) -> None:
    source = MASTER.read_text()
    if maskable:
        # Maskable icons must be full-bleed: drop the rounded tile rect and
        # shrink the artwork into the safe zone (80% of the canvas).
        artwork = FIRST_RECT.sub("", source)
        artwork = artwork.replace("</svg>", "").split(">", 1)[1]
        source = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
            f'width="{size}" height="{size}">'
            '<rect width="512" height="512" fill="#0D9488" />'
            '<g transform="translate(76.8 76.8) scale(0.7)">' + artwork + "</g></svg>"
        )
    temp = ICONS / f".render-{size}{'-m' if maskable else ''}.svg"
    temp.write_text(source)
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size), str(temp), "-o", str(target)],
            check=True,
        )
    finally:
        temp.unlink(missing_ok=True)
    print(f"wrote public/icons/{target.name} ({size}x{size})")


def main() -> int:
    if not MASTER.is_file():
        print(f"missing {MASTER}", file=sys.stderr)
        return 1
    for filename, size, maskable in SIZES:
        render(ICONS / filename, size, maskable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
