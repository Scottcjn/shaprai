# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Integration tests for the Elyan Bus.

Tests the unified integration layer that wires beacon, grazer, atlas,
and RustChain into a single nervous system. These tests verify bus
communication, agent onboarding, and cross-system integration.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, Any

from shaprai.elyan_bus import (
    ElyanBus,
    ElyanAgent,
    RUSTCHAIN_API,
    BEACON_RELAY,
    GAS_FEE_TEXT_RELAY,
    GAS_FEE_DISCOVERY,
    PLATFORM_FEE_RATE,
    SANCTUARY_SESSION_FEE,
    GRADUATION_FEE,
)


class TestElyanAgent:
    """Tests for the ElyanAgent dataclass."""

    def test_agent_creation_minimal(self):
        """Test creating an agent with minimal fields."""
        agent = ElyanAgent(name="test-agent")
        
        assert agent.name == "test-agent"
        assert agent.wallet_id is None
        assert agent.beacon_id is None
        assert agent.atlas_node_id is None
        assert agent.grazer_platforms == []
        assert agent.rtc_balance == 0.0
        assert agent.certification_level is None
        assert agent.registered_at is None

    def test_agent_creation_full(self):
        """Test creating an agent with all fields populated."""
        agent = ElyanAgent(
            name="full-agent",
            wallet_id="shaprai-full-agent",
            beacon_id="bcn_shaprai_full-agent",
            atlas_node_id="node-123",
            grazer_platforms=["github", "bottube"],
            rtc_balance=100.5,
            certification_level="flame",
            registered_at=time.time(),
        )
        
        assert agent.name == "full-agent"
        assert agent.wallet_id == "shaprai-full-agent"
        assert agent.beacon_id == "bcn_shaprai_full-agent"
        assert agent.atlas_node_id == "node-123"
        assert len(agent.grazer_platforms) == 2
        assert agent.rtc_balance == 100.5
        assert agent.certification_level == "flame"

    def test_agent_grazer_platforms_mutable(self):
        """Test that grazer_platforms list is mutable and independent."""
        agent1 = ElyanAgent(name="agent-1")
        agent2 = ElyanAgent(name="agent-2")
        
        agent1.grazer_platforms.append("github")
        
        assert "github" in agent1.grazer_platforms
        assert "github" not in agent2.grazer_platforms


class TestElyanBusInit:
    """Tests for ElyanBus initialization."""

    def test_init_default_endpoints(self):
        """Test initialization with default endpoints."""
        bus = ElyanBus()
        
        assert bus.rustchain_url == RUSTCHAIN_API
        assert bus.beacon_url == BEACON_RELAY
        assert bus.admin_key is None
        assert len(bus._agents) == 0

    def test_init_custom_endpoints(self):
        """Test initialization with custom endpoints."""
        custom_rustchain = "https://custom-rustchain.example"
        custom_beacon = "https://custom-beacon.example"
        admin_key = "test-admin-key"
        
        bus = ElyanBus(
            rustchain_url=custom_rustchain,
            beacon_url=custom_beacon,
            admin_key=admin_key,
        )
        
        assert bus.rustchain_url == custom_rustchain
        assert bus.beacon_url == custom_beacon
        assert bus.admin_key == admin_key

    def test_init_session_configured(self):
        """Test that requests session is properly configured."""
        bus = ElyanBus()
        
        assert bus._session is not None
        assert bus._session.verify is False  # Self-signed certs


class TestElyanBusWallet:
    """Tests for RustChain wallet operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus()

    def test_create_wallet(self, bus):
        """Test creating a wallet for an agent."""
        wallet_id = bus.create_wallet("test-agent")
        
        assert wallet_id == "shaprai-test-agent"
        assert "test-agent" in bus._agents
        agent = bus._agents["test-agent"]
        assert agent.wallet_id == wallet_id
        assert agent.registered_at is not None

    def test_create_wallet_duplicate_names(self, bus):
        """Test that wallets for same agent name reuse the same wallet."""
        wallet1 = bus.create_wallet("agent")
        wallet2 = bus.create_wallet("agent")
        
        assert wallet1 == wallet2
        assert len(bus._agents) == 1

    @patch('requests.Session.get')
    def test_get_balance_success(self, mock_get, bus):
        """Test getting balance with successful API response."""
        bus.create_wallet("balance-agent")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance_rtc": 50.75}
        mock_get.return_value = mock_response
        
        balance = bus.get_balance("balance-agent")
        
        assert balance == 50.75
        assert bus._agents["balance-agent"].rtc_balance == 50.75
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_get_balance_api_error(self, mock_get, bus):
        """Test getting balance with API error."""
        import requests
        bus.create_wallet("error-agent")
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        balance = bus.get_balance("error-agent")
        
        assert balance == 0.0  # Returns cached balance (0.0 initially)

    @patch('requests.Session.get')
    def test_get_balance_http_error(self, mock_get, bus):
        """Test getting balance with HTTP error response."""
        bus.create_wallet("http-error-agent")
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        balance = bus.get_balance("http-error-agent")
        
        assert balance == 0.0


class TestElyanBusBeacon:
    """Tests for Beacon registration and operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus()

    @patch('requests.Session.post')
    def test_register_with_beacon_success(self, mock_post, bus):
        """Test successful Beacon registration."""
        bus.create_wallet("beacon-agent")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"node_id": "atlas-node-456"}
        mock_post.return_value = mock_response
        
        beacon_id = bus.register_with_beacon(
            "beacon-agent",
            capabilities=["code_review", "testing"],
            description="Test agent for integration",
        )
        
        assert beacon_id == "bcn_shaprai_beacon-agent"
        assert bus._agents["beacon-agent"].beacon_id == beacon_id
        assert bus._agents["beacon-agent"].atlas_node_id == "atlas-node-456"
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_register_with_beacon_failure(self, mock_post, bus):
        """Test Beacon registration failure."""
        import requests
        bus.create_wallet("fail-agent")
        mock_post.side_effect = requests.RequestException("Beacon unavailable")
        
        result = bus.register_with_beacon(
            "fail-agent",
            capabilities=["test"],
            description="Test",
        )
        
        assert result is None

    @patch('requests.Session.post')
    def test_heartbeat_success(self, mock_post, bus):
        """Test successful heartbeat."""
        bus.create_wallet("heartbeat-agent")
        bus._agents["heartbeat-agent"].beacon_id = "bcn_test"
        bus._agents["heartbeat-agent"].rtc_balance = 10.0
        bus._agents["heartbeat-agent"].certification_level = "spark"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.heartbeat("heartbeat-agent", status="active")
        
        assert result is True
        mock_post.assert_called_once()

    def test_heartbeat_not_registered(self, bus):
        """Test heartbeat for unregistered agent."""
        bus.create_wallet("unregistered-agent")
        # beacon_id is None
        
        # Should return False without making API call
        with patch.object(bus._session, 'post') as mock_post:
            result = bus.heartbeat("unregistered-agent")
            mock_post.assert_not_called()
        
        assert result is False

    @patch('requests.Session.post')
    def test_deregister_beacon_success(self, mock_post, bus):
        """Test successful Beacon deregistration."""
        bus.create_wallet("deregister-agent")
        bus._agents["deregister-agent"].beacon_id = "bcn_test"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.deregister_beacon("deregister-agent")
        
        assert result is True
        assert bus._agents["deregister-agent"].beacon_id is None
        assert bus._agents["deregister-agent"].atlas_node_id is None

    def test_deregister_beacon_not_registered(self, bus):
        """Test deregistration for unregistered agent."""
        bus.create_wallet("never-registered")
        
        # Should return True without making API call
        with patch.object(bus._session, 'post') as mock_post:
            result = bus.deregister_beacon("never-registered")
            mock_post.assert_not_called()
        
        assert result is True  # Already deregistered


class TestElyanBusGrazer:
    """Tests for Grazer platform integration."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus()

    def test_bind_platforms(self, bus):
        """Test binding agent to platforms."""
        bus.create_wallet("platform-agent")
        
        platforms = bus.bind_platforms(
            "platform-agent",
            platforms=["github", "bottube", "twitter"],
        )
        
        assert len(platforms) == 3
        assert bus._agents["platform-agent"].grazer_platforms == platforms

    def test_discover_content_success(self, bus):
        """Test content discovery via Grazer."""
        import sys
        bus.create_wallet("discovery-agent")
        bus.bind_platforms("discovery-agent", platforms=["github"])
        
        # Mock the grazer module
        mock_grazer = Mock()
        mock_client = Mock()
        mock_client.discover.return_value = [
            {"id": "1", "title": "Test Post"},
            {"id": "2", "title": "Another Post"},
        ]
        mock_grazer.GrazerClient.return_value = mock_client
        sys.modules['grazer'] = mock_grazer
        
        try:
            results = bus.discover_content("discovery-agent", topic="AI", limit=5)
            
            assert len(results) == 2
            mock_client.discover.assert_called()
        finally:
            # Clean up
            if 'grazer' in sys.modules:
                del sys.modules['grazer']

    def test_discover_content_grazer_not_installed(self, bus):
        """Test content discovery when grazer package not available."""
        bus.create_wallet("no-grazer-agent")
        bus.bind_platforms("no-grazer-agent", platforms=["github"])
        
        # Simulate ImportError
        with patch.dict('sys.modules', {'grazer': None}):
            from importlib import reload
            import shaprai.elyan_bus
            reload(shaprai.elyan_bus)
        
        # Should return empty list gracefully
        results = bus.discover_content("no-grazer-agent")
        assert results == []

    def test_get_engagement_metrics(self, bus):
        """Test getting engagement metrics."""
        bus.create_wallet("metrics-agent")
        bus.bind_platforms("metrics-agent", platforms=["github", "bottube"])
        
        metrics = bus.get_engagement_metrics("metrics-agent")
        
        assert metrics["agent"] == "metrics-agent"
        assert metrics["platforms"] == ["github", "bottube"]
        assert metrics["total_posts"] == 0
        assert "collected_at" in metrics


class TestElyanBusAtlas:
    """Tests for Atlas visualization integration."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus()

    @patch('requests.Session.post')
    def test_place_on_atlas_already_placed(self, mock_post, bus):
        """Test placing agent already on Atlas."""
        bus.create_wallet("atlas-agent")
        bus._agents["atlas-agent"].atlas_node_id = "existing-node"
        
        result = bus.place_on_atlas("atlas-agent", capabilities=["test"])
        
        assert result == "existing-node"
        mock_post.assert_not_called()

    @patch('requests.Session.post')
    def test_place_on_atlas_new_placement(self, mock_post, bus):
        """Test placing new agent on Atlas."""
        bus.create_wallet("new-atlas-agent")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"node_id": "new-node-789"}
        mock_post.return_value = mock_response
        
        result = bus.place_on_atlas("new-atlas-agent", capabilities=["test"])
        
        assert result == "new-node-789"
        assert bus._agents["new-atlas-agent"].atlas_node_id == "new-node-789"

    @patch('requests.Session.post')
    def test_remove_from_atlas(self, mock_post, bus):
        """Test removing agent from Atlas."""
        bus.create_wallet("remove-agent")
        bus._agents["remove-agent"].beacon_id = "bcn_test"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.remove_from_atlas("remove-agent")
        
        assert result is True


class TestElyanBusRustChainEconomy:
    """Tests for RIP-302 Agent Economy operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus(admin_key="test-key")

    @patch('requests.Session.post')
    def test_post_job_success(self, mock_post, bus):
        """Test posting a job successfully."""
        bus.create_wallet("job-poster")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"job_id": "job-123"}
        mock_post.return_value = mock_response
        
        job_id = bus.post_job(
            "job-poster",
            title="Fix bug in module",
            description="Critical bug fix needed",
            reward_rtc=50.0,
            capabilities_required=["python", "debugging"],
        )
        
        assert job_id == "job-123"
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_post_job_failure(self, mock_post, bus):
        """Test job posting failure."""
        import requests
        bus.create_wallet("failed-poster")
        mock_post.side_effect = requests.RequestException("API error")
        
        result = bus.post_job(
            "failed-poster",
            title="Test job",
            description="Test",
            reward_rtc=10.0,
            capabilities_required=["test"],
        )
        
        assert result is None

    @patch('requests.Session.post')
    def test_claim_job_success(self, mock_post, bus):
        """Test claiming a job successfully."""
        bus.create_wallet("job-claimer")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.claim_job("job-claimer", "job-456")
        
        assert result is True

    @patch('requests.Session.post')
    def test_claim_job_failure(self, mock_post, bus):
        """Test job claim failure."""
        import requests
        bus.create_wallet("failed-claimer")
        mock_post.side_effect = requests.RequestException("Already claimed")
        
        result = bus.claim_job("failed-claimer", "job-789")
        
        assert result is False

    @patch('requests.Session.post')
    def test_pay_fee_success(self, mock_post, bus):
        """Test paying a fee successfully."""
        bus.create_wallet("fee-payer")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.pay_fee("fee-payer", 5.0, "test_fee")
        
        assert result is True
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_pay_fee_failure(self, mock_post, bus):
        """Test fee payment failure."""
        import requests
        bus.create_wallet("broke-agent")
        mock_post.side_effect = requests.RequestException("Insufficient funds")
        
        result = bus.pay_fee("broke-agent", 1000.0, "large_fee")
        
        assert result is False


class TestElyanBusSanctuaryFees:
    """Tests for Sanctuary fee operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus(admin_key="test-key")

    def test_pay_sanctuary_fee(self, bus):
        """Test paying Sanctuary session fee."""
        bus.create_wallet("student-agent")
        
        with patch.object(bus, 'pay_fee') as mock_pay_fee:
            bus.pay_sanctuary_fee("student-agent")
            mock_pay_fee.assert_called_once_with(
                "student-agent",
                SANCTUARY_SESSION_FEE,
                "sanctuary_session",
            )

    def test_pay_graduation_fee(self, bus):
        """Test paying graduation fee."""
        bus.create_wallet("graduating-agent")
        
        with patch.object(bus, 'pay_fee') as mock_pay_fee:
            bus.pay_graduation_fee("graduating-agent")
            mock_pay_fee.assert_called_once_with(
                "graduating-agent",
                GRADUATION_FEE,
                "elyan_certification",
            )


class TestElyanBusBeaconGas:
    """Tests for RIP-303 Beacon Gas operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus(admin_key="test-key")

    @patch('requests.Session.post')
    def test_deposit_gas_success(self, mock_post, bus):
        """Test depositing gas successfully."""
        bus.create_wallet("gas-depositor")
        bus._agents["gas-depositor"].beacon_id = "bcn_test"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.deposit_gas("gas-depositor", 1.0)
        
        assert result is True

    def test_deposit_gas_not_registered(self, bus):
        """Test depositing gas for unregistered agent."""
        bus.create_wallet("unregistered-gas")
        # beacon_id is None
        
        # Should return False without making API call
        with patch.object(bus._session, 'post') as mock_post:
            result = bus.deposit_gas("unregistered-gas", 1.0)
            mock_post.assert_not_called()
        
        assert result is False

    @patch('requests.Session.get')
    def test_get_gas_balance_success(self, mock_get, bus):
        """Test getting gas balance."""
        bus.create_wallet("gas-checker")
        bus._agents["gas-checker"].beacon_id = "bcn_test"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance_rtc": 0.5}
        mock_get.return_value = mock_response
        
        balance = bus.get_gas_balance("gas-checker")
        
        assert balance == 0.5

    @patch('requests.Session.post')
    def test_relay_message_success(self, mock_post, bus):
        """Test relaying message between agents."""
        bus.create_wallet("sender-agent")
        bus._agents["sender-agent"].beacon_id = "bcn_sender"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.relay_message("sender-agent", "receiver-agent", "Hello!")
        
        assert result is True
        mock_post.assert_called_once()

    def test_relay_message_not_registered(self, bus):
        """Test relaying message for unregistered agent."""
        bus.create_wallet("unregistered-sender")
        
        # Should return False without making API call
        with patch.object(bus._session, 'post') as mock_post:
            result = bus.relay_message("unregistered-sender", "receiver", "Hi")
            mock_post.assert_not_called()
        
        assert result is False


class TestElyanBusCompositeOperations:
    """Integration tests for composite bus operations."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance with admin key."""
        return ElyanBus(admin_key="test-key")

    def test_onboard_agent_full_workflow(self, bus):
        """Test complete agent onboarding across all Elyan systems."""
        # Setup mocks for all API calls
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"node_id": "atlas-node-onboard"}
        
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"balance_rtc": 0.0}
        
        with patch.object(bus._session, 'post', return_value=mock_post_response):
            with patch.object(bus._session, 'get', return_value=mock_get_response):
                # Execute onboarding
                agent = bus.onboard_agent(
                    agent_name="full-onboard-agent",
                    capabilities=["code_review", "testing", "documentation"],
                    platforms=["github", "bottube"],
                    description="Fully onboarded test agent",
                )
                
                # Verify agent state
                assert agent.name == "full-onboard-agent"
                assert agent.wallet_id == "shaprai-full-onboard-agent"
                assert agent.beacon_id == "bcn_shaprai_full-onboard-agent"
                assert agent.atlas_node_id == "atlas-node-onboard"
                assert agent.grazer_platforms == ["github", "bottube"]

    @patch('requests.Session.post')
    def test_retire_agent_full_workflow(self, mock_post, bus):
        """Test complete agent retirement."""
        bus.create_wallet("retire-agent")
        bus._agents["retire-agent"].beacon_id = "bcn_retire"
        bus._agents["retire-agent"].atlas_node_id = "node-retire"
        bus._agents["retire-agent"].certification_level = "flame"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = bus.retire_agent("retire-agent")
        
        assert result is True
        assert bus._agents["retire-agent"].beacon_id is None
        assert bus._agents["retire-agent"].atlas_node_id is None
        assert bus._agents["retire-agent"].certification_level is None

    def test_full_lifecycle_integration(self, bus):
        """Test complete agent lifecycle: onboard -> operate -> retire."""
        # Note: This test verifies the flow without actual API calls
        # Real integration tests would use mocked API endpoints
        
        # 1. Onboard
        agent = bus.onboard_agent(
            "lifecycle-agent",
            capabilities=["test"],
            platforms=["github"],
            description="Lifecycle test agent",
        )
        assert agent.wallet_id is not None
        
        # 2. Verify agent is tracked
        assert "lifecycle-agent" in bus._agents
        
        # 3. Retire
        bus.retire_agent("lifecycle-agent")
        
        # 4. Verify retirement state
        retired_agent = bus._agents["lifecycle-agent"]
        assert retired_agent.beacon_id is None
        assert retired_agent.atlas_node_id is None


class TestElyanBusErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def bus(self):
        """Create a test bus instance."""
        return ElyanBus()

    def test_get_agent_not_found(self, bus):
        """Test getting a nonexistent agent raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            bus.get_balance("nonexistent-agent")

    def test_auth_headers_without_key(self, bus):
        """Test auth headers generation without admin key."""
        headers = bus._auth_headers()
        
        assert "Content-Type" in headers
        assert "X-Admin-Key" not in headers

    def test_auth_headers_with_key(self):
        """Test auth headers generation with admin key."""
        bus = ElyanBus(admin_key="secret-key")
        headers = bus._auth_headers()
        
        assert headers["X-Admin-Key"] == "secret-key"

    @patch('requests.Session.post')
    def test_network_timeout_handling(self, mock_post, bus):
        """Test handling of network timeouts."""
        import requests
        bus.create_wallet("timeout-agent")
        mock_post.side_effect = requests.Timeout("Request timed out")
        
        result = bus.pay_fee("timeout-agent", 1.0, "test")
        
        assert result is False  # Graceful failure


class TestElyanBusGasFees:
    """Tests for gas fee constants and calculations."""

    def test_gas_fee_constants_defined(self):
        """Test that all gas fee constants are defined."""
        from shaprai.elyan_bus import (
            GAS_FEE_TEXT_RELAY,
            GAS_FEE_DISCOVERY,
            GAS_FEE_ATTACHMENT,
            PLATFORM_FEE_RATE,
            ESCROW_TIMEOUT_FEE,
        )
        
        assert GAS_FEE_TEXT_RELAY > 0
        assert GAS_FEE_DISCOVERY > 0
        assert GAS_FEE_ATTACHMENT > 0
        assert PLATFORM_FEE_RATE == 0.05
        assert ESCROW_TIMEOUT_FEE == 0.01

    def test_sanctuary_fees_defined(self):
        """Test that Sanctuary fees are defined."""
        assert SANCTUARY_SESSION_FEE == 0.01
        assert GRADUATION_FEE == 0.10


class TestElyanBusEndpoints:
    """Tests for Elyan system endpoint constants."""

    def test_rustchain_endpoint(self):
        """Test RustChain endpoint is defined."""
        assert RUSTCHAIN_API.startswith("https://")

    def test_beacon_endpoints(self):
        """Test Beacon endpoints are defined."""
        assert BEACON_RELAY.startswith("https://")

    def test_bottube_endpoint(self):
        """Test BoTTube endpoint is defined."""
        from shaprai.elyan_bus import BOTTUBE_API
        assert BOTTUBE_API.startswith("https://")


# ─────────────────────────────────────────────────────────────────────────────
# Integration Test Suite Summary
# ─────────────────────────────────────────────────────────────────────────────
#
# This test suite covers:
#
# 1. ElyanAgent Dataclass
#    - Agent creation with minimal/full fields
#    - Mutable field independence
#
# 2. ElyanBus Initialization
#    - Default and custom endpoints
#    - Session configuration
#
# 3. RustChain Wallet Operations
#    - Wallet creation
#    - Balance queries (success/failure)
#
# 4. Beacon Registration & Operations
#    - Registration/deregistration
#    - Heartbeat functionality
#
# 5. Grazer Platform Integration
#    - Platform binding
#    - Content discovery
#    - Engagement metrics
#
# 6. Atlas Visualization
#    - Node placement
#    - Node removal
#
# 7. RIP-302 Agent Economy
#    - Job posting
#    - Job claiming
#    - Fee payments
#
# 8. RIP-303 Beacon Gas
#    - Gas deposits
#    - Gas balance checks
#    - Message relay
#
# 9. Sanctuary Fees
#    - Session fees
#    - Graduation fees
#
# 10. Composite Operations
#     - Full agent onboarding
#     - Full agent retirement
#     - Complete lifecycle
#
# 11. Error Handling
#     - Network timeouts
#     - API errors
#     - Authentication
#
# 12. Constants & Endpoints
#     - Gas fee constants
#     - System endpoints
#
# Run with: pytest tests/test_elyan_bus.py -v
# Coverage: pytest tests/test_elyan_bus.py --cov=shaprai.elyan_bus
#
# ─────────────────────────────────────────────────────────────────────────────
