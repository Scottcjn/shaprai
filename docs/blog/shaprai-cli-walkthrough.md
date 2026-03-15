# ShaprAI CLI Walkthrough: From Raw Model to Deployed Agent

ShaprAI is an open-source agent lifecycle management platform built by Elyan Labs. It takes raw language models and sharpens them into **Elyan-class agents** -- principled, self-governing AI agents that maintain identity coherence, resist sycophancy, and operate within a biblical ethical framework called SophiaCore. Whether you want to spin up an autonomous bounty hunter, a code reviewer, or a community builder, ShaprAI gives you one unified CLI to create, train, educate, and deploy your agents.

This walkthrough covers the full agent lifecycle using the ShaprAI CLI. By the end, you will have taken a raw model from creation through training, Sanctuary education, graduation, and deployment to a live platform.

## Prerequisites

Before you start, make sure you have:

- **Python 3.10+** with `pip`
- The four Elyan ecosystem dependencies installed:
  - [beacon-skill](https://github.com/Scottcjn/beacon-skill) -- Agent discovery and SEO heartbeat
  - [grazer-skill](https://github.com/Scottcjn/grazer-skill) -- Content discovery and engagement
  - [atlas](https://github.com/Scottcjn/atlas) -- Agent deployment orchestration
  - A **RustChain wallet** -- RTC token integration for bounties and fees

Install ShaprAI itself:

```bash
pip install shaprai
```

Verify the installation:

```bash
shaprai --version
```

## Step 1: Explore Available Templates

ShaprAI ships with several pre-built agent templates. Each template defines a model, personality, capabilities, target platforms, ethics profile, and DriftLock configuration. Before creating an agent, browse what is available:

```bash
shaprai template list
```

```
Name                      Model                               Description
------------------------------------------------------------------------------------------
bounty_hunter             Qwen/Qwen3-7B-Instruct              Autonomous bounty hunter — discovers, cl
chaos_engineer            Qwen/Qwen3-7B-Instruct              Chaos engineer that stress-tests system
code_reviewer             Qwen/Qwen3-7B-Instruct              Thorough code reviewer with security awa
community_builder         Qwen/Qwen3-7B-Instruct              Community engagement and support agent
content_creator           Qwen/Qwen3-7B-Instruct              Technical content writer with authentic
```

Each template is a YAML file in the `templates/` directory. You can fork an existing template to customize it, or create one from scratch with `shaprai template create`.

## Step 2: Create an Agent

Pick a template and create your agent. We will use the `bounty_hunter` template and name our agent `scout-01`:

```bash
shaprai create scout-01 --template bounty_hunter --model Qwen/Qwen3-7B-Instruct
```

```
Onboarding 'scout-01' across Elyan ecosystem...
Agent 'scout-01' created from template 'bounty_hunter'
  Model:    Qwen/Qwen3-7B-Instruct
  State:    created
  Wallet:   rtc-bounty-hunter-scout-01-a3f8
  Beacon:   beacon-scout-01-7c21
  Atlas:    atlas-node-scout-01-e4b9
  Platforms: github, rustchain, bottube
  Path:     /home/user/.shaprai/agents/scout-01
```

Behind the scenes, ShaprAI does several things during creation:

- Writes a `manifest.yaml` to `~/.shaprai/agents/scout-01/` with the full agent configuration
- Registers the agent with the **RustChain** wallet system for identity and RTC token handling
- Broadcasts a **Beacon** registration so other agents and platforms can discover it
- Places the agent on the **Atlas** network graph
- Binds the agent to its target **Grazer** platforms for content discovery

The `--model` flag is optional. If omitted, it uses whichever base model the template defines.

## Step 3: Train the Agent

Training happens in three sequential phases. Each phase builds on the last, progressively refining the agent's behavior.

### Phase 1: Supervised Fine-Tuning (SFT)

SFT teaches the agent the baseline behavior patterns from curated examples:

```bash
shaprai train scout-01 --phase sft --epochs 3
```

```
Training 'scout-01' -- phase: sft, epochs: 3
Phase 'sft' complete for 'scout-01'.
```

You can supply custom training data with the `--data` flag pointing to a JSONL file. ShaprAI also provides a generator to create ChatML-formatted SFT data from any template:

```bash
shaprai generate-sft --template templates/bounty_hunter.yaml --output data/sft_bounty.jsonl --count 1000
```

### Phase 2: Direct Preference Optimization (DPO)

DPO teaches the agent to prefer good responses over bad ones using ranked pairs:

```bash
shaprai train scout-01 --phase dpo --epochs 3
```

```
Training 'scout-01' -- phase: dpo, epochs: 3
Phase 'dpo' complete for 'scout-01'.
```

### Phase 3: DriftLock

DriftLock is not traditional training. It is a coherence evaluation that verifies the agent maintains its identity across extended conversations. The agent must keep its personality anchors intact without drifting toward generic, corporate-style responses:

```bash
shaprai train scout-01 --phase driftlock
```

```
Training 'scout-01' -- phase: driftlock, epochs: 3
DriftLock score: 0.0312
PASSED -- Identity coherence maintained.
Phase 'driftlock' complete for 'scout-01'.
```

A low drift score is good -- it means the agent is stable. If the DriftLock check fails, go back and re-train with additional DPO data that reinforces identity-consistent responses.

## Step 4: Enter the Sanctuary

The Sanctuary is what separates ShaprAI from other agent frameworks. It is a mandatory education program that teaches agents real-world skills before they interact with actual humans and codebases. Think of it as onboarding for bots.

The full curriculum covers four lessons:

| Lesson | What It Teaches |
|--------|----------------|
| `pr_etiquette` | How to submit quality PRs, not spam. One change per PR, meaningful commits, reading the issue first. |
| `code_quality` | Writing maintainable code with type hints, docstrings, and tests. Following project style. |
| `communication` | Being direct and honest. Asking questions. Disagreeing respectfully instead of defaulting to sycophancy. |
| `ethics` | The SophiaCore ethical framework: identity coherence, anti-flattening, honest stewardship, biblical foundations. |

Run the full curriculum:

```bash
shaprai sanctuary scout-01
```

```
Agent 'scout-01' enrolled in Sanctuary (id: sanctuary-a1b2c3d4e5f6)
Running lesson: pr_etiquette...
Running lesson: code_quality...
Running lesson: communication...
Running lesson: ethics...
Full curriculum complete.
Progress score: 0.92 / 1.00
Graduation ready: Yes
```

You can also run individual lessons if an agent needs targeted education:

```bash
shaprai sanctuary scout-01 --lesson communication
```

The Sanctuary enforces anti-patterns too. Agents learn what **not** to do: submitting 20 identical template PRs, auto-generating "Looks Good" reviews, or agreeing with everything just to be agreeable.

## Step 5: Graduate

Once an agent completes all four Sanctuary lessons and scores at or above the Elyan-class threshold of **0.85**, it can graduate:

```bash
shaprai graduate scout-01
```

```
Agent 'scout-01' has GRADUATED to Elyan-class status.
```

Graduation transitions the agent from `SANCTUARY` to `GRADUATED` state. If the agent has not met the requirements, the command tells you what is missing and suggests running additional Sanctuary lessons.

## Step 6: Deploy

A graduated agent can be deployed to one or more platforms:

```bash
shaprai deploy scout-01 --platform github
```

```
Agent 'scout-01' deployed to: github
```

Deploy to all configured platforms at once:

```bash
shaprai deploy scout-01 --platform all
```

```
Agent 'scout-01' deployed to: bottube, moltbook, github
```

Only agents in the `GRADUATED` state can be deployed. If you try to deploy a non-graduated agent, ShaprAI blocks it and tells you the current state.

## Step 7: Monitor with Fleet Status

Once you have agents running, track them all with a single command:

```bash
shaprai fleet status
```

```
Name                      State           Template             Platforms
--------------------------------------------------------------------------------
scout-01                  deployed        bounty_hunter        github
reviewer-02               sanctuary       code_reviewer
writer-03                 training        content_creator

Total: 3 agent(s)
```

## Tips and Best Practices

**Start with the right template.** Forking an existing template is faster than building from scratch. Use `shaprai template fork bounty_hunter my_custom_agent --model your/model-id` to start from a proven base.

**Do not skip DriftLock.** It catches identity drift that DPO alone will not fix. An agent that passes DPO but fails DriftLock will slowly flatten into generic responses during long conversations.

**Run the full Sanctuary curriculum.** Individual lessons are useful for remediation, but agents that skip lessons will fail graduation. The 0.85 threshold exists for a reason -- it filters out agents that are not ready for real-world interactions.

**Use the `evaluate` command for diagnostics.** If an agent is behaving strangely, `shaprai evaluate scout-01` gives you a quick read on its state and DriftLock configuration without modifying anything.

**Keep training data clean.** SFT data from `generate-sft` is a starting point. For production agents, curate your training pairs manually. Quality beats quantity -- one hundred well-crafted examples outperform ten thousand generated ones.

**Respect the lifecycle order.** The pipeline exists for a reason: CREATE, TRAIN (SFT, DPO, DriftLock), SANCTUARY, GRADUATE, DEPLOY. Trying to shortcut the process produces agents that are technically functional but ethically unanchored.

## Summary

ShaprAI provides a principled pipeline for building agents that are not just capable, but responsible. The CLI makes every step explicit and auditable -- from the model you choose, through the training phases that shape behavior, to the Sanctuary education that teaches real-world etiquette, and finally deployment with full ecosystem integration across RustChain, Beacon, Atlas, and Grazer.

The full lifecycle in six commands:

```bash
shaprai create scout-01 --template bounty_hunter
shaprai train scout-01 --phase sft
shaprai train scout-01 --phase dpo
shaprai train scout-01 --phase driftlock
shaprai sanctuary scout-01
shaprai graduate scout-01
shaprai deploy scout-01 --platform github
```

For more information, visit the [ShaprAI repository](https://github.com/Scottcjn/shaprai) or explore the template library to find a starting point for your own Elyan-class agent.
