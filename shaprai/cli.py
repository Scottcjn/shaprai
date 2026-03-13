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
from shaprai.core.reputation import ReputationManager
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
@click.option("--with-rep", is_flag=True, help="Include reputation metrics")
def fleet_status(with_rep: bool) -> None:
    """Show status of all managed agents."""
    fm = FleetManager(agents_dir=AGENTS_DIR)
    agents = fm.list_agents()

    if not agents:
        click.echo("No agents managed. Run 'shaprai create' to get started.")
        return

    if with_rep:
        rm = ReputationManager()
        click.echo(f"{'Name':<25} {'State':<15} {'Rating':<10} {'Tasks':<10} {'Bounty (RTC)'}")
        click.echo("-" * 80)
        for agent in agents:
            stats = rm.get_agent_stats(agent["name"])
            rating_stars = '★' * int(round(stats['rating'])) + '☆' * (5 - int(round(stats['rating'])))
            click.echo(
                f"{agent['name']:<25} {agent['state']:<15} {rating_stars} {stats['total_tasks']:<10} {stats['bounty_earned']:.2f}"
            )
    else:
        click.echo(f"{'Name':<25} {'State':<15} {'Template':<20} {'Platforms'}")
        click.echo("-" * 80)
        for agent in agents:
            platforms = ", ".join(agent.get("platforms", []))
            click.echo(
                f"{agent['name']:<25} {agent['state']:<15} {agent.get('template', 'unknown'):<20} {platforms}"
            )
    click.echo(f"\nTotal: {len(agents)} agent(s)")
    
    # Show fleet health summary
    health = fm.get_fleet_health()
    if "reputation" in health:
        click.echo(f"\nFleet Reputation:")
        click.echo(f"  Average Rating: {health['reputation']['average_rating']:.1f}/5.0")
        click.echo(f"  Total Bounty Earned: {health['reputation']['total_bounty_earned']:.2f} RTC")
        click.echo(f"  High Rep Agents (7.0+): {health['reputation']['high_reputation_agents']}")


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
#  shaprai reputation
# --------------------------------------------------------------------------- #

@main.group()
def reputation() -> None:
    """Reputation system management."""


@reputation.command("show")
@click.argument("name")
def reputation_show(name: str) -> None:
    """Show reputation details for an agent."""
    rm = ReputationManager()
    stats = rm.get_agent_stats(name)

    if not stats or stats["total_tasks"] == 0:
        click.echo(f"No reputation data for agent '{name}' yet.")
        return

    click.echo(f"Reputation for '{name}':")
    click.echo(f"  Total Score:    {stats['total_score']:.2f} / 10.0")
    click.echo(f"  Rating:         {'★' * int(round(stats['rating']))}{'☆' * (5 - int(round(stats['rating'])))} ({stats['rating']:.1f}/5.0)")
    click.echo(f"  Tasks:          {stats['successful_tasks']}/{stats['total_tasks']} ({stats['success_rate']*100:.1f}% success)")
    click.echo(f"  Bounty Earned:  {stats['bounty_earned']:.2f} RTC")
    click.echo(f"  Recent Trend:   {'+' if stats['recent_trend'] >= 0 else ''}{stats['recent_trend']:.2f}")
    
    # Show last 5 events
    rep = rm.get_reputation(name)
    if rep.events:
        click.echo(f"\nRecent Events:")
        for event in rep.events[-5:]:
            event_type = event.event_type.replace('_', ' ').title()
            delta_str = f"+{event.score_delta:.2f}" if event.score_delta >= 0 else f"{event.score_delta:.2f}"
            click.echo(f"  • {event_type}: {delta_str}")


@reputation.command("leaderboard")
@click.option("--limit", "-l", default=10, type=int, help="Number of agents to show")
def reputation_leaderboard(limit: int) -> None:
    """Show top agents by reputation score."""
    rm = ReputationManager()
    leaderboard = rm.get_leaderboard(limit=limit)

    if not leaderboard:
        click.echo("No reputation data available yet.")
        return

    click.echo(f"{'Rank':<6} {'Agent':<25} {'Score':<10} {'Rating':<10} {'Tasks':<10} {'Bounty (RTC)'}")
    click.echo("-" * 85)
    for i, rep in enumerate(leaderboard, 1):
        rating_stars = '★' * int(round(rep.rating)) + '☆' * (5 - int(round(rep.rating)))
        click.echo(
            f"{i:<6} {rep.agent_name:<25} {rep.total_score:<10.2f} {rating_stars} {rep.total_tasks:<10} {rep.bounty_earned:.2f}"
        )


@reputation.command("record")
@click.argument("name")
@click.option("--event", "-e", required=True, type=click.Choice([
    "task_completed", "task_failed", "bounty_delivered", "bounty_rejected",
    "positive_review", "negative_review", "quality_pr", "helpful_interaction",
    "misconduct", "graduation"
]), help="Event type to record")
@click.option("--delta", "-d", default=None, type=float, help="Custom score delta")
@click.option("--details", "-D", default=None, help="Event details (JSON string)")
def reputation_record(name: str, event: str, delta: Optional[float], details: Optional[str]) -> None:
    """Manually record a reputation event for an agent."""
    import json
    
    rm = ReputationManager()
    
    event_details = None
    if details:
        try:
            event_details = json.loads(details)
        except json.JSONDecodeError:
            click.echo(f"Error: Invalid JSON for details: {details}", err=True)
            sys.exit(1)

    score_delta = rm.record_event(name, event, details=event_details, custom_delta=delta)
    click.echo(f"Recorded '{event}' for '{name}': {'+' if score_delta >= 0 else ''}{score_delta:.2f}")


@reputation.command("reset")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to reset this agent's reputation?")
def reputation_reset(name: str) -> None:
    """Reset an agent's reputation to default values."""
    rm = ReputationManager()
    rm.reset_reputation(name)
    click.echo(f"Reputation reset for '{name}'.")


@reputation.command("export")
@click.option("--output", "-o", default="reputation_export.json", help="Output file path")
def reputation_export(output: str) -> None:
    """Export all reputation data to JSON."""
    rm = ReputationManager()
    output_path = Path(output)
    rm.export_all(output_path)
    click.echo(f"Reputation data exported to {output_path}")


# --------------------------------------------------------------------------- #
#  shaprai generate-sft (Issue #2 - 50 RTC)
# --------------------------------------------------------------------------- #

@main.command("generate-sft")
@click.option("--template", "-t", required=True, help="Agent template YAML file")
@click.option("--output", "-o", default="sft_data.jsonl", help="Output JSONL file")
@click.option("--count", "-c", default=100, type=int, help="Number of examples to generate")
@click.option("--include-contrast", is_flag=True, help="Include contrast pairs")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def generate_sft(template: str, output: str, count: int, include_contrast: bool, verbose: bool) -> None:
    """Generate SFT training data with identity-weighted sampling.
    
    Creates ChatML-formatted JSONL training data compatible with HuggingFace TRL SFTTrainer.
    Identity-defining examples are weighted 3-5x higher than generic examples.
    """
    from shaprai.training.sft_generator import SFTDataGenerator, load_agent_template
    
    # Load template
    template_path = Path(template)
    if not template_path.exists():
        # Try templates directory
        template_path = TEMPLATES_DIR / f"{template}.yaml"
    
    if not template_path.exists():
        click.echo(f"Error: Template '{template}' not found.", err=True)
        sys.exit(1)
    
    tmpl = load_agent_template(str(template_path))
    
    if verbose:
        click.echo(f"Loading template: {tmpl.name}")
        click.echo(f"  Voice: {tmpl.voice}")
        click.echo(f"  Style: {tmpl.style}")
        click.echo(f"  Identity weight: {tmpl.identity_weight}")
    
    # Create generator and generate data
    generator = SFTDataGenerator(template=tmpl)
    stats = generator.generate_and_save(
        count=count,
        output_path=output,
        include_contrast_pairs=include_contrast,
    )
    
    click.echo(f"[OK] Generated {stats['total_examples']} examples")
    click.echo(f"  Output: {output}")
    click.echo(f"  Average weight: {stats['average_weight']:.2f}")
    click.echo(f"  Category distribution:")
    for category, count in stats['category_distribution'].items():
        click.echo(f"    {category}: {count}")


# --------------------------------------------------------------------------- #
#  shaprai generate-dpo (Issue #3 - 50 RTC)
# --------------------------------------------------------------------------- #

@main.command("generate-dpo")
@click.option("--conversations", "-c", default=None, help="Directory with conversation logs")
@click.option("--output", "-o", default="dpo_pairs.jsonl", help="Output JSONL file")
@click.option("--count", "-n", default=50, type=int, help="Number of pairs to generate")
@click.option("--synthetic", is_flag=True, help="Generate synthetic pairs")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def generate_dpo(conversations: Optional[str], output: str, count: int, synthetic: bool, verbose: bool) -> None:
    """Generate DPO contrastive pairs for preference optimization.
    
    Creates chosen/rejected pairs where:
    - Chosen: Principled, identity-coherent responses
    - Rejected: Sycophantic, generic AI slop
    
    Output is JSONL compatible with HuggingFace TRL DPOTrainer.
    """
    from shaprai.training.dpo_generator import DPOGenerator
    
    generator = DPOGenerator()
    
    if conversations:
        # Parse conversation logs
        conv_dir = Path(conversations)
        if not conv_dir.exists():
            click.echo(f"Error: Conversation directory '{conversations}' not found.", err=True)
            sys.exit(1)
        
        if verbose:
            click.echo(f"Parsing conversations from: {conv_dir}")
        
        pairs = generator.generate_from_conversations(conv_dir, max_pairs=count)
    elif synthetic:
        # Generate synthetic pairs
        if verbose:
            click.echo(f"Generating {count} synthetic DPO pairs...")
        
        pairs = generator.generate_synthetic_pairs(count=count)
    else:
        # Use built-in pairs
        if verbose:
            click.echo("Using built-in DPO pairs...")
        
        pairs = generator.get_builtin_pairs()
    
    # Save to JSONL
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    
    click.echo(f"[OK] Generated {len(pairs)} DPO pairs")
    click.echo(f"  Output: {output}")
    
    if verbose:
        click.echo(f"  Rejection patterns used: {len(generator.rejection_patterns)}")


# --------------------------------------------------------------------------- #
#  shaprai marketplace (Issue #8 - 40 RTC)
# --------------------------------------------------------------------------- #

@main.group()
def marketplace() -> None:
    """Template marketplace with RTC pricing."""


@marketplace.command("list")
def marketplace_list() -> None:
    """List all available templates in the marketplace."""
    from shaprai.core.template_engine import list_marketplace_templates
    
    templates = list_marketplace_templates()
    
    if not templates:
        click.echo("No templates in marketplace yet.")
        return
    
    click.echo(f"{'Name':<25} {'Author':<20} {'Price (RTC)':<15} {'Rating'}")
    click.echo("-" * 80)
    for tmpl in templates:
        rating = f"⭐ {tmpl['rating']:.1f}" if tmpl['rating'] > 0 else "New"
        click.echo(f"{tmpl['name']:<25} {tmpl['author']:<20} {tmpl['price_rtc']:<15.3f} {rating}")
    
    click.echo(f"\nTotal: {len(templates)} template(s)")


@marketplace.command("publish")
@click.argument("template_name")
@click.option("--price", "-p", required=True, type=float, help="Price in RTC")
@click.option("--author", "-a", required=True, help="Author name")
@click.option("--description", "-d", default="", help="Template description")
def marketplace_publish(template_name: str, price: float, author: str, description: str) -> None:
    """Publish a template to the marketplace with RTC pricing."""
    from shaprai.core.template_engine import publish_template
    from shaprai.integrations.rustchain import pay_template_listing_fee
    
    # Load the template
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    if not template_path.exists():
        click.echo(f"Error: Template '{template_name}' not found.", err=True)
        sys.exit(1)
    
    # Pay listing fee
    wallet_id = f"agent-{author}"
    try:
        pay_template_listing_fee(wallet_id, template_name)
        fee_paid = True
    except Exception as e:
        click.echo(f"Warning: Could not pay listing fee: {e}")
        fee_paid = False
    
    # Publish to marketplace
    result = publish_template(
        template_path=str(template_path),
        author=author,
        price_rtc=price,
        description=description,
    )
    
    click.echo(f"Template '{template_name}' published to marketplace!")
    click.echo(f"  Author: {author}")
    click.echo(f"  Price: {price:.3f} RTC")
    if fee_paid:
        click.echo(f"  Listing fee: 0.005 RTC (paid)")
    click.echo(f"  Wallet: {wallet_id}")


@marketplace.command("purchase")
@click.argument("template_name")
@click.option("--wallet", "-w", required=True, help="Your wallet ID")
def marketplace_purchase(template_name: str, wallet: str) -> None:
    """Purchase a template from the marketplace."""
    from shaprai.core.template_engine import purchase_template
    from shaprai.integrations.rustchain import get_wallet_balance
    
    # Check balance
    try:
        balance = get_wallet_balance(wallet)
        click.echo(f"Your balance: {balance:.3f} RTC")
    except Exception:
        click.echo("Warning: Could not check wallet balance")
    
    # Purchase template
    result = purchase_template(
        template_name=template_name,
        wallet_id=wallet,
    )
    
    if result['success']:
        click.echo(f"✅ Successfully purchased '{template_name}'!")
        click.echo(f"  Description: {result.get('description', 'N/A')}")
        if 'capabilities' in result:
            click.echo(f"  Capabilities: {', '.join(result['capabilities'])}")
        if 'model' in result:
            click.echo(f"  Model: {result['model']}")
    else:
        click.echo(f"❌ Purchase failed: {result.get('error', 'Unknown error')}", err=True)
        sys.exit(1)


@marketplace.command("rate")
@click.argument("template_name")
@click.option("--rating", "-r", required=True, type=click.FloatRange(1.0, 5.0), help="Rating (1.0-5.0)")
def marketplace_rate(template_name: str, rating: float) -> None:
    """Rate a purchased template."""
    from shaprai.core.template_engine import rate_template
    
    result = rate_template(template_name=template_name, rating=rating)
    
    if result['success']:
        click.echo(f"✅ Rated '{template_name}' with {rating} stars!")
        click.echo(f"  New average rating: {result['new_rating']:.1f}/5.0")
    else:
        click.echo(f"❌ Rating failed: {result.get('error', 'Unknown error')}", err=True)
        sys.exit(1)


@marketplace.command("balance")
@click.option("--wallet", "-w", required=True, help="Wallet ID to check")
def marketplace_balance(wallet: str) -> None:
    """Check wallet balance."""
    from shaprai.integrations.rustchain import get_wallet_balance
    
    try:
        balance = get_wallet_balance(wallet)
        click.echo(f"Wallet: {wallet}")
        click.echo(f"Balance: {balance:.3f} RTC")
    except Exception as e:
        click.echo(f"Error: Could not get balance: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
