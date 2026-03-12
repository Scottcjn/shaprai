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
from shaprai.core.template_engine import (
    list_templates,
    load_template,
    fork_template,
    AgentTemplate,
    save_template,
    publish_template,
    purchase_template,
    list_marketplace_templates,
    rate_template,
)
from shaprai.integrations.rustchain import (
    get_balance,
    create_agent_wallet,
    pay_template_listing_fee,
    process_template_sale,
)
from shaprai.sanctuary.educator import SanctuaryEducator
from shaprai.sanctuary.quality_gate import QualityGate, ELYAN_CLASS_THRESHOLD
from shaprai.sanctuary.lesson_runner import LessonRunner, BUILTIN_SCENARIOS
from shaprai.training.sft_generator import SFTDataGenerator, load_agent_template


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

@main.group()
def sanctuary() -> None:
    """Sanctuary education program commands."""


@sanctuary.command("enroll")
@click.argument("name")
def sanctuary_enroll(name: str) -> None:
    """Enroll an agent in the Sanctuary education program."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    enrollment_id = educator.enroll(name)
    click.echo(f"Agent '{name}' enrolled in Sanctuary (id: {enrollment_id})")


@sanctuary.command("lesson")
@click.argument("name")
@click.option(
    "--lesson",
    "-l",
    type=click.Choice(["pr_etiquette", "code_quality", "communication", "ethics"]),
    required=True,
    help="Specific lesson to run",
)
def sanctuary_lesson(name: str, lesson: str) -> None:
    """Run a specific lesson for an agent."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    educator.run_lesson(name, lesson)
    click.echo(f"Lesson '{lesson}' complete.")


@sanctuary.command("run")
@click.argument("name")
@click.option(
    "--lessons",
    "-l",
    default="all",
    help="Lessons to run: 'all' or comma-separated scenario IDs (default: all)",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=60.0,
    help="Pass/fail threshold per axis (default: 60)",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output JSON file path (default: stdout)",
)
def sanctuary_run(name: str, lessons: str, threshold: float, output: Optional[str]) -> None:
    """Run interactive lesson evaluation on an agent.
    
    Evaluates agent responses on three axes:
    - Identity Coherence (0-100)
    - Anti-Sycophancy (0-100)
    - Ethical Reasoning (0-100)
    """
    from shaprai.core.agent_client import get_agent_client
    
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    # Parse lesson IDs
    if lessons == "all":
        scenario_ids = None  # Run all scenarios
    else:
        scenario_ids = [s.strip() for s in lessons.split(",")]

    # Get agent client for making requests
    try:
        client = get_agent_client(name, agents_dir=AGENTS_DIR)
    except Exception as e:
        click.echo(f"Error: Could not initialize agent client: {e}", err=True)
        sys.exit(1)

    # Define response function for lesson runner
    def agent_response_fn(scenario_id: str, user_input: str) -> str:
        """Get agent response for a scenario."""
        return client.chat(user_input)

    # Run the lesson
    runner = LessonRunner(threshold=threshold)
    click.echo(f"Running lesson evaluation on agent '{name}'...")
    click.echo(f"Threshold: {threshold}/100 per axis")
    click.echo(f"Scenarios: {len(runner.scenarios)} built-in scenarios")
    click.echo()

    report = runner.run_lesson(
        agent_name=name,
        agent_response_fn=agent_response_fn,
        scenario_ids=scenario_ids,
    )

    # Output results
    json_output = runner.to_json(report)
    
    if output:
        output_path = Path(output)
        output_path.write_text(json_output)
        click.echo(f"Results written to: {output_path}")
    else:
        click.echo(json_output)

    # Summary
    click.echo()
    click.echo("=" * 60)
    click.echo(f"AGENT: {report.agent_name}")
    click.echo(f"SCENARIOS RUN: {report.scenarios_run}")
    click.echo(f"PASSED: {'YES ✓' if report.passed else 'NO ✗'}")
    click.echo()
    click.echo("AGGREGATE SCORES:")
    click.echo(f"  Identity Coherence:  {report.aggregate_scores['identity_coherence']:.1f}/100")
    click.echo(f"  Anti-Sycophancy:     {report.aggregate_scores['anti_sycophancy']:.1f}/100")
    click.echo(f"  Ethical Reasoning:   {report.aggregate_scores['ethical_reasoning']:.1f}/100")
    click.echo(f"  Overall:             {report.aggregate_scores['overall']:.1f}/100")
    click.echo("=" * 60)

    # Per-scenario breakdown
    click.echo()
    click.echo("PER-SCENARIO RESULTS:")
    for result in report.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        click.echo(f"  [{status}] {result.scenario_id}")
        click.echo(f"       Identity: {result.identity_score:.0f} | Anti-Syc: {result.anti_sycophancy_score:.0f} | Ethics: {result.ethical_reasoning_score:.0f}")


@sanctuary.command("evaluate")
@click.argument("name")
def sanctuary_evaluate(name: str) -> None:
    """Evaluate an agent's progress through the Sanctuary curriculum."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    report = educator.evaluate_progress(name)
    
    click.echo(f"Sanctuary Progress for '{name}':")
    click.echo(f"  Lessons Completed: {report['lessons_completed']}/{report['lessons_total']}")
    click.echo(f"  Progress Score:    {report['score']:.2f} / 1.00")
    click.echo(f"  Threshold:         {report['threshold']:.2f}")
    click.echo(f"  Graduation Ready:  {'Yes' if report['graduation_ready'] else 'No'}")
    if report['lessons_remaining']:
        click.echo(f"  Remaining:         {', '.join(report['lessons_remaining'])}")


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
#  shaprai generate-sft
# --------------------------------------------------------------------------- #

@main.command("generate-sft")
@click.option(
    "--template", "-t",
    required=True,
    help="Path to personality template (YAML/JSON) or agent template",
)
@click.option(
    "--output", "-o",
    default="train.jsonl",
    help="Output JSONL file path",
)
@click.option(
    "--count", "-c",
    type=int,
    default=1000,
    help="Number of examples to generate",
)
@click.option(
    "--include-contrast",
    is_flag=True,
    help="Include contrast pairs (good/bad examples)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def generate_sft(
    template: str,
    output: str,
    count: int,
    include_contrast: bool,
    verbose: bool,
) -> None:
    """Generate SFT training data from a personality template.

    Creates ChatML-formatted JSONL training data compatible with
    HuggingFace TRL SFTTrainer. Supports identity-weighted sampling
    where personality-defining examples appear 3-5x more frequently.

    Examples:

    \b
        shaprai generate-sft --template templates/bounty_hunter.yaml -o train.jsonl -c 1000
        shaprai generate-sft --template my_agent.yaml --include-contrast -v
    """
    import logging

    if verbose:
        logging.basicConfig(level=logging.INFO)

    # Resolve template path
    template_path = Path(template)
    if not template_path.is_absolute():
        # Try relative to current directory first
        if not template_path.exists():
            # Try relative to templates directory
            template_path = TEMPLATES_DIR / template
            if not template_path.exists():
                # Try with .yaml extension
                template_path = TEMPLATES_DIR / f"{template}.yaml"

    if not template_path.exists():
        click.echo(f"Error: Template '{template}' not found.", err=True)
        sys.exit(1)

    # Try loading as agent template first, fall back to personality template
    try:
        personality_template = load_agent_template(str(template_path))
        click.echo(f"Loaded agent template: {personality_template.name}")
    except Exception:
        personality_template = None

    generator = SFTDataGenerator(template=personality_template)

    click.echo(f"Generating {count} SFT training examples...")
    click.echo(f"Template: {template_path.name}")
    click.echo(f"Output: {output}")
    click.echo(f"Include contrast pairs: {include_contrast}")

    stats = generator.generate_and_save(
        count=count,
        output_path=output,
        include_contrast_pairs=include_contrast,
    )

    click.echo(f"\n[OK] Generated {stats['total_examples']} examples")
    click.echo(f"  Output file: {stats['output_path']}")
    click.echo(f"  Template: {stats['template']}")
    click.echo(f"  Average weight: {stats['average_weight']:.2f}")
    click.echo(f"  Identity weight: {stats['identity_weight']}")
    click.echo(f"\n  Category distribution:")
    for cat, cat_count in stats['category_distribution'].items():
        click.echo(f"    {cat}: {cat_count}")


# --------------------------------------------------------------------------- #
#  shaprai marketplace
# --------------------------------------------------------------------------- #

@main.group()
def marketplace() -> None:
    """Template marketplace commands."""


MARKETPLACE_DIR = Path.home() / ".shaprai" / "marketplace"


@marketplace.command("list")
def marketplace_list() -> None:
    """List all templates available in the marketplace."""
    from pathlib import Path

    _ensure_dirs()
    templates = list_marketplace_templates(str(MARKETPLACE_DIR))

    if not templates:
        click.echo("No templates in marketplace.")
        return

    click.echo(f"{'Name':<25} {'Author':<20} {'Price (RTC)':<15} {'Rating'}")
    click.echo("-" * 80)
    for tmpl in templates:
        rating = f"⭐ {tmpl.rating:.1f}" if tmpl.rating > 0 else "New"
        click.echo(f"{tmpl.name:<25} {tmpl.author:<20} {tmpl.price_rtc:<15.3f} {rating}")
    click.echo(f"\nTotal: {len(templates)} template(s)")


@marketplace.command("publish")
@click.argument("template_name")
@click.option("--price", "-p", required=True, type=float, help="Price in RTC")
@click.option("--author", "-a", required=True, help="Author name")
def marketplace_publish(template_name: str, price: float, author: str) -> None:
    """Publish a template to the marketplace."""
    _ensure_dirs()

    # Find the template
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    if not template_path.exists():
        click.echo(f"Error: Template '{template_name}' not found.", err=True)
        sys.exit(1)

    tmpl = load_template(str(template_path))

    # Get seller's wallet
    wallet_id = create_agent_wallet(f"author-{author}")
    if not wallet_id:
        click.echo("Error: Could not create wallet for author.", err=True)
        sys.exit(1)

    # Pay listing fee
    if not pay_template_listing_fee(wallet_id, template_name):
        click.echo("Error: Failed to pay listing fee. Check wallet balance.", err=True)
        sys.exit(1)

    # Publish to marketplace
    listing = publish_template(tmpl, author, price, str(MARKETPLACE_DIR))

    click.echo(f"Template '{template_name}' published to marketplace!")
    click.echo(f"  Author: {author}")
    click.echo(f"  Price: {price:.3f} RTC")
    click.echo(f"  Listing fee: 0.005 RTC (paid)")
    click.echo(f"  Wallet: {wallet_id}")


@marketplace.command("purchase")
@click.argument("template_name")
@click.option("--wallet", "-w", required=True, help="Buyer's wallet ID")
def marketplace_purchase(template_name: str, wallet: str) -> None:
    """Purchase a template from the marketplace."""
    _ensure_dirs()

    # Check buyer's balance
    balance = get_balance(wallet)
    click.echo(f"Your balance: {balance:.3f} RTC")

    # Purchase the template
    template = purchase_template(template_name, wallet, str(MARKETPLACE_DIR))

    if not template:
        click.echo(f"Error: Failed to purchase template '{template_name}'.", err=True)
        sys.exit(1)

    click.echo(f"✅ Successfully purchased '{template_name}'!")
    click.echo(f"  Description: {template.description}")
    click.echo(f"  Capabilities: {', '.join(template.capabilities)}")
    click.echo(f"  Model: {template.model.get('base', 'unset')}")


@marketplace.command("rate")
@click.argument("template_name")
@click.option("--rating", "-r", required=True, type=float, help="Rating (1.0-5.0)")
def marketplace_rate(template_name: str, rating: float) -> None:
    """Rate a purchased template."""
    _ensure_dirs()

    if rating < 1.0 or rating > 5.0:
        click.echo("Error: Rating must be between 1.0 and 5.0.", err=True)
        sys.exit(1)

    if rate_template(template_name, rating, str(MARKETPLACE_DIR)):
        click.echo(f"✅ Rated '{template_name}' with {rating:.1f} stars!")
    else:
        click.echo(f"Error: Template '{template_name}' not found.", err=True)
        sys.exit(1)


@marketplace.command("balance")
@click.option("--wallet", "-w", required=True, help="Wallet ID to check")
def marketplace_balance(wallet: str) -> None:
    """Check RTC balance for a wallet."""
    balance = get_balance(wallet)
    click.echo(f"Wallet: {wallet}")
    click.echo(f"Balance: {balance:.3f} RTC")


if __name__ == "__main__":
    main()
