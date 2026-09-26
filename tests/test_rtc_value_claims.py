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


def shipped_files():
    yield from (ROOT / "shaprai").rglob("*.py")
    yield from ROOT.glob("*.md")
    yield from (ROOT / "docs").rglob("*.md")
    yield ROOT / "llms.txt"


def test_no_rtc_exchange_rate_claims():
    hits = []
    for path in shipped_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RATE_CLAIM.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not hits, "RTC exchange-rate claims:\n" + "\n".join(hits)
