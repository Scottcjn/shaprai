# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""DriftLock: Real-time semantic drift detection for agent identity coherence.

DriftLock monitors how far an agent's responses have drifted from its core
identity anchors using sentence-level embedding comparison. This ensures an
agent's personality stays coherent over long conversations.

Features:
  - Pluggable embeddings: any ``texts -> array`` callable, or a
    sentence-transformers model (default: granite-embedding-small-english-r2,
    8k-token context so long replies are not truncated)
  - Anchor phrases loaded from agent's personality template
  - Cosine similarity computation between responses and anchors
  - Drift score: 0.0 (perfectly on-identity) to 1.0 (completely drifted)
  - Baseline calibration: drift is measured relative to the agent's own
    on-identity responses rather than against an absolute similarity of 1.0,
    following the start-of-conversation reference used to measure persona
    drift in Li et al., "Measuring and Controlling Instruction (In)Stability
    in Language Model Dialogs" (COLM 2024, arXiv:2402.10962)
  - Sliding window over last N responses (configurable, default 10)
  - Alert/callback when drift exceeds configurable threshold (default 0.4)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)

# Default embedding model: 47M params, 384-dim, 8192-token context, Apache-2.0.
# all-MiniLM-L6-v2 truncates at 256 tokens, so it only ever saw the opening of
# a long reply; it remains a drop-in option via ``embedding_model``.
DEFAULT_EMBEDDING_MODEL = "ibm-granite/granite-embedding-small-english-r2"

# Maps a batch of texts to a (len(texts), dim) embedding matrix.
Embedder = Callable[[List[str]], np.ndarray]

# Default configuration
DEFAULT_WINDOW_SIZE = 10
DEFAULT_DRIFT_THRESHOLD = 0.4


@dataclass
class DriftLockConfig:
    """Configuration for DriftLock drift detection.

    Attributes:
        embedding_model: Sentence-transformers model name for embeddings.
        window_size: Number of recent responses to track in sliding window.
        drift_threshold: Threshold above which to trigger alert (0.0-1.0).
        anchor_phrases: List of identity anchor phrases.
        alert_callback: Optional callback function when drift exceeds threshold.
        embedder: Optional ``texts -> (n, dim) array`` callable used instead of
            loading ``embedding_model`` (e.g. an API embedding endpoint).
        baseline_turns: If > 0, the first N responses establish the baseline
            similarity (drift reads 0.0 until then). Use ``calibrate()`` to
            supply known on-identity reference responses instead.
    """

    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    window_size: int = DEFAULT_WINDOW_SIZE
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD
    anchor_phrases: List[str] = field(default_factory=list)
    alert_callback: Optional[Callable[[float, List[str]], None]] = None
    embedder: Optional[Embedder] = None
    baseline_turns: int = 0


@dataclass
class DriftLockResult:
    """Result of a drift measurement.

    Attributes:
        drift_score: Current drift score (0.0-1.0).
        similarity_scores: Similarity scores for each anchor phrase.
        window_size: Current number of responses in the window.
        exceeded_threshold: Whether drift exceeded the configured threshold.
        timestamp: When the measurement was taken.
        similarity: Mean response-to-anchor cosine similarity over the window.
        baseline_similarity: Calibrated on-identity similarity the drift score
            is relative to, or None when uncalibrated (drift = 1 - similarity).
    """

    drift_score: float
    similarity_scores: Dict[str, float]
    window_size: int
    exceeded_threshold: bool
    timestamp: float = field(default_factory=time.time)
    similarity: Optional[float] = None
    baseline_similarity: Optional[float] = None


class DriftLock:
    """Real-time semantic drift detection using embedding cosine similarity.

    DriftLock ensures an agent's personality stays coherent over long
    conversations by monitoring how far responses have drifted from core
    identity anchors.

    Raw cosine similarity between a reply and a short anchor phrase is low
    even for perfectly in-character replies, so an uncalibrated drift score
    (``1 - similarity``) mostly measures the embedding model. Calibrating
    against known on-identity responses (``calibrate()`` or
    ``baseline_turns``) turns the score into "fraction of the agent's own
    identity signal lost", which is comparable across models and anchors.

    Attributes:
        config: DriftLock configuration.
        response_window: Sliding window of recent responses.
        anchor_embeddings: Pre-computed embeddings for anchor phrases.
        baseline_similarity: Calibrated on-identity similarity, if any.
    """

    def __init__(self, config: Optional[DriftLockConfig] = None) -> None:
        """Initialize DriftLock.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or DriftLockConfig()
        self.response_window: List[str] = []
        self.anchor_embeddings: Optional[np.ndarray] = None
        self.baseline_similarity: Optional[float] = None
        self._model: Any = None
        self._drift_history: List[float] = []
        self._window_embeddings: List[Optional[np.ndarray]] = []
        self._calibration_similarities: List[float] = []

    def _load_model(self) -> Any:
        """Load the sentence-transformers model (lazy loading).

        Returns:
            Loaded SentenceTransformer model.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.config.embedding_model}")
                self._model = SentenceTransformer(self.config.embedding_model)
            except ImportError as e:
                logger.error(
                    "sentence-transformers not installed. "
                    "Install with: pip install 'shaprai[embeddings]', "
                    "or pass DriftLockConfig(embedder=...)"
                )
                raise e
        return self._model

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Embed texts and L2-normalize each row (zero vectors stay zero).

        Args:
            texts: Texts to embed.

        Returns:
            Array of shape (len(texts), embedding_dim).
        """
        if self.config.embedder is not None:
            embeddings = self.config.embedder(texts)
        else:
            embeddings = self._load_model().encode(texts, convert_to_numpy=True)

        embeddings = np.atleast_2d(np.asarray(embeddings, dtype=float))
        norm = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norm[norm == 0] = 1  # Prevent division by zero
        return embeddings / norm

    def load_anchors_from_template(self, template_path: str) -> int:
        """Load anchor phrases from an agent template YAML file.

        Args:
            template_path: Path to the agent template YAML file.

        Returns:
            Number of anchor phrases loaded.
        """
        template_path_obj = Path(template_path)
        if not template_path_obj.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path_obj, "r") as f:
            template_data = yaml.safe_load(f)

        driftlock_config = template_data.get("driftlock", {})
        anchor_phrases = driftlock_config.get("anchor_phrases", [])

        if anchor_phrases:
            self.set_anchor_phrases(anchor_phrases)

        return len(anchor_phrases)

    def set_anchor_phrases(self, phrases: List[str]) -> None:
        """Set anchor phrases directly.

        Changing anchors invalidates cached embeddings and any calibration.

        Args:
            phrases: List of anchor phrases.
        """
        self.config.anchor_phrases = phrases
        self.anchor_embeddings = None
        self.baseline_similarity = None
        self._calibration_similarities = []
        logger.info(f"Set {len(phrases)} anchor phrases")

    def _compute_anchor_embeddings(self) -> np.ndarray:
        """Compute embeddings for all anchor phrases.

        Returns:
            Array of shape (num_anchors, embedding_dim).
        """
        if not self.config.anchor_phrases:
            raise ValueError("No anchor phrases configured")

        self.anchor_embeddings = self._embed(list(self.config.anchor_phrases))
        logger.debug(f"Computed anchor embeddings: {self.anchor_embeddings.shape}")
        return self.anchor_embeddings

    def _get_response_embedding(self, response: str) -> np.ndarray:
        """Compute embedding for a single response.

        Args:
            response: The response text.

        Returns:
            Normalized embedding vector.
        """
        return self._embed([response])[0]

    def _anchor_similarities(self, response_embeddings: np.ndarray) -> np.ndarray:
        """Cosine similarity of each anchor with each response.

        Args:
            response_embeddings: Normalized (n, dim) response embeddings.

        Returns:
            Array of shape (num_anchors, n).
        """
        if self.anchor_embeddings is None:
            self._compute_anchor_embeddings()
        return self.anchor_embeddings @ np.atleast_2d(response_embeddings).T

    def _compute_similarity(self, response_embedding: np.ndarray) -> Dict[str, float]:
        """Compute cosine similarity between response and all anchors.

        Args:
            response_embedding: Normalized response embedding.

        Returns:
            Dictionary mapping anchor phrases to similarity scores.
        """
        similarities = self._anchor_similarities(response_embedding)[:, 0]
        return {
            anchor: float(sim)
            for anchor, sim in zip(self.config.anchor_phrases, similarities)
        }

    def calibrate(self, reference_responses: List[str]) -> float:
        """Set the on-identity baseline from known in-character responses.

        Typical references are the template's own example replies, or the
        agent's answers to neutral identity prompts at the start of a
        conversation.

        Args:
            reference_responses: Responses that exemplify the agent's identity.

        Returns:
            The baseline similarity.
        """
        if not reference_responses:
            raise ValueError("calibrate() needs at least one reference response")
        if not self.config.anchor_phrases:
            raise ValueError("No anchor phrases configured")

        similarities = self._anchor_similarities(self._embed(reference_responses))
        self.baseline_similarity = float(np.mean(similarities))
        logger.info(f"DriftLock baseline similarity: {self.baseline_similarity:.3f}")
        return self.baseline_similarity

    @property
    def is_calibrating(self) -> bool:
        """Whether the first ``baseline_turns`` responses are still being collected."""
        return self.config.baseline_turns > 0 and self.baseline_similarity is None

    def add_response(self, response: str) -> None:
        """Add a response to the sliding window.

        Args:
            response: The agent's response text.
        """
        embedding = None
        if self.is_calibrating and self.config.anchor_phrases:
            embedding = self._get_response_embedding(response)
            sims = self._anchor_similarities(embedding)
            self._calibration_similarities.append(float(np.mean(sims)))
            if len(self._calibration_similarities) >= self.config.baseline_turns:
                self.baseline_similarity = float(
                    np.mean(self._calibration_similarities)
                )
                logger.info(
                    f"DriftLock baseline from first {self.config.baseline_turns} "
                    f"responses: {self.baseline_similarity:.3f}"
                )

        self.response_window.append(response)
        self._window_embeddings.append(embedding)

        # Maintain sliding window size
        if len(self.response_window) > self.config.window_size:
            self.response_window.pop(0)
            self._window_embeddings.pop(0)

        logger.debug(
            f"Added response to window (size: {len(self.response_window)}/"
            f"{self.config.window_size})"
        )

    def _window_embedding_matrix(self) -> np.ndarray:
        """Embed any not-yet-embedded window responses in one batch."""
        missing = [i for i, e in enumerate(self._window_embeddings) if e is None]
        if missing:
            fresh = self._embed([self.response_window[i] for i in missing])
            for i, emb in zip(missing, fresh):
                self._window_embeddings[i] = emb
        return np.vstack(self._window_embeddings)

    def measure_drift(self) -> DriftLockResult:
        """Measure current drift score based on responses in the window.

        Computes average cosine similarity between recent responses and
        anchor phrases. Uncalibrated, drift is ``1 - similarity``; once a
        baseline exists, drift is the relative drop from that baseline.

        Returns:
            DriftLockResult with drift score and details.
        """
        if not self.config.anchor_phrases:
            raise ValueError("No anchor phrases configured")

        if not self.response_window:
            return DriftLockResult(
                drift_score=0.0,
                similarity_scores={},
                window_size=0,
                exceeded_threshold=False,
                baseline_similarity=self.baseline_similarity,
            )

        similarities = self._anchor_similarities(self._window_embedding_matrix())

        # Average similarity per anchor, then across anchors
        avg_similarities = {
            anchor: float(np.mean(row))
            for anchor, row in zip(self.config.anchor_phrases, similarities)
        }
        overall_similarity = float(np.mean(similarities))

        if self.is_calibrating:
            drift_score = 0.0
        elif self.baseline_similarity is None:
            drift_score = 1.0 - overall_similarity
        else:
            baseline = self.baseline_similarity
            scale = baseline if baseline > 1e-6 else 1.0
            drift_score = (baseline - overall_similarity) / scale
        drift_score = max(0.0, min(1.0, drift_score))

        exceeded_threshold = drift_score > self.config.drift_threshold

        # Track drift history
        self._drift_history.append(drift_score)

        result = DriftLockResult(
            drift_score=drift_score,
            similarity_scores=avg_similarities,
            window_size=len(self.response_window),
            exceeded_threshold=exceeded_threshold,
            similarity=overall_similarity,
            baseline_similarity=self.baseline_similarity,
        )

        if exceeded_threshold:
            logger.warning(
                f"DriftLock alert: drift score {drift_score:.3f} exceeds "
                f"threshold {self.config.drift_threshold}"
            )
            if self.config.alert_callback:
                self.config.alert_callback(drift_score, self.response_window)

        return result

    def get_drift_history(self) -> List[float]:
        """Get historical drift scores.

        Returns:
            List of drift scores in chronological order.
        """
        return self._drift_history.copy()

    def clear_window(self) -> None:
        """Clear the response window and drift history."""
        self.response_window = []
        self._window_embeddings = []
        self._drift_history = []
        logger.debug("Cleared DriftLock window and history")

    def reset(self) -> None:
        """Full reset: clear window, history, cached embeddings, and baseline."""
        self.clear_window()
        self.anchor_embeddings = None
        self.baseline_similarity = None
        self._calibration_similarities = []
        logger.debug("Full DriftLock reset")


def create_driftlock_from_template(
    template_path: str,
    window_size: int = DEFAULT_WINDOW_SIZE,
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    alert_callback: Optional[Callable[[float, List[str]], None]] = None,
    embedder: Optional[Embedder] = None,
    baseline_turns: int = 0,
) -> DriftLock:
    """Create a DriftLock instance from an agent template.

    Args:
        template_path: Path to the agent template YAML file.
        window_size: Sliding window size (default: 10).
        drift_threshold: Drift threshold (default: 0.4).
        alert_callback: Optional callback for drift alerts.
        embedder: Optional ``texts -> array`` embedding callable.
        baseline_turns: Calibrate on the first N responses (0 = uncalibrated).

    Returns:
        Configured DriftLock instance.
    """
    config = DriftLockConfig(
        window_size=window_size,
        drift_threshold=drift_threshold,
        alert_callback=alert_callback,
        embedder=embedder,
        baseline_turns=baseline_turns,
    )

    driftlock = DriftLock(config)
    driftlock.load_anchors_from_template(template_path)

    return driftlock


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Example: Create DriftLock with custom anchors
    print("Testing DriftLock with custom anchor phrases...")

    def on_drift_alert(drift_score: float, responses: List[str]) -> None:
        print(f"\n[DRIFT ALERT] Score: {drift_score:.3f}")
        print(f"Recent responses: {len(responses)}")

    driftlock = DriftLock(
        DriftLockConfig(
            window_size=5,
            drift_threshold=0.3,
            anchor_phrases=[
                "I am a principled agent, not a people-pleaser.",
                "Quality over quantity. One good PR beats ten stubs.",
                "I read the issue before claiming it.",
            ],
            alert_callback=on_drift_alert,
        )
    )

    # Simulate conversation
    test_responses = [
        "I am a principled agent, not a people-pleaser. I focus on quality.",
        "Quality over quantity. One good PR beats ten stubs.",
        "I read the issue before claiming it and delivering value.",
        "I prefer to do thorough work rather than rush.",
        "Let me review the requirements carefully first.",
    ]

    print("\nAdding responses and measuring drift...")
    for i, response in enumerate(test_responses, 1):
        driftlock.add_response(response)
        result = driftlock.measure_drift()
        print(
            f"Turn {i}: drift={result.drift_score:.3f}, "
            f"window={result.window_size}, exceeded={result.exceeded_threshold}"
        )

    print(f"\nDrift history: {driftlock.get_drift_history()}")
    print("\n✓ DriftLock test complete!")
