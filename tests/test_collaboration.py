# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for multi-agent collaboration system."""

import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from shaprai.core.collaboration import (
    CollaborationHub,
    CollaborationAgent,
    AgentMessage,
    Task,
    MessageType,
    TaskPriority,
    TaskStatus,
)


@pytest.fixture
def temp_agents_dir():
    """Create a temporary agents directory for testing."""
    temp_dir = tempfile.mkdtemp()
    agents_dir = Path(temp_dir) / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    yield agents_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def hub(temp_agents_dir):
    """Create a CollaborationHub instance for testing."""
    return CollaborationHub(agents_dir=temp_agents_dir)


@pytest.fixture
def sample_agents(temp_agents_dir):
    """Create sample agent directories for testing."""
    agents = ["agent-alpha", "agent-beta", "agent-gamma"]
    for agent_name in agents:
        agent_dir = temp_agents_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": agent_name,
            "state": "deployed",
            "template": "bounty_hunter",
        }
        with open(agent_dir / "manifest.yaml", "w") as f:
            yaml.dump(manifest, f)
    return agents


class TestAgentMessage:
    """Test AgentMessage dataclass."""

    def test_create_message(self):
        """Test creating a basic message."""
        msg = AgentMessage(
            sender="agent-alpha",
            recipient="agent-beta",
            message_type=MessageType.COORDINATION,
            content={"key": "value"},
        )
        
        assert msg.sender == "agent-alpha"
        assert msg.recipient == "agent-beta"
        assert msg.message_type == MessageType.COORDINATION
        assert msg.content == {"key": "value"}
        assert msg.priority == TaskPriority.NORMAL
        assert msg.acknowledged is False

    def test_message_serialization(self):
        """Test message to_dict and from_dict."""
        original = AgentMessage(
            sender="agent-alpha",
            recipient="agent-beta",
            message_type=MessageType.TASK_ASSIGNMENT,
            content={"task_id": "123"},
            priority=TaskPriority.HIGH,
            requires_ack=True,
        )
        
        data = original.to_dict()
        restored = AgentMessage.from_dict(data)
        
        assert restored.sender == original.sender
        assert restored.recipient == original.recipient
        assert restored.message_type == original.message_type
        assert restored.content == original.content
        assert restored.priority == original.priority
        assert restored.requires_ack == original.requires_ack

    def test_message_id_generation(self):
        """Test that each message gets a unique ID."""
        msg1 = AgentMessage(sender="a", recipient="b")
        msg2 = AgentMessage(sender="a", recipient="b")
        
        assert msg1.message_id != msg2.message_id
        assert len(msg1.message_id) > 0


class TestTask:
    """Test Task dataclass."""

    def test_create_task(self):
        """Test creating a basic task."""
        task = Task(
            title="Test Task",
            description="Test description",
            created_by="agent-alpha",
            assigned_to="agent-beta",
            priority=TaskPriority.HIGH,
        )
        
        assert task.title == "Test Task"
        assert task.description == "Test description"
        assert task.created_by == "agent-alpha"
        assert task.assigned_to == "agent-beta"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING

    def test_task_serialization(self):
        """Test task to_dict and from_dict."""
        original = Task(
            title="Complex Task",
            description="With dependencies",
            created_by="agent-alpha",
            priority=TaskPriority.CRITICAL,
            dependencies=["task-1", "task-2"],
            metadata={"key": "value"},
        )
        
        data = original.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.title == original.title
        assert restored.dependencies == original.dependencies
        assert restored.metadata == original.metadata
        assert restored.priority == original.priority

    def test_task_status_transitions(self):
        """Test task status can be updated."""
        task = Task(title="Test", description="Test", created_by="agent-alpha")
        
        assert task.status == TaskStatus.PENDING
        
        task.status = TaskStatus.IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS
        
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED


class TestCollaborationHub:
    """Test CollaborationHub functionality."""

    def test_hub_initialization(self, hub, temp_agents_dir):
        """Test hub creates necessary directories and files."""
        assert hub.hub_dir.exists()
        assert hub.messages_file.exists()
        assert hub.tasks_file.exists()
        assert hub.sessions_file.exists()

    def test_send_and_get_message(self, hub):
        """Test sending and retrieving messages."""
        msg = AgentMessage(
            sender="agent-alpha",
            recipient="agent-beta",
            message_type=MessageType.COORDINATION,
            content={"test": "data"},
        )
        
        message_id = hub.send_message(msg)
        assert message_id == msg.message_id
        
        messages = hub.get_messages("agent-beta")
        assert len(messages) == 1
        assert messages[0].sender == "agent-alpha"
        assert messages[0].content == {"test": "data"}

    def test_broadcast_message(self, hub):
        """Test broadcasting messages."""
        msg = AgentMessage(
            sender="agent-alpha",
            recipient="broadcast",
            message_type=MessageType.COORDINATION,
            content={"announcement": "hello"},
        )
        
        hub.send_message(msg)
        
        # Both agents should receive broadcast
        messages_alpha = hub.get_messages("agent-alpha")
        messages_beta = hub.get_messages("agent-beta")
        
        assert len(messages_alpha) == 1
        assert len(messages_beta) == 1

    def test_acknowledge_message(self, hub):
        """Test message acknowledgment."""
        msg = AgentMessage(
            sender="agent-alpha",
            recipient="agent-beta",
            message_type=MessageType.COORDINATION,
            content={"test": "data"},
            requires_ack=True,
        )
        
        message_id = hub.send_message(msg)
        
        # Should have unread message
        unread = hub.get_messages("agent-beta", unread_only=True)
        assert len(unread) == 1
        
        # Acknowledge
        result = hub.acknowledge_message(message_id, "agent-beta")
        assert result is True
        
        # Should have no unread messages
        unread = hub.get_messages("agent-beta", unread_only=True)
        assert len(unread) == 0

    def test_create_task(self, hub):
        """Test task creation."""
        task_id = hub.create_task(
            title="Test Task",
            description="Test description",
            created_by="agent-alpha",
            assigned_to="agent-beta",
            priority=TaskPriority.HIGH,
        )
        
        assert task_id is not None
        
        task = hub.get_task(task_id)
        assert task is not None
        assert task.title == "Test Task"
        assert task.assigned_to == "agent-beta"
        assert task.priority == TaskPriority.HIGH

    def test_update_task_status(self, hub):
        """Test updating task status."""
        task_id = hub.create_task(
            title="Test Task",
            description="Test description",
            created_by="agent-alpha",
            assigned_to="agent-beta",
        )
        
        result = hub.update_task_status(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS,
            agent_name="agent-beta",
        )
        
        assert result is True
        
        task = hub.get_task(task_id)
        assert task.status == TaskStatus.IN_PROGRESS

    def test_update_task_with_result(self, hub):
        """Test updating task with result data."""
        task_id = hub.create_task(
            title="Test Task",
            description="Test description",
            created_by="agent-alpha",
            assigned_to="agent-beta",
        )
        
        result_data = {"output": "success", "value": 42}
        
        hub.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            agent_name="agent-beta",
            result=result_data,
        )
        
        task = hub.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == result_data

    def test_task_assignment_notification(self, hub):
        """Test that task assignment sends notification."""
        task_id = hub.create_task(
            title="Assigned Task",
            description="Test",
            created_by="agent-alpha",
            assigned_to="agent-beta",
        )
        
        messages = hub.get_messages("agent-beta")
        assert len(messages) == 1
        assert messages[0].message_type == MessageType.TASK_ASSIGNMENT
        assert messages[0].content["task_id"] == task_id

    def test_list_tasks_with_filters(self, hub):
        """Test listing tasks with filters."""
        # Create multiple tasks
        hub.create_task(title="Task 1", description="Test", created_by="agent-alpha", assigned_to="agent-beta", priority=TaskPriority.HIGH)
        hub.create_task(title="Task 2", description="Test", created_by="agent-alpha", assigned_to="agent-beta", priority=TaskPriority.LOW)
        hub.create_task(title="Task 3", description="Test", created_by="agent-alpha", assigned_to="agent-gamma", priority=TaskPriority.HIGH)
        
        # Filter by assignee
        beta_tasks = hub.list_tasks(assignee_filter="agent-beta")
        assert len(beta_tasks) == 2
        
        # Filter by priority
        high_priority = hub.list_tasks(priority_filter=TaskPriority.HIGH)
        assert len(high_priority) == 2
        
        # Combined filters
        beta_high = hub.list_tasks(assignee_filter="agent-beta", priority_filter=TaskPriority.HIGH)
        assert len(beta_high) == 1

    def test_assign_task(self, hub):
        """Test assigning a task to an agent."""
        task_id = hub.create_task(
            title="Unassigned Task",
            description="Test",
            created_by="agent-alpha",
        )
        
        task = hub.get_task(task_id)
        assert task.assigned_to is None
        
        result = hub.assign_task(task_id, "agent-beta", "agent-alpha")
        assert result is True
        
        task = hub.get_task(task_id)
        assert task.assigned_to == "agent-beta"
        
        # Should send notification
        messages = hub.get_messages("agent-beta")
        assert len(messages) == 1

    def test_create_session(self, hub, sample_agents):
        """Test creating a collaboration session."""
        session_id = hub.create_session(
            session_name="Test Session",
            participants=["agent-alpha", "agent-beta"],
            created_by="agent-alpha",
            objective="Test objective",
        )
        
        assert session_id is not None
        
        session = hub.get_session(session_id)
        assert session is not None
        assert session["name"] == "Test Session"
        assert len(session["participants"]) == 2
        assert session["objective"] == "Test objective"

    def test_join_session(self, hub, sample_agents):
        """Test joining a session."""
        session_id = hub.create_session(
            session_name="Test Session",
            participants=["agent-alpha"],
            created_by="agent-alpha",
        )
        
        result = hub.join_session(session_id, "agent-beta")
        assert result is True
        
        session = hub.get_session(session_id)
        assert "agent-beta" in session["participants"]

    def test_get_agent_tasks(self, hub):
        """Test getting tasks assigned to an agent."""
        hub.create_task(title="Task 1", description="Test", created_by="agent-alpha", assigned_to="agent-beta")
        hub.create_task(title="Task 2", description="Test", created_by="agent-alpha", assigned_to="agent-beta")
        hub.create_task(title="Task 3", description="Test", created_by="agent-alpha", assigned_to="agent-gamma")
        
        beta_tasks = hub.get_agent_tasks("agent-beta")
        assert len(beta_tasks) == 2
        
        gamma_tasks = hub.get_agent_tasks("agent-gamma")
        assert len(gamma_tasks) == 1

    def test_broadcast_to_fleet(self, hub, sample_agents):
        """Test broadcasting to all agents."""
        count = hub.broadcast_to_fleet(
            message="Important announcement",
            sender="agent-alpha",
            priority=TaskPriority.HIGH,
        )
        
        assert count == 3  # Three sample agents
        
        # Each agent should have received the broadcast
        for agent in sample_agents:
            messages = hub.get_messages(agent)
            broadcast_msgs = [m for m in messages if m.recipient == "broadcast"]
            assert len(broadcast_msgs) >= 1

    def test_task_completion_notification(self, hub):
        """Test that task completion sends notification to creator."""
        task_id = hub.create_task(
            title="Test Task",
            description="Test",
            created_by="agent-alpha",
            assigned_to="agent-beta",
        )
        
        hub.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            agent_name="agent-beta",
            result={"success": True},
        )
        
        # Creator should be notified
        messages = hub.get_messages("agent-alpha")
        completion_msgs = [m for m in messages if m.message_type == MessageType.TASK_COMPLETE]
        assert len(completion_msgs) == 1
        assert completion_msgs[0].content["task_id"] == task_id


class TestCollaborationAgent:
    """Test CollaborationAgent interface."""

    def test_agent_interface_creation(self, temp_agents_dir):
        """Test creating a collaboration agent interface."""
        agent = CollaborationAgent("agent-alpha")
        
        assert agent.agent_name == "agent-alpha"
        assert agent.hub is not None

    def test_agent_check_messages(self, hub):
        """Test agent checking messages."""
        agent = CollaborationAgent("agent-beta", hub)
        
        # Send a message
        agent.send_message(
            recipient="agent-beta",
            content={"test": "data"},
            message_type=MessageType.COORDINATION,
        )
        
        messages = agent.check_messages()
        assert len(messages) == 1

    def test_agent_send_message(self, hub):
        """Test agent sending messages."""
        agent = CollaborationAgent("agent-alpha", hub)
        
        message_id = agent.send_message(
            recipient="agent-beta",
            content={"key": "value"},
            message_type=MessageType.TASK_REQUEST,
            priority=TaskPriority.HIGH,
        )
        
        assert message_id is not None
        
        messages = hub.get_messages("agent-beta")
        assert len(messages) == 1
        assert messages[0].sender == "agent-alpha"

    def test_agent_request_help(self, hub, sample_agents):
        """Test agent broadcasting help request."""
        agent = CollaborationAgent("agent-alpha", hub)
        
        message_id = agent.request_help(
            description="Need assistance with task",
            priority=TaskPriority.HIGH,
            skills_needed=["code_review", "testing"],
        )
        
        assert message_id is not None
        
        # Other agents should receive the broadcast
        beta_messages = hub.get_messages("agent-beta")
        help_requests = [m for m in beta_messages if m.message_type == MessageType.HELP_REQUEST]
        assert len(help_requests) == 1
        assert help_requests[0].content["skills_needed"] == ["code_review", "testing"]

    def test_agent_create_task(self, hub):
        """Test agent creating tasks."""
        agent = CollaborationAgent("agent-alpha", hub)
        
        task_id = agent.create_task(
            title="My Task",
            description="Task description",
            assigned_to="agent-beta",
            priority=TaskPriority.NORMAL,
        )
        
        assert task_id is not None
        
        task = hub.get_task(task_id)
        assert task.created_by == "agent-alpha"
        assert task.assigned_to == "agent-beta"

    def test_agent_get_my_tasks(self, hub):
        """Test agent getting assigned tasks."""
        agent = CollaborationAgent("agent-beta", hub)
        
        hub.create_task(title="Task 1", description="Test", created_by="agent-alpha", assigned_to="agent-beta")
        hub.create_task(title="Task 2", description="Test", created_by="agent-gamma", assigned_to="agent-beta")
        hub.create_task(title="Task 3", description="Test", created_by="agent-alpha", assigned_to="agent-gamma")
        
        my_tasks = agent.get_my_tasks()
        assert len(my_tasks) == 2

    def test_agent_update_task(self, hub):
        """Test agent updating task status."""
        agent = CollaborationAgent("agent-beta", hub)
        
        task_id = hub.create_task(
            title="Test Task",
            description="Test",
            created_by="agent-alpha",
            assigned_to="agent-beta",
        )
        
        result = agent.update_task(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result={"output": "success"},
        )
        
        assert result is True
        
        task = hub.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED

    def test_agent_join_session(self, hub):
        """Test agent joining a session."""
        agent = CollaborationAgent("agent-beta", hub)
        
        session_id = hub.create_session(
            session_name="Test Session",
            participants=["agent-alpha"],
            created_by="agent-alpha",
        )
        
        result = agent.join_session(session_id)
        assert result is True
        
        session = hub.get_session(session_id)
        assert "agent-beta" in session["participants"]

    def test_agent_acknowledge_message(self, hub):
        """Test agent acknowledging messages."""
        agent = CollaborationAgent("agent-beta", hub)
        
        message_id = agent.send_message(
            recipient="agent-beta",
            content={"test": "data"},
            requires_ack=True,
        )
        
        result = agent.acknowledge_message(message_id)
        assert result is True
        
        # Should have no unread messages
        unread = agent.check_messages()
        assert len(unread) == 0


class TestCollaborationIntegration:
    """Integration tests for collaboration system."""

    def test_full_collaboration_workflow(self, hub, sample_agents):
        """Test a complete collaboration workflow."""
        # Agent-alpha creates a session
        alpha = CollaborationAgent("agent-alpha", hub)
        beta = CollaborationAgent("agent-beta", hub)
        gamma = CollaborationAgent("agent-gamma", hub)
        
        session_id = alpha.hub.create_session(
            session_name="Project Alpha",
            participants=["agent-alpha", "agent-beta", "agent-gamma"],
            created_by="agent-alpha",
            objective="Complete complex task together",
        )
        
        # Beta and Gamma join
        beta.join_session(session_id)
        gamma.join_session(session_id)
        
        # Alpha creates and assigns a task
        task_id = alpha.create_task(
            title="Research Phase",
            description="Gather requirements",
            assigned_to="agent-beta",
            priority=TaskPriority.HIGH,
        )
        
        # Beta starts working
        beta.update_task(task_id, TaskStatus.IN_PROGRESS)
        
        # Beta completes the task
        beta.update_task(
            task_id,
            TaskStatus.COMPLETED,
            result={"findings": ["requirement-1", "requirement-2"]},
        )
        
        # Alpha creates another task for Gamma
        task_id_2 = alpha.create_task(
            title="Implementation Phase",
            description="Implement based on requirements",
            assigned_to="agent-gamma",
            priority=TaskPriority.HIGH,
            dependencies=[task_id],
        )
        
        # Verify workflow
        session = hub.get_session(session_id)
        assert session is not None
        assert len(session["participants"]) == 3
        
        all_tasks = hub.list_tasks()
        assert len(all_tasks) == 2
        
        completed_tasks = hub.list_tasks(status_filter=TaskStatus.COMPLETED)
        assert len(completed_tasks) == 1

    def test_multi_agent_task_delegation(self, hub, sample_agents):
        """Test task delegation between multiple agents."""
        alpha = CollaborationAgent("agent-alpha", hub)
        beta = CollaborationAgent("agent-beta", hub)
        
        # Alpha creates a task and assigns to Beta
        task_id = alpha.create_task(
            title="Delegated Task",
            description="Please handle this",
            assigned_to="agent-beta",
            priority=TaskPriority.NORMAL,
        )
        
        # Beta receives notification
        beta_messages = beta.check_messages()
        assert len(beta_messages) == 1
        assert beta_messages[0].message_type == MessageType.TASK_ASSIGNMENT
        
        # Beta acknowledges
        beta.acknowledge_message(beta_messages[0].message_id)
        
        # Beta works on task
        beta.update_task(task_id, TaskStatus.IN_PROGRESS)
        
        # Beta needs help, requests assistance
        help_id = beta.request_help(
            description="Need input on edge cases",
            skills_needed=["testing"],
        )
        
        # Gamma can see the help request
        gamma_messages = hub.get_messages("agent-gamma")
        help_requests = [m for m in gamma_messages if m.message_type == MessageType.HELP_REQUEST]
        assert len(help_requests) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
