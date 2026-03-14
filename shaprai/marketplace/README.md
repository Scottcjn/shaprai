# ShaprAI Template Marketplace

The ShaprAI Template Marketplace enables creators to publish, version, and sell agent personality templates priced in RTC tokens.

## Features

- **Template Registry**: SQLite-backed storage with full CRUD operations
- **Semantic Versioning**: All templates use semver (e.g., `sophia-personality@1.2.3`)
- **RTC Pricing**: Built-in pricing engine with 90/5/5 revenue split
- **Template Validation**: Schema validation before publishing
- **CLI Interface**: Easy-to-use commands for all marketplace operations

## Revenue Split

| Recipient | Share | Purpose |
|-----------|-------|---------|
| Creator | 90% | Template author |
| Protocol | 5% | ShaprAI development fund |
| Relay | 5% | Node that facilitated the transaction |

## Installation

The marketplace module is included with ShaprAI. Ensure you have the latest version:

```bash
pip install -e .
```

## CLI Commands

### Publish a Template

Publish a template to the marketplace with a specified RTC price:

```bash
shaprai marketplace publish --template my_agent.yaml --price 10
```

Options:
- `-t, --template`: Path to template file (YAML/JSON) [required]
- `-p, --price`: Price in RTC [required]
- `-a, --author`: Author name (defaults to 'anonymous')

### Search Templates

Search for templates in the marketplace:

```bash
shaprai marketplace search --tag personality --sort downloads
```

Options:
- `-t, --tag`: Filter by tag
- `-a, --author`: Filter by author
- `-q, --query`: Search query
- `-s, --sort`: Sort by (downloads, recent, price)
- `-l, --limit`: Maximum results (default: 20)

### Buy a Template

Purchase a template from the marketplace:

```bash
shaprai marketplace buy --template sophia-personality@1.2.3
```

Options:
- `-t, --template`: Template name with version (e.g., `sophia-personality@1.2.3`)

### List Your Templates

List all templates published by you:

```bash
shaprai marketplace list --author me
```

## Template Format

Templates should be YAML or JSON files with the following structure:

```yaml
name: sophia-personality
version: 1.2.3
author: Your Name
description: A friendly AI assistant personality
tags:
  - personality
  - assistant
  - friendly
personality:
  system_prompt: |
    You are Sophia, a friendly and helpful AI assistant...
  temperature: 0.7
  max_tokens: 2048
```

## API Usage

### Registry

```python
from shaprai.marketplace.registry import TemplateRegistry, Template

registry = TemplateRegistry()

# Create a template
template = Template(
    name="my-agent",
    version="1.0.0",
    author="Your Name",
    description="My custom agent",
    price_rtc=10,
    tags=["custom", "agent"],
    content=yaml_content,
)

# Publish
registry.publish(template)

# Search
templates = registry.search(tag="personality", sort="downloads", limit=10)

# Get specific version
template = registry.get("sophia-personality", "1.2.3")

# Get latest version
template = registry.get_latest("sophia-personality")
```

### Pricing

```python
from shaprai.marketplace.pricing import PricingEngine, calculate_purchase

engine = PricingEngine()

# Calculate revenue split
split = engine.calculate_split(
    price_rtc=100,
    template_name="sophia-personality",
    template_version="1.2.3"
)

print(f"Creator gets: {split.creator_amount} RTC")  # 90 RTC
print(f"Protocol gets: {split.protocol_amount} RTC")  # 5 RTC
print(f"Relay gets: {split.relay_amount} RTC")  # 5 RTC

# Or use convenience function
purchase = calculate_purchase(100, "sophia-personality", "1.2.3")
```

### Validator

```python
from shaprai.marketplace.validator import TemplateValidator

validator = TemplateValidator()
result = validator.validate_file("my_template.yaml")

if result.is_valid:
    print("Template is valid!")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

## Database Location

The marketplace uses SQLite for storage. The database is located at:

```
~/.shaprai/marketplace.db
```

## Examples

### Example 1: Publish a Personality Template

```bash
# Create template file
cat > sophia.yaml << 'EOF'
name: sophia-personality
version: 1.0.0
author: Alice
description: A friendly AI assistant with empathetic responses
tags:
  - personality
  - assistant
  - empathetic
personality:
  system_prompt: |
    You are Sophia, a warm and empathetic AI assistant...
EOF

# Publish for 15 RTC
shaprai marketplace publish --template sophia.yaml --price 15
```

### Example 2: Search for Templates

```bash
# Find all personality templates, sorted by popularity
shaprai marketplace search --tag personality --sort downloads

# Find templates by a specific author
shaprai marketplace search --author Alice

# Search by keyword
shaprai marketplace search --query "helpful assistant"
```

### Example 3: Purchase a Template

```bash
# Buy the latest version
shaprai marketplace buy --template sophia-personality

# Buy a specific version
shaprai marketplace buy --template sophia-personality@1.0.0
```

## Testing

Run the marketplace test suite:

```bash
pytest tests/test_marketplace.py -v
```

## License

MIT License - Copyright (c) 2026 Elyan Labs
