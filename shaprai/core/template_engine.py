# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Template engine for agent blueprints.

Templates define the complete specification for an Elyan-class agent:
model, personality, capabilities, ethics, and DriftLock configuration.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from shaprai.integrations.rustchain import RUSTCHAIN_DEFAULT_URL

logger = logging.getLogger(__name__)


@dataclass
class AgentTemplate:
    """Blueprint for creating an Elyan-class agent.

    Attributes:
        name: Unique template identifier.
        model: Model configuration (base, quantization, min_vram_gb).
        personality: Style, communication tone, humor level.
        capabilities: List of agent capabilities (code_review, bounty_discovery, etc.).
        platforms: Target deployment platforms (github, bottube, moltbook).
        ethics_profile: Ethics framework identifier (default: sophiacore_default).
        driftlock: DriftLock configuration (enabled, check_interval, anchor_phrases).
        description: Human-readable description of what agents from this template do.
        version: Template version string.
        rtc_config: RustChain token configuration for bounties and fees.
    """

    name: str
    model: Dict[str, Any] = field(default_factory=dict)
    personality: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
    ethics_profile: str = "sophiacore_default"
    driftlock: Dict[str, Any] = field(default_factory=lambda: {"enabled": True, "check_interval": 25})
    description: str = ""
    version: str = "1.0"
    rtc_config: Dict[str, Any] = field(default_factory=dict)


def load_template(path: str) -> AgentTemplate:
    """Load an agent template from a YAML file.

    Args:
        path: Path to the YAML template file.

    Returns:
        Parsed AgentTemplate instance.

    Raises:
        FileNotFoundError: If the template file doesn't exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    template_path = Path(path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {path}")

    with open(template_path, "r") as f:
        data = yaml.safe_load(f)

    return AgentTemplate(
        name=data.get("name", template_path.stem),
        model=data.get("model", {}),
        personality=data.get("personality", {}),
        capabilities=data.get("capabilities", []),
        platforms=data.get("platforms", []),
        ethics_profile=data.get("ethics_profile", "sophiacore_default"),
        driftlock=data.get("driftlock", {"enabled": True, "check_interval": 25}),
        description=data.get("description", ""),
        version=data.get("version", "1.0"),
        rtc_config=data.get("rtc_config", {}),
    )


def save_template(template: AgentTemplate, path: str) -> None:
    """Save an agent template to a YAML file.

    Args:
        template: The AgentTemplate to serialize.
        path: Destination file path.
    """
    template_path = Path(path)
    template_path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(template)
    with open(template_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def fork_template(
    source_path: str,
    new_name: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> AgentTemplate:
    """Fork an existing template with optional overrides.

    Args:
        source_path: Path to the source template YAML.
        new_name: Name for the forked template.
        overrides: Dictionary of fields to override in the fork.

    Returns:
        New AgentTemplate with the fork applied.
    """
    source = load_template(source_path)
    data = asdict(source)
    data["name"] = new_name

    if overrides:
        for key, value in overrides.items():
            if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value

    return AgentTemplate(**data)


def list_templates(templates_dir: str) -> List[AgentTemplate]:
    """List all available templates in a directory.

    Args:
        templates_dir: Path to the templates directory.

    Returns:
        List of AgentTemplate instances found in the directory.
    """
    templates_path = Path(templates_dir)
    if not templates_path.exists():
        return []

    templates = []
    for yaml_file in sorted(templates_path.glob("*.yaml")):
        try:
            templates.append(load_template(str(yaml_file)))
        except Exception:
            continue  # Skip malformed templates

    return templates


# ─────────────────────────────────────────────────────────────────────────────
# Template Marketplace Functions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MarketplaceTemplate:
    """Template listing in the marketplace with pricing info."""
    name: str
    author: str
    description: str
    price_rtc: float
    version: str
    capabilities: List[str] = field(default_factory=list)
    downloads: int = 0
    rating: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def publish_template(
    template_path: str,
    author: str,
    price_rtc: float,
    description: str = "",
    marketplace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish a template to the marketplace.

    Args:
        template_path: Path to the template YAML file.
        author: Author/publisher name.
        price_rtc: Price in RTC tokens.
        description: Optional description override.
        marketplace_dir: Directory to store marketplace listings (default: ~/.shaprai/marketplace).

    Returns:
        Dict with success status and listing info.
    """
    from shaprai.integrations.rustchain import pay_template_listing_fee
    
    marketplace_path = Path(marketplace_dir) if marketplace_dir else Path.home() / ".shaprai" / "marketplace"
    marketplace_path.mkdir(parents=True, exist_ok=True)

    # Load the template
    template = load_template(template_path)
    
    # Save the template YAML
    template_file = marketplace_path / f"{template.name}.yaml"
    save_template(template, str(template_file))

    # Create marketplace listing
    listing = MarketplaceTemplate(
        name=template.name,
        author=author,
        description=description or template.description,
        price_rtc=price_rtc,
        version=template.version,
        capabilities=template.capabilities,
    )

    # Save listing metadata
    listing_file = marketplace_path / f"{template.name}.listing.yaml"
    with open(listing_file, "w") as f:
        yaml.dump(asdict(listing), f, default_flow_style=False)

    return {
        "success": True,
        "name": template.name,
        "author": author,
        "price_rtc": price_rtc,
    }


def purchase_template(
    template_name: str,
    wallet_id: str,
    marketplace_dir: Optional[str] = None,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> Dict[str, Any]:
    """Purchase a template from the marketplace.

    Args:
        template_name: Name of the template to purchase.
        wallet_id: Buyer's RustChain wallet ID.
        marketplace_dir: Marketplace directory (default: ~/.shaprai/marketplace).
        rustchain_url: RustChain node URL for payment.

    Returns:
        Dict with success status and template info.
    """
    from shaprai.integrations.rustchain import process_template_sale
    
    marketplace_path = Path(marketplace_dir) if marketplace_dir else Path.home() / ".shaprai" / "marketplace"
    listing_file = marketplace_path / f"{template_name}.listing.yaml"
    template_file = marketplace_path / f"{template_name}.yaml"

    if not listing_file.exists() or not template_file.exists():
        return {"success": False, "error": f"Template '{template_name}' not found"}

    # Load listing to get price
    with open(listing_file, "r") as f:
        listing_data = yaml.safe_load(f)

    price_rtc = listing_data.get("price_rtc", 0.0)
    author = listing_data.get("author", "unknown")

    # Process payment via RustChain
    if price_rtc > 0:
        payment_success = process_template_sale(
            buyer_wallet=wallet_id,
            seller_wallet=f"agent-{author}",
            price_rtc=price_rtc,
            template_name=template_name,
            rustchain_url=rustchain_url,
        )
        if not payment_success:
            return {"success": False, "error": "Payment failed"}

    # Load template info
    template = load_template(str(template_file))
    
    # Update download count
    listing_data["downloads"] = listing_data.get("downloads", 0) + 1
    with open(listing_file, "w") as f:
        yaml.dump(listing_data, f, default_flow_style=False)

    return {
        "success": True,
        "name": template.name,
        "description": template.description,
        "capabilities": template.capabilities,
        "model": template.model.get("base", "unknown"),
    }


def _process_template_payment(
    buyer_wallet: str,
    author_wallet: str,
    amount_rtc: float,
    template_name: str,
    rustchain_url: str,
) -> bool:
    """Process RTC payment for template purchase.

    Args:
        buyer_wallet: Buyer's wallet ID.
        author_wallet: Author's wallet ID.
        amount_rtc: Payment amount in RTC.
        template_name: Template being purchased.
        rustchain_url: RustChain node URL.

    Returns:
        True if payment successful.
    """
    try:
        import requests

        payload = {
            "from_wallet": buyer_wallet,
            "to_wallet": author_wallet,
            "amount_rtc": amount_rtc,
            "memo": f"Template purchase: {template_name}",
        }

        response = requests.post(
            f"{rustchain_url}/wallet/transfer/signed",
            json=payload,
            timeout=30,
            verify=False,
        )
        return response.status_code == 200

    except Exception as e:
        logger.error("Template payment failed: %s", e)
        return False


def list_marketplace_templates(marketplace_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all templates available in the marketplace.

    Args:
        marketplace_dir: Marketplace directory path (default: ~/.shaprai/marketplace).

    Returns:
        List of template dicts with name, author, price_rtc, rating, etc.
    """
    marketplace_path = Path(marketplace_dir) if marketplace_dir else Path.home() / ".shaprai" / "marketplace"
    if not marketplace_path.exists():
        return []

    templates = []
    for listing_file in sorted(marketplace_path.glob("*.listing.yaml")):
        try:
            with open(listing_file, "r") as f:
                data = yaml.safe_load(f)
            templates.append({
                "name": data.get("name", ""),
                "author": data.get("author", "unknown"),
                "price_rtc": data.get("price_rtc", 0.0),
                "rating": data.get("rating", 0.0),
                "downloads": data.get("downloads", 0),
            })
        except Exception:
            continue  # Skip malformed listings

    return templates


def rate_template(
    template_name: str,
    rating: float,
    marketplace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Rate a purchased template.

    Args:
        template_name: Template to rate.
        rating: Rating score (1.0-5.0).
        marketplace_dir: Marketplace directory (default: ~/.shaprai/marketplace).

    Returns:
        Dict with success status and new rating.
    """
    marketplace_path = Path(marketplace_dir) if marketplace_dir else Path.home() / ".shaprai" / "marketplace"
    listing_file = marketplace_path / f"{template_name}.listing.yaml"

    if not listing_file.exists():
        return {"success": False, "error": f"Template '{template_name}' not found"}

    with open(listing_file, "r") as f:
        data = yaml.safe_load(f)

    # Update rating (simple average for now)
    current_rating = data.get("rating", 0.0)
    current_downloads = data.get("downloads", 0)

    # New average = (old_sum + new_rating) / (count + 1)
    old_sum = current_rating * current_downloads
    new_count = current_downloads + 1
    new_rating = round((old_sum + rating) / new_count, 2)
    
    data["rating"] = new_rating
    data["downloads"] = new_count
    data["updated_at"] = time.time()

    with open(listing_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    return {
        "success": True,
        "new_rating": new_rating,
    }
