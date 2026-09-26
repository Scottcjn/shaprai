# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""RTC is experimental and has no monetary value; nothing we ship may say otherwise."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# "1 RTC = $0.10", "RTC ... USD", "$ per RTC" and similar exchange-rate claims
RATE_CLAIM = re.compile(
    r"RTC[^\n]{0,40}(\$\s?\d|USD)|(\$\s?\d|USD)[^\n]{0,40}\bRTC\b", re.IGNORECASE
)


SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "build", "dist", "tests"}


def _tracked(pattern):
    for path in ROOT.rglob(pattern):
        rel = path.relative_to(ROOT).parts
        if not any(part in SKIP_DIRS or part.startswith(".") for part in rel[:-1]):
            yield path


def shipped_files():
    """Everything a user or another model may read as documentation or code."""
    yield from (ROOT / "shaprai").rglob("*.py")
    for pattern in ("*.md", "*.txt", "*.yaml", "*.yml"):
        yield from _tracked(pattern)


def test_scan_covers_nested_docs():
    scanned = {p.relative_to(ROOT).as_posix() for p in shipped_files()}
    assert "llms.txt" in scanned
    for doc in ("shaprai/marketplace/README.md", "tutorials/cli-walkthrough.md"):
        if (ROOT / doc).exists():
            assert doc in scanned


def test_no_rtc_exchange_rate_claims():
    hits = []
    for path in shipped_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RATE_CLAIM.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not hits, "RTC exchange-rate claims:\n" + "\n".join(hits)
