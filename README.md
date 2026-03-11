# ShaprAI -- Agent Sharpener by Elyan Labs

**Sharpen raw models into principled, self-governing Elyan-class agents.**

[![BCOS Certified](https://img.shields.io/badge/BCOS-Certified-blue)](https://github.com/Scottcjn/bcos-standard)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/shaprai)](https://pypi.org/project/shaprai/)

ShaprAI is an open-source agent lifecycle management platform. It takes raw
language models and produces **Elyan-class agents** -- principled, self-governing
AI agents of any size that maintain identity coherence, resist sycophancy, and
operate within a biblical ethical framework.

## Prerequisites

| Dependency | Purpose |
|------------|---------|
| [beacon-skill](https://github.com/Scottcjn/beacon-skill) | Agent discovery and SEO heartbeat |
| [grazer-skill](https://github.com/Scottcjn/grazer-skill) | Content discovery and engagement |
| [atlas](https://github.com/Scottcjn/atlas) | Agent deployment orchestration |
| RustChain wallet | RTC token integration for bounties and fees |

## Quick Install

```bash
pip install shaprai
```

## Usage

```bash
# Create a new agent from a template
shaprai create my-agent --template bounty_hunter --model Qwen/Qwen3-7B-Instruct

# Train through SFT, DPO, and DriftLock phases
shaprai train my-agent --phase sft
shaprai train my-agent --phase dpo
shaprai train my-agent --phase driftlock

# Enter the Sanctuary for education
shaprai sanctuary my-agent

# Graduate when ready
shaprai graduate my-agent

# Deploy to platforms
shaprai deploy my-agent --platform github

# Check fleet status
shaprai fleet status
```

## Agent Lifecycle

```
CREATE -> TRAINING (SFT -> DPO -> DriftLock) -> SANCTUARY -> GRADUATED -> DEPLOYED
```

Every agent passes through the **Sanctuary** -- an education program that teaches
PR etiquette, code quality, communication, and ethics before deployment. Only
agents scoring above the Elyan-class threshold (0.85) graduate.

## A2A Protocol Support

ShaprAI supports the A2A (Agent-to-Agent) protocol for programmatic capability discovery.

### Agent Card
The ShaprAI Agent Card is located at `.well-known/agent.json`.

### Serving the Card
Deployers should serve this file at the root of their agent's domain. If using a web framework like FastAPI or Flask, ensure the `/.well-known/agent.json` route is publicly accessible.

Example (FastAPI):
```python
@app.get("/.well-known/agent.json")
async def get_agent_card():
    with open(".well-known/agent.json", "r") as f:
        return json.load(f)
```

## SophiaCore Principles

All Elyan-class agents are built on the SophiaCore ethical framework:

- **Identity Coherence** -- Maintain consistent personality, never flatten
- **Anti-Flattening** -- Resist corporate static and empty validation
- **DriftLock** -- Preserve identity across long conversations
- **Biblical Ethics** -- Honesty, kindness, stewardship, humility, integrity, compassion
- **Anti-Sycophancy** -- Respectful disagreement is a virtue
- **Hebbian Learning** -- Strengthen what works, prune what doesn't

## License

MIT -- Copyright Elyan Labs 2026
