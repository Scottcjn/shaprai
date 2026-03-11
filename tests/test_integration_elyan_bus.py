import pytest
from shaprai.elyan_bus import ElyanBus
from shaprai.agent import Agent

class MockAgent(Agent):
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.processed_messages = []
    
    def process_message(self, message):
        self.processed_messages.append(message)
        return f"Processed: {message}"

def test_elyan_bus_initialization():
    """Test that ElyanBus initializes correctly."""
    bus = ElyanBus()
    assert bus.agents == {}
    assert bus.message_queue == []

def test_elyan_bus_register_agent():
    """Test registering an agent with the bus."""
    bus = ElyanBus()
    agent = MockAgent("test-agent")
    bus.register_agent(agent)
    assert "test-agent" in bus.agents
    assert bus.agents["test-agent"] == agent

def test_elyan_bus_unregister_agent():
    """Test unregistering an agent from the bus."""
    bus = ElyanBus()
    agent = MockAgent("test-agent")
    bus.register_agent(agent)
    bus.unregister_agent("test-agent")
    assert "test-agent" not in bus.agents

def test_elyan_bus_send_message():
    """Test sending a message to a specific agent."""
    bus = ElyanBus()
    agent = MockAgent("test-agent")
    bus.register_agent(agent)
    
    bus.send_message("test-agent", "Hello, Agent!")
    assert len(agent.processed_messages) == 1
    assert agent.processed_messages[0] == "Hello, Agent!"

def test_elyan_bus_send_message_to_nonexistent_agent():
    """Test sending a message to a non-existent agent."""
    bus = ElyanBus()
    with pytest.raises(ValueError, match="Agent not found"):
        bus.send_message("nonexistent-agent", "Hello!")

def test_elyan_bus_broadcast_message():
    """Test broadcasting a message to all agents."""
    bus = ElyanBus()
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    bus.register_agent(agent1)
    bus.register_agent(agent2)
    
    bus.broadcast_message("Hello, all agents!")
    assert len(agent1.processed_messages) == 1
    assert len(agent2.processed_messages) == 1
    assert agent1.processed_messages[0] == "Hello, all agents!"
    assert agent2.processed_messages[0] == "Hello, all agents!"

def test_elyan_bus_process_messages():
    """Test processing messages in the queue."""
    bus = ElyanBus()
    agent = MockAgent("test-agent")
    bus.register_agent(agent)
    
    # Add messages to queue
    bus.message_queue.append(("test-agent", "Message 1"))
    bus.message_queue.append(("test-agent", "Message 2"))
    
    bus.process_messages()
    assert len(agent.processed_messages) == 2
    assert agent.processed_messages[0] == "Message 1"
    assert agent.processed_messages[1] == "Message 2"
    assert len(bus.message_queue) == 0

def test_elyan_bus_process_messages_empty_queue():
    """Test processing messages when the queue is empty."""
    bus = ElyanBus()
    agent = MockAgent("test-agent")
    bus.register_agent(agent)
    
    bus.process_messages()
    assert len(agent.processed_messages) == 0
    assert len(bus.message_queue) == 0

def test_elyan_bus_multiple_agents():
    """Test bus functionality with multiple agents."""
    bus = ElyanBus()
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    agent3 = MockAgent("agent3")
    
    bus.register_agent(agent1)
    bus.register_agent(agent2)
    bus.register_agent(agent3)
    
    # Send specific messages
    bus.send_message("agent1", "Hello, Agent 1!")
    bus.send_message("agent2", "Hello, Agent 2!")
    
    # Broadcast to all
    bus.broadcast_message("Broadcast message")
    
    # Process messages
    bus.process_messages()
    
    # Check results
    assert len(agent1.processed_messages) == 2
    assert len(agent2.processed_messages) == 2
    assert len(agent3.processed_messages) == 1
    
    assert agent1.processed_messages[0] == "Hello, Agent 1!"
    assert agent1.processed_messages[1] == "Broadcast message"
    assert agent2.processed_messages[0] == "Hello, Agent 2!"
    assert agent2.processed_messages[1] == "Broadcast message"
    assert agent3.processed_messages[0] == "Broadcast message"

def test_elyan_bus_agent_error_handling():
    """Test error handling when an agent raises an exception."""
    class ErrorAgent(Agent):
        def process_message(self, message):
            raise ValueError("Agent processing error")
    
    bus = ElyanBus()
    agent = ErrorAgent("error-agent")
    bus.register_agent(agent)
    
    # This should not raise an exception, but should log the error
    bus.send_message("error-agent", "Test message")
    bus.process_messages()
    
    # The message should still be in the queue if processing failed
    assert len(bus.message_queue) == 1
    assert bus.message_queue[0] == ("error-agent", "Test message")
