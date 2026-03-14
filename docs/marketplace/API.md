# ShaprAI Marketplace API Reference

Complete API reference for the ShaprAI Template Marketplace module.

## Module Structure

```
shaprai/marketplace/
├── __init__.py       # Package exports
├── registry.py       # Template registry (CRUD, search)
├── pricing.py        # RTC pricing and revenue split
├── validator.py      # Template schema validation
└── cli.py            # Command-line interface
```

## Quick Start

```python
from shaprai.marketplace.registry import TemplateRegistry, Template
from shaprai.marketplace.pricing import calculate_purchase
from shaprai.marketplace.validator import validate_template

# Initialize registry
registry = TemplateRegistry()

# Validate a template
result = validate_template("my_template.yaml")
if not result.is_valid:
    print("Validation failed:", result.errors)
    exit(1)

# Create and publish a template
template = Template(
    name="my-agent",
    version="1.0.0",
    author="Your Name",
    description="My custom agent",
    price_rtc=10,
    tags=["custom", "agent"],
    content=yaml_content,
)
registry.publish(template)

# Search for templates
templates = registry.search(tag="personality", sort="downloads", limit=10)

# Calculate purchase
purchase = calculate_purchase(100, "sophia-personality", "1.2.3")
print(f"Creator gets: {purchase['creator']['amount']} RTC")
```

## Registry API

### Template Dataclass

```python
from shaprai.marketplace.registry import Template

template = Template(
    name: str,              # Unique template identifier
    version: str,           # Semver format (e.g., "1.0.0")
    author: str,            # Author name
    description: str,       # Brief description
    price_rtc: int,         # Price in RTC tokens
    tags: List[str],        # Category tags
    content: str,           # Full template content (YAML/JSON)
    download_count: int = 0,  # Auto-tracked
    created_at: str = None,   # Auto-generated ISO timestamp
    updated_at: str = None,   # Auto-generated ISO timestamp
)
```

### TemplateRegistry Methods

#### `publish(template: Template) -> bool`

Publish a new template version.

```python
try:
    registry.publish(template)
except ValueError as e:
    print(f"Publish failed: {e}")
```

**Exceptions**:
- `ValueError`: If version already exists or semver is invalid

#### `get(name: str, version: str) -> Optional[Template]`

Get a specific template version.

```python
template = registry.get("sophia-personality", "1.2.3")
```

#### `get_latest(name: str) -> Optional[Template]`

Get the latest version of a template.

```python
latest = registry.get_latest("sophia-personality")
```

#### `search(...) -> List[Template]`

Search templates with filters.

```python
templates = registry.search(
    tag="personality",
    author="Jane Doe",
    query="business assistant",
    sort="downloads",  # or "recent", "price"
    limit=20
)
```

#### `list_by_author(author: str) -> List[Template]`

List all templates by an author.

```python
templates = registry.list_by_author("Jane Doe")
```

#### `increment_download(name: str, version: str) -> None`

Increment download count (called automatically on purchase).

#### `delete(name: str, version: str) -> bool`

Delete a template version.

## Pricing API

### RevenueSplit Dataclass

```python
from shaprai.marketplace.pricing import RevenueSplit

split = RevenueSplit(
    creator_amount: int,    # 90% of total
    protocol_amount: int,   # 5% of total
    relay_amount: int,      # 5% of total
    total_rtc: int,         # Total price
    template_name: str,
    template_version: str,
    buyer_id: str = None,
)
```

### PricingEngine Methods

#### `calculate_split(price_rtc, template_name, template_version) -> RevenueSplit`

Calculate revenue distribution.

```python
engine = PricingEngine()
split = engine.calculate_split(100, "sophia-personality", "1.2.3")
print(f"Creator: {split.creator_amount} RTC")  # 90
```

#### `validate_price(price_rtc: int) -> bool`

Validate a template price (0 to 100,000 RTC).

#### `format_rtc(amount: int) -> str`

Format RTC amount for display.

### Convenience Function

```python
from shaprai.marketplace.pricing import calculate_purchase

purchase = calculate_purchase(100, "sophia-personality", "1.2.3")
# Returns dict with total_rtc, creator, protocol, relay amounts
```

## Validator API

### ValidationResult Dataclass

```python
from shaprai.marketplace.validator import ValidationResult

result = ValidationResult(
    is_valid: bool,
    errors: List[str],
    warnings: List[str],
)
```

### TemplateValidator Methods

#### `validate_file(file_path: Path) -> ValidationResult`

Validate a template file.

```python
validator = TemplateValidator()
result = validator.validate_file(Path("my_template.yaml"))
if result.is_valid:
    print("✅ Valid")
else:
    for error in result.errors:
        print(f"❌ {error}")
```

#### `validate_content(content: str, file_type: str) -> ValidationResult`

Validate template content directly.

#### `validate_template_dict(data: dict) -> ValidationResult`

Validate a parsed template dictionary.

### Schema Requirements

**Required Fields**:
- `name`: Non-empty string, alphanumeric with hyphens
- `version`: Valid semver format
- `author`: Non-empty string
- `description`: Non-empty string, max 200 characters

**Optional Fields**:
- `tags`: List of strings
- `personality`: Personality configuration
- `agent`: Agent configuration

## Testing

```python
import pytest
from shaprai.marketplace.registry import TemplateRegistry, Template

def test_publish_and_search():
    registry = TemplateRegistry(db_path=":memory:")
    
    template = Template(
        name="test-template",
        version="1.0.0",
        author="Test",
        description="Test",
        price_rtc=10,
        tags=["test"],
        content="test"
    )
    
    registry.publish(template)
    results = registry.search(tag="test")
    
    assert len(results) == 1
```

Run tests:
```bash
pytest tests/test_marketplace.py -v
```
