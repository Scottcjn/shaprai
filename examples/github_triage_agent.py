#!/usr/bin/env python3
"""GitHub Triage Agent example.

Demonstrates a ShaprAI agent that triages GitHub issues by:
1. Connecting to the Elyan ecosystem (RustChain wallet + Beacon discovery)
2. Fetching open issues from a repository
3. Scoring priority based on keywords, labels, and age
4. Assigning suggested labels and priority levels
5. Detecting potential duplicates via title similarity

This is a standalone example -- it does not require a running LLM.
The triage logic uses rule-based heuristics that a real deployment
would augment with an LLM for nuanced classification.

Usage:
    python examples/github_triage_agent.py
    python examples/github_triage_agent.py --repo Scottcjn/rustchain-bounties
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.integrations.elyan_ecosystem import ElyanEcosystem, EcosystemConfig


# ── Priority keywords ────────────────────────────────────────

CRITICAL_KEYWORDS = ["crash", "data loss", "security", "vulnerability", "exploit", "cve"]
HIGH_KEYWORDS = ["bug", "broken", "error", "fail", "regression", "blocker"]
MEDIUM_KEYWORDS = ["enhancement", "feature", "improvement", "request"]
LOW_KEYWORDS = ["docs", "typo", "cosmetic", "style", "nit", "question"]

# ── Label suggestions ────────────────────────────────────────

LABEL_RULES: List[Tuple[str, List[str]]] = [
    ("bug", ["bug", "error", "crash", "broken", "regression", "fail"]),
    ("security", ["security", "vulnerability", "exploit", "cve", "injection"]),
    ("enhancement", ["feature", "enhancement", "improvement", "request"]),
    ("documentation", ["docs", "documentation", "readme", "typo"]),
    ("good first issue", ["beginner", "easy", "starter", "simple", "first"]),
    ("bounty", ["bounty", "rtc", "reward", "pay"]),
]


@dataclass
class TriageResult:
    """Result of triaging a single issue.

    Attributes:
        issue_number: GitHub issue number.
        title: Issue title.
        priority: Assigned priority (critical, high, medium, low).
        suggested_labels: Labels to apply.
        duplicate_of: Issue number if a potential duplicate was found.
        summary: One-line triage summary.
    """

    issue_number: int
    title: str
    priority: str = "medium"
    suggested_labels: List[str] = field(default_factory=list)
    duplicate_of: Optional[int] = None
    summary: str = ""


def score_priority(title: str, body: str = "") -> str:
    """Score issue priority based on keyword analysis.

    Args:
        title: Issue title.
        body: Issue body text.

    Returns:
        Priority string: critical, high, medium, or low.
    """
    text = (title + " " + body).lower()

    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            return "critical"

    for kw in HIGH_KEYWORDS:
        if kw in text:
            return "high"

    for kw in LOW_KEYWORDS:
        if kw in text:
            return "low"

    for kw in MEDIUM_KEYWORDS:
        if kw in text:
            return "medium"

    return "medium"


def suggest_labels(title: str, body: str = "") -> List[str]:
    """Suggest labels based on issue content.

    Args:
        title: Issue title.
        body: Issue body text.

    Returns:
        List of suggested label names.
    """
    text = (title + " " + body).lower()
    labels = []

    for label, keywords in LABEL_RULES:
        if any(kw in text for kw in keywords):
            labels.append(label)

    return labels


def find_duplicates(
    title: str,
    existing_issues: List[Dict[str, Any]],
    threshold: float = 0.65,
) -> Optional[int]:
    """Find potential duplicate issues by title similarity.

    Uses SequenceMatcher for fuzzy string matching.

    Args:
        title: New issue title to check.
        existing_issues: List of existing issues with 'number' and 'title'.
        threshold: Similarity threshold (0-1).

    Returns:
        Issue number of the best duplicate match, or None.
    """
    best_match = None
    best_score = 0.0

    title_lower = title.lower().strip()

    for issue in existing_issues:
        existing_title = issue.get("title", "").lower().strip()
        score = SequenceMatcher(None, title_lower, existing_title).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = issue.get("number")

    return best_match


def triage_issue(
    issue: Dict[str, Any],
    existing_issues: Optional[List[Dict[str, Any]]] = None,
) -> TriageResult:
    """Triage a single GitHub issue.

    Args:
        issue: Issue dict with 'number', 'title', 'body'.
        existing_issues: Other issues to check for duplicates.

    Returns:
        TriageResult with priority, labels, and duplicate info.
    """
    number = issue.get("number", 0)
    title = issue.get("title", "")
    body = issue.get("body", "") or ""

    priority = score_priority(title, body)
    labels = suggest_labels(title, body)
    duplicate_of = None

    if existing_issues:
        # Exclude self from duplicate search
        others = [i for i in existing_issues if i.get("number") != number]
        duplicate_of = find_duplicates(title, others)

    summary_parts = [f"Priority: {priority}"]
    if labels:
        summary_parts.append(f"Labels: {', '.join(labels)}")
    if duplicate_of:
        summary_parts.append(f"Possible duplicate of #{duplicate_of}")

    return TriageResult(
        issue_number=number,
        title=title,
        priority=priority,
        suggested_labels=labels,
        duplicate_of=duplicate_of,
        summary=" | ".join(summary_parts),
    )


def demo_triage() -> List[TriageResult]:
    """Run a demo triage on sample issues.

    Returns:
        List of TriageResult for the sample issues.
    """
    sample_issues = [
        {"number": 101, "title": "Server crash on epoch settlement", "body": "Node crashes with segfault during epoch 450 settlement."},
        {"number": 102, "title": "Add dark mode to block explorer", "body": "Feature request: dark mode theme for the explorer UI."},
        {"number": 103, "title": "Typo in README installation section", "body": "Line 42 says 'pip instal' instead of 'pip install'."},
        {"number": 104, "title": "Security vulnerability in wallet transfer endpoint", "body": "The /wallet/transfer endpoint accepts unauthenticated requests."},
        {"number": 105, "title": "Node crash during epoch settlement", "body": "Similar to #101, node goes down at settlement time."},
        {"number": 106, "title": "Bounty: Add SPARC miner support (50 RTC)", "body": "Implement SPARC architecture detection in fingerprint_checks.py."},
    ]

    results = []
    for issue in sample_issues:
        result = triage_issue(issue, existing_issues=sample_issues)
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="ShaprAI GitHub Triage Agent")
    parser.add_argument("--repo", default="", help="GitHub repo (owner/name) to triage")
    args = parser.parse_args()

    print("=" * 60)
    print("ShaprAI GitHub Triage Agent")
    print("=" * 60)
    print()

    # Connect to Elyan ecosystem (offline mode -- no live network calls needed)
    config = EcosystemConfig(
        auto_register_beacon=False,
        auto_create_wallet=False,
    )
    eco = ElyanEcosystem(config=config)
    profile = eco.connect_agent(
        name="triage-demo",
        capabilities=["issue_triage", "label_assignment", "duplicate_detection"],
        platforms=["github"],
        description="Demo triage agent for GitHub issues",
    )
    print(f"Agent: {profile.name}")
    print(f"Wallet: {profile.wallet_id}")
    print()

    # Run triage on sample issues
    print("Triaging sample issues...")
    print("-" * 60)

    results = demo_triage()
    for r in results:
        priority_icon = {
            "critical": "[!!!]",
            "high": "[!! ]",
            "medium": "[!  ]",
            "low": "[   ]",
        }.get(r.priority, "[?  ]")

        print(f"  {priority_icon} #{r.issue_number}: {r.title}")
        print(f"         {r.summary}")
        if r.duplicate_of:
            print(f"         ** Potential duplicate of #{r.duplicate_of}")
        print()

    # Summary
    by_priority = {}
    for r in results:
        by_priority.setdefault(r.priority, []).append(r)

    print("-" * 60)
    print("Triage Summary:")
    for p in ["critical", "high", "medium", "low"]:
        count = len(by_priority.get(p, []))
        if count:
            print(f"  {p.upper():10s}: {count} issue(s)")

    duplicates = [r for r in results if r.duplicate_of]
    if duplicates:
        print(f"  DUPLICATES: {len(duplicates)} detected")

    print()
    print("In production, this agent would:")
    print("  1. Poll GitHub issues via API on a schedule")
    print("  2. Auto-apply labels and priority via GitHub API")
    print("  3. Post triage comments on new issues")
    print("  4. Earn RTC for each issue triaged via RustChain")


if __name__ == "__main__":
    main()
