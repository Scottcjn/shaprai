# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""RTC pricing and revenue split calculation."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RevenueSplit:
    """Revenue split for a template purchase."""
    creator_amount: int  # 90% to creator
    protocol_amount: int  # 5% to ShaprAI development fund
    relay_amount: int  # 5% to relay node
    total_rtc: int
    template_name: str
    template_version: str
    buyer_id: Optional[str] = None


class PricingEngine:
    """Calculate RTC pricing and revenue splits."""

    # Revenue split percentages
    CREATOR_SHARE = 0.90  # 90%
    PROTOCOL_SHARE = 0.05  # 5%
    RELAY_SHARE = 0.05  # 5%

    def __init__(self, relay_node_id: Optional[str] = None):
        self.relay_node_id = relay_node_id

    def calculate_split(self, price_rtc: int, template_name: str, template_version: str) -> RevenueSplit:
        """Calculate revenue split for a purchase.
        
        Args:
            price_rtc: Total RTC price
            template_name: Name of the template
            template_version: Version of the template
            
        Returns:
            RevenueSplit with amounts for each party
        """
        creator_amount = int(price_rtc * self.CREATOR_SHARE)
        protocol_amount = int(price_rtc * self.PROTOCOL_SHARE)
        relay_amount = price_rtc - creator_amount - protocol_amount  # Ensure we don't lose any RTC due to rounding

        return RevenueSplit(
            creator_amount=creator_amount,
            protocol_amount=protocol_amount,
            relay_amount=relay_amount,
            total_rtc=price_rtc,
            template_name=template_name,
            template_version=template_version,
        )

    def validate_price(self, price_rtc: int) -> bool:
        """Validate a template price.
        
        Args:
            price_rtc: Proposed price in RTC
            
        Returns:
            True if price is valid
            
        Raises:
            ValueError: If price is invalid
        """
        if price_rtc < 0:
            raise ValueError("Price cannot be negative")
        if price_rtc > 100000:
            raise ValueError("Price cannot exceed 100,000 RTC")
        return True

    def format_rtc(self, amount: int) -> str:
        """Format RTC amount for display."""
        return f"{amount} RTC"

    def get_creator_share_percent(self) -> float:
        """Get creator share as percentage."""
        return self.CREATOR_SHARE * 100

    def get_protocol_share_percent(self) -> float:
        """Get protocol share as percentage."""
        return self.PROTOCOL_SHARE * 100

    def get_relay_share_percent(self) -> float:
        """Get relay share as percentage."""
        return self.RELAY_SHARE * 100


def calculate_purchase(price_rtc: int, template_name: str, template_version: str) -> Dict:
    """Convenience function to calculate a purchase.
    
    Args:
        price_rtc: Total RTC price
        template_name: Name of the template
        template_version: Version of the template
        
    Returns:
        Dict with revenue split details
    """
    engine = PricingEngine()
    split = engine.calculate_split(price_rtc, template_name, template_version)
    return {
        "total_rtc": split.total_rtc,
        "creator": {
            "amount": split.creator_amount,
            "percent": "90%",
        },
        "protocol": {
            "amount": split.protocol_amount,
            "percent": "5%",
        },
        "relay": {
            "amount": split.relay_amount,
            "percent": "5%",
        },
        "template": f"{template_name}@{template_version}",
    }
