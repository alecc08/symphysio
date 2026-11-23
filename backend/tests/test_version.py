"""One version of record: the repo-root VERSION file.

`package.json` and `pyproject.toml` also carry version numbers because their
tooling wants them, and nothing reads them at runtime — so they are not checked
here. What must agree is the running app and the file the release workflow tags
from.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.main import __version__, create_app

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")


def test_the_version_file_holds_plain_semver():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert SEMVER.fullmatch(version), version
    assert __version__ == version


def test_the_api_document_reports_the_same_version():
    assert create_app().version == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_the_changelog_documents_the_current_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"(?m)^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog)
    assert re.search(rf"(?m)^\[{re.escape(version)}\]: https://", changelog)
