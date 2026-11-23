#!/usr/bin/env python3
"""Regenerate ``app/data/common_passwords.txt`` (blocklist for weak passwords).

Sources (public, non-CC0-restricted credential corpora):
  * NCSC 100k most-used passwords
  * SecLists 10k most-common

Usage:  uv run python scripts/build_password_list.py [--limit 20000]
"""

from __future__ import annotations

import argparse
import string
import urllib.request
from pathlib import Path

SOURCES = (
    "https://raw.githubusercontent.com/danielmiessler/SecLists/master/"
    "Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt",
    "https://raw.githubusercontent.com/danielmiessler/SecLists/master/"
    "Passwords/Common-Credentials/10k-most-common.txt",
)
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "data" / "common_passwords.txt"
PRINTABLE = set(string.printable) - set(string.whitespace)


def fetch(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (https, no eval)
        return response.read().decode("utf-8", errors="replace").splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20_000)
    args = parser.parse_args()

    seen: list[str] = []
    unique: set[str] = set()
    for url in SOURCES:
        for line in fetch(url):
            value = line.strip().lower()
            if not (3 <= len(value) <= 64):
                continue
            if any(char not in PRINTABLE for char in value):
                continue
            if value in unique:
                continue
            unique.add(value)
            seen.append(value)
            if len(seen) >= args.limit:
                break

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(seen) + "\n", encoding="utf-8")
    print(f"wrote {len(seen)} entries to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
