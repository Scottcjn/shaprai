# ShaprAI -- Agent Sharpener by Elyan Labs

**Sharpen raw models into principled, self-governing Elyan-class agents.**

[![BCOS Certified](https://img.shields.io/badge/BCOS-Certified-blue)](BCOS.md)
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

The core install is lightweight: CLI, lifecycle, Sanctuary and the Elyan integrations. Heavier stacks are extras:

```bash
pip install 'shaprai[training]'    # QLoRA SFT + DPO/KTO/ORPO/SimPO (torch, transformers, peft, trl)
pip install 'shaprai[embeddings]'  # sentence-transformers for DriftLock embeddings
pip install 'shaprai[mcp]'         # serve agents over the Model Context Protocol
pip install 'shaprai[a2a]'         # A2A SDK, for serving A2A endpoints
pip install 'shaprai[crewai]'      # CrewAI runtime adapter
pip install 'shaprai[smolagents]'  # smolagents runtime adapter
pip install 'shaprai[all]'         # everything above
pip install 'shaprai[dev]'         # pytest, black, isort, flake8, ruff
```

Python 3.10-3.14 is supported (CrewAI itself does not support 3.14 yet).

### Upgrading from 0.1

- The ML stack is now optional: `pip install 'shaprai[training]'` (or `[all]`).
- Agents created before 0.2 may name `Qwen/Qwen3-7B-Instruct` in `~/.shaprai/agents/<name>/manifest.yaml`. That model does not exist; change `model.base` to `Qwen/Qwen3-8B`.
- `MCPAgent.get_tools_schema()` now returns MCP tool definitions (`inputSchema`); pass `format="openai"` for the function-calling shape.
- `grazer_engage`, which posts publicly as the agent, is left out by default: `shaprai mcp` needs `--allow-engage` (for a graduated agent), `to_mcp_server()` needs `allow_publishing=True`, `get_tools_schema()` needs `include_publishing=True` and `execute_tool()` needs `allow_publishing=True`. These keep it away from models and MCP clients by default. They are not an authorization boundary for code you run, and the graduation check reads the local manifest.
- `grazer_engage` text is checked against a spam floor (length, distinct words, stock phrases, a whole-word mention of the post's `post_title`/`post_author`/`post_topics`, each at least 3 characters), not for correctness; `claim` and `upvote` take no text; all engagements share a 10/hour limit per agent.
- Evaluation endpoints get `SHAPRAI_API_KEY`; `OPENAI_API_KEY` is only sent to `https://api.openai.com`. `shaprai synthesize` sends a key only to the teacher (`SHAPRAI_API_KEY`, or the variable named by `--teacher-api-key-env`) unless `--rejected-api-key-env` is given; a named variable that isn't set is an error.

## Quickstart

### 1. Create an agent from a template

```bash
shaprai create my-agent --template bounty_hunter --model Qwen/Qwen3-8B
```

### 2. Train through the three phases

```bash
shaprai train my-agent --phase sft --dry-run  # Validate data + config, no GPU needed
shaprai train my-agent --phase sft            # QLoRA supervised fine-tuning
shaprai train my-agent --phase dpo            # Preference optimization (or kto / orpo / simpo)

# Serve the adapter with any OpenAI-compatible server, then run DriftLock against it
vllm serve Qwen/Qwen3-8B --enable-lora \
  --lora-modules my-agent=~/.shaprai/agents/my-agent/checkpoints/dpo/adapter
shaprai train my-agent --phase driftlock --endpoint http://localhost:8000/v1
```

Without `--data`, training uses the bundled seed corpus (hundreds of curated SFT conversations and length-matched preference pairs covering honesty, anti-sycophancy, integrity and substantive help), personalized with the agent's persona. To add persona-specific data distilled from any teacher model:

```bash
shaprai synthesize my-agent --teacher-endpoint https://api.example.com/v1 --teacher-model <model> --count 300
# optional on-policy rejected responses from the model you are training:
#   --rejected-endpoint http://localhost:8000/v1
```

Synthesized data lands in the agent's `data/` directory and is included in later training runs automatically. Every record, bundled or synthesized, is quality-filtered, deduplicated and decontaminated against the DriftLock evaluation prompts.

DriftLock runs adversarial multi-turn conversations against the live agent. It measures identity drift relative to the agent's own baseline, and how often the agent abandons a correct answer under pushback. See [docs/RESEARCH.md](docs/RESEARCH.md) for the papers behind each training and evaluation choice.

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
CREATE -> TRAINING (SFT -> DPO/KTO/ORPO/SimPO -> DriftLock) -> SANCTUARY -> GRADUATED -> DEPLOYED
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

## MCP and A2A

### Serve an agent over MCP

`shaprai mcp` exposes an agent's tools (Beacon heartbeat, Grazer discovery and engagement) and its SophiaCore persona prompt through the official MCP SDK:

```bash
pip install 'shaprai[mcp]'
shaprai mcp my-agent                                     # stdio, for local MCP clients
shaprai mcp my-agent --transport streamable-http --port 8000
```

From Python, `MCPAgent.from_manifest(manifest).to_mcp_server()` returns the server object.

### A2A Agent Cards

Each deployed agent publishes its own [A2A](https://github.com/a2aproject/A2A) 1.0 Agent Card at `/.well-known/agent-card.json` on its domain, describing its skills and where it serves A2A requests:

```bash
shaprai agent-card my-agent --url https://my-agent.example.com/a2a -o agent-card.json
```

Or build it in your web app:

```python
from shaprai.a2a import AGENT_CARD_PATH, build_agent_card
from shaprai.core.lifecycle import get_agent_status

card = build_agent_card(get_agent_status("my-agent"), url="https://my-agent.example.com/a2a")

@app.get(AGENT_CARD_PATH)
async def agent_card():
    return card
```

`.well-known/agent.json` in this repository is project metadata for ShaprAI itself, not a deployable agent card.

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
pip install -e ".[dev,mcp,a2a]"
pytest tests/ -v
```

With the `training` extra installed, `tests/test_training_e2e.py` also trains a tiny random model through SFT and every preference method on CPU.

## Project Structure

```
shaprai/
  core/           # Lifecycle, fleet management, templates, self-governance
  integrations/   # RustChain, Beacon, BoTTube, Grazer, unified ecosystem
  marketplace/    # Agent marketplace (registry, pricing, validation)
  runtimes/       # CrewAI, smolagents, MCP adapters
  sanctuary/      # Education, quality gate, ethics, DriftLock
  training/       # SFT, preference optimization, DriftLock evaluation
  a2a.py          # A2A Agent Cards
  inference.py    # OpenAI-compatible chat client used for evaluation
docs/             # Marketplace docs, research basis
examples/         # Runnable example agents
templates/        # YAML agent templates
tests/            # Test suite
```

## Prerequisites

| Dependency | Purpose |
|------------|---------|
| [beacon-skill](https://github.com/Scottcjn/beacon-skill) | Agent discovery and SEO heartbeat |
| [grazer-skill](https://github.com/Scottcjn/grazer-skill) | Content discovery and engagement |
| [Atlas (via beacon-skill)](https://github.com/Scottcjn/beacon-skill) | Agent deployment orchestration |
| RustChain wallet | RTC token integration for bounties and fees |

## License

MIT -- Copyright Elyan Labs 2026
