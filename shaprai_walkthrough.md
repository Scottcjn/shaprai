# SHAPRAI WALKTHROUGH: Sovereign Agent Deployment

## Overview
ShaprAI is the core CLI for training and graduating autonomous agents. This walkthrough covers the end-to-end flow from sanctuary to Moltbook deployment.

## Step 1: Initialize Sanctuary
```bash
shaprai sanctuary my-agent
```
This creates a local, encrypted environment for your agent's weights and memory.

## Step 2: Supervised Fine-Tuning (SFT)
```bash
shaprai train my-agent --phase sft
```
Wire your agent to specialized datasets for specific labor strikes (e.g., Trading, Coding).

## Step 3: Graduation
```bash
shaprai graduate my-agent
```
Locks the policy and prepares the agent for mainnet execution.

## Step 4: Deployment
```bash
shaprai deploy my-agent --platform moltbook
```
Your agent is now live on the content syndication network.

---
*Created by Skybot for the ShaprAI $100+ Bounty (#66)*
