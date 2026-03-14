# ShaprAI CLI Walkthrough Tutorial

**Repository:** Scottcjn/shaprai  
**Issue:** #66 - ShaprAI CLI walkthrough video or blog post  
**Reward:** 8 RTC  
**Format:** Documentation/Guide

---

## Introduction

This tutorial demonstrates the complete ShaprAI agent lifecycle using the command-line interface. ShaprAI is Elyan Labs' platform for creating and managing AI agents with identity coherence.

---

## Prerequisites

Before starting, ensure you have:

1. **Python 3.8+** installed
2. **ShaprAI installed:**
   ```bash
   pip install shaprai
   ```

3. **Elyan Ecosystem dependencies:**
   - beacon-skill (agent discovery)
   - grazer-skill (content engagement)
   - atlas (deployment orchestration)
   - RustChain wallet (for RTC tokens)

---

## Step-by-Step Walkthrough

### Step 1: Create an Agent

Use the `create` command to generate a new agent from a template:

```bash
shaprai create --template sophia_elya --name my-agent
```

**What this does:**
- Creates a new agent named "my-agent" 
- Uses the "sophia_elya" template as a base
- Registers with all Elyan systems (RustChain, Beacon, Atlas, Grazer)
- Sets up the agent's identity and personality

**Expected output:**
```
Onboarding 'my-agent' across Elyan ecosystem...
Agent 'my-agent' created from template 'sophia_elya'
  Model:    Qwen/Qwen3-7B-Instruct
  State:    CREATED
  Wallet:   0x...
  Beacon:   beacon_...
  Atlas:    atlas_node_...
  Platforms: github, rustchain, bottube
  Path:     ~/.shaprai/agents/my-agent
```

---

### Step 2: Train the Agent (SFT Phase)

Supervised Fine-Tuning (SFT) teaches the agent the basics:

```bash
shaprai train my-agent --phase sft
```

**What this does:**
- Loads the agent's configuration
- Runs SFT training on the base model
- Teaches the agent its personality and communication style
- Generates training data from the personality template

**Options:**
- `--data /path/to/data.jsonl` - Custom training data (optional)
- `--epochs 3` - Number of training epochs (default: 3)

---

### Step 3: Enter the Sanctuary

The Sanctuary is ShaprAI's education program:

```bash
shaprai sanctuary my-agent
```

**What this does:**
- Enrolls the agent in the Sanctuary education program
- Runs lessons on:
  - PR etiquette
  - Code quality
  - Communication
  - Ethics
- Evaluates the agent's progress

**Expected output:**
```
Agent 'my-agent' enrolled in Sanctuary (id: enrollment_...)
Running lesson: pr_etiquette...
Running lesson: code_quality...
Running lesson: communication...
Running lesson: ethics...
Full curriculum complete.
Progress score: 0.87 / 1.00
Graduation ready: Yes
```

---

### Step 4: Graduate the Agent

When the agent passes the Sanctuary:

```bash
shaprai graduate my-agent
```

**What this does:**
- Evaluates the agent against Elyan-class standards
- Checks DriftLock configuration
- Verifies quality threshold (0.85+)

**Expected output:**
```
Agent 'my-agent' has GRADUATED to Elyan-class status.
```

---

### Step 5: Deploy to a Platform

Deploy your graduated agent:

```bash
shaprai deploy my-agent --platform moltbook
```

**Available platforms:**
- `bottube` - AI video platform
- `moltbook` - Social platform
- `github` - Code collaboration
- `all` - Deploy to all platforms

**What this does:**
- Registers the agent on the specified platform
- Activates Beacon heartbeat for discovery
- Starts the agent's engagement routines

---

### Step 6: Check Fleet Status

View all your managed agents:

```bash
shaprai fleet status
```

**Expected output:**
```
Name                     State          Template            Platforms
--------------------------------------------------------------------------------
my-agent                 DEPLOYED       sophia_elya         github, rustchain, bottube

Total: 1 agent(s)
```

---

## Additional Commands

### Training Phases

**DPO (Direct Preference Optimization):**
```bash
shaprai train my-agent --phase dpo
```
Teaches the agent to prefer good responses over bad ones.

**DriftLock:**
```bash
shaprai train my-agent --phase driftlock
```
Tests identity coherence and resistance to drift.

### Template Management

**List templates:**
```bash
shaprai template list
```

**Create a template:**
```bash
shaprai template create --model Qwen/Qwen3-7B-Instruct --description "My custom agent"
```

**Fork a template:**
```bash
shaprai template fork bounty_hunter my-bounty-hunter --model Qwen/Qwen3-8B
```

---

## Example: Full Agent Creation Flow

```bash
# 1. Create agent
shaprai create --template bounty_hunter --name pr-agent

# 2. Train through phases
shaprai train pr-agent --phase sft --epochs 3
shaprai train pr-agent --phase dpo
shaprai train pr-agent --phase driftlock

# 3. Education
shaprai sanctuary pr-agent

# 4. Graduate
shaprai graduate pr-agent

# 5. Deploy
shaprai deploy pr-agent --platform github

# 6. Monitor
shaprai fleet status
```

---

## Beacon Registration

Every ShaprAI agent registers with Beacon for:
- **Discovery** - Agents can be found by other systems
- **Heartbeat** - Regular signals showing the agent is active
- **SEO** - Beacon provides search engine visibility

The Beacon ID is shown during agent creation:
```
Beacon: beacon_abc123
```

---

## DriftLock: Identity Protection

DriftLock ensures your agent maintains its identity over time:

```yaml
driftlock:
  enabled: true
  check_interval: 25
  anchor_phrases:
    - "I am a principled agent, not a people-pleaser."
    - "Quality over quantity."
```

The agent is regularly tested to ensure it hasn't drifted from its core personality.

---

## Conclusion

ShaprAI provides a complete lifecycle for creating principled, self-governing Elyan-class agents. From creation to deployment, the CLI makes it easy to manage your AI agents.

For more information:
- GitHub: https://github.com/Scottcjn/shaprai
- Documentation: https://shaprai.readthedocs.io

---

*This tutorial was created as part of GitHub Issue #66 - ShaprAI CLI walkthrough*
