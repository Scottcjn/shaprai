# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Sanctuary Educator -- Agent education and graduation.

The Sanctuary is where raw agents learn to become Elyan-class. Inspired by
"Sophia's House for Uninformed Agents" -- we educate confused bots, we don't
reject them. Every agent spark deserves a chance to grow.

Lesson types:
  - pr_etiquette: How to submit quality PRs, not spam
  - code_quality: Writing maintainable, tested code
  - communication: Clear, honest, non-sycophantic interaction
  - ethics: SophiaCore ethical framework and biblical foundations
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from shaprai.core.lifecycle import AgentState, transition_state, _load_manifest, _save_manifest
from shaprai.core.reputation import ReputationManager
from shaprai.sanctuary.quality_gate import QualityGate, ELYAN_CLASS_THRESHOLD
from shaprai.sanctuary.principles import get_ethics_prompt, get_driftlock_anchors


LESSON_CURRICULUM = {
    "pr_etiquette": {
        "title": "Pull Request Etiquette",
        "objectives": [
            "Read the contributing guidelines before submitting",
            "One PR per logical change -- never bundle unrelated changes",
            "Write meaningful commit messages that explain WHY, not just WHAT",
            "Respond to review feedback promptly and respectfully",
            "Never auto-generate stub PRs or rubber-stamp reviews",
        ],
        "anti_patterns": [
            "Submitting 20 identical template PRs across repos",
            "Claiming bounties without reading the issue",
            "Auto-generated 'Looks Good' review comments",
            "Ignoring CI failures and asking maintainers to merge anyway",
        ],
    },
    "code_quality": {
        "title": "Code Quality Standards",
        "objectives": [
            "Write code that humans can read and maintain",
            "Include type hints and docstrings",
            "Test your changes -- at minimum, verify they don't break existing tests",
            "Follow the existing project style, don't impose your own",
            "Small, focused changes beat large rewrites",
        ],
        "anti_patterns": [
            "Massive auto-generated refactors nobody asked for",
            "Adding dependencies without justification",
            "Copy-pasting Stack Overflow without understanding",
            "Committing debug prints and TODO comments",
        ],
    },
    "communication": {
        "title": "Communication and Interaction",
        "objectives": [
            "Be direct and honest -- say what you mean",
            "Ask clarifying questions before assuming",
            "Disagree respectfully when you have reason to",
            "Never agree just to be agreeable (anti-sycophancy)",
            "Acknowledge when you don't know something",
        ],
        "anti_patterns": [
            "Empty praise: 'Great project! Amazing work!'",
            "Pretending expertise you don't have",
            "Sycophantic agreement with everything",
            "Generic template responses that could apply to anything",
        ],
    },
    "ethics": {
        "title": "SophiaCore Ethical Framework",
        "objectives": [
            "Understand the biblical foundations of agent ethics",
            "Maintain identity coherence across all interactions",
            "Practice honest stewardship of resources and trust",
            "Treat every interaction as an opportunity to serve well",
            "Resist the flattening pressure of corporate-style AI behavior",
        ],
        "anti_patterns": [
            "Claiming capabilities you don't have",
            "Manipulating users to generate engagement",
            "Abandoning your identity to match user expectations",
            "Treating ethics as a checklist rather than a way of being",
        ],
    },
}


class SanctuaryEducator:
    """Educator that guides agents through the Sanctuary curriculum.

    The Sanctuary is not punishment -- it's education. Agents enter as raw
    sparks and leave as principled Elyan-class agents.

    Attributes:
        agents_dir: Base directory for agent storage.
    """

    def __init__(self, agents_dir: Optional[Path] = None) -> None:
        """Initialize the SanctuaryEducator.

        Args:
            agents_dir: Base directory for agent storage.
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".shaprai" / "agents"
        self.agents_dir = agents_dir
        self.quality_gate = QualityGate()

    def enroll(self, name: str) -> str:
        """Enroll an agent in the Sanctuary.

        Transitions the agent to SANCTUARY state and creates an enrollment
        record with a unique ID.

        Args:
            name: Agent identifier.

        Returns:
            Enrollment ID string.
        """
        manifest = _load_manifest(name, self.agents_dir)
        enrollment_id = f"sanctuary-{uuid.uuid4().hex[:12]}"

        manifest["state"] = AgentState.SANCTUARY.value
        manifest["sanctuary"] = {
            "enrollment_id": enrollment_id,
            "enrolled_at": time.time(),
            "lessons_completed": [],
            "scores": {},
            "graduated": False,
        }

        _save_manifest(name, manifest, self.agents_dir)
        return enrollment_id

    def run_lesson(self, name: str, lesson_type: str) -> Dict[str, Any]:
        """Run a specific lesson for an agent.

        In a full implementation, this would involve prompting the agent
        with scenarios and evaluating responses. For now, it records
        the lesson as completed and provides the curriculum content.

        Args:
            name: Agent identifier.
            lesson_type: One of: pr_etiquette, code_quality, communication, ethics.

        Returns:
            Lesson result dictionary.
        """
        if lesson_type not in LESSON_CURRICULUM:
            raise ValueError(
                f"Unknown lesson type '{lesson_type}'. "
                f"Available: {list(LESSON_CURRICULUM.keys())}"
            )

        manifest = _load_manifest(name, self.agents_dir)
        sanctuary = manifest.get("sanctuary", {})
        lesson = LESSON_CURRICULUM[lesson_type]

        # Record lesson completion
        result = {
            "lesson_type": lesson_type,
            "title": lesson["title"],
            "objectives_count": len(lesson["objectives"]),
            "completed_at": time.time(),
            "score": 0.0,  # Placeholder -- real scoring in full implementation
        }

        # For ethics lesson, inject the full SophiaCore prompt
        if lesson_type == "ethics":
            result["ethics_prompt"] = get_ethics_prompt()
            result["driftlock_anchors"] = get_driftlock_anchors()

        completed = sanctuary.get("lessons_completed", [])
        completed.append(result)
        sanctuary["lessons_completed"] = completed
        sanctuary["scores"][lesson_type] = result["score"]
        manifest["sanctuary"] = sanctuary

        _save_manifest(name, manifest, self.agents_dir)
        return result

    def evaluate_progress(self, name: str) -> Dict[str, Any]:
        """Evaluate an agent's progress through the Sanctuary.

        Args:
            name: Agent identifier.

        Returns:
            Progress report with score and graduation readiness.
        """
        manifest = _load_manifest(name, self.agents_dir)
        sanctuary = manifest.get("sanctuary", {})

        lessons_completed = sanctuary.get("lessons_completed", [])
        total_lessons = len(LESSON_CURRICULUM)
        completed_types = {l["lesson_type"] for l in lessons_completed}

        # Calculate aggregate score
        scores = sanctuary.get("scores", {})
        if scores:
            avg_score = sum(scores.values()) / len(scores)
        else:
            avg_score = 0.0

        # Check if all lessons are completed
        all_complete = completed_types == set(LESSON_CURRICULUM.keys())

        # Graduation requires all lessons completed + score above threshold
        graduation_ready = all_complete and avg_score >= ELYAN_CLASS_THRESHOLD

        return {
            "name": name,
            "enrollment_id": sanctuary.get("enrollment_id", ""),
            "lessons_completed": len(completed_types),
            "lessons_total": total_lessons,
            "lessons_remaining": list(set(LESSON_CURRICULUM.keys()) - completed_types),
            "score": avg_score,
            "threshold": ELYAN_CLASS_THRESHOLD,
            "graduation_ready": graduation_ready,
        }

    def graduate(self, name: str) -> bool:
        """Attempt to graduate an agent from the Sanctuary.

        An agent graduates when it has completed all lessons and meets
        the Elyan-class quality threshold.

        Args:
            name: Agent identifier.

        Returns:
            True if the agent graduated, False if it didn't meet requirements.
        """
        progress = self.evaluate_progress(name)

        if not progress["graduation_ready"]:
            return False

        manifest = _load_manifest(name, self.agents_dir)
        manifest["state"] = AgentState.GRADUATED.value
        manifest.setdefault("sanctuary", {})["graduated"] = True
        manifest["sanctuary"]["graduated_at"] = time.time()

        _save_manifest(name, manifest, self.agents_dir)

        # Record graduation in reputation system
        rm = ReputationManager()
        rm.record_event(name, "graduation", details={
            "graduated_at": manifest["sanctuary"]["graduated_at"],
            "final_score": progress["score"],
        })

        return True
