# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for task queue management."""

import pytest
import time
from pathlib import Path
import tempfile
import shutil

from shaprai.core.task_queue import TaskQueueManager, QueueStrategy


@pytest.fixture
def temp_agents_dir():
    """Create a temporary directory for agent data."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def queue_manager(temp_agents_dir):
    """Create a TaskQueueManager instance."""
    return TaskQueueManager(agents_dir=temp_agents_dir)


class TestTaskQueueManager:
    """Test suite for TaskQueueManager."""
    
    def test_init(self, queue_manager):
        """Test queue manager initialization."""
        assert queue_manager.queue_dir.exists()
        assert queue_manager.queue_file.exists()
        assert queue_manager.agents_file.exists()
        assert queue_manager.history_file.exists()
    
    def test_enqueue_task(self, queue_manager):
        """Test adding a task to the queue."""
        task_id = queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
            priority="normal",
            created_by="agent1",
        )
        
        assert task_id == "task-001"
        assert queue_manager.get_queue_size() == 1
        
        task = queue_manager.get_task_by_id("task-001")
        assert task is not None
        assert task["title"] == "Test Task"
        assert task["priority"] == "normal"
        assert task["status"] == "queued"
    
    def test_enqueue_priority_ordering(self, queue_manager):
        """Test that tasks are ordered by priority."""
        # Add tasks with different priorities
        queue_manager.enqueue_task("task-low", "Low Priority", "Desc", priority="low")
        queue_manager.enqueue_task("task-critical", "Critical Priority", "Desc", priority="critical")
        queue_manager.enqueue_task("task-high", "High Priority", "Desc", priority="high")
        
        # Peek at queue - should be ordered by priority
        tasks = queue_manager.peek_queue(limit=10)
        assert len(tasks) == 3
        # Critical should be first
        assert tasks[0]["priority"] == "critical"
        # High should be second
        assert tasks[1]["priority"] == "high"
        # Low should be last
        assert tasks[2]["priority"] == "low"
    
    def test_dequeue_task(self, queue_manager):
        """Test removing a task from the queue."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
            priority="high",
        )
        
        task = queue_manager.dequeue_task()
        assert task is not None
        assert task["task_id"] == "task-001"
        assert task["status"] == "assigned"
        assert queue_manager.get_queue_size() == 0
    
    def test_dequeue_with_agent_assignment(self, queue_manager):
        """Test dequeuing a task and assigning to an agent."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
            priority="normal",
        )
        
        task = queue_manager.dequeue_task(agent_name="agent1")
        assert task is not None
        assert task["assigned_to"] == "agent1"
        
        # Check agent load
        load = queue_manager.get_agent_load("agent1")
        assert load["active_tasks"] == 1
    
    def test_assign_task_to_agent(self, queue_manager):
        """Test assigning a specific task to an agent."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
        )
        
        success = queue_manager.assign_task_to_agent("task-001", "agent1")
        assert success is True
        
        task = queue_manager.get_task_by_id("task-001")
        assert task["assigned_to"] == "agent1"
        assert task["status"] == "assigned"
    
    def test_complete_task(self, queue_manager):
        """Test marking a task as completed."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
        )
        queue_manager.assign_task_to_agent("task-001", "agent1")
        
        result = {"output": "success"}
        success = queue_manager.complete_task("task-001", result)
        assert success is True
        
        # Task should be removed from queue
        task = queue_manager.get_task_by_id("task-001")
        assert task is None
        
        # Agent load should be decremented
        load = queue_manager.get_agent_load("agent1")
        assert load["active_tasks"] == 0
        assert load["total_completed"] == 1
    
    def test_fail_task(self, queue_manager):
        """Test marking a task as failed."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
        )
        queue_manager.assign_task_to_agent("task-001", "agent1")
        
        error_msg = "Timeout exceeded"
        success = queue_manager.fail_task("task-001", error_msg)
        assert success is True
        
        # Task should be removed from queue
        task = queue_manager.get_task_by_id("task-001")
        assert task is None
        
        # Check history
        history = queue_manager._load_history()
        assert len(history) == 1
        assert history[0]["status"] == "failed"
        assert history[0]["error"] == error_msg
    
    def test_get_queue_statistics(self, queue_manager):
        """Test getting queue statistics."""
        # Add some tasks
        queue_manager.enqueue_task("task-1", "Task 1", "Desc", priority="critical")
        queue_manager.enqueue_task("task-2", "Task 2", "Desc", priority="high")
        queue_manager.enqueue_task("task-3", "Task 3", "Desc", priority="normal")
        queue_manager.enqueue_task("task-4", "Task 4", "Desc", priority="low")
        
        # Complete one task
        queue_manager.assign_task_to_agent("task-1", "agent1")
        queue_manager.complete_task("task-1")
        
        stats = queue_manager.get_queue_statistics()
        
        assert stats["queue_size"] == 3
        assert stats["priority_distribution"]["critical"] == 0
        assert stats["priority_distribution"]["high"] == 1
        assert stats["priority_distribution"]["normal"] == 1
        assert stats["priority_distribution"]["low"] == 1
        assert stats["total_completed"] == 1
        assert stats["total_failed"] == 0
    
    def test_agent_load_tracking(self, queue_manager):
        """Test agent load tracking."""
        # Assign multiple tasks to different agents
        queue_manager.enqueue_task("task-1", "Task 1", "Desc")
        queue_manager.enqueue_task("task-2", "Task 2", "Desc")
        queue_manager.enqueue_task("task-3", "Task 3", "Desc")
        
        queue_manager.assign_task_to_agent("task-1", "agent1")
        queue_manager.assign_task_to_agent("task-2", "agent1")
        queue_manager.assign_task_to_agent("task-3", "agent2")
        
        load1 = queue_manager.get_agent_load("agent1")
        load2 = queue_manager.get_agent_load("agent2")
        
        assert load1["active_tasks"] == 2
        assert load2["active_tasks"] == 1
        
        # Complete a task for agent1
        queue_manager.complete_task("task-1")
        
        load1 = queue_manager.get_agent_load("agent1")
        assert load1["active_tasks"] == 1
        assert load1["total_completed"] == 1
    
    def test_reprioritize_task(self, queue_manager):
        """Test changing task priority."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
            priority="low",
        )
        
        success = queue_manager.reprioritize_task("task-001", "critical")
        assert success is True
        
        task = queue_manager.get_task_by_id("task-001")
        assert task["priority"] == "critical"
    
    def test_remove_task(self, queue_manager):
        """Test removing a task without completing it."""
        queue_manager.enqueue_task(
            task_id="task-001",
            title="Test Task",
            description="Test Description",
        )
        queue_manager.assign_task_to_agent("task-001", "agent1")
        
        success = queue_manager.remove_task("task-001")
        assert success is True
        assert queue_manager.get_queue_size() == 0
        
        # Agent load should be decremented
        load = queue_manager.get_agent_load("agent1")
        assert load["active_tasks"] == 0
    
    def test_get_tasks_by_agent(self, queue_manager):
        """Test getting all tasks for an agent."""
        queue_manager.enqueue_task("task-1", "Task 1", "Desc")
        queue_manager.enqueue_task("task-2", "Task 2", "Desc")
        queue_manager.enqueue_task("task-3", "Task 3", "Desc")
        
        queue_manager.assign_task_to_agent("task-1", "agent1")
        queue_manager.assign_task_to_agent("task-2", "agent1")
        queue_manager.assign_task_to_agent("task-3", "agent2")
        
        agent1_tasks = queue_manager.get_tasks_by_agent("agent1")
        assert len(agent1_tasks) == 2
        assert all(t["assigned_to"] == "agent1" for t in agent1_tasks)
    
    def test_overdue_tasks(self, queue_manager):
        """Test getting overdue tasks."""
        current_time = time.time()
        past_deadline = current_time - 3600  # 1 hour ago
        future_deadline = current_time + 3600  # 1 hour from now
        
        queue_manager.enqueue_task(
            "task-1", "Overdue Task", "Desc",
            deadline=past_deadline,
        )
        queue_manager.enqueue_task(
            "task-2", "Future Task", "Desc",
            deadline=future_deadline,
        )
        
        overdue = queue_manager.get_overdue_tasks()
        assert len(overdue) == 1
        assert overdue[0]["task_id"] == "task-1"
    
    def test_clear_queue(self, queue_manager):
        """Test clearing all tasks from the queue."""
        queue_manager.enqueue_task("task-1", "Task 1", "Desc")
        queue_manager.enqueue_task("task-2", "Task 2", "Desc")
        queue_manager.enqueue_task("task-3", "Task 3", "Desc")
        
        count = queue_manager.clear_queue()
        assert count == 3
        assert queue_manager.get_queue_size() == 0
    
    def test_dequeue_empty_queue(self, queue_manager):
        """Test dequeuing from an empty queue."""
        task = queue_manager.dequeue_task()
        assert task is None
    
    def test_get_nonexistent_task(self, queue_manager):
        """Test getting a task that doesn't exist."""
        task = queue_manager.get_task_by_id("nonexistent")
        assert task is None
    
    def test_complete_nonexistent_task(self, queue_manager):
        """Test completing a task that doesn't exist."""
        success = queue_manager.complete_task("nonexistent")
        assert success is False
    
    def test_persistence(self, temp_agents_dir):
        """Test that queue data persists across manager instances."""
        # Create manager and add task
        manager1 = TaskQueueManager(agents_dir=temp_agents_dir)
        manager1.enqueue_task("task-001", "Persistent Task", "Desc", priority="high")
        
        # Create new manager instance
        manager2 = TaskQueueManager(agents_dir=temp_agents_dir)
        
        # Task should still be there
        task = manager2.get_task_by_id("task-001")
        assert task is not None
        assert task["title"] == "Persistent Task"
        assert manager2.get_queue_size() == 1


class TestQueueStrategy:
    """Test different queue strategies."""
    
    def test_priority_strategy(self, temp_agents_dir):
        """Test priority-based scheduling."""
        manager = TaskQueueManager(
            agents_dir=temp_agents_dir,
            strategy=QueueStrategy.PRIORITY,
        )
        
        # Add tasks in random order
        manager.enqueue_task("task-1", "Low", "Desc", priority="low")
        manager.enqueue_task("task-2", "Critical", "Desc", priority="critical")
        manager.enqueue_task("task-3", "High", "Desc", priority="high")
        
        # Should dequeue in priority order
        task1 = manager.dequeue_task()
        assert task1["priority"] == "critical"
        
        task2 = manager.dequeue_task()
        assert task2["priority"] == "high"
        
        task3 = manager.dequeue_task()
        assert task3["priority"] == "low"
    
    def test_load_balancing(self, temp_agents_dir):
        """Test load balancing strategy."""
        manager = TaskQueueManager(
            agents_dir=temp_agents_dir,
            strategy=QueueStrategy.LOAD_BALANCE,
        )
        
        # Add tasks
        manager.enqueue_task("task-1", "Task 1", "Desc")
        manager.enqueue_task("task-2", "Task 2", "Desc")
        
        # Assign to different agents
        task1 = manager.dequeue_task("agent1")
        task2 = manager.dequeue_task("agent2")
        
        assert task1["assigned_to"] == "agent1"
        assert task2["assigned_to"] == "agent2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
