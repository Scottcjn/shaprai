# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Agent lifecycle management.

Manages the state machine for Elyan-class agents from creation through
deployment and eventual retirement.

Lifecycle: CREATED -> TRAINING -> SANCTUARY -> GRADUATED -> DEPLOYED -> RETIRED
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from shaprai.core.template_engine import AgentTemplate


class AgentState(Enum):
    """Agent lifecycle states."""

    CREATED = "created"
    TRAINING = "training"
    SANCTUARY = "sanctuary"
    DEPLOYED = "deployed"
    GRADUATED = "graduated"
    RETIRED = "retired"


def create_agent(
    name: str,
    template: AgentTemplate,
    agents_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a new agent from a template.

    Creates the agent directory, writes the manifest, and sets the initial
    state to CREATED.

    Args:
        name: Unique agent identifier.
        template: AgentTemplate defining the agent's configuration.
        agents_dir: Base directory for agent storage. Defaults to ~/.shaprai/agents.

    Returns:
        Dictionary with the agent's initial manifest.

    Raises:
        FileExistsError: If an agent with this name already exists.
    """
    if agents_dir is None:
        agents_dir = Path.home() / ".shaprai" / "agents"

    agent_dir = agents_dir / name
    if agent_dir.exists():
        raise FileExistsError(f"Agent '{name}' already exists at {agent_dir}")

    agent_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name,
        "state": AgentState.CREATED.value,
        "template": template.name,
        "model": template.model,
        "personality": template.personality,
        "capabilities": template.capabilities,
        "platforms": template.platforms,
        "ethics_profile": template.ethics_profile,
        "driftlock": template.driftlock,
        "rtc_config": template.rtc_config,
        "training": template.training,
        "created_at": time.time(),
        "updated_at": time.time(),
        "training_history": [],
        "deployment_history": [],
    }

    manifest_path = agent_dir / "manifest.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    return manifest


def _load_manifest(name: str, agents_dir: Path) -> Dict[str, Any]:
    """Load an agent's manifest from disk."""
    manifest_path = agents_dir / name / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Agent '{name}' not found at {agents_dir / name}")
    with open(manifest_path, "r") as f:
        return yaml.safe_load(f)


def _save_manifest(name: str, manifest: Dict[str, Any], agents_dir: Path) -> None:
    """Save an agent's manifest to disk."""
    manifest["updated_at"] = time.time()
    manifest_path = agents_dir / name / "manifest.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)


def transition_state(
    name: str,
    new_state: AgentState,
    agents_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Transition an agent to a new lifecycle state.

    Args:
        name: Agent identifier.
        new_state: Target state.
        agents_dir: Base directory for agents.

    Returns:
        Updated manifest.
    """
    if agents_dir is None:
        agents_dir = Path.home() / ".shaprai" / "agents"

    manifest = _load_manifest(name, agents_dir)
    old_state = manifest["state"]
    manifest["state"] = new_state.value
    manifest.setdefault("state_history", []).append(
        {
            "from": old_state,
            "to": new_state.value,
            "timestamp": time.time(),
        }
    )
    _save_manifest(name, manifest, agents_dir)
    return manifest


def deploy_agent(
    name: str,
    platforms: List[str],
    agents_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Deploy an agent to the specified platforms.

    Args:
        name: Agent identifier.
        platforms: List of platform names to deploy to.
        agents_dir: Base directory for agents.

    Returns:
        Updated manifest with deployment record.
    """
    if agents_dir is None:
        agents_dir = Path.home() / ".shaprai" / "agents"

    manifest = _load_manifest(name, agents_dir)
    manifest["state"] = AgentState.DEPLOYED.value
    manifest["platforms"] = platforms
    manifest.setdefault("deployment_history", []).append(
        {
            "platforms": platforms,
            "timestamp": time.time(),
        }
    )
    _save_manifest(name, manifest, agents_dir)
    return manifest


def retire_agent(
    name: str,
    agents_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Retire an agent, removing it from active duty.

    Args:
        name: Agent identifier.
        agents_dir: Base directory for agents.

    Returns:
        Updated manifest.
    """
    return transition_state(name, AgentState.RETIRED, agents_dir)


def get_agent_status(
    name: str,
    agents_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Get the current status of an agent.

    Args:
        name: Agent identifier.
        agents_dir: Base directory for agents.

    Returns:
        Agent manifest dictionary.
    """
    if agents_dir is None:
        agents_dir = Path.home() / ".shaprai" / "agents"
    return _load_manifest(name, agents_dir)
