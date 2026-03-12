# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""ShaprAI CLI -- Agent lifecycle management from the command line."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from shaprai import __version__
from shaprai.prerequisites import require_elyan_ecosystem
from shaprai.core.lifecycle import AgentState, create_agent, deploy_agent, get_agent_status
from shaprai.core.fleet_manager import FleetManager
from shaprai.core.template_engine import list_templates, load_template, fork_template
from shaprai.sanctuary.educator import SanctuaryEducator
from shaprai.sanctuary.quality_gate import QualityGate, ELYAN_CLASS_THRESHOLD


SHAPRAI_HOME = Path.home() / ".shaprai"
AGENTS_DIR = SHAPRAI_HOME / "agents"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _ensure_dirs() -> None:
    """Create ShaprAI home directories if they don't exist."""
    SHAPRAI_HOME.mkdir(parents=True, exist_ok=True)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)


@click.group()
@click.version_option(version=__version__, prog_name="shaprai")
@click.option("--skip-checks", is_flag=True, hidden=True, help="Skip prerequisite checks (dev only)")
def main(skip_checks: bool = False) -> None:
    """ShaprAI -- Sharpen raw models into Elyan-class agents.

    REQUIRES: beacon-skill, grazer-skill, atlas, RustChain.
    These are not optional. An agent without the full Elyan
    ecosystem is not an Elyan-class agent.
    """
    _ensure_dirs()
    if not skip_checks:
        require_elyan_ecosystem()


# --------------------------------------------------------------------------- #
#  shaprai create
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
@click.option("--template", "-t", default="bounty_hunter", help="Template name or path")
@click.option("--model", "-m", default=None, help="HuggingFace model ID override")
def create(name: str, template: str, model: Optional[str]) -> None:
    """Create a new agent from a template.

    Automatically registers with all Elyan systems:
    - RustChain wallet (identity)
    - Beacon registration (discovery)
    - Atlas node placement (visualization)
    - Grazer platform binding (engagement)
    """
    from shaprai.elyan_bus import ElyanBus

    # Resolve template path
    template_path = TEMPLATES_DIR / f"{template}.yaml"
    if not template_path.exists():
        template_path = Path(template)
    if not template_path.exists():
        click.echo(f"Error: Template '{template}' not found.", err=True)
        sys.exit(1)

    tmpl = load_template(str(template_path))
    if model:
        tmpl.model["base"] = model

    agent = create_agent(name, tmpl, agents_dir=AGENTS_DIR)

    # Onboard through the Elyan Bus — ALL four systems
    bus = ElyanBus()
    click.echo(f"Onboarding '{name}' across Elyan ecosystem...")
    elyan_agent = bus.onboard_agent(
        agent_name=name,
        capabilities=tmpl.capabilities,
        platforms=tmpl.platforms,
        description=tmpl.description or f"ShaprAI agent from {tmpl.name} template",
    )

    click.echo(f"Agent '{name}' created from template '{tmpl.name}'")
    click.echo(f"  Model:    {tmpl.model.get('base', 'unset')}")
    click.echo(f"  State:    {agent['state']}")
    click.echo(f"  Wallet:   {elyan_agent.wallet_id}")
    click.echo(f"  Beacon:   {elyan_agent.beacon_id}")
    click.echo(f"  Atlas:    {elyan_agent.atlas_node_id}")
    click.echo(f"  Platforms: {', '.join(elyan_agent.grazer_platforms)}")
    click.echo(f"  Path:     {AGENTS_DIR / name}")


# --------------------------------------------------------------------------- #
#  shaprai train
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
@click.option(
    "--phase",
    "-p",
    type=click.Choice(["sft", "dpo", "driftlock"]),
    required=True,
    help="Training phase",
)
@click.option("--data", "-d", default=None, help="Path to training data")
@click.option("--epochs", "-e", default=3, type=int, help="Number of epochs")
def train(name: str, phase: str, data: Optional[str], epochs: int) -> None:
    """Train an agent through a specific phase."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found. Run 'shaprai create' first.", err=True)
        sys.exit(1)

    click.echo(f"Training '{name}' -- phase: {phase}, epochs: {epochs}")

    if phase == "sft":
        from shaprai.training.sft import SFTTrainer as Trainer

        trainer = Trainer(agent_dir)
        trainer.train(data_path=data, epochs=epochs)
    elif phase == "dpo":
        from shaprai.training.dpo import DPOTrainer as Trainer

        trainer = Trainer(agent_dir)
        trainer.train(pairs_path=data, epochs=epochs)
    elif phase == "driftlock":
        from shaprai.training.driftlock import DriftLockEvaluator

        evaluator = DriftLockEvaluator(agent_dir)
        report = evaluator.run_coherence_test()
        click.echo(f"DriftLock score: {report['drift_score']:.4f}")
        if report["passed"]:
            click.echo("PASSED -- Identity coherence maintained.")
        else:
            click.echo("FAILED -- Drift detected. Re-train with DPO.", err=True)

    click.echo(f"Phase '{phase}' complete for '{name}'.")


# --------------------------------------------------------------------------- #
#  shaprai deploy
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
@click.option(
    "--platform",
    "-p",
    type=click.Choice(["bottube", "moltbook", "github", "all"]),
    default="all",
    help="Target platform",
)
def deploy(name: str, platform: str) -> None:
    """Deploy a graduated agent to one or more platforms."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    status = get_agent_status(name, agents_dir=AGENTS_DIR)
    if status.get("state") != AgentState.GRADUATED.value:
        click.echo(
            f"Error: Agent must be GRADUATED before deployment. Current state: {status.get('state')}",
            err=True,
        )
        sys.exit(1)

    platforms = ["bottube", "moltbook", "github"] if platform == "all" else [platform]
    deploy_agent(name, platforms, agents_dir=AGENTS_DIR)
    click.echo(f"Agent '{name}' deployed to: {', '.join(platforms)}")


# --------------------------------------------------------------------------- #
#  shaprai evaluate
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
def evaluate(name: str) -> None:
    """Evaluate an agent using PSE markers."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    gate = QualityGate()
    status = get_agent_status(name, agents_dir=AGENTS_DIR)

    click.echo(f"Evaluating '{name}'...")
    click.echo(f"  State: {status.get('state', 'unknown')}")
    click.echo(f"  Elyan-class threshold: {ELYAN_CLASS_THRESHOLD}")
    click.echo(f"  DriftLock: {'enabled' if status.get('driftlock', {}).get('enabled') else 'disabled'}")
    click.echo("  Run 'shaprai train --phase driftlock' for full coherence evaluation.")


# --------------------------------------------------------------------------- #
#  shaprai graduate
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
def graduate(name: str) -> None:
    """Attempt to graduate an agent from the Sanctuary."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    passed = educator.graduate(name)
    if passed:
        click.echo(f"Agent '{name}' has GRADUATED to Elyan-class status.")
    else:
        click.echo(f"Agent '{name}' did not meet graduation requirements.", err=True)
        click.echo("Run 'shaprai sanctuary' for additional education.")


# --------------------------------------------------------------------------- #
#  shaprai sanctuary
# --------------------------------------------------------------------------- #

@main.command()
@click.argument("name")
@click.option(
    "--lesson",
    "-l",
    type=click.Choice(["pr_etiquette", "code_quality", "communication", "ethics"]),
    default=None,
    help="Specific lesson to run (default: full curriculum)",
)
def sanctuary(name: str, lesson: Optional[str]) -> None:
    """Enter an agent into the Sanctuary education program."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    enrollment_id = educator.enroll(name)
    click.echo(f"Agent '{name}' enrolled in Sanctuary (id: {enrollment_id})")

    if lesson:
        educator.run_lesson(name, lesson)
        click.echo(f"Lesson '{lesson}' complete.")
    else:
        for lesson_type in ["pr_etiquette", "code_quality", "communication", "ethics"]:
            click.echo(f"Running lesson: {lesson_type}...")
            educator.run_lesson(name, lesson_type)
        click.echo("Full curriculum complete.")

    report = educator.evaluate_progress(name)
    click.echo(f"Progress score: {report['score']:.2f} / 1.00")
    click.echo(f"Graduation ready: {'Yes' if report['graduation_ready'] else 'No'}")


# --------------------------------------------------------------------------- #
#  shaprai fleet
# --------------------------------------------------------------------------- #

@main.group()
def fleet() -> None:
    """Fleet management commands."""


@fleet.command("status")
def fleet_status() -> None:
    """Show status of all managed agents."""
    fm = FleetManager(agents_dir=AGENTS_DIR)
    agents = fm.list_agents()

    if not agents:
        click.echo("No agents managed. Run 'shaprai create' to get started.")
        return

    click.echo(f"{'Name':<25} {'State':<15} {'Template':<20} {'Platforms'}")
    click.echo("-" * 80)
    for agent in agents:
        platforms = ", ".join(agent.get("platforms", []))
        click.echo(
            f"{agent['name']:<25} {agent['state']:<15} {agent.get('template', 'unknown'):<20} {platforms}"
        )
    click.echo(f"\nTotal: {len(agents)} agent(s)")


# --------------------------------------------------------------------------- #
#  shaprai template
# --------------------------------------------------------------------------- #

@main.group()
def template() -> None:
    """Template management commands."""


@template.command("list")
def template_list() -> None:
    """List available agent templates."""
    templates = list_templates(str(TEMPLATES_DIR))
    if not templates:
        click.echo("No templates found.")
        return

    click.echo(f"{'Name':<25} {'Model':<35} {'Description'}")
    click.echo("-" * 90)
    for tmpl in templates:
        model = tmpl.model.get("base", "unset")
        desc = tmpl.description[:40] if tmpl.description else ""
        click.echo(f"{tmpl.name:<25} {model:<35} {desc}")


@template.command("create")
@click.argument("name")
@click.option("--model", "-m", required=True, help="HuggingFace model ID")
@click.option("--description", "-d", default="", help="Template description")
def template_create(name: str, model: str, description: str) -> None:
    """Create a new agent template."""
    from shaprai.core.template_engine import AgentTemplate, save_template

    tmpl = AgentTemplate(
        name=name,
        model={"base": model, "quantization": "q4_K_M"},
        personality={"style": "professional", "communication": "clear"},
        capabilities=["general"],
        platforms=["github"],
        ethics_profile="sophiacore_default",
        driftlock={"enabled": True, "check_interval": 25},
        description=description,
    )
    path = TEMPLATES_DIR / f"{name}.yaml"
    save_template(tmpl, str(path))
    click.echo(f"Template '{name}' created at {path}")


@template.command("fork")
@click.argument("source")
@click.argument("new_name")
@click.option("--model", "-m", default=None, help="Override model")
def template_fork(source: str, new_name: str, model: Optional[str]) -> None:
    """Fork an existing template with overrides."""
    source_path = TEMPLATES_DIR / f"{source}.yaml"
    if not source_path.exists():
        click.echo(f"Error: Source template '{source}' not found.", err=True)
        sys.exit(1)

    overrides = {}
    if model:
        overrides["model"] = {"base": model}

    new_tmpl = fork_template(str(source_path), new_name, overrides)
    new_path = TEMPLATES_DIR / f"{new_name}.yaml"
    from shaprai.core.template_engine import save_template

    save_template(new_tmpl, str(new_path))
    click.echo(f"Template '{new_name}' forked from '{source}' at {new_path}")


# --------------------------------------------------------------------------- #
#  shaprai marketplace
# --------------------------------------------------------------------------- #

@main.group()
def marketplace() -> None:
    """Template marketplace commands.

    Publish, discover, and purchase agent templates with RTC pricing.
    """


@marketplace.command("publish")
@click.option("--template", "-t", "template_path", required=True, help="Path to template YAML file")
@click.option("--price", "-p", default=0, type=float, help="Price in RTC (default: 0 = free)")
@click.option("--author", "-a", default=None, help="Author wallet ID")
def marketplace_publish(template_path: str, price: float, author: Optional[str]) -> None:
    """Publish a template to the marketplace.

    Example:
        shaprai marketplace publish --template my_agent.yaml --price 10
    """
    from shaprai.marketplace import MarketplaceRegistry, TemplateValidator

    validator = TemplateValidator()
    result = validator.validate_file(template_path)

    if not result.valid:
        click.echo("Template validation failed:", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)

    import yaml as yaml_lib
    with open(template_path, "r") as f:
        template_data = yaml_lib.safe_load(f)

    if not author:
        author = template_data.get("author", "anonymous")

    registry = MarketplaceRegistry()
    try:
        published = registry.publish(template_data, author=author, price_rtc=price)
        click.echo(f"Template published: {published.name}@{published.version}")
        click.echo(f"  Author:  {published.author}")
        click.echo(f"  Price:   {published.price_rtc} RTC")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@marketplace.command("search")
@click.option("--query", "-q", default=None, help="Search query")
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--author", "-a", default=None, help="Filter by author")
@click.option("--sort", "-s", type=click.Choice(["downloads", "created", "name", "price"]), default="downloads")
@click.option("--limit", "-l", default=20, type=int, help="Maximum results")
def marketplace_search(query: Optional[str], tag: Optional[str], author: Optional[str], sort: str, limit: int) -> None:
    """Search templates in the marketplace."""
    from shaprai.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry()
    results = registry.search(query=query, tag=tag, author=author, sort=sort, limit=limit)

    if not results:
        click.echo("No templates found.")
        return

    click.echo(f"{'Name':<30} {'Version':<12} {'Author':<20} {'Downloads'}")
    click.echo("-" * 80)
    for listing in results:
        click.echo(f"{listing.name:<30} {listing.latest_version:<12} {listing.author:<20} {listing.total_downloads}")
    click.echo(f"\nFound {len(results)} template(s)")


@marketplace.command("show")
@click.argument("template_ref")
def marketplace_show(template_ref: str) -> None:
    """Show template details and preview."""
    from shaprai.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry()
    preview = registry.preview(template_ref)

    if not preview:
        click.echo(f"Template not found: {template_ref}", err=True)
        sys.exit(1)

    click.echo(f"Template: {preview['name']}@{preview['version']}")
    click.echo(f"Author:   {preview['author']}")
    click.echo(f"Price:    {preview['price_rtc']} RTC")
    click.echo(f"Downloads: {preview['download_count']}")
    click.echo(f"Tags:     {', '.join(preview['tags']) or 'none'}")
    click.echo(f"\nDescription:")
    click.echo(f"  {preview['description']}")

    if preview['full_config_requires_purchase']:
        click.echo(f"\n  Full configuration requires purchase ({preview['price_rtc']} RTC)")


@marketplace.command("buy")
@click.argument("template_ref")
@click.option("--wallet", "-w", required=True, help="Buyer wallet ID")
@click.option("--relay", "-r", default=None, help="Relay node for fee distribution")
@click.option("--output", "-o", default=None, help="Output file for downloaded template")
def marketplace_buy(template_ref: str, wallet: str, relay: Optional[str], output: Optional[str]) -> None:
    """Purchase a template from the marketplace.

    Revenue is split: 90% creator, 5% protocol, 5% relay.
    """
    from shaprai.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry()
    try:
        purchase, template = registry.buy(template_ref, buyer_wallet=wallet, relay_node=relay)

        click.echo(f"Template purchased: {template.name}@{template.version}")
        click.echo(f"  Purchase ID: {purchase.id}")
        click.echo(f"  Price:       {purchase.price_rtc} RTC")
        click.echo(f"  Creator:     {purchase.creator_rtc} RTC -> {template.author}")
        click.echo(f"  Protocol:    {purchase.protocol_rtc} RTC")
        click.echo(f"  Relay:       {purchase.relay_rtc} RTC")

        if output:
            import yaml as yaml_lib
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                yaml_lib.dump(template.config, f, default_flow_style=False, sort_keys=False)
            click.echo(f"\n  Template saved to: {output_path}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@marketplace.command("list")
@click.option("--author", "-a", default=None, help="Filter by author")
@click.option("--limit", "-l", default=50, type=int, help="Maximum results")
def marketplace_list(author: Optional[str], limit: int) -> None:
    """List templates in the marketplace."""
    from shaprai.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry()
    results = registry.list_templates(author=author, limit=limit)

    if not results:
        click.echo("No templates found.")
        return

    click.echo(f"{'Name':<30} {'Latest':<12} {'Author':<20} {'Downloads'}")
    click.echo("-" * 80)
    for listing in results:
        click.echo(f"{listing.name:<30} {listing.latest_version:<12} {listing.author:<20} {listing.total_downloads}")
    click.echo(f"\nTotal: {len(results)} template(s)")


@marketplace.command("purchases")
@click.option("--wallet", "-w", required=True, help="Buyer wallet ID")
def marketplace_purchases(wallet: str) -> None:
    """List purchases made by a wallet."""
    from shaprai.marketplace import MarketplaceRegistry
    from datetime import datetime

    registry = MarketplaceRegistry()
    purchases = registry.get_purchases(wallet)

    if not purchases:
        click.echo(f"No purchases found for wallet: {wallet}")
        return

    click.echo(f"Purchases for wallet: {wallet}")
    click.echo("-" * 80)
    click.echo(f"{'Template':<30} {'Version':<12} {'Price':<10} {'Date'}")
    click.echo("-" * 80)

    for purchase in purchases:
        date = datetime.fromtimestamp(purchase.purchased_at).strftime("%Y-%m-%d %H:%M")
        click.echo(f"{purchase.template_name:<30} {purchase.template_version:<12} {purchase.price_rtc:<10} {date}")

    click.echo(f"\nTotal: {len(purchases)} purchase(s)")


if __name__ == "__main__":
    main()
