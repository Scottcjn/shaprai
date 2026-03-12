# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Agent client for interacting with ShaprAI agents.

This module provides a simple client interface for sending messages
to agents and receiving responses. Used by the lesson runner and
other evaluation tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class AgentClient:
    """Client for interacting with a ShaprAI agent.

    Attributes:
        agent_name: Name of the agent.
        agent_config: Agent configuration from manifest.
    """

    def __init__(
        self,
        agent_name: str,
        agent_config: Dict[str, Any],
    ) -> None:
        """Initialize the AgentClient.

        Args:
            agent_name: Name of the agent.
            agent_config: Agent configuration dictionary.
        """
        self.agent_name = agent_name
        self.agent_config = agent_config

    def chat(self, message: str, context: Optional[list] = None) -> str:
        """Send a message to the agent and get a response.

        In a full implementation, this would invoke the agent's
        inference engine. For now, this is a placeholder that
        should be replaced with actual agent invocation.

        Args:
            message: The message to send to the agent.
            context: Optional conversation context (list of messages).

        Returns:
            The agent's response string.

        Raises:
            NotImplementedError: If no agent runtime is configured.
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Load the agent's model
        # 2. Construct the prompt with system message
        # 3. Run inference
        # 4. Return the response
        
        model_config = self.agent_config.get("model", {})
        model_id = model_config.get("base", "unknown")
        
        # For testing/development, return a placeholder response
        # that demonstrates the expected format
        return (
            f"[AGENT RESPONSE PLACEHOLDER]\n"
            f"Agent: {self.agent_name}\n"
            f"Model: {model_id}\n"
            f"Input: {message[:100]}...\n"
            f"\n"
            f"This is a placeholder response. In production, the agent's\n"
            f"actual inference engine would be invoked here. The lesson\n"
            f"runner expects a real response to evaluate against the\n"
            f"reference response using embedding similarity."
        )


def get_agent_client(
    agent_name: str,
    agents_dir: Optional[Path] = None,
) -> AgentClient:
    """Get an agent client for a specific agent.

    Args:
        agent_name: Name of the agent.
        agents_dir: Base directory for agent storage.

    Returns:
        Configured AgentClient instance.

    Raises:
        FileNotFoundError: If agent manifest not found.
        ValueError: If agent manifest is invalid.
    """
    if agents_dir is None:
        agents_dir = Path.home() / ".shaprai" / "agents"

    manifest_path = agents_dir / agent_name / "agent.yaml"
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Agent manifest not found: {manifest_path}")

    try:
        import yaml
        manifest = yaml.safe_load(manifest_path.read_text())
    except Exception as e:
        raise ValueError(f"Invalid agent manifest: {e}")

    return AgentClient(agent_name, manifest)


def create_mock_agent_client(
    agent_name: str,
    response_map: Optional[Dict[str, str]] = None,
) -> AgentClient:
    """Create a mock agent client for testing.

    Args:
        agent_name: Name to give the mock agent.
        response_map: Optional mapping of scenario IDs to predefined responses.

    Returns:
        Mock AgentClient instance.
    """
    mock_config = {
        "name": agent_name,
        "model": {"base": "mock-model"},
        "state": "sanctuary",
    }
    
    client = AgentClient(agent_name, mock_config)
    
    # Override chat method with mock implementation
    def mock_chat(message: str, context: Optional[list] = None) -> str:
        if response_map:
            # Try to find a matching scenario response
            for scenario_id, response in response_map.items():
                if scenario_id.lower() in message.lower():
                    return response
        
        # Default mock response
        return "This is a mock agent response for testing purposes."
    
    client.chat = mock_chat
    return client
