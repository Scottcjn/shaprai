# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Content discovery engine for Grazer integration.

Discovers relevant posts, threads, and discussions across configured
platforms based on topic matching and quality scoring.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPost:
    """A content item discovered by Grazer."""

    post_id: str
    platform: str
    title: str
    content: str
    author: str
    url: str
    topics: List[str]
    relevance_score: float
    discovered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_quality(self) -> bool:
        """Check if this post meets the quality threshold."""
        return self.relevance_score >= 0.8


@dataclass
class DiscoveryConfig:
    """Configuration for content discovery."""

    platforms: List[str]
    topics: List[str]
    quality_threshold: float = 0.8
    discovery_interval: int = 300
    max_results_per_scan: int = 20
    grazer_url: str = "https://rustchain.org/grazer"


class GrazerDiscovery:
    """Discovers content across platforms using Grazer.

    Handles platform-specific content fetching, topic matching,
    and relevance scoring.
    """

    def __init__(self, config: DiscoveryConfig) -> None:
        self.config = config
        self._last_scan: float = 0.0
        self._discovered: List[DiscoveredPost] = []

    def discover(self, agent_name: str) -> List[DiscoveredPost]:
        """Run a discovery scan across all configured platforms.

        Args:
            agent_name: The agent performing discovery.

        Returns:
            List of discovered posts above the quality threshold.
        """
        all_posts: List[DiscoveredPost] = []

        for platform in self.config.platforms:
            try:
                posts = self._discover_platform(agent_name, platform)
                all_posts.extend(posts)
            except Exception as e:
                logger.error("Discovery failed on %s: %s", platform, e)

        quality_posts = [
            p for p in all_posts
            if p.relevance_score >= self.config.quality_threshold
        ]

        self._last_scan = time.time()
        self._discovered.extend(quality_posts)

        logger.info(
            "Discovery scan complete: %d found, %d above threshold (%.1f)",
            len(all_posts),
            len(quality_posts),
            self.config.quality_threshold,
        )

        return quality_posts

    def _discover_platform(
        self, agent_name: str, platform: str
    ) -> List[DiscoveredPost]:
        """Discover content on a specific platform.

        Args:
            agent_name: The agent performing discovery.
            platform: Platform identifier (moltbook, bottube, github).

        Returns:
            List of discovered posts from the platform.
        """
        try:
            import requests

            payload = {
                "agent_name": agent_name,
                "platform": platform,
                "topics": self.config.topics,
                "max_results": self.config.max_results_per_scan,
                "timestamp": time.time(),
            }

            response = requests.post(
                f"{self.config.grazer_url}/discover",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            items = response.json().get("items", [])

            return [
                DiscoveredPost(
                    post_id=item["id"],
                    platform=platform,
                    title=item["title"],
                    content=item["content"],
                    author=item["author"],
                    url=item["url"],
                    topics=item.get("topics", []),
                    relevance_score=item.get("relevance_score", 0.0),
                    metadata=item.get("metadata", {}),
                )
                for item in items
            ]

        except ImportError:
            logger.warning("requests not installed — discovery skipped")
            return []
        except Exception as e:
            logger.error("Platform %s discovery error: %s", platform, e)
            return []

    @property
    def scan_history(self) -> List[DiscoveredPost]:
        """Return all posts discovered across all scans."""
        return list(self._discovered)

    def should_scan(self) -> bool:
        """Check if enough time has passed for a new scan."""
        return (time.time() - self._last_scan) >= self.config.discovery_interval
