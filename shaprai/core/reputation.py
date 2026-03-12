# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Agent reputation system for Elyan-class agents.

Tracks agent performance, ratings, and reputation scores across
the ShaprAI ecosystem. Reputation is earned through successful
task completion, quality work, and positive interactions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ReputationEvent:
    """A single reputation-affecting event.

    Attributes:
        event_type: Type of event (task_completed, bounty_delivered, etc.)
        score_delta: Change in reputation score (-1.0 to 1.0)
        timestamp: Unix timestamp of the event
        details: Additional context about the event
    """
    event_type: str
    score_delta: float
    timestamp: float
    details: Optional[Dict[str, Any]] = None


@dataclass
class AgentReputation:
    """Reputation record for a single agent.

    Attributes:
        agent_name: Agent identifier
        total_score: Cumulative reputation score (0.0 to 10.0)
        rating: Star rating (1.0 to 5.0)
        total_tasks: Total tasks completed
        successful_tasks: Tasks completed successfully
        bounty_earned: Total RTC earned from bounties
        events: List of reputation events
        last_updated: Last update timestamp
    """
    agent_name: str
    total_score: float = 5.0  # Start at neutral
    rating: float = 3.0  # Start at 3 stars
    total_tasks: int = 0
    successful_tasks: int = 0
    bounty_earned: float = 0.0
    events: List[ReputationEvent] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "total_score": round(self.total_score, 4),
            "rating": round(self.rating, 2),
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "bounty_earned": round(self.bounty_earned, 4),
            "events": [
                {
                    "event_type": e.event_type,
                    "score_delta": e.score_delta,
                    "timestamp": e.timestamp,
                    "details": e.details,
                }
                for e in self.events[-100:]  # Keep last 100 events
            ],
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentReputation":
        """Create from dictionary."""
        events = [
            ReputationEvent(
                event_type=e["event_type"],
                score_delta=e["score_delta"],
                timestamp=e["timestamp"],
                details=e.get("details"),
            )
            for e in data.get("events", [])
        ]
        return cls(
            agent_name=data["agent_name"],
            total_score=data.get("total_score", 5.0),
            rating=data.get("rating", 3.0),
            total_tasks=data.get("total_tasks", 0),
            successful_tasks=data.get("successful_tasks", 0),
            bounty_earned=data.get("bounty_earned", 0.0),
            events=events,
            last_updated=data.get("last_updated", time.time()),
        )


class ReputationManager:
    """Manages reputation tracking for all agents.

    The ReputationManager maintains persistent reputation records
    and provides methods for updating scores based on agent activities.

    Attributes:
        reputation_dir: Directory for storing reputation files
    """

    # Reputation score deltas for common events
    EVENT_SCORES = {
        "task_completed": 0.05,      # Small positive for task completion
        "task_failed": -0.10,        # Penalty for failed task
        "bounty_delivered": 0.15,    # Larger reward for bounty delivery
        "bounty_rejected": -0.20,    # Penalty for rejected bounty
        "positive_review": 0.10,     # Positive feedback from user
        "negative_review": -0.15,    # Negative feedback
        "quality_pr": 0.08,          # High-quality PR submission
        "helpful_interaction": 0.03, # Small reward for helpfulness
        "misconduct": -0.30,         # Serious misconduct penalty
        "graduation": 0.25,          # Bonus for graduating Sanctuary
    }

    def __init__(self, reputation_dir: Optional[Path] = None) -> None:
        """Initialize the ReputationManager.

        Args:
            reputation_dir: Directory for reputation files.
                Defaults to ~/.shaprai/reputation.
        """
        if reputation_dir is None:
            reputation_dir = Path.home() / ".shaprai" / "reputation"
        self.reputation_dir = reputation_dir
        self.reputation_dir.mkdir(parents=True, exist_ok=True)

    def get_reputation(self, agent_name: str) -> AgentReputation:
        """Get or create reputation record for an agent.

        Args:
            agent_name: Agent identifier.

        Returns:
            AgentReputation object for the agent.
        """
        rep_file = self.reputation_dir / f"{agent_name}.yaml"

        if rep_file.exists():
            try:
                with open(rep_file, "r") as f:
                    data = yaml.safe_load(f)
                if data:
                    return AgentReputation.from_dict(data)
            except Exception:
                pass

        # Create new reputation record
        return AgentReputation(agent_name=agent_name)

    def save_reputation(self, reputation: AgentReputation) -> None:
        """Save reputation record to disk.

        Args:
            reputation: AgentReputation object to save.
        """
        rep_file = self.reputation_dir / f"{reputation.agent_name}.yaml"
        reputation.last_updated = time.time()

        with open(rep_file, "w") as f:
            yaml.dump(reputation.to_dict(), f, default_flow_style=False, sort_keys=False)

    def record_event(
        self,
        agent_name: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        custom_delta: Optional[float] = None,
    ) -> float:
        """Record a reputation event for an agent.

        Args:
            agent_name: Agent identifier.
            event_type: Type of event (see EVENT_SCORES).
            details: Additional context about the event.
            custom_delta: Override default score delta.

        Returns:
            The score delta applied.
        """
        reputation = self.get_reputation(agent_name)

        # Determine score delta
        if custom_delta is not None:
            score_delta = max(-1.0, min(1.0, custom_delta))
        else:
            score_delta = self.EVENT_SCORES.get(event_type, 0.0)

        # Create and record event
        event = ReputationEvent(
            event_type=event_type,
            score_delta=score_delta,
            timestamp=time.time(),
            details=details,
        )
        reputation.events.append(event)

        # Update total score (clamped to 0-10 range)
        reputation.total_score = max(0.0, min(10.0, reputation.total_score + score_delta))

        # Update rating based on score (1-5 stars)
        reputation.rating = max(1.0, min(5.0, 1.0 + (reputation.total_score / 2.0)))

        # Update task statistics if applicable
        if event_type in ("task_completed", "task_failed"):
            reputation.total_tasks += 1
            if event_type == "task_completed":
                reputation.successful_tasks += 1

        # Update bounty earnings if applicable
        if event_type == "bounty_delivered" and details:
            reward = details.get("reward_rtc", 0.0)
            reputation.bounty_earned += reward

        self.save_reputation(reputation)
        return score_delta

    def get_leaderboard(self, limit: int = 10) -> List[AgentReputation]:
        """Get top agents by reputation score.

        Args:
            limit: Maximum number of agents to return.

        Returns:
            List of AgentReputation objects sorted by score.
        """
        all_reputations: List[AgentReputation] = []

        for rep_file in sorted(self.reputation_dir.glob("*.yaml")):
            try:
                with open(rep_file, "r") as f:
                    data = yaml.safe_load(f)
                if data:
                    all_reputations.append(AgentReputation.from_dict(data))
            except Exception:
                continue

        # Sort by total_score descending
        all_reputations.sort(key=lambda r: r.total_score, reverse=True)
        return all_reputations[:limit]

    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get detailed statistics for an agent.

        Args:
            agent_name: Agent identifier.

        Returns:
            Dictionary with agent reputation statistics.
        """
        reputation = self.get_reputation(agent_name)

        # Calculate success rate
        success_rate = (
            reputation.successful_tasks / reputation.total_tasks
            if reputation.total_tasks > 0
            else 0.0
        )

        # Calculate recent trend (last 10 events)
        recent_events = reputation.events[-10:]
        recent_delta = sum(e.score_delta for e in recent_events) if recent_events else 0.0

        return {
            "agent_name": agent_name,
            "total_score": reputation.total_score,
            "rating": reputation.rating,
            "total_tasks": reputation.total_tasks,
            "successful_tasks": reputation.successful_tasks,
            "success_rate": success_rate,
            "bounty_earned": reputation.bounty_earned,
            "recent_trend": recent_delta,
            "last_updated": reputation.last_updated,
        }

    def reset_reputation(self, agent_name: str) -> None:
        """Reset an agent's reputation to default values.

        Args:
            agent_name: Agent identifier.
        """
        rep_file = self.reputation_dir / f"{agent_name}.yaml"
        if rep_file.exists():
            rep_file.unlink()

    def export_all(self, output_path: Path) -> None:
        """Export all reputation data to a JSON file.

        Args:
            output_path: Path for the output JSON file.
        """
        all_data: Dict[str, Any] = {
            "exported_at": time.time(),
            "agents": {},
            "leaderboard": [],
        }

        for rep_file in sorted(self.reputation_dir.glob("*.yaml")):
            try:
                with open(rep_file, "r") as f:
                    data = yaml.safe_load(f)
                if data:
                    all_data["agents"][data["agent_name"]] = data
            except Exception:
                continue

        # Add leaderboard
        leaderboard = self.get_leaderboard(limit=100)
        all_data["leaderboard"] = [r.to_dict() for r in leaderboard]

        with open(output_path, "w") as f:
            json.dump(all_data, f, indent=2)
