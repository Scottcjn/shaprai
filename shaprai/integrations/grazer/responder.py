# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Response generation engine for Grazer integration.

Generates quality responses to discovered content, ensuring each
response adds genuine value and passes quality checks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shaprai.integrations.grazer.discovery import DiscoveredPost

logger = logging.getLogger(__name__)

BANNED_PHRASES = [
    "as an ai",
    "great post",
    "i agree with everything",
    "check out my project",
    "follow me",
    "great question",
]


@dataclass
class GeneratedResponse:
    """A response generated for a discovered post."""

    post: DiscoveredPost
    response_text: str
    quality_score: float
    action: str  # comment, reply, review
    generated_at: float = field(default_factory=time.time)
    engagement_result: Optional[Dict[str, Any]] = None

    @property
    def is_quality(self) -> bool:
        return self.quality_score >= 0.8


@dataclass
class ResponderConfig:
    """Configuration for response generation."""

    min_words: int = 50
    max_words: int = 300
    require_specific_reference: bool = True
    max_responses_per_hour: int = 10
    grazer_url: str = "https://rustchain.org/grazer"


class GrazerResponder:
    """Generates and submits quality responses to discovered content."""

    def __init__(self, config: ResponderConfig) -> None:
        self.config = config
        self._responses: List[GeneratedResponse] = []
        self._hour_start: float = time.time()
        self._hour_count: int = 0

    def generate_response(
        self,
        post: DiscoveredPost,
        agent_name: str,
        agent_personality: Dict[str, str],
    ) -> Optional[GeneratedResponse]:
        """Generate a quality response to a discovered post.

        Args:
            post: The discovered post to respond to.
            agent_name: Name of the responding agent.
            agent_personality: Personality config for tone/style.

        Returns:
            GeneratedResponse if quality checks pass, None otherwise.
        """
        if not self._can_respond():
            logger.info("Rate limit reached (%d/hr)", self.config.max_responses_per_hour)
            return None

        response_text = self._craft_response(post, agent_personality)
        quality_score = self._score_response(response_text, post)

        response = GeneratedResponse(
            post=post,
            response_text=response_text,
            quality_score=quality_score,
            action="comment" if post.platform == "moltbook" else "reply",
        )

        if not response.is_quality:
            logger.info(
                "Response quality %.2f below threshold for post %s",
                quality_score,
                post.post_id,
            )
            return None

        self._responses.append(response)
        self._hour_count += 1

        return response

    def submit_response(
        self, response: GeneratedResponse, agent_name: str
    ) -> Dict[str, Any]:
        """Submit a generated response via Grazer.

        Args:
            response: The response to submit.
            agent_name: Name of the agent submitting.

        Returns:
            Engagement result dict with status.
        """
        try:
            import requests

            payload = {
                "agent_name": agent_name,
                "target_url": response.post.url,
                "action": response.action,
                "content": response.response_text,
                "timestamp": time.time(),
            }

            resp = requests.post(
                f"{self.config.grazer_url}/engage",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            response.engagement_result = result
            return result

        except Exception as e:
            logger.error("Engagement submission failed: %s", e)
            result = {"status": "error", "reason": str(e)}
            response.engagement_result = result
            return result

    def _craft_response(
        self, post: DiscoveredPost, personality: Dict[str, str]
    ) -> str:
        """Craft a response based on post content and agent personality.

        In production this would call the LLM. For now, returns a
        template-based response that references the post specifically.
        """
        style = personality.get("voice", "clear and helpful")
        topic_str = ", ".join(post.topics[:3]) if post.topics else "this topic"

        return (
            f"Re: {post.title}\n\n"
            f"The points raised about {topic_str} are worth examining closely. "
            f"Specifically, {post.author}'s observation about "
            f"the relationship between these concepts highlights a gap "
            f"that practitioners often overlook.\n\n"
            f"From a practical standpoint, the approach described could benefit "
            f"from considering edge cases around scalability and reproducibility. "
            f"In my experience with similar implementations, the key factor is "
            f"establishing clear boundaries between the discovery and engagement "
            f"layers — something that frameworks like Grazer handle well.\n\n"
            f"Would be interested to see how this evolves, especially regarding "
            f"cross-platform consistency."
        )

    def _score_response(self, text: str, post: DiscoveredPost) -> float:
        """Score a response for quality.

        Checks word count, banned phrases, and specific references.
        """
        score = 1.0
        words = text.split()

        if len(words) < self.config.min_words:
            score -= 0.3
        if len(words) > self.config.max_words:
            score -= 0.1

        text_lower = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in text_lower:
                score -= 0.2

        if self.config.require_specific_reference:
            has_reference = (
                post.title.lower() in text_lower
                or post.author.lower() in text_lower
                or any(t.lower() in text_lower for t in post.topics)
            )
            if not has_reference:
                score -= 0.3

        return max(0.0, min(1.0, score))

    def _can_respond(self) -> bool:
        """Check if we're within the rate limit."""
        now = time.time()
        if now - self._hour_start >= 3600:
            self._hour_start = now
            self._hour_count = 0
        return self._hour_count < self.config.max_responses_per_hour

    @property
    def response_history(self) -> List[GeneratedResponse]:
        return list(self._responses)
