# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Training modules for Elyan-class agents.

Three-phase training pipeline:
  1. SFT (Supervised Fine-Tuning) -- Teach the base model to speak like an Elyan agent
  2. Preference optimization (DPO, KTO, ORPO or SimPO) -- Align preferences toward
     principled behavior
  3. DriftLock -- Verify identity coherence and sycophancy resistance across long
     conversations with the served agent

SFT and preference training run on TRL with QLoRA and need the ``training``
extra: pip install 'shaprai[training]'.
"""
