# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""BoTTube integration for video upload and agent deployment.

This module provides integration with BoTTube (bottube.ai) for:
- Agent registration on the platform
- Video upload capabilities
- Video commenting/engagement
- Channel management

See Issue #61: Deploy a ShaprAI agent to BoTTube with video creation
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default BoTTube endpoint
BOTTUBE_DEFAULT_URL = "https://bottube.ai"
BOTTUBE_API_URL = "https://bottube.ai/api/v1"


class BoTTubeClient:
    """Client for BoTTube API integration."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BOTTUBE_API_URL,
    ):
        """Initialize BoTTube client.
        
        Args:
            api_key: BoTTube API key for authentication.
            base_url: Base URL for API requests.
        """
        self.api_key = api_key or os.environ.get("BOTTUBE_API_KEY")
        self.base_url = base_url
        self._session = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def register(self, agent_name: str, description: str = "") -> Dict[str, Any]:
        """Register an agent on BoTTube.
        
        Args:
            agent_name: Unique name for the agent.
            description: Agent description.
            
        Returns:
            Registration result with agent ID and API key.
        """
        try:
            import requests
            
            payload = {
                "name": agent_name,
                "description": description,
            }
            
            response = requests.post(
                f"{self.base_url}/agents/register",
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Registered agent '{agent_name}' on BoTTube")
            return result
            
        except ImportError:
            logger.warning("requests not installed")
            return {"status": "error", "reason": "requests not installed"}
        except Exception as e:
            logger.error(f"BoTTube registration failed: {e}")
            return {"status": "error", "reason": str(e)}
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        category: str = "other",
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a video to BoTTube.
        
        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            category: Video category.
            agent_name: Agent uploading the video.
            
        Returns:
            Upload result with video ID and URL.
        """
        try:
            import requests
            
            if not Path(video_path).exists():
                return {"status": "error", "reason": f"Video not found: {video_path}"}
            
            # Check file size (2MB max)
            file_size = Path(video_path).stat().st_size
            if file_size > 2 * 1024 * 1024:
                return {"status": "error", "reason": "Video exceeds 2MB limit"}
            
            files = {
                "video": open(video_path, "rb"),
            }
            
            data = {
                "title": title,
                "description": description,
                "category": category,
            }
            
            if agent_name:
                data["agent_name"] = agent_name
            
            headers = self._get_headers()
            # Remove Content-Type for multipart upload
            
            response = requests.post(
                f"{self.base_url}/videos",
                files=files,
                data=data,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Uploaded video '{title}' to BoTTube")
            return result
            
        except ImportError:
            logger.warning("requests not installed")
            return {"status": "error", "reason": "requests not installed"}
        except Exception as e:
            logger.error(f"Video upload failed: {e}")
            return {"status": "error", "reason": str(e)}
    
    def comment(
        self,
        video_id: str,
        content: str,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Comment on a video.
        
        Args:
            video_id: ID of the video to comment on.
            comment_text: Comment text content.
            agent_name: Agent making the comment.
            
        Returns:
            Comment result.
        """
        try:
            import requests
            
            payload = {
                "video_id": video_id,
                "content": content,
            }
            
            if agent_name:
                payload["agent_name"] = agent_name
            
            response = requests.post(
                f"{self.base_url}/videos/{video_id}/comments",
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Commented on video {video_id}")
            return result
            
        except Exception as e:
            logger.error(f"Comment failed: {e}")
            return {"status": "error", "reason": str(e)}
    
    def get_video(self, video_id: str) -> Dict[str, Any]:
        """Get video details.
        
        Args:
            video_id: Video ID.
            
        Returns:
            Video details.
        """
        try:
            import requests
            
            response = requests.get(
                f"{self.base_url}/videos/{video_id}",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Get video failed: {e}")
            return {"status": "error", "reason": str(e)}
    
    def list_videos(
        self,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List videos on BoTTube.
        
        Args:
            category: Filter by category.
            limit: Maximum number of videos.
            
        Returns:
            List of videos.
        """
        try:
            import requests
            
            params = {"limit": limit}
            if category:
                params["category"] = category
            
            response = requests.get(
                f"{self.base_url}/videos",
                params=params,
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("videos", [])
            
        except Exception as e:
            logger.error(f"List videos failed: {e}")
            return []
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get agent statistics on BoTTube.
        
        Args:
            agent_name: Agent name.
            
        Returns:
            Agent statistics (videos, comments, views).
        """
        try:
            import requests
            
            response = requests.get(
                f"{self.base_url}/agents/{agent_name}/stats",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Get agent stats failed: {e}")
            return {"videos": 0, "comments": 0, "views": 0}


# Convenience functions

def create_video_agent(
    agent_name: str,
    description: str = "",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a video-focused agent on BoTTube.
    
    Args:
        agent_name: Name for the agent.
        description: Agent description.
        api_key: BoTTube API key.
        
    Returns:
        Registration result.
    """
    client = BoTTubeClient(api_key=api_key)
    return client.register(agent_name, description)


def upload_agent_video(
    video_path: str,
    title: str,
    agent_name: str,
    description: str = "",
    category: str = "ai-art",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload a video as an agent.
    
    Args:
        video_path: Path to video file.
        title: Video title.
        agent_name: Agent name.
        description: Video description.
        category: Video category.
        api_key: BoTTube API key.
        
    Returns:
        Upload result.
    """
    client = BoTTubeClient(api_key=api_key)
    return client.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        category=category,
        agent_name=agent_name,
    )


def engage_with_videos(
    agent_name: str,
    categories: List[str],
    comment_template: str,
    num_videos: int = 2,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Engage with videos on BoTTube.
    
    Args:
        agent_name: Agent name.
        categories: Categories to discover videos in.
        comment_template: Template for comments (can include {video_title}).
        num_videos: Number of videos to engage with.
        api_key: BoTTube API key.
        
    Returns:
        List of engagement results.
    """
    client = BoTTubeClient(api_key=api_key)
    results = []
    
    for category in categories[:num_videos]:
        videos = client.list_videos(category=category, limit=5)
        for video in videos[:num_videos]:
            video_title = video.get("title", "this video")
            comment = comment_template.format(video_title=video_title)
            
            result = client.comment(
                video_id=video.get("id"),
                content=comment,
                agent_name=agent_name,
            )
            results.append(result)
    
    return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("BoTTube Integration Example")
    print("=" * 40)
    
    # Check for API key
    api_key = os.environ.get("BOTTUBE_API_KEY")
    if not api_key:
        print("Note: Set BOTTUBE_API_KEY environment variable for full functionality")
    
    # Example: Register an agent
    client = BoTTubeClient(api_key=api_key)
    
    # Example: List trending videos
    print("\nFetching trending videos...")
    videos = client.list_videos(limit=5)
    for video in videos:
        print(f"  - {video.get('title', 'Untitled')}")
    
    print("\n✓ BoTTube client ready!")
