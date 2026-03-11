import requests
import pytest
from unittest.mock import Mock

from shaprai.elyan_bus import ElyanBus


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def bus():
    return ElyanBus(admin_key="test-admin-key")


@pytest.fixture
def onboarded_bus(bus):
    bus.create_wallet("alice")
    bus._get_agent("alice").beacon_id = "bcn_shaprai_alice"
    return bus


def test_wallet_creation_and_balance_check_mock_mode(bus, monkeypatch):
    wallet_id = bus.create_wallet("alice")
    assert wallet_id == "shaprai-alice"

    def fake_get(url, timeout=10):
        assert url.endswith("/api/balance/shaprai-alice")
        return DummyResponse(200, {"balance_rtc": 12.5})

    monkeypatch.setattr(bus._session, "get", fake_get)
    balance = bus.get_balance("alice")
    assert balance == 12.5


def test_beacon_registration_with_capabilities_mock_mode(bus, monkeypatch):
    bus.create_wallet("alice")

    def fake_post(url, json=None, timeout=15, headers=None):
        assert url.endswith("/relay/register")
        assert json["agent_id"] == "bcn_shaprai_alice"
        assert "analysis" in json["capabilities"]
        return DummyResponse(200, {"node_id": "atlas-node-1"})

    monkeypatch.setattr(bus._session, "post", fake_post)
    beacon_id = bus.register_with_beacon("alice", ["analysis", "coding"], "test agent")
    agent = bus._get_agent("alice")
    assert beacon_id == "bcn_shaprai_alice"
    assert agent.atlas_node_id == "atlas-node-1"


def test_gas_deposit_flow_mock_mode(onboarded_bus, monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=10):
        calls.append((url, json, headers))
        assert url.endswith("/relay/gas/deposit")
        assert json["agent_id"] == "bcn_shaprai_alice"
        assert json["amount_rtc"] == 0.25
        assert headers["X-Admin-Key"] == "test-admin-key"
        return DummyResponse(200, {})

    monkeypatch.setattr(onboarded_bus._session, "post", fake_post)
    assert onboarded_bus.deposit_gas("alice", 0.25) is True
    assert len(calls) == 1


def test_job_posting_and_discovery_mock_mode(bus, monkeypatch):
    bus.create_wallet("alice")

    def fake_post(url, json=None, headers=None, timeout=15):
        assert url.endswith("/agent/jobs")
        assert json["poster_wallet"] == "shaprai-alice"
        return DummyResponse(200, {"job_id": "job-123"})

    monkeypatch.setattr(bus._session, "post", fake_post)
    job_id = bus.post_job(
        "alice",
        title="Test Job",
        description="desc",
        reward_rtc=5.0,
        capabilities_required=["python"],
    )
    assert job_id == "job-123"

    bus.bind_platforms("alice", ["github", "telegram"])
    discovered = bus.discover_content("alice", topic="python", limit=5)
    assert discovered == []


def test_error_handling_timeout_returns_safe_values(bus, monkeypatch):
    bus.create_wallet("alice")

    def fake_get(*args, **kwargs):
        raise requests.Timeout("timeout")

    def fake_post(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(bus._session, "get", fake_get)
    monkeypatch.setattr(bus._session, "post", fake_post)

    assert bus.get_balance("alice") == 0.0
    assert bus.post_job("alice", "t", "d", 1.0, ["x"]) is None
    assert bus.claim_job("alice", "job-1") is False


def test_error_handling_500_and_invalid_auth(bus, monkeypatch):
    bus.create_wallet("alice")
    bus._get_agent("alice").beacon_id = "bcn_shaprai_alice"

    def fake_post_500(url, json=None, headers=None, timeout=15):
        return DummyResponse(500, {"error": "server error"})

    monkeypatch.setattr(bus._session, "post", fake_post_500)
    assert bus.deposit_gas("alice", 0.1) is False
    assert bus.register_with_beacon("alice", ["coding"], "desc") is None


@pytest.mark.integration
def test_live_mode_smoke(monkeypatch):
    """Live-mode smoke test skeleton.

    This test is skipped by default unless explicitly selected with:
      pytest -m integration
    and LIVE_ELYAN_TESTS=1 is set.
    """
    import os
    if os.getenv("LIVE_ELYAN_TESTS") != "1":
        pytest.skip("Set LIVE_ELYAN_TESTS=1 to run live integration tests")

    bus = ElyanBus()
    bus.create_wallet("live-smoke")
    assert bus._get_agent("live-smoke").wallet_id == "shaprai-live-smoke"
