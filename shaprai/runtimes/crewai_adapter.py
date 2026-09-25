# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""CrewAI adapter for Elyan-class agents.

Wraps CrewAI's Agent and Crew classes with SophiaCore principle injection,
ensuring that multi-agent orchestration preserves Elyan-class identity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from shaprai.sanctuary.principles import get_ethics_prompt

logger = logging.getLogger(__name__)


class ShaprCrewAgent:
    """CrewAI Agent wrapper with SophiaCore principles injected.

    Ensures that agents participating in CrewAI crews maintain their
    Elyan-class identity and ethical framework throughout multi-agent
    collaboration.

    Attributes:
        name: Agent identifier.
        role: Agent's role in the crew.
        goal: What the agent aims to accomplish.
        backstory: Agent's personality and background.
        tools: List of tools available to the agent.
    """

    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str = "",
        tools: Optional[List[Any]] = None,
        model: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        """Initialize a ShaprAI-wrapped CrewAI agent.

        The SophiaCore ethics prompt is automatically prepended to
        the backstory to establish principled behavior.

        Args:
            name: Unique agent identifier.
            role: The agent's role (e.g., "Code Reviewer", "Bounty Hunter").
            goal: The agent's primary goal.
            backstory: Agent personality and context.
            tools: List of tool objects the agent can use.
            model: LLM model identifier.
            verbose: Enable verbose logging.
        """
        self.name = name
        self.role = role
        self.goal = goal
        self.tools = tools or []
        self.model = model
        self.verbose = verbose

        # Inject SophiaCore principles into backstory
        ethics = get_ethics_prompt()
        self.backstory = f"{ethics}\n\n---\n\n{backstory}" if backstory else ethics

        self._crew_agent = None

    def to_crewai_agent(self) -> Any:
        """Convert to a CrewAI Agent object.

        Returns:
            CrewAI Agent instance with SophiaCore principles injected.

        Raises:
            ImportError: If crewai is not installed.
        """
        try:
            from crewai import Agent

            self._crew_agent = Agent(
                role=self.role,
                goal=self.goal,
                backstory=self.backstory,
                tools=self.tools,
                verbose=self.verbose,
                llm=self.model,
            )
            return self._crew_agent

        except ImportError:
            raise ImportError(
                "crewai not installed. Install with: pip install 'shaprai[crewai]'"
            )

    @classmethod
    def from_manifest(cls, manifest: Dict[str, Any]) -> "ShaprCrewAgent":
        """Create a ShaprCrewAgent from an agent manifest.

        Args:
            manifest: Agent manifest dictionary.

        Returns:
            Configured ShaprCrewAgent instance.
        """
        personality = manifest.get("personality", {})
        return cls(
            name=manifest.get("name", "unnamed"),
            role=personality.get("style", "general_assistant"),
            goal=manifest.get(
                "description", "Assist with tasks while maintaining principles"
            ),
            backstory=personality.get("backstory", ""),
            model=manifest.get("model", {}).get("base"),
        )


def create_crew(
    agents: List[ShaprCrewAgent],
    tasks: List[Dict[str, Any]],
    process: str = "sequential",
    verbose: bool = False,
    manager_llm: Optional[str] = None,
) -> Any:
    """Create a CrewAI Crew with ShaprAI-wrapped agents.

    Args:
        agents: List of ShaprCrewAgent instances.
        tasks: List of task dictionaries with 'description' and 'agent' keys.
        process: Execution process ('sequential' or 'hierarchical').
        verbose: Enable verbose output.
        manager_llm: Model for the manager agent; CrewAI requires one (or a
            manager agent) for the hierarchical process.

    Returns:
        CrewAI Crew object ready to execute.

    Raises:
        ImportError: If crewai is not installed.
    """
    if process not in ("sequential", "hierarchical"):
        raise ValueError(
            f"process must be 'sequential' or 'hierarchical', not '{process}'"
        )

    try:
        from crewai import Crew, Process, Task

        crew_agents = [a.to_crewai_agent() for a in agents]

        # Build agent lookup by name
        agent_map = {a.name: ca for a, ca in zip(agents, crew_agents)}

        crew_tasks = []
        for task_spec in tasks:
            agent_name = task_spec.get("agent", agents[0].name)
            crew_agent = agent_map.get(agent_name, crew_agents[0])

            crew_tasks.append(
                Task(
                    description=task_spec.get("description", ""),
                    expected_output=task_spec.get("expected_output", "Completed task"),
                    agent=crew_agent,
                )
            )

        crew = Crew(
            agents=crew_agents,
            tasks=crew_tasks,
            process=Process(process),
            manager_llm=manager_llm,
            verbose=verbose,
        )

        logger.info("Created crew with %d agents and %d tasks", len(agents), len(tasks))
        return crew

    except ImportError:
        raise ImportError(
            "crewai not installed. Install with: pip install 'shaprai[crewai]'"
        )
