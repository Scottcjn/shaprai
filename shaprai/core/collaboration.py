# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Multi-agent collaboration system.

Enables Elyan-class agents to collaborate on complex tasks through
message passing, task delegation, and coordinated workflows.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import yaml


class MessageType(Enum):
    """Types of inter-agent messages."""
    
    TASK_REQUEST = "task_request"
    TASK_ASSIGNMENT = "task_assignment"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    HELP_REQUEST = "help_request"
    STATUS_QUERY = "status_query"
    STATUS_RESPONSE = "status_response"
    COORDINATION = "coordination"


class TaskPriority(Enum):
    """Task priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """Task execution status."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentMessage:
    """Message passed between agents."""
    
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipient: str = ""  # Can be specific agent or "broadcast"
    message_type: MessageType = MessageType.COORDINATION
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: TaskPriority = TaskPriority.NORMAL
    requires_ack: bool = False
    acknowledged: bool = False
    in_reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "requires_ack": self.requires_ack,
            "acknowledged": self.acknowledged,
            "in_reply_to": self.in_reply_to,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        """Create from dictionary."""
        return cls(
            message_id=data["message_id"],
            sender=data["sender"],
            recipient=data["recipient"],
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            timestamp=data["timestamp"],
            priority=TaskPriority(data["priority"]),
            requires_ack=data["requires_ack"],
            acknowledged=data["acknowledged"],
            in_reply_to=data.get("in_reply_to"),
        )


@dataclass
class Task:
    """Represents a task that can be delegated between agents."""
    
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    assigned_to: Optional[str] = None
    created_by: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    dependencies: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deadline": self.deadline,
            "dependencies": self.dependencies,
            "subtasks": self.subtasks,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            title=data["title"],
            description=data["description"],
            assigned_to=data.get("assigned_to"),
            created_by=data["created_by"],
            priority=TaskPriority(data["priority"]),
            status=TaskStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            deadline=data.get("deadline"),
            dependencies=data.get("dependencies", []),
            subtasks=data.get("subtasks", []),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class CollaborationHub:
    """Central hub for multi-agent collaboration.
    
    The CollaborationHub manages message routing, task assignment,
    and coordination between agents in the fleet.
    
    Attributes:
        agents_dir: Base directory containing agent data.
        hub_dir: Directory for collaboration hub data.
    """
    
    def __init__(self, agents_dir: Optional[Path] = None) -> None:
        """Initialize the CollaborationHub.
        
        Args:
            agents_dir: Base directory for agent storage.
                Defaults to ~/.shaprai/agents.
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".shaprai" / "agents"
        self.agents_dir = agents_dir
        self.hub_dir = self.agents_dir / ".collaboration_hub"
        self.hub_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize storage files
        self.messages_file = self.hub_dir / "message_queue.yaml"
        self.tasks_file = self.hub_dir / "task_board.yaml"
        self.sessions_file = self.hub_dir / "collaboration_sessions.yaml"
        
        self._init_storage()
    
    def _init_storage(self) -> None:
        """Initialize storage files if they don't exist."""
        if not self.messages_file.exists():
            self._save_messages([])
        if not self.tasks_file.exists():
            self._save_tasks({})
        if not self.sessions_file.exists():
            self._save_sessions({})
    
    def _load_messages(self) -> List[Dict[str, Any]]:
        """Load message queue from disk."""
        try:
            with open(self.messages_file, "r") as f:
                return yaml.safe_load(f) or []
        except Exception:
            return []
    
    def _save_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Save message queue to disk."""
        with open(self.messages_file, "w") as f:
            yaml.dump(messages, f, default_flow_style=False, sort_keys=False)
    
    def _load_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Load task board from disk."""
        try:
            with open(self.tasks_file, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    
    def _save_tasks(self, tasks: Dict[str, Dict[str, Any]]) -> None:
        """Save task board to disk."""
        with open(self.tasks_file, "w") as f:
            yaml.dump(tasks, f, default_flow_style=False, sort_keys=False)
    
    def _load_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load collaboration sessions from disk."""
        try:
            with open(self.sessions_file, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    
    def _save_sessions(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Save collaboration sessions to disk."""
        with open(self.sessions_file, "w") as f:
            yaml.dump(sessions, f, default_flow_style=False, sort_keys=False)
    
    def send_message(self, message: AgentMessage) -> str:
        """Send a message to another agent or broadcast.
        
        Args:
            message: The message to send.
        
        Returns:
            Message ID for tracking.
        """
        messages = self._load_messages()
        messages.append(message.to_dict())
        self._save_messages(messages)
        return message.message_id
    
    def get_messages(self, recipient: str, unread_only: bool = True) -> List[AgentMessage]:
        """Get messages for a specific agent.
        
        Args:
            recipient: Agent name to get messages for.
            unread_only: Only return unacknowledged messages.
        
        Returns:
            List of messages for the agent.
        """
        messages = self._load_messages()
        result = []
        
        for msg_data in messages:
            msg = AgentMessage.from_dict(msg_data)
            if msg.recipient == recipient or msg.recipient == "broadcast":
                if not unread_only or not msg.acknowledged:
                    result.append(msg)
        
        return result
    
    def acknowledge_message(self, message_id: str, agent_name: str) -> bool:
        """Mark a message as acknowledged by an agent.
        
        Args:
            message_id: ID of the message to acknowledge.
            agent_name: Name of the acknowledging agent.
        
        Returns:
            True if message was found and acknowledged.
        """
        messages = self._load_messages()
        updated = False
        
        for msg_data in messages:
            if msg_data["message_id"] == message_id:
                if msg_data["recipient"] == agent_name or msg_data["recipient"] == "broadcast":
                    msg_data["acknowledged"] = True
                    updated = True
                    break
        
        if updated:
            self._save_messages(messages)
        
        return updated
    
    def create_task(
        self,
        title: str,
        description: str,
        created_by: str,
        assigned_to: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        deadline: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new task.
        
        Args:
            title: Task title.
            description: Task description.
            created_by: Agent creating the task.
            assigned_to: Agent to assign the task to (optional).
            priority: Task priority level.
            deadline: Optional deadline timestamp.
            dependencies: List of task IDs this task depends on.
            metadata: Additional task metadata.
        
        Returns:
            Task ID for tracking.
        """
        task = Task(
            title=title,
            description=description,
            created_by=created_by,
            assigned_to=assigned_to,
            priority=priority,
            deadline=deadline,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        
        tasks = self._load_tasks()
        tasks[task.task_id] = task.to_dict()
        self._save_tasks(tasks)
        
        # If assigned, send notification message
        if assigned_to:
            notification = AgentMessage(
                sender=created_by,
                recipient=assigned_to,
                message_type=MessageType.TASK_ASSIGNMENT,
                content={"task_id": task.task_id, "title": title},
                priority=priority,
            )
            self.send_message(notification)
        
        return task.task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID.
        
        Args:
            task_id: Task identifier.
        
        Returns:
            Task object or None if not found.
        """
        tasks = self._load_tasks()
        task_data = tasks.get(task_id)
        if task_data:
            return Task.from_dict(task_data)
        return None
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        agent_name: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the status of a task.
        
        Args:
            task_id: Task identifier.
            status: New task status.
            agent_name: Agent updating the task.
            result: Optional task result.
            error: Optional error message.
        
        Returns:
            True if task was updated successfully.
        """
        tasks = self._load_tasks()
        
        if task_id not in tasks:
            return False
        
        task_data = tasks[task_id]
        
        # Verify agent is assigned to this task
        if task_data.get("assigned_to") != agent_name:
            return False
        
        task_data["status"] = status.value
        task_data["updated_at"] = time.time()
        
        if result is not None:
            task_data["result"] = result
        if error:
            task_data["error"] = error
        
        tasks[task_id] = task_data
        self._save_tasks(tasks)
        
        # Notify task creator
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            notification = AgentMessage(
                sender=agent_name,
                recipient=task_data["created_by"],
                message_type=MessageType.TASK_COMPLETE,
                content={
                    "task_id": task_id,
                    "status": status.value,
                    "result": result,
                    "error": error,
                },
            )
            self.send_message(notification)
        
        return True
    
    def assign_task(self, task_id: str, agent_name: str, assigned_by: str) -> bool:
        """Assign a task to an agent.
        
        Args:
            task_id: Task identifier.
            agent_name: Agent to assign the task to.
            assigned_by: Agent making the assignment.
        
        Returns:
            True if task was assigned successfully.
        """
        tasks = self._load_tasks()
        
        if task_id not in tasks:
            return False
        
        task_data = tasks[task_id]
        old_assignee = task_data.get("assigned_to")
        
        task_data["assigned_to"] = agent_name
        task_data["updated_at"] = time.time()
        tasks[task_id] = task_data
        self._save_tasks(tasks)
        
        # Notify the assigned agent
        notification = AgentMessage(
            sender=assigned_by,
            recipient=agent_name,
            message_type=MessageType.TASK_ASSIGNMENT,
            content={
                "task_id": task_id,
                "title": task_data["title"],
                "previous_assignee": old_assignee,
            },
            priority=TaskPriority(task_data["priority"]),
        )
        self.send_message(notification)
        
        return True
    
    def list_tasks(
        self,
        status_filter: Optional[TaskStatus] = None,
        assignee_filter: Optional[str] = None,
        priority_filter: Optional[TaskPriority] = None,
    ) -> List[Task]:
        """List tasks with optional filters.
        
        Args:
            status_filter: Filter by task status.
            assignee_filter: Filter by assigned agent.
            priority_filter: Filter by priority level.
        
        Returns:
            List of matching tasks.
        """
        tasks = self._load_tasks()
        result = []
        
        for task_data in tasks.values():
            if status_filter and task_data["status"] != status_filter.value:
                continue
            if assignee_filter and task_data.get("assigned_to") != assignee_filter:
                continue
            if priority_filter and task_data["priority"] != priority_filter.value:
                continue
            result.append(Task.from_dict(task_data))
        
        return result
    
    def create_session(
        self,
        session_name: str,
        participants: List[str],
        created_by: str,
        objective: str = "",
    ) -> str:
        """Create a collaboration session.
        
        Args:
            session_name: Name for the session.
            participants: List of agent names participating.
            created_by: Agent creating the session.
            objective: Session objective or goal.
        
        Returns:
            Session ID.
        """
        session_id = str(uuid.uuid4())
        
        session = {
            "session_id": session_id,
            "name": session_name,
            "participants": participants,
            "created_by": created_by,
            "objective": objective,
            "created_at": time.time(),
            "status": "active",
            "tasks": [],
            "message_log": [],
        }
        
        sessions = self._load_sessions()
        sessions[session_id] = session
        self._save_sessions(sessions)
        
        # Notify all participants
        for participant in participants:
            if participant != created_by:
                invitation = AgentMessage(
                    sender=created_by,
                    recipient=participant,
                    message_type=MessageType.COORDINATION,
                    content={
                        "session_id": session_id,
                        "session_name": session_name,
                        "objective": objective,
                        "invitation": True,
                    },
                )
                self.send_message(invitation)
        
        return session_id
    
    def join_session(self, session_id: str, agent_name: str) -> bool:
        """Join an existing collaboration session.
        
        Args:
            session_id: Session identifier.
            agent_name: Agent joining the session.
        
        Returns:
            True if successfully joined.
        """
        sessions = self._load_sessions()
        
        if session_id not in sessions:
            return False
        
        session = sessions[session_id]
        if agent_name not in session["participants"]:
            session["participants"].append(agent_name)
            session["updated_at"] = time.time()
            sessions[session_id] = session
            self._save_sessions(sessions)
        
        return True
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a collaboration session by ID.
        
        Args:
            session_id: Session identifier.
        
        Returns:
            Session data or None if not found.
        """
        sessions = self._load_sessions()
        return sessions.get(session_id)
    
    def get_agent_tasks(self, agent_name: str) -> List[Task]:
        """Get all tasks assigned to an agent.
        
        Args:
            agent_name: Agent name.
        
        Returns:
            List of tasks assigned to the agent.
        """
        return self.list_tasks(assignee_filter=agent_name)
    
    def get_pending_messages_count(self, agent_name: str) -> int:
        """Get count of unacknowledged messages for an agent.
        
        Args:
            agent_name: Agent name.
        
        Returns:
            Number of pending messages.
        """
        messages = self.get_messages(agent_name, unread_only=True)
        return len(messages)
    
    def broadcast_to_fleet(
        self,
        message: str,
        sender: str,
        message_type: MessageType = MessageType.COORDINATION,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> int:
        """Broadcast a message to all agents in the fleet.
        
        Args:
            message: Message content.
            sender: Sending agent name.
            message_type: Type of message.
            priority: Message priority.
        
        Returns:
            Number of agents that received the broadcast.
        """
        broadcast_msg = AgentMessage(
            sender=sender,
            recipient="broadcast",
            message_type=message_type,
            content={"message": message},
            priority=priority,
        )
        
        self.send_message(broadcast_msg)
        
        # Count agents (approximate by listing agent directories)
        count = 0
        if self.agents_dir.exists():
            for agent_dir in self.agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                    count += 1
        
        return count


class CollaborationAgent:
    """Agent-side collaboration interface.
    
    This class provides a simple interface for agents to interact
    with the collaboration system.
    
    Attributes:
        agent_name: Name of this agent.
        hub: CollaborationHub instance.
    """
    
    def __init__(self, agent_name: str, hub: Optional[CollaborationHub] = None) -> None:
        """Initialize the collaboration agent.
        
        Args:
            agent_name: Name of this agent.
            hub: CollaborationHub instance (created if not provided).
        """
        self.agent_name = agent_name
        self.hub = hub or CollaborationHub()
    
    def check_messages(self) -> List[AgentMessage]:
        """Check for new messages.
        
        Returns:
            List of new messages.
        """
        return self.hub.get_messages(self.agent_name, unread_only=True)
    
    def send_message(
        self,
        recipient: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.COORDINATION,
        priority: TaskPriority = TaskPriority.NORMAL,
        requires_ack: bool = False,
    ) -> str:
        """Send a message to another agent.
        
        Args:
            recipient: Target agent name.
            content: Message content.
            message_type: Type of message.
            priority: Message priority.
            requires_ack: Whether acknowledgment is required.
        
        Returns:
            Message ID.
        """
        message = AgentMessage(
            sender=self.agent_name,
            recipient=recipient,
            message_type=message_type,
            content=content,
            priority=priority,
            requires_ack=requires_ack,
        )
        return self.hub.send_message(message)
    
    def request_help(
        self,
        description: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        skills_needed: Optional[List[str]] = None,
    ) -> str:
        """Broadcast a help request to the fleet.
        
        Args:
            description: Description of what help is needed.
            priority: Request priority.
            skills_needed: List of skills/capabilities needed.
        
        Returns:
            Message ID.
        """
        return self.send_message(
            recipient="broadcast",
            content={
                "help_request": True,
                "description": description,
                "skills_needed": skills_needed or [],
                "requester": self.agent_name,
            },
            message_type=MessageType.HELP_REQUEST,
            priority=priority,
        )
    
    def create_task(
        self,
        title: str,
        description: str,
        assigned_to: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        deadline: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """Create a new task.
        
        Args:
            title: Task title.
            description: Task description.
            assigned_to: Agent to assign to (optional).
            priority: Task priority.
            deadline: Optional deadline timestamp.
            dependencies: List of task IDs this task depends on.
        
        Returns:
            Task ID.
        """
        return self.hub.create_task(
            title=title,
            description=description,
            created_by=self.agent_name,
            assigned_to=assigned_to,
            priority=priority,
            deadline=deadline,
            dependencies=dependencies,
        )
    
    def get_my_tasks(self) -> List[Task]:
        """Get tasks assigned to this agent.
        
        Returns:
            List of assigned tasks.
        """
        return self.hub.get_agent_tasks(self.agent_name)
    
    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update a task's status.
        
        Args:
            task_id: Task identifier.
            status: New status.
            result: Optional result data.
            error: Optional error message.
        
        Returns:
            True if updated successfully.
        """
        return self.hub.update_task_status(
            task_id=task_id,
            status=status,
            agent_name=self.agent_name,
            result=result,
            error=error,
        )
    
    def join_session(self, session_id: str) -> bool:
        """Join a collaboration session.
        
        Args:
            session_id: Session identifier.
        
        Returns:
            True if joined successfully.
        """
        return self.hub.join_session(session_id, self.agent_name)
    
    def acknowledge_message(self, message_id: str) -> bool:
        """Acknowledge receipt of a message.
        
        Args:
            message_id: Message identifier.
        
        Returns:
            True if acknowledged successfully.
        """
        return self.hub.acknowledge_message(message_id, self.agent_name)
