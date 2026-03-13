# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for template marketplace functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from shaprai.core.template_engine import (
    AgentTemplate,
    save_template,
    publish_template,
    purchase_template,
    list_marketplace_templates,
    rate_template,
    MarketplaceTemplate,
)
from shaprai.integrations.rustchain import (
    pay_template_listing_fee,
    process_template_sale,
    TEMPLATE_LISTING_FEE,
    TEMPLATE_SALE_ROYALTY,
)


@pytest.fixture
def sample_template():
    """Create a sample agent template for testing."""
    return AgentTemplate(
        name="test_template",
        model={"base": "Qwen/Qwen3-7B-Instruct", "quantization": "q4_K_M"},
        personality={"style": "professional", "communication": "clear"},
        capabilities=["code_review", "test_writing"],
        platforms=["github"],
        ethics_profile="sophiacore_default",
        driftlock={"enabled": True, "check_interval": 25},
        description="Test template for marketplace",
        version="1.0",
    )


@pytest.fixture
def temp_marketplace_dir():
    """Create a temporary directory for marketplace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestPublishTemplate:
    """Tests for template publishing functionality."""

    def test_publish_template_creates_files(self, sample_template, temp_marketplace_dir):
        """Test that publishing creates both YAML and listing files."""
        listing = publish_template(
            template=sample_template,
            author="test_author",
            price_rtc=5.0,
            marketplace_dir=temp_marketplace_dir,
        )

        # Check listing object
        assert listing.name == "test_template"
        assert listing.author == "test_author"
        assert listing.price_rtc == 5.0
        assert listing.description == "Test template for marketplace"

        # Check files were created
        template_file = Path(temp_marketplace_dir) / "test_template.yaml"
        listing_file = Path(temp_marketplace_dir) / "test_template.listing.yaml"

        assert template_file.exists()
        assert listing_file.exists()

    def test_publish_template_yaml_content(self, sample_template, temp_marketplace_dir):
        """Test that template YAML is saved correctly."""
        publish_template(
            template=sample_template,
            author="test_author",
            price_rtc=5.0,
            marketplace_dir=temp_marketplace_dir,
        )

        template_file = Path(temp_marketplace_dir) / "test_template.yaml"
        with open(template_file, "r") as f:
            data = yaml.safe_load(f)

        assert data["name"] == "test_template"
        assert data["capabilities"] == ["code_review", "test_writing"]
        assert data["version"] == "1.0"

    def test_publish_template_listing_content(self, sample_template, temp_marketplace_dir):
        """Test that listing metadata is saved correctly."""
        publish_template(
            template=sample_template,
            author="test_author",
            price_rtc=5.0,
            marketplace_dir=temp_marketplace_dir,
        )

        listing_file = Path(temp_marketplace_dir) / "test_template.listing.yaml"
        with open(listing_file, "r") as f:
            data = yaml.safe_load(f)

        assert data["name"] == "test_template"
        assert data["author"] == "test_author"
        assert data["price_rtc"] == 5.0
        assert data["downloads"] == 0
        assert data["rating"] == 0.0


class TestListMarketplaceTemplates:
    """Tests for marketplace listing functionality."""

    def test_list_empty_marketplace(self, temp_marketplace_dir):
        """Test listing when marketplace is empty."""
        templates = list_marketplace_templates(temp_marketplace_dir)
        assert templates == []

    def test_list_marketplace_with_templates(self, sample_template, temp_marketplace_dir):
        """Test listing marketplace with multiple templates."""
        # Publish two templates
        publish_template(sample_template, "author1", 5.0, temp_marketplace_dir)

        template2 = AgentTemplate(
            name="another_template",
            description="Another test template",
        )
        publish_template(template2, "author2", 10.0, temp_marketplace_dir)

        templates = list_marketplace_templates(temp_marketplace_dir)

        assert len(templates) == 2
        names = [t.name for t in templates]
        assert "test_template" in names
        assert "another_template" in names

    def test_list_marketplace_skips_malformed(self, temp_marketplace_dir):
        """Test that malformed listings are skipped."""
        # Create a malformed listing file
        listing_file = Path(temp_marketplace_dir) / "bad_template.listing.yaml"
        with open(listing_file, "w") as f:
            f.write("invalid: yaml: content: [")

        # Should not raise, just skip the bad file
        templates = list_marketplace_templates(temp_marketplace_dir)
        assert templates == []


class TestRateTemplate:
    """Tests for template rating functionality."""

    def test_rate_template_updates_rating(self, sample_template, temp_marketplace_dir):
        """Test that rating a template updates the listing."""
        publish_template(sample_template, "author", 5.0, temp_marketplace_dir)

        # Rate the template
        result = rate_template("test_template", 4.5, temp_marketplace_dir)
        assert result is True

        # Check rating was updated
        templates = list_marketplace_templates(temp_marketplace_dir)
        assert len(templates) == 1
        assert templates[0].rating == 4.5
        assert templates[0].downloads == 1

    def test_rate_template_multiple_ratings(self, sample_template, temp_marketplace_dir):
        """Test that multiple ratings are averaged correctly."""
        publish_template(sample_template, "author", 5.0, temp_marketplace_dir)

        # Add multiple ratings
        rate_template("test_template", 3.0, temp_marketplace_dir)
        rate_template("test_template", 5.0, temp_marketplace_dir)

        templates = list_marketplace_templates(temp_marketplace_dir)
        assert templates[0].rating == 4.0  # Average of 3 and 5
        assert templates[0].downloads == 2

    def test_rate_nonexistent_template(self, temp_marketplace_dir):
        """Test rating a template that doesn't exist."""
        result = rate_template("nonexistent", 5.0, temp_marketplace_dir)
        assert result is False


class TestPurchaseTemplate:
    """Tests for template purchase functionality."""

    @patch('shaprai.core.template_engine._process_template_payment')
    def test_purchase_template_success(self, mock_payment, sample_template, temp_marketplace_dir):
        """Test successful template purchase."""
        mock_payment.return_value = True

        # Publish template first
        publish_template(sample_template, "author", 5.0, temp_marketplace_dir)

        # Purchase it
        purchased = purchase_template(
            template_name="test_template",
            buyer_wallet="buyer-wallet-123",
            marketplace_dir=temp_marketplace_dir,
        )

        assert purchased is not None
        assert purchased.name == "test_template"
        assert purchased.description == "Test template for marketplace"
        mock_payment.assert_called_once()

    @patch('shaprai.core.template_engine._process_template_payment')
    def test_purchase_template_payment_fails(self, mock_payment, sample_template, temp_marketplace_dir):
        """Test purchase when payment fails."""
        mock_payment.return_value = False

        publish_template(sample_template, "author", 5.0, temp_marketplace_dir)

        purchased = purchase_template(
            template_name="test_template",
            buyer_wallet="buyer-wallet-123",
            marketplace_dir=temp_marketplace_dir,
        )

        assert purchased is None

    def test_purchase_nonexistent_template(self, temp_marketplace_dir):
        """Test purchasing a template that doesn't exist."""
        purchased = purchase_template(
            template_name="nonexistent",
            buyer_wallet="buyer-wallet-123",
            marketplace_dir=temp_marketplace_dir,
        )
        assert purchased is None


class TestTemplatePayment:
    """Tests for template payment processing."""

    @patch('requests.post')
    def test_process_template_payment_success(self, mock_post):
        """Test successful payment processing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        from shaprai.core.template_engine import _process_template_payment

        result = _process_template_payment(
            buyer_wallet="buyer-123",
            author_wallet="author-456",
            amount_rtc=5.0,
            template_name="test_template",
            rustchain_url="https://test.rustchain.local",
        )

        assert result is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_process_template_payment_failure(self, mock_post):
        """Test failed payment processing."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        from shaprai.core.template_engine import _process_template_payment

        result = _process_template_payment(
            buyer_wallet="buyer-123",
            author_wallet="author-456",
            amount_rtc=5.0,
            template_name="test_template",
            rustchain_url="https://test.rustchain.local",
        )

        assert result is False


class TestRustChainMarketplaceFunctions:
    """Tests for RustChain marketplace integration."""

    def test_listing_fee_constant_defined(self):
        """Test that listing fee constant is defined."""
        assert TEMPLATE_LISTING_FEE > 0
        assert TEMPLATE_LISTING_FEE < 1.0  # Should be reasonable

    def test_royalty_rate_constant_defined(self):
        """Test that royalty rate constant is defined."""
        assert TEMPLATE_SALE_ROYALTY > 0
        assert TEMPLATE_SALE_ROYALTY < 0.1  # Should be less than 10%

    @patch('requests.post')
    def test_pay_template_listing_fee_success(self, mock_post):
        """Test successful listing fee payment."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = pay_template_listing_fee(
            wallet_id="seller-wallet-123",
            template_name="test_template",
        )

        assert result is True

    @patch('requests.post')
    def test_process_template_sale_with_royalty(self, mock_post):
        """Test template sale with automatic royalty split."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = process_template_sale(
            buyer_wallet="buyer-123",
            seller_wallet="seller-456",
            template_name="test_template",
            price_rtc=10.0,
        )

        assert result is True
        # Should make two calls: one to seller, one to platform
        assert mock_post.call_count == 2

        # Verify royalty calculation
        calls = mock_post.call_args_list
        seller_payload = calls[0][1]['json']
        platform_payload = calls[1][1]['json']

        # Seller gets 98% (10.0 * 0.98 = 9.8)
        assert seller_payload['amount_rtc'] == 10.0 * (1 - TEMPLATE_SALE_ROYALTY)
        # Platform gets 2% royalty
        assert platform_payload['amount_rtc'] == 10.0 * TEMPLATE_SALE_ROYALTY


class TestMarketplaceTemplateDataclass:
    """Tests for MarketplaceTemplate dataclass."""

    def test_marketplace_template_defaults(self):
        """Test MarketplaceTemplate default values."""
        tmpl = MarketplaceTemplate(
            name="test",
            author="author",
            description="desc",
            price_rtc=5.0,
            version="1.0",
        )

        assert tmpl.downloads == 0
        assert tmpl.rating == 0.0
        assert tmpl.capabilities == []
        assert tmpl.created_at is not None
        assert tmpl.updated_at is not None

    def test_marketplace_template_with_capabilities(self):
        """Test MarketplaceTemplate with capabilities."""
        tmpl = MarketplaceTemplate(
            name="test",
            author="author",
            description="desc",
            price_rtc=5.0,
            version="1.0",
            capabilities=["code_review", "testing"],
            rating=4.5,
            downloads=10,
        )

        assert tmpl.capabilities == ["code_review", "testing"]
        assert tmpl.rating == 4.5
        assert tmpl.downloads == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
