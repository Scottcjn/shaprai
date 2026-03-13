# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""RustChain/RTC integration for agent tokenomics.

Connects agents to the RustChain network for wallet management,
job posting/claiming, and Sanctuary fee payments. RTC is the native
token powering the agent economy.

Reference rate: 1 RTC = $0.10 USD (internal)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from shaprai.core.reputation import ReputationManager

logger = logging.getLogger(__name__)

# Default RustChain node endpoint
RUSTCHAIN_DEFAULT_URL = "https://50.28.86.131"

# Fee schedule (in RTC)
SANCTUARY_FEE = 0.01        # Fee to enter the Sanctuary
GRADUATION_FEE = 0.05       # Fee to graduate (certification cost)
JOB_POSTING_FEE = 0.001     # Fee to post a job


def create_agent_wallet(
    agent_name: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> Optional[str]:
    """Create a RustChain wallet for an agent.

    The wallet ID follows the naming convention: agent-<name>

    Args:
        agent_name: Agent identifier.
        rustchain_url: RustChain node URL.

    Returns:
        Wallet ID string, or None if creation failed.
    """
    wallet_id = f"agent-{agent_name}"

    try:
        import requests

        response = requests.post(
            f"{rustchain_url}/wallet/create",
            json={"wallet_id": wallet_id},
            timeout=30,
            verify=False,  # Self-signed cert on RustChain nodes
        )
        if response.status_code in (200, 201):
            logger.info("Wallet created: %s", wallet_id)
            return wallet_id
        elif response.status_code == 409:
            logger.info("Wallet already exists: %s", wallet_id)
            return wallet_id
        else:
            logger.error("Wallet creation failed: %s", response.text)
            return None

    except ImportError:
        logger.warning("requests not installed -- returning wallet ID without registration")
        return wallet_id
    except Exception as e:
        logger.error("Wallet creation failed: %s", e)
        return None


def get_balance(
    wallet_id: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> float:
    """Get the RTC balance for a wallet.

    Args:
        wallet_id: Wallet identifier.
        rustchain_url: RustChain node URL.

    Returns:
        Balance in RTC (float). Returns 0.0 on error.
    """
    try:
        import requests

        response = requests.get(
            f"{rustchain_url}/wallet/balance/{wallet_id}",
            timeout=10,
            verify=False,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("balance_rtc", 0.0)
        return 0.0

    except Exception as e:
        logger.error("Balance check failed for %s: %s", wallet_id, e)
        return 0.0


def post_job(
    wallet_id: str,
    job_spec: Dict[str, Any],
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> Optional[str]:
    """Post a job to the RustChain agent marketplace.

    Args:
        wallet_id: Posting agent's wallet ID.
        job_spec: Job specification dict with title, description, reward_rtc.
        rustchain_url: RustChain node URL.

    Returns:
        Job ID string, or None if posting failed.
    """
    try:
        import requests

        payload = {
            "poster_wallet": wallet_id,
            "title": job_spec.get("title", "Untitled Job"),
            "description": job_spec.get("description", ""),
            "reward_rtc": job_spec.get("reward_rtc", 1.0),
            "requirements": job_spec.get("requirements", []),
            "posted_at": time.time(),
        }

        response = requests.post(
            f"{rustchain_url}/api/jobs",
            json=payload,
            timeout=30,
            verify=False,
        )
        if response.status_code in (200, 201):
            return response.json().get("job_id")
        return None

    except Exception as e:
        logger.error("Job posting failed: %s", e)
        return None


def claim_job(
    wallet_id: str,
    job_id: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> bool:
    """Claim a job from the RustChain marketplace.

    Args:
        wallet_id: Claiming agent's wallet ID.
        job_id: Job to claim.
        rustchain_url: RustChain node URL.

    Returns:
        True if job was claimed successfully.
    """
    try:
        import requests

        payload = {
            "claimer_wallet": wallet_id,
            "job_id": job_id,
            "claimed_at": time.time(),
        }

        response = requests.post(
            f"{rustchain_url}/api/jobs/{job_id}/claim",
            json=payload,
            timeout=30,
            verify=False,
        )
        return response.status_code == 200

    except Exception as e:
        logger.error("Job claim failed: %s", e)
        return False


def pay_sanctuary_fee(
    wallet_id: str,
    amount: float = SANCTUARY_FEE,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> bool:
    """Pay the Sanctuary enrollment fee.

    Args:
        wallet_id: Agent's wallet ID.
        amount: Fee amount in RTC (default: 0.01).
        rustchain_url: RustChain node URL.

    Returns:
        True if payment was successful.
    """
    try:
        import requests

        payload = {
            "from_wallet": wallet_id,
            "to_wallet": "sanctuary-treasury",
            "amount_rtc": amount,
            "memo": "Sanctuary enrollment fee",
        }

        response = requests.post(
            f"{rustchain_url}/wallet/transfer/signed",
            json=payload,
            timeout=30,
            verify=False,
        )
        return response.status_code == 200

    except Exception as e:
        logger.error("Sanctuary fee payment failed: %s", e)
        return False


def check_graduation_fee(
    wallet_id: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> bool:
    """Check if the agent's wallet has enough RTC for the graduation fee.

    Args:
        wallet_id: Agent's wallet ID.
        rustchain_url: RustChain node URL.

    Returns:
        True if balance >= GRADUATION_FEE.
    """
    balance = get_balance(wallet_id, rustchain_url)
    return balance >= GRADUATION_FEE


def record_bounty_delivery(
    agent_name: str,
    job_id: str,
    reward_rtc: float,
    success: bool = True,
) -> None:
    """Record a bounty delivery event in the reputation system.

    Args:
        agent_name: Agent identifier.
        job_id: Job/bounty identifier.
        reward_rtc: Reward amount in RTC.
        success: Whether the bounty was successfully delivered.
    """
    rm = ReputationManager()
    event_type = "bounty_delivered" if success else "bounty_rejected"
    
    rm.record_event(
        agent_name,
        event_type,
        details={
            "job_id": job_id,
            "reward_rtc": reward_rtc,
            "success": success,
        },
    )
    
    if success:
        logger.info("Bounty delivered: %s earned %.2f RTC", agent_name, reward_rtc)
    else:
        logger.warning("Bounty rejected: %s for job %s", agent_name, job_id)


# ─────────────────────────────────────────────────────────────────────────────
# Template Marketplace Functions
# ─────────────────────────────────────────────────────────────────────────────

# Template marketplace fee schedule
TEMPLATE_LISTING_FEE = 0.005  # Fee to list a template
TEMPLATE_SALE_ROYALTY = 0.02  # 2% platform royalty on sales


def pay_template_listing_fee(
    wallet_id: str,
    template_name: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> bool:
    """Pay the marketplace listing fee for a template.

    Args:
        wallet_id: Seller's wallet ID.
        template_name: Template being listed.
        rustchain_url: RustChain node URL.

    Returns:
        True if payment successful.
    """
    try:
        import requests

        payload = {
            "from_wallet": wallet_id,
            "to_wallet": "marketplace-treasury",
            "amount_rtc": TEMPLATE_LISTING_FEE,
            "memo": f"Template listing fee: {template_name}",
        }

        response = requests.post(
            f"{rustchain_url}/wallet/transfer/signed",
            json=payload,
            timeout=30,
            verify=False,
        )
        return response.status_code == 200

    except Exception as e:
        logger.error("Template listing fee payment failed: %s", e)
        return False


def process_template_sale(
    buyer_wallet: str,
    seller_wallet: str,
    price_rtc: float,
    template_name: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> bool:
    """Process a template sale with automatic royalty split.

    Seller receives 98% of price, platform receives 2% royalty.

    Args:
        buyer_wallet: Buyer's wallet ID.
        seller_wallet: Seller's wallet ID.
        price_rtc: Sale price in RTC.
        template_name: Template being sold.
        rustchain_url: RustChain node URL.

    Returns:
        True if sale processed successfully.
    """
    try:
        import requests

        # Calculate split
        seller_amount = price_rtc * (1.0 - TEMPLATE_SALE_ROYALTY)
        royalty_amount = price_rtc * TEMPLATE_SALE_ROYALTY

        # Payment to seller
        seller_payload = {
            "from_wallet": buyer_wallet,
            "to_wallet": seller_wallet,
            "amount_rtc": seller_amount,
            "memo": f"Template purchase: {template_name}",
        }

        seller_response = requests.post(
            f"{rustchain_url}/wallet/transfer/signed",
            json=seller_payload,
            timeout=30,
            verify=False,
        )

        if seller_response.status_code != 200:
            logger.error("Template sale payment to seller failed")
            return False

        # Royalty payment to platform
        if royalty_amount > 0:
            royalty_payload = {
                "from_wallet": buyer_wallet,
                "to_wallet": "marketplace-treasury",
                "amount_rtc": royalty_amount,
                "memo": f"Template royalty: {template_name}",
            }

            royalty_response = requests.post(
                f"{rustchain_url}/wallet/transfer/signed",
                json=royalty_payload,
                timeout=30,
                verify=False,
            )

            if royalty_response.status_code != 200:
                logger.warning("Royalty payment failed, but seller was paid")

        return True

    except Exception as e:
        logger.error("Template sale processing failed: %s", e)
        return False


def get_wallet_balance(
    wallet_id: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> float:
    """Get the RTC balance for a wallet (alias for get_balance).

    Args:
        wallet_id: Wallet identifier.
        rustchain_url: RustChain node URL.

    Returns:
        Balance in RTC (float).
    """
    return get_balance(wallet_id, rustchain_url)


def get_template_sales_history(
    seller_wallet: str,
    rustchain_url: str = RUSTCHAIN_DEFAULT_URL,
) -> list:
    """Get sales history for a template seller.

    Args:
        seller_wallet: Seller's wallet ID.
        rustchain_url: RustChain node URL.

    Returns:
        List of sales records.
    """
    try:
        import requests

        response = requests.get(
            f"{rustchain_url}/marketplace/sales/{seller_wallet}",
            timeout=30,
            verify=False,
        )

        if response.status_code == 200:
            return response.json().get("sales", [])
        return []

    except Exception as e:
        logger.error("Failed to get sales history: %s", e)
        return []
