import pytest
import time
from pathlib import Path
from shaprai.core.lifecycle import AgentState, create_agent, transition_state, deploy_agent, retire_agent, get_agent_status

def test_create_agent(temp_agents_dir, mock_template):
    manifest = create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    
    assert manifest["name"] == "test-bot"
    assert manifest["state"] == AgentState.CREATED.value
    assert (temp_agents_dir / "test-bot" / "manifest.yaml").exists()

def test_create_agent_duplicate(temp_agents_dir, mock_template):
    create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    with pytest.raises(FileExistsError):
        create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)

def test_transition_state(temp_agents_dir, mock_template):
    create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    
    updated = transition_state("test-bot", AgentState.TRAINING, agents_dir=temp_agents_dir)
    assert updated["state"] == AgentState.TRAINING.value
    assert updated["state_history"][-1]["to"] == AgentState.TRAINING.value

def test_deploy_agent(temp_agents_dir, mock_template):
    create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    
    platforms = ["github", "discord"]
    updated = deploy_agent("test-bot", platforms, agents_dir=temp_agents_dir)
    
    assert updated["state"] == AgentState.DEPLOYED.value
    assert updated["platforms"] == platforms
    assert updated["deployment_history"][-1]["platforms"] == platforms

def test_retire_agent(temp_agents_dir, mock_template):
    create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    updated = retire_agent("test-bot", agents_dir=temp_agents_dir)
    assert updated["state"] == AgentState.RETIRED.value

def test_get_agent_status(temp_agents_dir, mock_template):
    create_agent("test-bot", mock_template, agents_dir=temp_agents_dir)
    status = get_agent_status("test-bot", agents_dir=temp_agents_dir)
    assert status["name"] == "test-bot"

def test_load_manifest_not_found(temp_agents_dir):
    with pytest.raises(FileNotFoundError):
        get_agent_status("ghost", agents_dir=temp_agents_dir)
