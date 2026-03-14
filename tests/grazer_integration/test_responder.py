# SPDX-License-Identifier: MIT
"""Tests for Grazer responder module."""

import pytest

from shaprai.integrations.grazer.discovery import DiscoveredPost
from shaprai.integrations.grazer.responder import (
    GeneratedResponse,
    GrazerResponder,
    ResponderConfig,
)


@pytest.fixture
def responder_config() -> ResponderConfig:
    return ResponderConfig(
        min_words=50,
        max_words=300,
        require_specific_reference=True,
        max_responses_per_hour=10,
    )


@pytest.fixture
def responder(responder_config: ResponderConfig) -> GrazerResponder:
    return GrazerResponder(responder_config)


@pytest.fixture
def sample_post() -> DiscoveredPost:
    return DiscoveredPost(
        post_id="moltbook-4821",
        platform="moltbook",
        title="Why most AI agent frameworks fail at long-running tasks",
        content="Testing several agent frameworks for production workloads.",
        author="dev_marcus",
        url="https://moltbook.social/@dev_marcus/posts/4821",
        topics=["ai_agents", "developer_tools", "machine_learning"],
        relevance_score=0.94,
    )


@pytest.fixture
def personality() -> dict:
    return {
        "style": "analytical_helpful",
        "voice": "Clear and technical.",
    }


class TestGeneratedResponse:
    def test_is_quality_true(self, sample_post: DiscoveredPost) -> None:
        resp = GeneratedResponse(
            post=sample_post,
            response_text="test response",
            quality_score=0.9,
            action="comment",
        )
        assert resp.is_quality is True

    def test_is_quality_false(self, sample_post: DiscoveredPost) -> None:
        resp = GeneratedResponse(
            post=sample_post,
            response_text="test response",
            quality_score=0.5,
            action="comment",
        )
        assert resp.is_quality is False


class TestGrazerResponder:
    def test_generate_response(
        self,
        responder: GrazerResponder,
        sample_post: DiscoveredPost,
        personality: dict,
    ) -> None:
        response = responder.generate_response(
            post=sample_post,
            agent_name="test_agent",
            agent_personality=personality,
        )
        assert response is not None
        assert response.quality_score >= 0.8
        assert response.action == "comment"  # moltbook -> comment
        assert len(response.response_text.split()) >= 50

    def test_response_action_bottube(
        self, responder: GrazerResponder, personality: dict
    ) -> None:
        post = DiscoveredPost(
            post_id="bottube-001",
            platform="bottube",
            title="Test video about ai_agents",
            content="Video content here.",
            author="video_user",
            url="https://bottube.video/watch/001",
            topics=["ai_agents"],
            relevance_score=0.9,
        )
        response = responder.generate_response(
            post=post,
            agent_name="test_agent",
            agent_personality=personality,
        )
        assert response is not None
        assert response.action == "reply"  # bottube -> reply

    def test_rate_limiting(
        self,
        sample_post: DiscoveredPost,
        personality: dict,
    ) -> None:
        config = ResponderConfig(max_responses_per_hour=2)
        responder = GrazerResponder(config)

        r1 = responder.generate_response(sample_post, "agent", personality)
        r2 = responder.generate_response(sample_post, "agent", personality)
        r3 = responder.generate_response(sample_post, "agent", personality)

        assert r1 is not None
        assert r2 is not None
        assert r3 is None  # Rate limited

    def test_score_banned_phrases(self, responder: GrazerResponder) -> None:
        post = DiscoveredPost(
            post_id="test-001",
            platform="moltbook",
            title="Test",
            content="Content",
            author="author",
            url="https://example.com",
            topics=["ai_agents"],
            relevance_score=0.9,
        )
        score = responder._score_response("Great post! I agree with everything about ai_agents " * 5, post)
        assert score < 0.8  # Should be penalized for banned phrases

    def test_response_history(
        self,
        responder: GrazerResponder,
        sample_post: DiscoveredPost,
        personality: dict,
    ) -> None:
        assert responder.response_history == []
        responder.generate_response(sample_post, "agent", personality)
        assert len(responder.response_history) == 1


class TestResponderConfig:
    def test_defaults(self) -> None:
        config = ResponderConfig()
        assert config.min_words == 50
        assert config.max_words == 300
        assert config.require_specific_reference is True
        assert config.max_responses_per_hour == 10
