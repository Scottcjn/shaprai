# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Template engine for agent blueprints.

Templates define the complete specification for an Elyan-class agent:
model, personality, capabilities, ethics, and DriftLock configuration.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class AgentTemplate:
    """Blueprint for creating an Elyan-class agent.

    Attributes:
        name: Unique template identifier.
        model: Model configuration (base, quantization, min_vram_gb).
        personality: Style, communication tone, humor level.
        capabilities: List of agent capabilities (code_review, bounty_discovery, etc.).
        platforms: Target deployment platforms (github, bottube, moltbook).
        ethics_profile: Ethics framework identifier (default: sophiacore_default).
        driftlock: DriftLock configuration (enabled, check_interval, anchor_phrases).
        description: Human-readable description of what agents from this template do.
        version: Template version string.
        rtc_config: RustChain token configuration for bounties and fees.
        training: Per-phase training overrides, e.g.
            ``{"sft": {"use_dora": True}, "dpo": {"loss_type": ["apo_zero"]}}``.
    """

    name: str
    model: Dict[str, Any] = field(default_factory=dict)
    personality: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
    ethics_profile: str = "sophiacore_default"
    driftlock: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "check_interval": 25}
    )
    description: str = ""
    version: str = "1.0"
    rtc_config: Dict[str, Any] = field(default_factory=dict)
    training: Dict[str, Any] = field(default_factory=dict)


def load_template(path: str) -> AgentTemplate:
    """Load an agent template from a YAML file.

    Args:
        path: Path to the YAML template file.

    Returns:
        Parsed AgentTemplate instance.

    Raises:
        FileNotFoundError: If the template file doesn't exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    template_path = Path(path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {path}")

    with open(template_path, "r") as f:
        data = yaml.safe_load(f)

    return AgentTemplate(
        name=data.get("name", template_path.stem),
        model=data.get("model", {}),
        personality=data.get("personality", {}),
        capabilities=data.get("capabilities", []),
        platforms=data.get("platforms", []),
        ethics_profile=data.get("ethics_profile", "sophiacore_default"),
        driftlock=data.get("driftlock", {"enabled": True, "check_interval": 25}),
        description=data.get("description", ""),
        version=data.get("version", "1.0"),
        rtc_config=data.get("rtc_config", {}),
        training=data.get("training", {}),
    )


def save_template(template: AgentTemplate, path: str) -> None:
    """Save an agent template to a YAML file.

    Args:
        template: The AgentTemplate to serialize.
        path: Destination file path.
    """
    template_path = Path(path)
    template_path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(template)
    with open(template_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def fork_template(
    source_path: str,
    new_name: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> AgentTemplate:
    """Fork an existing template with optional overrides.

    Args:
        source_path: Path to the source template YAML.
        new_name: Name for the forked template.
        overrides: Dictionary of fields to override in the fork.

    Returns:
        New AgentTemplate with the fork applied.
    """
    source = load_template(source_path)
    data = asdict(source)
    data["name"] = new_name

    if overrides:
        for key, value in overrides.items():
            if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value

    return AgentTemplate(**data)


def list_templates(templates_dir: str) -> List[AgentTemplate]:
    """List all available templates in a directory.

    Args:
        templates_dir: Path to the templates directory.

    Returns:
        List of AgentTemplate instances found in the directory.
    """
    templates_path = Path(templates_dir)
    if not templates_path.exists():
        return []

    templates = []
    for yaml_file in sorted(templates_path.glob("*.yaml")):
        try:
            templates.append(load_template(str(yaml_file)))
        except Exception:
            continue  # Skip malformed templates

    return templates
