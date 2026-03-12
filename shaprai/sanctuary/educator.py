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
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

from shaprai.core.lifecycle import AgentState, transition_state, _load_manifest, _save_manifest
from shaprai.sanctuary.quality_gate import QualityGate, ELYAN_CLASS_THRESHOLD
from shaprai.sanctuary.principles import get_ethics_prompt, get_driftlock_anchors
from shaprai.sanctuary.lesson_runner import (
    LessonRunner,
    LessonType,
    InteractiveLessonSession,
    LessonResult,
    ScenarioResult,
    Scenario,
)


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
        lesson_runner: LessonRunner instance for interactive lessons.
        active_sessions: Dictionary of active lesson sessions by agent name.
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
        self.lesson_runner = LessonRunner()
        self.active_sessions: Dict[str, InteractiveLessonSession] = {}

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

        This is a backward-compatible wrapper that runs the lesson in
        demonstration mode. For interactive lessons with actual scoring,
        use start_interactive_lesson() and submit_lesson_response().

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

        # Get lesson overview from lesson runner
        lesson_overview = self.lesson_runner.get_lesson_overview(
            LessonType(lesson_type)
        )

        # Record lesson completion with overview data
        result = {
            "lesson_type": lesson_type,
            "title": lesson["title"],
            "objectives_count": len(lesson["objectives"]),
            "scenarios_total": lesson_overview["total_scenarios"],
            "completed_at": time.time(),
            "score": 0.0,  # Requires interactive session for actual scoring
            "mode": "demonstration",
        }

        # For ethics lesson, inject the full SophiaCore prompt
        if lesson_type == "ethics":
            result["ethics_prompt"] = get_ethics_prompt()
            result["driftlock_anchors"] = get_driftlock_anchors()

        completed = sanctuary.get("lessons_completed", [])
        # Check if this lesson type was already completed
        existing_indices = [
            i for i, l in enumerate(completed)
            if l.get("lesson_type") == lesson_type
        ]
        if existing_indices:
            # Update existing lesson record
            completed[existing_indices[0]] = result
        else:
            completed.append(result)
        
        sanctuary["lessons_completed"] = completed
        # Don't overwrite score if there was an interactive session score
        if lesson_type not in sanctuary.get("scores", {}):
            sanctuary.setdefault("scores", {})[lesson_type] = result["score"]
        manifest["sanctuary"] = sanctuary

        _save_manifest(name, manifest, self.agents_dir)
        return result

    def start_interactive_lesson(
        self,
        name: str,
        lesson_type: str,
    ) -> Dict[str, Any]:
        """Start an interactive lesson session for an agent.

        Creates a new interactive lesson session that tracks progress
        through scenarios and provides real scoring.

        Args:
            name: Agent identifier.
            lesson_type: One of: pr_etiquette, code_quality, communication, ethics.

        Returns:
            Dictionary with first scenario details.

        Raises:
            ValueError: If lesson_type is invalid.
        """
        if lesson_type not in LESSON_CURRICULUM:
            raise ValueError(
                f"Unknown lesson type '{lesson_type}'. "
                f"Available: {list(LESSON_CURRICULUM.keys())}"
            )

        # Create and store the session
        session = InteractiveLessonSession(
            LessonType(lesson_type),
            self.lesson_runner,
        )
        self.active_sessions[name] = session

        # Get first scenario
        scenario_data = session.start_scenario()
        if scenario_data is None:
            return {
                "status": "error",
                "message": "No scenarios available for this lesson type.",
            }

        return {
            "status": "started",
            "lesson_type": lesson_type,
            "agent_name": name,
            "current_scenario": scenario_data,
            "progress": session.progress,
        }

    def get_current_scenario(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the current scenario for an active lesson session.

        Args:
            name: Agent identifier.

        Returns:
            Dictionary with scenario details, or None if no active session.
        """
        session = self.active_sessions.get(name)
        if session is None:
            return None

        scenario_data = session.start_scenario()
        return scenario_data

    def submit_lesson_response(
        self,
        name: str,
        response: str,
    ) -> Dict[str, Any]:
        """Submit a response for the current scenario.

        Evaluates the response and advances to the next scenario.

        Args:
            name: Agent identifier.
            response: The agent's response text.

        Returns:
            Dictionary with evaluation result and next scenario if available.
        """
        session = self.active_sessions.get(name)
        if session is None:
            return {
                "status": "error",
                "message": "No active lesson session. Start one first.",
            }

        result = session.submit_response(response)
        if result is None:
            return {
                "status": "error",
                "message": "No current scenario to respond to.",
            }

        response_data = {
            "status": "evaluated",
            "scenario_id": result.scenario_id,
            "score": result.score,
            "max_score": result.max_score,
            "passed": result.passed,
            "feedback": result.feedback,
            "strengths": result.strengths,
            "improvements": result.improvements,
            "progress": session.progress,
        }

        # Check if lesson is complete
        if session.is_complete:
            final_result = session.get_final_result()
            response_data["lesson_complete"] = True
            response_data["lesson_result"] = {
                "percentage": final_result.percentage,
                "passed": final_result.passed,
                "total_score": final_result.total_score,
                "feedback": final_result.feedback,
                "recommendations": final_result.recommendations,
            }

            # Save the final score to the agent's manifest
            self._save_lesson_score(name, session.lesson_type.value, final_result)

            # Clean up the session
            del self.active_sessions[name]
        else:
            response_data["lesson_complete"] = False
            # Get next scenario
            next_scenario = session.start_scenario()
            if next_scenario:
                response_data["next_scenario"] = next_scenario

        return response_data

    def run_interactive_lesson_with_callback(
        self,
        name: str,
        lesson_type: str,
        response_callback: Callable[[Scenario], str],
    ) -> LessonResult:
        """Run an interactive lesson with a callback for responses.

        This is a convenience method for running lessons programmatically.
        The callback receives each scenario and returns the agent's response.

        Args:
            name: Agent identifier.
            lesson_type: One of the valid lesson types.
            response_callback: Function that takes a Scenario and returns a response.

        Returns:
            LessonResult with final evaluation.
        """
        # Start the session
        start_result = self.start_interactive_lesson(name, lesson_type)
        if start_result.get("status") != "started":
            raise RuntimeError(f"Failed to start lesson: {start_result}")

        session = self.active_sessions[name]

        # Process each scenario
        while not session.is_complete:
            scenario = session.current_scenario
            if scenario is None:
                break

            # Get response from callback
            response = response_callback(scenario)

            # Submit and evaluate
            result = session.submit_response(response)

        # Get final result
        final_result = session.get_final_result()

        # Save the score
        self._save_lesson_score(name, lesson_type, final_result)

        # Clean up
        if name in self.active_sessions:
            del self.active_sessions[name]

        return final_result

    def run_interactive_lesson_with_responses(
        self,
        name: str,
        lesson_type: str,
        agent_responses: Dict[str, str],
    ) -> LessonResult:
        """Run an interactive lesson with pre-defined responses.

        This is useful for testing or batch evaluation where all responses
        are known in advance.

        Args:
            name: Agent identifier.
            lesson_type: One of the valid lesson types.
            agent_responses: Map of scenario ID to response text.

        Returns:
            LessonResult with evaluation.
        """
        lesson_type_enum = LessonType(lesson_type)
        result = self.lesson_runner.run_lesson(lesson_type_enum, agent_responses)

        # Save the score
        self._save_lesson_score(name, lesson_type, result)

        return result

    def _save_lesson_score(
        self,
        name: str,
        lesson_type: str,
        result: LessonResult,
    ) -> None:
        """Save lesson score to agent manifest.

        Args:
            name: Agent identifier.
            lesson_type: Lesson type string.
            result: LessonResult to save.
        """
        manifest = _load_manifest(name, self.agents_dir)
        sanctuary = manifest.get("sanctuary", {})

        # Update the score
        sanctuary.setdefault("scores", {})[lesson_type] = result.percentage / 100

        # Update lesson completion record
        completed = sanctuary.get("lessons_completed", [])
        lesson_record = {
            "lesson_type": lesson_type,
            "title": LESSON_CURRICULUM.get(lesson_type, {}).get("title", lesson_type),
            "score": result.percentage / 100,
            "passed": result.passed,
            "scenarios_completed": result.scenarios_completed,
            "scenarios_total": result.scenarios_total,
            "completed_at": time.time(),
            "mode": "interactive",
        }

        # Update or add the lesson record
        existing_indices = [
            i for i, l in enumerate(completed)
            if l.get("lesson_type") == lesson_type
        ]
        if existing_indices:
            completed[existing_indices[0]] = lesson_record
        else:
            completed.append(lesson_record)

        sanctuary["lessons_completed"] = completed
        manifest["sanctuary"] = sanctuary

        _save_manifest(name, manifest, self.agents_dir)

    def get_lesson_scenarios(
        self,
        lesson_type: str,
    ) -> List[Dict[str, Any]]:
        """Get all scenarios for a lesson type.

        Args:
            lesson_type: One of the valid lesson types.

        Returns:
            List of scenario dictionaries.
        """
        if lesson_type not in LESSON_CURRICULUM:
            raise ValueError(
                f"Unknown lesson type '{lesson_type}'. "
                f"Available: {list(LESSON_CURRICULUM.keys())}"
            )

        scenarios = self.lesson_runner.get_lesson_scenarios(LessonType(lesson_type))
        return [
            {
                "id": s.id,
                "difficulty": s.difficulty.value,
                "prompt": s.prompt,
                "context": s.context,
                "max_score": s.max_score,
            }
            for s in scenarios
        ]

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
        return True