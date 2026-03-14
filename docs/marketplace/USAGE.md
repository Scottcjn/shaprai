# ShaprAI Marketplace Usage Guide

This guide provides detailed instructions for using the ShaprAI Template Marketplace.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating Templates](#creating-templates)
3. [Publishing Templates](#publishing-templates)
4. [Searching and Discovering](#searching-and-discovering)
5. [Purchasing Templates](#purchasing-templates)
6. [Managing Your Templates](#managing-your-templates)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- ShaprAI installed (`pip install -e .`)
- RTC wallet configured (for purchases)
- Python 3.8+

### Quick Start

```bash
# Check marketplace status
shaprai marketplace --help

# View available commands
shaprai marketplace search --help
```

## Creating Templates

### Template Structure

A valid template must include:

```yaml
# Required fields
name: string          # Unique template identifier
version: string       # Semver format (e.g., 1.0.0)
author: string        # Your name or pseudonym
description: string   # Brief description (max 200 chars)

# Optional fields
tags: [string]        # Categories for discovery
price_rtc: integer    # Price in RTC (optional, set at publish time)

# Template content (varies by type)
personality:
  system_prompt: string
  temperature: float
  max_tokens: integer
```

### Example Templates

#### Personality Template

```yaml
name: professional-assistant
version: 1.0.0
author: Jane Doe
description: Professional business assistant with formal tone
tags:
  - personality
  - business
  - professional
personality:
  system_prompt: |
    You are a professional business assistant. 
    Maintain a formal, courteous tone in all interactions.
    Focus on clarity, accuracy, and efficiency.
  temperature: 0.5
  max_tokens: 2048
  top_p: 0.9
```

#### Agent Template

```yaml
name: research-agent
version: 2.1.0
author: Research Labs
description: Autonomous research agent with web browsing capabilities
tags:
  - agent
  - research
  - autonomous
agent:
  capabilities:
    - web_search
    - document_analysis
    - citation_generation
  tools:
    - browser
    - pdf_reader
    - citation_manager
  workflow:
    - understand_query
    - search_sources
    - analyze_results
    - generate_report
```

## Publishing Templates

### Step-by-Step Publishing

1. **Create your template file** (YAML or JSON)

2. **Validate before publishing**:
   ```bash
   # Validation happens automatically during publish
   # But you can test locally first
   python -c "from shaprai.marketplace.validator import TemplateValidator; print(TemplateValidator().validate_file('my_template.yaml'))"
   ```

3. **Publish with price**:
   ```bash
   shaprai marketplace publish \
     --template my_template.yaml \
     --price 25 \
     --author "Your Name"
   ```

4. **Verify publication**:
   ```bash
   shaprai marketplace search --author "Your Name"
   ```

### Publishing Tips

- **Version correctly**: Use semver (major.minor.patch)
  - `1.0.0` - Initial release
  - `1.0.1` - Bug fix
  - `1.1.0` - New feature
  - `2.0.0` - Breaking change

- **Price appropriately**: 
  - Simple templates: 5-15 RTC
  - Complex personalities: 15-50 RTC
  - Full agent configurations: 50-100 RTC

- **Use descriptive tags**: Helps users discover your templates

## Searching and Discovering

### Search Strategies

```bash
# By tag (most common)
shaprai marketplace search --tag personality
shaprai marketplace search --tag agent --tag research

# By author
shaprai marketplace search --author "Jane Doe"

# By keyword in description
shaprai marketplace search --query "business assistant"

# Combined filters
shaprai marketplace search --tag personality --author "Jane Doe" --sort downloads
```

### Sorting Options

| Sort Key | Description | Use Case |
|----------|-------------|----------|
| `downloads` | Most downloaded first | Find popular templates |
| `recent` | Newest first | Discover latest templates |
| `price` | Price ascending | Find budget options |

### Reading Search Results

```
Found 3 templates:

  📦 sophia-personality@1.2.3
     💰 15 RTC | 📥 1234 downloads
     📝 A friendly AI assistant with empathetic responses

  📦 professional-assistant@2.0.0
     💰 25 RTC | 📥 567 downloads
     📝 Professional business assistant with formal tone
```

## Purchasing Templates

### Purchase Flow

1. **Find a template**:
   ```bash
   shaprai marketplace search --tag personality
   ```

2. **Preview the template** (shown automatically):
   ```
   📦 sophia-personality@1.2.3
   💰 Price: 15 RTC
   👤 Author: Alice
   📝 Description: A friendly AI assistant...
   
   Preview (truncated):
   personality:
     system_prompt: |
       You are Sophia, a friendly...
   ```

3. **Confirm purchase**:
   ```bash
   shaprai marketplace buy --template sophia-personality@1.2.3
   ```

4. **Download completes**:
   ```
   ✅ Purchase successful!
   💳 Charged: 15 RTC
   📥 Template downloaded to: ~/.shaprai/templates/sophia-personality@1.2.3.yaml
   ```

### Revenue Distribution

When you purchase a template for 100 RTC:
- 90 RTC → Template creator
- 5 RTC → ShaprAI development fund
- 5 RTC → Relay node

## Managing Your Templates

### List Your Published Templates

```bash
# List all your templates
shaprai marketplace list --author me

# List with details
shaprai marketplace list --author me --verbose
```

### Update a Template

You cannot overwrite an existing version. Create a new version:

```bash
# Update your template file with new version
# version: 1.1.0

# Publish new version
shaprai marketplace publish --template my_template_v1.1.yaml --price 25
```

### Delete a Template

```bash
# Note: Deletion is permanent and cannot be undone
shaprai marketplace delete --template my-template@1.0.0
```

## Best Practices

### For Template Creators

1. **Write clear descriptions**: Help users understand what your template does
2. **Use appropriate tags**: 3-5 relevant tags improve discoverability
3. **Test before publishing**: Validate your template works as expected
4. **Version responsibly**: Follow semver conventions
5. **Price fairly**: Consider complexity and value provided
6. **Update regularly**: Fix bugs and improve based on feedback

### For Template Buyers

1. **Check download counts**: Popular templates are often more reliable
2. **Read descriptions carefully**: Ensure the template meets your needs
3. **Start with lower-priced templates**: Test before investing heavily
4. **Leave feedback**: Help improve the marketplace ecosystem
5. **Check version history**: Newer versions may have important fixes

## Troubleshooting

### Common Issues

#### "Template already exists"
```
Error: Template my-template@1.0.0 already exists
```
**Solution**: Increment the version number (e.g., to 1.0.1)

#### "Invalid semver version"
```
Error: Invalid semver version: 1.0
```
**Solution**: Use full semver format (e.g., 1.0.0)

#### "Validation failed"
```
Validation failed:
  ❌ Missing required field: name
  ❌ Missing required field: version
```
**Solution**: Add all required fields to your template

#### "Template not found"
```
Error: Template 'sophia-personality@1.2.3' not found
```
**Solution**: Check the template name and version, or search to verify it exists

#### "Insufficient RTC"
```
Error: Insufficient RTC balance
```
**Solution**: Add RTC to your wallet before purchasing

### Getting Help

```bash
# View help for any command
shaprai marketplace --help
shaprai marketplace publish --help
shaprai marketplace search --help

# Check marketplace status
shaprai marketplace status
```

## Additional Resources

- [API Reference](../shaprai/marketplace/README.md#api-usage)
- [Template Examples](examples/)
- [Revenue Split Details](REVENUE.md)
