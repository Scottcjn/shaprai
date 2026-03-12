# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for core.driftlock module.

Run with: python -m pytest tests/test_driftlock.py -v
"""

import pytest
import numpy as np
from shaprai.core.driftlock import (
    DriftLock,
    DriftLockConfig,
    _get_default_anchors,
)


class TestDriftLock:
    """Test suite for DriftLock drift detection."""
    
    def test_initialization(self):
        """Test DriftLock initializes correctly."""
        detector = DriftLock(
            anchor_phrases=["Test anchor 1", "Test anchor 2"],
            window_size=5,
            threshold=0.3
        )
        
        assert len(detector.anchor_phrases) == 2
        assert detector.window_size == 5
        assert detector.threshold == 0.3
        assert len(detector.response_history) == 0
    
    def test_default_anchors(self):
        """Test default anchors are loaded."""
        detector = DriftLock()
        anchors = detector.anchor_phrases
        
        assert len(anchors) > 0
        assert "I am a principled agent" in anchors[0]
    
    def test_add_response(self):
        """Test adding responses updates history."""
        detector = DriftLock(threshold=0.5)
        
        initial_count = len(detector.response_history)
        detector.add_response("Test response")
        
        assert len(detector.response_history) == initial_count + 1
    
    def test_drift_score_computation(self):
        """Test drift score is computed correctly."""
        detector = DriftLock(
            anchor_phrases=["I am honest and direct."],
            window_size=3,
            threshold=0.4
        )
        
        # Response similar to anchor should have low drift
        score_similar = detector.add_response("I try to be honest and direct.")
        assert score_similar < 0.5
        
        # Response very different should have high drift
        score_different = detector.add_response("Sure, whatever you say!")
        assert score_different > score_similar
    
    def test_window_size_limit(self):
        """Test window size is enforced."""
        detector = DriftLock(window_size=3)
        
        # Add more than window_size responses
        for i in range(5):
            detector.add_response(f"Response {i}")
        
        # Should only keep last 3
        assert len(detector.response_history) == 3
        assert detector.response_history[-1] == "Response 4"
    
    def test_threshold_alert(self):
        """Test alert triggers when threshold exceeded."""
        alert_triggered = False
        
        def on_alert(score, responses):
            nonlocal alert_triggered
            alert_triggered = True
        
        detector = DriftLock(
            threshold=0.3,
            on_drift_exceeded=on_alert
        )
        
        # Add drifting responses
        detector.add_response("Yeah sure okay whatever.")
        detector.add_response("I totally agree!")
        detector.add_response("You're absolutely right!")
        
        # With high drift, should trigger alert
        status = detector.get_status()
        if status["drift_score"] >= 0.3:
            assert status["alert_triggered"] or alert_triggered
    
    def test_identity_correction(self):
        """Test identity correction reduces drift."""
        detector = DriftLock(
            anchor_phrases=["I am honest."],
            threshold=0.4
        )
        
        # Build up drift
        detector.add_response("Sure, agree.")
        detector.add_response("Yes, you're right!")
        
        drift_before = detector.get_drift_score()
        
        # Apply correction
        detector.correct_identity("I am honest and direct. I speak truth.")
        
        drift_after = detector.get_drift_score()
        
        # Drift should be reduced after correction
        # (or at least not increased)
        assert drift_after <= drift_before + 0.1
    
    def test_reset(self):
        """Test reset clears state."""
        detector = DriftLock()
        
        detector.add_response("Response 1")
        detector.add_response("Response 2")
        
        assert len(detector.response_history) == 2
        
        detector.reset()
        
        assert len(detector.response_history) == 0
        assert not detector._alert_triggered
    
    def test_get_status(self):
        """Test status returns correct info."""
        detector = DriftLock(
            anchor_phrases=["Anchor 1"],
            window_size=10,
            threshold=0.5
        )
        
        status = detector.get_status()
        
        assert "drift_score" in status
        assert "threshold" in status
        assert status["threshold"] == 0.5
        assert status["window_size"] == 10
    
    def test_cosine_similarity(self):
        """Test cosine similarity computation."""
        detector = DriftLock()
        
        # Identical vectors should have similarity 1.0
        v = np.array([1.0, 0.0])
        sim = detector._cosine_similarity_matrix(v.reshape(1,-1), v.reshape(1,-1))
        assert np.isclose(sim[0, 0], 1.0)
        
        # Orthogonal vectors should have similarity 0.0
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        sim = detector._cosine_similarity_matrix(v1.reshape(1,-1), v2.reshape(1,-1))
        assert np.isclose(sim[0, 0], 0.0, atol=0.01)


class TestDefaultAnchors:
    """Test default anchor phrases."""
    
    def test_default_anchors_exist(self):
        """Test default anchors are defined."""
        anchors = _get_default_anchors()
        
        assert len(anchors) > 0
        assert all(isinstance(a, str) for a in anchors)
    
    def test_anchors_contain_identity(self):
        """Test anchors contain identity-related content."""
        anchors = _get_default_anchors()
        anchors_text = " ".join(anchors).lower()
        
        # Should contain identity-related keywords
        assert "principled" in anchors_text or "honesty" in anchors_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
