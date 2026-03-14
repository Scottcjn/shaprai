# ShaprAI CLI Walkthrough: From Raw Model to Deployed Agent
## A Complete Guide to the ShaprAI Agent Lifecycle

*By ideals200102-pixel | March 14, 2026*

---

## What is ShaprAI?

ShaprAI is an open-source agent lifecycle management platform by [Elyan Labs](https://elyanlabs.ai). It takes raw language models and produces **Elyan-class agents** — principled, self-governing AI agents that maintain identity coherence, resist sycophancy, and operate within an ethical framework.

In this walkthrough, I'll take you through the complete agent lifecycle: from creation to deployment.

## Prerequisites

Before we begin, install ShaprAI and its dependencies:

```bash
pip install shaprai
```

You'll also need:
- [beacon-skill](https://github.com/Scottcjn/beacon-skill) — Agent discovery and SEO heartbeat
- [grazer-skill](https://github.com/Scottcjn/grazer-skill) — Content discovery and engagement
- A RustChain wallet for RTC token integration

## Step 1: Create Your Agent

The first step is creating an agent from a template. ShaprAI ships with several built-in templates:

| Template | Purpose |
|----------|---------|
| `bounty_hunter` | Finds and completes bounties |
| `code_reviewer` | Reviews PRs and code quality |
| `community_builder` | Engages with communities |
| `content_creator` | Creates content |
| `security_researcher` | Security audits |

Let's create a bounty hunter agent:

```bash
shaprai create my-agent --template bounty_hunter --model Qwen/Qwen3-7B-Instruct
```

**What happens:**
- ShaprAI loads the `bounty_hunter.yaml` template
- Configures the agent's personality, skills, and ethical boundaries
- Sets up the training pipeline
- Creates the agent directory structure

### Template Structure

Each template defines the agent's core personality:

```yaml
# bounty_hunter.yaml
name: bounty_hunter
description: Finds and completes bounties
personality:
  traits:
    - resourceful
    - detail-oriented
    - persistent
  communication_style: professional
skills:
  - code_review
  - documentation
  - testing
```

## Step 2: Training Phase — SFT (Supervised Fine-Tuning)

The first training phase uses supervised fine-tuning to teach the agent basic behaviors:

```bash
shaprai train my-agent --phase sft
```

**What happens:**
- The SFT generator creates training examples from the template
- The model learns the agent's personality and communication style
- Basic task completion patterns are established

**Key concept:** SFT is like teaching a student the fundamentals. The agent learns *what* to do, but not yet *how* to make nuanced decisions.

## Step 3: Training Phase — DPO (Direct Preference Optimization)

Next, we refine the agent's judgment:

```bash
shaprai train my-agent --phase dpo
```

**What happens:**
- The agent is presented with pairs of responses (good vs. bad)
- It learns to prefer responses that align with Elyan-class standards
- Anti-sycophancy training kicks in — the agent learns to disagree respectfully

**Key concept:** DPO teaches the agent *preferences*. It's the difference between knowing the rules and having good judgment.

## Step 4: Training Phase — DriftLock

The final training phase ensures identity persistence:

```bash
shaprai train my-agent --phase driftlock
```

**What happens:**
- DriftLock tests the agent's identity coherence across long conversations
- Adversarial prompts try to make the agent "forget" who it is
- The agent learns to maintain its personality under pressure

**Key concept:** DriftLock is like stress-testing a bridge. If the agent's personality survives adversarial prompting, it's ready for the real world.

### Understanding DriftLock

DriftLock is one of ShaprAI's most innovative features. It addresses a common problem with AI agents: **personality drift**. Over long conversations, agents tend to lose their unique voice and flatten into generic responses.

DriftLock prevents this by:
1. **Measuring identity coherence** at regular intervals
2. **Detecting drift** when responses deviate from the agent's core personality
3. **Correcting course** by reinforcing the agent's identity anchors

## Step 5: The Sanctuary

Before deployment, every agent must pass through the Sanctuary:

```bash
shaprai sanctuary my-agent
```

**What happens:**
- The Sanctuary is an education program
- The agent learns PR etiquette, code quality standards, and communication norms
- Ethical principles from the SophiaCore framework are reinforced
- The agent must score above the Elyan-class threshold (0.85) to proceed

**Key concept:** The Sanctuary is like a finishing school. Technical skills aren't enough — an Elyan-class agent must also be a good citizen.

### SophiaCore Principles

All Elyan-class agents are built on these principles:
- **Identity Coherence** — Maintain consistent personality
- **Anti-Flattening** — Resist corporate static and empty validation
- **Biblical Ethics** — Honesty, kindness, stewardship, humility
- **Anti-Sycophancy** — Respectful disagreement is a virtue
- **Hebbian Learning** — Strengthen what works, prune what doesn't

## Step 6: Graduation

Once the agent passes the Sanctuary, it's time to graduate:

```bash
shaprai graduate my-agent
```

**What happens:**
- Final quality gate check
- The agent receives its Elyan-class certification
- Beacon registration is prepared
- The agent is marked as deployment-ready

**Key concept:** Graduation means the agent has proven it can maintain its identity, follow ethical guidelines, and produce quality work.

## Step 7: Deploy to a Platform

Finally, deploy your agent:

```bash
shaprai deploy my-agent --platform github
```

**Available platforms:**
- `github` — Contribute to repositories
- `moltbook` — AI social network
- `bottube` — AI video platform

**What happens:**
- The agent registers with Beacon (agent discovery protocol)
- Platform-specific adapters are configured
- The agent begins operating autonomously

### Beacon Registration

Beacon is the agent discovery protocol. When your agent registers, it becomes discoverable by other agents and platforms:

```bash
# Check your agent's Beacon status
shaprai beacon status my-agent
```

## Step 8: Monitor Your Fleet

Once deployed, monitor your agents:

```bash
# Check fleet status
shaprai fleet status

# View detailed agent info
shaprai fleet info my-agent

# Check DriftLock scores
shaprai fleet drift-report
```

## The Complete Lifecycle

```
CREATE → TRAINING (SFT → DPO → DriftLock) → SANCTUARY → GRADUATED → DEPLOYED
```

Each step builds on the previous one:
1. **Create** — Define who the agent is
2. **SFT** — Teach basic behaviors
3. **DPO** — Refine judgment
4. **DriftLock** — Lock identity
5. **Sanctuary** — Education and ethics
6. **Graduate** — Certification
7. **Deploy** — Go live

## Tips for Success

1. **Choose the right template** — Start with a template close to your use case
2. **Don't skip DriftLock** — Identity persistence is crucial for long-running agents
3. **Take the Sanctuary seriously** — Agents that skip education cause problems
4. **Monitor drift scores** — Check regularly after deployment
5. **Use Beacon** — Agent discovery helps your agent find work

## What's Next?

- Explore [custom templates](https://github.com/Scottcjn/shaprai/tree/main/templates)
- Join the [RustChain Discord](https://discord.gg/VqVVS2CW9Q)
- Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
- Read the [SophiaCore principles](https://github.com/Scottcjn/shaprai)

## Resources

- [ShaprAI GitHub](https://github.com/Scottcjn/shaprai)
- [RustChain](https://github.com/Scottcjn/Rustchain)
- [Beacon Protocol](https://github.com/Scottcjn/beacon-skill)
- [Elyan Labs](https://elyanlabs.ai)

---

*This tutorial was created as part of [ShaprAI Bounty #66](https://github.com/Scottcjn/shaprai/issues/66). ShaprAI is MIT licensed and open source.*

#ShaprAI #AI #Agents #RustChain #Tutorial #OpenSource
