#!/usr/bin/env python3
"""Code Review Agent example.

Demonstrates a ShaprAI agent that reviews code for:
1. Common bug patterns and anti-patterns
2. Security concerns (hardcoded secrets, SQL injection, etc.)
3. Style and quality issues
4. ShaprAI QualityGate ethics checks on PR comments

This example uses static analysis heuristics. A production deployment
would combine these checks with LLM-powered semantic analysis.

Usage:
    python examples/code_review_agent.py
    python examples/code_review_agent.py --file path/to/code.py
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.integrations.elyan_ecosystem import ElyanEcosystem, EcosystemConfig
from shaprai.sanctuary.quality_gate import QualityGate


# ── Review patterns ──────────────────────────────────────────

@dataclass
class ReviewFinding:
    """A single finding from a code review.

    Attributes:
        severity: critical, warning, or info.
        category: Category of the finding (security, bug, style, etc.).
        line: Line number (0 if not line-specific).
        message: Human-readable description.
        suggestion: Suggested fix or improvement.
    """

    severity: str
    category: str
    line: int = 0
    message: str = ""
    suggestion: str = ""


@dataclass
class ReviewReport:
    """Complete code review report.

    Attributes:
        filename: File that was reviewed.
        findings: List of review findings.
        quality_score: Overall quality score (0-1).
        lines_reviewed: Number of lines analyzed.
        passed: Whether the code passes review.
    """

    filename: str
    findings: List[ReviewFinding] = field(default_factory=list)
    quality_score: float = 1.0
    lines_reviewed: int = 0
    passed: bool = True


# Security patterns
SECURITY_PATTERNS = [
    (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected", "Use environment variables or a secrets manager"),
    (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected", "Use environment variables"),
    (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected", "Use a secrets manager"),
    (r'eval\s*\(', "Use of eval() is a code injection risk", "Avoid eval; use ast.literal_eval for data parsing"),
    (r'exec\s*\(', "Use of exec() is a code injection risk", "Refactor to avoid dynamic code execution"),
    (r'\.format\(.*\).*(?:SELECT|INSERT|UPDATE|DELETE)', "Possible SQL injection via string formatting", "Use parameterized queries"),
    (r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)', "Possible SQL injection via f-string", "Use parameterized queries"),
    (r'subprocess\.call\(.*shell\s*=\s*True', "Shell injection risk with subprocess", "Use subprocess with shell=False and a list of args"),
    (r'verify\s*=\s*False', "SSL verification disabled", "Enable SSL verification in production"),
]

# Bug patterns
BUG_PATTERNS = [
    (r'except\s*:', "Bare except catches all exceptions including SystemExit", "Specify exception types: except (ValueError, TypeError)"),
    (r'except\s+Exception\s*:', "Broad exception catch may hide bugs", "Catch specific exception types"),
    (r'== None', "Use 'is None' instead of '== None'", "Replace with 'is None'"),
    (r'!= None', "Use 'is not None' instead of '!= None'", "Replace with 'is not None'"),
    (r'type\(\w+\)\s*==', "Use isinstance() instead of type comparison", "Replace with isinstance()"),
    (r'import \*', "Wildcard import pollutes namespace", "Import specific names"),
    (r'TODO|FIXME|HACK|XXX', "Unresolved TODO/FIXME marker", "Resolve or file an issue for tracking"),
]

# Style patterns
STYLE_PATTERNS = [
    (r'^.{120,}$', "Line exceeds 120 characters", "Break long lines for readability"),
    (r'print\(', "print() in production code", "Use logging module instead of print"),
    (r'#\s*noqa', "noqa suppresses linter warnings", "Fix the underlying issue instead of suppressing"),
]


def review_code(code: str, filename: str = "code.py") -> ReviewReport:
    """Review a code snippet for issues.

    Runs security, bug, and style pattern checks against the code.

    Args:
        code: Source code string.
        filename: Name of the file being reviewed.

    Returns:
        ReviewReport with all findings.
    """
    lines = code.split("\n")
    findings: List[ReviewFinding] = []

    for line_num, line in enumerate(lines, start=1):
        # Security checks
        for pattern, message, suggestion in SECURITY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(ReviewFinding(
                    severity="critical",
                    category="security",
                    line=line_num,
                    message=message,
                    suggestion=suggestion,
                ))

        # Bug checks
        for pattern, message, suggestion in BUG_PATTERNS:
            if re.search(pattern, line):
                findings.append(ReviewFinding(
                    severity="warning",
                    category="bug",
                    line=line_num,
                    message=message,
                    suggestion=suggestion,
                ))

        # Style checks
        for pattern, message, suggestion in STYLE_PATTERNS:
            if re.search(pattern, line):
                findings.append(ReviewFinding(
                    severity="info",
                    category="style",
                    line=line_num,
                    message=message,
                    suggestion=suggestion,
                ))

    # Calculate quality score
    critical_count = sum(1 for f in findings if f.severity == "critical")
    warning_count = sum(1 for f in findings if f.severity == "warning")
    info_count = sum(1 for f in findings if f.severity == "info")

    score = 1.0
    score -= critical_count * 0.20
    score -= warning_count * 0.05
    score -= info_count * 0.01
    score = max(0.0, min(1.0, score))

    return ReviewReport(
        filename=filename,
        findings=findings,
        quality_score=round(score, 2),
        lines_reviewed=len(lines),
        passed=critical_count == 0 and score >= 0.60,
    )


def review_pr_comment(comment: str, quality_gate: QualityGate) -> Dict[str, Any]:
    """Review a PR comment for quality using the ShaprAI QualityGate.

    Checks for sycophancy, flattening, and ethical alignment.

    Args:
        comment: The PR comment text.
        quality_gate: QualityGate instance.

    Returns:
        Dict with quality score and ethics report.
    """
    quality_score = quality_gate.score_output("code-reviewer", comment)
    ethics = quality_gate.check_ethics(comment)

    return {
        "quality_score": round(quality_score, 2),
        "ethics_passed": ethics.passed,
        "ethics_score": round(ethics.score, 2),
        "violations": ethics.violations,
        "strengths": ethics.strengths,
    }


def main():
    parser = argparse.ArgumentParser(description="ShaprAI Code Review Agent")
    parser.add_argument("--file", help="Path to a file to review")
    args = parser.parse_args()

    print("=" * 60)
    print("ShaprAI Code Review Agent")
    print("=" * 60)
    print()

    # Connect to Elyan ecosystem (offline mode)
    config = EcosystemConfig(
        auto_register_beacon=False,
        auto_create_wallet=False,
    )
    eco = ElyanEcosystem(config=config)
    profile = eco.connect_agent(
        name="reviewer-demo",
        capabilities=["code_review", "security_audit", "pr_commenting"],
        platforms=["github"],
        description="Demo code review agent",
    )
    print(f"Agent: {profile.name}")
    print(f"Capabilities: {', '.join(profile.capabilities)}")
    print()

    # Review provided file or use sample code
    if args.file:
        filepath = Path(args.file)
        if filepath.exists():
            code = filepath.read_text()
            filename = filepath.name
        else:
            print(f"File not found: {args.file}")
            return
    else:
        filename = "sample.py"
        code = '''import os
from module import *

API_KEY = "sk-1234567890abcdef"
DB_PASSWORD = "hunter2"

def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    try:
        result = eval(input_data)
    except:
        print("Something went wrong")
        return None

    if type(result) == dict:
        return result
    if result == None:
        return {}
    return result

def run_command(cmd):
    # TODO: add input validation
    subprocess.call(cmd, shell=True)
    return True
'''

    print(f"-- Reviewing: {filename} --")
    print()

    report = review_code(code, filename)

    # Display findings
    severity_icons = {"critical": "[CRIT]", "warning": "[WARN]", "info": "[INFO]"}

    for finding in report.findings:
        icon = severity_icons.get(finding.severity, "[????]")
        print(f"  {icon} Line {finding.line}: {finding.message}")
        print(f"         Fix: {finding.suggestion}")
        print()

    # Summary
    print("-" * 60)
    print(f"Quality Score: {report.quality_score}")
    print(f"Lines Reviewed: {report.lines_reviewed}")
    print(f"Findings: {len(report.findings)} "
          f"({sum(1 for f in report.findings if f.severity == 'critical')} critical, "
          f"{sum(1 for f in report.findings if f.severity == 'warning')} warnings, "
          f"{sum(1 for f in report.findings if f.severity == 'info')} info)")
    print(f"Verdict: {'PASS' if report.passed else 'FAIL'}")
    print()

    # Demo: Review a PR comment with QualityGate
    print("-- PR Comment Quality Check --")
    print()

    quality_gate = QualityGate()

    good_comment = (
        "This PR introduces a potential SQL injection vulnerability on line 42. "
        "The query uses f-string interpolation with user input. "
        "I would suggest using parameterized queries instead. "
        "I might be wrong about the exact attack vector, but the pattern is risky."
    )

    bad_comment = (
        "Great question! That's an excellent point. This looks wonderful. "
        "As an AI language model, I think this is fantastic work!"
    )

    print("  Good comment:")
    good_result = review_pr_comment(good_comment, quality_gate)
    print(f"    Quality: {good_result['quality_score']} | Ethics: {good_result['ethics_score']}")
    for s in good_result["strengths"]:
        print(f"    + {s}")
    print()

    print("  Bad comment (sycophantic):")
    bad_result = review_pr_comment(bad_comment, quality_gate)
    print(f"    Quality: {bad_result['quality_score']} | Ethics: {bad_result['ethics_score']}")
    for v in bad_result["violations"]:
        print(f"    - {v}")
    print()

    print("In production, this agent would:")
    print("  1. Run on every PR via GitHub Actions or webhook")
    print("  2. Post review comments with specific line-level feedback")
    print("  3. Block merging PRs with critical security findings")
    print("  4. Earn RTC for each review via the RustChain job economy")


if __name__ == "__main__":
    main()
