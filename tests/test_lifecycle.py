# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for the lifecycle management module."""

import pytest
import yaml
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from shaprai.core.lifecycle import (
    AgentState,
    create_agent,
    transition_state,
    deploy_agent,
    retire_agent,
    get_agent_status,
    _load_manifest,
    _save_manifest,
)
from shaprai.core.template_engine import AgentTemplate


class TestAgentState:
    """Tests for AgentState enum."""

    def test_all_states_exist(self):
        """Test that all expected states are defined."""
        states = [state.value for state in AgentState]
        
        assert "created" in states
        assert "training" in states
        assert "sanctuary" in states
        assert "graduated" in states
        assert "deployed" in states
        assert "retired" in states


class TestCreateAgent:
    """Tests for create_agent function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(
            name="test-template",
            model={"base": "llama-3.1-8b"},
            capabilities=["code_review"],
            platforms=["github"],
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_agent_basic(self):
        """Test basic agent creation."""
        manifest = create_agent("test-agent", self.template, self.temp_dir)
        
        assert manifest["name"] == "test-agent"
        assert manifest["state"] == "created"
        assert manifest["template"] == "test-template"
        assert manifest["model"] == {"base": "llama-3.1-8b"}
        assert manifest["capabilities"] == ["code_review"]
        assert "created_at" in manifest
        assert "updated_at" in manifest

    def test_create_agent_creates_directory(self):
        """Test that agent directory is created."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        agent_dir = self.temp_dir / "test-agent"
        assert agent_dir.exists()
        assert agent_dir.is_dir()

    def test_create_agent_writes_manifest(self):
        """Test that manifest file is written."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        manifest_path = self.temp_dir / "test-agent" / "manifest.yaml"
        assert manifest_path.exists()
        
        with open(manifest_path, "r") as f:
            saved_manifest = yaml.safe_load(f)
        
        assert saved_manifest["name"] == "test-agent"

    def test_create_agent_duplicate(self):
        """Test that creating a duplicate agent raises FileExistsError."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        with pytest.raises(FileExistsError, match="already exists"):
            create_agent("test-agent", self.template, self.temp_dir)

    def test_create_agent_default_agents_dir(self):
        """Test agent creation with default agents directory."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = self.temp_dir / "home"
            
            manifest = create_agent("test-agent", self.template)
            
            agent_dir = self.temp_dir / "home" / ".shaprai" / "agents" / "test-agent"
            assert agent_dir.exists()

    def test_create_agent_includes_all_template_fields(self):
        """Test that all template fields are included in manifest."""
        full_template = AgentTemplate(
            name="full-template",
            model={"base": "test", "quantization": "q4"},
            personality={"style": "professional"},
            capabilities=["cap1", "cap2"],
            platforms=["github", "bottube"],
            ethics_profile="strict",
            driftlock={"enabled": True, "check_interval": 50},
            description="Test description",
            version="2.0",
            rtc_config={"bounty_percentage": 0.1},
        )
        
        manifest = create_agent("full-agent", full_template, self.temp_dir)
        
        assert manifest["model"] == {"base": "test", "quantization": "q4"}
        assert manifest["personality"] == {"style": "professional"}
        assert manifest["capabilities"] == ["cap1", "cap2"]
        assert manifest["platforms"] == ["github", "bottube"]
        assert manifest["ethics_profile"] == "strict"
        assert manifest["driftlock"] == {"enabled": True, "check_interval": 50}
        assert manifest["rtc_config"] == {"bounty_percentage": 0.1}


class TestLoadManifest:
    """Tests for _load_manifest helper function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_manifest_success(self):
        """Test loading a valid manifest."""
        agent_dir = self.temp_dir / "test-agent"
        agent_dir.mkdir()
        
        manifest_data = {"name": "test-agent", "state": "created"}
        manifest_path = agent_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        loaded = _load_manifest("test-agent", self.temp_dir)
        
        assert loaded["name"] == "test-agent"
        assert loaded["state"] == "created"

    def test_load_manifest_not_found(self):
        """Test loading a nonexistent manifest raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            _load_manifest("nonexistent", self.temp_dir)


class TestSaveManifest:
    """Tests for _save_manifest helper function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_manifest_updates_timestamp(self):
        """Test that saving updates the timestamp."""
        agent_dir = self.temp_dir / "test-agent"
        agent_dir.mkdir()
        
        original_time = time.time() - 100
        manifest = {"name": "test-agent", "updated_at": original_time}
        
        _save_manifest("test-agent", manifest, self.temp_dir)
        
        with open(agent_dir / "manifest.yaml", "r") as f:
            saved = yaml.safe_load(f)
        
        assert saved["updated_at"] > original_time


class TestTransitionState:
    """Tests for transition_state function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(name="test")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transition_state_basic(self):
        """Test basic state transition."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        manifest = transition_state("test-agent", AgentState.TRAINING, self.temp_dir)
        
        assert manifest["state"] == "training"
        assert "state_history" in manifest
        assert len(manifest["state_history"]) == 1
        assert manifest["state_history"][0]["from"] == "created"
        assert manifest["state_history"][0]["to"] == "training"

    def test_transition_state_multiple(self):
        """Test multiple state transitions."""
        create_agent("test-agent", self.template, self.temp_dir)
        transition_state("test-agent", AgentState.TRAINING, self.temp_dir)
        transition_state("test-agent", AgentState.SANCTUARY, self.temp_dir)
        
        manifest = transition_state("test-agent", AgentState.GRADUATED, self.temp_dir)
        
        assert manifest["state"] == "graduated"
        assert len(manifest["state_history"]) == 3


class TestDeployAgent:
    """Tests for deploy_agent function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(name="test")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deploy_agent_basic(self):
        """Test basic agent deployment."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        manifest = deploy_agent("test-agent", ["github", "bottube"], self.temp_dir)
        
        assert manifest["state"] == "deployed"
        assert manifest["platforms"] == ["github", "bottube"]
        assert len(manifest["deployment_history"]) == 1
        assert manifest["deployment_history"][0]["platforms"] == ["github", "bottube"]

    def test_deploy_agent_multiple_deployments(self):
        """Test multiple deployments are tracked."""
        create_agent("test-agent", self.template, self.temp_dir)
        deploy_agent("test-agent", ["github"], self.temp_dir)
        
        manifest = deploy_agent("test-agent", ["github", "bottube"], self.temp_dir)
        
        assert len(manifest["deployment_history"]) == 2


class TestRetireAgent:
    """Tests for retire_agent function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(name="test")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_retire_agent_basic(self):
        """Test basic agent retirement."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        manifest = retire_agent("test-agent", self.temp_dir)
        
        assert manifest["state"] == "retired"


class TestGetAgentStatus:
    """Tests for get_agent_status function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(name="test")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_agent_status_basic(self):
        """Test getting agent status."""
        create_agent("test-agent", self.template, self.temp_dir)
        
        manifest = get_agent_status("test-agent", self.temp_dir)
        
        assert manifest["name"] == "test-agent"
        assert manifest["state"] == "created"

    def test_get_agent_status_not_found(self):
        """Test getting status of nonexistent agent."""
        with pytest.raises(FileNotFoundError, match="not found"):
            get_agent_status("nonexistent", self.temp_dir)


class TestAgentLifecycleIntegration:
    """Integration tests for the full agent lifecycle."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template = AgentTemplate(
            name="integration-test",
            capabilities=["test"],
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_lifecycle(self):
        """Test complete agent lifecycle from creation to retirement."""
        # Create
        manifest = create_agent("lifecycle-agent", self.template, self.temp_dir)
        assert manifest["state"] == "created"
        
        # Transition to training
        manifest = transition_state("lifecycle-agent", AgentState.TRAINING, self.temp_dir)
        assert manifest["state"] == "training"
        
        # Transition to sanctuary
        manifest = transition_state("lifecycle-agent", AgentState.SANCTUARY, self.temp_dir)
        assert manifest["state"] == "sanctuary"
        
        # Graduate
        manifest = transition_state("lifecycle-agent", AgentState.GRADUATED, self.temp_dir)
        assert manifest["state"] == "graduated"
        
        # Deploy
        manifest = deploy_agent("lifecycle-agent", ["github"], self.temp_dir)
        assert manifest["state"] == "deployed"
        
        # Retire
        manifest = retire_agent("lifecycle-agent", self.temp_dir)
        assert manifest["state"] == "retired"
        
        # Verify state history (deploy_agent doesn't add to state_history, only transitions do)
        assert len(manifest["state_history"]) == 4

    @patch('pathlib.Path.home')
    def test_transition_state_default_dir(self, mock_home):
        """Test transition_state with default agents directory."""
        mock_home.return_value = self.temp_dir / "home"
        
        # Create agent with default dir
        create_agent("default-agent", self.template)
        
        # Transition with default dir
        manifest = transition_state("default-agent", AgentState.TRAINING)
        
        assert manifest["state"] == "training"
        assert len(manifest["state_history"]) == 1

    @patch('pathlib.Path.home')
    def test_deploy_agent_default_dir(self, mock_home):
        """Test deploy_agent with default agents directory."""
        mock_home.return_value = self.temp_dir / "home"
        
        create_agent("deploy-agent", self.template)
        
        manifest = deploy_agent("deploy-agent", ["github"])
        
        assert manifest["state"] == "deployed"
        assert manifest["platforms"] == ["github"]

    @patch('pathlib.Path.home')
    def test_get_agent_status_default_dir(self, mock_home):
        """Test get_agent_status with default agents directory."""
        mock_home.return_value = self.temp_dir / "home"
        
        create_agent("status-agent", self.template)
        
        manifest = get_agent_status("status-agent")
        
        assert manifest["name"] == "status-agent"
        assert manifest["state"] == "created"
