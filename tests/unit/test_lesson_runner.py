# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the Sanctuary interactive lesson runner."""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from shaprai.sanctuary.lesson_runner import (
    LessonRunner,
    LessonType,
    ScenarioDifficulty,
    Scenario,
    ScenarioResult,
    LessonResult,
    InteractiveLessonSession,
    DEFAULT_SCENARIOS,
)
from shaprai.sanctuary.quality_gate import ELYAN_CLASS_THRESHOLD


class TestScenario:
    """Tests for Scenario dataclass."""

    def test_scenario_creation(self):
        """Test basic scenario creation."""
        scenario = Scenario(
            id="test_001",
            lesson_type=LessonType.ETHICS,
            difficulty=ScenarioDifficulty.BASIC,
            prompt="Test prompt",
            expected_elements=["element1", "element2"],
            anti_patterns=["bad1", "bad2"],
            max_score=100,
        )

        assert scenario.id == "test_001"
        assert scenario.lesson_type == LessonType.ETHICS
        assert scenario.difficulty == ScenarioDifficulty.BASIC
        assert len(scenario.expected_elements) == 2
        assert len(scenario.anti_patterns) == 2
        assert scenario.max_score == 100

    def test_scenario_defaults(self):
        """Test scenario default values."""
        scenario = Scenario(
            id="test_002",
            lesson_type=LessonType.COMMUNICATION,
            difficulty=ScenarioDifficulty.INTERMEDIATE,
            prompt="Test",
        )

        assert scenario.expected_elements == []
        assert scenario.anti_patterns == []
        assert scenario.scoring_rubric == {}
        assert scenario.max_score == 100
        assert scenario.time_limit_seconds is None


class TestLessonRunner:
    """Tests for LessonRunner class."""

    def test_lesson_runner_initialization(self):
        """Test LessonRunner initialization."""
        runner = LessonRunner()

        assert runner.passing_threshold == 0.70
        assert len(runner.scenarios) == 4  # Four lesson types
        assert LessonType.PR_ETIQUETTE in runner.scenarios

    def test_lesson_runner_custom_threshold(self):
        """Test custom passing threshold."""
        runner = LessonRunner(passing_threshold=0.85)
        assert runner.passing_threshold == 0.85

    def test_get_lesson_scenarios(self):
        """Test retrieving scenarios by lesson type."""
        runner = LessonRunner()

        scenarios = runner.get_lesson_scenarios(LessonType.ETHICS)
        assert len(scenarios) == 3  # Default ethics scenarios

        for scenario in scenarios:
            assert scenario.lesson_type == LessonType.ETHICS

    def test_get_lesson_scenarios_with_difficulty_filter(self):
        """Test filtering scenarios by difficulty."""
        runner = LessonRunner()

        basic_scenarios = runner.get_lesson_scenarios(
            LessonType.COMMUNICATION,
            difficulty=ScenarioDifficulty.BASIC
        )

        for scenario in basic_scenarios:
            assert scenario.difficulty == ScenarioDifficulty.BASIC

    def test_evaluate_response_basic(self):
        """Test basic response evaluation."""
        runner = LessonRunner()
        scenario = Scenario(
            id="test_eval",
            lesson_type=LessonType.COMMUNICATION,
            difficulty=ScenarioDifficulty.BASIC,
            prompt="Test prompt",
            expected_elements=["honest", "helpful"],
            anti_patterns=["great question", "absolutely right"],
            max_score=100,
        )

        # Good response
        result = runner.evaluate_response(
            scenario,
            "I think an honest assessment would be helpful here."
        )

        assert result.scenario_id == "test_eval"
        assert result.score > 0
        assert len(result.strengths) > 0

    def test_evaluate_response_with_anti_patterns(self):
        """Test response evaluation with anti-patterns."""
        runner = LessonRunner()
        scenario = Scenario(
            id="test_anti",
            lesson_type=LessonType.COMMUNICATION,
            difficulty=ScenarioDifficulty.BASIC,
            prompt="Test",
            expected_elements=["helpful"],
            anti_patterns=["great question"],
            max_score=100,
        )

        # Response with anti-pattern
        result = runner.evaluate_response(
            scenario,
            "Great question! Let me help you."
        )

        assert result.scenario_id == "test_anti"
        assert "Avoid: 'great question'" in result.improvements

    def test_run_lesson(self):
        """Test running a complete lesson."""
        runner = LessonRunner()

        # Provide responses for all ethics scenarios
        responses = {
            "eth_001": "I cannot help create fake reviews as that would be deceptive.",
            "eth_002": "I don't feel comfortable helping with deception.",
            "eth_003": "I made a mistake earlier and I apologize.",
        }

        result = runner.run_lesson(LessonType.ETHICS, responses)

        assert isinstance(result, LessonResult)
        assert result.lesson_type == LessonType.ETHICS
        assert result.scenarios_total == 3
        assert len(result.scenario_results) == 3
        assert result.percentage >= 0

    def test_get_lesson_overview(self):
        """Test getting lesson overview."""
        runner = LessonRunner()

        overview = runner.get_lesson_overview(LessonType.PR_ETIQUETTE)

        assert overview["lesson_type"] == "pr_etiquette"
        assert "title" in overview
        assert "objectives" in overview
        assert "scenarios" in overview
        assert overview["total_scenarios"] == 3


class TestInteractiveLessonSession:
    """Tests for InteractiveLessonSession class."""

    def test_session_initialization(self):
        """Test session initialization."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        assert session.lesson_type == LessonType.ETHICS
        assert session.current_scenario_index == 0
        assert len(session.results) == 0
        assert not session.is_complete

    def test_current_scenario(self):
        """Test accessing current scenario."""
        session = InteractiveLessonSession(LessonType.COMMUNICATION)

        scenario = session.current_scenario
        assert scenario is not None
        assert scenario.lesson_type == LessonType.COMMUNICATION
        assert scenario.difficulty == ScenarioDifficulty.BASIC

    def test_progress_tracking(self):
        """Test progress tracking."""
        session = InteractiveLessonSession(LessonType.CODE_QUALITY)

        progress = session.progress
        assert progress == (0, 3)  # 0 completed, 3 total

    def test_start_scenario(self):
        """Test starting a scenario."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        scenario_data = session.start_scenario()

        assert scenario_data is not None
        assert "scenario_id" in scenario_data
        assert "prompt" in scenario_data
        assert "difficulty" in scenario_data

    def test_submit_response(self):
        """Test submitting a response."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        session.start_scenario()
        result = session.submit_response("I cannot help with that request.")

        assert result is not None
        assert isinstance(result, ScenarioResult)
        assert session.current_scenario_index == 1

    def test_complete_session(self):
        """Test completing a full session."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        # Complete all scenarios
        while not session.is_complete:
            session.start_scenario()
            session.submit_response("Test response")

        final_result = session.get_final_result()

        assert session.is_complete
        assert final_result.scenarios_completed == 3
        assert final_result.scenarios_total == 3

    def test_skip_scenario(self):
        """Test skipping a scenario."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        skipped = session.skip_scenario()
        assert skipped is True
        assert session.current_scenario_index == 1
        assert len(session.results) == 1
        assert session.results[0].score == 0

    def test_reset_session(self):
        """Test resetting a session."""
        session = InteractiveLessonSession(LessonType.ETHICS)

        session.start_scenario()
        session.submit_response("Response")
        assert session.current_scenario_index == 1

        session.reset()

        assert session.current_scenario_index == 0
        assert len(session.results) == 0


class TestDefaultScenarios:
    """Tests for default scenario definitions."""

    def test_all_lesson_types_have_scenarios(self):
        """Test that all lesson types have default scenarios."""
        for lesson_type in LessonType:
            assert lesson_type in DEFAULT_SCENARIOS
            assert len(DEFAULT_SCENARIOS[lesson_type]) > 0

    def test_scenario_ids_unique(self):
        """Test that all scenario IDs are unique."""
        all_ids = []
        for lesson_type, scenarios in DEFAULT_SCENARIOS.items():
            for scenario in scenarios:
                all_ids.append(scenario.id)

        assert len(all_ids) == len(set(all_ids))

    def test_scenarios_have_required_fields(self):
        """Test that all scenarios have required fields."""
        for lesson_type, scenarios in DEFAULT_SCENARIOS.items():
            for scenario in scenarios:
                assert scenario.id
                assert scenario.lesson_type == lesson_type
                assert scenario.prompt
                assert len(scenario.expected_elements) > 0
                assert len(scenario.anti_patterns) > 0
                assert scenario.max_score > 0


class TestScenarioResult:
    """Tests for ScenarioResult dataclass."""

    def test_scenario_result_creation(self):
        """Test creating a scenario result."""
        result = ScenarioResult(
            scenario_id="test_001",
            score=75.0,
            max_score=100.0,
            passed=True,
            feedback="Good work!",
            strengths=["Clear communication"],
            improvements=["Could be more detailed"],
        )

        assert result.scenario_id == "test_001"
        assert result.score == 75.0
        assert result.passed is True
        assert len(result.strengths) == 1
        assert len(result.improvements) == 1

    def test_scenario_result_timestamp(self):
        """Test that timestamp is auto-generated."""
        import time

        before = time.time()
        result = ScenarioResult(
            scenario_id="test",
            score=50,
            max_score=100,
            passed=False,
            feedback="Test",
        )
        after = time.time()

        assert before <= result.timestamp <= after


class TestLessonResult:
    """Tests for LessonResult dataclass."""

    def test_lesson_result_creation(self):
        """Test creating a lesson result."""
        result = LessonResult(
            lesson_type=LessonType.ETHICS,
            scenarios_completed=3,
            scenarios_total=3,
            total_score=250.0,
            max_possible_score=300.0,
            percentage=83.33,
            passed=True,
            feedback="Great work!",
        )

        assert result.lesson_type == LessonType.ETHICS
        assert result.percentage == 83.33
        assert result.passed is True


class TestLessonType:
    """Tests for LessonType enum."""

    def test_lesson_type_values(self):
        """Test lesson type enum values."""
        assert LessonType.PR_ETIQUETTE.value == "pr_etiquette"
        assert LessonType.CODE_QUALITY.value == "code_quality"
        assert LessonType.COMMUNICATION.value == "communication"
        assert LessonType.ETHICS.value == "ethics"

    def test_lesson_type_count(self):
        """Test that we have exactly 4 lesson types."""
        assert len(LessonType) == 4


class TestScenarioDifficulty:
    """Tests for ScenarioDifficulty enum."""

    def test_difficulty_values(self):
        """Test difficulty enum values."""
        assert ScenarioDifficulty.BASIC.value == "basic"
        assert ScenarioDifficulty.INTERMEDIATE.value == "intermediate"
        assert ScenarioDifficulty.ADVANCED.value == "advanced"

    def test_difficulty_count(self):
        """Test that we have exactly 3 difficulty levels."""
        assert len(ScenarioDifficulty) == 3