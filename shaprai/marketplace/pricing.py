# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""RTC pricing and revenue split calculations for the template marketplace.

Revenue Split:
    - Creator: 90%
    - Protocol: 5% (ShaprAI development fund)
    - Relay: 5% (Node that facilitated the transaction)

Reference rate: 1 RTC = $0.10 USD (internal)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Revenue split percentages
MARKETPLACE_CREATOR_SHARE = 0.90  # 90% to creator
MARKETPLACE_PROTOCOL_FEE = 0.05   # 5% to ShaprAI development fund
MARKETPLACE_RELAY_FEE = 0.05      # 5% to relay node

# Minimum and maximum price bounds
MIN_PRICE_RTC = 0      # Free templates allowed
MAX_PRICE_RTC = 10000  # Hard cap for sanity


@dataclass
class RevenueSplit:
    """Calculated revenue split for a template purchase.

    Attributes:
        total_rtc: Total amount paid by buyer (in RTC).
        creator_rtc: Amount going to template creator.
        protocol_rtc: Amount going to ShaprAI development fund.
        relay_rtc: Amount going to the relay node.
        creator_wallet: Creator's wallet ID (for logging).
        relay_node: Relay node identifier (for logging).
    """

    total_rtc: float
    creator_rtc: float
    protocol_rtc: float
    relay_rtc: float
    creator_wallet: Optional[str] = None
    relay_node: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_rtc": self.total_rtc,
            "creator_rtc": self.creator_rtc,
            "protocol_rtc": self.protocol_rtc,
            "relay_rtc": self.relay_rtc,
            "creator_wallet": self.creator_wallet,
            "relay_node": self.relay_node,
        }

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"RevenueSplit(total={self.total_rtc:.4f} RTC, "
            f"creator={self.creator_rtc:.4f}, "
            f"protocol={self.protocol_rtc:.4f}, "
            f"relay={self.relay_rtc:.4f})"
        )


def calculate_revenue_split(
    price_rtc: float,
    creator_wallet: Optional[str] = None,
    relay_node: Optional[str] = None,
) -> RevenueSplit:
    """Calculate the revenue split for a template purchase.

    The split is:
    - 90% to the template creator
    - 5% to ShaprAI protocol fund
    - 5% to the relay node

    Args:
        price_rtc: Price paid by the buyer (in RTC).
        creator_wallet: Creator's wallet ID for logging.
        relay_node: Relay node identifier for logging.

    Returns:
        RevenueSplit with calculated amounts for each party.

    Raises:
        ValueError: If price is negative or exceeds maximum.
    """
    if price_rtc < MIN_PRICE_RTC:
        raise ValueError(f"Price cannot be negative: {price_rtc}")
    if price_rtc > MAX_PRICE_RTC:
        raise ValueError(f"Price exceeds maximum ({MAX_PRICE_RTC} RTC): {price_rtc}")

    creator_rtc = round(price_rtc * MARKETPLACE_CREATOR_SHARE, 8)
    protocol_rtc = round(price_rtc * MARKETPLACE_PROTOCOL_FEE, 8)
    relay_rtc = round(price_rtc * MARKETPLACE_RELAY_FEE, 8)

    # Handle floating point rounding to ensure split sums correctly
    total_split = creator_rtc + protocol_rtc + relay_rtc
    if abs(total_split - price_rtc) > 0.00000001:
        creator_rtc = round(price_rtc - protocol_rtc - relay_rtc, 8)

    logger.info(
        "Revenue split calculated: %f RTC -> creator=%f, protocol=%f, relay=%f",
        price_rtc, creator_rtc, protocol_rtc, relay_rtc,
    )

    return RevenueSplit(
        total_rtc=price_rtc,
        creator_rtc=creator_rtc,
        protocol_rtc=protocol_rtc,
        relay_rtc=relay_rtc,
        creator_wallet=creator_wallet,
        relay_node=relay_node,
    )


def validate_price(price: float) -> bool:
    """Check if a price is within valid bounds."""
    return MIN_PRICE_RTC <= price <= MAX_PRICE_RTC


def format_rtc(amount: float) -> str:
    """Format an RTC amount for display."""
    return f"{amount:.2f} RTC"


def rtc_to_usd(amount: float, rate: float = 0.10) -> float:
    """Convert RTC to USD reference rate."""
    return amount * rate


def usd_to_rtc(amount: float, rate: float = 0.10) -> float:
    """Convert USD to RTC reference rate."""
    if rate <= 0:
        raise ValueError("Rate must be positive")
    return amount / rate