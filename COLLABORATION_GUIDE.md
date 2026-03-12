# Multi-Agent Collaboration Guide

This guide demonstrates how to use ShaprAI's multi-agent collaboration features to enable agents to work together on complex tasks.

## Overview

The collaboration system provides:

- **Message Passing**: Agents can send direct messages or broadcast to the fleet
- **Task Management**: Create, assign, and track tasks between agents
- **Collaboration Sessions**: Group agents into sessions for coordinated work
- **Help Requests**: Agents can broadcast requests for assistance

## Core Concepts

### AgentMessage

Messages are the primary communication method between agents:

```python
from shaprai.core.collaboration import AgentMessage, MessageType, TaskPriority

msg = AgentMessage(
    sender="agent-alpha",
    recipient="agent-beta",
    message_type=MessageType.TASK_REQUEST,
    content={"request": "Need help with code review"},
    priority=TaskPriority.HIGH,
)
```

### Task

Tasks represent work that can be delegated:

```python
from shaprai.core.collaboration import Task, TaskPriority, TaskStatus

task = Task(
    title="Review PR #42",
    description="Check for bugs and style issues",
    created_by="agent-alpha",
    assigned_to="agent-beta",
    priority=TaskPriority.HIGH,
    status=TaskStatus.PENDING,
)
```

### CollaborationHub

The central hub manages all collaboration:

```python
from shaprai.core.collaboration import CollaborationHub

hub = CollaborationHub()

# Send a message
hub.send_message(msg)

# Create a task
task_id = hub.create_task(
    title="My Task",
    description="Task description",
    created_by="agent-alpha",
    assigned_to="agent-beta",
    priority=TaskPriority.NORMAL,
)

# Get messages for an agent
messages = hub.get_messages("agent-beta")

# Update task status
hub.update_task_status(
    task_id=task_id,
    status=TaskStatus.COMPLETED,
    agent_name="agent-beta",
    result={"output": "success"},
)
```

### CollaborationAgent

Simplified interface for agents:

```python
from shaprai.core.collaboration import CollaborationAgent

agent = CollaborationAgent("agent-alpha")

# Check messages
messages = agent.check_messages()

# Send a message
agent.send_message(
    recipient="agent-beta",
    content={"key": "value"},
    message_type=MessageType.COORDINATION,
)

# Create and assign a task
task_id = agent.create_task(
    title="Important Task",
    description="Please complete this",
    assigned_to="agent-beta",
    priority=TaskPriority.HIGH,
)

# Request help from the fleet
help_id = agent.request_help(
    description="Need assistance with testing",
    skills_needed=["testing", "ci_cd"],
    priority=TaskPriority.HIGH,
)

# Update a task
agent.update_task(
    task_id=task_id,
    status=TaskStatus.COMPLETED,
    result={"findings": ["bug-1", "bug-2"]},
)
```

## CLI Usage

### Send a Message

```bash
shaprai collaborate message agent-alpha agent-beta \
  --content '{"request": "Code review needed"}' \
  --type task_request \
  --priority high
```

### Check Messages

```bash
shaprai collaborate check agent-beta
shaprai collaborate check agent-beta --unread-only
```

### Acknowledge a Message

```bash
shaprai collaborate ack agent-beta <message-id>
```

### Create a Task

```bash
shaprai collaborate task-create agent-alpha \
  --title "Review PR" \
  --description "Review pull request #42" \
  --assign-to agent-beta \
  --priority high
```

### List Tasks

```bash
shaprai collaborate task-list
shaprai collaborate task-list --status pending
shaprai collaborate task-list --assignee agent-beta
shaprai collaborate task-list --priority high
```

### Update a Task

```bash
shaprai collaborate task-update <task-id> agent-beta \
  --status completed \
  --result '{"output": "success"}'
```

### Create a Collaboration Session

```bash
shaprai collaborate session-create agent-alpha \
  --name "Project Alpha" \
  --participants "agent-alpha,agent-beta,agent-gamma" \
  --objective "Complete complex task together"
```

### Join a Session

```bash
shaprai collaborate session-join <session-id> agent-beta
```

### Get Session Info

```bash
shaprai collaborate session-info <session-id>
```

### Broadcast to Fleet

```bash
shaprai collaborate broadcast agent-alpha \
  --message "Important announcement" \
  --priority critical
```

## Example Workflows

### Workflow 1: Task Delegation

```python
from shaprai.core.collaboration import CollaborationAgent, TaskStatus

# Manager agent creates and delegates tasks
manager = CollaborationAgent("manager-agent")
worker = CollaborationAgent("worker-agent")

# Create and assign task
task_id = manager.create_task(
    title="Implement Feature X",
    description="Full implementation with tests",
    assigned_to="worker-agent",
    priority="high",
)

# Worker receives notification
messages = worker.check_messages()

# Worker starts task
worker.update_task(task_id, TaskStatus.IN_PROGRESS)

# Worker completes task
worker.update_task(
    task_id,
    TaskStatus.COMPLETED,
    result={"feature": "implemented", "tests": "passing"},
)

# Manager receives completion notification
manager_messages = manager.check_messages()
```

### Workflow 2: Collaborative Problem Solving

```python
from shaprai.core.collaboration import CollaborationAgent

# Create a collaboration session
alpha = CollaborationAgent("agent-alpha")
session_id = alpha.hub.create_session(
    session_name="Problem Solving Session",
    participants=["agent-alpha", "agent-beta", "agent-gamma"],
    created_by="agent-alpha",
    objective="Solve complex bug together",
)

# Other agents join
beta = CollaborationAgent("agent-beta")
beta.join_session(session_id)

gamma = CollaborationAgent("agent-gamma")
gamma.join_session(session_id)

# Alpha requests help
alpha.request_help(
    description="Debugging memory leak in production",
    skills_needed=["debugging", "performance"],
    priority="critical",
)

# Beta and Gamma receive the help request and can respond
```

### Workflow 3: Multi-Stage Pipeline

```python
from shaprai.core.collaboration import CollaborationAgent, TaskStatus

# Create a pipeline of dependent tasks
coordinator = CollaborationAgent("coordinator")

# Stage 1: Research
research_task = coordinator.create_task(
    title="Research Phase",
    description="Gather requirements and analyze",
    assigned_to="researcher-agent",
    priority="high",
)

# Stage 2: Implementation (depends on research)
impl_task = coordinator.create_task(
    title="Implementation Phase",
    description="Build the feature",
    assigned_to="developer-agent",
    priority="high",
    dependencies=[research_task],
)

# Stage 3: Testing (depends on implementation)
test_task = coordinator.create_task(
    title="Testing Phase",
    description="Write and run tests",
    assigned_to="tester-agent",
    priority="high",
    dependencies=[impl_task],
)

# Each agent updates their task when complete
# Dependent tasks can check if prerequisites are done
```

## Message Types

| Type | Description | Use Case |
|------|-------------|----------|
| `task_request` | Request a task from another agent | Asking for help |
| `task_assignment` | Assign a task to an agent | Delegating work |
| `task_update` | Update on task progress | Status reports |
| `task_complete` | Task completion notification | Finished work |
| `help_request` | Broadcast request for help | Need assistance |
| `status_query` | Query agent status | Check availability |
| `status_response` | Respond to status query | Report status |
| `coordination` | General coordination message | Team communication |

## Task Priorities

| Priority | Description | When to Use |
|----------|-------------|-------------|
| `low` | Low priority | Background tasks |
| `normal` | Default priority | Regular work |
| `high` | High priority | Important deadlines |
| `critical` | Critical priority | Urgent/blocking issues |

## Task Statuses

| Status | Description |
|--------|-------------|
| `pending` | Task not yet started |
| `in_progress` | Currently working |
| `blocked` | Waiting on dependencies |
| `completed` | Finished successfully |
| `failed` | Failed with error |
| `cancelled` | Cancelled by creator |

## Best Practices

1. **Use meaningful task titles and descriptions**: Clear communication reduces confusion
2. **Set appropriate priorities**: Don't mark everything as critical
3. **Acknowledge messages**: Let senders know you received important messages
4. **Update task status promptly**: Keep collaborators informed of progress
5. **Use dependencies wisely**: Model real workflow dependencies
6. **Include result data**: When completing tasks, provide useful output
7. **Broadcast sparingly**: Use broadcasts for important fleet-wide announcements

## Storage

Collaboration data is stored in `~/.shaprai/agents/.collaboration_hub/`:

- `message_queue.yaml`: All inter-agent messages
- `task_board.yaml`: Task board with all tasks
- `collaboration_sessions.yaml`: Active and past sessions

## Testing

Run the collaboration tests:

```bash
pytest tests/test_collaboration.py -v
```

## API Reference

See `shaprai/core/collaboration.py` for full API documentation.

Key classes:
- `CollaborationHub`: Central collaboration management
- `CollaborationAgent`: Agent-side interface
- `AgentMessage`: Message structure
- `Task`: Task structure
- `MessageType`: Message type enum
- `TaskPriority`: Priority levels
- `TaskStatus`: Task status enum
