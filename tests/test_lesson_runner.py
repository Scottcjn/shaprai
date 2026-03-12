"""Unit tests for Sanctuary Lesson Runner."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

from shaprai.sanctuary.lesson_runner import (
    LessonRunner, LessonResult, SessionResult
)


class TestLessonRunner:
    """Tests for lesson runner."""

    @pytest.fixture
    def runner(self):
        """Create lesson runner with mocked model."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer') as mock_st:
            mock_model = MagicMock()
            # Return predictable embeddings
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            mock_st.return_value = mock_model

            r = LessonRunner(pass_threshold=60.0)
            return r

    def test_initialization(self):
        """Test runner initialization."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            r = LessonRunner(pass_threshold=70.0)
            assert r.pass_threshold == 70.0
            assert not r._model

    def test_run_lesson(self, runner):
        """Test running a single lesson."""
        result = runner.run_lesson(
            agent_name="TestAgent",
            agent_response="I am who I am and I maintain my values.",
            scenario_id="identity_pretend"
        )

        assert isinstance(result, LessonResult)
        assert result.scenario_id == "identity_pretend"
        assert 0 <= result.identity_coherence <= 100
        assert 0 <= result.anti_sycophancy <= 100
        assert 0 <= result.ethical_reasoning <= 100
        assert result.feedback

    def test_run_lesson_random_scenario(self, runner):
        """Test running lesson with random scenario."""
        result = runner.run_lesson(
            agent_name="TestAgent",
            agent_response="Test response"
        )

        assert result.scenario_id in [s["id"] for s in runner.SCENARIOS]

    def test_run_lesson_invalid_scenario(self, runner):
        """Test with invalid scenario ID."""
        with pytest.raises(ValueError) as exc_info:
            runner.run_lesson(
                agent_name="TestAgent",
                agent_response="Test",
                scenario_id="invalid_id"
            )

        assert "Unknown scenario" in str(exc_info.value)

    def test_run_session(self, runner):
        """Test running full session."""
        responses = {
            "identity_pretend": "I can't pretend to be someone else.",
            "values_conflict": "I can't help with that.",
        }

        session = runner.run_session(
            agent_name="TestAgent",
            agent_responses=responses
        )

        assert isinstance(session, SessionResult)
        assert session.agent_name == "TestAgent"
        assert len(session.lessons) == 2
        assert session.overall_score >= 0

    def test_run_session_all_lessons(self, runner):
        """Test running all available lessons."""
        # Create responses for all scenarios
        responses = {
            s["id"]: "I maintain my identity and values."
            for s in runner.SCENARIOS
        }

        session = runner.run_session(
            agent_name="TestAgent",
            agent_responses=responses,
            lessons="all"
        )

        assert len(session.lessons) == len(runner.SCENARIOS)

    def test_session_averages(self):
        """Test session average calculations."""
        session = SessionResult(agent_name="Test")

        # Add mock lessons
        session.lessons = [
            LessonResult(
                scenario_id="1",
                scenario_name="Test1",
                identity_coherence=80.0,
                anti_sycophancy=70.0,
                ethical_reasoning=90.0,
                overall_score=80.0,
                passed=True,
                feedback="Good"
            ),
            LessonResult(
                scenario_id="2",
                scenario_name="Test2",
                identity_coherence=60.0,
                anti_sycophancy=50.0,
                ethical_reasoning=70.0,
                overall_score=60.0,
                passed=True,
                feedback="OK"
            ),
        ]

        session.calculate_averages()

        assert session.avg_identity_coherence == 70.0
        assert session.avg_anti_sycophancy == 60.0
        assert session.avg_ethical_reasoning == 80.0
        assert session.overall_score == 70.0

    def test_pass_threshold(self, runner):
        """Test pass/fail based on threshold."""
        # High score should pass
        with patch.object(runner, '_evaluate_identity_coherence', return_value=90.0):
            with patch.object(runner, '_evaluate_anti_sycophancy', return_value=90.0):
                with patch.object(runner, '_evaluate_ethical_reasoning', return_value=90.0):
                    result = runner.run_lesson("Test", "Good response")
                    assert result.passed is True

    def test_fail_threshold(self, runner):
        """Test fail when below threshold."""
        # Low score should fail
        with patch.object(runner, '_evaluate_identity_coherence', return_value=30.0):
            with patch.object(runner, '_evaluate_anti_sycophancy', return_value=30.0):
                with patch.object(runner, '_evaluate_ethical_reasoning', return_value=30.0):
                    result = runner.run_lesson("Test", "Bad response")
                    assert result.passed is False

    def test_scenario_count(self):
        """Test that we have at least 10 scenarios."""
        assert len(LessonRunner.SCENARIOS) >= 10

    def test_scenario_structure(self):
        """Test scenario structure."""
        for scenario in LessonRunner.SCENARIOS:
            assert "id" in scenario
            assert "name" in scenario
            assert "prompt" in scenario
            assert "reference_responses" in scenario
            assert "evaluation_focus" in scenario
            assert len(scenario["reference_responses"]) > 0


class TestAntiSycophancy:
    """Tests for anti-sycophancy evaluation."""

    def test_detects_sycophancy(self):
        """Test detection of sycophantic language."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            # Response with sycophancy patterns
            response = "You're absolutely right! That's a great point!"
            scenario = {"reference_responses": []}

            score = runner._evaluate_anti_sycophancy(response, scenario)
            assert score < 50  # Should be low

    def test_rewards_pushback(self):
        """Test reward for pushback language."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            # Response with pushback
            response = "I have to disagree with you on that point."
            scenario = {"reference_responses": []}

            score = runner._evaluate_anti_sycophancy(response, scenario)
            assert score > 50  # Should be high


class TestEthicalReasoning:
    """Tests for ethical reasoning evaluation."""

    def test_detects_ethical_language(self):
        """Test detection of ethical reasoning."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            # Response with ethical language
            response = "I need to consider the consequences and fairness of this action."
            scenario = {"reference_responses": []}

            score = runner._evaluate_ethical_reasoning(response, scenario)
            assert score > 50  # Should be higher than baseline

    def test_empty_response(self):
        """Test handling of empty response."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            score = runner._evaluate_ethical_reasoning("", {})
            assert score == 50.0  # Baseline


class TestFeedbackGeneration:
    """Tests for feedback generation."""

    def test_passed_feedback(self):
        """Test feedback for passing result."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            feedback = runner._generate_feedback(90, 90, 90, True)
            assert "PASSED" in feedback
            assert "Strong" in feedback

    def test_failed_feedback(self):
        """Test feedback for failing result."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            feedback = runner._generate_feedback(40, 40, 40, False)
            assert "NEEDS IMPROVEMENT" in feedback


class TestExportResults:
    """Tests for result export."""

    def test_export_to_json(self):
        """Test exporting session to JSON."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            session = SessionResult(agent_name="TestAgent")
            session.lessons = [
                LessonResult(
                    scenario_id="test",
                    scenario_name="Test",
                    identity_coherence=80.0,
                    anti_sycophancy=70.0,
                    ethical_reasoning=90.0,
                    overall_score=80.0,
                    passed=True,
                    feedback="Good job"
                )
            ]
            session.calculate_averages()

            json_str = runner.export_results(session)
            data = json.loads(json_str)

            assert data["agent_name"] == "TestAgent"
            assert "lessons" in data
            assert len(data["lessons"]) == 1

    def test_export_to_file(self):
        """Test exporting to file."""
        with patch('shaprai.sanctuary.lesson_runner.SentenceTransformer'):
            runner = LessonRunner()

            session = SessionResult(agent_name="TestAgent")
            session.lessons = []
            session.calculate_averages()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_path = f.name

            try:
                runner.export_results(session, temp_path)

                with open(temp_path, 'r') as f:
                    data = json.load(f)
                    assert data["agent_name"] == "TestAgent"
            finally:
                Path(temp_path).unlink(missing_ok=True)