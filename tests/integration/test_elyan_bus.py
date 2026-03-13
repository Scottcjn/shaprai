# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""
Integration tests for ElyanBus — ShaprAI's communication layer.

Two modes:
  Mock mode (default):  pytest tests/integration/test_elyan_bus.py
  Live mode:            pytest tests/integration/test_elyan_bus.py -m integration

Mock mode uses the `responses` library to intercept HTTP calls.
Live mode hits real endpoints (RustChain, Beacon) — use with caution.

Requires:
  pip install pytest responses
"""

import time

import pytest
import responses

from shaprai.elyan_bus import (
    BEACON_RELAY,
    RUSTCHAIN_API,
    ElyanBus,
    ElyanAgent,
    GAS_FEE_TEXT_RELAY,
    SANCTUARY_SESSION_FEE,
    GRADUATION_FEE,
    PLATFORM_FEE_RATE,
)


# ─────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────


@pytest.fixture
def bus():
    """ElyanBus with default (production) endpoints."""
    return ElyanBus(admin_key="test-admin-key")


@pytest.fixture
def bus_with_agent(bus):
    """Bus with one pre-registered agent."""
    bus.create_wallet("testbot")
    return bus


# ─────────────────────────────────────────────────
# Mock Mode: RustChain — Wallet & Economy
# ─────────────────────────────────────────────────


class TestWalletCreation:
    """Wallet creation is local — no HTTP calls needed."""

    def test_create_wallet_returns_id(self, bus):
        wallet_id = bus.create_wallet("alpha")
        assert wallet_id == "shaprai-alpha"

    def test_create_wallet_registers_agent(self, bus):
        bus.create_wallet("alpha")
        agent = bus._agents["alpha"]
        assert isinstance(agent, ElyanAgent)
        assert agent.wallet_id == "shaprai-alpha"
        assert agent.registered_at is not None
        assert agent.registered_at <= time.time()

    def test_create_wallet_idempotent(self, bus):
        """Creating wallet twice for same agent doesn't clobber other fields."""
        bus.create_wallet("alpha")
        bus._agents["alpha"].beacon_id = "bcn_test"
        bus.create_wallet("alpha")
        assert bus._agents["alpha"].beacon_id == "bcn_test"

    def test_multiple_agents(self, bus):
        bus.create_wallet("alpha")
        bus.create_wallet("bravo")
        assert "alpha" in bus._agents
        assert "bravo" in bus._agents
        assert bus._agents["alpha"].wallet_id != bus._agents["bravo"].wallet_id


class TestBalance:
    @responses.activate
    def test_get_balance_success(self, bus_with_agent):
        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-testbot",
            json={"balance_rtc": 42.5},
            status=200,
        )
        balance = bus_with_agent.get_balance("testbot")
        assert balance == 42.5

    @responses.activate
    def test_get_balance_server_error(self, bus_with_agent):
        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-testbot",
            json={"error": "internal"},
            status=500,
        )
        balance = bus_with_agent.get_balance("testbot")
        # Falls back to cached balance (0.0 for fresh agent)
        assert balance == 0.0

    @responses.activate
    def test_get_balance_timeout(self, bus_with_agent):
        import requests as req_lib

        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-testbot",
            body=req_lib.exceptions.ConnectionError("timeout"),
        )
        balance = bus_with_agent.get_balance("testbot")
        assert balance == 0.0

    def test_get_balance_unregistered_agent(self, bus):
        with pytest.raises(ValueError, match="not registered"):
            bus.get_balance("ghost")


# ─────────────────────────────────────────────────
# Mock Mode: RustChain — Jobs (RIP-302)
# ─────────────────────────────────────────────────


class TestJobs:
    @responses.activate
    def test_post_job_success(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            json={"job_id": "job-123"},
            status=200,
        )
        job_id = bus_with_agent.post_job(
            "testbot",
            title="Fix bug",
            description="There is a bug",
            reward_rtc=10.0,
            capabilities_required=["python"],
        )
        assert job_id == "job-123"

        # Verify request body
        body = responses.calls[0].request.body
        import json
        payload = json.loads(body)
        assert payload["poster_wallet"] == "shaprai-testbot"
        assert payload["reward_rtc"] == 10.0
        assert payload["capabilities_required"] == ["python"]

    @responses.activate
    def test_post_job_failure(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            json={"error": "insufficient balance"},
            status=403,
        )
        job_id = bus_with_agent.post_job(
            "testbot", "Fix", "desc", 10.0, ["python"]
        )
        assert job_id is None

    @responses.activate
    def test_claim_job_success(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs/job-123/claim",
            json={"status": "claimed"},
            status=200,
        )
        assert bus_with_agent.claim_job("testbot", "job-123") is True

    @responses.activate
    def test_claim_job_already_claimed(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs/job-123/claim",
            json={"error": "already claimed"},
            status=409,
        )
        assert bus_with_agent.claim_job("testbot", "job-123") is False


class TestPayFee:
    @responses.activate
    def test_pay_fee_success(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.pay_fee("testbot", 0.01, "test_fee") is True

        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["from_miner"] == "shaprai-testbot"
        assert payload["to_miner"] == "founder_community"
        assert payload["amount_rtc"] == 0.01
        assert payload["memo"] == "shaprai:test_fee"

    @responses.activate
    def test_pay_fee_insufficient_balance(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            json={"error": "insufficient"},
            status=400,
        )
        assert bus_with_agent.pay_fee("testbot", 999.0, "big_fee") is False


# ─────────────────────────────────────────────────
# Mock Mode: Beacon — Registration & Discovery
# ─────────────────────────────────────────────────


class TestBeaconRegistration:
    @responses.activate
    def test_register_success(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json={"node_id": "atlas-node-42"},
            status=200,
        )
        beacon_id = bus_with_agent.register_with_beacon(
            "testbot",
            capabilities=["python", "distributed-systems"],
            description="Test agent",
        )
        assert beacon_id == "bcn_shaprai_testbot"

        agent = bus_with_agent._agents["testbot"]
        assert agent.beacon_id == "bcn_shaprai_testbot"
        assert agent.atlas_node_id == "atlas-node-42"

        # Verify request payload
        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["agent_id"] == "bcn_shaprai_testbot"
        assert payload["wallet_id"] == "shaprai-testbot"
        assert payload["framework"] == "shaprai"
        assert "python" in payload["capabilities"]

    @responses.activate
    def test_register_failure(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json={"error": "rate limited"},
            status=429,
        )
        beacon_id = bus_with_agent.register_with_beacon(
            "testbot", ["python"], "Test"
        )
        assert beacon_id is None
        assert bus_with_agent._agents["testbot"].beacon_id is None

    @responses.activate
    def test_register_network_error(self, bus_with_agent):
        import requests as req_lib

        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            body=req_lib.exceptions.ConnectionError("refused"),
        )
        beacon_id = bus_with_agent.register_with_beacon(
            "testbot", ["python"], "Test"
        )
        assert beacon_id is None


class TestHeartbeat:
    @responses.activate
    def test_heartbeat_success(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/heartbeat",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.heartbeat("testbot") is True

    def test_heartbeat_not_registered(self, bus_with_agent):
        """Heartbeat without Beacon registration returns False."""
        assert bus_with_agent.heartbeat("testbot") is False

    @responses.activate
    def test_heartbeat_custom_status(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/heartbeat",
            json={"status": "ok"},
            status=200,
        )
        bus_with_agent.heartbeat("testbot", status="idle")

        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["status"] == "idle"


class TestDeregisterBeacon:
    @responses.activate
    def test_deregister_success(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        bus_with_agent._agents["testbot"].atlas_node_id = "node-1"
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/deregister",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.deregister_beacon("testbot") is True
        assert bus_with_agent._agents["testbot"].beacon_id is None
        assert bus_with_agent._agents["testbot"].atlas_node_id is None

    def test_deregister_not_registered(self, bus_with_agent):
        """Deregistering agent that was never registered returns True."""
        assert bus_with_agent.deregister_beacon("testbot") is True


# ─────────────────────────────────────────────────
# Mock Mode: Gas (RIP-303)
# ─────────────────────────────────────────────────


class TestGas:
    @responses.activate
    def test_deposit_gas_success(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/gas/deposit",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.deposit_gas("testbot", 0.10) is True

    def test_deposit_gas_not_registered(self, bus_with_agent):
        """Can't deposit gas without Beacon registration."""
        assert bus_with_agent.deposit_gas("testbot", 0.10) is False

    @responses.activate
    def test_get_gas_balance(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/relay/gas/balance/bcn_shaprai_testbot",
            json={"balance_rtc": 0.05},
            status=200,
        )
        assert bus_with_agent.get_gas_balance("testbot") == 0.05

    def test_get_gas_balance_not_registered(self, bus_with_agent):
        assert bus_with_agent.get_gas_balance("testbot") == 0.0

    @responses.activate
    def test_relay_message(self, bus_with_agent):
        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/message",
            json={"status": "sent"},
            status=200,
        )
        assert bus_with_agent.relay_message("testbot", "other_agent", "hello") is True

        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["from"] == "bcn_shaprai_testbot"
        assert payload["to"] == "bcn_shaprai_other_agent"
        assert payload["content"] == "hello"

    def test_relay_message_not_registered(self, bus_with_agent):
        assert bus_with_agent.relay_message("testbot", "other", "hi") is False


# ─────────────────────────────────────────────────
# Mock Mode: Grazer — Content Discovery
# ─────────────────────────────────────────────────


class TestGrazer:
    def test_bind_platforms(self, bus_with_agent):
        platforms = bus_with_agent.bind_platforms(
            "testbot", ["moltbook", "twitter"]
        )
        assert platforms == ["moltbook", "twitter"]
        assert bus_with_agent._agents["testbot"].grazer_platforms == [
            "moltbook",
            "twitter",
        ]

    def test_discover_content_no_grazer(self, bus_with_agent):
        """Without grazer package, returns empty list gracefully."""
        bus_with_agent.bind_platforms("testbot", ["moltbook"])
        results = bus_with_agent.discover_content("testbot", topic="AI")
        assert results == []

    def test_engagement_metrics_structure(self, bus_with_agent):
        bus_with_agent.bind_platforms("testbot", ["moltbook"])
        metrics = bus_with_agent.get_engagement_metrics("testbot")
        assert metrics["agent"] == "testbot"
        assert metrics["platforms"] == ["moltbook"]
        assert "total_posts" in metrics
        assert "collected_at" in metrics


# ─────────────────────────────────────────────────
# Mock Mode: Sanctuary Fees
# ─────────────────────────────────────────────────


class TestSanctuaryFees:
    @responses.activate
    def test_sanctuary_session_fee(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.pay_sanctuary_fee("testbot") is True

        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["amount_rtc"] == SANCTUARY_SESSION_FEE
        assert "sanctuary_session" in payload["memo"]

    @responses.activate
    def test_graduation_fee(self, bus_with_agent):
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            json={"status": "ok"},
            status=200,
        )
        assert bus_with_agent.pay_graduation_fee("testbot") is True

        import json
        payload = json.loads(responses.calls[0].request.body)
        assert payload["amount_rtc"] == GRADUATION_FEE
        assert "elyan_certification" in payload["memo"]


# ─────────────────────────────────────────────────
# Mock Mode: Composite Operations
# ─────────────────────────────────────────────────


class TestOnboarding:
    @responses.activate
    def test_full_onboarding(self, bus):
        """Test the complete onboard_agent lifecycle."""
        # Mock Beacon registration
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json={"node_id": "atlas-42"},
            status=200,
        )
        # Mock gas deposit
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/gas/deposit",
            json={"status": "ok"},
            status=200,
        )

        agent = bus.onboard_agent(
            agent_name="omega",
            capabilities=["python", "rust"],
            platforms=["moltbook", "twitter"],
            description="Test onboarding",
        )

        assert agent.name == "omega"
        assert agent.wallet_id == "shaprai-omega"
        assert agent.beacon_id == "bcn_shaprai_omega"
        assert agent.atlas_node_id == "atlas-42"
        assert agent.grazer_platforms == ["moltbook", "twitter"]
        assert agent.registered_at is not None

    @responses.activate
    def test_onboarding_beacon_failure_partial(self, bus):
        """If Beacon fails, wallet is still created but beacon/atlas are None."""
        import requests as req_lib

        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            body=req_lib.exceptions.ConnectionError("down"),
        )
        # Gas deposit won't be called since beacon_id is None
        # but deposit_gas will return False

        agent = bus.onboard_agent(
            "omega", ["python"], ["moltbook"], "Test"
        )

        assert agent.wallet_id == "shaprai-omega"
        assert agent.beacon_id is None
        assert agent.atlas_node_id is None


class TestRetirement:
    @responses.activate
    def test_full_retirement(self, bus):
        # Set up an agent first
        bus.create_wallet("omega")
        bus._agents["omega"].beacon_id = "bcn_shaprai_omega"
        bus._agents["omega"].atlas_node_id = "atlas-42"
        bus._agents["omega"].certification_level = "flame"

        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/deregister",
            json={"status": "ok"},
            status=200,
        )

        assert bus.retire_agent("omega") is True
        agent = bus._agents["omega"]
        assert agent.beacon_id is None
        assert agent.atlas_node_id is None
        assert agent.certification_level is None
        # Wallet is preserved (archived, not deleted)
        assert agent.wallet_id == "shaprai-omega"


# ─────────────────────────────────────────────────
# Mock Mode: Error Handling
# ─────────────────────────────────────────────────


class TestErrorHandling:
    def test_unregistered_agent_raises(self, bus):
        """Operations on unknown agents raise ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            bus.get_balance("nobody")
        with pytest.raises(ValueError, match="not registered"):
            bus.post_job("nobody", "t", "d", 1.0, [])
        with pytest.raises(ValueError, match="not registered"):
            bus.claim_job("nobody", "job-1")

    @responses.activate
    def test_invalid_auth_key(self, bus_with_agent):
        """Server rejects invalid admin key."""
        responses.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            json={"error": "unauthorized"},
            status=401,
        )
        job_id = bus_with_agent.post_job(
            "testbot", "Test", "desc", 5.0, ["python"]
        )
        assert job_id is None

    @responses.activate
    def test_connection_timeout_all_endpoints(self, bus_with_agent):
        """All endpoints handle connection errors gracefully."""
        import requests as req_lib

        bus_with_agent._agents["testbot"].beacon_id = "bcn_shaprai_testbot"

        # Balance
        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-testbot",
            body=req_lib.exceptions.Timeout("timeout"),
        )
        assert bus_with_agent.get_balance("testbot") == 0.0

        # Heartbeat
        responses.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/heartbeat",
            body=req_lib.exceptions.Timeout("timeout"),
        )
        assert bus_with_agent.heartbeat("testbot") is False

        # Gas balance
        responses.add(
            responses.GET,
            f"{RUSTCHAIN_API}/relay/gas/balance/bcn_shaprai_testbot",
            body=req_lib.exceptions.Timeout("timeout"),
        )
        assert bus_with_agent.get_gas_balance("testbot") == 0.0


# ─────────────────────────────────────────────────
# Mock Mode: Constants & Configuration
# ─────────────────────────────────────────────────


class TestConstants:
    """Verify fee constants match RIP specifications."""

    def test_gas_fees(self):
        assert GAS_FEE_TEXT_RELAY == 0.0001
        assert SANCTUARY_SESSION_FEE == 0.01
        assert GRADUATION_FEE == 0.10

    def test_economy_fees(self):
        assert PLATFORM_FEE_RATE == 0.05
        assert 0 < PLATFORM_FEE_RATE < 1

    def test_bus_defaults(self):
        bus = ElyanBus()
        assert bus.rustchain_url == RUSTCHAIN_API
        assert bus.beacon_url == BEACON_RELAY
        assert bus.admin_key is None
        assert bus._session.verify is False


# ─────────────────────────────────────────────────
# Live Mode (integration marker)
# ─────────────────────────────────────────────────


@pytest.mark.integration
class TestLiveRustChain:
    """Tests against live RustChain endpoint.

    Run with: pytest -m integration
    WARNING: These hit real servers. Use sparingly.
    """

    @pytest.fixture
    def live_bus(self):
        return ElyanBus()

    def test_live_wallet_creation(self, live_bus):
        """Create wallet locally — no HTTP call needed."""
        wallet_id = live_bus.create_wallet("live-test-agent")
        assert wallet_id == "shaprai-live-test-agent"

    def test_live_balance_check(self, live_bus):
        """Check balance on a fresh (nonexistent) wallet — should return 0."""
        live_bus.create_wallet("live-test-agent")
        balance = live_bus.get_balance("live-test-agent")
        # Fresh wallet has 0 balance (or server returns error → 0)
        assert isinstance(balance, float)
        assert balance >= 0.0

    def test_live_beacon_registration(self, live_bus):
        """Try to register with Beacon (may fail if endpoint is down)."""
        live_bus.create_wallet("live-test-agent")
        beacon_id = live_bus.register_with_beacon(
            "live-test-agent",
            capabilities=["integration-test"],
            description="ShaprAI integration test — safe to ignore",
        )
        # Beacon may or may not be available
        if beacon_id:
            assert beacon_id == "bcn_shaprai_live-test-agent"
            # Clean up
            live_bus.deregister_beacon("live-test-agent")
