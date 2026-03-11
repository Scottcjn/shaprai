import pytest
from unittest.mock import Mock, patch
from shaprai.elyan_bus import ElyanBus
from shaprai.agent import ElyanAgent

class TestElyanBusIntegration:
    """Integration tests for Elyan Bus"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.bus = ElyanBus()
        self.agent1 = ElyanAgent("agent1")
        self.agent2 = ElyanAgent("agent2")
    
    def test_register_agent(self):
        """Test registering an agent with the bus"""
        self.bus.register_agent(self.agent1)
        assert self.agent1.id in self.bus.agents
        assert self.bus.agents[self.agent1.id] == self.agent1
    
    def test_unregister_agent(self):
        """Test unregistering an agent from the bus"""
        self.bus.register_agent(self.agent1)
        self.bus.unregister_agent(self.agent1.id)
        assert self.agent1.id not in self.bus.agents
    
    def test_broadcast_message(self):
        """Test broadcasting a message to all agents"""
        self.bus.register_agent(self.agent1)
        self.bus.register_agent(self.agent2)
        
        with patch.object(self.agent1, 'receive_message') as mock_agent1:
            with patch.object(self.agent2, 'receive_message') as mock_agent2:
                message = {"type": "test", "content": "Hello"}
                self.bus.broadcast_message(message)
                
                mock_agent1.assert_called_once_with(message)
                mock_agent2.assert_called_once_with(message)
    
    def test_send_direct_message(self):
        """Test sending a direct message to a specific agent"""
        self.bus.register_agent(self.agent1)
        
        with patch.object(self.agent1, 'receive_message') as mock_agent1:
            message = {"type": "direct", "content": "Private message"}
            self.bus.send_direct_message(self.agent1.id, message)
            mock_agent1.assert_called_once_with(message)
    
    def test_send_direct_message_to_nonexistent_agent(self):
        """Test sending a message to a non-existent agent"""
        with pytest.raises(ValueError, match="Agent not found"):
            self.bus.send_direct_message("nonexistent", {"type": "test"})
    
    def test_agent_communication_flow(self):
        """Test a complete communication flow between agents"""
        self.bus.register_agent(self.agent1)
        self.bus.register_agent(self.agent2)
        
        # Agent1 sends a message to Agent2
        with patch.object(self.agent2, 'receive_message') as mock_agent2:
            message = {"type": "request", "content": "Can you help?"}
            self.bus.send_direct_message(self.agent2.id, message)
            mock_agent2.assert_called_once_with(message)
        
        # Agent2 responds to Agent1
        with patch.object(self.agent1, 'receive_message') as mock_agent1:
            response = {"type": "response", "content": "Sure, I can help"}
            self.bus.send_direct_message(self.agent1.id, response)
            mock_agent1.assert_called_once_with(response)
    
    def test_bus_with_multiple_agents(self):
        """Test bus functionality with multiple agents"""
        agents = [ElyanAgent(f"agent{i}") for i in range(5)]
        
        # Register all agents
        for agent in agents:
            self.bus.register_agent(agent)
        
        # Verify all agents are registered
        assert len(self.bus.agents) == 5
        for agent in agents:
            assert agent.id in self.bus.agents
        
        # Broadcast message to all agents
        with patch.object(agent, 'receive_message') as mock_agent:
            message = {"type": "broadcast", "content": "Hello everyone"}
            self.bus.broadcast_message(message)
            
            # All agents should receive the message
            for agent in agents:
                mock_agent.assert_called_with(message)
    
    def test_bus_error_handling(self):
        """Test error handling in the bus"""
        # Test with empty agent ID
        with pytest.raises(ValueError, match="Agent ID cannot be empty"):
            self.bus.register_agent(ElyanAgent(""))
        
        # Test with None message
        self.bus.register_agent(self.agent1)
        with pytest.raises(ValueError, match="Message cannot be None"):
            self.bus.send_direct_message(self.agent1.id, None)
        
        with pytest.raises(ValueError, match="Message cannot be None"):
            self.bus.broadcast_message(None)
    
    def tearDown(self):
        """Clean up after tests"""
        self.bus.agents.clear()