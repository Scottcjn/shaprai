# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Fleet management for Elyan-class agents.

Provides a unified view of all managed agents, their states, health,
and deployment status. Supports broadcasting updates and coordinating
multi-agent operations.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

from shaprai.core.lifecycle import AgentState, agent_path


class FleetManager:
    """Manages a fleet of Elyan-class agents.

    The FleetManager provides centralized visibility and control over
    all agents in the ShaprAI ecosystem.

    Attributes:
        agents_dir: Base directory containing agent subdirectories.
    """

    def __init__(self, agents_dir: Optional[Path] = None) -> None:
        """Initialize the FleetManager.

        Args:
            agents_dir: Base directory for agent storage.
                Defaults to ~/.shaprai/agents.
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".shaprai" / "agents"
        self.agents_dir = agents_dir
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def register_agent(self, agent_manifest: Dict[str, Any]) -> None:
        """Register a new agent with the fleet.

        Args:
            agent_manifest: The agent's manifest dictionary. Must contain 'name'.

        Raises:
            ValueError: If the name would place the agent outside agents_dir.
        """
        name = agent_manifest["name"]
        agent_dir = agent_path(self.agents_dir, name)
        agent_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = agent_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(agent_manifest, f, default_flow_style=False, sort_keys=False)

    def list_agents(
        self,
        state_filter: Optional[AgentState] = None,
        platform_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all managed agents with optional filters.

        Args:
            state_filter: Only return agents in this state.
            platform_filter: Only return agents deployed to this platform.

        Returns:
            List of agent manifest dictionaries.
        """
        return [
            manifest
            for _, manifest in self._iter_agents(state_filter, platform_filter)
        ]

    def _iter_agents(
        self,
        state_filter: Optional[AgentState] = None,
        platform_filter: Optional[str] = None,
    ) -> Iterator[Tuple[Path, Dict[str, Any]]]:
        """Yield (agent directory, manifest) for each readable agent."""
        if not self.agents_dir.exists():
            return

        for agent_dir in sorted(self.agents_dir.iterdir()):
            manifest_path = agent_dir / "manifest.yaml"
            if not manifest_path.is_file():
                continue

            try:
                with open(manifest_path, "r") as f:
                    manifest = yaml.safe_load(f)
            except Exception:
                continue

            if manifest is None:
                continue

            # Apply filters
            if state_filter and manifest.get("state") != state_filter.value:
                continue
            if platform_filter and platform_filter not in manifest.get("platforms", []):
                continue

            yield agent_dir, manifest

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent's manifest.

        Args:
            name: Agent identifier.

        Returns:
            Agent manifest dictionary, or None if not found.

        Raises:
            ValueError: If the name would resolve outside agents_dir.
        """
        manifest_path = agent_path(self.agents_dir, name) / "manifest.yaml"
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r") as f:
            return yaml.safe_load(f)

    def broadcast_update(
        self, message: str, state_filter: Optional[AgentState] = None
    ) -> int:
        """Broadcast an update message to fleet agents.

        Writes the message to each agent's update log for consumption
        on their next check-in cycle.

        Args:
            message: Update message to broadcast.
            state_filter: Only broadcast to agents in this state.

        Returns:
            Number of agents that received the broadcast.
        """
        count = 0

        for agent_dir, _ in self._iter_agents(state_filter=state_filter):
            # Write by directory, never by the manifest's (untrusted) 'name'
            try:
                updates_path = agent_path(self.agents_dir, agent_dir.name) / "updates.yaml"
            except ValueError:
                continue  # e.g. a symlink pointing outside agents_dir

            updates: List[Dict[str, Any]] = []
            if updates_path.exists():
                with open(updates_path, "r") as f:
                    updates = yaml.safe_load(f) or []

            updates.append(
                {
                    "message": message,
                    "timestamp": time.time(),
                    "acknowledged": False,
                }
            )

            with open(updates_path, "w") as f:
                yaml.dump(updates, f, default_flow_style=False, sort_keys=False)

            count += 1

        return count

    def get_fleet_health(self) -> Dict[str, Any]:
        """Get aggregate health metrics for the entire fleet.

        Returns:
            Dictionary with fleet-wide health statistics.
        """
        agents = self.list_agents()
        total = len(agents)

        if total == 0:
            return {
                "total_agents": 0,
                "by_state": {},
                "platforms": {},
                "health": "empty",
            }

        # Count agents by state
        by_state: Dict[str, int] = {}
        for agent in agents:
            state = agent.get("state", "unknown")
            by_state[state] = by_state.get(state, 0) + 1

        # Count agents by platform
        platforms: Dict[str, int] = {}
        for agent in agents:
            for platform in agent.get("platforms", []):
                platforms[platform] = platforms.get(platform, 0) + 1

        # Determine overall health
        deployed = by_state.get(AgentState.DEPLOYED.value, 0)
        graduated = by_state.get(AgentState.GRADUATED.value, 0)
        retired = by_state.get(AgentState.RETIRED.value, 0)

        active_ratio = (deployed + graduated) / total if total > 0 else 0

        if active_ratio >= 0.7:
            health = "healthy"
        elif active_ratio >= 0.4:
            health = "fair"
        else:
            health = "needs_attention"

        return {
            "total_agents": total,
            "by_state": by_state,
            "platforms": platforms,
            "active_ratio": round(active_ratio, 2),
            "health": health,
        }
