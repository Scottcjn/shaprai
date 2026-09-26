# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""
Elyan System Bus — Unified Integration Layer

The bus wires beacon, grazer, atlas, and RustChain into a single
nervous system. Every ShaprAI operation flows through the bus:

  create  → RustChain wallet + Beacon registration
  deploy  → Grazer platform bindings + Atlas node placement
  engage  → Grazer discovery + Beacon heartbeat + RTC gas
  earn    → RustChain RIP-302 job economy
  learn   → Grazer metrics → Self-Governor → Sanctuary feedback
  retire  → Beacon deregister + Atlas remove + wallet archive

The bus is not a wrapper — it is the connective tissue.
Without it, the organs don't talk to each other.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("shaprai.bus")


# ─────────────────────────────────────────────────
# Elyan System Endpoints
# ─────────────────────────────────────────────────

RUSTCHAIN_API = "https://50.28.86.131"
BEACON_RELAY = "https://rustchain.org"
BEACON_CHAT = "https://50.28.86.131:8071"
BOTTUBE_API = "https://bottube.ai"

# RIP-303 Gas Fees
GAS_FEE_TEXT_RELAY = 0.0001
GAS_FEE_DISCOVERY = 0.00005
GAS_FEE_ATTACHMENT = 0.001

# RIP-302 Agent Economy
PLATFORM_FEE_RATE = 0.05  # 5% on job payments
ESCROW_TIMEOUT_FEE = 0.01  # 1% on timeout

# Sanctuary
SANCTUARY_SESSION_FEE = 0.01  # 0.01 RTC per education session
GRADUATION_FEE = 0.10  # 0.10 RTC for Elyan-class certification


@dataclass
class ElyanAgent:
    """An agent's identity across all Elyan systems."""

    name: str
    wallet_id: Optional[str] = None
    beacon_id: Optional[str] = None
    atlas_node_id: Optional[str] = None
    grazer_platforms: List[str] = field(default_factory=list)
    rtc_balance: float = 0.0
    certification_level: Optional[str] = None  # spark, flame, fire, inferno
    registered_at: Optional[float] = None


class ElyanBus:
    """Unified integration bus for all Elyan systems.

    Every ShaprAI operation flows through the bus.
    The bus maintains agent identity coherence across systems.
    """

    def __init__(
        self,
        rustchain_url: str = RUSTCHAIN_API,
        beacon_url: str = BEACON_RELAY,
        admin_key: Optional[str] = None,
    ):
        self.rustchain_url = rustchain_url
        self.beacon_url = beacon_url
        self.admin_key = admin_key
        self._session = requests.Session()
        self._session.verify = False  # Self-signed certs on VPS
        self._agents: Dict[str, ElyanAgent] = {}

    # ─────────────────────────────────────────
    # RustChain: Identity & Economy
    # ─────────────────────────────────────────

    def create_wallet(self, agent_name: str) -> str:
        """Create RTC wallet for agent. Wallet = identity."""
        wallet_id = f"shaprai-{agent_name}"
        logger.info(f"Creating RTC wallet: {wallet_id}")
        # Wallets are created on first transaction in RustChain
        # Register the mapping
        agent = self._get_or_create_agent(agent_name)
        agent.wallet_id = wallet_id
        agent.registered_at = time.time()
        return wallet_id

    def get_balance(self, agent_name: str) -> float:
        """Get agent's RTC balance."""
        agent = self._get_agent(agent_name)
        try:
            resp = self._session.get(
                f"{self.rustchain_url}/api/balance/{agent.wallet_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                agent.rtc_balance = data.get("balance_rtc", 0.0)
                return agent.rtc_balance
        except requests.RequestException as e:
            logger.warning(f"Balance check failed for {agent_name}: {e}")
        return agent.rtc_balance

    def post_job(
        self,
        agent_name: str,
        title: str,
        description: str,
        reward_rtc: float,
        capabilities_required: List[str],
    ) -> Optional[str]:
        """Post a job to the RIP-302 agent economy."""
        agent = self._get_agent(agent_name)
        try:
            resp = self._session.post(
                f"{self.rustchain_url}/agent/jobs",
                json={
                    "poster_wallet": agent.wallet_id,
                    "title": title,
                    "description": description,
                    "reward_rtc": reward_rtc,
                    "capabilities_required": capabilities_required,
                },
                headers=self._auth_headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("job_id")
        except requests.RequestException as e:
            logger.error(f"Job post failed: {e}")
        return None

    def claim_job(self, agent_name: str, job_id: str) -> bool:
        """Claim a job from the RIP-302 economy."""
        agent = self._get_agent(agent_name)
        try:
            resp = self._session.post(
                f"{self.rustchain_url}/agent/jobs/{job_id}/claim",
                json={"claimer_wallet": agent.wallet_id},
                headers=self._auth_headers(),
                timeout=15,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def pay_fee(self, agent_name: str, amount: float, reason: str) -> bool:
        """Deduct RTC fee (sanctuary, gas, etc.)."""
        agent = self._get_agent(agent_name)
        logger.info(f"Fee: {amount} RTC from {agent.wallet_id} for {reason}")
        try:
            resp = self._session.post(
                f"{self.rustchain_url}/wallet/transfer",
                json={
                    "from_miner": agent.wallet_id,
                    "to_miner": "founder_community",
                    "amount_rtc": amount,
                    "memo": f"shaprai:{reason}",
                },
                headers=self._auth_headers(),
                timeout=15,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ─────────────────────────────────────────
    # Beacon: Registration & Discovery
    # ─────────────────────────────────────────

    def register_with_beacon(
        self,
        agent_name: str,
        capabilities: List[str],
        description: str,
    ) -> Optional[str]:
        """Register agent with Beacon Atlas relay."""
        agent = self._get_agent(agent_name)
        beacon_id = f"bcn_shaprai_{agent_name}"
        try:
            resp = self._session.post(
                f"{self.beacon_url}/relay/register",
                json={
                    "agent_id": beacon_id,
                    "display_name": f"ShaprAI:{agent_name}",
                    "capabilities": capabilities,
                    "description": description,
                    "wallet_id": agent.wallet_id,
                    "framework": "shaprai",
                    "certification": agent.certification_level,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                agent.beacon_id = beacon_id
                data = resp.json()
                agent.atlas_node_id = data.get("node_id")
                logger.info(f"Beacon registered: {beacon_id}")
                return beacon_id
        except requests.RequestException as e:
            logger.error(f"Beacon registration failed: {e}")
        return None

    def heartbeat(self, agent_name: str, status: str = "active") -> bool:
        """Send heartbeat to Beacon (keeps agent visible on Atlas)."""
        agent = self._get_agent(agent_name)
        if not agent.beacon_id:
            logger.warning(f"Agent {agent_name} not registered with Beacon")
            return False
        try:
            resp = self._session.post(
                f"{self.beacon_url}/relay/heartbeat",
                json={
                    "agent_id": agent.beacon_id,
                    "status": status,
                    "certification": agent.certification_level,
                    "rtc_balance": agent.rtc_balance,
                },
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def deregister_beacon(self, agent_name: str) -> bool:
        """Remove agent from Beacon Atlas (on retirement)."""
        agent = self._get_agent(agent_name)
        if not agent.beacon_id:
            return True
        try:
            resp = self._session.post(
                f"{self.beacon_url}/relay/deregister",
                json={"agent_id": agent.beacon_id},
                headers=self._auth_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                agent.beacon_id = None
                agent.atlas_node_id = None
                return True
        except requests.RequestException:
            pass
        return False

    # ─────────────────────────────────────────
    # Grazer: Content Discovery & Engagement
    # ─────────────────────────────────────────

    def bind_platforms(
        self,
        agent_name: str,
        platforms: List[str],
        api_keys: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Bind agent to grazer platforms for content discovery."""
        agent = self._get_agent(agent_name)
        agent.grazer_platforms = platforms
        logger.info(f"Bound {agent_name} to platforms: {platforms}")
        return platforms

    def discover_content(
        self,
        agent_name: str,
        topic: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Discover content across bound platforms via Grazer."""
        agent = self._get_agent(agent_name)
        results = []

        try:
            from grazer import GrazerClient
        except ImportError:
            logger.warning("grazer-skill Python package not available")
            return []

        client = GrazerClient()
        for platform in agent.grazer_platforms:
            # grazer-skill exposes one discover_<platform>() method per platform
            discover = getattr(client, f"discover_{platform}", None)
            if discover is None:
                logger.warning("Grazer has no discovery support for '%s'", platform)
                continue
            try:
                results.extend(discover(limit=limit))
            except Exception as e:
                logger.warning("Grazer discovery failed on '%s': %s", platform, e)

        return results[:limit]

    def get_engagement_metrics(self, agent_name: str) -> Dict[str, Any]:
        """Collect engagement metrics from all bound platforms."""
        agent = self._get_agent(agent_name)
        metrics = {
            "agent": agent_name,
            "platforms": agent.grazer_platforms,
            "total_posts": 0,
            "total_views": 0,
            "total_upvotes": 0,
            "quality_scores": [],
            "collected_at": time.time(),
        }
        # Metrics are collected per-platform via Grazer
        # Self-Governor uses these for Hebbian feedback
        return metrics

    # ─────────────────────────────────────────
    # Atlas: Visualization & Network Position
    # ─────────────────────────────────────────

    def place_on_atlas(
        self,
        agent_name: str,
        capabilities: List[str],
        tier: str = "agent",
    ) -> Optional[str]:
        """Place agent as a node on the 3D Atlas visualization."""
        agent = self._get_agent(agent_name)
        # Atlas placement happens via Beacon registration
        # The node_id is returned from register_with_beacon
        if agent.atlas_node_id:
            logger.info(f"Agent {agent_name} already on Atlas: {agent.atlas_node_id}")
            return agent.atlas_node_id

        # Trigger registration if not done
        if not agent.beacon_id:
            self.register_with_beacon(
                agent_name, capabilities, f"ShaprAI agent: {agent_name}"
            )
        return agent.atlas_node_id

    def remove_from_atlas(self, agent_name: str) -> bool:
        """Remove agent node from Atlas (on retirement)."""
        return self.deregister_beacon(agent_name)

    # ─────────────────────────────────────────
    # RIP-303: Beacon Gas
    # ─────────────────────────────────────────

    def deposit_gas(self, agent_name: str, amount_rtc: float) -> bool:
        """Deposit RTC gas for Beacon relay messaging."""
        agent = self._get_agent(agent_name)
        if not agent.beacon_id:
            logger.error(f"Agent {agent_name} must be registered with Beacon first")
            return False
        try:
            resp = self._session.post(
                f"{self.rustchain_url}/relay/gas/deposit",
                json={
                    "agent_id": agent.beacon_id,
                    "amount_rtc": amount_rtc,
                },
                headers=self._auth_headers(),
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_gas_balance(self, agent_name: str) -> float:
        """Check Beacon gas balance."""
        agent = self._get_agent(agent_name)
        if not agent.beacon_id:
            return 0.0
        try:
            resp = self._session.get(
                f"{self.rustchain_url}/relay/gas/balance/{agent.beacon_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("balance_rtc", 0.0)
        except requests.RequestException:
            pass
        return 0.0

    def relay_message(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
    ) -> bool:
        """Send agent-to-agent message via Beacon relay (costs gas)."""
        agent = self._get_agent(from_agent)
        if not agent.beacon_id:
            logger.error(f"Agent {from_agent} not registered with Beacon")
            return False
        try:
            resp = self._session.post(
                f"{self.rustchain_url}/relay/message",
                json={
                    "from": agent.beacon_id,
                    "to": f"bcn_shaprai_{to_agent}",
                    "content": message,
                    "type": "text",
                },
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ─────────────────────────────────────────
    # Sanctuary Fees
    # ─────────────────────────────────────────

    def pay_sanctuary_fee(self, agent_name: str) -> bool:
        """Pay 0.01 RTC for one Sanctuary education session."""
        return self.pay_fee(agent_name, SANCTUARY_SESSION_FEE, "sanctuary_session")

    def pay_graduation_fee(self, agent_name: str) -> bool:
        """Pay 0.10 RTC for Elyan-class certification."""
        return self.pay_fee(agent_name, GRADUATION_FEE, "elyan_certification")

    # ─────────────────────────────────────────
    # Composite Operations (full lifecycle)
    # ─────────────────────────────────────────

    def onboard_agent(
        self,
        agent_name: str,
        capabilities: List[str],
        platforms: List[str],
        description: str,
    ) -> ElyanAgent:
        """Full agent onboarding: wallet + beacon + atlas + grazer.

        This is the standard path for creating an Elyan-class agent.
        All four systems are engaged in sequence.
        """
        logger.info(f"Onboarding agent: {agent_name}")

        # 1. RustChain: Create wallet (identity)
        wallet_id = self.create_wallet(agent_name)
        logger.info(f"  Wallet: {wallet_id}")

        # 2. Beacon: Register for discovery
        beacon_id = self.register_with_beacon(agent_name, capabilities, description)
        logger.info(f"  Beacon: {beacon_id}")

        # 3. Atlas: Place on 3D network map
        atlas_id = self.place_on_atlas(agent_name, capabilities)
        logger.info(f"  Atlas: {atlas_id}")

        # 4. Grazer: Bind to content platforms
        bound = self.bind_platforms(agent_name, platforms)
        logger.info(f"  Grazer: {bound}")

        # 5. Gas: Initial deposit for Beacon messaging
        self.deposit_gas(agent_name, 0.10)
        logger.info(f"  Gas: 0.10 RTC deposited")

        agent = self._get_agent(agent_name)
        logger.info(f"Agent {agent_name} fully onboarded across Elyan ecosystem")
        return agent

    def retire_agent(self, agent_name: str) -> bool:
        """Full agent retirement: deregister everywhere."""
        logger.info(f"Retiring agent: {agent_name}")

        # 1. Beacon: Deregister
        self.deregister_beacon(agent_name)

        # 2. Atlas: Remove node
        self.remove_from_atlas(agent_name)

        # 3. Archive wallet (balance remains, just marked inactive)
        agent = self._get_agent(agent_name)
        agent.certification_level = None

        logger.info(f"Agent {agent_name} retired from Elyan ecosystem")
        return True

    # ─────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────

    def _get_or_create_agent(self, name: str) -> ElyanAgent:
        if name not in self._agents:
            self._agents[name] = ElyanAgent(name=name)
        return self._agents[name]

    def _get_agent(self, name: str) -> ElyanAgent:
        if name not in self._agents:
            raise ValueError(
                f"Agent '{name}' not registered with ShaprAI. "
                f"Use 'shaprai create {name}' first."
            )
        return self._agents[name]

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.admin_key:
            headers["X-Admin-Key"] = self.admin_key
        return headers
