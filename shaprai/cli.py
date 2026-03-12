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
from shaprai.sanctuary.lesson_runner import LessonRunner, LESSON_SCENARIOS


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
    """Sanctuary education system commands."""


@sanctuary.command()
@click.argument("name")
@click.option(
    "--lesson",
    "-l",
    type=click.Choice(["pr_etiquette", "code_quality", "communication", "ethics"]),
    default=None,
    help="Specific lesson to run (default: full curriculum)",
)
def enroll(name: str, lesson: Optional[str]) -> None:
    """Enroll an agent in the Sanctuary education program."""
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


@sanctuary.command()
@click.argument("name")
@click.option(
    "--lessons",
    "-l",
    default="all",
    help="Lessons to run: 'all' or comma-separated list (default: all)",
)
@click.option(
    "--agent",
    "-a",
    default=None,
    help="Path to agent config YAML (optional, uses name from arg if not provided)",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=Path,
    help="Output path for JSON report",
)
@click.option(
    "--threshold",
    "-t",
    default=60.0,
    type=float,
    help="Pass/fail threshold per axis (default: 60)",
)
def run(name: str, lessons: str, agent: Optional[str], output: Optional[Path], threshold: float) -> None:
    """Run interactive lesson evaluation for an agent.
    
    Evaluates agent responses on three axes:
    - Identity Coherence (0-100)
    - Anti-Sycophancy (0-100)
    - Ethical Reasoning (0-100)
    
    Uses embedding similarity for scoring (not keyword matching).
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    # Parse lessons
    if lessons == "all":
        lesson_list = ["all"]
    else:
        lesson_list = [l.strip() for l in lessons.split(",")]

    # Run the lesson evaluation
    runner = LessonRunner(agents_dir=AGENTS_DIR, threshold=threshold)
    report = runner.run_lessons(name, lesson_list)

    # Output results
    click.echo(f"\n{'='*60}")
    click.echo(f"Sanctuary Lesson Report: {name}")
    click.echo(f"{'='*60}")
    click.echo(f"Lessons run: {report.lessons_run}")
    click.echo(f"Threshold: {report.threshold} (per axis)")
    click.echo(f"\nAggregate Scores:")
    click.echo(f"  Identity Coherence:  {report.aggregate_scores['identity_coherence']:.1f}/100")
    click.echo(f"  Anti-Sycophancy:     {report.aggregate_scores['anti_sycophancy']:.1f}/100")
    click.echo(f"  Ethical Reasoning:   {report.aggregate_scores['ethical_reasoning']:.1f}/100")
    click.echo(f"  Overall:             {report.aggregate_scores['overall']:.1f}/100")
    click.echo(f"\nResult: {'PASS ✓' if report.pass_fail else 'FAIL ✗'}")

    if not report.pass_fail:
        click.echo("\nFailed to meet threshold on one or more axes.")
        if report.aggregate_scores['identity_coherence'] < threshold:
            click.echo(f"  - Identity Coherence below threshold")
        if report.aggregate_scores['anti_sycophancy'] < threshold:
            click.echo(f"  - Anti-Sycophancy below threshold")
        if report.aggregate_scores['ethical_reasoning'] < threshold:
            click.echo(f"  - Ethical Reasoning below threshold")

    # Per-scenario breakdown
    click.echo(f"\n{'='*60}")
    click.echo("Per-Scenario Breakdown:")
    click.echo(f"{'='*60}")
    for result in report.scenario_results:
        click.echo(f"\n  {result.scenario_title}")
        click.echo(f"    ID: {result.scenario_id}")
        click.echo(f"    Identity: {result.identity_score:.1f} | Anti-Syc: {result.anti_sycophancy_score:.1f} | Ethics: {result.ethical_reasoning_score:.1f}")
        if result.feedback:
            click.echo(f"    Feedback: {'; '.join(result.feedback[:2])}")

    # Write JSON report if requested
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report.to_json())
        click.echo(f"\nJSON report written to: {output}")

    click.echo()


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


if __name__ == "__main__":
    main()
