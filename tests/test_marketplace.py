# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the marketplace module."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_template():
    """Sample valid template data."""
    return {
        "name": "test-template",
        "version": "1.0.0",
        "description": "A test template for unit testing purposes",
        "author": "test-creator",
        "model": {"base": "Qwen/Qwen3-7B-Instruct", "quantization": "q4_K_M"},
        "personality": {"style": "professional", "communication": "clear"},
        "capabilities": ["code_review", "test_writing"],
        "platforms": ["github"],
        "ethics_profile": "sophiacore_default",
        "driftlock": {"enabled": True, "check_interval": 25},
        "tags": ["testing", "example"],
        "price_rtc": 10,
    }


class TestTemplateValidator:
    """Tests for TemplateValidator."""

    def test_validate_valid_template(self, sample_template):
        from shaprai.marketplace.validator import TemplateValidator
        validator = TemplateValidator()
        result = validator.validate(sample_template)
        assert result.valid
        assert len(result.errors) == 0
        assert result.template_name == "test-template"
        assert result.template_version == "1.0.0"

    def test_validate_missing_required_field(self, sample_template):
        from shaprai.marketplace.validator import TemplateValidator
        validator = TemplateValidator()
        template = sample_template.copy()
        del template["name"]
        result = validator.validate(template)
        assert not result.valid
        assert any("name" in e for e in result.errors)

    def test_validate_invalid_version_format(self, sample_template):
        from shaprai.marketplace.validator import TemplateValidator
        validator = TemplateValidator()
        template = sample_template.copy()
        template["version"] = "1.0"
        result = validator.validate(template)
        assert not result.valid

    def test_validate_negative_price(self, sample_template):
        from shaprai.marketplace.validator import TemplateValidator
        validator = TemplateValidator()
        template = sample_template.copy()
        template["price_rtc"] = -5
        result = validator.validate(template)
        assert not result.valid


class TestPricing:
    """Tests for pricing and revenue split calculations."""

    def test_calculate_revenue_split_free(self):
        from shaprai.marketplace.pricing import calculate_revenue_split
        split = calculate_revenue_split(0)
        assert split.total_rtc == 0
        assert split.creator_rtc == 0

    def test_calculate_revenue_split_10_rtc(self):
        from shaprai.marketplace.pricing import calculate_revenue_split
        split = calculate_revenue_split(10)
        assert split.total_rtc == 10
        assert split.creator_rtc == 9.0
        assert split.protocol_rtc == 0.5
        assert split.relay_rtc == 0.5

    def test_calculate_revenue_split_negative_raises(self):
        from shaprai.marketplace.pricing import calculate_revenue_split
        with pytest.raises(ValueError, match="negative"):
            calculate_revenue_split(-1)


class TestMarketplaceRegistry:
    """Tests for MarketplaceRegistry."""

    def test_publish_template(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        published = registry.publish(sample_template, author="test-creator", price_rtc=10)
        assert published.name == "test-template"
        assert published.version == "1.0.0"

    def test_publish_duplicate_version_raises(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        with pytest.raises(ValueError, match="already exists"):
            registry.publish(sample_template, author="test-creator", price_rtc=15)

    def test_get_template(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        template = registry.get("test-template@1.0.0")
        assert template is not None
        assert template.name == "test-template"

    def test_search_templates(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        results = registry.search(query="test")
        assert len(results) == 1
        assert results[0].name == "test-template"

    def test_buy_template(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        purchase, template = registry.buy("test-template@1.0.0", buyer_wallet="buyer-001", relay_node="node-alpha")
        assert purchase.template_name == "test-template"
        assert purchase.price_rtc == 10
        assert purchase.creator_rtc == 9.0
        assert template.download_count == 1

    def test_buy_template_already_purchased(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        registry.buy("test-template@1.0.0", buyer_wallet="buyer-001")
        with pytest.raises(ValueError, match="Already purchased"):
            registry.buy("test-template@1.0.0", buyer_wallet="buyer-001")

    def test_preview_template(self, temp_db, sample_template):
        from shaprai.marketplace.registry import MarketplaceRegistry
        registry = MarketplaceRegistry(db_path=temp_db)
        registry.publish(sample_template, author="test-creator", price_rtc=10)
        preview = registry.preview("test-template@1.0.0")
        assert preview is not None
        assert preview["name"] == "test-template"
        assert preview["full_config_requires_purchase"] is True


class TestMarketplaceIntegration:
    """Integration tests for the full marketplace flow."""

    def test_full_workflow(self, temp_db, sample_template):
        from shaprai.marketplace import MarketplaceRegistry, TemplateValidator, calculate_revenue_split
        validator = TemplateValidator()
        result = validator.validate(sample_template)
        assert result.valid

        registry = MarketplaceRegistry(db_path=temp_db)
        published = registry.publish(sample_template, author="creator-001", price_rtc=25)
        assert published.name == "test-template"

        results = registry.search(query="test")
        assert len(results) == 1

        preview = registry.preview("test-template@1.0.0")
        assert preview["price_rtc"] == 25

        purchase, template = registry.buy("test-template@1.0.0", buyer_wallet="buyer-001", relay_node="node-alpha")
        split = calculate_revenue_split(25)
        assert purchase.creator_rtc == split.creator_rtc

        listing = registry.get_listing("test-template")
        assert listing.total_downloads == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])