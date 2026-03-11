# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""Marketplace CLI commands for ShaprAI."""

import click
import yaml
import json
from pathlib import Path
from typing import Optional

from .registry import TemplateRegistry, Template
from .pricing import PricingEngine, calculate_purchase
from .validator import TemplateValidator, validate_template


@click.group()
def marketplace():
    """Template marketplace commands."""
    pass


@marketplace.command()
@click.option("--template", "-t", required=True, help="Path to template file (YAML/JSON)")
@click.option("--price", "-p", required=True, type=int, help="Price in RTC")
@click.option("--author", "-a", default=None, help="Author name (defaults to 'anonymous')")
def publish(template: str, price: int, author: Optional[str]):
    """Publish a template to the marketplace.
    
    Example:
        shaprai marketplace publish --template my_agent.yaml --price 10
    """
    template_path = Path(template)
    if not template_path.exists():
        click.echo(f"Error: Template file not found: {template}", err=True)
        return 1

    # Validate the template
    validator = TemplateValidator()
    result = validator.validate_file(template_path)
    
    if not result.is_valid:
        click.echo("Validation failed:", err=True)
        for error in result.errors:
            click.echo(f"  ❌ {error}", err=True)
        return 1
    
    if result.warnings:
        click.echo("Warnings:")
        for warning in result.warnings:
            click.echo(f"  ⚠️  {warning}")

    # Load template content
    content = template_path.read_text()
    if content.strip().startswith("{"):
        template_data = json.loads(content)
    else:
        template_data = yaml.safe_load(content)

    # Validate price
    pricing_engine = PricingEngine()
    try:
        pricing_engine.validate_price(price)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        return 1

    # Create template object
    tmpl = Template(
        name=template_data.get("name", template_path.stem),
        version=template_data.get("version", "1.0.0"),
        author=author or template_data.get("author", "anonymous"),
        description=template_data.get("description", ""),
        price_rtc=price,
        tags=template_data.get("tags", []),
        content=content,
    )

    # Publish to registry
    registry = TemplateRegistry()
    try:
        registry.publish(tmpl)
        click.echo(f"✅ Published {tmpl.name}@{tmpl.version} for {price} RTC")
        click.echo(f"   Author: {tmpl.author}")
        if tmpl.tags:
            click.echo(f"   Tags: {', '.join(tmpl.tags)}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        return 1


@marketplace.command()
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--author", "-a", default=None, help="Filter by author")
@click.option("--query", "-q", default=None, help="Search query")
@click.option("--sort", "-s", default="downloads", type=click.Choice(["downloads", "recent", "price"]), help="Sort by")
@click.option("--limit", "-l", default=20, help="Maximum results")
def search(tag: Optional[str], author: Optional[str], query: Optional[str], sort: str, limit: int):
    """Search templates in the marketplace.
    
    Example:
        shaprai marketplace search --tag personality --sort downloads
    """
    registry = TemplateRegistry()
    templates = registry.search(tag=tag, author=author, query=query, sort=sort, limit=limit)
    
    if not templates:
        click.echo("No templates found.")
        return
    
    click.echo(f"Found {len(templates)} templates:\n")
    for tmpl in templates:
        click.echo(f"  📦 {tmpl.name}@{tmpl.version}")
        click.echo(f"     💰 {tmpl.price_rtc} RTC | 📥 {tmpl.download_count} downloads")
        if tmpl.description:
            desc = tmpl.description[:60] + "..." if len(tmpl.description) > 60 else tmpl.description
            click.echo(f"     📝 {desc}")
        click.echo()


@marketplace.command()
@click.option("--template", "-t", required=True, help="Template name with version (e.g., sophia-personality@1.2.3)")
def buy(template: str):
    """Buy a template from the marketplace.
    
    Example:
        shaprai marketplace buy --template sophia-personality@1.2.3
    """
    # Parse template name and version
    if "@" in template:
        name, version = template.rsplit("@", 1)
    else:
        name = template
        version = None
    
    registry = TemplateRegistry()
    
    # Get template
    if version:
        tmpl = registry.get(name, version)
    else:
        tmpl = registry.get_latest(name)
    
    if not tmpl:
        click.echo(f"Error: Template '{template}' not found.", err=True)
        return 1
    
    # Show preview (truncated)
    click.echo(f"📦 {tmpl.name}@{tmpl.version}")
    click.echo(f"💰 Price: {tmpl.price_rtc} RTC")
    click.echo(f"👤 Author: {tmpl.author}")
    if tmpl.description:
        click.echo(f"📝 {tmpl.description}")
    click.echo()
    
    # Calculate revenue split
    split = calculate_purchase(tmpl.price_rtc, tmpl.name, tmpl.version)
    click.echo("Revenue split:")
    click.echo(f"  👤 Creator: {split['creator']['amount']} RTC (90%)")
    click.echo(f"  🏛️  Protocol: {split['protocol']['amount']} RTC (5%)")
    click.echo(f"  📡 Relay: {split['relay']['amount']} RTC (5%)")
    click.echo()
    
    # Increment download count
    registry.increment_downloads(tmpl.name, tmpl.version)
    
    # In a real implementation, this would transfer RTC tokens
    click.echo("✅ Purchase recorded! (RTC transfer would happen here)")
    click.echo(f"\nTemplate content preview (first 500 chars):")
    click.echo("-" * 40)
    click.echo(tmpl.content[:500] + "..." if len(tmpl.content) > 500 else tmpl.content)


@marketplace.command()
@click.option("--author", "-a", default=None, help="Filter by author")
def list(author: Optional[str]):
    """List templates (optionally by author).
    
    Example:
        shaprai marketplace list --author me
    """
    registry = TemplateRegistry()
    
    if author:
        templates = registry.list_by_author(author)
    else:
        templates = registry.search(limit=50)
    
    if not templates:
        click.echo("No templates found.")
        return
    
    click.echo(f"\n📚 {len(templates)} templates:\n")
    for tmpl in templates:
        click.echo(f"  📦 {tmpl.name}@{tmpl.version} - {tmpl.price_rtc} RTC")
        click.echo(f"     👤 {tmpl.author} | 📥 {tmpl.download_count} downloads")
        if tmpl.tags:
            click.echo(f"     🏷️  {', '.join(tmpl.tags)}")
        click.echo()
