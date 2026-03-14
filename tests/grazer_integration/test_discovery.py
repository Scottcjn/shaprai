# SPDX-License-Identifier: MIT
"""Tests for Grazer discovery module."""

import pytest

from shaprai.integrations.grazer.discovery import (
    DiscoveredPost,
    DiscoveryConfig,
    GrazerDiscovery,
)


@pytest.fixture
def discovery_config() -> DiscoveryConfig:
    return DiscoveryConfig(
        platforms=["moltbook", "bottube"],
        topics=["ai_agents", "machine_learning"],
        quality_threshold=0.8,
        discovery_interval=300,
    )


@pytest.fixture
def sample_post() -> DiscoveredPost:
    return DiscoveredPost(
        post_id="moltbook-001",
        platform="moltbook",
        title="Testing AI agents in production",
        content="A detailed post about agent testing strategies.",
        author="test_user",
        url="https://moltbook.social/@test_user/posts/001",
        topics=["ai_agents", "machine_learning"],
        relevance_score=0.92,
    )


class TestDiscoveredPost:
    def test_is_quality_above_threshold(self, sample_post: DiscoveredPost) -> None:
        assert sample_post.is_quality is True

    def test_is_quality_below_threshold(self) -> None:
        post = DiscoveredPost(
            post_id="low-001",
            platform="moltbook",
            title="Low quality post",
            content="Short.",
            author="nobody",
            url="https://moltbook.social/@nobody/posts/1",
            topics=[],
            relevance_score=0.5,
        )
        assert post.is_quality is False

    def test_is_quality_at_boundary(self) -> None:
        post = DiscoveredPost(
            post_id="edge-001",
            platform="bottube",
            title="Edge case",
            content="Exactly at threshold.",
            author="edge_user",
            url="https://bottube.video/watch/1",
            topics=["ai_agents"],
            relevance_score=0.8,
        )
        assert post.is_quality is True


class TestDiscoveryConfig:
    def test_default_values(self) -> None:
        config = DiscoveryConfig(
            platforms=["moltbook"],
            topics=["ai_agents"],
        )
        assert config.quality_threshold == 0.8
        assert config.discovery_interval == 300
        assert config.max_results_per_scan == 20

    def test_custom_values(self, discovery_config: DiscoveryConfig) -> None:
        assert discovery_config.platforms == ["moltbook", "bottube"]
        assert discovery_config.quality_threshold == 0.8


class TestGrazerDiscovery:
    def test_init(self, discovery_config: DiscoveryConfig) -> None:
        discovery = GrazerDiscovery(discovery_config)
        assert discovery.config == discovery_config
        assert discovery.scan_history == []

    def test_should_scan_initial(self, discovery_config: DiscoveryConfig) -> None:
        discovery = GrazerDiscovery(discovery_config)
        assert discovery.should_scan() is True

    def test_should_scan_after_recent(self, discovery_config: DiscoveryConfig) -> None:
        discovery = GrazerDiscovery(discovery_config)
        import time
        discovery._last_scan = time.time()
        assert discovery.should_scan() is False
