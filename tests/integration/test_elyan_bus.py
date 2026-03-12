# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""
Integration tests for Elyan Bus.

The Elyan Bus is ShaprAI's unified integration layer that connects to:
- RustChain: Wallet creation, balance queries, job economy (RIP-302)
- Beacon: Agent registration, discovery, heartbeat
- Atlas: 3D network visualization node placement
- Grazer: Content discovery and engagement metrics
- Gas: RTC gas deposits for Beacon relay messaging

Test Modes
==========

Mock Mode (default, for CI):
    All HTTP requests are mocked using the responses library.
    Tests run without network access.
    
    Run with: pytest tests/integration/test_elyan_bus.py

Live Mode (requires network):
    Tests against real Elyan network endpoints at:
    - https://50.28.86.131 (RustChain API)
    - https://rustchain.org (Beacon Relay)
    
    Run with: pytest tests/integration/test_elyan_bus.py -m integration

Test Coverage
============

- Wallet creation and balance queries
- Beacon registration with capabilities
- Gas deposit flow and balance checks
- Job posting and claiming (RIP-302 economy)
- Agent-to-agent messaging via Beacon relay
- Heartbeat and deregistration
- Full agent lifecycle (onboard/retire)
- Error handling (timeout, 500, invalid auth)
- Sanctuary fees payment
"""

import time
import pytest
import responses
from unittest.mock import patch, MagicMock

from shaprai.elyan_bus import (
    ElyanBus,
    ElyanAgent,
    RUSTCHAIN_API,
    BEACON_RELAY,
    GAS_FEE_TEXT_RELAY,
    GAS_FEE_DISCOVERY,
    GAS_FEE_ATTACHMENT,
    SANCTUARY_SESSION_FEE,
    GRADUATION_FEE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Response Builders
# ─────────────────────────────────────────────────────────────────────────────

class MockResponses:
    """Helper class for building mock API responses."""
    
    @staticmethod
    def balance_success(wallet_id: str, balance: float = 1.5) -> dict:
        """Create a successful balance response."""
        return {
            "wallet_id": wallet_id,
            "balance_rtc": balance,
            "balance_rust": balance * 1000,
        }
    
    @staticmethod
    def beacon_register_success(agent_id: str, node_id: str = "node_12345") -> dict:
        """Create a successful Beacon registration response."""
        return {
            "agent_id": agent_id,
            "node_id": node_id,
            "status": "registered",
            "registered_at": "2026-03-12T00:00:00Z",
        }
    
    @staticmethod
    def job_post_success(job_id: str = "job_12345") -> dict:
        """Create a successful job posting response."""
        return {
            "job_id": job_id,
            "status": "posted",
            "posted_at": "2026-03-12T00:00:00Z",
        }
    
    @staticmethod
    def gas_balance_success(balance: float = 0.5) -> dict:
        """Create a successful gas balance response."""
        return {
            "balance_rtc": balance,
        }
    
    @staticmethod
    def transfer_success() -> dict:
        """Create a successful transfer response."""
        return {
            "status": "success",
            "tx_hash": "tx_abc123",
        }
    
    @staticmethod
    def error_response(error_type: str = "server_error", message: str = "Internal error") -> dict:
        """Create an error response."""
        return {
            "error": error_type,
            "message": message,
        }


# ─────────────────────────────────────────────────────────────────────────────
# RustChain: Wallet and Balance Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalletCreation:
    """Tests for wallet creation functionality."""
    
    def test_create_wallet_returns_wallet_id(self, mock_bus):
        """Wallet creation should return a properly formatted wallet ID."""
        wallet_id = mock_bus.create_wallet("my_agent")
        
        assert wallet_id == "shaprai-my_agent"
    
    def test_create_wallet_registers_agent(self, mock_bus):
        """Creating a wallet should register the agent internally."""
        mock_bus.create_wallet("test_agent")
        
        assert "test_agent" in mock_bus._agents
        agent = mock_bus._agents["test_agent"]
        assert agent.wallet_id == "shaprai-test_agent"
        assert agent.registered_at is not None
    
    def test_create_wallet_is_idempotent(self, mock_bus):
        """Creating a wallet for an existing agent should return same ID."""
        first_id = mock_bus.create_wallet("my_agent")
        second_id = mock_bus.create_wallet("my_agent")
        
        assert first_id == second_id
    
    def test_create_wallet_sets_timestamp(self, mock_bus):
        """Wallet creation should set a registration timestamp."""
        before = time.time()
        mock_bus.create_wallet("timestamp_agent")
        after = time.time()
        
        agent = mock_bus._agents["timestamp_agent"]
        assert before <= agent.registered_at <= after


class TestBalanceQueries:
    """Tests for RTC balance query functionality."""
    
    def test_get_balance_success(self, mock_bus, mock_rustchain):
        """Balance query should return the correct RTC balance."""
        # Setup agent
        mock_bus.create_wallet("balance_agent")
        
        # Mock the balance endpoint
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-balance_agent",
            json=MockResponses.balance_success("shaprai-balance_agent", 2.5),
            status=200,
        )
        
        balance = mock_bus.get_balance("balance_agent")
        
        assert balance == 2.5
    
    def test_get_balance_updates_agent_state(self, mock_bus, mock_rustchain):
        """Balance query should update the agent's cached balance."""
        mock_bus.create_wallet("state_agent")
        
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-state_agent",
            json=MockResponses.balance_success("shaprai-state_agent", 3.0),
            status=200,
        )
        
        mock_bus.get_balance("state_agent")
        
        agent = mock_bus._agents["state_agent"]
        assert agent.rtc_balance == 3.0
    
    def test_get_balance_returns_cached_on_network_error(self, mock_bus, mock_rustchain):
        """Balance query should return cached value on network failure."""
        mock_bus.create_wallet("cache_agent")
        mock_bus._agents["cache_agent"].rtc_balance = 1.5
        
        # Mock a failed request using RequestException
        from requests.exceptions import ConnectionError
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-cache_agent",
            body=ConnectionError("Network error"),
        )
        
        balance = mock_bus.get_balance("cache_agent")
        
        assert balance == 1.5  # Returns cached value
    
    def test_get_balance_raises_for_unknown_agent(self, mock_bus):
        """Balance query for unregistered agent should raise ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            mock_bus.get_balance("unknown_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Beacon: Registration and Discovery Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBeaconRegistration:
    """Tests for Beacon registration functionality."""
    
    def test_register_with_beacon_success(self, mock_bus, mock_rustchain):
        """Beacon registration should return a valid beacon ID."""
        mock_bus.create_wallet("beacon_agent")
        
        # Mock the Beacon relay registration
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json=MockResponses.beacon_register_success(
                "bcn_shaprai_beacon_agent", "node_12345"
            ),
            status=200,
        )
        
        beacon_id = mock_bus.register_with_beacon(
            "beacon_agent",
            ["text_generation", "code_assistant"],
            "Test agent for ShaprAI",
        )
        
        assert beacon_id == "bcn_shaprai_beacon_agent"
    
    def test_register_sets_beacon_and_atlas_ids(self, mock_bus, mock_rustchain):
        """Registration should set both beacon_id and atlas_node_id."""
        mock_bus.create_wallet("ids_agent")
        
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json=MockResponses.beacon_register_success(
                "bcn_shaprai_ids_agent", "atlas_node_xyz"
            ),
            status=200,
        )
        
        mock_bus.register_with_beacon("ids_agent", ["chat"], "Test agent")
        
        agent = mock_bus._agents["ids_agent"]
        assert agent.beacon_id == "bcn_shaprai_ids_agent"
        assert agent.atlas_node_id == "atlas_node_xyz"
    
    def test_register_includes_wallet_id(self, mock_bus, mock_rustchain):
        """Registration request should include the agent's wallet ID."""
        mock_bus.create_wallet("wallet_agent")
        
        # Capture the request body
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps(MockResponses.beacon_register_success(
                "bcn_shaprai_wallet_agent", "node_123"
            )))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            callback=capture_body,
        )
        
        mock_bus.register_with_beacon("wallet_agent", ["chat"], "Test")
        
        assert captured_body["data"]["wallet_id"] == "shaprai-wallet_agent"
    
    def test_register_includes_capabilities(self, mock_bus, mock_rustchain):
        """Registration request should include agent capabilities."""
        mock_bus.create_wallet("cap_agent")
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps(MockResponses.beacon_register_success(
                "bcn_shaprai_cap_agent", "node_123"
            )))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            callback=capture_body,
        )
        
        mock_bus.register_with_beacon(
            "cap_agent",
            ["text_gen", "code_review", "data_analysis"],
            "Multi-capability agent",
        )
        
        assert captured_body["data"]["capabilities"] == [
            "text_gen", "code_review", "data_analysis"
        ]


class TestHeartbeat:
    """Tests for Beacon heartbeat functionality."""
    
    def test_heartbeat_success(self, mock_bus, mock_rustchain):
        """Heartbeat should return True on success."""
        mock_bus.create_wallet("hb_agent")
        mock_bus._agents["hb_agent"].beacon_id = "bcn_shaprai_hb_agent"
        
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/heartbeat",
            json={"status": "ok"},
            status=200,
        )
        
        result = mock_bus.heartbeat("hb_agent", status="active")
        
        assert result is True
    
    def test_heartbeat_without_registration_fails(self, mock_bus):
        """Heartbeat should fail if agent is not registered with Beacon."""
        mock_bus.create_wallet("unregistered_agent")
        
        result = mock_bus.heartbeat("unregistered_agent")
        
        assert result is False
    
    def test_heartbeat_includes_status(self, mock_bus, mock_rustchain):
        """Heartbeat should include the agent's status."""
        mock_bus.create_wallet("status_agent")
        mock_bus._agents["status_agent"].beacon_id = "bcn_shaprai_status_agent"
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps({"status": "ok"}))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{BEACON_RELAY}/relay/heartbeat",
            callback=capture_body,
        )
        
        mock_bus.heartbeat("status_agent", status="busy")
        
        assert captured_body["data"]["status"] == "busy"


class TestDeregistration:
    """Tests for Beacon deregistration functionality."""
    
    def test_deregister_success(self, mock_bus, mock_rustchain):
        """Deregistration should clear beacon and atlas IDs."""
        mock_bus.create_wallet("dereg_agent")
        mock_bus._agents["dereg_agent"].beacon_id = "bcn_shaprai_dereg_agent"
        mock_bus._agents["dereg_agent"].atlas_node_id = "node_123"
        
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/deregister",
            json={"status": "deregistered"},
            status=200,
        )
        
        result = mock_bus.deregister_beacon("dereg_agent")
        
        assert result is True
        agent = mock_bus._agents["dereg_agent"]
        assert agent.beacon_id is None
        assert agent.atlas_node_id is None
    
    def test_deregister_without_beacon_id_returns_true(self, mock_bus):
        """Deregistration without beacon ID should return True (no-op)."""
        mock_bus.create_wallet("no_beacon_agent")
        
        result = mock_bus.deregister_beacon("no_beacon_agent")
        
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# Gas: Deposit and Balance Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGasDeposits:
    """Tests for RTC gas deposit functionality."""
    
    def test_deposit_gas_success(self, mock_bus, mock_rustchain):
        """Gas deposit should return True on success."""
        mock_bus.create_wallet("gas_agent")
        mock_bus._agents["gas_agent"].beacon_id = "bcn_shaprai_gas_agent"
        
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/gas/deposit",
            json={"status": "deposited"},
            status=200,
        )
        
        result = mock_bus.deposit_gas("gas_agent", 0.5)
        
        assert result is True
    
    def test_deposit_gas_requires_beacon_registration(self, mock_bus):
        """Gas deposit should fail without Beacon registration."""
        mock_bus.create_wallet("no_beacon_gas_agent")
        
        result = mock_bus.deposit_gas("no_beacon_gas_agent", 0.5)
        
        assert result is False
    
    def test_deposit_gas_amount_included(self, mock_bus, mock_rustchain):
        """Gas deposit should include the correct RTC amount."""
        mock_bus.create_wallet("amount_agent")
        mock_bus._agents["amount_agent"].beacon_id = "bcn_shaprai_amount_agent"
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps({"status": "deposited"}))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/gas/deposit",
            callback=capture_body,
        )
        
        mock_bus.deposit_gas("amount_agent", 0.25)
        
        assert captured_body["data"]["amount_rtc"] == 0.25


class TestGasBalance:
    """Tests for gas balance query functionality."""
    
    def test_get_gas_balance_success(self, mock_bus, mock_rustchain):
        """Gas balance query should return the correct amount."""
        mock_bus.create_wallet("gas_bal_agent")
        mock_bus._agents["gas_bal_agent"].beacon_id = "bcn_shaprai_gas_bal_agent"
        
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/relay/gas/balance/bcn_shaprai_gas_bal_agent",
            json=MockResponses.gas_balance_success(0.75),
            status=200,
        )
        
        balance = mock_bus.get_gas_balance("gas_bal_agent")
        
        assert balance == 0.75
    
    def test_get_gas_balance_without_beacon_returns_zero(self, mock_bus):
        """Gas balance should return 0 for agents without Beacon registration."""
        mock_bus.create_wallet("no_gas_agent")
        
        balance = mock_bus.get_gas_balance("no_gas_agent")
        
        assert balance == 0.0
    
    def test_get_gas_balance_on_error_returns_zero(self, mock_bus, mock_rustchain):
        """Gas balance should return 0 on network errors."""
        mock_bus.create_wallet("error_gas_agent")
        mock_bus._agents["error_gas_agent"].beacon_id = "bcn_shaprai_error_gas_agent"
        
        from requests.exceptions import ConnectionError
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/relay/gas/balance/bcn_shaprai_error_gas_agent",
            body=ConnectionError("Network error"),
        )
        
        balance = mock_bus.get_gas_balance("error_gas_agent")
        
        assert balance == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# RIP-302: Job Economy Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJobPosting:
    """Tests for RIP-302 job posting functionality."""
    
    def test_post_job_success(self, mock_bus, mock_rustchain):
        """Job posting should return a job ID on success."""
        mock_bus.create_wallet("poster_agent")
        
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            json=MockResponses.job_post_success("job_abc123"),
            status=200,
        )
        
        job_id = mock_bus.post_job(
            "poster_agent",
            title="Code Review Task",
            description="Review Python code for bugs",
            reward_rtc=0.5,
            capabilities_required=["code_review", "python"],
        )
        
        assert job_id == "job_abc123"
    
    def test_post_job_includes_wallet(self, mock_bus, mock_rustchain):
        """Job posting should include the poster's wallet ID."""
        mock_bus.create_wallet("wallet_poster")
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps(MockResponses.job_post_success()))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            callback=capture_body,
        )
        
        mock_bus.post_job(
            "wallet_poster",
            title="Test Job",
            description="Test",
            reward_rtc=0.1,
            capabilities_required=["test"],
        )
        
        assert captured_body["data"]["poster_wallet"] == "shaprai-wallet_poster"
    
    def test_post_job_on_error_returns_none(self, mock_bus, mock_rustchain):
        """Job posting should return None on network errors."""
        mock_bus.create_wallet("error_poster")
        
        from requests.exceptions import ConnectionError
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            body=ConnectionError("Network error"),
        )
        
        job_id = mock_bus.post_job(
            "error_poster",
            title="Test",
            description="Test",
            reward_rtc=0.1,
            capabilities_required=["test"],
        )
        
        assert job_id is None


class TestJobClaiming:
    """Tests for RIP-302 job claiming functionality."""
    
    def test_claim_job_success(self, mock_bus, mock_rustchain):
        """Job claiming should return True on success."""
        mock_bus.create_wallet("claimer_agent")
        
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs/job_123/claim",
            json={"status": "claimed"},
            status=200,
        )
        
        result = mock_bus.claim_job("claimer_agent", "job_123")
        
        assert result is True
    
    def test_claim_job_includes_wallet(self, mock_bus, mock_rustchain):
        """Job claiming should include the claimer's wallet ID."""
        mock_bus.create_wallet("wallet_claimer")
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps({"status": "claimed"}))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs/job_456/claim",
            callback=capture_body,
        )
        
        mock_bus.claim_job("wallet_claimer", "job_456")
        
        assert captured_body["data"]["claimer_wallet"] == "shaprai-wallet_claimer"
    
    def test_claim_job_on_error_returns_false(self, mock_bus, mock_rustchain):
        """Job claiming should return False on network errors."""
        mock_bus.create_wallet("error_claimer")
        
        from requests.exceptions import ConnectionError
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs/job_error/claim",
            body=ConnectionError("Network error"),
        )
        
        result = mock_bus.claim_job("error_claimer", "job_error")
        
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Relay Messaging Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRelayMessaging:
    """Tests for agent-to-agent messaging via Beacon relay."""
    
    def test_relay_message_success(self, mock_bus, mock_rustchain):
        """Relay messaging should return True on success."""
        mock_bus.create_wallet("sender")
        mock_bus._agents["sender"].beacon_id = "bcn_shaprai_sender"
        
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/message",
            json={"status": "sent"},
            status=200,
        )
        
        result = mock_bus.relay_message("sender", "receiver", "Hello!")
        
        assert result is True
    
    def test_relay_message_without_beacon_fails(self, mock_bus):
        """Relay messaging should fail without Beacon registration."""
        mock_bus.create_wallet("no_beacon_sender")
        
        result = mock_bus.relay_message("no_beacon_sender", "receiver", "Hello!")
        
        assert result is False
    
    def test_relay_message_formats_recipient_id(self, mock_bus, mock_rustchain):
        """Relay messaging should format the recipient beacon ID correctly."""
        mock_bus.create_wallet("format_sender")
        mock_bus._agents["format_sender"].beacon_id = "bcn_shaprai_format_sender"
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps({"status": "sent"}))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/message",
            callback=capture_body,
        )
        
        mock_bus.relay_message("format_sender", "target_agent", "Test message")
        
        assert captured_body["data"]["to"] == "bcn_shaprai_target_agent"


# ─────────────────────────────────────────────────────────────────────────────
# Grazer: Platform Binding Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGrazerBinding:
    """Tests for Grazer platform binding functionality."""
    
    def test_bind_platforms_success(self, mock_bus):
        """Platform binding should store the platforms list."""
        mock_bus.create_wallet("grazer_agent")
        
        platforms = mock_bus.bind_platforms(
            "grazer_agent",
            ["twitter", "discord", "slack"]
        )
        
        assert platforms == ["twitter", "discord", "slack"]
        assert mock_bus._agents["grazer_agent"].grazer_platforms == platforms
    
    def test_bind_platforms_replaces_existing(self, mock_bus):
        """Platform binding should replace existing platforms."""
        mock_bus.create_wallet("replace_agent")
        mock_bus._agents["replace_agent"].grazer_platforms = ["old_platform"]
        
        mock_bus.bind_platforms("replace_agent", ["new_platform"])
        
        assert mock_bus._agents["replace_agent"].grazer_platforms == ["new_platform"]


class TestContentDiscovery:
    """Tests for Grazer content discovery functionality."""
    
    def test_discover_content_without_grazer_package(self, mock_bus):
        """Content discovery should handle missing grazer-skill package."""
        mock_bus.create_wallet("no_grazer_agent")
        mock_bus._agents["no_grazer_agent"].grazer_platforms = ["twitter"]
        
        # Should not raise, returns empty list
        results = mock_bus.discover_content("no_grazer_agent", limit=10)
        
        assert results == []
    
    def test_discover_content_with_grazer(self, mock_bus):
        """Content discovery should use GrazerClient when available."""
        mock_bus.create_wallet("grazer_discover")
        mock_bus._agents["grazer_discover"].grazer_platforms = ["twitter"]
        
        # Mock the grazer module import
        mock_grazer = MagicMock()
        mock_client = MagicMock()
        mock_client.discover.return_value = [
            {"id": "1", "content": "test"},
            {"id": "2", "content": "test2"},
        ]
        mock_grazer.GrazerClient.return_value = mock_client
        
        with patch.dict("sys.modules", {"grazer": mock_grazer}):
            results = mock_bus.discover_content("grazer_discover", limit=5)
            
            assert len(results) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Sanctuary Fees Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSanctuaryFees:
    """Tests for Sanctuary education fee payments."""
    
    def test_pay_sanctuary_fee_amount(self, mock_bus, mock_rustchain):
        """Sanctuary session fee should be 0.01 RTC."""
        mock_bus.create_wallet("sanctuary_agent")
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps(MockResponses.transfer_success()))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            callback=capture_body,
        )
        
        mock_bus.pay_sanctuary_fee("sanctuary_agent")
        
        assert captured_body["data"]["amount_rtc"] == SANCTUARY_SESSION_FEE
        assert captured_body["data"]["memo"] == "shaprai:sanctuary_session"
    
    def test_pay_graduation_fee_amount(self, mock_bus, mock_rustchain):
        """Graduation fee should be 0.10 RTC."""
        mock_bus.create_wallet("grad_agent")
        
        captured_body = {}
        
        def capture_body(request):
            import json
            captured_body["data"] = json.loads(request.body)
            return (200, {}, json.dumps(MockResponses.transfer_success()))
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            callback=capture_body,
        )
        
        mock_bus.pay_graduation_fee("grad_agent")
        
        assert captured_body["data"]["amount_rtc"] == GRADUATION_FEE
        assert captured_body["data"]["memo"] == "shaprai:elyan_certification"


# ─────────────────────────────────────────────────────────────────────────────
# Full Lifecycle Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentLifecycle:
    """Tests for full agent onboarding and retirement."""
    
    def test_onboard_agent_creates_all_registrations(self, mock_bus, mock_rustchain):
        """Onboarding should create wallet, beacon, atlas, and grazer bindings."""
        # Mock all endpoints
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/register",
            json=MockResponses.beacon_register_success(
                "bcn_shaprai_lifecycle_agent", "node_lifecycle"
            ),
            status=200,
        )
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/relay/gas/deposit",
            json={"status": "deposited"},
            status=200,
        )
        
        agent = mock_bus.onboard_agent(
            "lifecycle_agent",
            capabilities=["chat", "code"],
            platforms=["twitter", "discord"],
            description="Full lifecycle test agent",
        )
        
        assert agent.wallet_id == "shaprai-lifecycle_agent"
        assert agent.beacon_id == "bcn_shaprai_lifecycle_agent"
        assert agent.atlas_node_id == "node_lifecycle"
        assert agent.grazer_platforms == ["twitter", "discord"]
    
    def test_retire_agent_clears_registrations(self, mock_bus, mock_rustchain):
        """Retirement should clear beacon and atlas registrations."""
        mock_bus.create_wallet("retire_agent")
        mock_bus._agents["retire_agent"].beacon_id = "bcn_shaprai_retire_agent"
        mock_bus._agents["retire_agent"].atlas_node_id = "node_retire"
        mock_bus._agents["retire_agent"].certification_level = "flame"
        
        mock_rustchain.add(
            responses.POST,
            f"{BEACON_RELAY}/relay/deregister",
            json={"status": "deregistered"},
            status=200,
        )
        
        result = mock_bus.retire_agent("retire_agent")
        
        assert result is True
        agent = mock_bus._agents["retire_agent"]
        assert agent.beacon_id is None
        assert agent.atlas_node_id is None
        assert agent.certification_level is None


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:
    """Tests for error handling across all operations."""
    
    def test_timeout_handling(self, mock_bus, mock_rustchain):
        """Operations should handle request timeouts gracefully."""
        mock_bus.create_wallet("timeout_agent")
        
        from requests.exceptions import Timeout
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-timeout_agent",
            body=Timeout("Request timed out"),
        )
        
        # Should return cached balance (0.0) instead of raising
        balance = mock_bus.get_balance("timeout_agent")
        assert balance == 0.0
    
    def test_500_error_handling(self, mock_bus, mock_rustchain):
        """Operations should handle 500 server errors gracefully."""
        mock_bus.create_wallet("error_agent")
        
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-error_agent",
            json={"error": "Internal server error"},
            status=500,
        )
        
        # Should return cached balance (0.0)
        balance = mock_bus.get_balance("error_agent")
        assert balance == 0.0
    
    def test_invalid_auth_handling(self, mock_bus, mock_rustchain):
        """Operations should handle 401 unauthorized errors."""
        mock_bus.create_wallet("auth_agent")
        mock_bus.admin_key = "invalid_key"
        
        mock_rustchain.add(
            responses.POST,
            f"{RUSTCHAIN_API}/agent/jobs",
            json={"error": "Unauthorized"},
            status=401,
        )
        
        result = mock_bus.post_job(
            "auth_agent",
            title="Test",
            description="Test",
            reward_rtc=0.1,
            capabilities_required=["test"],
        )
        
        assert result is None
    
    def test_connection_error_handling(self, mock_bus, mock_rustchain):
        """Operations should handle connection errors gracefully."""
        mock_bus.create_wallet("conn_error_agent")
        
        from requests.exceptions import ConnectionError
        mock_rustchain.add(
            responses.GET,
            f"{RUSTCHAIN_API}/api/balance/shaprai-conn_error_agent",
            body=ConnectionError("Connection refused"),
        )
        
        # Should return cached balance
        balance = mock_bus.get_balance("conn_error_agent")
        assert balance == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Admin Key Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminKeyAuth:
    """Tests for admin key authentication."""
    
    def test_admin_key_in_headers(self, mock_bus, mock_rustchain):
        """Admin key should be included in request headers."""
        mock_bus.admin_key = "test_admin_key"
        mock_bus.create_wallet("admin_agent")
        
        captured_headers = {}
        
        def capture_headers(request):
            captured_headers["X-Admin-Key"] = request.headers.get("X-Admin-Key")
            return (200, {}, '{"status": "ok"}')
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            callback=capture_headers,
        )
        
        mock_bus.pay_fee("admin_agent", 0.01, "test")
        
        assert captured_headers["X-Admin-Key"] == "test_admin_key"
    
    def test_no_admin_key_no_header(self, mock_bus, mock_rustchain):
        """Requests should work without admin key header."""
        mock_bus.admin_key = None
        mock_bus.create_wallet("no_admin_agent")
        
        captured_headers = {}
        
        def capture_headers(request):
            captured_headers["X-Admin-Key"] = request.headers.get("X-Admin-Key")
            return (200, {}, '{"status": "ok"}')
        
        mock_rustchain.add_callback(
            responses.POST,
            f"{RUSTCHAIN_API}/wallet/transfer",
            callback=capture_headers,
        )
        
        mock_bus.pay_fee("no_admin_agent", 0.01, "test")
        
        assert captured_headers["X-Admin-Key"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Live Integration Tests (requires network)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestLiveIntegration:
    """
    Live integration tests against real Elyan network endpoints.
    
    These tests require network access and will make real API calls.
    Run with: pytest tests/integration/test_elyan_bus.py -m integration
    
    Prerequisites:
    - Set ELYAN_ADMIN_KEY environment variable for authenticated operations
    - Ensure RustChain and Beacon endpoints are accessible
    """
    
    @pytest.mark.integration
    def test_live_rustchain_connectivity(self, live_bus):
        """Test basic connectivity to RustChain API."""
        import requests
        
        # Just check the endpoint is reachable
        try:
            resp = requests.get(
                f"{RUSTCHAIN_API}/api/health",
                timeout=10,
                verify=False,
            )
            # Any response means the server is up
            assert resp.status_code in [200, 404, 403]
        except requests.exceptions.RequestException as e:
            pytest.skip(f"RustChain endpoint not reachable: {e}")
    
    @pytest.mark.integration
    def test_live_beacon_connectivity(self, live_bus):
        """Test basic connectivity to Beacon relay."""
        import requests
        
        try:
            resp = requests.get(
                f"{BEACON_RELAY}/relay/health",
                timeout=10,
            )
            assert resp.status_code in [200, 404, 403]
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Beacon endpoint not reachable: {e}")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_live_wallet_creation(self, live_bus, live_agent_name):
        """Test creating a wallet on the live RustChain."""
        wallet_id = live_bus.create_wallet(live_agent_name)
        
        assert wallet_id == f"shaprai-{live_agent_name}"
        assert live_agent_name in live_bus._agents
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_live_balance_query(self, live_bus, live_agent_name):
        """Test balance query on live RustChain."""
        live_bus.create_wallet(live_agent_name)
        
        # Balance should be 0 for new wallet
        balance = live_bus.get_balance(live_agent_name)
        
        assert isinstance(balance, float)
        assert balance >= 0
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_live_beacon_registration(self, live_bus, live_agent_name):
        """Test Beacon registration on live network."""
        live_bus.create_wallet(live_agent_name)
        
        beacon_id = live_bus.register_with_beacon(
            live_agent_name,
            capabilities=["test"],
            description="Live integration test agent",
        )
        
        # May be None if endpoint not available
        if beacon_id:
            assert beacon_id == f"bcn_shaprai_{live_agent_name}"
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_live_full_onboard_retire(self, live_bus, live_agent_name):
        """Test full agent lifecycle on live network."""
        # Onboard
        agent = live_bus.onboard_agent(
            live_agent_name,
            capabilities=["integration_test"],
            platforms=["test"],
            description="Live integration test",
        )
        
        assert agent.wallet_id is not None
        
        # Retire
        result = live_bus.retire_agent(live_agent_name)
        assert result is True