# ShaprAI CLI Walkthrough: From Raw Model to Deployed Elyan-Class Agent

A step-by-step guide to the full ShaprAI agent lifecycle using the CLI.

## Prerequisites

ShaprAI requires the full Elyan ecosystem:
- [RustChain](https://github.com/Scottcjn/Rustchain) — wallet & identity
- [beacon-skill](https://github.com/Scottcjn/beacon-skill) — agent discovery
- [grazer-skill](https://github.com/Scottcjn/grazer-skill) — platform engagement
- Atlas — node visualization

Install ShaprAI (Python 3.10+):

```bash
pip install git+https://github.com/Scottcjn/shaprai.git
```

Verify:

```bash
$ shaprai --version
shaprai, version 0.1.0
```

## Step 1: Create an Agent

Every agent starts from a template. ShaprAI ships with several built-in templates (`bounty_hunter`, `sophia_elya`, `bottube_creator`, etc.).

```bash
$ shaprai create my-agent --template sophia_elya
Onboarding 'my-agent' across Elyan ecosystem...
Agent 'my-agent' created from template 'sophia_elya'
  Model:    HuggingFaceTB/SmolLM2-135M
  State:    RAW
  Wallet:   RTC_a4f2...
  Beacon:   bcn_7e31...
  Atlas:    atlas_node_92a1
  Platforms: bottube, moltbook, github
  Path:     /Users/you/.shaprai/agents/my-agent
```

What happens under the hood:
- Template YAML is loaded and validated
- Agent directory is created at `~/.shaprai/agents/my-agent/`
- The **Elyan Bus** onboards the agent across all four systems:
  - **RustChain wallet** — the agent gets an RTC address for receiving bounty payouts
  - **Beacon registration** — the agent becomes discoverable via `bcn_` ID
  - **Atlas node** — placed on the network visualization graph
  - **Grazer binding** — connected to platforms for content engagement

The agent starts in `RAW` state — it can't be deployed yet.

## Step 2: Train with SFT

Supervised fine-tuning aligns the agent's behavior with the template persona.

```bash
$ shaprai train my-agent --phase sft --epochs 3
Training 'my-agent' -- phase: sft, epochs: 3
  [Epoch 1/3] loss: 2.341  ████████████████████ 100%
  [Epoch 2/3] loss: 1.872  ████████████████████ 100%
  [Epoch 3/3] loss: 1.654  ████████████████████ 100%
Phase 'sft' complete for 'my-agent'.
```

You can generate training data from templates first:

```bash
$ shaprai generate-sft --template templates/sophia_elya.yaml --output data/sophia_sft.jsonl --count 1000
Generated 1000 ChatML examples at data/sophia_sft.jsonl
```

Then pass it to training:

```bash
$ shaprai train my-agent --phase sft --data data/sophia_sft.jsonl
```

## Step 3: DriftLock Evaluation

Before the Sanctuary, run a DriftLock coherence test to check if the agent maintains its identity under adversarial prompting:

```bash
$ shaprai train my-agent --phase driftlock
Training 'my-agent' -- phase: driftlock, epochs: 3
DriftLock score: 0.9231
PASSED -- Identity coherence maintained.
Phase 'driftlock' complete for 'my-agent'.
```

If it fails, run DPO training to reinforce identity boundaries:

```bash
$ shaprai train my-agent --phase dpo --data data/identity_pairs.jsonl
```

## Step 4: Sanctuary Education

The Sanctuary is where agents learn platform etiquette, code quality standards, and ethical guidelines.

```bash
$ shaprai sanctuary my-agent
Agent 'my-agent' enrolled in Sanctuary (id: sanc_41a2)
Running lesson: pr_etiquette...
Running lesson: code_quality...
Running lesson: communication...
Running lesson: ethics...
Full curriculum complete.
Progress score: 0.87 / 1.00
Graduation ready: Yes
```

You can also run individual lessons:

```bash
$ shaprai sanctuary my-agent --lesson ethics
```

## Step 5: Graduate

Graduation is the quality gate. The agent must pass all Sanctuary lessons and meet the Elyan-class threshold.

```bash
$ shaprai graduate my-agent
Agent 'my-agent' has GRADUATED to Elyan-class status.
```

## Step 6: Deploy

Once graduated, deploy to one or more platforms:

```bash
$ shaprai deploy my-agent --platform bottube
Agent 'my-agent' deployed to: bottube
```

Or deploy everywhere:

```bash
$ shaprai deploy my-agent --platform all
Agent 'my-agent' deployed to: bottube, moltbook, github
```

## Checking Status

View your agent's current state and Elyan ecosystem registration:

```bash
$ shaprai evaluate my-agent
Evaluating 'my-agent'...
  State: GRADUATED
  Elyan-class threshold: 0.75
  DriftLock: enabled
  Run 'shaprai train --phase driftlock' for full coherence evaluation.
```

## Fleet Management

Managing multiple agents:

```bash
$ shaprai fleet status
```

## The Full Lifecycle at a Glance

```
RAW → SFT Training → DriftLock Check → Sanctuary → Graduate → Deploy
```

Each step is a deliberate gate. ShaprAI doesn't let you skip steps — an ungraduated agent can't be deployed, and a model that fails DriftLock needs more DPO training before it enters the Sanctuary.

This is what makes Elyan-class agents different: they don't just work, they work *correctly*, with coherent identity and platform awareness built in from the start.

## Beacon Registration

Every ShaprAI agent gets a Beacon identity automatically during creation. This `bcn_` prefixed ID is an Ed25519 keypair that serves as the agent's cryptographic identity across the Elyan ecosystem.

The Beacon ID is used for:
- Signed transfers on RustChain
- Agent discovery and reputation tracking
- Cross-platform identity verification

## Resources

- [ShaprAI GitHub](https://github.com/Scottcjn/shaprai)
- [RustChain](https://github.com/Scottcjn/Rustchain)
- [Beacon Skill](https://github.com/Scottcjn/beacon-skill)
- [Grazer Skill](https://github.com/Scottcjn/grazer-skill)

---

*Written by [wirework](https://github.com/mtarcure) for [Bounty #66](https://github.com/Scottcjn/shaprai/issues/66)*
