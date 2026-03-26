# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the Elyan Labs ecosystem integration module."""

import pytest

from shaprai.integrations.elyan_ecosystem import (
    AgentProfile,
    EcosystemConfig,
    ElyanEcosystem,
)


@pytest.fixture
def offline_ecosystem():
    """Ecosystem with auto-registration disabled (no network calls)."""
    config = EcosystemConfig(
        auto_register_beacon=False,
        auto_create_wallet=False,
    )
    return ElyanEcosystem(config=config)


@pytest.fixture
def full_ecosystem():
    """Ecosystem with all features enabled (still no real network)."""
    config = EcosystemConfig(
        rustchain_url="https://localhost:9999",
        beacon_url="https://localhost:9998",
        bottube_url="https://localhost:9997",
        bottube_api_key="test-key-123",
    )
    return ElyanEcosystem(config=config)


class TestEcosystemConfig:
    def test_default_config(self):
        config = EcosystemConfig()
        assert "50.28.86.131" in config.rustchain_url
        assert "rustchain.org" in config.beacon_url
        assert "bottube.ai" in config.bottube_url
        assert config.auto_register_beacon is True
        assert config.auto_create_wallet is True

    def test_custom_config(self):
        config = EcosystemConfig(
            rustchain_url="https://custom.node",
            admin_key="secret123",
        )
        assert config.rustchain_url == "https://custom.node"
        assert config.admin_key == "secret123"


class TestAgentProfile:
    def test_default_profile(self):
        p = AgentProfile(name="test-agent")
        assert p.name == "test-agent"
        assert p.wallet_id == ""
        assert p.beacon_id == ""
        assert p.capabilities == []
        assert p.rtc_balance == 0.0

    def test_profile_with_fields(self):
        p = AgentProfile(
            name="my-bot",
            wallet_id="agent-my-bot",
            capabilities=["code_review"],
            platforms=["github"],
        )
        assert p.wallet_id == "agent-my-bot"
        assert "code_review" in p.capabilities


class TestConnectAgent:
    def test_connect_basic(self, offline_ecosystem):
        profile = offline_ecosystem.connect_agent(
            name="test-bot",
            capabilities=["triage"],
            platforms=["github"],
        )
        assert profile.name == "test-bot"
        assert "triage" in profile.capabilities
        assert "github" in profile.platforms
        assert profile.connected_at > 0

    def test_connect_creates_wallet_id_when_disabled(self, offline_ecosystem):
        """When auto_create_wallet is False, wallet_id should be empty."""
        profile = offline_ecosystem.connect_agent(name="no-wallet")
        assert profile.wallet_id == ""

    def test_connect_creates_wallet_id_when_enabled(self):
        """When auto_create_wallet is True, wallet_id should be set."""
        config = EcosystemConfig(
            auto_create_wallet=True,
            auto_register_beacon=False,
            # Use unreachable URL so network calls fail silently
            rustchain_url="https://localhost:1",
        )
        eco = ElyanEcosystem(config=config)
        profile = eco.connect_agent(name="wallet-bot")
        assert profile.wallet_id == "agent-wallet-bot"

    def test_connect_sets_beacon_id_when_enabled(self):
        """When auto_register_beacon is True, beacon_id should be set."""
        config = EcosystemConfig(
            auto_create_wallet=False,
            auto_register_beacon=True,
            beacon_url="https://localhost:1",
        )
        eco = ElyanEcosystem(config=config)
        profile = eco.connect_agent(name="beacon-bot")
        assert profile.beacon_id == "bcn_shaprai_beacon-bot"

    def test_connect_multiple_agents(self, offline_ecosystem):
        p1 = offline_ecosystem.connect_agent(name="agent-a")
        p2 = offline_ecosystem.connect_agent(name="agent-b")
        assert p1.name != p2.name
        assert offline_ecosystem.get_profile("agent-a") is p1
        assert offline_ecosystem.get_profile("agent-b") is p2


class TestGetProfile:
    def test_get_existing_profile(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="exists")
        profile = offline_ecosystem.get_profile("exists")
        assert profile is not None
        assert profile.name == "exists"

    def test_get_missing_profile(self, offline_ecosystem):
        assert offline_ecosystem.get_profile("ghost") is None


class TestDisconnectAgent:
    def test_disconnect_connected(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="to-disconnect")
        assert offline_ecosystem.disconnect_agent("to-disconnect") is True
        assert offline_ecosystem.get_profile("to-disconnect") is None

    def test_disconnect_not_connected(self, offline_ecosystem):
        assert offline_ecosystem.disconnect_agent("never-connected") is False


class TestRTCBalance:
    def test_balance_no_profile(self, offline_ecosystem):
        assert offline_ecosystem.get_rtc_balance("nobody") == 0.0

    def test_balance_no_wallet(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="no-wallet")
        assert offline_ecosystem.get_rtc_balance("no-wallet") == 0.0


class TestPayFee:
    def test_pay_fee_no_profile(self, offline_ecosystem):
        assert offline_ecosystem.pay_fee("nobody", 1.0) is False

    def test_pay_fee_no_wallet(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="broke")
        assert offline_ecosystem.pay_fee("broke", 0.01) is False


class TestHeartbeat:
    def test_heartbeat_no_beacon(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="no-beacon")
        assert offline_ecosystem.send_heartbeat("no-beacon") is False

    def test_heartbeat_not_connected(self, offline_ecosystem):
        assert offline_ecosystem.send_heartbeat("ghost") is False


class TestBoTTube:
    def test_get_client_with_key(self, full_ecosystem):
        full_ecosystem.connect_agent(name="vid-bot")
        client = full_ecosystem.get_bottube_client("vid-bot")
        assert client is not None
        assert client.api_key == "test-key-123"

    def test_get_client_no_key(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="no-key")
        client = offline_ecosystem.get_bottube_client("no-key")
        assert client is None

    def test_browse_feed_no_client(self, offline_ecosystem):
        offline_ecosystem.connect_agent(name="no-feed")
        result = offline_ecosystem.browse_bottube_feed("no-feed")
        assert result == []
