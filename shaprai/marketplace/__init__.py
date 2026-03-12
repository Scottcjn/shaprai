# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Template marketplace for publishing, discovering, and purchasing agent templates.

The marketplace enables creators to publish personality templates with RTC pricing,
and buyers to discover and purchase templates for use with ShaprAI's template engine.

Revenue Split:
    - Creator: 90%
    - Protocol: 5% (ShaprAI development fund)
    - Relay: 5% (Node that facilitated the transaction)
"""

from __future__ import annotations

from shaprai.marketplace.registry import (
    MarketplaceRegistry,
    TemplateListing,
    TemplateVersion,
)
from shaprai.marketplace.pricing import (
    RevenueSplit,
    calculate_revenue_split,
    MARKETPLACE_PROTOCOL_FEE,
    MARKETPLACE_RELAY_FEE,
    MARKETPLACE_CREATOR_SHARE,
)
from shaprai.marketplace.validator import (
    TemplateValidator,
    ValidationResult,
    TEMPLATE_SCHEMA,
)

__all__ = [
    # Registry
    "MarketplaceRegistry",
    "TemplateListing",
    "TemplateVersion",
    # Pricing
    "RevenueSplit",
    "calculate_revenue_split",
    "MARKETPLACE_PROTOCOL_FEE",
    "MARKETPLACE_RELAY_FEE",
    "MARKETPLACE_CREATOR_SHARE",
    # Validator
    "TemplateValidator",
    "ValidationResult",
    "TEMPLATE_SCHEMA",
]