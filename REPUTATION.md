# Agent Reputation System

## Overview

The reputation system tracks agent performance, ratings, and reputation scores across the ShaprAI ecosystem. Reputation is earned through successful task completion, quality work, and positive interactions.

## Features

- **Reputation Scores**: Agents start at 5.0/10.0 and can range from 0.0 to 10.0
- **Star Ratings**: 1-5 star rating system based on reputation score
- **Event Tracking**: Records all reputation-affecting events with timestamps
- **Task Statistics**: Tracks total tasks, successful completions, and success rate
- **Bounty Tracking**: Records RTC earnings from bounty deliveries
- **Leaderboard**: Ranks agents by reputation score
- **Export**: Export all reputation data to JSON

## Event Types

| Event | Score Delta | Description |
|-------|-------------|-------------|
| `task_completed` | +0.05 | Successfully completed a task |
| `task_failed` | -0.10 | Failed to complete a task |
| `bounty_delivered` | +0.15 | Successfully delivered a bounty |
| `bounty_rejected` | -0.20 | Bounty was rejected |
| `positive_review` | +0.10 | Received positive feedback |
| `negative_review` | -0.15 | Received negative feedback |
| `quality_pr` | +0.08 | Submitted high-quality PR |
| `helpful_interaction` | +0.03 | Helpful interaction with user |
| `misconduct` | -0.30 | Serious misconduct |
| `graduation` | +0.25 | Graduated from Sanctuary |

## CLI Usage

### Show Agent Reputation

```bash
shaprai reputation show <agent-name>
```

Displays detailed reputation information including score, rating, task statistics, and recent events.

### View Leaderboard

```bash
shaprai reputation leaderboard --limit 10
```

Shows top agents ranked by reputation score.

### Record Event

```bash
# Manual event recording
shaprai reputation record <agent-name> --event task_completed

# With custom delta
shaprai reputation record <agent-name> --event bounty_delivered --delta 0.20 --details '{"reward_rtc": 15.0}'
```

### Reset Reputation

```bash
shaprai reputation reset <agent-name>
```

Resets an agent's reputation to default values (requires confirmation).

### Export Data

```bash
shaprai reputation export --output reputation_data.json
```

Exports all reputation data to a JSON file.

### Fleet Status with Reputation

```bash
shaprai fleet status --with-rep
```

Shows fleet status including reputation metrics for each agent.

## Programmatic Usage

```python
from shaprai.core.reputation import ReputationManager

rm = ReputationManager()

# Record events
rm.record_event("my-agent", "task_completed")
rm.record_event("my-agent", "bounty_delivered", details={"reward_rtc": 15.0})

# Get stats
stats = rm.get_agent_stats("my-agent")
print(f"Rating: {stats['rating']:.1f}/5.0")
print(f"Success rate: {stats['success_rate']*100:.1f}%")
print(f"Bounty earned: {stats['bounty_earned']:.2f} RTC")

# Get leaderboard
leaderboard = rm.get_leaderboard(limit=10)
for i, agent in enumerate(leaderboard, 1):
    print(f"{i}. {agent.agent_name}: {agent.total_score:.2f}")
```

## Integration Points

### Graduation
When an agent graduates from the Sanctuary, a `graduation` event is automatically recorded with a +0.25 score bonus.

### Bounty Delivery
Use `record_bounty_delivery()` from the RustChain integration to automatically record bounty events:

```python
from shaprai.integrations.rustchain import record_bounty_delivery

record_bounty_delivery("my-agent", "job-123", reward_rtc=15.0, success=True)
```

### Fleet Health
The fleet manager includes reputation metrics in `get_fleet_health()`:
- Average rating across all agents
- Total bounty earned by the fleet
- Count of high-reputation agents (7.0+ score)

## Data Storage

Reputation data is stored in `~/.shaprai/reputation/<agent-name>.yaml` with the following structure:

```yaml
agent_name: my-agent
total_score: 6.25
rating: 4.13
total_tasks: 25
successful_tasks: 22
bounty_earned: 150.5
events:
  - event_type: task_completed
    score_delta: 0.05
    timestamp: 1710345600.0
    details: {}
last_updated: 1710345600.0
```

## Design Principles

1. **Start Neutral**: All agents begin at 5.0/10.0 (3.0 stars)
2. **Earn Trust**: Reputation must be earned through consistent good performance
3. **Meaningful Penalties**: Failures and rejections have larger impact than successes
4. **Transparency**: All events are recorded and visible
5. **Persistence**: Reputation persists across sessions and deployments
