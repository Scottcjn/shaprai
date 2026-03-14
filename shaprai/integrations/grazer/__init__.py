# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Grazer integration for content discovery and engagement.

Grazer enables agents to discover relevant content across platforms
(Moltbook, BoTTube, GitHub) and engage meaningfully — not spam,
but genuine contribution.
"""

from shaprai.integrations.grazer.discovery import GrazerDiscovery
from shaprai.integrations.grazer.responder import GrazerResponder
from shaprai.integrations.grazer.agent import GrazerAgent

__all__ = ["GrazerDiscovery", "GrazerResponder", "GrazerAgent"]
