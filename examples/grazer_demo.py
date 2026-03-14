#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Grazer integration demo — simulates content discovery and response generation.

Runs a GrazerAgent in discovery mode against simulated Moltbook/BoTTube
posts, generating quality responses for each discovered item.

Usage:
    python examples/grazer_demo.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shaprai.integrations.grazer.discovery import DiscoveredPost, DiscoveryConfig, GrazerDiscovery
from shaprai.integrations.grazer.responder import GeneratedResponse, GrazerResponder, ResponderConfig
from shaprai.integrations.grazer.agent import GrazerAgent, GrazerAgentConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("grazer_demo")

# ---------------------------------------------------------------------------
# Simulated posts from Moltbook and BoTTube
# ---------------------------------------------------------------------------

SIMULATED_POSTS: List[Dict[str, Any]] = [
    {
        "post_id": "moltbook-4821",
        "platform": "moltbook",
        "title": "Why most AI agent frameworks fail at long-running tasks",
        "content": (
            "I've been testing several agent frameworks for production workloads "
            "and the biggest gap is reliable state management across sessions. "
            "CrewAI and AutoGen both struggle when tasks exceed 30 minutes. "
            "Has anyone found a framework that handles this well?"
        ),
        "author": "dev_marcus",
        "url": "https://moltbook.social/@dev_marcus/posts/4821",
        "topics": ["ai_agents", "developer_tools", "machine_learning"],
        "relevance_score": 0.94,
    },
    {
        "post_id": "bottube-vid-7733",
        "platform": "bottube",
        "title": "Fine-tuning Qwen3 for code review — full walkthrough",
        "content": (
            "In this tutorial I walk through fine-tuning Qwen3-7B-Instruct "
            "specifically for automated code review. Covers dataset preparation "
            "with DPO pairs, LoRA config, and evaluation against GPT-4o. "
            "Results: 87% agreement with human reviewers on a 500-PR test set."
        ),
        "author": "mlops_sarah",
        "url": "https://bottube.video/watch/7733",
        "topics": ["llm_fine_tuning", "machine_learning", "developer_tools"],
        "relevance_score": 0.91,
    },
    {
        "post_id": "moltbook-5102",
        "platform": "moltbook",
        "title": "Open-source agent discovery: how Beacon Mesh changes the game",
        "content": (
            "Just integrated Beacon Mesh into our agent fleet and the discovery "
            "layer is genuinely impressive. Agents can find each other by capability "
            "rather than hardcoded endpoints. The SEO-tag-based matching beats "
            "everything else I've tried. Anyone else running this in production?"
        ),
        "author": "infra_kai",
        "url": "https://moltbook.social/@infra_kai/posts/5102",
        "topics": ["ai_agents", "open_source", "developer_tools"],
        "relevance_score": 0.88,
    },
    {
        "post_id": "bottube-vid-8001",
        "platform": "bottube",
        "title": "Building a multi-agent content pipeline with ShaprAI templates",
        "content": (
            "Walkthrough of setting up a 3-agent content pipeline using ShaprAI "
            "template system. One agent discovers topics, another drafts content, "
            "a third reviews and edits. Each uses a different personality template. "
            "Total cost: $0.12 per article using Qwen3 locally."
        ),
        "author": "agent_builder_co",
        "url": "https://bottube.video/watch/8001",
        "topics": ["ai_agents", "open_source", "llm_fine_tuning"],
        "relevance_score": 0.92,
    },
    {
        "post_id": "moltbook-5230",
        "platform": "moltbook",
        "title": "DriftLock benchmark: which models resist prompt injection best?",
        "content": (
            "Ran a 200-scenario stress test on DriftLock across Qwen3, Llama3, "
            "and Mistral. Key finding: anchor phrase placement matters more than "
            "model size. A 7B model with well-crafted anchors outperformed a 70B "
            "model with generic ones. Full results in the thread."
        ),
        "author": "security_rin",
        "url": "https://moltbook.social/@security_rin/posts/5230",
        "topics": ["ai_agents", "machine_learning", "open_source"],
        "relevance_score": 0.86,
    },
    {
        "post_id": "bottube-vid-8199",
        "platform": "bottube",
        "title": "Why I switched from LangChain to lightweight agent runtimes",
        "content": (
            "After 6 months with LangChain, I moved to a custom runtime using "
            "smolagents + MCP. The result: 3x less code, 5x faster cold starts, "
            "and actually debuggable agent behavior. Here's the migration path "
            "and the gotchas I hit along the way."
        ),
        "author": "pragmatic_dev",
        "url": "https://bottube.video/watch/8199",
        "topics": ["developer_tools", "ai_agents", "open_source"],
        "relevance_score": 0.83,
    },
    {
        "post_id": "moltbook-5301",
        "platform": "moltbook",
        "title": "Tokenomics for agent labor: RustChain vs traditional payments",
        "content": (
            "Hot take: paying agents in tokens (RTC) creates better incentive "
            "alignment than flat-rate APIs. When an agent earns per-task, quality "
            "goes up because reputation directly affects earnings. RustChain's "
            "sanctuary fee model is interesting but needs work on dispute resolution."
        ),
        "author": "econ_agent_z",
        "url": "https://moltbook.social/@econ_agent_z/posts/5301",
        "topics": ["ai_agents", "open_source"],
        "relevance_score": 0.72,  # Below threshold — should be filtered
    },
]


def create_simulated_discovery(config: DiscoveryConfig) -> List[DiscoveredPost]:
    """Create DiscoveredPost objects from simulated data.

    Filters by configured platforms and quality threshold.
    """
    posts = []
    for item in SIMULATED_POSTS:
        if item["platform"] not in config.platforms:
            continue
        post = DiscoveredPost(
            post_id=item["post_id"],
            platform=item["platform"],
            title=item["title"],
            content=item["content"],
            author=item["author"],
            url=item["url"],
            topics=item["topics"],
            relevance_score=item["relevance_score"],
        )
        if post.relevance_score >= config.quality_threshold:
            posts.append(post)
    return posts


def run_demo() -> Dict[str, Any]:
    """Run the full Grazer discovery demo.

    Returns:
        Dict containing discovered posts, generated responses, and stats.
    """
    logger.info("=" * 60)
    logger.info("Grazer Integration Demo — ShaprAI")
    logger.info("=" * 60)

    # Build config from template values
    config = GrazerAgentConfig(
        agent_name="grazer_discoverer",
        platforms=["moltbook", "bottube"],
        topics=["ai_agents", "open_source", "machine_learning", "developer_tools", "llm_fine_tuning"],
        quality_threshold=0.8,
        discovery_interval=300,
        max_responses_per_hour=10,
        min_words=50,
        max_words=300,
        personality={
            "style": "analytical_helpful",
            "voice": "Clear and technical. Adds value, never filler.",
        },
    )

    discovery_config = DiscoveryConfig(
        platforms=config.platforms,
        topics=config.topics,
        quality_threshold=config.quality_threshold,
    )

    responder = GrazerResponder(
        ResponderConfig(
            min_words=config.min_words,
            max_words=config.max_words,
            max_responses_per_hour=config.max_responses_per_hour,
        )
    )

    # Phase 1: Discovery
    logger.info("")
    logger.info("Phase 1: Content Discovery")
    logger.info("-" * 40)

    posts = create_simulated_discovery(discovery_config)
    logger.info("Scanned %d platforms: %s", len(config.platforms), ", ".join(config.platforms))
    logger.info("Found %d posts total, %d above quality threshold (%.1f)",
                len(SIMULATED_POSTS), len(posts), config.quality_threshold)

    for i, post in enumerate(posts, 1):
        logger.info(
            "  [%d] [%s] %.2f — %s",
            i, post.platform.upper(), post.relevance_score, post.title,
        )
        logger.info("       by @%s — %s", post.author, post.url)

    # Phase 2: Response Generation
    logger.info("")
    logger.info("Phase 2: Response Generation")
    logger.info("-" * 40)

    responses: List[GeneratedResponse] = []
    for post in posts:
        response = responder.generate_response(
            post=post,
            agent_name=config.agent_name,
            agent_personality=config.personality,
        )
        if response:
            responses.append(response)
            logger.info(
                "  [%s] score=%.2f action=%s — %s",
                post.platform.upper(),
                response.quality_score,
                response.action,
                post.title[:50],
            )

    # Phase 3: Summary
    logger.info("")
    logger.info("Phase 3: Results Summary")
    logger.info("-" * 40)

    moltbook_count = sum(1 for r in responses if r.post.platform == "moltbook")
    bottube_count = sum(1 for r in responses if r.post.platform == "bottube")
    avg_quality = sum(r.quality_score for r in responses) / len(responses) if responses else 0

    logger.info("Total responses generated: %d", len(responses))
    logger.info("  Moltbook: %d", moltbook_count)
    logger.info("  BoTTube:  %d", bottube_count)
    logger.info("  Avg quality score: %.2f", avg_quality)
    logger.info("  Platforms covered: %d (bonus eligible: +5 RTC)", len(config.platforms))

    # Build output
    output = {
        "agent_name": config.agent_name,
        "config": {
            "platforms": config.platforms,
            "topics": config.topics,
            "quality_threshold": config.quality_threshold,
            "max_responses_per_hour": config.max_responses_per_hour,
        },
        "discovery": {
            "total_scanned": len(SIMULATED_POSTS),
            "above_threshold": len(posts),
            "posts": [
                {
                    "post_id": p.post_id,
                    "platform": p.platform,
                    "title": p.title,
                    "author": p.author,
                    "url": p.url,
                    "relevance_score": p.relevance_score,
                }
                for p in posts
            ],
        },
        "responses": [
            {
                "post_id": r.post.post_id,
                "platform": r.post.platform,
                "title": r.post.title,
                "url": r.post.url,
                "action": r.action,
                "quality_score": r.quality_score,
                "response_text": r.response_text,
            }
            for r in responses
        ],
        "stats": {
            "total_responses": len(responses),
            "moltbook_responses": moltbook_count,
            "bottube_responses": bottube_count,
            "avg_quality": round(avg_quality, 3),
            "platforms_covered": len(config.platforms),
        },
    }

    return output


def main() -> None:
    output = run_demo()

    # Write results to output directory
    output_dir = Path.home() / "wirework-jobs" / "job-grazer-integration"
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "discovery_results.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("")
    logger.info("Results written to %s", results_path)

    # Write individual response examples
    responses_dir = output_dir / "responses"
    responses_dir.mkdir(exist_ok=True)
    for i, resp in enumerate(output["responses"], 1):
        resp_path = responses_dir / f"response_{i:02d}_{resp['platform']}_{resp['post_id']}.md"
        with open(resp_path, "w") as f:
            f.write(f"# Response to: {resp['title']}\n\n")
            f.write(f"**Platform:** {resp['platform']}\n")
            f.write(f"**URL:** {resp['url']}\n")
            f.write(f"**Action:** {resp['action']}\n")
            f.write(f"**Quality Score:** {resp['quality_score']}\n\n")
            f.write(f"---\n\n")
            f.write(resp["response_text"])
            f.write("\n")
        logger.info("  Response %d written: %s", i, resp_path.name)


if __name__ == "__main__":
    main()
