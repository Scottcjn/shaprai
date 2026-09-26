# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""A2A (Agent2Agent) Agent Cards for Elyan-class agents.

An Agent Card is how other agents discover what an agent does and how to
reach it. Each deployed agent publishes its own card at
``/.well-known/agent-card.json`` on its domain. Cards generated here follow
the A2A 1.0 specification, whose JSON fields mirror the protobuf
``AgentCard`` message in camelCase; no A2A SDK is needed to build one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

A2A_PROTOCOL_VERSION = "1.0"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
PROTOCOL_BINDINGS = ("JSONRPC", "HTTP+JSON", "GRPC")


def _skill(capability: str, agent_name: str, platforms: List[str]) -> Dict[str, Any]:
    """An A2A skill entry for one agent capability."""
    label = capability.replace("_", " ").replace("-", " ").strip()
    return {
        "id": capability,
        "name": label.title(),
        "description": f"{label.capitalize()}, performed by the Elyan-class agent "
        f"'{agent_name}' under the SophiaCore principles.",
        "tags": [capability, *platforms],
    }


def build_agent_card(
    manifest: Dict[str, Any],
    url: str,
    *,
    protocol_binding: str = "JSONRPC",
    provider: Optional[Dict[str, str]] = None,
    documentation_url: Optional[str] = None,
    icon_url: Optional[str] = None,
    streaming: bool = False,
    push_notifications: bool = False,
) -> Dict[str, Any]:
    """Build an A2A 1.0 Agent Card from an agent manifest.

    Args:
        manifest: Agent manifest (see ``shaprai.core.lifecycle.create_agent``).
        url: Endpoint where the agent serves A2A requests.
        protocol_binding: ``JSONRPC``, ``HTTP+JSON`` or ``GRPC``.
        provider: Optional ``{"organization": ..., "url": ...}``.
        documentation_url: Optional link to the agent's documentation.
        icon_url: Optional icon URL.
        streaming: Whether the endpoint supports streaming responses.
        push_notifications: Whether the endpoint supports push notifications.

    Returns:
        The Agent Card as a JSON-serializable dict.
    """
    if protocol_binding not in PROTOCOL_BINDINGS:
        raise ValueError(f"protocol_binding must be one of {PROTOCOL_BINDINGS}")

    name = manifest.get("name", "unnamed")
    platforms = list(manifest.get("platforms") or [])
    capabilities = list(manifest.get("capabilities") or []) or ["general"]
    description = manifest.get("description") or (
        f"Elyan-class agent '{name}' built with ShaprAI on the SophiaCore principles."
    )

    card: Dict[str, Any] = {
        "name": name,
        "description": description,
        "supportedInterfaces": [
            {
                "url": url,
                "protocolBinding": protocol_binding,
                "protocolVersion": A2A_PROTOCOL_VERSION,
            }
        ],
        "version": str(manifest.get("version") or "1.0"),
        "capabilities": {
            "streaming": streaming,
            "pushNotifications": push_notifications,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [_skill(c, name, platforms) for c in capabilities],
    }
    if provider:
        card["provider"] = dict(provider)
    if documentation_url:
        card["documentationUrl"] = documentation_url
    if icon_url:
        card["iconUrl"] = icon_url
    return card
