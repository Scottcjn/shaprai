# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Platform integrations for Elyan-class agents.

Connects agents to external services: Beacon (discovery), Grazer (engagement),
RustChain (tokenomics), HuggingFace (model hosting), and BoTTube (video platform).
"""

from shaprai.integrations.beacon import BeaconClient, register_agent, heartbeat
from shaprai.integrations.grazer import (
    discover_content,
    engage,
    get_engagement_metrics,
    GRAZER_DEFAULT_URL,
)
from shaprai.integrations.bottube import (
    BoTTubeClient,
    create_video_agent,
    upload_agent_video,
    engage_with_videos,
    BOTTUBE_DEFAULT_URL,
    BOTTUBE_API_URL,
)

__all__ = [
    # Beacon
    "BeaconClient",
    "register_agent",
    "heartbeat",
    # Grazer
    "discover_content",
    "engage",
    "get_engagement_metrics",
    "GRAZER_DEFAULT_URL",
    # BoTTube
    "BoTTubeClient",
    "create_video_agent",
    "upload_agent_video",
    "engage_with_videos",
    "BOTTUBE_DEFAULT_URL",
    "BOTTUBE_API_URL",
]
