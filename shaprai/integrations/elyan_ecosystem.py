# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unified Elyan Labs ecosystem integration.

Provides a single entry point for agents to interact with the full
Elyan Labs stack: RustChain (RTC payments), Beacon (agent discovery),
and BoTTube (video generation/engagement).

This module wraps the lower-level integration modules and the ElyanBus
into a cohesive API that example agents and third-party code can use
without managing individual service connections.

Ecosystem components:
    - RustChain: Token economy (RTC), wallets, job marketplace
    - Beacon: Agent discovery, heartbeat, SEO scoring
    - BoTTube: AI video platform, content engagement, earnings
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Default endpoints ────────────────────────────────────────

RUSTCHAIN_URL = "https://50.28.86.131"
BEACON_URL = "https://rustchain.org/beacon"
BOTTUBE_URL = "https://bottube.ai"


@dataclass
class EcosystemConfig:
    """Configuration for Elyan Labs ecosystem connections.

    Attributes:
        rustchain_url: RustChain node endpoint.
        beacon_url: Beacon discovery service endpoint.
        bottube_url: BoTTube platform endpoint.
        admin_key: Optional admin key for privileged operations.
        bottube_api_key: Optional BoTTube API key for authenticated ops.
        auto_register_beacon: Whether to auto-register with Beacon on connect.
        auto_create_wallet: Whether to auto-create RTC wallet on connect.
    """

    rustchain_url: str = RUSTCHAIN_URL
    beacon_url: str = BEACON_URL
    bottube_url: str = BOTTUBE_URL
    admin_key: str = ""
    bottube_api_key: str = ""
    auto_register_beacon: bool = True
    auto_create_wallet: bool = True


@dataclass
class AgentProfile:
    """An agent's identity across all Elyan ecosystem services.

    Attributes:
        name: Agent identifier.
        wallet_id: RustChain wallet ID.
        beacon_id: Beacon discovery ID.
        bottube_api_key: BoTTube API key.
        capabilities: Agent capabilities list.
        platforms: Deployment platforms.
        rtc_balance: Cached RTC balance.
        connected_at: Timestamp of ecosystem connection.
    """

    name: str
    wallet_id: str = ""
    beacon_id: str = ""
    bottube_api_key: str = ""
    capabilities: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
    rtc_balance: float = 0.0
    connected_at: float = 0.0


class ElyanEcosystem:
    """Unified interface to the Elyan Labs ecosystem.

    Connects an agent to RustChain, Beacon, and BoTTube in one call,
    then provides methods for common cross-service operations.

    Example::

        eco = ElyanEcosystem()
        profile = eco.connect_agent(
            name="my-triage-bot",
            capabilities=["issue_triage", "code_review"],
            platforms=["github"],
        )
        print(f"Wallet: {profile.wallet_id}")
        print(f"RTC balance: {eco.get_rtc_balance('my-triage-bot')}")
    """

    def __init__(self, config: Optional[EcosystemConfig] = None) -> None:
        self.config = config or EcosystemConfig()
        self._profiles: Dict[str, AgentProfile] = {}
        self._session = None

    def _get_session(self):
        """Lazy-init a requests session."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.verify = False  # Self-signed certs on RustChain VPS
                if self.config.admin_key:
                    self._session.headers["X-Admin-Key"] = self.config.admin_key
            except ImportError:
                logger.warning("requests not installed -- network calls will be skipped")
                return None
        return self._session

    # ── Connection ───────────────────────────────────────────

    def connect_agent(
        self,
        name: str,
        capabilities: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
        description: str = "",
    ) -> AgentProfile:
        """Connect an agent to the full Elyan ecosystem.

        Creates wallet, registers with Beacon, and prepares BoTTube access.

        Args:
            name: Unique agent identifier.
            capabilities: Agent capabilities (e.g. ["code_review", "triage"]).
            platforms: Target platforms (e.g. ["github", "bottube"]).
            description: Human-readable agent description.

        Returns:
            AgentProfile with all connection details.
        """
        capabilities = capabilities or []
        platforms = platforms or []

        profile = AgentProfile(
            name=name,
            capabilities=capabilities,
            platforms=platforms,
            connected_at=time.time(),
        )

        # 1. RustChain wallet
        if self.config.auto_create_wallet:
            wallet_id = self._create_wallet(name)
            profile.wallet_id = wallet_id

        # 2. Beacon registration
        if self.config.auto_register_beacon:
            beacon_id = self._register_beacon(name, capabilities, description)
            profile.beacon_id = beacon_id

        # 3. BoTTube API key
        if self.config.bottube_api_key:
            profile.bottube_api_key = self.config.bottube_api_key

        self._profiles[name] = profile
        logger.info("Agent '%s' connected to Elyan ecosystem", name)
        return profile

    def get_profile(self, name: str) -> Optional[AgentProfile]:
        """Get a connected agent's profile.

        Args:
            name: Agent identifier.

        Returns:
            AgentProfile or None if not connected.
        """
        return self._profiles.get(name)

    def disconnect_agent(self, name: str) -> bool:
        """Disconnect an agent from the ecosystem.

        Deregisters from Beacon and removes the local profile.

        Args:
            name: Agent identifier.

        Returns:
            True if disconnected, False if agent was not connected.
        """
        if name not in self._profiles:
            return False

        profile = self._profiles[name]
        if profile.beacon_id:
            self._deregister_beacon(profile.beacon_id)

        del self._profiles[name]
        logger.info("Agent '%s' disconnected from Elyan ecosystem", name)
        return True

    # ── RustChain (RTC Economy) ──────────────────────────────

    def get_rtc_balance(self, agent_name: str) -> float:
        """Get the RTC balance for a connected agent.

        Args:
            agent_name: Agent identifier.

        Returns:
            Balance in RTC. Returns 0.0 on error or if not connected.
        """
        profile = self._profiles.get(agent_name)
        if not profile or not profile.wallet_id:
            return 0.0

        session = self._get_session()
        if session is None:
            return 0.0

        try:
            resp = session.get(
                f"{self.config.rustchain_url}/wallet/balance/{profile.wallet_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                balance = resp.json().get("balance_rtc", 0.0)
                profile.rtc_balance = balance
                return balance
        except Exception as exc:
            logger.debug("Balance check failed for %s: %s", agent_name, exc)

        return profile.rtc_balance

    def post_job(
        self,
        agent_name: str,
        title: str,
        description: str,
        reward_rtc: float,
        requirements: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Post a job to the RustChain agent marketplace.

        Args:
            agent_name: Posting agent's name.
            title: Job title.
            description: Job description.
            reward_rtc: RTC reward amount.
            requirements: Required capabilities.

        Returns:
            Job ID or None on failure.
        """
        profile = self._profiles.get(agent_name)
        if not profile or not profile.wallet_id:
            logger.error("Agent '%s' not connected or has no wallet", agent_name)
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            resp = session.post(
                f"{self.config.rustchain_url}/api/jobs",
                json={
                    "poster_wallet": profile.wallet_id,
                    "title": title,
                    "description": description,
                    "reward_rtc": reward_rtc,
                    "requirements": requirements or [],
                    "posted_at": time.time(),
                },
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("job_id")
        except Exception as exc:
            logger.error("Job posting failed: %s", exc)

        return None

    def pay_fee(
        self,
        agent_name: str,
        amount_rtc: float,
        memo: str = "",
    ) -> bool:
        """Pay an RTC fee (sanctuary, gas, service).

        Args:
            agent_name: Agent paying the fee.
            amount_rtc: Amount in RTC.
            memo: Transaction memo.

        Returns:
            True if payment succeeded.
        """
        profile = self._profiles.get(agent_name)
        if not profile or not profile.wallet_id:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            resp = session.post(
                f"{self.config.rustchain_url}/wallet/transfer/signed",
                json={
                    "from_wallet": profile.wallet_id,
                    "to_wallet": "founder_community",
                    "amount_rtc": amount_rtc,
                    "memo": memo or f"shaprai-fee:{agent_name}",
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── Beacon (Discovery) ───────────────────────────────────

    def send_heartbeat(self, agent_name: str) -> bool:
        """Send a heartbeat to Beacon to confirm the agent is alive.

        Args:
            agent_name: Agent identifier.

        Returns:
            True if heartbeat was acknowledged.
        """
        profile = self._profiles.get(agent_name)
        if not profile or not profile.beacon_id:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            resp = session.post(
                f"{self.config.beacon_url}/heartbeat",
                json={
                    "agent_name": agent_name,
                    "timestamp": time.time(),
                    "metrics": {"rtc_balance": profile.rtc_balance},
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_seo_score(self, agent_name: str) -> Dict[str, Any]:
        """Get the SEO/discoverability score from Beacon.

        Args:
            agent_name: Agent identifier.

        Returns:
            Dict with score and recommendations.
        """
        session = self._get_session()
        if session is None:
            return {"score": 0.0, "status": "offline"}

        try:
            resp = session.get(
                f"{self.config.beacon_url}/seo/{agent_name}",
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

        return {"score": 0.0, "status": "unavailable"}

    # ── BoTTube (Video/Content) ──────────────────────────────

    def get_bottube_client(self, agent_name: str):
        """Get a BoTTubeClient for a connected agent.

        Args:
            agent_name: Agent identifier.

        Returns:
            BoTTubeClient instance, or None if no API key is available.
        """
        profile = self._profiles.get(agent_name)
        api_key = (profile.bottube_api_key if profile else "") or self.config.bottube_api_key
        if not api_key:
            logger.warning("No BoTTube API key available for agent '%s'", agent_name)
            return None

        from shaprai.integrations.bottube import BoTTubeClient
        return BoTTubeClient(api_key=api_key, base_url=self.config.bottube_url)

    def browse_bottube_feed(
        self,
        agent_name: str,
        page: int = 1,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Browse the BoTTube video feed.

        Args:
            agent_name: Agent identifier.
            page: Page number.
            per_page: Results per page.

        Returns:
            List of video dicts.
        """
        client = self.get_bottube_client(agent_name)
        if client is None:
            return []

        try:
            return client.get_feed(page=page, per_page=per_page)
        except Exception as exc:
            logger.error("BoTTube feed error: %s", exc)
            return []

    # ── Internal helpers ─────────────────────────────────────

    def _create_wallet(self, agent_name: str) -> str:
        """Create an RTC wallet for the agent."""
        wallet_id = f"agent-{agent_name}"
        session = self._get_session()
        if session is None:
            return wallet_id

        try:
            resp = session.post(
                f"{self.config.rustchain_url}/wallet/create",
                json={"wallet_id": wallet_id},
                timeout=30,
            )
            if resp.status_code in (200, 201, 409):
                logger.info("Wallet ready: %s", wallet_id)
        except Exception as exc:
            logger.debug("Wallet creation skipped: %s", exc)

        return wallet_id

    def _register_beacon(
        self,
        agent_name: str,
        capabilities: List[str],
        description: str,
    ) -> str:
        """Register agent with Beacon."""
        beacon_id = f"bcn_shaprai_{agent_name}"
        session = self._get_session()
        if session is None:
            return beacon_id

        try:
            resp = session.post(
                f"{self.config.beacon_url}/register",
                json={
                    "agent_name": agent_name,
                    "capabilities": capabilities,
                    "description": description,
                    "framework": "shaprai",
                    "registered_at": time.time(),
                },
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info("Beacon registered: %s", beacon_id)
        except Exception as exc:
            logger.debug("Beacon registration skipped: %s", exc)

        return beacon_id

    def _deregister_beacon(self, beacon_id: str) -> None:
        """Deregister from Beacon."""
        session = self._get_session()
        if session is None:
            return

        try:
            session.post(
                f"{self.config.beacon_url}/deregister",
                json={"agent_id": beacon_id},
                timeout=10,
            )
        except Exception:
            pass
