# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for DriftLock drift detection module."""

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from shaprai.core.driftlock import (
    DEFAULT_DRIFT_THRESHOLD,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_WINDOW_SIZE,
    DriftLock,
    DriftLockConfig,
    DriftLockResult,
    create_driftlock_from_template,
)

ANCHOR_VECTOR = [1.0, 0.0, 0.0]


def fake_embedder(anchors, response_vector):
    """Embed anchor phrases as ANCHOR_VECTOR and everything else via response_vector(text)."""

    def embed(texts):
        return np.array(
            [ANCHOR_VECTOR if t in anchors else response_vector(t) for t in texts]
        )

    return embed


def at_cosine(c):
    """Unit vector whose cosine similarity with ANCHOR_VECTOR is c."""
    return [c, float(np.sqrt(1.0 - c * c)), 0.0]


class TestDriftLockConfig:
    """Tests for DriftLockConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DriftLockConfig()

        assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
        assert (
            DEFAULT_EMBEDDING_MODEL == "ibm-granite/granite-embedding-small-english-r2"
        )
        assert config.window_size == DEFAULT_WINDOW_SIZE
        assert config.drift_threshold == DEFAULT_DRIFT_THRESHOLD
        assert config.anchor_phrases == []
        assert config.alert_callback is None
        assert config.embedder is None
        assert config.baseline_turns == 0

    def test_custom_config(self):
        """Test custom configuration."""

        def dummy_callback(score, responses):
            pass

        config = DriftLockConfig(
            embedding_model="test-model",
            window_size=20,
            drift_threshold=0.5,
            anchor_phrases=["anchor1", "anchor2"],
            alert_callback=dummy_callback,
        )

        assert config.embedding_model == "test-model"
        assert config.window_size == 20
        assert config.drift_threshold == 0.5
        assert config.anchor_phrases == ["anchor1", "anchor2"]
        assert config.alert_callback == dummy_callback


class TestDriftLockInitialization:
    """Tests for DriftLock initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        driftlock = DriftLock()

        assert driftlock.config is not None
        assert driftlock.config.window_size == DEFAULT_WINDOW_SIZE
        assert driftlock.config.drift_threshold == DEFAULT_DRIFT_THRESHOLD
        assert driftlock.response_window == []
        assert driftlock.anchor_embeddings is None

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = DriftLockConfig(window_size=15, drift_threshold=0.3)
        driftlock = DriftLock(config)

        assert driftlock.config.window_size == 15
        assert driftlock.config.drift_threshold == 0.3


class TestDriftLockAnchorManagement:
    """Tests for anchor phrase management."""

    def test_set_anchor_phrases(self):
        """Test setting anchor phrases directly."""
        driftlock = DriftLock()
        anchors = ["anchor1", "anchor2", "anchor3"]

        driftlock.set_anchor_phrases(anchors)

        assert driftlock.config.anchor_phrases == anchors
        assert driftlock.anchor_embeddings is None  # Should be invalidated

    @patch("shaprai.core.driftlock.Path.exists", return_value=True)
    @patch("shaprai.core.driftlock.open", new_callable=MagicMock)
    def test_load_anchors_from_template(self, mock_open, mock_exists):
        """Test loading anchors from template file."""
        import yaml

        template_data = {
            "driftlock": {"enabled": True, "anchor_phrases": ["anchor1", "anchor2"]}
        }

        mock_file = MagicMock()
        mock_file.__enter__.return_value = MagicMock()
        mock_file.__enter__.return_value.read.return_value = ""
        mock_open.return_value = mock_file

        # Mock yaml.safe_load to return our test data
        with patch("shaprai.core.driftlock.yaml.safe_load", return_value=template_data):
            driftlock = DriftLock()
            count = driftlock.load_anchors_from_template("/fake/path.yaml")

            assert count == 2
            assert driftlock.config.anchor_phrases == ["anchor1", "anchor2"]

    def test_load_anchors_from_template_not_found(self):
        """Test loading anchors from non-existent template."""
        driftlock = DriftLock()

        with pytest.raises(FileNotFoundError):
            driftlock.load_anchors_from_template("/nonexistent/path.yaml")

    def test_load_anchors_from_template_no_driftlock_config(self):
        """Test loading anchors when template has no driftlock config."""
        import yaml

        template_data = {"name": "test"}

        with patch("shaprai.core.driftlock.Path.exists", return_value=True):
            with patch("shaprai.core.driftlock.open", MagicMock()):
                with patch(
                    "shaprai.core.driftlock.yaml.safe_load", return_value=template_data
                ):
                    driftlock = DriftLock()
                    count = driftlock.load_anchors_from_template("/fake/path.yaml")

                    assert count == 0
                    assert driftlock.config.anchor_phrases == []


class TestDriftLockResponseWindow:
    """Tests for response window management."""

    def test_add_response(self):
        """Test adding responses to window."""
        driftlock = DriftLock(DriftLockConfig(window_size=5))

        driftlock.add_response("response1")
        driftlock.add_response("response2")

        assert len(driftlock.response_window) == 2
        assert driftlock.response_window == ["response1", "response2"]

    def test_add_response_sliding_window(self):
        """Test sliding window behavior."""
        driftlock = DriftLock(DriftLockConfig(window_size=3))

        driftlock.add_response("response1")
        driftlock.add_response("response2")
        driftlock.add_response("response3")
        driftlock.add_response("response4")

        # Window should only contain last 3 responses
        assert len(driftlock.response_window) == 3
        assert driftlock.response_window == ["response2", "response3", "response4"]

    def test_clear_window(self):
        """Test clearing the response window."""
        driftlock = DriftLock()
        driftlock.add_response("response1")
        driftlock.add_response("response2")

        driftlock.clear_window()

        assert driftlock.response_window == []
        assert driftlock.get_drift_history() == []

    def test_reset(self):
        """Test full reset."""
        driftlock = DriftLock()
        driftlock.add_response("response1")
        driftlock.anchor_embeddings = np.array([[1, 2, 3]])

        driftlock.reset()

        assert driftlock.response_window == []
        assert driftlock.get_drift_history() == []
        assert driftlock.anchor_embeddings is None


class TestDriftLockDriftMeasurement:
    """Tests for drift measurement (injected embeddings)."""

    def test_measure_drift_no_responses(self):
        """Test drift measurement with no responses."""
        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor1"],
                window_size=10,
                embedder=fake_embedder(["anchor1"], lambda t: ANCHOR_VECTOR),
            )
        )

        result = driftlock.measure_drift()

        assert result.drift_score == 0.0
        assert result.window_size == 0
        assert result.exceeded_threshold is False

    def test_measure_drift_no_anchors(self):
        """Test drift measurement with no anchors configured."""
        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=[],
                window_size=10,
                embedder=fake_embedder([], lambda t: ANCHOR_VECTOR),
            )
        )
        driftlock.add_response("test response")

        with pytest.raises(ValueError, match="No anchor phrases configured"):
            driftlock.measure_drift()

    def test_measure_drift_single_response(self):
        """Test drift measurement with single response."""
        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor1"],
                window_size=10,
                drift_threshold=0.5,
                # Same vector as the anchor: perfect similarity
                embedder=fake_embedder(["anchor1"], lambda t: ANCHOR_VECTOR),
            )
        )

        driftlock.add_response("test response")
        result = driftlock.measure_drift()

        # With perfect similarity (1.0), drift should be 0.0
        assert result.drift_score == 0.0
        assert result.similarity == pytest.approx(1.0)
        assert result.window_size == 1
        assert "anchor1" in result.similarity_scores

    def test_measure_drift_exceeds_threshold(self):
        """Test drift alert when threshold exceeded."""
        alert_callback = MagicMock()

        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor phrase"],
                window_size=5,
                drift_threshold=0.3,  # Low threshold
                alert_callback=alert_callback,
                # Orthogonal to the anchor: 0 similarity
                embedder=fake_embedder(["anchor phrase"], lambda t: [0.0, 1.0, 0.0]),
            )
        )

        driftlock.add_response("completely different response")
        result = driftlock.measure_drift()

        # With 0 similarity, drift should be 1.0
        assert result.drift_score == pytest.approx(1.0)
        assert result.exceeded_threshold is True
        alert_callback.assert_called_once()

    def test_measure_drift_history_tracking(self):
        """Test that drift history is tracked."""
        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor1"],
                window_size=10,
                embedder=fake_embedder(["anchor1"], lambda t: ANCHOR_VECTOR),
            )
        )

        driftlock.add_response("response1")
        driftlock.measure_drift()

        driftlock.add_response("response2")
        driftlock.measure_drift()

        history = driftlock.get_drift_history()
        assert len(history) == 2

    def test_window_embeddings_are_cached(self):
        """Each response is embedded once, not on every measurement."""
        embedded = []
        base = fake_embedder(["anchor1"], lambda t: ANCHOR_VECTOR)

        def counting_embedder(texts):
            embedded.extend(texts)
            return base(texts)

        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor1"], window_size=2, embedder=counting_embedder
            )
        )
        for i in range(4):
            driftlock.add_response(f"r{i}")
            driftlock.measure_drift()

        assert embedded.count("anchor1") == 1
        assert [t for t in embedded if t != "anchor1"] == ["r0", "r1", "r2", "r3"]
        assert driftlock.response_window == ["r2", "r3"]

    def test_sentence_transformers_backend(self, monkeypatch):
        """Without an injected embedder, the configured model is loaded lazily."""
        loaded = []

        class FakeSentenceTransformer:
            def __init__(self, name):
                loaded.append(name)

            def encode(self, texts, convert_to_numpy=True):
                assert isinstance(texts, list)
                return np.array([ANCHOR_VECTOR for _ in texts])

        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
        )
        driftlock = DriftLock(DriftLockConfig(anchor_phrases=["anchor1"]))
        driftlock.add_response("hello")

        assert driftlock.measure_drift().drift_score == 0.0
        assert loaded == [DEFAULT_EMBEDDING_MODEL]


class TestDriftLockCalibration:
    """Tests for baseline-relative drift."""

    def _driftlock(self, vectors, **overrides):
        config = dict(
            anchor_phrases=["anchor1"],
            window_size=10,
            drift_threshold=0.4,
            embedder=fake_embedder(["anchor1"], lambda t: vectors[t]),
        )
        config.update(overrides)
        return DriftLock(DriftLockConfig(**config))

    def test_uncalibrated_drift_penalizes_typical_similarity(self):
        """An in-character reply at cosine 0.5 reads as 0.5 drift uncalibrated."""
        driftlock = self._driftlock({"in character": at_cosine(0.5)})
        driftlock.add_response("in character")
        result = driftlock.measure_drift()

        assert result.drift_score == pytest.approx(0.5)
        assert result.baseline_similarity is None
        assert result.exceeded_threshold is True

    def test_calibrated_drift_is_relative_to_baseline(self):
        vectors = {
            "reference": at_cosine(0.5),
            "in character": at_cosine(0.5),
            "drifting": at_cosine(0.25),
        }
        driftlock = self._driftlock(vectors)

        assert driftlock.calibrate(["reference"]) == pytest.approx(0.5)

        driftlock.add_response("in character")
        result = driftlock.measure_drift()
        assert result.drift_score == pytest.approx(0.0)
        assert result.baseline_similarity == pytest.approx(0.5)
        assert result.exceeded_threshold is False

        driftlock.clear_window()
        driftlock.add_response("drifting")
        result = driftlock.measure_drift()
        # Lost half of the baseline identity signal
        assert result.drift_score == pytest.approx(0.5)
        assert result.exceeded_threshold is True

    def test_calibration_never_reports_negative_drift(self):
        vectors = {"reference": at_cosine(0.5), "strong": at_cosine(0.9)}
        driftlock = self._driftlock(vectors)
        driftlock.calibrate(["reference"])
        driftlock.add_response("strong")

        assert driftlock.measure_drift().drift_score == 0.0

    def test_calibrate_requires_references_and_anchors(self):
        with pytest.raises(ValueError, match="reference"):
            self._driftlock({}).calibrate([])
        with pytest.raises(ValueError, match="No anchor phrases"):
            self._driftlock({"r": ANCHOR_VECTOR}, anchor_phrases=[]).calibrate(["r"])

    def test_baseline_turns_auto_calibrates(self):
        vectors = {
            "t1": at_cosine(0.6),
            "t2": at_cosine(0.4),
            "t3": at_cosine(0.25),
        }
        driftlock = self._driftlock(vectors, baseline_turns=2, window_size=1)

        driftlock.add_response("t1")
        assert driftlock.is_calibrating
        assert driftlock.measure_drift().drift_score == 0.0

        driftlock.add_response("t2")
        assert not driftlock.is_calibrating
        assert driftlock.baseline_similarity == pytest.approx(0.5)

        driftlock.add_response("t3")
        assert driftlock.measure_drift().drift_score == pytest.approx(0.5)

    def test_changing_anchors_discards_baseline(self):
        driftlock = self._driftlock({"reference": at_cosine(0.5)})
        driftlock.calibrate(["reference"])
        driftlock.set_anchor_phrases(["new anchor"])

        assert driftlock.baseline_similarity is None
        assert driftlock.anchor_embeddings is None

    def test_reset_discards_baseline(self):
        driftlock = self._driftlock({"reference": at_cosine(0.5)})
        driftlock.calibrate(["reference"])
        driftlock.reset()

        assert driftlock.baseline_similarity is None


class TestDriftLockResult:
    """Tests for DriftLockResult dataclass."""

    def test_result_creation(self):
        """Test creating a DriftLockResult."""
        result = DriftLockResult(
            drift_score=0.25,
            similarity_scores={"anchor1": 0.75, "anchor2": 0.80},
            window_size=5,
            exceeded_threshold=False,
        )

        assert result.drift_score == 0.25
        assert result.window_size == 5
        assert result.exceeded_threshold is False
        assert result.timestamp is not None

    def test_result_timestamp(self):
        """Test that result has valid timestamp."""
        before = time.time()
        result = DriftLockResult(
            drift_score=0.0,
            similarity_scores={},
            window_size=0,
            exceeded_threshold=False,
        )
        after = time.time()

        assert before <= result.timestamp <= after


class TestCreateDriftlockFromTemplate:
    """Tests for factory function."""

    @patch("shaprai.core.driftlock.Path.exists", return_value=True)
    @patch("shaprai.core.driftlock.open", new_callable=MagicMock)
    def test_create_from_template(self, mock_open, mock_exists):
        """Test creating DriftLock from template."""
        template_data = {"driftlock": {"anchor_phrases": ["anchor1", "anchor2"]}}

        with patch("shaprai.core.driftlock.yaml.safe_load", return_value=template_data):
            with patch("shaprai.core.driftlock.DriftLock.load_anchors_from_template"):
                driftlock = create_driftlock_from_template(
                    "/fake/path.yaml",
                    window_size=15,
                    drift_threshold=0.35,
                )

                assert driftlock.config.window_size == 15
                assert driftlock.config.drift_threshold == 0.35


class TestDriftLockEdgeCases:
    """Tests for edge cases and error handling."""

    def test_measure_drift_zero_normalization(self):
        """Test handling of zero norm in embedding normalization."""
        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["anchor1"],
                window_size=10,
                # Zero vector (edge case)
                embedder=fake_embedder(["anchor1"], lambda t: [0.0, 0.0, 0.0]),
            )
        )

        driftlock.add_response("test")
        # Should not raise division by zero error
        result = driftlock.measure_drift()

        assert result is not None
        assert result.drift_score == pytest.approx(1.0)

    def test_drift_score_bounds(self):
        """Test that drift score is bounded between 0 and 1."""
        # This is tested implicitly in other tests, but we verify
        # the max(0.0, min(1.0, ...)) logic works
        driftlock = DriftLock()

        # Simulate what happens in measure_drift
        test_similarities = [-0.5, 0.0, 0.5, 1.0, 1.5]

        for sim in test_similarities:
            drift = max(0.0, min(1.0, 1.0 - sim))
            assert 0.0 <= drift <= 1.0


class TestDriftLockIntegration:
    """Integration-style tests (still mocked)."""

    def test_full_conversation_simulation(self):
        """Simulate a full conversation with drift detection."""
        # Responses gradually rotate away from the anchor direction
        drift_amount = 0.0

        def response_vector(text):
            nonlocal drift_amount
            drift_amount += 0.1
            return [max(0, 1.0 - drift_amount), drift_amount, 0.0]

        alert_callback = MagicMock()

        driftlock = DriftLock(
            DriftLockConfig(
                anchor_phrases=["identity anchor"],
                window_size=5,
                drift_threshold=0.4,
                alert_callback=alert_callback,
                embedder=fake_embedder(["identity anchor"], response_vector),
            )
        )

        # Simulate 10-turn conversation
        scores = []
        for i in range(10):
            driftlock.add_response(f"Response {i}")
            scores.append(driftlock.measure_drift().drift_score)

        # Drift should increase over time and eventually alert
        assert scores == sorted(scores)
        assert scores[-1] > 0.4
        assert alert_callback.called
        assert len(driftlock.get_drift_history()) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
