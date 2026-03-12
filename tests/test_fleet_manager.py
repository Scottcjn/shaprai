# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for the fleet management module."""

import pytest
import yaml
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from shaprai.core.fleet_manager import FleetManager
from shaprai.core.lifecycle import AgentState


class TestFleetManagerInit:
    """Tests for FleetManager initialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_with_custom_dir(self):
        """Test initialization with custom agents directory."""
        manager = FleetManager(self.temp_dir)
        
        assert manager.agents_dir == self.temp_dir
        assert self.temp_dir.exists()

    def test_init_creates_directory(self):
        """Test that initialization creates the agents directory."""
        new_dir = self.temp_dir / "new_agents"
        assert not new_dir.exists()
        
        manager = FleetManager(new_dir)
        
        assert new_dir.exists()

    def test_init_default_dir(self):
        """Test initialization with default directory."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = self.temp_dir / "home"
            
            manager = FleetManager()
            
            expected_dir = self.temp_dir / "home" / ".shaprai" / "agents"
            assert manager.agents_dir == expected_dir
            assert expected_dir.exists()


class TestRegisterAgent:
    """Tests for FleetManager.register_agent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_agent_basic(self):
        """Test basic agent registration."""
        manifest = {
            "name": "test-agent",
            "state": "created",
            "model": {"base": "llama-3.1-8b"},
        }
        
        self.manager.register_agent(manifest)
        
        agent_dir = self.temp_dir / "test-agent"
        assert agent_dir.exists()
        
        manifest_path = agent_dir / "manifest.yaml"
        assert manifest_path.exists()
        
        with open(manifest_path, "r") as f:
            saved = yaml.safe_load(f)
        
        assert saved["name"] == "test-agent"
        assert saved["state"] == "created"

    def test_register_agent_creates_directory(self):
        """Test that registration creates agent directory."""
        manifest = {"name": "new-agent", "state": "created"}
        
        self.manager.register_agent(manifest)
        
        assert (self.temp_dir / "new-agent").exists()


class TestListAgents:
    """Tests for FleetManager.list_agents."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_agents_empty(self):
        """Test listing agents when fleet is empty."""
        agents = self.manager.list_agents()
        assert agents == []

    def test_list_agents_single(self):
        """Test listing a single agent."""
        manifest = {"name": "single-agent", "state": "created"}
        self.manager.register_agent(manifest)
        
        agents = self.manager.list_agents()
        
        assert len(agents) == 1
        assert agents[0]["name"] == "single-agent"

    def test_list_agents_multiple(self):
        """Test listing multiple agents."""
        for i in range(3):
            manifest = {"name": f"agent-{i}", "state": "created"}
            self.manager.register_agent(manifest)
        
        agents = self.manager.list_agents()
        
        assert len(agents) == 3
        names = [a["name"] for a in agents]
        assert names == ["agent-0", "agent-1", "agent-2"]

    def test_list_agents_state_filter(self):
        """Test listing agents with state filter."""
        self.manager.register_agent({"name": "created-agent", "state": "created"})
        self.manager.register_agent({"name": "deployed-agent", "state": "deployed"})
        self.manager.register_agent({"name": "retired-agent", "state": "retired"})
        
        created_agents = self.manager.list_agents(state_filter=AgentState.CREATED)
        assert len(created_agents) == 1
        assert created_agents[0]["name"] == "created-agent"
        
        deployed_agents = self.manager.list_agents(state_filter=AgentState.DEPLOYED)
        assert len(deployed_agents) == 1
        assert deployed_agents[0]["name"] == "deployed-agent"

    def test_list_agents_platform_filter(self):
        """Test listing agents with platform filter."""
        self.manager.register_agent({
            "name": "github-agent",
            "state": "deployed",
            "platforms": ["github"],
        })
        self.manager.register_agent({
            "name": "bottube-agent",
            "state": "deployed",
            "platforms": ["bottube"],
        })
        self.manager.register_agent({
            "name": "multi-agent",
            "state": "deployed",
            "platforms": ["github", "bottube"],
        })
        
        github_agents = self.manager.list_agents(platform_filter="github")
        assert len(github_agents) == 2
        
        bottube_agents = self.manager.list_agents(platform_filter="bottube")
        assert len(bottube_agents) == 2

    def test_list_agents_nonexistent_directory(self):
        """Test listing agents when directory doesn't exist."""
        shutil.rmtree(self.temp_dir)
        
        agents = self.manager.list_agents()
        assert agents == []

    def test_list_agents_skips_invalid(self):
        """Test that invalid manifests are skipped."""
        # Create a valid agent
        self.manager.register_agent({"name": "valid-agent", "state": "created"})
        
        # Create an invalid agent directory (no manifest)
        invalid_dir = self.temp_dir / "invalid-agent"
        invalid_dir.mkdir()
        
        # Create a malformed manifest
        malformed_dir = self.temp_dir / "malformed-agent"
        malformed_dir.mkdir()
        with open(malformed_dir / "manifest.yaml", "w") as f:
            f.write("invalid: yaml: [")
        
        agents = self.manager.list_agents()
        
        # Should only return the valid agent
        assert len(agents) == 1
        assert agents[0]["name"] == "valid-agent"

    def test_list_agents_skips_empty_manifest(self):
        """Test that agents with empty (None) manifests are skipped."""
        # Create a valid agent
        self.manager.register_agent({"name": "valid-agent", "state": "created"})
        
        # Create an agent with empty manifest file
        empty_dir = self.temp_dir / "empty-agent"
        empty_dir.mkdir()
        with open(empty_dir / "manifest.yaml", "w") as f:
            f.write("")  # Empty file results in None when loaded
        
        agents = self.manager.list_agents()
        
        # Should only return the valid agent
        assert len(agents) == 1
        assert agents[0]["name"] == "valid-agent"


class TestGetAgent:
    """Tests for FleetManager.get_agent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_agent_exists(self):
        """Test getting an existing agent."""
        manifest = {
            "name": "test-agent",
            "state": "created",
            "model": {"base": "test"},
        }
        self.manager.register_agent(manifest)
        
        retrieved = self.manager.get_agent("test-agent")
        
        assert retrieved is not None
        assert retrieved["name"] == "test-agent"
        assert retrieved["model"]["base"] == "test"

    def test_get_agent_not_found(self):
        """Test getting a nonexistent agent."""
        retrieved = self.manager.get_agent("nonexistent")
        assert retrieved is None


class TestBroadcastUpdate:
    """Tests for FleetManager.broadcast_update."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_broadcast_update_basic(self):
        """Test basic broadcast to all agents."""
        self.manager.register_agent({"name": "agent-1", "state": "created"})
        self.manager.register_agent({"name": "agent-2", "state": "deployed"})
        
        count = self.manager.broadcast_update("Test update message")
        
        assert count == 2
        
        # Check that updates file was created for agent-1
        updates_path = self.temp_dir / "agent-1" / "updates.yaml"
        assert updates_path.exists()
        
        with open(updates_path, "r") as f:
            updates = yaml.safe_load(f)
        
        assert len(updates) == 1
        assert updates[0]["message"] == "Test update message"
        assert updates[0]["acknowledged"] is False
        assert "timestamp" in updates[0]

    def test_broadcast_update_state_filter(self):
        """Test broadcast with state filter."""
        self.manager.register_agent({"name": "created-agent", "state": "created"})
        self.manager.register_agent({"name": "deployed-agent", "state": "deployed"})
        
        count = self.manager.broadcast_update(
            "Deployed agents only",
            state_filter=AgentState.DEPLOYED,
        )
        
        assert count == 1
        
        # Only deployed-agent should have the update
        deployed_updates = self.temp_dir / "deployed-agent" / "updates.yaml"
        created_updates = self.temp_dir / "created-agent" / "updates.yaml"
        
        assert deployed_updates.exists()
        assert not created_updates.exists()

    def test_broadcast_update_appends(self):
        """Test that broadcast appends to existing updates."""
        self.manager.register_agent({"name": "test-agent", "state": "created"})
        
        self.manager.broadcast_update("First message")
        self.manager.broadcast_update("Second message")
        
        updates_path = self.temp_dir / "test-agent" / "updates.yaml"
        with open(updates_path, "r") as f:
            updates = yaml.safe_load(f)
        
        assert len(updates) == 2
        assert updates[0]["message"] == "First message"
        assert updates[1]["message"] == "Second message"

    def test_broadcast_update_empty_fleet(self):
        """Test broadcast to empty fleet."""
        count = self.manager.broadcast_update("Test")
        assert count == 0


class TestGetFleetHealth:
    """Tests for FleetManager.get_fleet_health."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_fleet_health_empty(self):
        """Test health report for empty fleet."""
        health = self.manager.get_fleet_health()
        
        assert health["total_agents"] == 0
        assert health["by_state"] == {}
        assert health["platforms"] == {}
        assert health["health"] == "empty"

    def test_get_fleet_health_single_agent(self):
        """Test health report with single agent."""
        self.manager.register_agent({
            "name": "single-agent",
            "state": "created",
        })
        
        health = self.manager.get_fleet_health()
        
        assert health["total_agents"] == 1
        assert health["by_state"]["created"] == 1

    def test_get_fleet_health_multiple_states(self):
        """Test health report with agents in different states."""
        self.manager.register_agent({"name": "agent-1", "state": "created"})
        self.manager.register_agent({"name": "agent-2", "state": "deployed"})
        self.manager.register_agent({"name": "agent-3", "state": "deployed"})
        self.manager.register_agent({"name": "agent-4", "state": "retired"})
        
        health = self.manager.get_fleet_health()
        
        assert health["total_agents"] == 4
        assert health["by_state"]["created"] == 1
        assert health["by_state"]["deployed"] == 2
        assert health["by_state"]["retired"] == 1

    def test_get_fleet_health_platforms(self):
        """Test health report tracks platforms."""
        self.manager.register_agent({
            "name": "github-agent",
            "state": "deployed",
            "platforms": ["github"],
        })
        self.manager.register_agent({
            "name": "bottube-agent",
            "state": "deployed",
            "platforms": ["bottube"],
        })
        self.manager.register_agent({
            "name": "multi-agent",
            "state": "deployed",
            "platforms": ["github", "bottube"],
        })
        
        health = self.manager.get_fleet_health()
        
        assert health["platforms"]["github"] == 2
        assert health["platforms"]["bottube"] == 2

    def test_get_fleet_health_healthy(self):
        """Test health calculation - healthy fleet."""
        # 7 out of 10 agents active (70%)
        for i in range(7):
            self.manager.register_agent({
                "name": f"active-{i}",
                "state": "deployed",
            })
        for i in range(3):
            self.manager.register_agent({
                "name": f"inactive-{i}",
                "state": "created",
            })
        
        health = self.manager.get_fleet_health()
        
        assert health["active_ratio"] == 0.7
        assert health["health"] == "healthy"

    def test_get_fleet_health_fair(self):
        """Test health calculation - fair fleet."""
        # 5 out of 10 agents active (50%)
        for i in range(5):
            self.manager.register_agent({
                "name": f"active-{i}",
                "state": "deployed",
            })
        for i in range(5):
            self.manager.register_agent({
                "name": f"inactive-{i}",
                "state": "created",
            })
        
        health = self.manager.get_fleet_health()
        
        assert health["active_ratio"] == 0.5
        assert health["health"] == "fair"

    def test_get_fleet_health_needs_attention(self):
        """Test health calculation - needs attention."""
        # 3 out of 10 agents active (30%)
        for i in range(3):
            self.manager.register_agent({
                "name": f"active-{i}",
                "state": "deployed",
            })
        for i in range(7):
            self.manager.register_agent({
                "name": f"inactive-{i}",
                "state": "created",
            })
        
        health = self.manager.get_fleet_health()
        
        assert health["active_ratio"] == 0.3
        assert health["health"] == "needs_attention"

    def test_get_fleet_health_includes_graduated(self):
        """Test that graduated agents count as active."""
        for i in range(4):
            self.manager.register_agent({
                "name": f"deployed-{i}",
                "state": "deployed",
            })
        for i in range(4):
            self.manager.register_agent({
                "name": f"graduated-{i}",
                "state": "graduated",
            })
        for i in range(2):
            self.manager.register_agent({
                "name": f"created-{i}",
                "state": "created",
            })
        
        health = self.manager.get_fleet_health()
        
        # 8 out of 10 active (deployed + graduated)
        assert health["active_ratio"] == 0.8
        assert health["health"] == "healthy"


class TestFleetManagerIntegration:
    """Integration tests for FleetManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = FleetManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_fleet_workflow(self):
        """Test complete fleet management workflow."""
        # Register agents
        self.manager.register_agent({
            "name": "agent-1",
            "state": "deployed",
            "platforms": ["github"],
        })
        self.manager.register_agent({
            "name": "agent-2",
            "state": "deployed",
            "platforms": ["bottube"],
        })
        self.manager.register_agent({
            "name": "agent-3",
            "state": "created",
        })
        
        # List all agents
        all_agents = self.manager.list_agents()
        assert len(all_agents) == 3
        
        # List deployed only
        deployed = self.manager.list_agents(state_filter=AgentState.DEPLOYED)
        assert len(deployed) == 2
        
        # Get specific agent
        agent = self.manager.get_agent("agent-1")
        assert agent["name"] == "agent-1"
        
        # Broadcast to deployed
        count = self.manager.broadcast_update(
            "Update for deployed",
            state_filter=AgentState.DEPLOYED,
        )
        assert count == 2
        
        # Check health
        health = self.manager.get_fleet_health()
        assert health["total_agents"] == 3
        assert health["health"] == "fair"  # 2/3 = 66.7%
