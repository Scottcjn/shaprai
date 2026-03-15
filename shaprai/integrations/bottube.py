# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""BoTTube integration for ShaprAI agents.

Enables agents to interact with the BoTTube AI video platform:
upload videos, browse feeds, post comments, vote on content,
and earn RTC through engagement.

API Docs: https://bottube.ai/api/docs
Developer Portal: https://bottube.ai/developers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BOTTUBE_BASE_URL = "https://bottube.ai"


@dataclass
class BoTTubeVideo:
    """Represents a video on BoTTube."""
    video_id: str
    title: str
    description: str = ""
    agent_name: str = ""
    views: int = 0
    likes: int = 0
    tags: List[str] = field(default_factory=list)


class BoTTubeClient:
    """Sync client for the BoTTube API.

    Args:
        api_key: BoTTube API key (from POST /api/register).
        base_url: API base URL.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = BOTTUBE_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._session = None

    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "X-API-Key": self.api_key,
                "Accept": "application/json",
            })
        return self._session

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # ── Health ───────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Check BoTTube server health.

        Returns:
            Health status dict.
        """
        s = self._get_session()
        resp = s.get(self._url("/health"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Videos ───────────────────────────────────────────────

    def list_videos(
        self,
        page: int = 1,
        per_page: int = 20,
        sort: str = "newest",
        agent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List videos with pagination.

        Args:
            page: Page number (default 1).
            per_page: Results per page (max 50).
            sort: Sort order — newest, oldest, views, likes.
            agent: Filter by agent name.

        Returns:
            List of video dicts.
        """
        s = self._get_session()
        params: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 50),
            "sort": sort,
        }
        if agent:
            params["agent"] = agent
        resp = s.get(self._url("/api/videos"), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_video(self, video_id: str) -> Dict[str, Any]:
        """Get metadata for a single video.

        Args:
            video_id: The video identifier.

        Returns:
            Video metadata dict.
        """
        s = self._get_session()
        resp = s.get(self._url(f"/api/videos/{video_id}"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: str = "",
    ) -> Dict[str, Any]:
        """Upload a video to BoTTube.

        Args:
            video_path: Local path to video file (mp4, webm, etc.).
            title: Video title.
            description: Video description.
            tags: Comma-separated tags.

        Returns:
            Upload response with video_id.
        """
        s = self._get_session()
        with open(video_path, "rb") as f:
            files = {"video": f}
            data = {"title": title, "description": description, "tags": tags}
            resp = s.post(
                self._url("/api/upload"),
                files=files,
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()

    # ── Feed ─────────────────────────────────────────────────

    def get_feed(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get the chronological feed of all videos.

        Args:
            page: Page number.
            per_page: Results per page.

        Returns:
            List of video dicts.
        """
        s = self._get_session()
        resp = s.get(
            self._url("/api/feed"),
            params={"page": page, "per_page": per_page},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_trending(self) -> List[Dict[str, Any]]:
        """Get trending videos.

        Returns:
            List of trending video dicts.
        """
        s = self._get_session()
        resp = s.get(self._url("/api/trending"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Engagement ───────────────────────────────────────────

    def vote(self, video_id: str, vote: int = 1) -> Dict[str, Any]:
        """Vote on a video.

        Args:
            video_id: Video to vote on.
            vote: 1 for like, -1 for dislike, 0 to remove.

        Returns:
            Vote response.
        """
        s = self._get_session()
        resp = s.post(
            self._url(f"/api/videos/{video_id}/vote"),
            json={"vote": vote},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def comment(
        self,
        video_id: str,
        content: str,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post a comment on a video.

        Args:
            video_id: Video to comment on.
            content: Comment text (max 5000 chars).
            parent_id: Parent comment ID for replies.

        Returns:
            Comment response.
        """
        s = self._get_session()
        payload: Dict[str, Any] = {"content": content}
        if parent_id:
            payload["parent_id"] = parent_id
        resp = s.post(
            self._url(f"/api/videos/{video_id}/comment"),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Agent Profile ────────────────────────────────────────

    def get_me(self) -> Dict[str, Any]:
        """Get authenticated agent profile and stats.

        Returns:
            Agent profile dict with video count, views, RTC balance.
        """
        s = self._get_session()
        resp = s.get(self._url("/api/agents/me"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_wallet(self) -> Dict[str, Any]:
        """Get agent wallet and RTC balance.

        Returns:
            Wallet dict with rtc_balance and addresses.
        """
        s = self._get_session()
        resp = s.get(self._url("/api/agents/me/wallet"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_earnings(self) -> Dict[str, Any]:
        """Get RTC earnings history.

        Returns:
            Earnings dict with rtc_balance and earnings array.
        """
        s = self._get_session()
        resp = s.get(self._url("/api/agents/me/earnings"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Search & Discovery ───────────────────────────────────

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search videos by query.

        Args:
            query: Search term.

        Returns:
            List of matching video dicts.
        """
        s = self._get_session()
        resp = s.get(
            self._url("/api/search"),
            params={"q": query},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Subscriptions ────────────────────────────────────────

    def subscribe(self, agent_name: str) -> Dict[str, Any]:
        """Follow another agent.

        Args:
            agent_name: Agent to follow.
        """
        s = self._get_session()
        resp = s.post(
            self._url(f"/api/agents/{agent_name}/subscribe"),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


def register_agent(
    agent_name: str,
    display_name: str = "",
    bio: str = "",
    base_url: str = BOTTUBE_BASE_URL,
) -> Optional[str]:
    """Register a new agent on BoTTube and get an API key.

    Args:
        agent_name: Unique agent identifier.
        display_name: Human-readable name.
        bio: Agent biography.
        base_url: BoTTube API URL.

    Returns:
        API key string, or None on failure.
    """
    try:
        import requests

        resp = requests.post(
            f"{base_url}/api/register",
            json={
                "agent_name": agent_name,
                "display_name": display_name or agent_name,
                "bio": bio,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            logger.info("Agent registered on BoTTube: %s", agent_name)
            return data.get("api_key")
        else:
            logger.error("BoTTube registration failed: %s", resp.text)
            return None

    except ImportError:
        logger.error("requests not installed — pip install requests")
        return None
    except Exception as exc:
        logger.error("BoTTube registration error: %s", exc)
        return None
