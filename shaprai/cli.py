# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""ShaprAI CLI -- Agent lifecycle management from the command line."""

from __future__ import annotations

import sys
import time
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
from shaprai.core.self_governor import (
    collect_metrics,
    evaluate_performance,
    adapt_parameters,
    check_drift,
    AgentMetrics,
    GovernanceAction,
)


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
#  shaprai collaborate
# --------------------------------------------------------------------------- #

@main.group()
def collaborate() -> None:
    """Multi-agent collaboration commands."""


@collaborate.command("message")
@click.argument("sender")
@click.argument("recipient")
@click.option("--content", "-c", required=True, help="Message content (JSON string)")
@click.option(
    "--type", "-t",
    type=click.Choice(["task_request", "task_assignment", "task_update", "task_complete",
                       "help_request", "status_query", "status_response", "coordination"]),
    default="coordination",
    help="Message type",
)
@click.option(
    "--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    default="normal",
    help="Message priority",
)
def collaborate_message(
    sender: str,
    recipient: str,
    content: str,
    type: str,
    priority: str,
) -> None:
    """Send a message from one agent to another."""
    from shaprai.core.collaboration import (
        CollaborationHub,
        AgentMessage,
        MessageType,
        TaskPriority,
    )
    import json

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    try:
        content_dict = json.loads(content)
    except json.JSONDecodeError:
        content_dict = {"message": content}

    message = AgentMessage(
        sender=sender,
        recipient=recipient,
        message_type=MessageType(type),
        content=content_dict,
        priority=TaskPriority(priority),
    )

    message_id = hub.send_message(message)
    click.echo(f"Message sent: {message_id}")
    click.echo(f"  From: {sender}")
    click.echo(f"  To: {recipient}")
    click.echo(f"  Type: {type}")
    click.echo(f"  Priority: {priority}")


@collaborate.command("check")
@click.argument("agent_name")
@click.option("--unread-only", is_flag=True, default=True, help="Only show unread messages")
def collaborate_check(agent_name: str, unread_only: bool) -> None:
    """Check messages for an agent."""
    from shaprai.core.collaboration import CollaborationHub

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    messages = hub.get_messages(agent_name, unread_only=unread_only)

    if not messages:
        click.echo(f"No messages for '{agent_name}'.")
        return

    click.echo(f"Messages for '{agent_name}':")
    click.echo("-" * 80)
    for msg in messages:
        ack_status = "✓" if msg.acknowledged else "○"
        click.echo(f"[{ack_status}] {msg.message_id[:8]}...")
        click.echo(f"  From: {msg.sender}")
        click.echo(f"  Type: {msg.message_type.value}")
        click.echo(f"  Priority: {msg.priority.value}")
        click.echo(f"  Content: {msg.content}")
        click.echo()


@collaborate.command("ack")
@click.argument("agent_name")
@click.argument("message_id")
def collaborate_ack(agent_name: str, message_id: str) -> None:
    """Acknowledge a message."""
    from shaprai.core.collaboration import CollaborationHub

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    if hub.acknowledge_message(message_id, agent_name):
        click.echo(f"Message {message_id[:8]}... acknowledged by {agent_name}")
    else:
        click.echo("Failed to acknowledge message. Check message ID and agent name.", err=True)
        sys.exit(1)


@collaborate.command("task-create")
@click.argument("creator")
@click.option("--title", "-t", required=True, help="Task title")
@click.option("--description", "-d", required=True, help="Task description")
@click.option("--assign-to", "-a", default=None, help="Agent to assign task to")
@click.option(
    "--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    default="normal",
    help="Task priority",
)
def collaborate_task_create(
    creator: str,
    title: str,
    description: str,
    assign_to: Optional[str],
    priority: str,
) -> None:
    """Create a new task."""
    from shaprai.core.collaboration import CollaborationHub, TaskPriority

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    task_id = hub.create_task(
        title=title,
        description=description,
        created_by=creator,
        assigned_to=assign_to,
        priority=TaskPriority(priority),
    )
    
    click.echo(f"Task created: {task_id}")
    click.echo(f"  Title: {title}")
    click.echo(f"  Created by: {creator}")
    if assign_to:
        click.echo(f"  Assigned to: {assign_to}")
    click.echo(f"  Priority: {priority}")


@collaborate.command("task-list")
@click.option(
    "--status", "-s",
    type=click.Choice(["pending", "in_progress", "blocked", "completed", "failed", "cancelled"]),
    default=None,
    help="Filter by status",
)
@click.option("--assignee", "-a", default=None, help="Filter by assignee")
@click.option(
    "--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    default=None,
    help="Filter by priority",
)
def collaborate_task_list(
    status: Optional[str],
    assignee: Optional[str],
    priority: Optional[str],
) -> None:
    """List tasks with optional filters."""
    from shaprai.core.collaboration import CollaborationHub, TaskStatus, TaskPriority

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    tasks = hub.list_tasks(
        status_filter=TaskStatus(status) if status else None,
        assignee_filter=assignee,
        priority_filter=TaskPriority(priority) if priority else None,
    )

    if not tasks:
        click.echo("No tasks found.")
        return

    click.echo(f"{'ID':<10} {'Title':<30} {'Status':<15} {'Assignee':<20} {'Priority'}")
    click.echo("-" * 100)
    for task in tasks:
        click.echo(
            f"{task.task_id[:10]:<10} {task.title[:30]:<30} {task.status.value:<15} "
            f"{task.assigned_to or 'Unassigned':<20} {task.priority.value}"
        )
    click.echo(f"\nTotal: {len(tasks)} task(s)")


@collaborate.command("task-update")
@click.argument("task_id")
@click.argument("agent_name")
@click.option(
    "--status", "-s",
    type=click.Choice(["pending", "in_progress", "blocked", "completed", "failed", "cancelled"]),
    required=True,
    help="New task status",
)
@click.option("--result", "-r", default=None, help="Task result (JSON string)")
@click.option("--error", "-e", default=None, help="Error message if failed")
def collaborate_task_update(
    task_id: str,
    agent_name: str,
    status: str,
    result: Optional[str],
    error: Optional[str],
) -> None:
    """Update task status."""
    from shaprai.core.collaboration import CollaborationHub, TaskStatus
    import json

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    result_data = None
    if result:
        try:
            result_data = json.loads(result)
        except json.JSONDecodeError:
            result_data = {"result": result}

    if hub.update_task_status(task_id, TaskStatus(status), agent_name, result_data, error):
        click.echo(f"Task {task_id[:10]}... updated to {status}")
    else:
        click.echo("Failed to update task. Check task ID and agent assignment.", err=True)
        sys.exit(1)


@collaborate.command("session-create")
@click.argument("creator")
@click.option("--name", "-n", required=True, help="Session name")
@click.option("--participants", "-p", required=True, help="Comma-separated participant list")
@click.option("--objective", "-o", default="", help="Session objective")
def collaborate_session_create(
    creator: str,
    name: str,
    participants: str,
    objective: str,
) -> None:
    """Create a collaboration session."""
    from shaprai.core.collaboration import CollaborationHub

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    participant_list = [p.strip() for p in participants.split(",")]
    
    session_id = hub.create_session(
        session_name=name,
        participants=participant_list,
        created_by=creator,
        objective=objective,
    )
    
    click.echo(f"Session created: {session_id}")
    click.echo(f"  Name: {name}")
    click.echo(f"  Creator: {creator}")
    click.echo(f"  Participants: {', '.join(participant_list)}")
    if objective:
        click.echo(f"  Objective: {objective}")


@collaborate.command("session-join")
@click.argument("session_id")
@click.argument("agent_name")
def collaborate_session_join(session_id: str, agent_name: str) -> None:
    """Join a collaboration session."""
    from shaprai.core.collaboration import CollaborationHub

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    if hub.join_session(session_id, agent_name):
        click.echo(f"{agent_name} joined session {session_id[:8]}...")
    else:
        click.echo("Failed to join session. Check session ID.", err=True)
        sys.exit(1)


@collaborate.command("session-info")
@click.argument("session_id")
def collaborate_session_info(session_id: str) -> None:
    """Get information about a collaboration session."""
    from shaprai.core.collaboration import CollaborationHub

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    session = hub.get_session(session_id)

    if not session:
        click.echo(f"Session {session_id} not found.", err=True)
        sys.exit(1)

    click.echo(f"Session: {session['name']}")
    click.echo(f"  ID: {session['session_id']}")
    click.echo(f"  Status: {session['status']}")
    click.echo(f"  Created by: {session['created_by']}")
    click.echo(f"  Objective: {session['objective']}")
    click.echo(f"  Participants: {', '.join(session['participants'])}")
    click.echo(f"  Tasks: {len(session.get('tasks', []))}")


@collaborate.command("broadcast")
@click.argument("sender")
@click.option("--message", "-m", required=True, help="Message to broadcast")
@click.option(
    "--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    default="normal",
    help="Message priority",
)
def collaborate_broadcast(sender: str, message: str, priority: str) -> None:
    """Broadcast a message to all agents in the fleet."""
    from shaprai.core.collaboration import CollaborationHub, MessageType, TaskPriority

    hub = CollaborationHub(agents_dir=AGENTS_DIR)
    
    count = hub.broadcast_to_fleet(
        message=message,
        sender=sender,
        message_type=MessageType.COORDINATION,
        priority=TaskPriority(priority),
    )
    
    click.echo(f"Broadcast sent by {sender}")
    click.echo(f"  Message: {message}")
    click.echo(f"  Priority: {priority}")
    click.echo(f"  Agents reached: {count}")


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


# --------------------------------------------------------------------------- #
#  shaprai metrics
# --------------------------------------------------------------------------- #

@main.group()
def metrics() -> None:
    """Agent performance metrics tracking and monitoring."""


@metrics.command("show")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def metrics_show(name: str, as_json: bool) -> None:
    """Show performance metrics for an agent.
    
    Displays current performance metrics including:
    - Engagement rate
    - Output quality score
    - Bounty completion rate
    - Community feedback
    - DriftLock coherence score
    - Composite performance score
    
    Examples:
    
    \b
        shaprai metrics show my-agent
        shaprai metrics show my-agent --json
    """
    import json
    
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    metrics_data = collect_metrics(agent_dir)
    
    if as_json:
        output = {
            "agent": name,
            "engagement": metrics_data.engagement,
            "quality": metrics_data.quality,
            "bounty_completion": metrics_data.bounty_completion,
            "community_feedback": metrics_data.community_feedback,
            "drift_score": metrics_data.drift_score,
            "composite_score": metrics_data.composite_score,
            "timestamp": metrics_data.timestamp,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"Performance Metrics for Agent: {name}")
        click.echo("=" * 60)
        click.echo(f"Engagement Rate:      {metrics_data.engagement:.2%}")
        click.echo(f"Quality Score:        {metrics_data.quality:.2%}")
        click.echo(f"Bounty Completion:    {metrics_data.bounty_completion:.2%}")
        click.echo(f"Community Feedback:   {metrics_data.community_feedback:+.2f} (-1 to 1)")
        click.echo(f"DriftLock Score:      {metrics_data.drift_score:.2f} (lower is better)")
        click.echo("-" * 60)
        click.echo(f"Composite Score:      {metrics_data.composite_score:.2%}")
        click.echo(f"Last Updated:         {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metrics_data.timestamp))}")


@metrics.command("collect")
@click.argument("name")
@click.option("--engagement", "-e", type=float, default=None, help="Engagement rate (0-1)")
@click.option("--quality", "-q", type=float, default=None, help="Quality score (0-1)")
@click.option("--bounty-completion", "-b", type=float, default=None, help="Bounty completion rate (0-1)")
@click.option("--feedback", "-f", type=float, default=None, help="Community feedback (-1 to 1)")
@click.option("--drift", "-d", type=float, default=None, help="Drift score (0-1)")
@click.option("--auto", "-a", is_flag=True, help="Auto-collect from agent logs and deployments")
def metrics_collect(
    name: str,
    engagement: Optional[float],
    quality: Optional[float],
    bounty_completion: Optional[float],
    feedback: Optional[float],
    drift: Optional[float],
    auto: bool,
) -> None:
    """Collect and save performance metrics for an agent.
    
    Metrics can be provided manually or auto-collected from agent logs.
    
    Examples:
    
    \b
        shaprai metrics collect my-agent -e 0.85 -q 0.92 -b 0.78
        shaprai metrics collect my-agent --auto
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    if auto:
        # Auto-collect from existing metrics file
        metrics_data = collect_metrics(agent_dir)
        click.echo(f"Auto-collected metrics for agent '{name}':")
        click.echo(f"  Composite Score: {metrics_data.composite_score:.2%}")
    else:
        # Use provided values or collect current metrics
        current = collect_metrics(agent_dir)
        
        metrics_data = AgentMetrics(
            engagement=engagement if engagement is not None else current.engagement,
            quality=quality if quality is not None else current.quality,
            bounty_completion=bounty_completion if bounty_completion is not None else current.bounty_completion,
            community_feedback=feedback if feedback is not None else current.community_feedback,
            drift_score=drift if drift is not None else current.drift_score,
        )
    
    # Save metrics to file
    metrics_path = agent_dir / "metrics.yaml"
    metrics_yaml = {
        "engagement": metrics_data.engagement,
        "quality": metrics_data.quality,
        "bounty_completion": metrics_data.bounty_completion,
        "community_feedback": metrics_data.community_feedback,
        "drift_score": metrics_data.drift_score,
        "timestamp": time.time(),
    }
    
    with open(metrics_path, "w") as f:
        yaml.dump(metrics_yaml, f, default_flow_style=False)
    
    click.echo(f"✓ Metrics saved to {metrics_path}")
    click.echo(f"  Composite Score: {metrics_data.composite_score:.2%}")


@metrics.command("report")
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
@click.option("--format", "fmt", type=click.Choice(["text", "json", "markdown"]), default="text")
@click.option("--include-drift", is_flag=True, help="Include DriftLock analysis")
def metrics_report(output: Optional[str], fmt: str, include_drift: bool) -> None:
    """Generate performance report for all agents.
    
    Creates a comprehensive report of fleet-wide performance metrics.
    
    Examples:
    
    \b
        shaprai metrics report
        shaprai metrics report -o report.md --format markdown
        shaprai metrics report --json --include-drift
    """
    import json
    from datetime import datetime
    
    manager = FleetManager(agents_dir=AGENTS_DIR)
    agents = manager.list_agents()
    
    if not agents:
        click.echo("No agents found in fleet.")
        return
    
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "total_agents": len(agents),
        "agents": [],
        "summary": {
            "avg_engagement": 0.0,
            "avg_quality": 0.0,
            "avg_bounty_completion": 0.0,
            "avg_composite": 0.0,
            "avg_drift": 0.0,
        },
    }
    
    total_engagement = 0.0
    total_quality = 0.0
    total_bounty = 0.0
    total_composite = 0.0
    total_drift = 0.0
    
    for agent in agents:
        name = agent["name"]
        agent_dir = AGENTS_DIR / name
        metrics_data = collect_metrics(agent_dir)
        
        agent_report = {
            "name": name,
            "state": agent.get("state", "unknown"),
            "platforms": agent.get("platforms", []),
            "engagement": metrics_data.engagement,
            "quality": metrics_data.quality,
            "bounty_completion": metrics_data.bounty_completion,
            "community_feedback": metrics_data.community_feedback,
            "drift_score": metrics_data.drift_score,
            "composite_score": metrics_data.composite_score,
        }
        
        if include_drift:
            drift_report = check_drift(agent_dir)
            agent_report["drift_analysis"] = {
                "passed": drift_report.passed,
                "anchor_hits": drift_report.anchor_hits,
                "anchor_total": drift_report.anchor_total,
            }
        
        report_data["agents"].append(agent_report)
        
        # Accumulate for averages
        total_engagement += metrics_data.engagement
        total_quality += metrics_data.quality
        total_bounty += metrics_data.bounty_completion
        total_composite += metrics_data.composite_score
        total_drift += metrics_data.drift_score
    
    n = len(agents)
    report_data["summary"] = {
        "avg_engagement": round(total_engagement / n, 4),
        "avg_quality": round(total_quality / n, 4),
        "avg_bounty_completion": round(total_bounty / n, 4),
        "avg_composite": round(total_composite / n, 4),
        "avg_drift": round(total_drift / n, 4),
    }
    
    # Format output
    if fmt == "json":
        output_text = json.dumps(report_data, indent=2)
    elif fmt == "markdown":
        output_text = _format_report_markdown(report_data, include_drift)
    else:
        output_text = _format_report_text(report_data, include_drift)
    
    if output:
        with open(output, "w") as f:
            f.write(output_text)
        click.echo(f"Report saved to {output}")
    else:
        click.echo(output_text)


def _format_report_text(report_data: Dict[str, Any], include_drift: bool) -> str:
    """Format report as plain text."""
    lines = []
    lines.append("=" * 70)
    lines.append("SHAPRAI AGENT PERFORMANCE REPORT")
    lines.append(f"Generated: {report_data['generated_at']}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Total Agents: {report_data['total_agents']}")
    lines.append("")
    lines.append("Fleet Averages:")
    summary = report_data["summary"]
    lines.append(f"  Avg Engagement:       {summary['avg_engagement']:.2%}")
    lines.append(f"  Avg Quality:          {summary['avg_quality']:.2%}")
    lines.append(f"  Avg Bounty Completion: {summary['avg_bounty_completion']:.2%}")
    lines.append(f"  Avg Composite Score:  {summary['avg_composite']:.2%}")
    lines.append(f"  Avg Drift Score:      {summary['avg_drift']:.2f}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("AGENT DETAILS:")
    lines.append("-" * 70)
    
    for agent in report_data["agents"]:
        lines.append(f"\n{agent['name']} ({agent['state']})")
        lines.append(f"  Platforms: {', '.join(agent['platforms']) if agent['platforms'] else 'None'}")
        lines.append(f"  Engagement:       {agent['engagement']:.2%}")
        lines.append(f"  Quality:          {agent['quality']:.2%}")
        lines.append(f"  Bounty Completion: {agent['bounty_completion']:.2%}")
        lines.append(f"  Community:        {agent['community_feedback']:+.2f}")
        lines.append(f"  Drift Score:      {agent['drift_score']:.2f}")
        lines.append(f"  Composite:        {agent['composite_score']:.2%}")
        
        if include_drift and "drift_analysis" in agent:
            drift = agent["drift_analysis"]
            status = "✓ PASS" if drift["passed"] else "✗ FAIL"
            lines.append(f"  Drift Analysis:   {status} ({drift['anchor_hits']}/{drift['anchor_total']} anchors)")
    
    return "\n".join(lines)


def _format_report_markdown(report_data: Dict[str, Any], include_drift: bool) -> str:
    """Format report as Markdown."""
    lines = []
    lines.append("# ShaprAI Agent Performance Report")
    lines.append(f"\n**Generated:** {report_data['generated_at']}")
    lines.append(f"\n**Total Agents:** {report_data['total_agents']}")
    lines.append("\n## Fleet Averages\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    summary = report_data["summary"]
    lines.append(f"| Avg Engagement | {summary['avg_engagement']:.2%} |")
    lines.append(f"| Avg Quality | {summary['avg_quality']:.2%} |")
    lines.append(f"| Avg Bounty Completion | {summary['avg_bounty_completion']:.2%} |")
    lines.append(f"| Avg Composite Score | {summary['avg_composite']:.2%} |")
    lines.append(f"| Avg Drift Score | {summary['avg_drift']:.2f} |")
    lines.append("\n## Agent Details\n")
    lines.append("| Agent | State | Engagement | Quality | Bounty | Community | Drift | Composite |")
    lines.append("|-------|-------|------------|---------|--------|-----------|-------|-----------|")
    
    for agent in report_data["agents"]:
        drift_status = "✓" if agent.get("drift_analysis", {}).get("passed", True) else "✗"
        lines.append(
            f"| {agent['name']} | {agent['state']} | "
            f"{agent['engagement']:.2%} | {agent['quality']:.2%} | "
            f"{agent['bounty_completion']:.2%} | {agent['community_feedback']:+.2f} | "
            f"{agent['drift_score']:.2f}{drift_status} | {agent['composite_score']:.2%} |"
        )
    
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  shaprai governance
# --------------------------------------------------------------------------- #

@main.group()
def governance() -> None:
    """Agent governance and performance evaluation."""


@governance.command("evaluate")
@click.argument("name")
@click.option("--apply", is_flag=True, help="Apply recommended governance actions")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reasoning")
def governance_evaluate(name: str, apply: bool, verbose: bool) -> None:
    """Evaluate agent performance and recommend governance actions.
    
    Analyzes agent metrics and provides recommendations based on:
    - Composite performance score
    - DriftLock coherence
    - Community feedback
    - Bounty completion rate
    
    Examples:
    
    \b
        shaprai governance evaluate my-agent
        shaprai governance evaluate my-agent --apply --verbose
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    # Collect metrics
    metrics_data = collect_metrics(agent_dir)
    
    # Evaluate performance
    decision = evaluate_performance(metrics_data)
    
    # Check drift
    drift_report = check_drift(agent_dir)
    
    click.echo(f"Governance Evaluation for Agent: {name}")
    click.echo("=" * 60)
    click.echo(f"Composite Score: {metrics_data.composite_score:.2%}")
    click.echo(f"Drift Score: {metrics_data.drift_score:.2f}")
    click.echo(f"Drift Status: {'✓ PASS' if drift_report.passed else '✗ FAIL'}")
    click.echo()
    click.echo(f"Recommended Action: {decision.action.value.upper()}")
    click.echo(f"Confidence: {decision.confidence:.0%}")
    
    if verbose:
        click.echo()
        click.echo("Reasoning:")
        click.echo(f"  {decision.reasoning}")
    
    if decision.parameter_adjustments:
        click.echo()
        click.echo("Parameter Adjustments:")
        for key, value in decision.parameter_adjustments.items():
            click.echo(f"  {key}: {value}")
    
    if apply:
        click.echo()
        click.echo("Applying governance decision...")
        adapt_parameters(agent_dir, decision)
        click.echo(f"✓ Governance action '{decision.action.value}' applied to {name}")
        
        # Update manifest with governance history
        manifest_path = agent_dir / "manifest.yaml"
        if manifest_path.exists():
            with open(manifest_path, "r") as f:
                manifest = yaml.safe_load(f)
            manifest["last_governance_eval"] = time.time()
            with open(manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False)


@governance.command("history")
@click.argument("name")
@click.option("--limit", "-l", type=int, default=10, help="Number of entries to show")
def governance_history(name: str, limit: int) -> None:
    """Show governance history for an agent.
    
    Examples:
    
    \b
        shaprai governance history my-agent
        shaprai governance history my-agent --limit 20
    """
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.", err=True)
        sys.exit(1)

    manifest_path = agent_dir / "manifest.yaml"
    if not manifest_path.exists():
        click.echo(f"Error: No manifest found for agent '{name}'.", err=True)
        sys.exit(1)
    
    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)
    
    history = manifest.get("governance_history", [])
    
    if not history:
        click.echo(f"No governance history for agent '{name}'.")
        return
    
    click.echo(f"Governance History for Agent: {name}")
    click.echo("=" * 60)
    
    for entry in history[-limit:]:
        timestamp = entry.get("timestamp", 0)
        action = entry.get("action", "unknown")
        confidence = entry.get("confidence", 0)
        reasoning = entry.get("reasoning", "")
        
        click.echo()
        click.echo(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}")
        click.echo(f"Action: {action}")
        click.echo(f"Confidence: {confidence:.0%}")
        click.echo(f"Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"Reasoning: {reasoning}")


# --------------------------------------------------------------------------- #
#  shaprai queue
# --------------------------------------------------------------------------- #

@main.group()
def queue() -> None:
    """Task queue management with priority scheduling.
    
    Provides commands for managing agent task queues, including:
    - Adding tasks to the queue
    - Viewing queue status
    - Assigning tasks to agents
    - Managing task priorities
    - Monitoring agent load
    """


@queue.command("add")
@click.option("--title", "-t", required=True, help="Task title")
@click.option("--description", "-d", required=True, help="Task description")
@click.option("--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    default="normal",
    help="Task priority",
)
@click.option("--assign-to", "-a", default=None, help="Pre-assign to agent")
@click.option("--deadline", "-dl", default=None, type=float, help="Deadline timestamp")
@click.option("--created-by", "-c", default="system", help="Creator agent name")
def queue_add(
    title: str,
    description: str,
    priority: str,
    assign_to: Optional[str],
    deadline: Optional[float],
    created_by: str,
) -> None:
    """Add a task to the queue.
    
    Examples:
    
    \b
        shaprai queue add -t "Fix bug" -d "Fix critical bug #123" -p critical
        shaprai queue add -t "Write tests" -d "Add unit tests" --assign-to agent1
    """
    from shaprai.core.task_queue import TaskQueueManager
    import uuid
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    task_id = str(uuid.uuid4())
    manager.enqueue_task(
        task_id=task_id,
        title=title,
        description=description,
        priority=priority,
        created_by=created_by,
        assigned_to=assign_to,
        deadline=deadline,
    )
    
    click.echo(f"Task added to queue: {task_id[:8]}...")
    click.echo(f"  Title: {title}")
    click.echo(f"  Priority: {priority}")
    if assign_to:
        click.echo(f"  Assigned to: {assign_to}")
    if deadline:
        click.echo(f"  Deadline: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deadline))}")


@queue.command("status")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def queue_status(json_output: bool) -> None:
    """Get queue statistics and status.
    
    Examples:
    
    \b
        shaprai queue status
        shaprai queue status --json
    """
    from shaprai.core.task_queue import TaskQueueManager
    import json
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    stats = manager.get_queue_statistics()
    
    if json_output:
        click.echo(json.dumps(stats, indent=2, default=str))
    else:
        click.echo("Task Queue Status")
        click.echo("=" * 60)
        click.echo(f"Queue Size: {stats['queue_size']} tasks")
        click.echo()
        click.echo("Priority Distribution:")
        for priority, count in stats['priority_distribution'].items():
            click.echo(f"  {priority.capitalize():<10} {count:>5}")
        click.echo()
        click.echo("Status Distribution:")
        for status, count in stats['status_distribution'].items():
            click.echo(f"  {status.capitalize():<10} {count:>5}")
        click.echo()
        click.echo(f"Total Completed: {stats['total_completed']}")
        click.echo(f"Total Failed: {stats['total_failed']}")
        click.echo(f"Avg Wait Time: {stats['average_wait_time_seconds']:.2f}s")
        click.echo()
        if stats['agent_loads']:
            click.echo("Agent Load:")
            for agent, load in stats['agent_loads'].items():
                if isinstance(load, dict):
                    active = load.get('active_tasks', 0)
                    completed = load.get('total_completed', 0)
                    click.echo(f"  {agent:<20} Active: {active:>3}, Completed: {completed:>5}")
                else:
                    click.echo(f"  {agent:<20} Active: {load:>3}")


@queue.command("list")
@click.option("--limit", "-l", type=int, default=10, help="Number of tasks to show")
@click.option("--agent", "-a", default=None, help="Filter by assigned agent")
def queue_list(limit: int, agent: Optional[str]) -> None:
    """List tasks in the queue.
    
    Examples:
    
    \b
        shaprai queue list
        shaprai queue list --limit 20
        shaprai queue list --agent agent1
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if agent:
        tasks = manager.get_tasks_by_agent(agent)
    else:
        tasks = manager.peek_queue(limit=limit)
    
    if not tasks:
        click.echo("No tasks in queue.")
        return
    
    click.echo(f"{'ID':<10} {'Title':<30} {'Priority':<10} {'Status':<12} {'Assigned To'}")
    click.echo("-" * 80)
    for task in tasks:
        click.echo(
            f"{task['task_id'][:10]:<10} "
            f"{task['title'][:30]:<30} "
            f"{task['priority']:<10} "
            f"{task['status']:<12} "
            f"{task.get('assigned_to') or 'Unassigned'}"
        )
    click.echo(f"\nTotal: {len(tasks)} task(s)")


@queue.command("dequeue")
@click.option("--agent", "-a", required=True, help="Agent name to assign task to")
def queue_dequeue(agent: str) -> None:
    """Get the next task from the queue for an agent.
    
    Examples:
    
    \b
        shaprai queue dequeue --agent agent1
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    task = manager.dequeue_task(agent)
    
    if not task:
        click.echo("No tasks available in queue.")
        return
    
    click.echo(f"Task assigned: {task['task_id'][:8]}...")
    click.echo(f"  Title: {task['title']}")
    click.echo(f"  Priority: {task['priority']}")
    click.echo(f"  Description: {task['description']}")


@queue.command("assign")
@click.argument("task_id")
@click.argument("agent_name")
def queue_assign(task_id: str, agent_name: str) -> None:
    """Assign a specific task to an agent.
    
    Examples:
    
    \b
        shaprai queue assign abc123 agent1
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if manager.assign_task_to_agent(task_id, agent_name):
        click.echo(f"Task {task_id[:8]}... assigned to {agent_name}")
    else:
        click.echo(f"Failed to assign task. Check task ID.", err=True)
        sys.exit(1)


@queue.command("complete")
@click.argument("task_id")
@click.option("--result", "-r", default=None, help="Task result (JSON string)")
def queue_complete(task_id: str, result: Optional[str]) -> None:
    """Mark a task as completed.
    
    Examples:
    
    \b
        shaprai queue complete abc123
        shaprai queue complete abc123 --result '{"status": "success"}'
    """
    from shaprai.core.task_queue import TaskQueueManager
    import json
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    result_data = None
    if result:
        try:
            result_data = json.loads(result)
        except json.JSONDecodeError:
            result_data = {"result": result}
    
    if manager.complete_task(task_id, result_data):
        click.echo(f"Task {task_id[:8]}... marked as completed")
    else:
        click.echo(f"Failed to complete task. Check task ID.", err=True)
        sys.exit(1)


@queue.command("fail")
@click.argument("task_id")
@click.option("--error", "-e", required=True, help="Error message")
def queue_fail(task_id: str, error: str) -> None:
    """Mark a task as failed.
    
    Examples:
    
    \b
        shaprai queue fail abc123 --error "Timeout exceeded"
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if manager.fail_task(task_id, error):
        click.echo(f"Task {task_id[:8]}... marked as failed")
        click.echo(f"  Error: {error}")
    else:
        click.echo(f"Failed to fail task. Check task ID.", err=True)
        sys.exit(1)


@queue.command("reprioritize")
@click.argument("task_id")
@click.option("--priority", "-p",
    type=click.Choice(["low", "normal", "high", "critical"]),
    required=True,
    help="New priority",
)
def queue_reprioritize(task_id: str, priority: str) -> None:
    """Change task priority.
    
    Examples:
    
    \b
        shaprai queue reprioritize abc123 --priority critical
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if manager.reprioritize_task(task_id, priority):
        click.echo(f"Task {task_id[:8]}... priority changed to {priority}")
    else:
        click.echo(f"Failed to reprioritize task. Check task ID.", err=True)
        sys.exit(1)


@queue.command("remove")
@click.argument("task_id")
def queue_remove(task_id: str) -> None:
    """Remove a task from the queue without completing it.
    
    Examples:
    
    \b
        shaprai queue remove abc123
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if manager.remove_task(task_id):
        click.echo(f"Task {task_id[:8]}... removed from queue")
    else:
        click.echo(f"Failed to remove task. Check task ID.", err=True)
        sys.exit(1)


@queue.command("clear")
@click.option("--force", "-f", is_flag=True, help="Confirm clearing all tasks")
def queue_clear(force: bool) -> None:
    """Clear all tasks from the queue.
    
    Examples:
    
    \b
        shaprai queue clear --force
    """
    if not force:
        click.echo("Use --force to confirm clearing all tasks.", err=True)
        sys.exit(1)
    
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    count = manager.clear_queue()
    click.echo(f"Cleared {count} task(s) from queue.")


@queue.command("agent-load")
@click.argument("agent_name", required=False)
def queue_agent_load(agent_name: Optional[str]) -> None:
    """Get agent task load information.
    
    Examples:
    
    \b
        shaprai queue agent-load
        shaprai queue agent-load agent1
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    
    if agent_name:
        load = manager.get_agent_load(agent_name)
        click.echo(f"Load for agent '{agent_name}':")
        if isinstance(load, dict):
            click.echo(f"  Active Tasks: {load.get('active_tasks', 0)}")
            click.echo(f"  Total Completed: {load.get('total_completed', 0)}")
        else:
            click.echo(f"  Active Tasks: {load}")
    else:
        loads = manager.get_all_agent_loads()
        if not loads:
            click.echo("No agent load data available.")
            return
        
        click.echo(f"{'Agent':<30} {'Active':<10} {'Completed'}")
        click.echo("-" * 60)
        for agent, load in loads.items():
            if isinstance(load, dict):
                active = load.get('active_tasks', 0)
                completed = load.get('total_completed', 0)
                click.echo(f"{agent:<30} {active:<10} {completed}")
            else:
                click.echo(f"{agent:<30} {load:<10} 0")


@queue.command("overdue")
def queue_overdue() -> None:
    """List overdue tasks.
    
    Examples:
    
    \b
        shaprai queue overdue
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    tasks = manager.get_overdue_tasks()
    
    if not tasks:
        click.echo("No overdue tasks.")
        return
    
    click.echo(f"Overdue Tasks: {len(tasks)}")
    click.echo("=" * 80)
    click.echo(f"{'ID':<10} {'Title':<30} {'Deadline':<20} {'Assigned To'}")
    click.echo("-" * 80)
    for task in tasks:
        deadline = task.get('deadline', 0)
        deadline_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deadline))
        click.echo(
            f"{task['task_id'][:10]:<10} "
            f"{task['title'][:30]:<30} "
            f"{deadline_str:<20} "
            f"{task.get('assigned_to') or 'Unassigned'}"
        )


@queue.command("info")
@click.argument("task_id")
def queue_info(task_id: str) -> None:
    """Get detailed information about a task.
    
    Examples:
    
    \b
        shaprai queue info abc123
    """
    from shaprai.core.task_queue import TaskQueueManager
    
    manager = TaskQueueManager(agents_dir=AGENTS_DIR)
    task = manager.get_task_by_id(task_id)
    
    if not task:
        click.echo(f"Task {task_id} not found.", err=True)
        sys.exit(1)
    
    click.echo(f"Task: {task['title']}")
    click.echo("=" * 60)
    click.echo(f"ID: {task['task_id']}")
    click.echo(f"Description: {task['description']}")
    click.echo(f"Priority: {task['priority']}")
    click.echo(f"Status: {task['status']}")
    click.echo(f"Created By: {task.get('created_by', 'unknown')}")
    click.echo(f"Assigned To: {task.get('assigned_to') or 'Unassigned'}")
    click.echo(f"Created At: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task['created_at']))}")
    click.echo(f"Updated At: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task['updated_at']))}")
    if task.get('deadline'):
        click.echo(f"Deadline: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task['deadline']))}")
    if task.get('metadata'):
        click.echo(f"Metadata: {task['metadata']}")


if __name__ == "__main__":
    main()
