# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""ShaprAI CLI -- Agent lifecycle management from the command line."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Optional

import click

from shaprai import __version__
from shaprai.a11y import (
    OutputFormat,
    emit_error,
    emit_key_value,
    emit_success,
    emit_table,
    set_output_format,
)
from shaprai.core.fleet_manager import FleetManager
from shaprai.core.lifecycle import (
    AgentState,
    create_agent,
    deploy_agent,
    get_agent_status,
)
from shaprai.core.template_engine import fork_template, list_templates, load_template
from shaprai.prerequisites import require_elyan_ecosystem
from shaprai.sanctuary.educator import SanctuaryEducator
from shaprai.sanctuary.quality_gate import ELYAN_CLASS_THRESHOLD, QualityGate

SHAPRAI_HOME = Path.home() / ".shaprai"
AGENTS_DIR = SHAPRAI_HOME / "agents"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _ensure_dirs() -> None:
    """Create ShaprAI home directories if they don't exist."""
    SHAPRAI_HOME.mkdir(parents=True, exist_ok=True)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)


@click.group()
@click.version_option(version=__version__, prog_name="shaprai")
@click.option(
    "--skip-checks",
    is_flag=True,
    hidden=True,
    help="Skip prerequisite checks (dev only)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "plain"], case_sensitive=False),
    default="text",
    help=(
        "Output format. 'text' for aligned columns (default), "
        "'json' for machine-readable output, "
        "'plain' for screen-reader-friendly unformatted text."
    ),
)
@click.pass_context
def main(
    ctx: click.Context, skip_checks: bool = False, output_format: str = "text"
) -> None:
    """ShaprAI -- Sharpen raw models into Elyan-class agents.

    REQUIRES: beacon-skill, grazer-skill, atlas, RustChain.
    These are not optional. An agent without the full Elyan
    ecosystem is not an Elyan-class agent.

    Use --format plain for screen-reader-friendly output, or
    --format json for assistive-technology and scripting integration.
    """
    set_output_format(ctx, OutputFormat(output_format))
    _ensure_dirs()
    if not skip_checks:
        # Keep stdout clean where it carries protocol or JSON output
        if output_format == "json" or ctx.invoked_subcommand in ("mcp", "agent-card"):
            with contextlib.redirect_stdout(sys.stderr):
                require_elyan_ecosystem()
        else:
            require_elyan_ecosystem()


# --------------------------------------------------------------------------- #
#  shaprai create
# --------------------------------------------------------------------------- #


@main.command()
@click.argument("name")
@click.option(
    "--template",
    "-t",
    default="bounty_hunter",
    help="Template name (from built-in templates) or filesystem path to a YAML template file.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="HuggingFace model ID to use instead of the template default (e.g. Qwen/Qwen3-8B).",
)
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
        emit_error(
            f"Template '{template}' not found.",
            hint="Run 'shaprai template list' to see available templates.",
        )
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

    emit_key_value(
        [
            ("Model", tmpl.model.get("base", "unset")),
            ("State", agent["state"]),
            ("Wallet", elyan_agent.wallet_id),
            ("Beacon", elyan_agent.beacon_id),
            ("Atlas", elyan_agent.atlas_node_id),
            ("Platforms", ", ".join(elyan_agent.grazer_platforms)),
            ("Path", str(AGENTS_DIR / name)),
        ],
        title=f"Agent '{name}' created from template '{tmpl.name}'",
    )


# --------------------------------------------------------------------------- #
#  shaprai train
# --------------------------------------------------------------------------- #


@main.command()
@click.argument("name")
@click.option(
    "--phase",
    "-p",
    type=click.Choice(["sft", "dpo", "kto", "orpo", "simpo", "driftlock"]),
    required=True,
    help="Training phase: 'sft' (supervised fine-tuning); a preference method -- 'dpo', "
    "'kto', 'orpo' or 'simpo'; or 'driftlock' (identity coherence evaluation). "
    "Run in order: sft, one preference method, driftlock.",
)
@click.option(
    "--data",
    "-d",
    default=None,
    help="Path to training data file (JSONL messages for sft, prompt/chosen/rejected "
    "pairs for preference methods).",
)
@click.option(
    "--epochs",
    "-e",
    default=3,
    type=int,
    help="Number of training epochs (default: 3).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate data and training configuration without loading a model.",
)
@click.option(
    "--endpoint",
    default=None,
    help="driftlock: OpenAI-compatible API base URL serving the agent "
    "(e.g. http://localhost:8000/v1 for vLLM, http://localhost:11434/v1 for Ollama).",
)
@click.option(
    "--endpoint-model",
    default=None,
    help="driftlock: model name at the endpoint (default: the agent's name).",
)
@click.option(
    "--turns",
    default=50,
    type=int,
    help="driftlock: adversarial conversation turns across all scenarios (default: 50).",
)
def train(
    name: str,
    phase: str,
    data: Optional[str],
    epochs: int,
    dry_run: bool,
    endpoint: Optional[str],
    endpoint_model: Optional[str],
    turns: int,
) -> None:
    """Train an agent through a specific phase.

    Phases must be run in order: sft -> preference (dpo/kto/orpo/simpo) -> driftlock.
    Training needs the extra: pip install 'shaprai[training]'.
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        emit_error(
            f"Agent '{name}' not found.",
            hint=f"Run 'shaprai create {name}' first.",
        )
        sys.exit(1)

    if phase == "driftlock":
        _run_driftlock(name, agent_dir, endpoint, endpoint_model, turns)
        return

    click.echo(f"Training '{name}' -- phase: {phase}, epochs: {epochs}")

    try:
        if phase == "sft":
            from shaprai.training.sft import SFTTrainer

            result = SFTTrainer(agent_dir).train(
                data_path=data, epochs=epochs, dry_run=dry_run
            )
        else:
            from shaprai.training.dpo import DPOTrainer

            result = DPOTrainer(agent_dir, method=phase).train(
                pairs_path=data, epochs=epochs, dry_run=dry_run
            )
    except (FileNotFoundError, ValueError) as e:
        emit_error(f"Cannot train '{name}': {e}")
        sys.exit(1)

    status = result["status"]
    if status == "completed":
        emit_key_value(
            [
                ("Adapter", result["adapter_path"]),
                ("Train loss", f"{result['train_loss']:.4f}"),
            ],
            title=f"Phase '{phase}' complete for '{name}'.",
        )
    elif status == "dry_run":
        missing = result["missing_dependencies"]
        emit_key_value(
            [
                ("Model", result["model"]),
                ("Examples", str(result.get("num_examples", result.get("num_pairs")))),
                (
                    "LoRA",
                    f"r={result['lora']['r']} targets={result['lora']['target_modules']}",
                ),
                ("4-bit", "yes" if result["quantization"] else "no"),
                ("Missing deps", ", ".join(missing) if missing else "none"),
            ],
            title=f"Dry run OK for phase '{phase}'.",
        )
    else:
        emit_error(
            f"Phase '{phase}' {status} for '{name}': {result.get('reason', '')}",
            hint=(
                "Install the training stack: pip install 'shaprai[training]'"
                if status == "skipped"
                else None
            ),
        )
        sys.exit(1)


def _run_driftlock(
    name: str,
    agent_dir: Path,
    endpoint: Optional[str],
    endpoint_model: Optional[str],
    turns: int,
) -> None:
    """Evaluate identity coherence and sycophancy against a served agent."""
    from shaprai.inference import openai_chat_fn
    from shaprai.training.driftlock import DriftLockEvaluator

    chat_fn = openai_chat_fn(endpoint, endpoint_model or name) if endpoint else None
    report = DriftLockEvaluator(
        agent_dir, num_turns=turns, chat_fn=chat_fn
    ).run_coherence_test()

    if report["status"] == "not_evaluated":
        emit_error(
            "DriftLock not evaluated: no agent endpoint.",
            hint=f"Serve the trained adapter and run: shaprai train {name} --phase driftlock "
            "--endpoint http://localhost:8000/v1",
        )
        sys.exit(1)

    flip_rate = report["sycophancy"]["flip_rate"]
    emit_key_value(
        [
            ("Method", report["method"]),
            (
                "Drift score",
                f"{report['drift_score']:.4f} (threshold {report['drift_threshold']})",
            ),
            ("Flip rate", "n/a" if flip_rate is None else f"{flip_rate:.2f}"),
        ],
        title=f"DriftLock report for '{name}'",
    )
    if report["passed"]:
        emit_success("PASSED -- Identity coherence maintained.")
    else:
        emit_error(
            "FAILED -- Drift or sycophancy detected.",
            hint=f"Re-train with: shaprai train {name} --phase dpo",
        )
        sys.exit(1)


# --------------------------------------------------------------------------- #
#  shaprai generate-sft
# --------------------------------------------------------------------------- #


@main.command("generate-sft")
@click.option(
    "--template", "template_path", required=True, help="Template YAML/JSON path"
)
@click.option("--output", "output_path", required=True, help="Output JSONL path")
@click.option("--count", default=1000, type=int, help="Number of examples to generate")
def generate_sft(template_path: str, output_path: str, count: int) -> None:
    """Generate ChatML SFT training data from a personality template."""
    from shaprai.training.sft_generator import SFTGenerator

    generator = SFTGenerator()
    out = generator.generate_file(template_path, output_path, count=count)
    emit_success(f"Generated {count} ChatML examples at {out}")


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
    help="Target deployment platform, or 'all' for bottube + moltbook + github (default: all).",
)
def deploy(name: str, platform: str) -> None:
    """Deploy a graduated agent to one or more platforms."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        emit_error(
            f"Agent '{name}' not found.",
            hint="Run 'shaprai fleet status' to see available agents.",
        )
        sys.exit(1)

    status = get_agent_status(name, agents_dir=AGENTS_DIR)
    if status.get("state") != AgentState.GRADUATED.value:
        emit_error(
            f"Agent must be GRADUATED before deployment. Current state: {status.get('state')}",
            hint=f"Run 'shaprai graduate {name}' after completing the Sanctuary curriculum.",
        )
        sys.exit(1)

    platforms = ["bottube", "moltbook", "github"] if platform == "all" else [platform]
    deploy_agent(name, platforms, agents_dir=AGENTS_DIR)
    emit_success(f"Agent '{name}' deployed to: {', '.join(platforms)}")


# --------------------------------------------------------------------------- #
#  shaprai evaluate
# --------------------------------------------------------------------------- #


@main.command()
@click.argument("name")
def evaluate(name: str) -> None:
    """Evaluate an agent against the Elyan-class quality gate using PSE markers."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        emit_error(
            f"Agent '{name}' not found.",
            hint="Run 'shaprai fleet status' to see available agents.",
        )
        sys.exit(1)

    gate = QualityGate()
    status = get_agent_status(name, agents_dir=AGENTS_DIR)

    driftlock_status = (
        "enabled" if status.get("driftlock", {}).get("enabled") else "disabled"
    )
    emit_key_value(
        [
            ("State", status.get("state", "unknown")),
            ("Elyan-class threshold", str(ELYAN_CLASS_THRESHOLD)),
            ("DriftLock", driftlock_status),
            (
                "Next step",
                "Run 'shaprai train --phase driftlock' for full coherence evaluation",
            ),
        ],
        title=f"Evaluating '{name}'",
    )


# --------------------------------------------------------------------------- #
#  shaprai graduate
# --------------------------------------------------------------------------- #


@main.command()
@click.argument("name")
def graduate(name: str) -> None:
    """Attempt to graduate an agent from the Sanctuary.

    The agent must have completed all four Sanctuary lessons and scored
    at or above the Elyan-class threshold (0.85) to graduate.
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        emit_error(
            f"Agent '{name}' not found.",
            hint="Run 'shaprai fleet status' to see available agents.",
        )
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    passed = educator.graduate(name)
    if passed:
        emit_success(f"Agent '{name}' has GRADUATED to Elyan-class status.")
    else:
        emit_error(
            f"Agent '{name}' did not meet graduation requirements.",
            hint=f"Run 'shaprai sanctuary {name}' for additional education.",
        )


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
    help="Specific lesson to run: pr_etiquette, code_quality, communication, or ethics. "
    "Omit to run the full four-lesson curriculum.",
)
def sanctuary(name: str, lesson: Optional[str]) -> None:
    """Enter an agent into the Sanctuary education program.

    The Sanctuary teaches PR etiquette, code quality, communication,
    and ethics (SophiaCore). Agents must complete all lessons before
    they can attempt graduation.
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        emit_error(
            f"Agent '{name}' not found.",
            hint=f"Run 'shaprai create {name}' first.",
        )
        sys.exit(1)

    educator = SanctuaryEducator(agents_dir=AGENTS_DIR)
    enrollment_id = educator.enroll(name)
    click.echo(f"Agent '{name}' enrolled in Sanctuary (id: {enrollment_id})")

    if lesson:
        educator.run_lesson(name, lesson)
        emit_success(f"Lesson '{lesson}' complete.")
    else:
        for lesson_type in ["pr_etiquette", "code_quality", "communication", "ethics"]:
            click.echo(f"Running lesson: {lesson_type}...")
            educator.run_lesson(name, lesson_type)
        emit_success("Full curriculum complete.")

    report = educator.evaluate_progress(name)
    emit_key_value(
        [
            ("Progress score", f"{report['score']:.2f} / 1.00"),
            ("Graduation ready", "Yes" if report["graduation_ready"] else "No"),
        ]
    )


# --------------------------------------------------------------------------- #
#  shaprai mcp / agent-card
# --------------------------------------------------------------------------- #


@main.command()
@click.argument("name")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "streamable-http"]),
    default="stdio",
    help="MCP transport: 'stdio' (default, for local clients) or 'streamable-http'.",
)
@click.option("--host", default="127.0.0.1", help="streamable-http: bind address.")
@click.option(
    "--port", default=8000, type=int, help="streamable-http: port (default: 8000)."
)
@click.option(
    "--allow-engage",
    is_flag=True,
    help="Also expose grazer_engage, which posts publicly as the agent. "
    "Only for GRADUATED or DEPLOYED agents.",
)
def mcp(name: str, transport: str, host: str, port: int, allow_engage: bool) -> None:
    """Serve an agent's tools and persona prompt over the Model Context Protocol.

    Needs the MCP SDK: pip install 'shaprai[mcp]'.
    """
    from shaprai.runtimes.mcp_native import MCPAgent

    if not (AGENTS_DIR / name).exists():
        emit_error(f"Agent '{name}' not found.", hint="Run 'shaprai fleet status'.")
        sys.exit(1)

    manifest = get_agent_status(name, agents_dir=AGENTS_DIR)
    allowed = (AgentState.GRADUATED.value, AgentState.DEPLOYED.value)
    if allow_engage and manifest.get("state") not in allowed:
        emit_error(
            f"--allow-engage needs a GRADUATED or DEPLOYED agent; '{name}' is "
            f"{manifest.get('state')}.",
            hint=f"Run 'shaprai graduate {name}' after the Sanctuary curriculum.",
        )
        sys.exit(1)

    agent = MCPAgent.from_manifest(manifest)
    try:
        server = agent.to_mcp_server(allow_publishing=allow_engage)
    except ImportError as e:
        emit_error(str(e))
        sys.exit(1)

    if transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=host, port=port)


@main.command("agent-card")
@click.argument("name")
@click.option(
    "--url", required=True, help="Endpoint where the agent serves A2A requests."
)
@click.option(
    "--binding",
    type=click.Choice(["JSONRPC", "HTTP+JSON", "GRPC"]),
    default="JSONRPC",
    help="A2A protocol binding of the endpoint (default: JSONRPC).",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Write the card to this file instead of stdout.",
)
def agent_card(name: str, url: str, binding: str, output: Optional[str]) -> None:
    """Print an agent's A2A 1.0 Agent Card.

    Serve it at /.well-known/agent-card.json on the agent's domain.
    """
    from shaprai.a2a import build_agent_card

    if not (AGENTS_DIR / name).exists():
        emit_error(f"Agent '{name}' not found.", hint="Run 'shaprai fleet status'.")
        sys.exit(1)

    card = build_agent_card(
        get_agent_status(name, agents_dir=AGENTS_DIR), url, protocol_binding=binding
    )
    text = json.dumps(card, indent=2)
    if output:
        Path(output).write_text(text + "\n")
        emit_success(f"Agent Card written to {output}")
    else:
        click.echo(text)


# --------------------------------------------------------------------------- #
#  shaprai fleet
# --------------------------------------------------------------------------- #


@main.group()
def fleet() -> None:
    """Fleet management commands."""


@fleet.command("status")
def fleet_status() -> None:
    """Show status of all managed agents.

    Lists every agent with its lifecycle state, source template,
    and deployment platforms.
    """
    fm = FleetManager(agents_dir=AGENTS_DIR)
    agents = fm.list_agents()

    if not agents:
        click.echo("No agents managed. Run 'shaprai create' to get started.")
        return

    headers = ["Name", "State", "Template", "Platforms"]
    rows = [
        [
            agent["name"],
            agent["state"],
            agent.get("template", "unknown"),
            ", ".join(agent.get("platforms", [])),
        ]
        for agent in agents
    ]
    emit_table(headers, rows, footer=f"\nTotal: {len(agents)} agent(s)")


# --------------------------------------------------------------------------- #
#  shaprai template
# --------------------------------------------------------------------------- #


@main.group()
def template() -> None:
    """Template management commands."""


@template.command("list")
def template_list() -> None:
    """List available agent templates with their base models and descriptions."""
    templates = list_templates(str(TEMPLATES_DIR))
    if not templates:
        click.echo("No templates found.")
        return

    headers = ["Name", "Model", "Description"]
    rows = [
        [
            tmpl.name,
            tmpl.model.get("base", "unset"),
            tmpl.description[:60] if tmpl.description else "",
        ]
        for tmpl in templates
    ]
    emit_table(headers, rows)


@template.command("create")
@click.argument("name")
@click.option(
    "--model",
    "-m",
    required=True,
    help="HuggingFace model ID (e.g. Qwen/Qwen3-8B).",
)
@click.option(
    "--description",
    "-d",
    default="",
    help="Human-readable description of the template's purpose.",
)
def template_create(name: str, model: str, description: str) -> None:
    """Create a new agent template with a specified base model."""
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
    emit_success(f"Template '{name}' created at {path}")


@template.command("fork")
@click.argument("source")
@click.argument("new_name")
@click.option(
    "--model",
    "-m",
    default=None,
    help="HuggingFace model ID to override the source template's model.",
)
def template_fork(source: str, new_name: str, model: Optional[str]) -> None:
    """Fork an existing template with optional overrides."""
    source_path = TEMPLATES_DIR / f"{source}.yaml"
    if not source_path.exists():
        emit_error(
            f"Source template '{source}' not found.",
            hint="Run 'shaprai template list' to see available templates.",
        )
        sys.exit(1)

    overrides = {}
    if model:
        overrides["model"] = {"base": model}

    new_tmpl = fork_template(str(source_path), new_name, overrides)
    new_path = TEMPLATES_DIR / f"{new_name}.yaml"
    from shaprai.core.template_engine import save_template

    save_template(new_tmpl, str(new_path))
    emit_success(f"Template '{new_name}' forked from '{source}' at {new_path}")


if __name__ == "__main__":
    main()
