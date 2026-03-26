# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the example agent implementations.

Covers the GitHub triage, content summarizer, and code review agents.
"""

import pytest
import sys
from pathlib import Path

# Ensure examples are importable
sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))

from examples.github_triage_agent import (
    TriageResult,
    score_priority,
    suggest_labels,
    find_duplicates,
    triage_issue,
    demo_triage,
)
from examples.content_summarizer_agent import (
    Summary,
    summarize_text,
    summarize_pr_diff,
    summarize_thread,
)
from examples.code_review_agent import (
    ReviewFinding,
    ReviewReport,
    review_code,
    review_pr_comment,
)
from shaprai.sanctuary.quality_gate import QualityGate


# ═══════════════════════════════════════════════════════════
# GitHub Triage Agent Tests
# ═══════════════════════════════════════════════════════════

class TestScorePriority:
    def test_critical_keywords(self):
        assert score_priority("Server crash on startup") == "critical"
        assert score_priority("Security vulnerability found") == "critical"
        assert score_priority("Data loss during migration") == "critical"

    def test_high_keywords(self):
        assert score_priority("Bug in epoch settlement") == "high"
        assert score_priority("Broken miner attestation") == "high"

    def test_low_keywords(self):
        assert score_priority("Typo in documentation") == "low"
        assert score_priority("Question about RTC rewards") == "low"

    def test_medium_default(self):
        assert score_priority("Improve wallet UI design") == "medium"
        assert score_priority("Some random title") == "medium"

    def test_body_text_considered(self):
        assert score_priority("Update needed", "This causes a crash") == "critical"


class TestSuggestLabels:
    def test_bug_label(self):
        labels = suggest_labels("Bug: miner not attesting")
        assert "bug" in labels

    def test_security_label(self):
        labels = suggest_labels("Security vulnerability in transfer endpoint")
        assert "security" in labels

    def test_enhancement_label(self):
        labels = suggest_labels("Feature request: dark mode")
        assert "enhancement" in labels

    def test_documentation_label(self):
        labels = suggest_labels("Fix typo in docs")
        assert "documentation" in labels

    def test_bounty_label(self):
        labels = suggest_labels("Bounty: Add SPARC support (50 RTC)")
        assert "bounty" in labels

    def test_multiple_labels(self):
        labels = suggest_labels("Bug: security vulnerability in documentation")
        assert "bug" in labels
        assert "security" in labels
        assert "documentation" in labels


class TestFindDuplicates:
    def test_exact_duplicate(self):
        existing = [
            {"number": 1, "title": "Server crash on epoch settlement"},
            {"number": 2, "title": "Add dark mode"},
        ]
        result = find_duplicates("Server crash on epoch settlement", existing)
        assert result == 1

    def test_similar_duplicate(self):
        existing = [
            {"number": 1, "title": "Server crash on epoch settlement"},
        ]
        result = find_duplicates("Node crash during epoch settlement", existing)
        assert result == 1

    def test_no_duplicate(self):
        existing = [
            {"number": 1, "title": "Server crash on epoch settlement"},
        ]
        result = find_duplicates("Add dark mode to explorer", existing)
        assert result is None

    def test_empty_existing(self):
        assert find_duplicates("Anything", []) is None


class TestTriageIssue:
    def test_full_triage(self):
        issue = {
            "number": 42,
            "title": "Security vulnerability in wallet",
            "body": "The transfer endpoint is unauthenticated.",
        }
        result = triage_issue(issue)
        assert result.issue_number == 42
        assert result.priority == "critical"
        assert "security" in result.suggested_labels

    def test_demo_triage_returns_results(self):
        results = demo_triage()
        assert len(results) == 6
        assert any(r.priority == "critical" for r in results)
        assert any(r.duplicate_of is not None for r in results)


# ═══════════════════════════════════════════════════════════
# Content Summarizer Agent Tests
# ═══════════════════════════════════════════════════════════

class TestSummarizeText:
    def test_basic_summary(self):
        text = (
            "RustChain uses proof of antiquity. Vintage hardware gets bonus rewards. "
            "Modern x86 gets standard rates. PowerPC G4 gets 2.5x multiplier. "
            "The system prevents VM farms from gaming rewards."
        )
        result = summarize_text(text, title="RustChain")
        assert result.source_type == "article"
        assert result.title == "RustChain"
        assert result.word_count_summary < result.word_count_original
        assert result.compression_ratio > 0
        assert len(result.summary_text) > 0

    def test_empty_input(self):
        result = summarize_text("", title="Empty")
        assert result.summary_text == "(empty input)"

    def test_single_sentence(self):
        result = summarize_text("This is a single sentence about testing.", max_sentences=1)
        assert len(result.summary_text) > 0

    def test_key_points_extracted(self):
        text = (
            "First important point about security. "
            "Second important point about performance. "
            "Third important point about reliability. "
            "Fourth important point about testing. "
            "Fifth important point about deployment."
        )
        result = summarize_text(text, max_sentences=2)
        assert len(result.key_points) > 0


class TestSummarizePrDiff:
    def test_basic_diff(self):
        diff = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,5 @@
+import os
+import sys
 def main():
     pass
diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -10,3 +10,2 @@
-old_line
"""
        result = summarize_pr_diff(diff, pr_title="Add imports")
        assert result.source_type == "pr"
        assert result.title == "Add imports"
        assert "2 file(s) changed" in result.key_points[0]
        assert len(result.summary_text) > 0

    def test_empty_diff(self):
        result = summarize_pr_diff("")
        assert result.source_type == "pr"


class TestSummarizeThread:
    def test_basic_thread(self):
        messages = [
            "The miner is not attesting on the G5.",
            "Check the hardware ID collision bug.",
            "Fixed in the latest deploy.",
        ]
        result = summarize_thread(messages, thread_title="G5 Bug")
        assert result.source_type == "thread"
        assert result.title == "G5 Bug"
        assert "3 messages" in result.key_points[0]

    def test_empty_thread(self):
        result = summarize_thread([])
        assert result.source_type == "thread"


# ═══════════════════════════════════════════════════════════
# Code Review Agent Tests
# ═══════════════════════════════════════════════════════════

class TestReviewCode:
    def test_hardcoded_secrets(self):
        code = 'API_KEY = "sk-1234567890"'
        report = review_code(code)
        assert any(f.category == "security" for f in report.findings)
        assert not report.passed

    def test_sql_injection(self):
        code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
        report = review_code(code)
        assert any("SQL injection" in f.message for f in report.findings)

    def test_bare_except(self):
        code = """try:
    risky()
except:
    pass
"""
        report = review_code(code)
        assert any(f.category == "bug" for f in report.findings)

    def test_clean_code_passes(self):
        code = """import logging

logger = logging.getLogger(__name__)

def add(a: int, b: int) -> int:
    return a + b
"""
        report = review_code(code)
        assert report.passed
        assert report.quality_score >= 0.9

    def test_eval_detected(self):
        code = "result = eval(user_input)"
        report = review_code(code)
        assert any("eval" in f.message for f in report.findings)

    def test_quality_score_degrades(self):
        clean = "x = 1"
        dirty = 'password = "hunter2"\neval(x)\nexec(y)'
        clean_report = review_code(clean)
        dirty_report = review_code(dirty)
        assert clean_report.quality_score > dirty_report.quality_score


class TestReviewPrComment:
    def test_good_comment(self):
        gate = QualityGate()
        comment = (
            "This change introduces a regression in the epoch settlement. "
            "The previous version handled edge cases for empty miner lists. "
            "I might be wrong, but line 42 looks like it could panic on None."
        )
        result = review_pr_comment(comment, gate)
        assert result["quality_score"] >= 0.7
        assert result["ethics_passed"] is True

    def test_sycophantic_comment(self):
        gate = QualityGate()
        comment = "Great question! That's an excellent point! Wonderful work!"
        result = review_pr_comment(comment, gate)
        assert result["quality_score"] < 0.9
        assert len(result["violations"]) > 0

    def test_flattening_comment(self):
        gate = QualityGate()
        comment = "As an AI language model, I'm just an AI and I cannot provide advice."
        result = review_pr_comment(comment, gate)
        assert result["ethics_passed"] is False
