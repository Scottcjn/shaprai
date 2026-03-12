# Issue #9: Add Multi-Agent Collaboration Features

## Summary

This PR implements comprehensive multi-agent collaboration features for ShaprAI, enabling Elyan-class agents to work together on complex tasks through message passing, task delegation, and coordinated workflows.

## Changes

### New Module: `shaprai/core/collaboration.py`

Implements the core collaboration system:

- **AgentMessage**: Structured message format for inter-agent communication
- **Task**: Task representation with status, priority, dependencies, and results
- **CollaborationHub**: Central hub for message routing and task management
- **CollaborationAgent**: Simplified agent-side interface

### Key Features

1. **Message Passing**
   - Direct messages between specific agents
   - Broadcast messages to entire fleet
   - Message acknowledgment system
   - Priority levels (low, normal, high, critical)
   - Message types for different purposes

2. **Task Management**
   - Create tasks with title, description, priority, deadline
   - Assign tasks to specific agents
   - Track task status (pending, in_progress, blocked, completed, failed, cancelled)
   - Task dependencies for workflow modeling
   - Automatic notifications on assignment and completion
   - Result/error reporting

3. **Collaboration Sessions**
   - Create sessions with multiple participants
   - Session objectives and tracking
   - Join/leave sessions
   - Session-based task organization

4. **Help Requests**
   - Broadcast help requests to fleet
   - Specify required skills
   - Priority-based routing

### CLI Commands

Added new `shaprai collaborate` command group:

```bash
# Messaging
shaprai collaborate message <sender> <recipient> --content "..." --type coordination
shaprai collaborate check <agent> [--unread-only]
shaprai collaborate ack <agent> <message-id>
shaprai collaborate broadcast <sender> --message "..." --priority high

# Task Management
shaprai collaborate task-create <creator> --title "..." --description "..." --assign-to <agent>
shaprai collaborate task-list [--status pending] [--assignee <agent>] [--priority high]
shaprai collaborate task-update <task-id> <agent> --status completed --result "..."

# Sessions
shaprai collaborate session-create <creator> --name "..." --participants "a,b,c" --objective "..."
shaprai collaborate session-join <session-id> <agent>
shaprai collaborate session-info <session-id>
```

### Tests

Comprehensive test suite in `tests/test_collaboration.py`:
- 32 test cases covering all functionality
- Unit tests for Message, Task, Hub, and Agent classes
- Integration tests for full collaboration workflows
- All tests passing ✓

### Documentation

- `COLLABORATION_GUIDE.md`: Complete usage guide with examples
- API documentation in module docstrings
- CLI help text for all commands

## Usage Examples

### Python API

```python
from shaprai.core.collaboration import CollaborationAgent, TaskStatus

# Create agent interface
agent = CollaborationAgent("agent-alpha")

# Send a message
agent.send_message(
    recipient="agent-beta",
    content={"request": "Code review needed"},
    message_type="task_request",
    priority="high",
)

# Create and assign a task
task_id = agent.create_task(
    title="Review PR #42",
    description="Check for bugs and style",
    assigned_to="agent-beta",
    priority="high",
)

# Update task status
agent.update_task(
    task_id=task_id,
    status=TaskStatus.COMPLETED,
    result={"approved": True, "comments": ["minor fixes needed"]},
)

# Request help from fleet
agent.request_help(
    description="Debugging memory leak",
    skills_needed=["debugging", "performance"],
    priority="critical",
)
```

### Collaboration Workflow

```python
# Manager coordinates work across multiple agents
manager = CollaborationAgent("manager")
developer = CollaborationAgent("developer")
tester = CollaborationAgent("tester")

# Create session for project
session_id = manager.hub.create_session(
    session_name="Feature X Development",
    participants=["manager", "developer", "tester"],
    created_by="manager",
    objective="Build and ship Feature X",
)

# Developer joins session
developer.join_session(session_id)
tester.join_session(session_id)

# Manager creates task pipeline
research_task = manager.create_task(
    title="Research",
    description="Analyze requirements",
    assigned_to="developer",
    priority="high",
)

impl_task = manager.create_task(
    title="Implementation",
    description="Build the feature",
    assigned_to="developer",
    dependencies=[research_task],
)

test_task = manager.create_task(
    title="Testing",
    description="Write and run tests",
    assigned_to="tester",
    dependencies=[impl_task],
)
```

## Testing

All tests pass:

```bash
$ pytest tests/test_collaboration.py -v
============================= 32 passed in 0.34s ==============================
```

## Integration

The collaboration system integrates seamlessly with existing ShaprAI components:

- Uses same `~/.shaprai/agents/` directory structure
- Compatible with existing agent lifecycle states
- Works with FleetManager for agent discovery
- No breaking changes to existing APIs

## Benefits

1. **Enables Complex Workflows**: Agents can now coordinate on multi-stage tasks
2. **Improved Efficiency**: Task delegation allows specialization
3. **Better Visibility**: Central hub provides fleet-wide collaboration visibility
4. **Flexible Communication**: Multiple message types for different scenarios
5. **Scalable**: Works with any number of agents in the fleet

## Future Enhancements

Potential future improvements:

- Real-time message delivery (currently file-based)
- Message encryption for sensitive communications
- Task priority queue optimization
- Agent capability matching for automatic task assignment
- Collaboration analytics and metrics
- Integration with external collaboration tools

## Checklist

- [x] Core collaboration module implemented
- [x] CLI commands added
- [x] Comprehensive test suite
- [x] Documentation complete
- [x] No breaking changes
- [x] All tests passing
- [x] Code follows existing style guidelines

## Related Issues

Closes #9
