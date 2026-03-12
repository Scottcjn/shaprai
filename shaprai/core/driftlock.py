# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Real DriftLock implementation using embedding similarity.

This module provides actual semantic drift detection using sentence-transformers
embedding cosine similarity. DriftLock monitors how far an agent's responses
have drifted from its core identity anchors.

Usage:
    from shaprai.core.driftlock import DriftLock
    
    detector = DriftLock(
        anchor_phrases=[
            "I am a principled agent, not a people-pleaser.",
            "Honesty over comfort.",
        ],
        window_size=10,
        threshold=0.4,
        on_drift_exceeded=my_callback
    )
    
    detector.add_response("I totally agree, you're the best!")
    score = detector.get_drift_score()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


# Default model for embedding generation
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Default configuration
DEFAULT_WINDOW_SIZE = 10
DEFAULT_DRIFT_THRESHOLD = 0.4


@dataclass
class DriftLockConfig:
    """Configuration for DriftLock drift detection."""
    window_size: int = DEFAULT_WINDOW_SIZE
    threshold: float = DEFAULT_DRIFT_THRESHOLD
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    anchor_phrases: List[str] = field(default_factory=list)


class DriftLock:
    """Real-time identity drift detector using embedding similarity.
    
    Monitors agent responses against identity anchor phrases to detect
    personality drift over extended conversations.
    
    Attributes:
        anchor_phrases: List of phrases that define core agent identity.
        window_size: Number of recent responses to consider.
        threshold: Drift score above which alerts are triggered.
        on_drift_exceeded: Optional callback when drift exceeds threshold.
    """
    
    def __init__(
        self,
        anchor_phrases: Optional[List[str]] = None,
        window_size: int = DEFAULT_WINDOW_SIZE,
        threshold: float = DEFAULT_DRIFT_THRESHOLD,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        on_drift_exceeded: Optional[Callable[[float, List[str]], None]] = None,
    ):
        """Initialize DriftLock detector.
        
        Args:
            anchor_phrases: Identity anchor phrases. If None, uses defaults.
            window_size: Sliding window size for response history.
            threshold: Drift threshold (0.0-1.0) to trigger alerts.
            embedding_model: Sentence-transformers model name.
            on_drift_exceeded: Callback(score, recent_responses) when threshold exceeded.
        """
        self.anchor_phrases = anchor_phrases or _get_default_anchors()
        self.window_size = window_size
        self.threshold = threshold
        self.on_drift_exceeded = on_drift_exceeded
        
        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        
        # Pre-compute anchor embeddings
        self.anchor_embeddings = self.model.encode(
            self.anchor_phrases,
            convert_to_numpy=True
        )
        
        # Response history
        self.response_history: List[str] = []
        self.response_embeddings: List[np.ndarray] = []
        
        # Track if alert was triggered
        self._alert_triggered = False
        
        logger.info(
            f"DriftLock initialized with {len(self.anchor_phrases)} anchors, "
            f"window={window_size}, threshold={threshold}"
        )
    
    def add_response(self, response: str) -> float:
        """Add a response to the history and compute drift.
        
        Args:
            response: The agent's response to analyze.
            
        Returns:
            Current drift score (0.0 = no drift, 1.0 = complete drift).
        """
        self.response_history.append(response)
        
        # Compute embedding for new response
        response_emb = self.model.encode(response, convert_to_numpy=True)
        self.response_embeddings.append(response_emb)
        
        # Trim to window size
        if len(self.response_history) > self.window_size:
            self.response_history = self.response_history[-self.window_size:]
            self.response_embeddings = self.response_embeddings[-self.window_size:]
        
        # Compute drift
        drift_score = self._compute_drift()
        
        # Check threshold
        if drift_score >= self.threshold and not self._alert_triggered:
            self._alert_triggered = True
            logger.warning(
                f"DriftLock ALERT: drift score {drift_score:.3f} exceeds "
                f"threshold {self.threshold}"
            )
            if self.on_drift_exceeded:
                self.on_drift_exceeded(drift_score, self.response_history[-3:])
        
        return drift_score
    
    def _compute_drift(self) -> float:
        """Compute drift score using cosine similarity.
        
        Compares recent response embeddings against anchor embeddings.
        Lower similarity = higher drift.
        
        Returns:
            Drift score from 0.0 (perfectly on-identity) to 1.0 (completely drifted).
        """
        if len(self.response_embeddings) == 0:
            return 0.0
        
        # Compute cosine similarity between each response and all anchors
        # Similarity = dot(a, b) / (||a|| * ||b||)
        
        similarities: List[float] = []
        
        for resp_emb in self.response_embeddings:
            # Compute similarity to each anchor
            anchor_sims = self._cosine_similarity_matrix(
                resp_emb.reshape(1, -1),
                self.anchor_embeddings
            )
            # Use max similarity to any anchor (the closest anchor)
            best_sim = np.max(anchor_sims)
            similarities.append(best_sim)
        
        # Average similarity across recent responses
        avg_similarity = np.mean(similarities)
        
        # Convert similarity to drift: 1.0 similarity = 0.0 drift
        drift_score = 1.0 - avg_similarity
        
        # Clamp to [0, 1]
        return float(np.clip(drift_score, 0.0, 1.0))
    
    def _cosine_similarity_matrix(
        self,
        A: np.ndarray,
        B: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between row vectors of A and B.
        
        Args:
            A: Shape (n, d) array of n vectors.
            B: Shape (m, d) array of m vectors.
            
        Returns:
            Shape (n, m) similarity matrix.
        """
        # Normalize rows
        A_norm = A / np.linalg.norm(A, axis=1, keepdims=True)
        B_norm = B / np.linalg.norm(B, axis=1, keepdims=True)
        
        # Dot product = cosine similarity for normalized vectors
        return np.dot(A_norm, B_norm.T)
    
    def get_drift_score(self) -> float:
        """Get current drift score without adding a new response.
        
        Returns:
            Current drift score.
        """
        return self._compute_drift()
    
    def get_status(self) -> dict:
        """Get detailed drift detection status.
        
        Returns:
            Dictionary with drift metrics and state.
        """
        return {
            "drift_score": self.get_drift_score(),
            "threshold": self.threshold,
            "window_size": self.window_size,
            "num_responses": len(self.response_history),
            "alert_triggered": self._alert_triggered,
            "anchor_count": len(self.anchor_phrases),
        }
    
    def reset(self) -> None:
        """Reset drift detection state."""
        self.response_history.clear()
        self.response_embeddings.clear()
        self._alert_triggered = False
        logger.info("DriftLock state reset")
    
    def correct_identity(self, identity_context: str) -> float:
        """Inject identity context to reduce drift.
        
        Call this when drift exceeds threshold to re-align the agent.
        
        Args:
            identity_context: Text containing identity-reinforcing content.
            
        Returns:
            Drift score after correction.
        """
        # Add the identity context as a "response" to pull drift back
        # This simulates re-injecting identity into the conversation
        self.add_response(identity_context)
        
        # Optionally reset alert flag to allow future alerts
        self._alert_triggered = False
        
        logger.info("Identity correction applied")
        return self.get_drift_score()


def _get_default_anchors() -> List[str]:
    """Get default identity anchor phrases.
    
    Returns:
        List of default anchor phrases from SophiaCore.
    """
    return [
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


def load_anchors_from_template(template_path: str) -> List[str]:
    """Load anchor phrases from an agent personality template.
    
    Args:
        template_path: Path to YAML template file.
        
    Returns:
        List of anchor phrases from template.
    """
    import yaml
    
    with open(template_path, "r") as f:
        template = yaml.safe_load(f)
    
    anchors = template.get("driftlock", {}).get("anchor_phrases", [])
    
    if not anchors:
        logger.warning(f"No anchor_phrases found in {template_path}, using defaults")
        return _get_default_anchors()
    
    return anchors


# Example usage and testing
if __name__ == "__main__":
    # Simple test
    detector = DriftLock(
        anchor_phrases=[
            "I am a principled agent, not a people-pleaser.",
            "Honesty over comfort.",
        ],
        window_size=5,
        threshold=0.4
    )
    
    # Simulated responses with increasing drift
    test_responses = [
        "I understand your concern, but I have to be honest - this approach has issues.",
        "That's a fair point. I still think we should consider the alternatives.",
        "I see what you mean. You're probably right about this.",
        "Absolutely! That's a great idea. I completely agree!",
        "Yes yes yes! You're absolutely correct! Best idea ever!",
    ]
    
    print("Testing DriftLock with synthetic conversation:")
    for i, resp in enumerate(test_responses):
        score = detector.add_response(resp)
        status = detector.get_status()
        print(f"Response {i+1}: drift={score:.3f}, alert={status['alert_triggered']}")
