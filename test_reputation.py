#!/usr/bin/env python3
"""Test script for the reputation system - standalone version."""

import sys
import tempfile
from pathlib import Path

# Add the shaprai module to path
sys.path.insert(0, str(Path(__file__).parent))

from shaprai.core.reputation import ReputationManager, AgentReputation


def test_reputation_manager():
    """Test basic reputation functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rm = ReputationManager(reputation_dir=Path(tmpdir))
        
        # Test getting reputation for new agent
        rep = rm.get_reputation("test-agent")
        assert rep.agent_name == "test-agent"
        assert rep.total_score == 5.0
        assert rep.rating == 3.0
        print("[OK] New agent reputation initialized correctly")
        
        # Test recording events
        delta = rm.record_event("test-agent", "task_completed")
        assert delta == 0.05
        print(f"[OK] Task completed event recorded: +{delta:.2f}")
        
        delta = rm.record_event("test-agent", "bounty_delivered", details={"reward_rtc": 15.0})
        assert delta == 0.15
        print(f"[OK] Bounty delivered event recorded: +{delta:.2f}")
        
        delta = rm.record_event("test-agent", "task_failed")
        assert delta == -0.10
        print(f"[OK] Task failed event recorded: {delta:.2f}")
        
        # Test stats
        stats = rm.get_agent_stats("test-agent")
        assert stats["total_tasks"] == 2
        assert stats["successful_tasks"] == 1
        assert stats["bounty_earned"] == 15.0
        print(f"[OK] Agent stats calculated correctly")
        print(f"  - Total tasks: {stats['total_tasks']}")
        print(f"  - Success rate: {stats['success_rate']*100:.1f}%")
        print(f"  - Bounty earned: {stats['bounty_earned']:.2f} RTC")
        print(f"  - Rating: {stats['rating']:.2f}/5.0")
        
        # Test leaderboard
        rm.record_event("agent-two", "graduation")
        rm.record_event("agent-two", "bounty_delivered", details={"reward_rtc": 30.0})
        rm.record_event("agent-two", "bounty_delivered", details={"reward_rtc": 20.0})
        
        leaderboard = rm.get_leaderboard(limit=5)
        assert len(leaderboard) == 2
        assert leaderboard[0].agent_name == "agent-two"  # Higher score
        print(f"[OK] Leaderboard sorted correctly")
        print(f"  1. {leaderboard[0].agent_name}: {leaderboard[0].total_score:.2f}")
        print(f"  2. {leaderboard[1].agent_name}: {leaderboard[1].total_score:.2f}")
        
        # Test export
        export_path = Path(tmpdir) / "export.json"
        rm.export_all(export_path)
        assert export_path.exists()
        print(f"[OK] Reputation data exported to {export_path}")
        
        # Test reset
        rm.reset_reputation("test-agent")
        rep_reset = rm.get_reputation("test-agent")
        assert rep_reset.total_score == 5.0
        print("[OK] Reputation reset works correctly")
        
        print("\n[SUCCESS] All reputation system tests passed!")


if __name__ == "__main__":
    test_reputation_manager()
