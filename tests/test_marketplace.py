# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""Unit tests for marketplace module."""

import pytest
import tempfile
from pathlib import Path

from shaprai.marketplace.registry import TemplateRegistry, Template
from shaprai.marketplace.pricing import PricingEngine, calculate_purchase
from shaprai.marketplace.validator import TemplateValidator, validate_template


# ============== Registry Tests ==============

class TestTemplateRegistry:
    """Tests for TemplateRegistry."""

    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.registry = TemplateRegistry(db_path=Path(self.temp_db.name))

    def teardown_method(self):
        Path(self.temp_db.name).unlink(missing_ok=True)

    def test_publish_template(self):
        """Test publishing a template."""
        template = Template(
            name="test-agent",
            version="1.0.0",
            author="test-author",
            description="Test template",
            price_rtc=10,
            tags=["test", "agent"],
            content="name: test-agent\nversion: 1.0.0",
        )
        result = self.registry.publish(template)
        assert result is True

    def test_publish_duplicate_version_fails(self):
        """Test that publishing duplicate version fails."""
        template = Template(
            name="test-agent",
            version="1.0.0",
            author="test-author",
            description="Test template",
            price_rtc=10,
            tags=[],
            content="test",
        )
        self.registry.publish(template)
        
        with pytest.raises(ValueError, match="already exists"):
            self.registry.publish(template)

    def test_get_template(self):
        """Test retrieving a template."""
        template = Template(
            name="my-agent",
            version="2.0.0",
            author="author1",
            description="Description",
            price_rtc=25,
            tags=["ai"],
            content="content",
        )
        self.registry.publish(template)
        
        result = self.registry.get("my-agent", "2.0.0")
        assert result is not None
        assert result.name == "my-agent"
        assert result.version == "2.0.0"
        assert result.price_rtc == 25

    def test_get_latest_template(self):
        """Test getting latest version."""
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            template = Template(
                name="evolving-agent",
                version=v,
                author="author",
                description=f"Version {v}",
                price_rtc=10,
                tags=[],
                content=f"version: {v}",
            )
            self.registry.publish(template)
        
        latest = self.registry.get_latest("evolving-agent")
        assert latest.version == "2.0.0"

    def test_search_by_tag(self):
        """Test searching by tag."""
        template1 = Template(
            name="agent1", version="1.0.0", author="a",
            description="", price_rtc=10, tags=["nlp", "chat"], content="",
        )
        template2 = Template(
            name="agent2", version="1.0.0", author="a",
            description="", price_rtc=10, tags=["vision"], content="",
        )
        self.registry.publish(template1)
        self.registry.publish(template2)
        
        results = self.registry.search(tag="nlp")
        assert len(results) == 1
        assert results[0].name == "agent1"

    def test_search_by_author(self):
        """Test searching by author."""
        template1 = Template(
            name="agent1", version="1.0.0", author="alice",
            description="", price_rtc=10, tags=[], content="",
        )
        template2 = Template(
            name="agent2", version="1.0.0", author="bob",
            description="", price_rtc=10, tags=[], content="",
        )
        self.registry.publish(template1)
        self.registry.publish(template2)
        
        results = self.registry.search(author="alice")
        assert len(results) == 1
        assert results[0].author == "alice"

    def test_increment_downloads(self):
        """Test incrementing download count."""
        template = Template(
            name="popular", version="1.0.0", author="a",
            description="", price_rtc=10, tags=[], content="",
        )
        self.registry.publish(template)
        
        self.registry.increment_downloads("popular", "1.0.0")
        self.registry.increment_downloads("popular", "1.0.0")
        
        result = self.registry.get("popular", "1.0.0")
        assert result.download_count == 2


# ============== Pricing Tests ==============

class TestPricingEngine:
    """Tests for PricingEngine."""

    def test_calculate_split(self):
        """Test revenue split calculation."""
        engine = PricingEngine()
        split = engine.calculate_split(100, "test", "1.0.0")
        
        assert split.total_rtc == 100
        assert split.creator_amount == 90  # 90%
        assert split.protocol_amount == 5   # 5%
        assert split.relay_amount == 5      # 5%

    def test_calculate_split_uneven(self):
        """Test split with uneven amounts."""
        engine = PricingEngine()
        split = engine.calculate_split(37, "test", "1.0.0")
        
        # 37 * 0.90 = 33.3 -> 33
        # 37 * 0.05 = 1.85 -> 1
        # Remainder goes to relay: 37 - 33 - 1 = 3
        assert split.creator_amount == 33
        assert split.protocol_amount == 1
        assert split.relay_amount == 3
        assert split.total_rtc == 37

    def test_validate_price_positive(self):
        """Test validating positive price."""
        engine = PricingEngine()
        assert engine.validate_price(0) is True
        assert engine.validate_price(100) is True
        assert engine.validate_price(10000) is True

    def test_validate_price_negative_fails(self):
        """Test that negative price fails."""
        engine = PricingEngine()
        with pytest.raises(ValueError, match="cannot be negative"):
            engine.validate_price(-1)

    def test_validate_price_too_high_fails(self):
        """Test that too high price fails."""
        engine = PricingEngine()
        with pytest.raises(ValueError, match="cannot exceed"):
            engine.validate_price(100001)

    def test_calculate_purchase_convenience(self):
        """Test convenience function."""
        result = calculate_purchase(100, "agent", "1.0.0")
        assert result["total_rtc"] == 100
        assert result["creator"]["amount"] == 90
        assert result["protocol"]["amount"] == 5
        assert result["relay"]["amount"] == 5


# ============== Validator Tests ==============

class TestTemplateValidator:
    """Tests for TemplateValidator."""

    def test_validate_valid_template_yaml(self):
        """Test validating valid YAML template."""
        content = """
name: my-agent
version: 1.0.0
author: test-author
model:
  base: gpt-4
capabilities:
  - chat
  - code
description: A test agent
tags:
  - ai
  - assistant
"""
        validator = TemplateValidator()
        result = validator.validate(content)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_valid_template_json(self):
        """Test validating valid JSON template."""
        content = '{"name": "agent", "version": "1.0.0", "author": "test", "model": {"base": "gpt-4"}, "capabilities": ["chat"]}'
        validator = TemplateValidator()
        result = validator.validate(content)
        assert result.is_valid is True

    def test_validate_missing_required_field(self):
        """Test that missing required field fails."""
        content = "name: agent\nversion: 1.0.0"
        validator = TemplateValidator()
        result = validator.validate(content)
        assert result.is_valid is False
        assert any("author" in e for e in result.errors)
        assert any("model" in e for e in result.errors)
        assert any("capabilities" in e for e in result.errors)

    def test_validate_invalid_semver(self):
        """Test that invalid semver fails."""
        content = "name: agent\nversion: not-a-version\nauthor: test\nmodel: {}\ncapabilities: []"
        validator = TemplateValidator()
        result = validator.validate(content)
        assert result.is_valid is False
        assert any("semver" in e.lower() for e in result.errors)

    def test_validate_invalid_yaml(self):
        """Test that invalid YAML fails."""
        content = "name: [unclosed\nversion: 1.0.0"
        validator = TemplateValidator()
        result = validator.validate(content)
        assert result.is_valid is False

    def test_validate_template_convenience(self):
        """Test convenience function."""
        content = "name: a\nversion: 1.0.0\nauthor: b\nmodel: {}\ncapabilities: []"
        is_valid, errors, warnings = validate_template(content)
        assert is_valid is True
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
