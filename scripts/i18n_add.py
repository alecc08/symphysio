#!/usr/bin/env python3
"""Append dictionary entries to en.ts and fr.ts in matched pairs.

A translation file that can drift from its source is a translation file that
silently ships English. So the pairs are added together or not at all: this reads
a TSV of `key<TAB>english<TAB>french`, refuses a row with no French and a key that
is already there, and writes both files in one pass. `npm run build` is what
catches the reverse mistake — fr.ts is typed against en.ts, so a key added by hand
to one file fails the compile.

    python3 scripts/i18n_add.py pairs.tsv     # run from anywhere
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "frontend" / "src" / "i18n" / "en.ts"
FR = ROOT / "frontend" / "src" / "i18n" / "fr.ts"


def insert(path: str, block: str, closing: str) -> None:
    text = open(path).read()
    if text.count(closing) != 1:
        raise SystemExit(f"{path}: closing marker {closing!r} is not unique")
    open(path, "w").write(text.replace(closing, "\n" + block + closing))


def main(pairs_path: str) -> None:
    en_lines, fr_lines, keys = [], [], []
    for raw in Path(pairs_path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("//"):
            en_lines.append("  " + line)
            fr_lines.append("  " + line)
            continue
        key, _, rest = line.partition("\t")
        en_text, _, fr_text = rest.partition("\t")
        if not fr_text:
            raise SystemExit(f"missing french for {key}")
        keys.append(key)
        en_lines.append(f'  "{key}": {en_text},')
        fr_lines.append(f'  "{key}": {fr_text},')
    existing = set(re.findall(r'^\s{2}"([\w.]+)":', EN.read_text(encoding="utf-8"), re.M))
    clash = sorted(k for k in keys if k in existing)
    if clash:
        raise SystemExit(f"keys already in en.ts: {clash}")
    insert(EN, "\n".join(en_lines), "} as const;")
    insert(FR, "\n".join(fr_lines), "\n};")
    print(f"added {len(keys)} keys")


if __name__ == "__main__":
    main(sys.argv[1])
