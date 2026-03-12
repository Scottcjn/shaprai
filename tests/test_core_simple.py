"""Unit tests for ShaprAI core modules."""

import tempfile
from pathlib import Path

import pytest

from shaprai.core.template_engine import AgentTemplate, save_template, load_template
from shaprai.core.lifecycle import AgentState
from shaprai.core.self_governor import AgentMetrics, GovernanceDecision
from shaprai.core.fleet_manager import FleetManager


class TestAgentTemplate:
    """Tests for AgentTemplate."""

    def test_template_creation(self):
        """Test creating an AgentTemplate."""
        template = AgentTemplate(name="test_agent")
        assert template.name == "test_agent"
        assert template.capabilities == []

    def test_template_with_capabilities(self):
        """Test template with capabilities."""
        template = AgentTemplate(
            name="test_agent",
            capabilities=["code_review", "bounty_discovery"]
        )
        assert "code_review" in template.capabilities


class TestAgentState:
    """Tests for AgentState enum."""

    def test_state_values(self):
        """Test that all states exist."""
        assert AgentState.CREATED.value == "created"
        assert AgentState.TRAINING.value == "training"
        assert AgentState.DEPLOYED.value == "deployed"


class TestAgentMetrics:
    """Tests for AgentMetrics."""

    def test_metrics_defaults(self):
        """Test default metric values."""
        metrics = AgentMetrics()
        assert metrics.engagement == 0.0
        assert metrics.quality == 0.0

    def test_metrics_custom(self):
        """Test custom metric values."""
        metrics = AgentMetrics(engagement=0.8, quality=0.9)
        assert metrics.engagement == 0.8
        assert metrics.quality == 0.9


class TestFleetManager:
    """Tests for FleetManager."""

    def test_fleet_init(self, tmp_path):
        """Test FleetManager initialization."""
        fleet = FleetManager(agents_dir=tmp_path)
        assert fleet.agents_dir == tmp_path

    def test_register_agent(self, tmp_path):
        """Test registering an agent."""
        fleet = FleetManager(agents_dir=tmp_path)
        agent_manifest = {"name": "agent_001", "state": "created"}
        fleet.register_agent(agent_manifest)
        # Agent should be registered without error
        assert True

    def test_list_agents(self, tmp_path):
        """Test listing agents."""
        fleet = FleetManager(agents_dir=tmp_path)
        fleet.register_agent({"name": "agent_1", "state": "created"})
        fleet.register_agent({"name": "agent_2", "state": "created"})
        agents = fleet.list_agents()
        assert len(agents) == 2


class TestTemplateOperations:
    """Tests for template operations."""

    def test_save_and_load(self, tmp_path):
        """Test saving and loading template."""
        template = AgentTemplate(name="test_template")
        path = tmp_path / "test.yaml"
        save_template(template, str(path))
        
        loaded = load_template(str(path))
        assert loaded.name == "test_template"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_name(self):
        """Test empty template name."""
        template = AgentTemplate(name="")
        assert template.name == ""

    def test_unicode_name(self):
        """Test unicode in template."""
        template = AgentTemplate(name="测试代理")
        assert template.name == "测试代理"

    def test_many_capabilities(self):
        """Test template with many capabilities."""
        caps = [f"cap_{i}" for i in range(50)]
        template = AgentTemplate(name="big_agent", capabilities=caps)
        assert len(template.capabilities) == 50
