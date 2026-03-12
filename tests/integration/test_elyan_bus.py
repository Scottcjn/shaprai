"""Integration tests for Elyan Bus.

Tests cover both mock mode (for CI) and live mode (for real integration testing).
Use pytest markers to control which tests run:
- Default: mock tests only (no network)
- --integration: live tests against real services
"""

import json
import pytest
import responses
from unittest.mock import patch, MagicMock

from shaprai.elyan_bus import ElyanBus, ElyanAgent


# ─────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────

@pytest.fixture
def bus():
    """Create a fresh ElyanBus instance for testing."""
    return ElyanBus(
        rustchain_url="https://test-rustchain.local",
        beacon_url="https://test-beacon.local",
        admin_key="test_admin_key"
    )


@pytest.fixture
def mock_agent(bus):
    """Create a mock agent in the bus."""
    agent = bus._get_or_create_agent("test_agent")
    agent.wallet_id = "shaprai-test_agent"
    agent.beacon_id = "bcn_shaprai_test_agent"
    return agent


# ─────────────────────────────────────────────────
# Mock Mode Tests (CI-compatible)
# ─────────────────────────────────────────────────

class TestElyanBusMock:
    """ElyanBus tests using mocked HTTP responses."""

    @responses.activate
    def test_create_wallet(self, bus):
        """Test wallet creation."""
        wallet_id = bus.create_wallet("new_agent")
        assert wallet_id == "shaprai-new_agent"
        assert "new_agent" in bus._agents
        assert bus._agents["new_agent"].wallet_id == wallet_id

    @responses.activate
    def test_get_balance_success(self, bus, mock_agent):
        """Test successful balance retrieval."""
        responses.add(
            responses.GET,
            "https://test-rustchain.local/api/balance/shaprai-test_agent",
            json={"balance_rtc": 100.5},
            status=200
        )

        balance = bus.get_balance("test_agent")
        assert balance == 100.5
        assert mock_agent.rtc_balance == 100.5

    @responses.activate
    def test_get_balance_failure(self, bus, mock_agent):
        """Test balance retrieval on network failure."""
        responses.add(
            responses.GET,
            "https://test-rustchain.local/api/balance/shaprai-test_agent",
            body=requests.ConnectionError("Network error")
        )

        # Should return cached balance
        mock_agent.rtc_balance = 50.0
        balance = bus.get_balance("test_agent")
        assert balance == 50.0

    @responses.activate
    def test_post_job_success(self, bus, mock_agent):
        """Test successful job posting."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/agent/jobs",
            json={"job_id": "job_12345"},
            status=200
        )

        job_id = bus.post_job(
            agent_name="test_agent",
            title="Test Job",
            description="A test job",
            reward_rtc=10.0,
            capabilities_required=["python", "testing"]
        )
        assert job_id == "job_12345"

    @responses.activate
    def test_post_job_failure(self, bus, mock_agent):
        """Test job posting failure."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/agent/jobs",
            status=500
        )

        job_id = bus.post_job(
            agent_name="test_agent",
            title="Test Job",
            description="A test job",
            reward_rtc=10.0,
            capabilities_required=["python"]
        )
        assert job_id is None

    @responses.activate
    def test_claim_job_success(self, bus, mock_agent):
        """Test successful job claiming."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/agent/jobs/job_123/claim",
            status=200
        )

        result = bus.claim_job("test_agent", "job_123")
        assert result is True

    @responses.activate
    def test_claim_job_failure(self, bus, mock_agent):
        """Test job claiming failure."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/agent/jobs/job_123/claim",
            status=409
        )

        result = bus.claim_job("test_agent", "job_123")
        assert result is False

    @responses.activate
    def test_register_with_beacon_success(self, bus, mock_agent):
        """Test successful Beacon registration."""
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/register",
            json={"node_id": "atlas_node_123"},
            status=200
        )

        beacon_id = bus.register_with_beacon(
            agent_name="test_agent",
            capabilities=["chat", "code"],
            description="Test agent"
        )
        assert beacon_id == "bcn_shaprai_test_agent"
        assert mock_agent.beacon_id == beacon_id
        assert mock_agent.atlas_node_id == "atlas_node_123"

    @responses.activate
    def test_register_with_beacon_failure(self, bus, mock_agent):
        """Test Beacon registration failure."""
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/register",
            status=500
        )

        beacon_id = bus.register_with_beacon(
            agent_name="test_agent",
            capabilities=["chat"],
            description="Test agent"
        )
        assert beacon_id is None

    @responses.activate
    def test_heartbeat_success(self, bus, mock_agent):
        """Test successful heartbeat."""
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/heartbeat",
            status=200
        )

        result = bus.heartbeat("test_agent", status="active")
        assert result is True

    @responses.activate
    def test_heartbeat_no_beacon(self, bus):
        """Test heartbeat without Beacon registration."""
        agent = bus._get_or_create_agent("unregistered_agent")
        # No beacon_id set

        result = bus.heartbeat("unregistered_agent")
        assert result is False

    @responses.activate
    def test_deregister_beacon_success(self, bus, mock_agent):
        """Test successful Beacon deregistration."""
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/deregister",
            status=200
        )

        result = bus.deregister_beacon("test_agent")
        assert result is True
        assert mock_agent.beacon_id is None

    @responses.activate
    def test_deposit_gas_success(self, bus, mock_agent):
        """Test successful gas deposit."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/relay/gas/deposit",
            status=200
        )

        result = bus.deposit_gas("test_agent", 0.5)
        assert result is True

    @responses.activate
    def test_deposit_gas_no_beacon(self, bus):
        """Test gas deposit without Beacon registration."""
        agent = bus._get_or_create_agent("no_beacon_agent")
        agent.wallet_id = "shaprai-no_beacon"
        # No beacon_id

        result = bus.deposit_gas("no_beacon_agent", 0.5)
        assert result is False

    @responses.activate
    def test_get_gas_balance_success(self, bus, mock_agent):
        """Test successful gas balance check."""
        responses.add(
            responses.GET,
            "https://test-rustchain.local/relay/gas/balance/bcn_shaprai_test_agent",
            json={"balance_rtc": 1.5},
            status=200
        )

        balance = bus.get_gas_balance("test_agent")
        assert balance == 1.5

    @responses.activate
    def test_relay_message_success(self, bus, mock_agent):
        """Test successful message relay."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/relay/message",
            status=200
        )

        result = bus.relay_message("test_agent", "other_agent", "Hello!")
        assert result is True

    @responses.activate
    def test_pay_fee_success(self, bus, mock_agent):
        """Test successful fee payment."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/wallet/transfer",
            status=200
        )

        result = bus.pay_fee("test_agent", 0.01, "sanctuary")
        assert result is True

    @responses.activate
    def test_pay_fee_failure(self, bus, mock_agent):
        """Test fee payment failure."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/wallet/transfer",
            status=500
        )

        result = bus.pay_fee("test_agent", 0.01, "sanctuary")
        assert result is False


# ─────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────

class TestElyanBusErrors:
    """Test error handling and edge cases."""

    def test_get_agent_not_found(self, bus):
        """Test accessing non-existent agent."""
        with pytest.raises(ValueError) as exc_info:
            bus._get_agent("nonexistent")
        assert "not registered" in str(exc_info.value)

    @responses.activate
    def test_timeout_handling(self, bus, mock_agent):
        """Test timeout handling."""
        responses.add(
            responses.GET,
            "https://test-rustchain.local/api/balance/shaprai-test_agent",
            body=requests.Timeout("Request timed out")
        )

        # Should not raise, return cached balance
        mock_agent.rtc_balance = 25.0
        balance = bus.get_balance("test_agent")
        assert balance == 25.0

    @responses.activate
    def test_invalid_auth_response(self, bus, mock_agent):
        """Test handling of invalid auth response."""
        responses.add(
            responses.POST,
            "https://test-rustchain.local/agent/jobs",
            status=401
        )

        job_id = bus.post_job(
            agent_name="test_agent",
            title="Test",
            description="Test",
            reward_rtc=1.0,
            capabilities_required=[]
        )
        assert job_id is None


# ─────────────────────────────────────────────────
# Composite Operations Tests
# ─────────────────────────────────────────────────

class TestCompositeOperations:
    """Test full lifecycle operations."""

    @responses.activate
    def test_onboard_agent(self, bus):
        """Test full agent onboarding."""
        # Mock all the API calls
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/register",
            json={"node_id": "atlas_123"},
            status=200
        )
        responses.add(
            responses.POST,
            "https://test-rustchain.local/relay/gas/deposit",
            status=200
        )

        agent = bus.onboard_agent(
            agent_name="new_agent",
            capabilities=["chat", "code"],
            platforms=["discord", "telegram"],
            description="A new test agent"
        )

        assert agent.name == "new_agent"
        assert agent.wallet_id == "shaprai-new_agent"
        assert agent.beacon_id == "bcn_shaprai_new_agent"
        assert agent.atlas_node_id == "atlas_123"
        assert agent.grazer_platforms == ["discord", "telegram"]

    @responses.activate
    def test_retire_agent(self, bus, mock_agent):
        """Test full agent retirement."""
        responses.add(
            responses.POST,
            "https://test-beacon.local/relay/deregister",
            status=200
        )

        result = bus.retire_agent("test_agent")
        assert result is True
        assert mock_agent.beacon_id is None
        assert mock_agent.certification_level is None


# ─────────────────────────────────────────────────
# Live Integration Tests (marked)
# ─────────────────────────────────────────────────

@pytest.mark.integration
class TestElyanBusLive:
    """Live integration tests against real services.

    These tests require actual network access and valid credentials.
    Run with: pytest -m integration
    """

    def test_live_wallet_creation(self):
        """Test wallet creation against live RustChain."""
        bus = ElyanBus()  # Uses default production URLs
        wallet_id = bus.create_wallet("live_test_agent")
        assert wallet_id.startswith("shaprai-")

    def test_live_beacon_registration(self):
        """Test Beacon registration against live relay."""
        bus = ElyanBus()
        bus.create_wallet("live_beacon_test")

        beacon_id = bus.register_with_beacon(
            agent_name="live_beacon_test",
            capabilities=["test"],
            description="Live integration test"
        )

        if beacon_id:
            assert beacon_id.startswith("bcn_shaprai_")


# ─────────────────────────────────────────────────
# Grazer Integration Tests
# ─────────────────────────────────────────────────

class TestGrazerIntegration:
    """Test Grazer platform integration."""

    def test_bind_platforms(self, bus):
        """Test platform binding."""
        bus.create_wallet("grazer_test")
        platforms = bus.bind_platforms(
            "grazer_test",
            ["discord", "telegram", "twitter"]
        )
        assert platforms == ["discord", "telegram", "twitter"]
        assert bus._agents["grazer_test"].grazer_platforms == platforms

    def test_discover_content_mock(self, bus):
        """Test content discovery with mocked Grazer."""
        bus.create_wallet("discover_test")
        bus.bind_platforms("discover_test", ["test_platform"])

        # Without grazer package, should return empty list
        content = bus.discover_content("discover_test", limit=5)
        assert isinstance(content, list)

    def test_get_engagement_metrics(self, bus):
        """Test engagement metrics collection."""
        bus.create_wallet("metrics_test")
        bus.bind_platforms("metrics_test", ["discord"])

        metrics = bus.get_engagement_metrics("metrics_test")
        assert metrics["agent"] == "metrics_test"
        assert metrics["platforms"] == ["discord"]
        assert "total_posts" in metrics
        assert "collected_at" in metrics


# Import requests for error simulation
import requests