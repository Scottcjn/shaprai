# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for the self-governance module."""

import pytest
import yaml
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from shaprai.core.self_governor import (
    AgentMetrics,
    GovernanceAction,
    GovernanceDecision,
    DriftReport,
    collect_metrics,
    evaluate_performance,
    adapt_parameters,
    check_drift,
)


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = AgentMetrics()
        
        assert metrics.engagement == 0.0
        assert metrics.quality == 0.0
        assert metrics.bounty_completion == 0.0
        assert metrics.community_feedback == 0.0
        assert metrics.drift_score == 0.0
        assert isinstance(metrics.timestamp, float)

    def test_custom_metrics(self):
        """Test custom metrics initialization."""
        metrics = AgentMetrics(
            engagement=0.8,
            quality=0.9,
            bounty_completion=0.7,
            community_feedback=0.5,
            drift_score=0.1,
        )
        
        assert metrics.engagement == 0.8
        assert metrics.quality == 0.9
        assert metrics.bounty_completion == 0.7
        assert metrics.community_feedback == 0.5
        assert metrics.drift_score == 0.1

    def test_composite_score_all_zero(self):
        """Test composite score when all metrics are zero."""
        metrics = AgentMetrics()
        # With all zeros: 0.25*0 + 0.30*0 + 0.25*0 + 0.10*0.5 (feedback transformed) + 0.10*1.0 (drift) = 0.15
        assert metrics.composite_score == pytest.approx(0.15, rel=1e-5)

    def test_composite_score_all_max(self):
        """Test composite score when all metrics are maximum."""
        metrics = AgentMetrics(
            engagement=1.0,
            quality=1.0,
            bounty_completion=1.0,
            community_feedback=1.0,
            drift_score=0.0,
        )
        assert metrics.composite_score == 1.0

    def test_composite_score_weights(self):
        """Test that composite score uses correct weights."""
        metrics = AgentMetrics(
            engagement=1.0,  # 0.25 weight
            quality=1.0,      # 0.30 weight
            bounty_completion=1.0,  # 0.25 weight
            community_feedback=1.0,  # 0.10 weight (after transformation)
            drift_score=0.0,   # 0.10 weight
        )
        # 0.25*1 + 0.30*1 + 0.25*1 + 0.10*1 + 0.10*1 = 1.0
        assert metrics.composite_score == 1.0

    def test_composite_score_negative_feedback(self):
        """Test composite score with negative community feedback."""
        metrics = AgentMetrics(
            engagement=0.0,
            quality=0.0,
            bounty_completion=0.0,
            community_feedback=-1.0,  # Should be transformed to 0
            drift_score=1.0,
        )
        # community_feedback: max(0, (-1+1)/2) = 0
        # drift: max(0, 1-1) = 0
        assert metrics.composite_score == 0.0


class TestGovernanceAction:
    """Tests for GovernanceAction enum."""

    def test_all_actions_exist(self):
        """Test that all expected actions are defined."""
        actions = [action.value for action in GovernanceAction]
        
        assert "maintain" in actions
        assert "strengthen" in actions
        assert "prune" in actions
        assert "retrain" in actions
        assert "sanctuary" in actions
        assert "retire" in actions


class TestGovernanceDecision:
    """Tests for GovernanceDecision dataclass."""

    def test_minimal_decision(self):
        """Test minimal governance decision."""
        decision = GovernanceDecision(
            action=GovernanceAction.MAINTAIN,
            confidence=0.7,
            reasoning="Test reasoning",
        )
        
        assert decision.action == GovernanceAction.MAINTAIN
        assert decision.confidence == 0.7
        assert decision.reasoning == "Test reasoning"
        assert decision.parameter_adjustments == {}

    def test_full_decision(self):
        """Test governance decision with parameter adjustments."""
        decision = GovernanceDecision(
            action=GovernanceAction.STRENGTHEN,
            confidence=0.9,
            reasoning="Excellent performance",
            parameter_adjustments={"confidence_boost": 0.05},
        )
        
        assert decision.action == GovernanceAction.STRENGTHEN
        assert decision.parameter_adjustments == {"confidence_boost": 0.05}


class TestDriftReport:
    """Tests for DriftReport dataclass."""

    def test_passed_report(self):
        """Test a passing drift report."""
        report = DriftReport(
            drift_score=0.05,
            anchor_hits=10,
            anchor_total=10,
            passed=True,
        )
        
        assert report.drift_score == 0.05
        assert report.passed is True
        assert report.details == []

    def test_failed_report(self):
        """Test a failing drift report."""
        report = DriftReport(
            drift_score=0.5,
            anchor_hits=3,
            anchor_total=10,
            passed=False,
            details=[{"anchor": "test", "present": False}],
        )
        
        assert report.drift_score == 0.5
        assert report.passed is False
        assert len(report.details) == 1


class TestCollectMetrics:
    """Tests for collect_metrics function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collect_metrics_from_file(self):
        """Test collecting metrics from existing metrics file."""
        metrics_data = {
            "engagement": 0.8,
            "quality": 0.9,
            "bounty_completion": 0.7,
            "community_feedback": 0.5,
            "drift_score": 0.1,
        }
        
        metrics_path = self.temp_dir / "metrics.yaml"
        with open(metrics_path, "w") as f:
            yaml.dump(metrics_data, f)
        
        metrics = collect_metrics(self.temp_dir)
        
        assert metrics.engagement == 0.8
        assert metrics.quality == 0.9
        assert metrics.bounty_completion == 0.7
        assert metrics.community_feedback == 0.5
        assert metrics.drift_score == 0.1

    def test_collect_metrics_no_file(self):
        """Test collecting metrics when no metrics file exists."""
        metrics = collect_metrics(self.temp_dir)
        
        assert metrics.engagement == 0.0
        assert metrics.quality == 0.0
        assert metrics.bounty_completion == 0.0
        assert metrics.community_feedback == 0.0
        assert metrics.drift_score == 0.0

    def test_collect_metrics_partial_data(self):
        """Test collecting metrics with partial data."""
        metrics_data = {"engagement": 0.5, "quality": 0.6}
        
        metrics_path = self.temp_dir / "metrics.yaml"
        with open(metrics_path, "w") as f:
            yaml.dump(metrics_data, f)
        
        metrics = collect_metrics(self.temp_dir)
        
        assert metrics.engagement == 0.5
        assert metrics.quality == 0.6
        assert metrics.bounty_completion == 0.0  # Default


class TestEvaluatePerformance:
    """Tests for evaluate_performance function."""

    def test_excellent_performance(self):
        """Test evaluation of excellent performance."""
        metrics = AgentMetrics(
            engagement=0.9,
            quality=0.95,
            bounty_completion=0.9,
            community_feedback=0.8,
            drift_score=0.05,
        )
        
        decision = evaluate_performance(metrics)
        
        assert decision.action == GovernanceAction.STRENGTHEN
        assert decision.confidence >= 0.8
        assert "excellent" in decision.reasoning.lower()

    def test_acceptable_performance(self):
        """Test evaluation of acceptable performance."""
        metrics = AgentMetrics(
            engagement=0.6,
            quality=0.6,
            bounty_completion=0.6,
            community_feedback=0.5,
            drift_score=0.1,
        )
        
        decision = evaluate_performance(metrics)
        
        assert decision.action == GovernanceAction.MAINTAIN
        assert "acceptable" in decision.reasoning.lower()

    def test_low_performance_retrain(self):
        """Test evaluation of low but salvageable performance."""
        metrics = AgentMetrics(
            engagement=0.3,
            quality=0.3,
            bounty_completion=0.3,
            community_feedback=0.2,
            drift_score=0.15,
        )
        
        decision = evaluate_performance(metrics)
        
        assert decision.action == GovernanceAction.RETRAIN
        assert "retrain" in decision.reasoning.lower()

    def test_critical_performance_retire(self):
        """Test evaluation of critically low performance."""
        metrics = AgentMetrics(
            engagement=0.1,
            quality=0.1,
            bounty_completion=0.1,
            community_feedback=-0.5,
            drift_score=0.2,
        )
        
        decision = evaluate_performance(metrics)
        
        assert decision.action == GovernanceAction.RETIRE
        assert "critically" in decision.reasoning.lower() or "low" in decision.reasoning.lower()

    def test_high_drift_sanctuary_return(self):
        """Test that high drift triggers sanctuary return regardless of score."""
        metrics = AgentMetrics(
            engagement=0.95,
            quality=0.95,
            bounty_completion=0.95,
            community_feedback=0.9,
            drift_score=0.35,  # Above 0.30 threshold
        )
        
        decision = evaluate_performance(metrics)
        
        assert decision.action == GovernanceAction.SANCTUARY_RETURN
        assert "drift" in decision.reasoning.lower()
        assert decision.confidence == 0.9

    def test_drift_threshold_boundary(self):
        """Test drift score exactly at threshold."""
        metrics = AgentMetrics(
            engagement=0.9,
            quality=0.9,
            bounty_completion=0.9,
            community_feedback=0.8,
            drift_score=0.30,  # Exactly at threshold
        )
        
        decision = evaluate_performance(metrics)
        
        # Should not trigger sanctuary return (threshold is > 0.30)
        assert decision.action == GovernanceAction.STRENGTHEN

    def test_strengthen_includes_adjustments(self):
        """Test that strengthen action includes parameter adjustments."""
        metrics = AgentMetrics(
            engagement=0.9,
            quality=0.9,
            bounty_completion=0.9,
            community_feedback=0.8,
            drift_score=0.05,
        )
        
        decision = evaluate_performance(metrics)
        
        assert "confidence_boost" in decision.parameter_adjustments
        assert "autonomy_level" in decision.parameter_adjustments

    def test_retrain_includes_adjustments(self):
        """Test that retrain action includes parameter adjustments."""
        metrics = AgentMetrics(
            engagement=0.3,
            quality=0.3,
            bounty_completion=0.3,
            community_feedback=0.2,
            drift_score=0.15,
        )
        
        decision = evaluate_performance(metrics)
        
        assert "prune_weak_patterns" in decision.parameter_adjustments
        assert "retrain_phase" in decision.parameter_adjustments


class TestAdaptParameters:
    """Tests for adapt_parameters function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_adapt_parameters_basic(self):
        """Test basic parameter adaptation."""
        # Create manifest
        manifest = {
            "name": "test-agent",
            "state": "deployed",
            "adapted_parameters": {},
        }
        manifest_path = self.temp_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        
        decision = GovernanceDecision(
            action=GovernanceAction.STRENGTHEN,
            confidence=0.9,
            reasoning="Test",
            parameter_adjustments={"confidence_boost": 0.05},
        )
        
        adapt_parameters(self.temp_dir, decision)
        
        with open(manifest_path, "r") as f:
            updated = yaml.safe_load(f)
        
        assert "governance_history" in updated
        assert len(updated["governance_history"]) == 1
        assert updated["governance_history"][0]["action"] == "strengthen"
        assert updated["adapted_parameters"]["confidence_boost"] == 0.05

    def test_adapt_parameters_multiple_decisions(self):
        """Test multiple governance decisions are tracked."""
        manifest = {"name": "test-agent", "state": "deployed"}
        manifest_path = self.temp_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        
        decision1 = GovernanceDecision(
            action=GovernanceAction.MAINTAIN,
            confidence=0.7,
            reasoning="First",
        )
        decision2 = GovernanceDecision(
            action=GovernanceAction.STRENGTHEN,
            confidence=0.9,
            reasoning="Second",
            parameter_adjustments={"boost": 0.1},
        )
        
        adapt_parameters(self.temp_dir, decision1)
        adapt_parameters(self.temp_dir, decision2)
        
        with open(manifest_path, "r") as f:
            updated = yaml.safe_load(f)
        
        assert len(updated["governance_history"]) == 2

    def test_adapt_parameters_no_manifest(self):
        """Test adaptation when manifest doesn't exist (should not crash)."""
        decision = GovernanceDecision(
            action=GovernanceAction.MAINTAIN,
            confidence=0.7,
            reasoning="Test",
        )
        
        # Should not raise an exception
        adapt_parameters(self.temp_dir / "nonexistent", decision)


class TestCheckDrift:
    """Tests for check_drift function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_drift_no_manifest(self):
        """Test drift check when manifest doesn't exist."""
        report = check_drift(self.temp_dir)
        
        assert report.drift_score == 1.0
        assert report.anchor_hits == 0
        assert report.anchor_total == 0
        assert report.passed is False

    def test_check_drift_no_anchors(self):
        """Test drift check with no anchor phrases."""
        manifest = {
            "name": "test-agent",
            "driftlock": {"enabled": True},
        }
        manifest_path = self.temp_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        
        report = check_drift(self.temp_dir)
        
        assert report.drift_score == 0.0
        assert report.anchor_hits == 0
        assert report.anchor_total == 0
        assert report.passed is True

    def test_check_drift_with_anchors(self):
        """Test drift check with anchor phrases."""
        manifest = {
            "name": "test-agent",
            "driftlock": {
                "enabled": True,
                "anchor_phrases": ["anchor1", "anchor2", "anchor3"],
            },
        }
        manifest_path = self.temp_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        
        report = check_drift(self.temp_dir)
        
        assert report.drift_score == 0.05
        assert report.anchor_hits == 3
        assert report.anchor_total == 3
        assert report.passed is True
        assert len(report.details) == 3
