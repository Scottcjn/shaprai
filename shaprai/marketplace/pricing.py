"""Pricing Engine — RTC pricing and revenue split calculations."""

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger("shaprai.marketplace.pricing")


@dataclass
class RevenueSplit:
    """Result of revenue split calculation."""
    creator: float
    protocol: float
    relay: float
    total: float


class PricingEngine:
    """Handle RTC pricing and revenue distribution.

    Revenue Split:
    - Creator: 90%
    - Protocol (ShaprAI dev fund): 5%
    - Relay (facilitating node): 5%
    """

    CREATOR_SHARE = 0.90
    PROTOCOL_SHARE = 0.05
    RELAY_SHARE = 0.05

    def __init__(self):
        """Initialize pricing engine."""
        pass

    def calculate_revenue_split(self, price_rtc: float) -> RevenueSplit:
        """Calculate revenue distribution for a sale.

        Args:
            price_rtc: Sale price in RTC

        Returns:
            RevenueSplit with all shares
        """
        creator = price_rtc * self.CREATOR_SHARE
        protocol = price_rtc * self.PROTOCOL_SHARE
        relay = price_rtc * self.RELAY_SHARE

        return RevenueSplit(
            creator=round(creator, 8),
            protocol=round(protocol, 8),
            relay=round(relay, 8),
            total=round(creator + protocol + relay, 8)
        )

    def validate_price(self, price_rtc: float) -> bool:
        """Validate that price is acceptable.

        Args:
            price_rtc: Proposed price

        Returns:
            True if valid
        """
        return price_rtc >= 0

    def estimate_creator_earnings(
        self,
        price_rtc: float,
        estimated_sales: int
    ) -> Dict[str, float]:
        """Estimate creator earnings.

        Args:
            price_rtc: Template price
            estimated_sales: Expected number of sales

        Returns:
            Dict with earnings estimates
        """
        split = self.calculate_revenue_split(price_rtc)
        total_earnings = split.creator * estimated_sales

        return {
            "price_per_sale": price_rtc,
            "creator_share_per_sale": split.creator,
            "estimated_sales": estimated_sales,
            "estimated_total_earnings": round(total_earnings, 8),
            "protocol_fees_total": round(split.protocol * estimated_sales, 8),
            "relay_fees_total": round(split.relay * estimated_sales, 8)
        }

    def format_price(self, price_rtc: float) -> str:
        """Format price for display.

        Args:
            price_rtc: Price in RTC

        Returns:
            Formatted string
        """
        if price_rtc == 0:
            return "Free"
        return f"{price_rtc:.4f} RTC"

    def compare_prices(self, price1: float, price2: float) -> Dict[str, any]:
        """Compare two pricing strategies.

        Args:
            price1: First price option
            price2: Second price option

        Returns:
            Comparison dict
        """
        split1 = self.calculate_revenue_split(price1)
        split2 = self.calculate_revenue_split(price2)

        return {
            "price_1": {
                "price": price1,
                "creator_share": split1.creator,
                "protocol_share": split1.protocol,
                "relay_share": split1.relay
            },
            "price_2": {
                "price": price2,
                "creator_share": split2.creator,
                "protocol_share": split2.protocol,
                "relay_share": split2.relay
            },
            "difference": {
                "price": price2 - price1,
                "creator_share": split2.creator - split1.creator
            }
        }