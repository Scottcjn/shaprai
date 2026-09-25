# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""smolagents adapter for Elyan-class agents.

Wraps HuggingFace's smolagents with SophiaCore principle injection,
ensuring lightweight tool-using agents maintain Elyan-class identity.
"""

from __future__ import annotations

import keyword
import logging
import re
from typing import Any, Dict, List, Optional

from shaprai.sanctuary.principles import get_ethics_prompt

logger = logging.getLogger(__name__)


def to_identifier(name: str) -> str:
    """smolagents requires agent names to be valid Python identifiers ('my-agent' -> 'my_agent')."""
    ident = re.sub(r"\W", "_", name) or "agent"
    if ident[0].isdigit():
        ident = "_" + ident
    if keyword.iskeyword(ident):
        ident += "_"
    return ident


class ShaprSmolagent:
    """smolagents wrapper with SophiaCore principles injected.

    Ensures that smolagents-based agents maintain their Elyan-class
    identity and ethical framework during tool-use interactions.

    Attributes:
        name: Agent identifier.
        model_id: HuggingFace model identifier.
        tools: List of tool objects.
        system_prompt: System prompt with SophiaCore principles.
    """

    def __init__(
        self,
        name: str,
        model_id: str = "Qwen/Qwen3-8B",
        tools: Optional[List[Any]] = None,
        additional_prompt: str = "",
        model: Any = None,
    ) -> None:
        """Initialize a ShaprAI-wrapped smolagent.

        Args:
            name: Unique agent identifier.
            model_id: Hugging Face model served through Inference Providers.
            tools: List of tool objects for the agent.
            additional_prompt: Extra system prompt content appended after ethics.
            model: Optional prebuilt smolagents model, e.g.
                ``OpenAIModel(model_id=..., api_base="http://localhost:8000/v1")``
                for a locally served, ShaprAI-trained adapter. Overrides ``model_id``.
        """
        self.name = name
        self.model_id = model_id
        self.model = model
        self.tools = tools or []

        # Build system prompt with SophiaCore principles
        ethics = get_ethics_prompt()
        self.system_prompt = ethics
        if additional_prompt:
            self.system_prompt += f"\n\n---\n\n{additional_prompt}"

        self._agent = None

    def build(self) -> Any:
        """Build the smolagents agent instance.

        Returns:
            smolagents agent object.

        Raises:
            ImportError: If smolagents is not installed.
        """
        try:
            from smolagents import CodeAgent, InferenceClientModel

            model = self.model or InferenceClientModel(model_id=self.model_id)

            # smolagents keeps its own tool-use system prompt; `instructions`
            # is inserted into it, so SophiaCore rides along with every step.
            self._agent = CodeAgent(
                tools=self.tools,
                model=model,
                instructions=self.system_prompt,
                name=to_identifier(self.name),
            )

            logger.info(
                "Built smolagent '%s' with model %s and %d tools",
                self.name,
                self.model_id,
                len(self.tools),
            )
            return self._agent

        except ImportError:
            raise ImportError(
                "smolagents not installed. Install with: pip install 'shaprai[smolagents]'"
            )

    def run(self, task: str) -> str:
        """Run a task through the smolagent.

        Args:
            task: Natural language task description.

        Returns:
            Agent's response string.
        """
        if self._agent is None:
            self.build()

        logger.info("Running task on '%s': %s", self.name, task[:100])
        return self._agent.run(task)

    @classmethod
    def from_manifest(cls, manifest: Dict[str, Any]) -> "ShaprSmolagent":
        """Create a ShaprSmolagent from an agent manifest.

        Args:
            manifest: Agent manifest dictionary.

        Returns:
            Configured ShaprSmolagent instance.
        """
        return cls(
            name=manifest.get("name", "unnamed"),
            model_id=manifest.get("model", {}).get("base", "Qwen/Qwen3-8B"),
            additional_prompt=manifest.get("personality", {}).get("backstory", ""),
        )
