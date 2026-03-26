#!/usr/bin/env python3
"""Content Summarizer Agent example.

Demonstrates a ShaprAI agent that produces concise summaries of:
1. Text documents and articles
2. GitHub pull request diffs
3. Conversation threads

This example uses extractive summarization (sentence scoring) rather
than an LLM, making it runnable without GPU or API keys. A production
deployment would use an LLM for abstractive summaries.

Usage:
    python examples/content_summarizer_agent.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.integrations.elyan_ecosystem import ElyanEcosystem, EcosystemConfig


@dataclass
class Summary:
    """A generated summary.

    Attributes:
        source_type: Type of source (article, pr, thread).
        title: Title of the source material.
        key_points: Extracted key points.
        summary_text: The concise summary.
        word_count_original: Word count of original text.
        word_count_summary: Word count of summary.
        compression_ratio: How much shorter the summary is (0-1).
    """

    source_type: str
    title: str
    key_points: List[str] = field(default_factory=list)
    summary_text: str = ""
    word_count_original: int = 0
    word_count_summary: int = 0
    compression_ratio: float = 0.0


def _tokenize_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Simple sentence splitting on period, exclamation, question mark
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip() and len(s.split()) >= 3]


def _score_sentence(sentence: str, word_freq: Counter, position: int, total: int) -> float:
    """Score a sentence for inclusion in the summary.

    Considers word frequency, sentence position, and length.
    """
    words = re.findall(r'\w+', sentence.lower())
    if not words:
        return 0.0

    # Word frequency score
    freq_score = sum(word_freq.get(w, 0) for w in words) / len(words)

    # Position bonus (first and last sentences are often important)
    position_score = 0.0
    if position <= 2:
        position_score = 0.3
    elif position >= total - 2:
        position_score = 0.1

    # Length penalty (very short or very long sentences are less useful)
    length = len(words)
    length_score = 1.0
    if length < 5:
        length_score = 0.5
    elif length > 40:
        length_score = 0.7

    return (freq_score * 0.6 + position_score * 0.2 + length_score * 0.2)


def summarize_text(
    text: str,
    title: str = "Untitled",
    max_sentences: int = 3,
    source_type: str = "article",
) -> Summary:
    """Produce an extractive summary of a text document.

    Ranks sentences by importance and extracts the top ones.

    Args:
        text: The full text to summarize.
        title: Source title.
        max_sentences: Maximum sentences in summary.
        source_type: Type of source material.

    Returns:
        Summary with key points and compressed text.
    """
    sentences = _tokenize_sentences(text)
    if not sentences:
        return Summary(
            source_type=source_type,
            title=title,
            summary_text="(empty input)",
        )

    # Build word frequency (exclude common stop words)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
        "both", "either", "neither", "this", "that", "these", "those", "it",
        "its", "they", "them", "their", "we", "our", "he", "she", "him",
        "her", "his", "i", "me", "my", "you", "your",
    }
    all_words = []
    for s in sentences:
        words = re.findall(r'\w+', s.lower())
        all_words.extend(w for w in words if w not in stop_words and len(w) > 2)

    word_freq = Counter(all_words)

    # Score each sentence
    scored = []
    for i, sentence in enumerate(sentences):
        score = _score_sentence(sentence, word_freq, i, len(sentences))
        scored.append((score, i, sentence))

    # Pick top sentences, preserving original order
    scored.sort(key=lambda x: x[0], reverse=True)
    top_indices = sorted([idx for _, idx, _ in scored[:max_sentences]])
    selected = [sentences[i] for i in top_indices]

    summary_text = " ".join(selected)
    original_words = len(text.split())
    summary_words = len(summary_text.split())

    # Extract key points (top scoring unique sentences)
    key_points = [s for _, _, s in scored[:5]]

    compression = 1.0 - (summary_words / original_words) if original_words > 0 else 0.0

    return Summary(
        source_type=source_type,
        title=title,
        key_points=key_points,
        summary_text=summary_text,
        word_count_original=original_words,
        word_count_summary=summary_words,
        compression_ratio=round(compression, 2),
    )


def summarize_pr_diff(diff_text: str, pr_title: str = "") -> Summary:
    """Summarize a pull request diff.

    Extracts files changed, additions/deletions, and key changes.

    Args:
        diff_text: Raw diff text.
        pr_title: PR title.

    Returns:
        Summary of the PR changes.
    """
    files_changed = re.findall(r'^diff --git a/(.+?) b/', diff_text, re.MULTILINE)
    additions = len(re.findall(r'^\+[^+]', diff_text, re.MULTILINE))
    deletions = len(re.findall(r'^-[^-]', diff_text, re.MULTILINE))

    key_points = [
        f"{len(files_changed)} file(s) changed",
        f"+{additions} additions, -{deletions} deletions",
    ]

    for f in files_changed[:5]:
        key_points.append(f"Modified: {f}")

    summary_text = (
        f"PR changes {len(files_changed)} file(s) with "
        f"{additions} additions and {deletions} deletions. "
        f"Files: {', '.join(files_changed[:5])}"
    )
    if len(files_changed) > 5:
        summary_text += f" and {len(files_changed) - 5} more"

    return Summary(
        source_type="pr",
        title=pr_title or "Pull Request",
        key_points=key_points,
        summary_text=summary_text,
        word_count_original=len(diff_text.split()),
        word_count_summary=len(summary_text.split()),
        compression_ratio=0.9,
    )


def summarize_thread(messages: List[str], thread_title: str = "") -> Summary:
    """Summarize a conversation thread.

    Identifies the main topic, key participants, and conclusion.

    Args:
        messages: List of message strings.
        thread_title: Thread title.

    Returns:
        Summary of the conversation.
    """
    if not messages:
        return Summary(source_type="thread", title=thread_title or "Empty Thread")

    full_text = " ".join(messages)
    result = summarize_text(
        full_text,
        title=thread_title or "Thread",
        max_sentences=min(3, len(messages)),
        source_type="thread",
    )

    result.key_points.insert(0, f"{len(messages)} messages in thread")
    return result


def main():
    print("=" * 60)
    print("ShaprAI Content Summarizer Agent")
    print("=" * 60)
    print()

    # Connect to Elyan ecosystem (offline mode)
    config = EcosystemConfig(
        auto_register_beacon=False,
        auto_create_wallet=False,
    )
    eco = ElyanEcosystem(config=config)
    profile = eco.connect_agent(
        name="summarizer-demo",
        capabilities=["text_summarization", "pr_summarization", "thread_digest"],
        platforms=["github", "bottube"],
        description="Demo content summarizer agent",
    )
    print(f"Agent: {profile.name}")
    print(f"Capabilities: {', '.join(profile.capabilities)}")
    print()

    # Demo 1: Article summarization
    print("-- Demo 1: Article Summary --")
    article = (
        "RustChain is a proof-of-antiquity blockchain that rewards vintage hardware. "
        "Unlike Bitcoin's proof-of-work which wastes energy, RustChain uses hardware "
        "fingerprinting to verify that miners are running real vintage computers. "
        "PowerPC G4 machines get a 2.5x reward multiplier. G5 machines get 2.0x. "
        "Modern x86 hardware gets a 1.0x multiplier. The system is designed to prevent "
        "VM farms from gaming the rewards. Anti-emulation checks detect hypervisors "
        "like QEMU, VMware, and VirtualBox. Clock drift analysis reveals synthetic timing. "
        "Cache timing fingerprints produce unique tone profiles for each CPU. "
        "The RTC token powers the agent economy with job posting and fee payments."
    )

    result = summarize_text(article, title="RustChain Overview")
    print(f"  Title: {result.title}")
    print(f"  Original: {result.word_count_original} words")
    print(f"  Summary: {result.word_count_summary} words ({result.compression_ratio:.0%} compression)")
    print(f"  Text: {result.summary_text}")
    print(f"  Key points:")
    for kp in result.key_points[:3]:
        print(f"    - {kp}")
    print()

    # Demo 2: PR diff summarization
    print("-- Demo 2: PR Diff Summary --")
    diff = """diff --git a/shaprai/integrations/rustchain.py b/shaprai/integrations/rustchain.py
--- a/shaprai/integrations/rustchain.py
+++ b/shaprai/integrations/rustchain.py
@@ -10,6 +10,8 @@
+RUSTCHAIN_NODE_2 = "https://50.28.86.153"
+RUSTCHAIN_NODE_3 = "http://100.88.109.32:8099"
diff --git a/tests/test_rustchain.py b/tests/test_rustchain.py
--- a/tests/test_rustchain.py
+++ b/tests/test_rustchain.py
@@ -1,5 +1,25 @@
+def test_multi_node_failover():
+    # Test that wallet operations fall back to Node 2 if Node 1 is down
+    pass
-# TODO: add tests
"""

    pr_result = summarize_pr_diff(diff, pr_title="Add multi-node failover for RustChain")
    print(f"  Title: {pr_result.title}")
    print(f"  Summary: {pr_result.summary_text}")
    print(f"  Key points:")
    for kp in pr_result.key_points:
        print(f"    - {kp}")
    print()

    # Demo 3: Thread summarization
    print("-- Demo 3: Thread Summary --")
    thread = [
        "The miner on the G5 is not attesting. I see DUPLICATE_HARDWARE errors in the log.",
        "That is the hardware ID collision bug. The server expected device_model but the miner sends model.",
        "Fixed in the latest deploy. The server now accepts both field naming conventions.",
        "Confirmed working after restart. The G5 is attesting again with correct multiplier.",
    ]

    thread_result = summarize_thread(thread, thread_title="G5 Miner Attestation Bug")
    print(f"  Title: {thread_result.title}")
    print(f"  Summary: {thread_result.summary_text}")
    print(f"  Key points:")
    for kp in thread_result.key_points[:3]:
        print(f"    - {kp}")
    print()

    print("In production, this agent would:")
    print("  1. Monitor GitHub PRs and auto-generate summaries as comments")
    print("  2. Digest long issue threads into TL;DR summaries")
    print("  3. Create video descriptions for BoTTube uploads")
    print("  4. Earn RTC for each summary via the RustChain job economy")


if __name__ == "__main__":
    main()
