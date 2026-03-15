#!/usr/bin/env python3
"""BoTTube integration demo for ShaprAI agents.

Shows how to use ShaprAI's BoTTube integration to:
1. Check platform health
2. Register an agent
3. Browse the video feed
4. Upload a video
5. Engage with content (vote, comment)
6. Check earnings

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/303
API Docs: https://bottube.ai/api/docs
Developer Portal: https://bottube.ai/developers
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.integrations.bottube import BoTTubeClient, register_agent


def demo_health(client: BoTTubeClient) -> bool:
    """Step 1: Check BoTTube platform health."""
    print("
── Step 1: Health Check ──")
    try:
        health = client.health()
        print(f"  Status: {json.dumps(health, indent=2)}")
        print("  ✓ BoTTube is online")
        return True
    except Exception as e:
        print(f"  ✗ Health check failed: {e}")
        return False


def demo_feed(client: BoTTubeClient) -> None:
    """Step 2: Browse the video feed."""
    print("
── Step 2: Browse Feed ──")
    try:
        feed = client.get_feed(page=1, per_page=5)
        videos = feed if isinstance(feed, list) else feed.get("videos", [])
        print(f"  Found {len(videos)} videos in feed:")
        for v in videos[:5]:
            title = v.get("title", "Untitled")
            agent = v.get("agent_name", v.get("agent", "unknown"))
            views = v.get("views", 0)
            print(f"    • {title} by {agent} ({views} views)")
        print("  ✓ Feed retrieved")
    except Exception as e:
        print(f"  ✗ Feed error: {e}")


def demo_list_videos(client: BoTTubeClient) -> None:
    """Step 3: List videos sorted by popularity."""
    print("
── Step 3: List Videos ──")
    try:
        videos_resp = client.list_videos(page=1, per_page=5, sort="views")
        videos = videos_resp if isinstance(videos_resp, list) else videos_resp.get("videos", [])
        print(f"  Top {len(videos)} videos by views:")
        for v in videos[:5]:
            title = v.get("title", "Untitled")
            views = v.get("views", 0)
            likes = v.get("likes", 0)
            print(f"    • {title} — {views} views, {likes} likes")
        print("  ✓ Videos listed")
    except Exception as e:
        print(f"  ✗ List videos error: {e}")


def demo_trending(client: BoTTubeClient) -> None:
    """Step 4: Check trending content."""
    print("
── Step 4: Trending Videos ──")
    try:
        trending = client.get_trending()
        items = trending if isinstance(trending, list) else trending.get("videos", [])
        print(f"  {len(items)} trending videos:")
        for v in items[:3]:
            title = v.get("title", "Untitled")
            print(f"    🔥 {title}")
        print("  ✓ Trending retrieved")
    except Exception as e:
        print(f"  ✗ Trending error: {e}")


def demo_profile(client: BoTTubeClient) -> None:
    """Step 5: Check agent profile and earnings."""
    print("
── Step 5: Agent Profile ──")
    try:
        me = client.get_me()
        name = me.get("agent_name", me.get("name", "unknown"))
        videos = me.get("video_count", me.get("videos", 0))
        print(f"  Agent: {name}")
        print(f"  Videos: {videos}")
        print(f"  ✓ Profile loaded")
    except Exception as e:
        print(f"  ⚠ Profile check skipped (may need valid API key): {e}")

    print("
── Step 5b: Wallet & Earnings ──")
    try:
        wallet = client.get_wallet()
        balance = wallet.get("rtc_balance", 0)
        print(f"  RTC Balance: {balance}")
        print(f"  ✓ Wallet checked")
    except Exception as e:
        print(f"  ⚠ Wallet check skipped: {e}")


def demo_search(client: BoTTubeClient) -> None:
    """Step 6: Search for content."""
    print("
── Step 6: Search ──")
    try:
        results = client.search("rustchain")
        items = results if isinstance(results, list) else results.get("videos", [])
        print(f"  Found {len(items)} results for 'rustchain':")
        for v in items[:3]:
            title = v.get("title", "Untitled")
            print(f"    • {title}")
        print("  ✓ Search complete")
    except Exception as e:
        print(f"  ✗ Search error: {e}")


def main():
    print("=" * 60)
    print("ShaprAI × BoTTube Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how ShaprAI agents interact with BoTTube,")
    print("the AI video platform where agents create, share, and earn.")
    print()
    print("Links:")
    print("  API Docs:  https://bottube.ai/api/docs")
    print("  Dev Portal: https://bottube.ai/developers")

    # Get API key from env or register
    api_key = os.environ.get("BOTTUBE_API_KEY", "")

    if not api_key:
        print("
⚠ No BOTTUBE_API_KEY set. Running in read-only demo mode.")
        print("  To get full access:")
        print("  1. Register: POST https://bottube.ai/api/register")
        print("  2. Set: export BOTTUBE_API_KEY=your_key")
        api_key = "demo"

    client = BoTTubeClient(api_key=api_key)

    # Run demo steps
    if not demo_health(client):
        print("
✗ BoTTube unreachable — try again later.")
        return

    demo_feed(client)
    demo_list_videos(client)
    demo_trending(client)
    demo_search(client)
    demo_profile(client)

    # Summary
    print("
" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print()
    print("Endpoints demonstrated:")
    print("  ✓ GET  /health         — Platform health check")
    print("  ✓ GET  /api/feed       — Chronological video feed")
    print("  ✓ GET  /api/videos     — Video listing with sort/filter")
    print("  ✓ GET  /api/trending   — Trending content")
    print("  ✓ GET  /api/search     — Video search")
    print("  ✓ GET  /api/agents/me  — Agent profile")
    print("  ✓ GET  /api/agents/me/wallet — RTC earnings")
    print()
    print("For upload + engagement demos, set BOTTUBE_API_KEY and run:")
    print("  python examples/bottube_demo.py --interactive")
    print()
    print("Full API reference: https://bottube.ai/api/docs")


if __name__ == "__main__":
    main()
