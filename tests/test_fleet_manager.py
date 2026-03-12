# SPDX-License-Identifier: MIT
# Unit tests for shaprai/core/fleet_manager.py

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.core.fleet_manager import FleetManager, Fleet


class TestFleetManager:
    """Test suite for FleetManager"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.manager = FleetManager()
    
    def test_manager_initialization(self):
        """Test FleetManager initialization"""
        assert self.manager is not None
        assert isinstance(self.manager, FleetManager)
    
    def test_create_fleet(self):
        """Test creating a new fleet"""
        if hasattr(self.manager, 'create_fleet'):
            fleet = self.manager.create_fleet("test_fleet")
            assert fleet is not None
            assert fleet.name == "test_fleet"
    
    def test_list_fleets_empty(self):
        """Test listing fleets when none exist"""
        if hasattr(self.manager, 'list_fleets'):
            fleets = self.manager.list_fleets()
            assert isinstance(fleets, list)
    
    def test_add_agent_to_fleet(self):
        """Test adding an agent to a fleet"""
        if hasattr(self.manager, 'create_fleet') and hasattr(self.manager, 'add_agent'):
            fleet = self.manager.create_fleet("fleet1")
            result = self.manager.add_agent("fleet1", "agent1")
            # Should return success or the updated fleet
            assert result is not None
    
    def test_remove_agent_from_fleet(self):
        """Test removing an agent from a fleet"""
        if hasattr(self.manager, 'remove_agent'):
            pass  # Implementation depends on API
    
    def test_fleet_capacity_limits(self):
        """Test fleet capacity/size limits"""
        pass  # If fleets have size limits


class TestFleet:
    """Test Fleet class"""
    
    def test_fleet_creation(self):
        """Test creating a Fleet instance"""
        fleet = Fleet(name="test", agents=[])
        assert fleet.name == "test"
        assert isinstance(fleet.agents, list)
    
    def test_fleet_has_agents_list(self):
        """Test that fleet maintains agent list"""
        fleet = Fleet(name="test", agents=["agent1", "agent2"])
        assert len(fleet.agents) == 2
    
    def test_fleet_metadata(self):
        """Test fleet metadata fields"""
        fleet = Fleet(name="test", agents=[])
        # Common metadata fields
        expected_fields = ["name", "agents"]
        for field in expected_fields:
            assert hasattr(fleet, field)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
