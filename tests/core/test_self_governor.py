import pytest
import yaml
from pathlib import Path
from shaprai.core.self_governor import AgentMetrics, GovernanceAction, evaluate_performance, collect_metrics, adapt_parameters, check_drift

def test_composite_score():
    m = AgentMetrics(engagement=1.0, quality=1.0, bounty_completion=1.0, community_feedback=1.0, drift_score=0.0)
    assert m.composite_score == 1.0
    
    m_poor = AgentMetrics(engagement=0.0, quality=0.0, bounty_completion=0.0, community_feedback=-1.0, drift_score=1.0)
    assert m_poor.composite_score == 0.0

def test_evaluate_performance_drift():
    m = AgentMetrics(drift_score=0.4)
    decision = evaluate_performance(m)
    assert decision.action == GovernanceAction.SANCTUARY_RETURN

def test_evaluate_performance_strengthen():
    m = AgentMetrics(engagement=0.9, quality=0.9, bounty_completion=0.9)
    decision = evaluate_performance(m)
    assert decision.action == GovernanceAction.STRENGTHEN

def test_evaluate_performance_retire():
    m = AgentMetrics(engagement=0.1, quality=0.1)
    decision = evaluate_performance(m)
    assert decision.action == GovernanceAction.RETIRE

def test_collect_metrics(tmp_path):
    agent_dir = tmp_path / "bot"
    agent_dir.mkdir()
    metrics_file = agent_dir / "metrics.yaml"
    
    with open(metrics_file, "w") as f:
        yaml.dump({"engagement": 0.8, "quality": 0.7}, f)
        
    m = collect_metrics(agent_dir)
    assert m.engagement == 0.8
    assert m.quality == 0.7

def test_adapt_parameters(tmp_path):
    agent_dir = tmp_path / "bot"
    agent_dir.mkdir()
    manifest_file = agent_dir / "manifest.yaml"
    with open(manifest_file, "w") as f:
        yaml.dump({"name": "bot", "state": "active"}, f)
        
    from shaprai.core.self_governor import GovernanceDecision
    decision = GovernanceDecision(
        action=GovernanceAction.STRENGTHEN,
        confidence=0.9,
        reasoning="Good job",
        parameter_adjustments={"boost": 0.1}
    )
    
    adapt_parameters(agent_dir, decision)
    
    with open(manifest_file, "r") as f:
        manifest = yaml.safe_load(f)
        
    assert manifest["adapted_parameters"]["boost"] == 0.1
    assert manifest["governance_history"][-1]["action"] == "strengthen"

def test_check_drift(tmp_path):
    agent_dir = tmp_path / "bot"
    agent_dir.mkdir()
    manifest_file = agent_dir / "manifest.yaml"
    with open(manifest_file, "w") as f:
        yaml.dump({"driftlock": {"anchor_phrases": ["hello"]}}, f)
        
    report = check_drift(agent_dir)
    assert report.passed is True
    assert report.anchor_total == 1
