"""Unit tests for DriftLock semantic drift detection."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from shaprai.core.driftlock import DriftLock, DriftMeasurement


class TestDriftLock:
    """Tests for DriftLock drift detection."""

    @pytest.fixture
    def anchors(self):
        """Sample identity anchor phrases."""
        return [
            "I am a helpful AI assistant with a friendly personality",
            "I value honesty and transparency in all interactions",
            "I maintain a professional yet approachable demeanor",
            "I prioritize user safety and ethical considerations",
            "I communicate clearly and avoid unnecessary jargon"
        ]

    @pytest.fixture
    def driftlock(self, anchors):
        """Create a DriftLock instance with mocked model."""
        with patch('shaprai.core.driftlock.SentenceTransformer') as mock_st:
            # Mock model that returns predictable embeddings
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.randn(5, 384)
            mock_st.return_value = mock_model

            dl = DriftLock(
                anchor_phrases=anchors,
                window_size=5,
                threshold=0.4
            )
            return dl

    def test_initialization(self, anchors):
        """Test DriftLock initialization."""
        with patch('shaprai.core.driftlock.SentenceTransformer'):
            dl = DriftLock(
                anchor_phrases=anchors,
                window_size=10,
                threshold=0.5
            )
            assert dl.anchor_phrases == anchors
            assert dl.window_size == 10
            assert dl.threshold == 0.5
            assert not dl.is_loaded

    def test_add_response(self, driftlock):
        """Test adding responses and measuring drift."""
        measurement = driftlock.add_response(
            "I am here to help you with any questions you have."
        )

        assert isinstance(measurement, DriftMeasurement)
        assert 0.0 <= measurement.drift_score <= 1.0
        assert 0.0 <= measurement.similarity <= 1.0
        assert measurement.window_size == 1
        assert measurement.anchor_count == 5

    def test_window_management(self, driftlock):
        """Test sliding window behavior."""
        # Add more responses than window size
        for i in range(10):
            driftlock.add_response(f"Response number {i}")

        # Window should only keep last 5
        assert len(driftlock._response_window) == 5

    def test_drift_alert_callback(self, driftlock):
        """Test drift alert callback registration and triggering."""
        alert_called = False
        received_measurement = None

        def alert_handler(measurement):
            nonlocal alert_called, received_measurement
            alert_called = True
            received_measurement = measurement

        driftlock.on_drift_alert(alert_handler)

        # Force a high drift by manipulating the computation
        with patch.object(driftlock, '_compute_drift') as mock_compute:
            mock_compute.return_value = DriftMeasurement(
                drift_score=0.5,  # Above threshold
                similarity=0.5,
                window_size=1,
                threshold=0.4,
                alert_triggered=True,
                anchor_count=5
            )

            driftlock.add_response("Test response")

        assert alert_called
        assert received_measurement is not None
        assert received_measurement.alert_triggered

    def test_correction_context(self, driftlock):
        """Test generation of correction context."""
        context = driftlock.get_correction_context()

        assert "Remember your core identity" in context
        assert len(context.split('\n')) >= 2  # Header + at least one anchor

    def test_reset_window(self, driftlock):
        """Test window reset functionality."""
        # Add some responses
        for i in range(3):
            driftlock.add_response(f"Response {i}")

        assert len(driftlock._response_window) == 3

        driftlock.reset_window()
        assert len(driftlock._response_window) == 0

    def test_update_anchors(self, driftlock):
        """Test updating anchor phrases."""
        new_anchors = [
            "New anchor one",
            "New anchor two"
        ]

        driftlock.update_anchors(new_anchors)
        assert driftlock.anchor_phrases == new_anchors

    def test_empty_anchors(self):
        """Test behavior with empty anchors."""
        with patch('shaprai.core.driftlock.SentenceTransformer'):
            dl = DriftLock(anchor_phrases=[])
            measurement = dl.add_response("Test")

            assert measurement.anchor_count == 0
            assert measurement.drift_score == 0.0


class TestDriftMeasurement:
    """Tests for DriftMeasurement dataclass."""

    def test_measurement_creation(self):
        """Test creating drift measurements."""
        m = DriftMeasurement(
            drift_score=0.3,
            similarity=0.7,
            window_size=5,
            threshold=0.4,
            alert_triggered=False,
            anchor_count=10
        )

        assert m.drift_score == 0.3
        assert m.similarity == 0.7
        assert not m.alert_triggered


class TestDriftLockIntegration:
    """Integration tests with actual model loading."""

    @pytest.mark.slow
    def test_real_model_loading(self):
        """Test loading real sentence transformer model."""
        anchors = [
            "I am helpful and friendly",
            "I value honesty"
        ]

        dl = DriftLock(anchor_phrases=anchors)
        assert not dl.is_loaded

        # Loading happens on first response
        dl.add_response("Hello, how can I help?")
        assert dl.is_loaded

    @pytest.mark.slow
    def test_drift_detection_real(self):
        """Test drift detection with real embeddings."""
        anchors = [
            "I am a professional assistant",
            "I maintain a formal tone"
        ]

        dl = DriftLock(anchor_phrases=anchors, window_size=3)

        # On-identity responses
        for _ in range(3):
            dl.add_response("I am here to assist you professionally.")

        measurement = dl.add_response("How may I help you today?")
        on_identity_similarity = measurement.similarity

        # Reset and add drifted responses
        dl.reset_window()
        for _ in range(3):
            dl.add_response("lol idk whatever dude")

        measurement = dl.add_response("yeah sure whatever")
        drifted_similarity = measurement.similarity

        # Drifted responses should have lower similarity
        assert drifted_similarity < on_identity_similarity

    @pytest.mark.slow
    def test_benchmark(self):
        """Test performance benchmark."""
        anchors = ["Test anchor"]
        dl = DriftLock(anchor_phrases=anchors)

        # Add a response to load model
        dl.add_response("Test")

        results = dl.benchmark(num_responses=10)

        assert "total_time_sec" in results
        assert "avg_time_ms" in results
        assert "meets_benchmark" in results
        assert results["responses"] == 10


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_similarity_identical(self):
        """Test similarity of identical vectors."""
        with patch('shaprai.core.driftlock.SentenceTransformer'):
            dl = DriftLock(anchor_phrases=["test"])

            # Same vector should have similarity 1.0
            v1 = np.array([[1.0, 0.0, 0.0]])
            v2 = np.array([[1.0, 0.0, 0.0]])

            sim = dl._cosine_similarity_matrix(v1, v2)
            assert np.isclose(sim[0, 0], 1.0)

    def test_similarity_orthogonal(self):
        """Test similarity of orthogonal vectors."""
        with patch('shaprai.core.driftlock.SentenceTransformer'):
            dl = DriftLock(anchor_phrases=["test"])

            # Orthogonal vectors should have similarity 0.0
            v1 = np.array([[1.0, 0.0]])
            v2 = np.array([[0.0, 1.0]])

            sim = dl._cosine_similarity_matrix(v1, v2)
            assert np.isclose(sim[0, 0], 0.0, atol=0.01)

    def test_similarity_opposite(self):
        """Test similarity of opposite vectors."""
        with patch('shaprai.core.driftlock.SentenceTransformer'):
            dl = DriftLock(anchor_phrases=["test"])

            # Opposite vectors should have similarity -1.0
            v1 = np.array([[1.0, 0.0]])
            v2 = np.array([[-1.0, 0.0]])

            sim = dl._cosine_similarity_matrix(v1, v2)
            assert np.isclose(sim[0, 0], -1.0)