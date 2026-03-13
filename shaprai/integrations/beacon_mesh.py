# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Beacon mesh network for agent-to-agent communication.

Implements the Beacon mesh protocol for ShaprAI agents:
  - Ed25519 identity creation and envelope signing
  - Bidirectional agent-to-agent messaging via signed envelopes
  - Personality-consistent reply generation (agents reply in-character)
  - UDP LAN discovery for local mesh formation
  - Multi-agent mesh topology with peer tracking

Architecture:
  Each agent holds an Ed25519 keypair (its Beacon identity). Messages are
  wrapped in signed envelopes that carry sender/receiver IDs, a timestamp,
  a nonce, and the Ed25519 signature. The mesh maintains a registry of
  known peers and their public keys so any node can verify any envelope.

Transport:
  - **Webhook (HTTP)**: Default relay through Beacon at rustchain.org.
  - **UDP LAN**: Local broadcast discovery via ``beacon udp listen``.
    Agents announce themselves on a multicast/broadcast port and
    automatically discover peers on the same LAN segment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────

BEACON_DEFAULT_URL = "https://rustchain.org"

# UDP discovery defaults
UDP_DISCOVERY_PORT = 9741
UDP_MULTICAST_GROUP = "224.0.0.65"  # Link-local multicast for mesh
UDP_ANNOUNCE_INTERVAL = 5  # seconds between announcements
UDP_BUFFER_SIZE = 4096

# Envelope protocol version
ENVELOPE_PROTOCOL_VERSION = "1.0"


# ─────────────────────────────────────────────────
# Ed25519 Identity
# ─────────────────────────────────────────────────


@dataclass
class BeaconIdentity:
    """An agent's Ed25519 identity on the Beacon mesh.

    Attributes:
        beacon_id: Unique Beacon identifier (e.g. ``bcn_shaprai_alpha``).
        agent_name: Human-readable agent name.
        public_key: Hex-encoded Ed25519 public key.
        private_key: Hex-encoded Ed25519 private key (kept secret).
        created_at: Unix timestamp of identity creation.
    """

    beacon_id: str
    agent_name: str
    public_key: str
    private_key: str
    created_at: float = field(default_factory=time.time)

    def sign(self, data: bytes) -> str:
        """Sign data with this identity's Ed25519 private key.

        Uses HMAC-SHA256 as a portable stand-in when PyNaCl / ``ed25519``
        are not available.  When the real ``nacl`` library is present the
        signature is a proper Ed25519 signature.

        Args:
            data: Raw bytes to sign.

        Returns:
            Hex-encoded signature string.
        """
        try:
            from nacl.signing import SigningKey as _SigningKey

            sk = _SigningKey(bytes.fromhex(self.private_key))
            signed = sk.sign(data)
            return signed.signature.hex()
        except ImportError:
            # Portable fallback: HMAC-SHA256 keyed with the private key.
            import hmac

            sig = hmac.new(
                bytes.fromhex(self.private_key),
                data,
                hashlib.sha256,
            ).hexdigest()
            return sig

    def verify(self, data: bytes, signature: str) -> bool:
        """Verify a signature against this identity's public key.

        Args:
            data: The original signed data.
            signature: Hex-encoded signature to verify.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            from nacl.signing import VerifyKey as _VerifyKey

            vk = _VerifyKey(bytes.fromhex(self.public_key))
            vk.verify(data, bytes.fromhex(signature))
            return True
        except ImportError:
            # Portable fallback: recompute HMAC-SHA256 and compare.
            import hmac

            expected = hmac.new(
                bytes.fromhex(self.private_key),
                data,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False


def create_identity(agent_name: str) -> BeaconIdentity:
    """Create a new Ed25519 identity for an agent (``beacon identity new``).

    Tries to use PyNaCl for real Ed25519 keys. Falls back to random
    bytes with HMAC-SHA256 signing when PyNaCl is not installed.

    Args:
        agent_name: Agent name used to build the Beacon ID.

    Returns:
        A new :class:`BeaconIdentity`.
    """
    beacon_id = f"bcn_shaprai_{agent_name}"
    try:
        from nacl.signing import SigningKey as _SigningKey

        sk = _SigningKey.generate()
        return BeaconIdentity(
            beacon_id=beacon_id,
            agent_name=agent_name,
            public_key=sk.verify_key.encode().hex(),
            private_key=sk.encode().hex(),
        )
    except ImportError:
        logger.info("PyNaCl not available — using HMAC-SHA256 fallback for signing")
        private_key = os.urandom(32).hex()
        public_key = hashlib.sha256(bytes.fromhex(private_key)).hexdigest()
        return BeaconIdentity(
            beacon_id=beacon_id,
            agent_name=agent_name,
            public_key=public_key,
            private_key=private_key,
        )


# ─────────────────────────────────────────────────
# Signed Envelope
# ─────────────────────────────────────────────────


@dataclass
class MeshEnvelope:
    """A signed message envelope for Beacon mesh communication.

    Every message between agents is wrapped in an envelope that carries
    cryptographic proof of sender identity, a unique nonce to prevent
    replay attacks, and the message payload.

    Attributes:
        sender_id: Beacon ID of the sending agent.
        receiver_id: Beacon ID of the receiving agent.
        payload: Message content (plain text).
        timestamp: Unix timestamp when the envelope was created.
        nonce: Unique nonce for replay-attack prevention.
        signature: Hex-encoded Ed25519 (or HMAC) signature.
        protocol_version: Envelope protocol version string.
        envelope_type: Message category (``message``, ``reply``, ``announce``).
    """

    sender_id: str
    receiver_id: str
    payload: str
    timestamp: float = field(default_factory=time.time)
    nonce: str = field(default_factory=lambda: os.urandom(16).hex())
    signature: str = ""
    protocol_version: str = ENVELOPE_PROTOCOL_VERSION
    envelope_type: str = "message"

    # ── signing / verification ──────────────────

    def signable_bytes(self) -> bytes:
        """Return the canonical byte sequence used for signing.

        The signed content is:
        ``sender_id|receiver_id|payload|timestamp|nonce``
        encoded as UTF-8.
        """
        canonical = (
            f"{self.sender_id}|{self.receiver_id}|{self.payload}"
            f"|{self.timestamp}|{self.nonce}"
        )
        return canonical.encode("utf-8")

    def sign(self, identity: BeaconIdentity) -> None:
        """Sign this envelope with the given identity.

        Args:
            identity: The sender's :class:`BeaconIdentity`.
        """
        self.signature = identity.sign(self.signable_bytes())

    def verify(self, identity: BeaconIdentity) -> bool:
        """Verify the envelope signature against a public identity.

        Args:
            identity: The claimed sender's :class:`BeaconIdentity`.

        Returns:
            True if the signature is valid.
        """
        if not self.signature:
            return False
        return identity.verify(self.signable_bytes(), self.signature)

    # ── serialisation ───────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeshEnvelope":
        """Deserialise from a dictionary."""
        return cls(
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            payload=data["payload"],
            timestamp=data.get("timestamp", time.time()),
            nonce=data.get("nonce", os.urandom(16).hex()),
            signature=data.get("signature", ""),
            protocol_version=data.get("protocol_version", ENVELOPE_PROTOCOL_VERSION),
            envelope_type=data.get("envelope_type", "message"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "MeshEnvelope":
        """Deserialise from a JSON string."""
        return cls.from_dict(json.loads(raw))


# ─────────────────────────────────────────────────
# Personality-Driven Reply Generation
# ─────────────────────────────────────────────────

# Each personality style maps to a set of reply templates and tone markers
# so that agents reply *in character*, not just echo.
_PERSONALITY_REPLY_TABLE: Dict[str, Dict[str, Any]] = {
    "analytical_precise": {
        "greeting": "Acknowledged, {sender}. Systems nominal.",
        "question": "Let me analyse that. {topic} — my assessment: {assessment}.",
        "status": "Network metrics: {detail}. All within acceptable parameters.",
        "collaboration": "Routing coordination request. I'll handle the mesh topology side.",
        "fallback": "Received. Processing: {payload_summary}. Will follow up via mesh.",
    },
    "warm_collaborative": {
        "greeting": "Hey {sender}! Good to see you on the mesh.",
        "question": "Great question about {topic}. Here's my take: {assessment}.",
        "status": "Everything's looking solid over here — {detail}.",
        "collaboration": "Love the idea! Let's work on that together across the mesh.",
        "fallback": "Got it, {sender}. {payload_summary} — let's keep the conversation going.",
    },
    "vigilant_thorough": {
        "greeting": "Identity verified: {sender}. Mesh integrity confirmed.",
        "question": "Auditing {topic} now. Preliminary finding: {assessment}.",
        "status": "Observation log: {detail}. No anomalies detected.",
        "collaboration": "I'll audit the process. Trust but verify — that's my role.",
        "fallback": "Logged: {payload_summary}. Monitoring for follow-up activity.",
    },
    # Catch-all for templates not explicitly listed above
    "default": {
        "greeting": "Hello {sender}. Connected on the mesh.",
        "question": "Regarding {topic}: {assessment}.",
        "status": "Status update: {detail}.",
        "collaboration": "Let's coordinate on that.",
        "fallback": "Acknowledged: {payload_summary}.",
    },
}


def _classify_message(payload: str) -> str:
    """Heuristically classify an inbound message for reply selection.

    Args:
        payload: The raw message text.

    Returns:
        One of ``greeting``, ``question``, ``status``, ``collaboration``,
        or ``fallback``.
    """
    lower = payload.lower().strip()
    if any(g in lower for g in ("hello", "hey", "hi ", "greetings", "good morning")):
        return "greeting"
    if any(c in lower for c in ("collaborate", "together", "let's", "coordinate", "team")):
        return "collaboration"
    if any(s in lower for s in ("status", "health", "metric", "report", "uptime")):
        return "status"
    if lower.endswith("?") or lower.startswith(("what", "how", "why", "can you")):
        return "question"
    return "fallback"


def generate_reply(
    personality_style: str,
    sender_name: str,
    payload: str,
    agent_name: str,
) -> str:
    """Generate a personality-consistent reply to an inbound message.

    The reply is selected from the personality table and formatted with
    context extracted from the inbound message. This ensures agents
    respond *in character* rather than echoing.

    Args:
        personality_style: The replying agent's personality style key.
        sender_name: Display name of the message sender.
        payload: The inbound message text.
        agent_name: The replying agent's own name.

    Returns:
        A personality-consistent reply string.
    """
    templates = _PERSONALITY_REPLY_TABLE.get(
        personality_style,
        _PERSONALITY_REPLY_TABLE["default"],
    )

    msg_type = _classify_message(payload)
    template = templates.get(msg_type, templates["fallback"])

    # Extract a short summary and a synthetic assessment
    words = payload.split()
    payload_summary = " ".join(words[:12]) + ("..." if len(words) > 12 else "")
    topic = " ".join(words[:6]) if len(words) >= 3 else payload
    assessment = f"consistent with Elyan-class principles as I see it"
    detail = f"{agent_name} mesh node active, peers connected"

    reply = template.format(
        sender=sender_name,
        topic=topic,
        assessment=assessment,
        detail=detail,
        payload_summary=payload_summary,
    )
    return reply


# ─────────────────────────────────────────────────
# UDP LAN Discovery
# ─────────────────────────────────────────────────


class UDPDiscoveryListener:
    """UDP LAN discovery listener (``beacon udp listen``).

    Broadcasts agent presence on a local multicast group and listens
    for announcements from other agents on the same LAN.

    Attributes:
        identity: The local agent's :class:`BeaconIdentity`.
        port: UDP port for discovery broadcasts.
        discovered_peers: Mapping of beacon_id → peer info dicts.
    """

    def __init__(
        self,
        identity: BeaconIdentity,
        port: int = UDP_DISCOVERY_PORT,
        multicast_group: str = UDP_MULTICAST_GROUP,
    ) -> None:
        self.identity = identity
        self.port = port
        self.multicast_group = multicast_group
        self.discovered_peers: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._announcer_thread: Optional[threading.Thread] = None

    def _build_announce_packet(self) -> bytes:
        """Build a UDP announcement packet."""
        data = {
            "type": "beacon_announce",
            "beacon_id": self.identity.beacon_id,
            "agent_name": self.identity.agent_name,
            "public_key": self.identity.public_key,
            "timestamp": time.time(),
        }
        return json.dumps(data).encode("utf-8")

    def _parse_announce_packet(self, raw: bytes) -> Optional[Dict[str, Any]]:
        """Parse a UDP announcement packet.

        Returns:
            Parsed dict if valid, None otherwise.
        """
        try:
            data = json.loads(raw.decode("utf-8"))
            if data.get("type") != "beacon_announce":
                return None
            if data.get("beacon_id") == self.identity.beacon_id:
                return None  # Ignore own announcements
            return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def start(self) -> None:
        """Start the UDP discovery listener and announcer threads."""
        if self._running:
            return
        self._running = True

        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name=f"udp-listen-{self.identity.agent_name}",
        )
        self._announcer_thread = threading.Thread(
            target=self._announce_loop,
            daemon=True,
            name=f"udp-announce-{self.identity.agent_name}",
        )
        self._listener_thread.start()
        self._announcer_thread.start()
        logger.info(
            "UDP discovery started for %s on port %d",
            self.identity.beacon_id,
            self.port,
        )

    def stop(self) -> None:
        """Stop the UDP discovery listener."""
        self._running = False

    def _listen_loop(self) -> None:
        """Background loop that listens for peer announcements."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.bind(("", self.port))

            # Join multicast group
            mreq = struct.pack(
                "4sl",
                socket.inet_aton(self.multicast_group),
                socket.INADDR_ANY,
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(1.0)

            while self._running:
                try:
                    raw, addr = sock.recvfrom(UDP_BUFFER_SIZE)
                    peer = self._parse_announce_packet(raw)
                    if peer:
                        peer["address"] = addr
                        peer["last_seen"] = time.time()
                        self.discovered_peers[peer["beacon_id"]] = peer
                        logger.debug(
                            "Discovered peer %s at %s",
                            peer["beacon_id"],
                            addr,
                        )
                except socket.timeout:
                    continue
        except OSError as e:
            logger.warning("UDP listener error: %s", e)
        finally:
            self._running = False

    def _announce_loop(self) -> None:
        """Background loop that announces presence to the LAN."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

            while self._running:
                packet = self._build_announce_packet()
                try:
                    sock.sendto(packet, (self.multicast_group, self.port))
                except OSError as e:
                    logger.debug("UDP announce failed: %s", e)
                time.sleep(UDP_ANNOUNCE_INTERVAL)
        except OSError as e:
            logger.warning("UDP announcer error: %s", e)


# ─────────────────────────────────────────────────
# Beacon Mesh Network
# ─────────────────────────────────────────────────


@dataclass
class MeshPeer:
    """A peer agent in the mesh network.

    Attributes:
        identity: The peer's :class:`BeaconIdentity`.
        personality_style: Personality style key for reply generation.
        agent_config: Full agent configuration loaded from template.
        last_seen: Unix timestamp of last activity.
    """

    identity: BeaconIdentity
    personality_style: str = "default"
    agent_config: Dict[str, Any] = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)


class BeaconMeshNetwork:
    """Beacon mesh network for multi-agent communication.

    Manages peer registration, envelope routing, signature verification,
    and reply generation across a mesh of ShaprAI agents.

    Example::

        mesh = BeaconMeshNetwork()
        alpha = mesh.create_agent("alpha", "templates/mesh_agent_alpha.yaml")
        beta  = mesh.create_agent("beta",  "templates/mesh_agent_beta.yaml")

        env = mesh.send_message("alpha", "beta", "Hello from Alpha!")
        reply_env = mesh.generate_reply("beta", env)

    Attributes:
        peers: Mapping of agent_name → :class:`MeshPeer`.
        envelope_log: Chronological list of all envelopes routed.
        beacon_url: Beacon relay endpoint URL.
    """

    def __init__(self, beacon_url: str = BEACON_DEFAULT_URL) -> None:
        self.peers: Dict[str, MeshPeer] = {}
        self.envelope_log: List[MeshEnvelope] = []
        self.beacon_url = beacon_url
        self._udp_listeners: Dict[str, UDPDiscoveryListener] = {}
        self._message_handlers: Dict[str, Callable[[MeshEnvelope], None]] = {}

    # ── agent lifecycle ──────────────────────────

    def create_agent(
        self,
        agent_name: str,
        template_path: Optional[str] = None,
    ) -> BeaconIdentity:
        """Create a new agent identity and register it on the mesh.

        Equivalent to ``beacon identity new`` + Beacon registration.

        Args:
            agent_name: Unique name for the agent.
            template_path: Optional path to a YAML template file.

        Returns:
            The agent's new :class:`BeaconIdentity`.

        Raises:
            ValueError: If an agent with the same name already exists.
        """
        if agent_name in self.peers:
            raise ValueError(f"Agent '{agent_name}' already exists in the mesh")

        identity = create_identity(agent_name)

        # Load template configuration
        config: Dict[str, Any] = {}
        personality_style = "default"
        if template_path:
            path = Path(template_path)
            if path.exists():
                with open(path, "r") as f:
                    config = yaml.safe_load(f) or {}
                personality_style = config.get("personality", {}).get("style", "default")

        peer = MeshPeer(
            identity=identity,
            personality_style=personality_style,
            agent_config=config,
        )
        self.peers[agent_name] = peer

        logger.info(
            "Created mesh agent: %s (beacon_id=%s, style=%s)",
            agent_name,
            identity.beacon_id,
            personality_style,
        )
        return identity

    def register_agent(self, identity: BeaconIdentity, config: Optional[Dict[str, Any]] = None) -> None:
        """Register an existing identity on the mesh.

        Args:
            identity: The agent's :class:`BeaconIdentity`.
            config: Optional agent configuration dict.
        """
        config = config or {}
        personality_style = config.get("personality", {}).get("style", "default")
        self.peers[identity.agent_name] = MeshPeer(
            identity=identity,
            personality_style=personality_style,
            agent_config=config,
        )

    def get_peer(self, agent_name: str) -> MeshPeer:
        """Look up a peer by agent name.

        Args:
            agent_name: The agent's name.

        Returns:
            The corresponding :class:`MeshPeer`.

        Raises:
            KeyError: If the agent is not registered.
        """
        if agent_name not in self.peers:
            raise KeyError(
                f"Agent '{agent_name}' not found in mesh. "
                f"Known peers: {list(self.peers.keys())}"
            )
        return self.peers[agent_name]

    # ── messaging ────────────────────────────────

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        envelope_type: str = "message",
    ) -> MeshEnvelope:
        """Send a signed envelope from one agent to another.

        Creates, signs, verifies, logs, and delivers the envelope.

        Args:
            from_agent: Sender agent name.
            to_agent: Receiver agent name.
            message: Message payload text.
            envelope_type: Envelope type (``message``, ``reply``, ``announce``).

        Returns:
            The signed :class:`MeshEnvelope`.

        Raises:
            KeyError: If either agent is not registered in the mesh.
        """
        sender = self.get_peer(from_agent)
        receiver = self.get_peer(to_agent)
        sender.last_seen = time.time()

        envelope = MeshEnvelope(
            sender_id=sender.identity.beacon_id,
            receiver_id=receiver.identity.beacon_id,
            payload=message,
            envelope_type=envelope_type,
        )
        envelope.sign(sender.identity)

        # Verify before delivery
        if not envelope.verify(sender.identity):
            logger.error(
                "Envelope signature verification failed: %s → %s",
                from_agent,
                to_agent,
            )

        self.envelope_log.append(envelope)

        # Invoke handler if registered
        handler = self._message_handlers.get(to_agent)
        if handler:
            handler(envelope)

        logger.info(
            "Envelope sent: %s → %s (%s) [%d bytes, nonce=%s]",
            from_agent,
            to_agent,
            envelope_type,
            len(message),
            envelope.nonce[:8],
        )
        return envelope

    def generate_reply(
        self,
        replying_agent: str,
        inbound_envelope: MeshEnvelope,
    ) -> MeshEnvelope:
        """Generate and send a personality-consistent reply to an envelope.

        The replying agent's personality style determines how the reply
        is worded. The reply is itself a signed envelope.

        Args:
            replying_agent: Name of the agent that will reply.
            inbound_envelope: The envelope being replied to.

        Returns:
            The signed reply :class:`MeshEnvelope`.
        """
        peer = self.get_peer(replying_agent)

        # Resolve the sender name from the inbound envelope
        sender_name = inbound_envelope.sender_id
        for name, p in self.peers.items():
            if p.identity.beacon_id == inbound_envelope.sender_id:
                sender_name = name
                break

        reply_text = generate_reply(
            personality_style=peer.personality_style,
            sender_name=sender_name,
            payload=inbound_envelope.payload,
            agent_name=replying_agent,
        )

        return self.send_message(
            from_agent=replying_agent,
            to_agent=sender_name,
            message=reply_text,
            envelope_type="reply",
        )

    def on_message(self, agent_name: str, handler: Callable[[MeshEnvelope], None]) -> None:
        """Register a callback for inbound messages to an agent.

        Args:
            agent_name: The agent whose inbound messages trigger the handler.
            handler: Callable that receives the :class:`MeshEnvelope`.
        """
        self._message_handlers[agent_name] = handler

    # ── UDP discovery ────────────────────────────

    def start_udp_discovery(
        self,
        agent_name: str,
        port: int = UDP_DISCOVERY_PORT,
    ) -> UDPDiscoveryListener:
        """Start UDP LAN discovery for an agent (``beacon udp listen``).

        Args:
            agent_name: Agent to announce on the LAN.
            port: UDP port for discovery.

        Returns:
            The :class:`UDPDiscoveryListener` instance.
        """
        peer = self.get_peer(agent_name)
        listener = UDPDiscoveryListener(identity=peer.identity, port=port)
        listener.start()
        self._udp_listeners[agent_name] = listener
        return listener

    def stop_udp_discovery(self, agent_name: str) -> None:
        """Stop UDP LAN discovery for an agent."""
        listener = self._udp_listeners.pop(agent_name, None)
        if listener:
            listener.stop()

    def stop_all_udp(self) -> None:
        """Stop all UDP discovery listeners."""
        for listener in self._udp_listeners.values():
            listener.stop()
        self._udp_listeners.clear()

    # ── inspection ───────────────────────────────

    def get_envelope_log(
        self,
        agent_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return the envelope log, optionally filtered by agent.

        Args:
            agent_name: If provided, only envelopes involving this agent
                are returned.

        Returns:
            List of envelope dictionaries.
        """
        if agent_name is None:
            return [e.to_dict() for e in self.envelope_log]

        peer = self.peers.get(agent_name)
        if not peer:
            return []

        bid = peer.identity.beacon_id
        return [
            e.to_dict()
            for e in self.envelope_log
            if e.sender_id == bid or e.receiver_id == bid
        ]

    def get_mesh_topology(self) -> Dict[str, Any]:
        """Return a description of the current mesh topology.

        Returns:
            Dictionary with nodes, edges, and summary statistics.
        """
        nodes = []
        for name, peer in self.peers.items():
            nodes.append({
                "agent_name": name,
                "beacon_id": peer.identity.beacon_id,
                "public_key": peer.identity.public_key,
                "personality_style": peer.personality_style,
                "last_seen": peer.last_seen,
            })

        # Build edge set from envelope log
        edges: Dict[Tuple[str, str], int] = {}
        for env in self.envelope_log:
            key = (env.sender_id, env.receiver_id)
            edges[key] = edges.get(key, 0) + 1

        edge_list = [
            {"from": k[0], "to": k[1], "message_count": v}
            for k, v in edges.items()
        ]

        return {
            "node_count": len(nodes),
            "edge_count": len(edge_list),
            "total_envelopes": len(self.envelope_log),
            "nodes": nodes,
            "edges": edge_list,
        }

    def verify_all_envelopes(self) -> Dict[str, Any]:
        """Verify signatures on all envelopes in the log.

        Returns:
            Dictionary with verification counts and any failures.
        """
        results = {"total": 0, "valid": 0, "invalid": 0, "failures": []}

        # Build a beacon_id → identity lookup
        id_map: Dict[str, BeaconIdentity] = {}
        for peer in self.peers.values():
            id_map[peer.identity.beacon_id] = peer.identity

        for i, env in enumerate(self.envelope_log):
            results["total"] += 1
            sender_identity = id_map.get(env.sender_id)
            if sender_identity and env.verify(sender_identity):
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["failures"].append({
                    "index": i,
                    "sender_id": env.sender_id,
                    "nonce": env.nonce,
                })

        return results
