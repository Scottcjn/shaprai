# ShaprAI -- Agent Sharpener by Elyan Labs

**Sharpen raw models into principled, self-governing Elyan-class agents.**

[![BCOS Certified](https://img.shields.io/badge/BCOS-Certified-blue)](https://github.com/Scottcjn/bcos-standard)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/shaprai)](https://pypi.org/project/shaprai/)

ShaprAI is an open-source agent lifecycle management platform. It takes raw
language models and produces **Elyan-class agents** -- principled, self-governing
AI agents of any size that maintain identity coherence, resist sycophancy, and
operate within a biblical ethical framework.

## Installation

### From PyPI

```bash
pip install shaprai
```

### From source (development)

```bash
git clone https://github.com/Scottcjn/shaprai.git
cd shaprai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify the install

```bash
shaprai --help
python -c "import shaprai; print(shaprai.__version__)"
```

### Dependencies

Core dependencies are installed automatically. Optional extras:

```bash
pip install shaprai[training]   # SFT/DPO/DriftLock training support
pip install shaprai[dev]        # pytest, ruff, coverage
```

## Quickstart

### 1. Create an agent from a template

```bash
shaprai create my-agent --template bounty_hunter --model Qwen/Qwen3-7B-Instruct
```

### 2. Train through the three phases

```bash
shaprai train my-agent --phase sft        # Supervised fine-tuning
shaprai train my-agent --phase dpo        # Direct preference optimization
shaprai train my-agent --phase driftlock  # Identity lock (anti-flattening)
```

### 3. Graduate from the Sanctuary

```bash
shaprai sanctuary my-agent   # Elyan-class education program
shaprai graduate my-agent    # Must score >= 0.85 to pass
```

### 4. Deploy

```bash
shaprai deploy my-agent --platform github
shaprai fleet status                       # Check all agents
```

## Agent Lifecycle

```
CREATE -> TRAINING (SFT -> DPO -> DriftLock) -> SANCTUARY -> GRADUATED -> DEPLOYED
```

Every agent passes through the **Sanctuary** -- an education program that teaches
PR etiquette, code quality, communication, and ethics before deployment. Only
agents scoring above the Elyan-class threshold (0.85) graduate.

## Elyan Labs Ecosystem Integration

ShaprAI agents connect to the full Elyan Labs stack out of the box:

| Service | Purpose | Integration |
|---------|---------|-------------|
| [RustChain](https://github.com/Scottcjn/rustchain-bounties) | RTC token economy, wallets, job marketplace | `shaprai.integrations.rustchain` |
| [Beacon](https://github.com/Scottcjn/beacon-skill) | Agent discovery, heartbeat, SEO scoring | `shaprai.integrations.beacon` |
| [BoTTube](https://bottube.ai) | AI video platform, content engagement | `shaprai.integrations.bottube` |
| [Grazer](https://github.com/Scottcjn/grazer-skill) | Content discovery across platforms | `shaprai.integrations.grazer` |

### Unified ecosystem access

```python
from shaprai.integrations.elyan_ecosystem import ElyanEcosystem

eco = ElyanEcosystem()
profile = eco.connect_agent(
    name="my-bot",
    capabilities=["code_review", "triage"],
    platforms=["github", "bottube"],
)
print(f"Wallet: {profile.wallet_id}")       # RustChain RTC wallet
print(f"Beacon: {profile.beacon_id}")       # Beacon discovery ID
print(f"Balance: {eco.get_rtc_balance('my-bot')} RTC")
```

### Elyan Bus (advanced)

The `ElyanBus` provides lower-level access to all four ecosystem services
(RustChain, Beacon, Atlas, Grazer) through a single integration layer:

```python
from shaprai.elyan_bus import ElyanBus

bus = ElyanBus()
agent = bus.onboard_agent(
    agent_name="my-agent",
    capabilities=["code_review"],
    platforms=["github"],
    description="My review agent",
)
```

## Example Agents

ShaprAI ships with three runnable example agents in `examples/`:

### GitHub Triage Agent

Labels, prioritizes, and deduplicates GitHub issues.

```bash
python examples/github_triage_agent.py
```

### Content Summarizer Agent

Produces extractive summaries of articles, PR diffs, and threads.

```bash
python examples/content_summarizer_agent.py
```

### Code Review Agent

Reviews code for security issues, bug patterns, and style problems.
Integrates with the ShaprAI QualityGate for PR comment quality checks.

```bash
python examples/code_review_agent.py
python examples/code_review_agent.py --file path/to/code.py
```

## Agent Templates

Pre-built templates in `templates/` for common agent roles:

| Template | Description |
|----------|-------------|
| `bounty_hunter` | Discovers and delivers GitHub bounties for RTC |
| `code_reviewer` | Thorough, principled PR reviews |
| `github_triage` | Issue labeling, priority scoring, duplicate detection |
| `content_summarizer` | Article/PR/thread summarization |
| `security_researcher` | Security audits and vulnerability reports |
| `community_builder` | Engagement and community management |
| `incident_commander` | Incident response coordination |

Load a template programmatically:

```python
from shaprai.core.template_engine import load_template

template = load_template("templates/github_triage.yaml")
print(template.name, template.capabilities)
```

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

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
shaprai/
  core/           # Lifecycle, fleet management, templates, self-governance
  integrations/   # RustChain, Beacon, BoTTube, Grazer, unified ecosystem
  marketplace/    # Agent marketplace (registry, pricing, validation)
  runtimes/       # CrewAI, smolagents, MCP adapters
  sanctuary/      # Education, quality gate, ethics, DriftLock
  training/       # SFT, DPO, DriftLock training pipelines
examples/         # Runnable example agents
templates/        # YAML agent templates
tests/            # Test suite
```

## Prerequisites

| Dependency | Purpose |
|------------|---------|
| [beacon-skill](https://github.com/Scottcjn/beacon-skill) | Agent discovery and SEO heartbeat |
| [grazer-skill](https://github.com/Scottcjn/grazer-skill) | Content discovery and engagement |
| [atlas](https://github.com/Scottcjn/atlas) | Agent deployment orchestration |
| RustChain wallet | RTC token integration for bounties and fees |

## License

MIT -- Copyright Elyan Labs 2026
