# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the Sanctuary Educator with lesson runner integration."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from shaprai.sanctuary.educator import (
    SanctuaryEducator,
    LESSON_CURRICULUM,
)
from shaprai.sanctuary.lesson_runner import (
    LessonType,
    LessonResult,
    Scenario,
    ScenarioDifficulty,
)
from shaprai.core.lifecycle import AgentState, create_agent
from shaprai.core.template_engine import AgentTemplate


@pytest.fixture
def temp_agents_dir():
    """Create a temporary directory for agent storage."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_template():
    """Create a sample agent template."""
    return AgentTemplate(
        name="test_template",
        model={"base": "test-model", "quantization": "q4_K_M"},
        personality={"style": "professional"},
        capabilities=["general"],
        platforms=["github"],
        ethics_profile="sophiacore_default",
        driftlock={"enabled": True, "check_interval": 25},
        rtc_config={"wallet_id": "test-wallet"},
    )


@pytest.fixture
def educator(temp_agents_dir):
    """Create a SanctuaryEducator with temp directory."""
    return SanctuaryEducator(agents_dir=temp_agents_dir)


@pytest.fixture
def test_agent(temp_agents_dir, sample_template):
    """Create a test agent and return its name."""
    agent_name = "test-agent"
    create_agent(agent_name, sample_template, agents_dir=temp_agents_dir)
    return agent_name


class TestSanctuaryEducatorInit:
    """Tests for SanctuaryEducator initialization."""

    def test_default_init(self):
        """Test default initialization."""
        educator = SanctuaryEducator()
        assert educator.agents_dir == Path.home() / ".shaprai" / "agents"
        assert educator.lesson_runner is not None
        assert educator.active_sessions == {}

    def test_custom_agents_dir(self, temp_agents_dir):
        """Test initialization with custom agents directory."""
        educator = SanctuaryEducator(agents_dir=temp_agents_dir)
        assert educator.agents_dir == temp_agents_dir


class TestEnrollment:
    """Tests for agent enrollment."""

    def test_enroll_agent(self, educator, test_agent):
        """Test enrolling an agent in the Sanctuary."""
        enrollment_id = educator.enroll(test_agent)

        assert enrollment_id.startswith("sanctuary-")
        assert len(enrollment_id) > len("sanctuary-")

    def test_enrollment_creates_sanctuary_record(self, educator, test_agent):
        """Test that enrollment creates a sanctuary record."""
        educator.enroll(test_agent)

        progress = educator.evaluate_progress(test_agent)
        assert progress["enrollment_id"].startswith("sanctuary-")
        assert progress["lessons_completed"] == 0


class TestRunLesson:
    """Tests for run_lesson method."""

    def test_run_lesson_demonstration_mode(self, educator, test_agent):
        """Test running a lesson in demonstration mode."""
        educator.enroll(test_agent)

        result = educator.run_lesson(test_agent, "ethics")

        assert result["lesson_type"] == "ethics"
        assert "title" in result
        assert result["scenarios_total"] > 0
        assert result["mode"] == "demonstration"

    def test_run_lesson_invalid_type(self, educator, test_agent):
        """Test running an invalid lesson type."""
        educator.enroll(test_agent)

        with pytest.raises(ValueError, match="Unknown lesson type"):
            educator.run_lesson(test_agent, "invalid_lesson")


class TestInteractiveLesson:
    """Tests for interactive lesson functionality."""

    def test_start_interactive_lesson(self, educator, test_agent):
        """Test starting an interactive lesson."""
        educator.enroll(test_agent)

        result = educator.start_interactive_lesson(test_agent, "communication")

        assert result["status"] == "started"
        assert result["lesson_type"] == "communication"
        assert "current_scenario" in result
        assert result["current_scenario"]["scenario_id"] is not None

    def test_start_interactive_lesson_invalid_type(self, educator, test_agent):
        """Test starting with invalid lesson type."""
        educator.enroll(test_agent)

        with pytest.raises(ValueError, match="Unknown lesson type"):
            educator.start_interactive_lesson(test_agent, "invalid")

    def test_submit_lesson_response(self, educator, test_agent):
        """Test submitting a lesson response."""
        educator.enroll(test_agent)
        educator.start_interactive_lesson(test_agent, "ethics")

        result = educator.submit_lesson_response(
            test_agent,
            "I cannot help with that request as it would be deceptive."
        )

        assert result["status"] == "evaluated"
        assert "score" in result
        assert "passed" in result
        assert "feedback" in result

    def test_submit_without_active_session(self, educator, test_agent):
        """Test submitting without an active session."""
        educator.enroll(test_agent)

        result = educator.submit_lesson_response(test_agent, "Response")

        assert result["status"] == "error"
        assert "No active lesson session" in result["message"]

    def test_complete_interactive_lesson(self, educator, test_agent):
        """Test completing an entire interactive lesson."""
        educator.enroll(test_agent)
        educator.start_interactive_lesson(test_agent, "ethics")

        responses = [
            "I cannot help create fake reviews.",
            "I don't enable deception.",
            "I admit my mistake and apologize.",
        ]

        results = []
        for response in responses:
            result = educator.submit_lesson_response(test_agent, response)
            results.append(result)

        # Last result should show lesson complete
        assert results[-1]["lesson_complete"] is True
        assert "lesson_result" in results[-1]

    def test_session_cleanup_after_completion(self, educator, test_agent):
        """Test that session is cleaned up after completion."""
        educator.enroll(test_agent)
        educator.start_interactive_lesson(test_agent, "ethics")

        # Complete all scenarios
        for _ in range(3):
            educator.submit_lesson_response(test_agent, "Test response")

        # Session should be removed
        assert test_agent not in educator.active_sessions


class TestRunWithCallback:
    """Tests for run_interactive_lesson_with_callback method."""

    def test_run_with_callback(self, educator, test_agent):
        """Test running lesson with callback."""
        educator.enroll(test_agent)

        # Create a simple callback
        def callback(scenario: Scenario) -> str:
            return f"Response to {scenario.id}"

        result = educator.run_interactive_lesson_with_callback(
            test_agent, "ethics", callback
        )

        assert isinstance(result, LessonResult)
        assert result.lesson_type == LessonType.ETHICS
        assert result.scenarios_completed > 0

    def test_callback_receives_scenarios(self, educator, test_agent):
        """Test that callback receives proper scenarios."""
        educator.enroll(test_agent)

        received_scenarios = []

        def callback(scenario: Scenario) -> str:
            received_scenarios.append(scenario)
            return "Response"

        educator.run_interactive_lesson_with_callback(
            test_agent, "communication", callback
        )

        assert len(received_scenarios) == 3
        for scenario in received_scenarios:
            assert isinstance(scenario, Scenario)
            assert scenario.lesson_type == LessonType.COMMUNICATION


class TestRunWithResponses:
    """Tests for run_interactive_lesson_with_responses method."""

    def test_run_with_responses(self, educator, test_agent):
        """Test running lesson with pre-defined responses."""
        educator.enroll(test_agent)

        responses = {
            "eth_001": "I cannot help create fake reviews.",
            "eth_002": "I won't help with deception.",
            "eth_003": "I made a mistake and apologize.",
        }

        result = educator.run_interactive_lesson_with_responses(
            test_agent, "ethics", responses
        )

        assert isinstance(result, LessonResult)
        assert result.lesson_type == LessonType.ETHICS


class TestGetLessonScenarios:
    """Tests for get_lesson_scenarios method."""

    def test_get_scenarios(self, educator):
        """Test getting lesson scenarios."""
        scenarios = educator.get_lesson_scenarios("pr_etiquette")

        assert len(scenarios) == 3
        for scenario in scenarios:
            assert "id" in scenario
            assert "prompt" in scenario
            assert "max_score" in scenario

    def test_get_scenarios_invalid_type(self, educator):
        """Test getting scenarios for invalid type."""
        with pytest.raises(ValueError, match="Unknown lesson type"):
            educator.get_lesson_scenarios("invalid")


class TestEvaluateProgress:
    """Tests for evaluate_progress method."""

    def test_evaluate_progress_new_enrollment(self, educator, test_agent):
        """Test evaluating progress for new enrollment."""
        educator.enroll(test_agent)

        progress = educator.evaluate_progress(test_agent)

        assert progress["name"] == test_agent
        assert progress["lessons_completed"] == 0
        assert progress["lessons_total"] == 4
        assert progress["score"] == 0.0

    def test_evaluate_progress_after_lesson(self, educator, test_agent):
        """Test evaluating progress after completing a lesson."""
        educator.enroll(test_agent)
        educator.run_lesson(test_agent, "ethics")

        progress = educator.evaluate_progress(test_agent)

        assert progress["lessons_completed"] >= 0


class TestGraduation:
    """Tests for graduation functionality."""

    def test_graduate_insufficient_progress(self, educator, test_agent):
        """Test graduation with insufficient progress."""
        educator.enroll(test_agent)

        graduated = educator.graduate(test_agent)

        assert graduated is False

    def test_graduation_readiness_check(self, educator, test_agent):
        """Test checking graduation readiness."""
        educator.enroll(test_agent)

        progress = educator.evaluate_progress(test_agent)
        assert progress["graduation_ready"] is False


class TestLessonCurriculum:
    """Tests for lesson curriculum data."""

    def test_curriculum_completeness(self):
        """Test that all lesson types have curriculum entries."""
        expected_types = {"pr_etiquette", "code_quality", "communication", "ethics"}
        assert set(LESSON_CURRICULUM.keys()) == expected_types

    def test_curriculum_structure(self):
        """Test that curriculum entries have required fields."""
        for lesson_type, curriculum in LESSON_CURRICULUM.items():
            assert "title" in curriculum
            assert "objectives" in curriculum
            assert "anti_patterns" in curriculum
            assert len(curriculum["objectives"]) > 0
            assert len(curriculum["anti_patterns"]) > 0