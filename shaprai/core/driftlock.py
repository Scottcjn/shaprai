"""DriftLock — Semantic Drift Detection for Agent Identity Coherence.

DriftLock monitors how far an agent's responses have drifted from its
core identity anchors using sentence-level embedding cosine similarity.
This ensures personality coherence over long conversations.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Callable, Optional
import numpy as np

logger = logging.getLogger("shaprai.driftlock")


@dataclass
class DriftMeasurement:
    """Result of a drift measurement."""
    drift_score: float  # 0.0 = perfect, 1.0 = completely drifted
    similarity: float   # Cosine similarity to anchors
    window_size: int    # Number of responses in window
    threshold: float    # Alert threshold used
    alert_triggered: bool
    anchor_count: int


class DriftLock:
    """Semantic drift detector using embedding similarity.

    Monitors agent responses against identity anchor phrases to detect
    when the agent's personality is drifting from its configured identity.

    Attributes:
        anchor_phrases: Core phrases defining the agent's personality
        window_size: Number of recent responses to consider
        threshold: Drift score that triggers alerts (0.0-1.0)
        model: Sentence transformer model for embeddings
    """

    def __init__(
        self,
        anchor_phrases: List[str],
        window_size: int = 10,
        threshold: float = 0.4,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """Initialize DriftLock.

        Args:
            anchor_phrases: Identity-defining phrases from personality template
            window_size: Sliding window size for recent responses
            threshold: Drift alert threshold (0.0-1.0, lower = stricter)
            model_name: Sentence transformer model to use
        """
        self.anchor_phrases = anchor_phrases
        self.window_size = window_size
        self.threshold = threshold
        self._model_name = model_name
        self._model = None
        self._anchor_embeddings: Optional[np.ndarray] = None
        self._response_window: List[str] = []
        self._alert_callbacks: List[Callable[[DriftMeasurement], None]] = []

        logger.info(f"DriftLock initialized with {len(anchor_phrases)} anchors")

    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading sentence transformer: {self._model_name}")
                self._model = SentenceTransformer(self._model_name)
                # Pre-compute anchor embeddings
                self._anchor_embeddings = self._model.encode(
                    self.anchor_phrases,
                    convert_to_numpy=True
                )
                logger.info("Model loaded and anchors encoded")
            except ImportError:
                raise ImportError(
                    "sentence-transformers required. Install with: "
                    "pip install sentence-transformers"
                )

    def add_response(self, response: str) -> DriftMeasurement:
        """Add a response to the window and measure drift.

        Args:
            response: The agent's response text

        Returns:
            DriftMeasurement with current drift status
        """
        self._load_model()

        # Add to window
        self._response_window.append(response)
        if len(self._response_window) > self.window_size:
            self._response_window.pop(0)

        # Compute drift
        measurement = self._compute_drift()

        # Trigger alerts if threshold exceeded
        if measurement.alert_triggered:
            self._trigger_alerts(measurement)

        return measurement

    def _compute_drift(self) -> DriftMeasurement:
        """Compute drift score from current window."""
        if not self._response_window or self._anchor_embeddings is None:
            return DriftMeasurement(
                drift_score=0.0,
                similarity=1.0,
                window_size=len(self._response_window),
                threshold=self.threshold,
                alert_triggered=False,
                anchor_count=len(self.anchor_phrases)
            )

        # Encode window responses
        window_embeddings = self._model.encode(
            self._response_window,
            convert_to_numpy=True
        )

        # Compute cosine similarity to all anchors
        # Shape: (window_size, anchor_count)
        similarities = self._cosine_similarity_matrix(
            window_embeddings,
            self._anchor_embeddings
        )

        # Max similarity for each response (best matching anchor)
        max_similarities = np.max(similarities, axis=1)

        # Average similarity across window
        avg_similarity = float(np.mean(max_similarities))

        # Drift is inverse of similarity (0 = on-identity, 1 = drifted)
        drift_score = 1.0 - avg_similarity

        # Check threshold
        alert_triggered = drift_score > self.threshold

        return DriftMeasurement(
            drift_score=drift_score,
            similarity=avg_similarity,
            window_size=len(self._response_window),
            threshold=self.threshold,
            alert_triggered=alert_triggered,
            anchor_count=len(self.anchor_phrases)
        )

    def _cosine_similarity_matrix(
        self,
        embeddings1: np.ndarray,
        embeddings2: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity matrix between two embedding sets."""
        # Normalize embeddings
        norm1 = np.linalg.norm(embeddings1, axis=1, keepdims=True)
        norm2 = np.linalg.norm(embeddings2, axis=1, keepdims=True)

        embeddings1_norm = embeddings1 / (norm1 + 1e-8)
        embeddings2_norm = embeddings2 / (norm2 + 1e-8)

        # Compute similarity matrix
        return np.dot(embeddings1_norm, embeddings2_norm.T)

    def _trigger_alerts(self, measurement: DriftMeasurement):
        """Trigger registered alert callbacks."""
        logger.warning(
            f"Drift alert! Score: {measurement.drift_score:.3f} "
            f"(threshold: {measurement.threshold})"
        )
        for callback in self._alert_callbacks:
            try:
                callback(measurement)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def on_drift_alert(self, callback: Callable[[DriftMeasurement], None]):
        """Register a callback for drift alerts.

        Args:
            callback: Function to call when drift exceeds threshold
        """
        self._alert_callbacks.append(callback)

    def get_correction_context(self) -> str:
        """Generate identity re-injection context to reduce drift.

        Returns:
            String containing anchor phrases to re-inject into context
        """
        if not self.anchor_phrases:
            return ""

        context = "Remember your core identity:\n"
        for phrase in self.anchor_phrases[:5]:  # Top 5 anchors
            context += f"- {phrase}\n"

        return context

    def reset_window(self):
        """Clear the response window (e.g., after context re-injection)."""
        self._response_window.clear()
        logger.info("DriftLock window reset")

    def update_anchors(self, new_anchors: List[str]):
        """Update anchor phrases and recompute embeddings.

        Args:
            new_anchors: New list of identity-defining phrases
        """
        self.anchor_phrases = new_anchors
        if self._model is not None:
            self._anchor_embeddings = self._model.encode(
                self.anchor_phrases,
                convert_to_numpy=True
            )
        logger.info(f"Updated anchors: {len(new_anchors)} phrases")

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def benchmark(self, num_responses: int = 100) -> dict:
        """Benchmark embedding computation speed.

        Args:
            num_responses: Number of responses to test

        Returns:
            Dict with timing statistics
       "
        import time

        self._load_model()
        test_responses = [
            f"This is test response number {i} for benchmarking purposes."
            for i in range(num_responses)
        ]

        start = time.time()
        for response in test_responses:
            self.add_response(response)
        elapsed = time.time() - start

        avg_time = (elapsed / num_responses) * 1000  # Convert to ms

        return {
            "total_time_sec": elapsed,
            "avg_time_ms": avg_time,
            "responses": num_responses,
            "meets_benchmark": avg_time < 50  # Target: < 50ms per response
        }