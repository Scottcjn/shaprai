import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_agents_dir(tmp_path):
    """Fixture for a temporary agents directory."""
    d = tmp_path / "agents"
    d.mkdir()
    return d


@pytest.fixture
def mock_template():
    """Fixture for a basic AgentTemplate."""
    from shaprai.core.template_engine import AgentTemplate

    return AgentTemplate(
        name="test-template",
        model={"base": "test-model"},
        personality={"tone": "professional"},
        capabilities=["code_review"],
        platforms=["github"],
    )
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""
Pytest configuration and fixtures for Elyan Bus integration tests.

This module provides fixtures for two testing modes:
- Mock mode (default): Uses responses library to mock HTTP requests
- Live mode: Tests against real Elyan network endpoints

Running Tests
=============

Mock mode (default, for CI):
    pytest tests/integration/test_elyan_bus.py

Live mode (requires network access):
    pytest tests/integration/test_elyan_bus.py -m integration

Run all tests including live:
    pytest tests/integration/test_elyan_bus.py -m "integration or not integration"
"""

import os
import pytest
import responses
from unittest.mock import MagicMock, patch

from shaprai.elyan_bus import (
    ElyanBus,
    ElyanAgent,
    RUSTCHAIN_API,
    BEACON_RELAY,
    GAS_FEE_TEXT_RELAY,
    SANCTUARY_SESSION_FEE,
    GRADUATION_FEE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pytest Configuration
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires network)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests by default unless explicitly requested."""
    # Check if integration tests are explicitly requested via -m flag
    marker_expr = config.getoption("-m", default="")
    
    # Only skip tests that are explicitly marked with @pytest.mark.integration
    # if integration is not in the marker expression
    if "integration" not in marker_expr:
        skip_integration = pytest.mark.skip(
            reason="integration test - use -m integration to run"
        )
        for item in items:
            # Only skip if the test has the integration marker
            if item.get_closest_marker("integration") is not None:
                item.add_marker(skip_integration)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Mode Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_rustchain():
    """
    Mock RustChain API responses.
    
    Yields a responses mock context for RustChain endpoints.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def mock_bus():
    """
    ElyanBus instance for testing.
    
    This fixture provides a clean bus instance. Individual tests
    should use mock_rustchain fixture to mock network calls.
    """
    bus = ElyanBus()
    return bus


@pytest.fixture
def mock_agent(mock_bus):
    """
    Create a pre-registered mock agent for testing.
    
    Returns an ElyanAgent with wallet and beacon IDs already set.
    """
    agent_name = "test_agent"
    agent = mock_bus._get_or_create_agent(agent_name)
    agent.wallet_id = f"shaprai-{agent_name}"
    agent.beacon_id = f"bcn_shaprai_{agent_name}"
    agent.atlas_node_id = "node_12345"
    agent.grazer_platforms = ["twitter", "discord"]
    agent.rtc_balance = 1.0
    return agent_name, agent


# ─────────────────────────────────────────────────────────────────────────────
# Live Mode Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def live_bus():
    """
    ElyanBus instance for live integration testing.
    
    WARNING: This fixture makes real network calls to Elyan endpoints.
    Only use with -m integration marker.
    """
    admin_key = os.environ.get("ELYAN_ADMIN_KEY")
    bus = ElyanBus(admin_key=admin_key)
    return bus


@pytest.fixture
def live_agent_name():
    """Generate a unique agent name for live testing."""
    import time
    return f"test_agent_{int(time.time())}"


# ─────────────────────────────────────────────────────────────────────────────
# Utility Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def caplog_setup(caplog):
    """Set up logging capture for tests."""
    import logging
    caplog.set_level(logging.DEBUG, logger="shaprai.bus")
    return caplog
