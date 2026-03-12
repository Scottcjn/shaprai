# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""ShaprAI core modules -- template engine, lifecycle, governance, fleet, driftlock, self-healing, collaboration."""

from shaprai.core.driftlock import (
    DriftLock,
    DriftLockConfig,
    DriftLockResult,
    create_driftlock_from_template,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_DRIFT_THRESHOLD,
)

from shaprai.core.self_healing import (
    SelfHealingManager,
    HealthStatus,
    FaultType,
    HealthCheckResult,
    RecoveryAction,
    enable_auto_healing,
    check_agent_health,
    heal_agent,
)

from shaprai.core.lifecycle import (
    AgentState,
    create_agent,
    transition_state,
    deploy_agent,
    retire_agent,
    get_agent_status,
    check_fleet_health,
    heal_all_agents,
)

from shaprai.core.collaboration import (
    CollaborationHub,
    CollaborationAgent,
    AgentMessage,
    Task,
    MessageType,
    TaskPriority,
    TaskStatus,
)

from shaprai.core.task_queue import (
    TaskQueueManager,
    QueueStrategy,
    QueuedTask,
)

__all__ = [
    # DriftLock
    "DriftLock",
    "DriftLockConfig",
    "DriftLockResult",
    "create_driftlock_from_template",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_DRIFT_THRESHOLD",
    # Self-Healing
    "SelfHealingManager",
    "HealthStatus",
    "FaultType",
    "HealthCheckResult",
    "RecoveryAction",
    "enable_auto_healing",
    "check_agent_health",
    "heal_agent",
    # Lifecycle
    "AgentState",
    "create_agent",
    "transition_state",
    "deploy_agent",
    "retire_agent",
    "get_agent_status",
    "check_fleet_health",
    "heal_all_agents",
    # Collaboration
    "CollaborationHub",
    "CollaborationAgent",
    "AgentMessage",
    "Task",
    "MessageType",
    "TaskPriority",
    "TaskStatus",
    # Task Queue
    "TaskQueueManager",
    "QueueStrategy",
    "QueuedTask",
]
