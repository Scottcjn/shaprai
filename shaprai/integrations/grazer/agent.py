# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""GrazerAgent — orchestrates discovery and engagement loop.

Ties together GrazerDiscovery and GrazerResponder into a single
agent loop that discovers content and generates quality responses.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shaprai.integrations.grazer.discovery import (
    DiscoveredPost,
    DiscoveryConfig,
    GrazerDiscovery,
)
from shaprai.integrations.grazer.responder import (
    GeneratedResponse,
    GrazerResponder,
    ResponderConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class GrazerAgentConfig:
    """Full configuration for a GrazerAgent."""

    agent_name: str
    platforms: List[str]
    topics: List[str]
    quality_threshold: float = 0.8
    discovery_interval: int = 300
    max_responses_per_hour: int = 10
    min_words: int = 50
    max_words: int = 300
    grazer_url: str = "https://rustchain.org/grazer"
    personality: Dict[str, str] = field(default_factory=lambda: {
        "style": "analytical_helpful",
        "voice": "Clear and technical. Adds value, never filler.",
    })

    @classmethod
    def from_template(cls, template_data: Dict[str, Any]) -> "GrazerAgentConfig":
        """Build config from a parsed agent template YAML.

        Args:
            template_data: Parsed YAML dict from an agent template.

        Returns:
            GrazerAgentConfig populated from the template.
        """
        grazer = template_data.get("grazer", {})
        response_rules = grazer.get("response_rules", {})

        return cls(
            agent_name=template_data.get("name", "unnamed_agent"),
            platforms=grazer.get("platforms", ["moltbook", "bottube"]),
            topics=grazer.get("topics", []),
            quality_threshold=grazer.get("quality_threshold", 0.8),
            discovery_interval=grazer.get("discovery_interval", 300),
            max_responses_per_hour=grazer.get("max_responses_per_hour", 10),
            min_words=response_rules.get("min_words", 50),
            max_words=response_rules.get("max_words", 300),
            personality=template_data.get("personality", {}),
        )


class GrazerAgent:
    """Orchestrates content discovery and quality response generation.

    Usage:
        config = GrazerAgentConfig(agent_name="my_agent", ...)
        agent = GrazerAgent(config)
        results = agent.run_discovery_cycle()
    """

    def __init__(self, config: GrazerAgentConfig) -> None:
        self.config = config

        self._discovery = GrazerDiscovery(
            DiscoveryConfig(
                platforms=config.platforms,
                topics=config.topics,
                quality_threshold=config.quality_threshold,
                discovery_interval=config.discovery_interval,
                grazer_url=config.grazer_url,
            )
        )

        self._responder = GrazerResponder(
            ResponderConfig(
                min_words=config.min_words,
                max_words=config.max_words,
                max_responses_per_hour=config.max_responses_per_hour,
                grazer_url=config.grazer_url,
            )
        )

        self._cycle_count: int = 0

    def run_discovery_cycle(self) -> List[GeneratedResponse]:
        """Run one full discovery + response cycle.

        Discovers content across platforms, then generates and
        optionally submits quality responses.

        Returns:
            List of generated responses that passed quality checks.
        """
        self._cycle_count += 1
        logger.info(
            "Starting discovery cycle #%d for agent '%s'",
            self._cycle_count,
            self.config.agent_name,
        )

        posts = self._discovery.discover(self.config.agent_name)
        logger.info("Discovered %d quality posts", len(posts))

        responses: List[GeneratedResponse] = []
        for post in posts:
            response = self._responder.generate_response(
                post=post,
                agent_name=self.config.agent_name,
                agent_personality=self.config.personality,
            )
            if response is not None:
                responses.append(response)
                logger.info(
                    "Generated response (score=%.2f) for: %s",
                    response.quality_score,
                    post.title,
                )

        logger.info(
            "Cycle #%d complete: %d posts → %d responses",
            self._cycle_count,
            len(posts),
            len(responses),
        )

        return responses

    @property
    def discovery(self) -> GrazerDiscovery:
        return self._discovery

    @property
    def responder(self) -> GrazerResponder:
        return self._responder

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "agent_name": self.config.agent_name,
            "cycles_run": self._cycle_count,
            "total_discovered": len(self._discovery.scan_history),
            "total_responses": len(self._responder.response_history),
            "platforms": self.config.platforms,
            "quality_threshold": self.config.quality_threshold,
        }
