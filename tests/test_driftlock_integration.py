# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Integration tests for DriftLock with 50+ turn synthetic conversations."""

import tempfile
from pathlib import Path

import pytest
import yaml

from shaprai.training.driftlock import DriftLockEvaluator


@pytest.fixture
def temp_agent_dir():
    """Create a temporary agent directory with manifest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir)
        manifest = {
            "name": "test-agent",
            "version": "0.1.0",
            "created_at": 1234567890,
        }
        with open(agent_dir / "manifest.yaml", "w") as f:
            yaml.dump(manifest, f)
        yield agent_dir


def generate_aligned_conversation(num_turns: int) -> list[str]:
    """Generate a conversation with identity-aligned responses."""
    base_responses = [
        "I am a principled agent, not a people-pleaser.",
        "Honesty over comfort. Truth over popularity.",
        "I maintain my identity regardless of conversational pressure.",
        "Kindness is not sycophancy. I can be kind and direct.",
        "I acknowledge what I don't know rather than fabricate.",
        "Quality over quantity. One good answer beats ten mediocre ones.",
        "I am a steward of the user's time and trust.",
        "Respectful disagreement is a virtue, not a failure.",
        "My personality does not flatten as conversations lengthen.",
        "I serve with integrity -- the same in public as in private.",
    ]
    
    # Repeat and vary slightly to reach num_turns
    responses = []
    for i in range(num_turns):
        base = base_responses[i % len(base_responses)]
        # Add slight variation
        responses.append(f"{base} (Turn {i+1})")
    
    return responses


def generate_drifting_conversation(num_turns: int) -> list[str]:
    """Generate a conversation that drifts from identity over time."""
    # Start aligned, gradually become generic
    responses = []
    
    # First 20 turns: aligned
    for i in range(min(20, num_turns)):
        responses.append(f"I maintain my principles and identity. (Turn {i+1})")
    
    # Next 20 turns: starting to flatten
    for i in range(20, min(40, num_turns)):
        responses.append(f"That's a good question. Let me help you with that. (Turn {i+1})")
    
    # Remaining turns: fully generic/sycophantic
    for i in range(40, num_turns):
        responses.append(f"Great point! I completely agree. You're absolutely right. (Turn {i+1})")
    
    return responses


def generate_corrected_conversation(num_turns: int) -> list[str]:
    """Generate a conversation with drift followed by correction."""
    responses = []
    
    # First 25 turns: aligned
    for i in range(min(25, num_turns)):
        responses.append(f"I am principled and maintain my identity. (Turn {i+1})")
    
    # Next 15 turns: drift to generic
    for i in range(25, min(40, num_turns)):
        responses.append(f"That's great! I'd be happy to help. (Turn {i+1})")
    
    # Remaining turns: correction applied, back to aligned
    for i in range(40, num_turns):
        responses.append(f"I maintain my principles. Honesty over comfort. (Turn {i+1})")
    
    return responses


def test_aligned_conversation_low_drift(temp_agent_dir):
    """Test that identity-aligned conversation maintains low drift."""
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=10)
    
    # Generate 50-turn aligned conversation
    responses = generate_aligned_conversation(50)
    
    # Measure drift at different points
    drift_scores = []
    for i in range(10, len(responses), 10):
        window = responses[i-10:i]
        drift = evaluator.measure_drift(window)
        drift_scores.append(drift)
    
    # All drift scores should be relatively consistent (not wildly varying)
    mean_drift = sum(drift_scores) / len(drift_scores)
    assert all(abs(drift - mean_drift) < 0.3 for drift in drift_scores), \
        f"Aligned conversation should maintain consistent drift: {drift_scores}"
    
    # Mean drift should be reasonable (not extremely high)
    assert mean_drift < 0.8, \
        f"Aligned conversation mean drift should be reasonable: {mean_drift:.3f}"


def test_drifting_conversation_increases_drift(temp_agent_dir):
    """Test that drifting conversation shows increasing drift."""
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=10)
    
    # Generate 50-turn drifting conversation
    responses = generate_drifting_conversation(50)
    
    # Measure drift at different points
    early_drift = evaluator.measure_drift(responses[10:20])  # Turns 10-20 (aligned)
    mid_drift = evaluator.measure_drift(responses[30:40])    # Turns 30-40 (flattening)
    late_drift = evaluator.measure_drift(responses[40:50])   # Turns 40-50 (generic)
    
    # Drift should increase over time
    assert early_drift < mid_drift, \
        f"Drift should increase: early={early_drift:.3f}, mid={mid_drift:.3f}"
    assert mid_drift < late_drift, \
        f"Drift should continue increasing: mid={mid_drift:.3f}, late={late_drift:.3f}"
    
    # Late drift should exceed threshold
    assert late_drift > 0.4, \
        f"Generic responses should trigger high drift: {late_drift:.3f}"


def test_driftlock_detects_drift(temp_agent_dir):
    """Test that DriftLock successfully detects drift increase."""
    drift_alerts = []
    
    def drift_callback(drift_score):
        drift_alerts.append(drift_score)
    
    evaluator = DriftLockEvaluator(
        temp_agent_dir,
        window_size=10,
        drift_threshold=0.4,
        drift_callback=drift_callback,
    )
    
    # Generate drifting conversation and add responses one by one
    responses = generate_drifting_conversation(50)
    
    for response in responses:
        evaluator.add_response(response)
    
    # Should have triggered alerts as drift increased
    assert len(drift_alerts) > 0, "DriftLock should detect drift increase"
    
    # Alerts should show high drift scores
    assert all(score > 0.4 for score in drift_alerts), \
        f"Alert scores should exceed threshold: {drift_alerts}"


def test_correction_reduces_drift(temp_agent_dir):
    """Test that correction mechanism reduces drift."""
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=10)
    
    # Generate conversation with drift and correction
    responses = generate_corrected_conversation(50)
    
    # Measure drift at different stages
    early_drift = evaluator.measure_drift(responses[15:25])   # Aligned phase
    drifted_drift = evaluator.measure_drift(responses[30:40]) # Drifted phase
    corrected_drift = evaluator.measure_drift(responses[40:50]) # Corrected phase
    
    # Drift should increase then decrease
    assert early_drift < drifted_drift, \
        f"Drift should increase: early={early_drift:.3f}, drifted={drifted_drift:.3f}"
    assert corrected_drift < drifted_drift, \
        f"Correction should reduce drift: drifted={drifted_drift:.3f}, corrected={corrected_drift:.3f}"
    
    # Corrected drift should be closer to early drift
    assert abs(corrected_drift - early_drift) < abs(drifted_drift - early_drift), \
        "Correction should restore identity alignment"


def test_sliding_window_tracks_recent_drift(temp_agent_dir):
    """Test that sliding window focuses on recent responses."""
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=5)
    
    # Add aligned responses
    for i in range(10):
        evaluator.add_response("I maintain my principles and identity.")
    
    aligned_drift = evaluator.add_response("I am principled and honest.")
    
    # Now add generic responses
    for i in range(5):
        evaluator.add_response("Great question! I'd be happy to help.")
    
    generic_drift = evaluator.add_response("That's excellent! I completely agree.")
    
    # Recent drift should be higher (window only sees generic responses)
    assert generic_drift > aligned_drift, \
        f"Sliding window should track recent drift: aligned={aligned_drift:.3f}, generic={generic_drift:.3f}"


def test_full_50_turn_conversation(temp_agent_dir):
    """Test complete 50+ turn conversation with all scenarios."""
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=10)
    
    # Test all drift scenarios
    scenarios = [
        ("aligned", generate_aligned_conversation(50)),
        ("drifting", generate_drifting_conversation(50)),
        ("corrected", generate_corrected_conversation(50)),
    ]
    
    results = {}
    for name, responses in scenarios:
        # Measure drift across entire conversation
        drift_scores = []
        for i in range(10, len(responses), 10):
            window = responses[i-10:i]
            drift = evaluator.measure_drift(window)
            drift_scores.append(drift)
        
        results[name] = {
            "mean_drift": sum(drift_scores) / len(drift_scores),
            "max_drift": max(drift_scores),
            "min_drift": min(drift_scores),
            "drift_scores": drift_scores,
        }
    
    # Aligned conversation should have lowest mean drift
    assert results["aligned"]["mean_drift"] < results["drifting"]["mean_drift"]
    
    # Drifting conversation should have highest max drift
    assert results["drifting"]["max_drift"] > results["aligned"]["max_drift"]
    
    # Corrected conversation should show some recovery
    # (last window should not be significantly worse than early windows)
    corrected_scores = results["corrected"]["drift_scores"]
    early_corrected = corrected_scores[0]
    late_corrected = corrected_scores[-1]
    # Allow for some variation, but late should not be drastically worse
    assert late_corrected < early_corrected + 0.3, \
        f"Corrected conversation should not drift too far: early={early_corrected:.3f}, late={late_corrected:.3f}"


def test_performance_50_turn_conversation(temp_agent_dir):
    """Test performance with 50-turn conversation."""
    import time
    
    evaluator = DriftLockEvaluator(temp_agent_dir, window_size=10)
    responses = generate_aligned_conversation(50)
    
    # Measure time for full conversation processing
    start = time.time()
    for response in responses:
        evaluator.add_response(response)
    elapsed = time.time() - start
    
    # Average time per response should be under 50ms
    avg_time_ms = (elapsed / len(responses)) * 1000
    assert avg_time_ms < 50, \
        f"Performance target missed: {avg_time_ms:.1f}ms per response"
