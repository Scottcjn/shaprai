import pytest
import yaml
from pathlib import Path
from shaprai.core.fleet_manager import FleetManager
from shaprai.core.lifecycle import AgentState

def test_register_and_get_agent(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    manifest = {"name": "fleet-bot", "state": "created"}
    fm.register_agent(manifest)
    
    assert (temp_agents_dir / "fleet-bot" / "manifest.yaml").exists()
    loaded = fm.get_agent("fleet-bot")
    assert loaded["name"] == "fleet-bot"

def test_list_agents(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    fm.register_agent({"name": "bot1", "state": "deployed", "platforms": ["github"]})
    fm.register_agent({"name": "bot2", "state": "created"})
    
    all_bots = fm.list_agents()
    assert len(all_bots) == 2
    
    deployed_bots = fm.list_agents(state_filter=AgentState.DEPLOYED)
    assert len(deployed_bots) == 1
    assert deployed_bots[0]["name"] == "bot1"
    
    github_bots = fm.list_agents(platform_filter="github")
    assert len(github_bots) == 1
    assert github_bots[0]["name"] == "bot1"

def test_broadcast_update(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    fm.register_agent({"name": "bot1", "state": "deployed"})
    fm.register_agent({"name": "bot2", "state": "created"})
    
    # Broadcast to all
    count = fm.broadcast_update("Hello fleet!")
    assert count == 2
    assert (temp_agents_dir / "bot1" / "updates.yaml").exists()
    
    # Broadcast to specific state
    count = fm.broadcast_update("Training update", state_filter=AgentState.TRAINING)
    assert count == 0

def test_fleet_health(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    fm.register_agent({"name": "bot1", "state": "deployed", "platforms": ["github"]})
    fm.register_agent({"name": "bot2", "state": "retired"})
    
    health = fm.get_fleet_health()
    assert health["total_agents"] == 2
    assert health["by_state"]["deployed"] == 1
    assert health["platforms"]["github"] == 1
    assert health["active_ratio"] == 0.5
    assert health["health"] == "fair"

def test_list_agents_malformed(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    bad_dir = temp_agents_dir / "bad-bot"
    bad_dir.mkdir()
    (bad_dir / "manifest.yaml").write_text(":") # Invalid
    
    assert len(fm.list_agents()) == 0

def test_list_agents_not_dir(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    (temp_agents_dir / "not-a-dir").touch()
    assert len(fm.list_agents()) == 0

def test_get_agent_not_found(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    assert fm.get_agent("missing") is None

def test_fleet_health_no_agents(temp_agents_dir):
    fm = FleetManager(agents_dir=temp_agents_dir)
    health = fm.get_fleet_health()
    assert health["total_agents"] == 0
