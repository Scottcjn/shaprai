# SPDX-License-Identifier: MIT
"""Tests for GrazerAgent orchestrator."""

import pytest
import yaml
from pathlib import Path

from shaprai.integrations.grazer.agent import GrazerAgent, GrazerAgentConfig


@pytest.fixture
def agent_config() -> GrazerAgentConfig:
    return GrazerAgentConfig(
        agent_name="test_grazer",
        platforms=["moltbook", "bottube"],
        topics=["ai_agents", "machine_learning"],
        quality_threshold=0.8,
    )


@pytest.fixture
def agent(agent_config: GrazerAgentConfig) -> GrazerAgent:
    return GrazerAgent(agent_config)


class TestGrazerAgentConfig:
    def test_defaults(self) -> None:
        config = GrazerAgentConfig(
            agent_name="test",
            platforms=["moltbook"],
            topics=["ai_agents"],
        )
        assert config.quality_threshold == 0.8
        assert config.discovery_interval == 300
        assert config.max_responses_per_hour == 10
        assert config.min_words == 50
        assert config.max_words == 300

    def test_from_template(self) -> None:
        template_data = {
            "name": "grazer_discoverer",
            "personality": {"style": "analytical_helpful"},
            "grazer": {
                "platforms": ["moltbook", "bottube"],
                "topics": ["ai_agents"],
                "quality_threshold": 0.85,
                "discovery_interval": 600,
                "max_responses_per_hour": 5,
                "response_rules": {
                    "min_words": 100,
                    "max_words": 250,
                },
            },
        }
        config = GrazerAgentConfig.from_template(template_data)
        assert config.agent_name == "grazer_discoverer"
        assert config.platforms == ["moltbook", "bottube"]
        assert config.quality_threshold == 0.85
        assert config.discovery_interval == 600
        assert config.max_responses_per_hour == 5
        assert config.min_words == 100
        assert config.max_words == 250

    def test_from_template_file(self) -> None:
        template_path = (
            Path(__file__).resolve().parent.parent.parent
            / "templates"
            / "grazer_discoverer.yaml"
        )
        if not template_path.exists():
            pytest.skip("Template file not found")

        with open(template_path) as f:
            data = yaml.safe_load(f)

        config = GrazerAgentConfig.from_template(data)
        assert config.agent_name == "grazer_discoverer"
        assert "moltbook" in config.platforms
        assert "bottube" in config.platforms
        assert config.quality_threshold == 0.8


class TestGrazerAgent:
    def test_init(self, agent: GrazerAgent) -> None:
        assert agent.config.agent_name == "test_grazer"
        assert agent.discovery is not None
        assert agent.responder is not None

    def test_stats_initial(self, agent: GrazerAgent) -> None:
        stats = agent.stats
        assert stats["agent_name"] == "test_grazer"
        assert stats["cycles_run"] == 0
        assert stats["total_discovered"] == 0
        assert stats["total_responses"] == 0
        assert stats["platforms"] == ["moltbook", "bottube"]
        assert stats["quality_threshold"] == 0.8
