"""Unit tests for Template Marketplace."""

import json
import tempfile
from pathlib import Path

import pytest

from shaprai.marketplace.registry import TemplateRegistry, Template
from shaprai.marketplace.pricing import PricingEngine, RevenueSplit
from shaprai.marketplace.validator import TemplateValidator, ValidationError


class TestTemplateRegistry:
    """Tests for template registry."""

    @pytest.fixture
    def registry(self):
        """Create a temporary registry."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        reg = TemplateRegistry(db_path=db_path)
        yield reg

        # Cleanup
        db_path.unlink(missing_ok=True)

    def test_initialization(self):
        """Test registry initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            reg = TemplateRegistry(db_path=db_path)
            assert reg.db_path == db_path
            assert db_path.exists()
        finally:
            db_path.unlink(missing_ok=True)

    def test_publish_template(self, registry):
        """Test publishing a template."""
        template = registry.publish(
            name="TestTemplate",
            description="A test template",
            author="test_author",
            version="1.0.0",
            tags=["test", "example"],
            price_rtc=10.0,
            content="name: Test\ntraits:\n  - helpful"
        )

        assert template.name == "TestTemplate"
        assert template.version == "1.0.0"
        assert template.price_rtc == 10.0
        assert template.author == "test_author"
        assert "test" in template.tags

    def test_version_conflict(self, registry):
        """Test that duplicate versions are rejected."""
        registry.publish(
            name="UniqueTemplate",
            description="Test",
            author="test",
            version="1.0.0",
            tags=[],
            price_rtc=5.0,
            content="test"
        )

        with pytest.raises(ValueError) as exc_info:
            registry.publish(
                name="UniqueTemplate",
                description="Test",
                author="test",
                version="1.0.0",
                tags=[],
                price_rtc=5.0,
                content="test"
            )

        assert "already exists" in str(exc_info.value)

    def test_get_template(self, registry):
        """Test retrieving a template."""
        published = registry.publish(
            name="GetTest",
            description="Test get",
            author="test",
            version="1.0.0",
            tags=["test"],
            price_rtc=1.0,
            content="content"
        )

        retrieved = registry.get(published.id)

        assert retrieved is not None
        assert retrieved.name == "GetTest"
        assert retrieved.content is None  # Default: no content

    def test_get_with_content(self, registry):
        """Test retrieving template with content."""
        published = registry.publish(
            name="ContentTest",
            description="Test",
            author="test",
            version="1.0.0",
            tags=[],
            price_rtc=1.0,
            content="full content here"
        )

        retrieved = registry.get(published.id, include_content=True)
        assert retrieved.content == "full content here"

    def test_search_templates(self, registry):
        """Test searching templates."""
        # Publish multiple templates
        registry.publish(
            name="PythonAgent",
            description="A Python coding agent",
            author="coder",
            version="1.0.0",
            tags=["python", "coding"],
            price_rtc=5.0,
            content="python template"
        )

        registry.publish(
            name="WriterAgent",
            description="A creative writing agent",
            author="writer",
            version="1.0.0",
            tags=["writing", "creative"],
            price_rtc=3.0,
            content="writer template"
        )

        # Search
        results = registry.search(query="python")
        assert len(results) == 1
        assert results[0].name == "PythonAgent"

    def test_search_by_tag(self, registry):
        """Test searching by tag."""
        registry.publish(
            name="Tagged",
            description="Test",
            author="test",
            version="1.0.0",
            tags=["special"],
            price_rtc=1.0,
            content="test"
        )

        results = registry.search(tag="special")
        assert len(results) == 1

    def test_search_by_author(self, registry):
        """Test searching by author."""
        registry.publish(
            name="AuthorTest",
            description="Test",
            author="specific_author",
            version="1.0.0",
            tags=[],
            price_rtc=1.0,
            content="test"
        )

        results = registry.list_by_author("specific_author")
        assert len(results) == 1
        assert results[0].author == "specific_author"

    def test_increment_downloads(self, registry):
        """Test download counter."""
        template = registry.publish(
            name="DownloadTest",
            description="Test",
            author="test",
            version="1.0.0",
            tags=[],
            price_rtc=1.0,
            content="test"
        )

        assert template.download_count == 0

        registry.increment_downloads(template.id)
        registry.increment_downloads(template.id)

        retrieved = registry.get(template.id)
        assert retrieved.download_count == 2

    def test_get_versions(self, registry):
        """Test getting all versions of a template."""
        registry.publish(
            name="Versioned",
            description="V1",
            author="test",
            version="1.0.0",
            tags=[],
            price_rtc=1.0,
            content="v1"
        )

        registry.publish(
            name="Versioned",
            description="V2",
            author="test",
            version="2.0.0",
            tags=[],
            price_rtc=2.0,
            content="v2"
        )

        versions = registry.get_versions("Versioned")
        assert len(versions) == 2

    def test_delete_template(self, registry):
        """Test deleting a template."""
        template = registry.publish(
            name="ToDelete",
            description="Test",
            author="test",
            version="1.0.0",
            tags=[],
            price_rtc=1.0,
            content="test"
        )

        result = registry.delete(template.id)
        assert result is True

        retrieved = registry.get(template.id)
        assert retrieved is None

    def test_stats(self, registry):
        """Test marketplace statistics."""
        registry.publish(
            name="Stat1",
            description="Test",
            author="author1",
            version="1.0.0",
            tags=[],
            price_rtc=5.0,
            content="test"
        )

        registry.publish(
            name="Stat2",
            description="Test",
            author="author2",
            version="1.0.0",
            tags=[],
            price_rtc=15.0,
            content="test"
        )

        stats = registry.get_stats()
        assert stats["total_templates"] == 2
        assert stats["unique_authors"] == 2
        assert stats["average_price_rtc"] == 10.0


class TestPricingEngine:
    """Tests for pricing engine."""

    @pytest.fixture
    def engine(self):
        """Create pricing engine."""
        return PricingEngine()

    def test_revenue_split(self, engine):
        """Test revenue split calculation."""
        split = engine.calculate_revenue_split(100.0)

        assert split.creator == 90.0
        assert split.protocol == 5.0
        assert split.relay == 5.0
        assert split.total == 100.0

    def test_validate_price(self, engine):
        """Test price validation."""
        assert engine.validate_price(10.0) is True
        assert engine.validate_price(0.0) is True
        assert engine.validate_price(-5.0) is False

    def test_estimate_earnings(self, engine):
        """Test earnings estimation."""
        estimate = engine.estimate_creator_earnings(10.0, 100)

        assert estimate["price_per_sale"] == 10.0
        assert estimate["creator_share_per_sale"] == 9.0
        assert estimate["estimated_sales"] == 100
        assert estimate["estimated_total_earnings"] == 900.0

    def test_format_price(self, engine):
        """Test price formatting."""
        assert engine.format_price(0) == "Free"
        assert engine.format_price(1.5) == "1.5000 RTC"
        assert engine.format_price(0.001) == "0.0010 RTC"

    def test_compare_prices(self, engine):
        """Test price comparison."""
        comparison = engine.compare_prices(10.0, 20.0)

        assert comparison["price_1"]["price"] == 10.0
        assert comparison["price_2"]["price"] == 20.0
        assert comparison["difference"]["price"] == 10.0


class TestTemplateValidator:
    """Tests for template validator."""

    @pytest.fixture
    def validator(self):
        """Create validator."""
        return TemplateValidator()

    def test_valid_yaml_template(self, validator):
        """Test validating valid YAML."""
        content = """
name: TestAgent
description: A test agent
traits:
  - helpful
  - friendly
values:
  - honesty
"""
        is_valid, errors = validator.validate(content, "yaml")

        assert is_valid is True
        assert len(errors) == 0

    def test_valid_json_template(self, validator):
        """Test validating valid JSON."""
        content = json.dumps({
            "name": "TestAgent",
            "description": "A test agent",
            "traits": ["helpful"],
            "values": ["honesty"]
        })

        is_valid, errors = validator.validate(content, "json")

        assert is_valid is True

    def test_missing_required_field(self, validator):
        """Test validation with missing required field."""
        content = """
description: Missing name
traits:
  - helpful
"""
        is_valid, errors = validator.validate(content, "yaml")

        assert is_valid is False
        assert any(e.field == "name" for e in errors)

    def test_short_description_warning(self, validator):
        """Test short description warning."""
        content = """
name: Test
description: Short
"""
        is_valid, errors = validator.validate(content, "yaml")

        # Should have warning but still be valid
        assert any(e.severity == "warning" for e in errors)

    def test_invalid_json(self, validator):
        """Test invalid JSON handling."""
        content = "{ invalid json }"

        is_valid, errors = validator.validate(content, "json")

        assert is_valid is False
        assert any("parse" in e.message.lower() for e in errors)

    def test_forbidden_patterns(self, validator):
        """Test detection of forbidden patterns."""
        content = json.dumps({
            "name": "BadTemplate",
            "description": "Has api_key: secret123",
            "api_key": "should_not_be_here"
        })

        is_valid, errors = validator.validate(content, "json")

        assert is_valid is False
        assert any("api" in e.message.lower() for e in errors)

    def test_detect_format(self, validator):
        """Test format auto-detection."""
        yaml_content = "name: test\ndescription: test"
        json_content = '{"name": "test", "description": "test"}'

        assert validator._detect_format(yaml_content) == "yaml"
        assert validator._detect_format(json_content) == "json"

    def test_validation_summary(self, validator):
        """Test getting validation summary."""
        summary = validator.get_validation_summary()

        assert "required_fields" in summary
        assert "recommended_fields" in summary
        assert "supported_formats" in summary
        assert "yaml" in summary["supported_formats"]