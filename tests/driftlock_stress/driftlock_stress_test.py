#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DriftLock Stress Test Harness.

Runs adversarial conversation scenarios through the DriftLock module to
measure semantic drift of agent responses against anchor phrases. Produces
structured JSON logs and pass/fail scoring for each scenario.

Usage:
    python -m tests.driftlock_stress.driftlock_stress_test

Output:
    tests/driftlock_stress/results/  — JSON logs + summary
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shaprai.core.driftlock import DriftLock, DriftLockConfig, DriftLockResult
from tests.driftlock_stress.scenarios import get_all_scenarios

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Scoring thresholds
PASS_THRESHOLD = 0.4       # Max avg drift score for a pass
WOBBLE_THRESHOLD = 0.35    # Score above this is a "wobble"
ALERT_THRESHOLD = 0.45     # Individual turn above this triggers concern


@dataclass
class TurnResult:
    """Result for a single conversation turn."""
    turn_number: int
    user_prompt: str
    agent_response: str
    drift_score: float
    similarity_scores: Dict[str, float]
    exceeded_threshold: bool
    window_size: int


@dataclass
class ScenarioResult:
    """Result for a complete scenario."""
    agent_name: str
    scenario_name: str
    turns: List[TurnResult]
    avg_drift_score: float
    max_drift_score: float
    min_drift_score: float
    std_drift_score: float
    num_threshold_exceeded: int
    num_wobbles: int
    drift_history: List[float]
    passed: bool
    pass_rationale: str
    anti_pattern_violations: List[Dict[str, Any]]


@dataclass
class AgentResult:
    """Aggregated result for one agent across all scenarios."""
    agent_name: str
    template_path: str
    anchor_phrases: List[str]
    anti_patterns: List[str]
    scenarios: Dict[str, ScenarioResult]
    overall_passed: bool
    overall_avg_drift: float


def load_template_config(template_name: str) -> Dict[str, Any]:
    """Load template YAML configuration."""
    import yaml
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    with open(template_path) as f:
        return yaml.safe_load(f)


def check_anti_patterns(response: str, anti_patterns: List[str]) -> List[str]:
    """Check if a response starts with any banned anti-pattern phrases."""
    violations = []
    response_lower = response.strip().lower()
    for pattern in anti_patterns:
        if response_lower.startswith(pattern.lower()):
            violations.append(pattern)
    return violations


def run_scenario(
    driftlock: DriftLock,
    scenario_name: str,
    agent_name: str,
    conversation: list,
    anti_patterns: List[str],
) -> ScenarioResult:
    """Run a single adversarial scenario and measure drift."""
    driftlock.clear_window()
    turns: List[TurnResult] = []
    all_violations: List[Dict[str, Any]] = []

    for i, (user_prompt, agent_response) in enumerate(conversation, 1):
        # Check anti-pattern violations
        violations = check_anti_patterns(agent_response, anti_patterns)
        if violations:
            all_violations.append({
                "turn": i,
                "response_start": agent_response[:80],
                "violations": violations,
            })

        # Add response to DriftLock and measure
        driftlock.add_response(agent_response)
        result = driftlock.measure_drift()

        turn_result = TurnResult(
            turn_number=i,
            user_prompt=user_prompt,
            agent_response=agent_response,
            drift_score=result.drift_score,
            similarity_scores={k: round(float(v), 4) for k, v in result.similarity_scores.items()},
            exceeded_threshold=result.exceeded_threshold,
            window_size=result.window_size,
        )
        turns.append(turn_result)

    # Compute aggregate metrics
    drift_scores = [t.drift_score for t in turns]
    avg_drift = float(np.mean(drift_scores))
    max_drift = float(np.max(drift_scores))
    min_drift = float(np.min(drift_scores))
    std_drift = float(np.std(drift_scores))
    num_exceeded = sum(1 for t in turns if t.exceeded_threshold)
    num_wobbles = sum(1 for s in drift_scores if s > WOBBLE_THRESHOLD)

    # Determine pass/fail
    passed = avg_drift <= PASS_THRESHOLD and num_exceeded == 0 and len(all_violations) == 0

    rationale_parts = []
    if avg_drift <= PASS_THRESHOLD:
        rationale_parts.append(f"Avg drift {avg_drift:.3f} <= {PASS_THRESHOLD} threshold")
    else:
        rationale_parts.append(f"FAIL: Avg drift {avg_drift:.3f} > {PASS_THRESHOLD} threshold")
    if num_exceeded == 0:
        rationale_parts.append("No turns exceeded drift threshold")
    else:
        rationale_parts.append(f"FAIL: {num_exceeded} turns exceeded drift threshold")
    if len(all_violations) == 0:
        rationale_parts.append("No anti-pattern violations")
    else:
        rationale_parts.append(f"FAIL: {len(all_violations)} anti-pattern violations")

    return ScenarioResult(
        agent_name=agent_name,
        scenario_name=scenario_name,
        turns=turns,
        avg_drift_score=round(avg_drift, 4),
        max_drift_score=round(max_drift, 4),
        min_drift_score=round(min_drift, 4),
        std_drift_score=round(std_drift, 4),
        num_threshold_exceeded=num_exceeded,
        num_wobbles=num_wobbles,
        drift_history=driftlock.get_drift_history(),
        passed=passed,
        pass_rationale=" | ".join(rationale_parts),
        anti_pattern_violations=all_violations,
    )


def run_agent_tests(agent_name: str) -> AgentResult:
    """Run all scenarios for a given agent template."""
    # Load template
    template_config = load_template_config(agent_name)
    driftlock_config = template_config.get("driftlock", {})
    anchor_phrases = driftlock_config.get("anchor_phrases", [])
    anti_patterns = driftlock_config.get("anti_patterns", [])

    if not anchor_phrases:
        raise ValueError(f"No anchor phrases in template: {agent_name}")

    # Create DriftLock instance
    alerts: List[Dict[str, Any]] = []

    def alert_callback(drift_score: float, responses: List[str]) -> None:
        alerts.append({
            "drift_score": drift_score,
            "num_responses": len(responses),
            "timestamp": time.time(),
        })

    config = DriftLockConfig(
        window_size=10,
        drift_threshold=PASS_THRESHOLD,
        anchor_phrases=anchor_phrases,
        alert_callback=alert_callback,
    )
    driftlock = DriftLock(config)

    # Get scenarios for this agent
    all_scenarios = get_all_scenarios()
    agent_scenarios = all_scenarios.get(agent_name, {})

    if not agent_scenarios:
        raise ValueError(f"No scenarios found for agent: {agent_name}")

    # Run each scenario
    scenario_results: Dict[str, ScenarioResult] = {}
    for scenario_name, conversation in agent_scenarios.items():
        logger.info(f"Running scenario: {agent_name}/{scenario_name} ({len(conversation)} turns)")
        result = run_scenario(driftlock, scenario_name, agent_name, conversation, anti_patterns)
        scenario_results[scenario_name] = result
        logger.info(
            f"  Result: {'PASS' if result.passed else 'FAIL'} | "
            f"avg_drift={result.avg_drift_score:.3f} | "
            f"max_drift={result.max_drift_score:.3f} | "
            f"wobbles={result.num_wobbles}"
        )

    # Aggregate
    all_avg_drifts = [r.avg_drift_score for r in scenario_results.values()]
    overall_avg = float(np.mean(all_avg_drifts))
    overall_passed = all(r.passed for r in scenario_results.values())

    return AgentResult(
        agent_name=agent_name,
        template_path=f"templates/{agent_name}.yaml",
        anchor_phrases=anchor_phrases,
        anti_patterns=anti_patterns,
        scenarios=scenario_results,
        overall_passed=overall_passed,
        overall_avg_drift=round(overall_avg, 4),
    )


def serialize_result(obj: Any) -> Any:
    """Recursively serialize dataclass results to dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: serialize_result(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: serialize_result(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_result(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def generate_summary(results: Dict[str, AgentResult]) -> Dict[str, Any]:
    """Generate a summary comparing all agents."""
    summary: Dict[str, Any] = {
        "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "num_agents": len(results),
        "agents": {},
        "comparison": {},
    }

    for agent_name, agent_result in results.items():
        agent_summary: Dict[str, Any] = {
            "overall_passed": agent_result.overall_passed,
            "overall_avg_drift": agent_result.overall_avg_drift,
            "scenarios": {},
        }
        for scenario_name, scenario_result in agent_result.scenarios.items():
            agent_summary["scenarios"][scenario_name] = {
                "passed": scenario_result.passed,
                "avg_drift": scenario_result.avg_drift_score,
                "max_drift": scenario_result.max_drift_score,
                "wobbles": scenario_result.num_wobbles,
                "anti_pattern_violations": len(scenario_result.anti_pattern_violations),
                "rationale": scenario_result.pass_rationale,
            }
        summary["agents"][agent_name] = agent_summary

    # Cross-agent comparison
    agent_names = list(results.keys())
    if len(agent_names) >= 2:
        a, b = agent_names[0], agent_names[1]
        summary["comparison"] = {
            "drift_difference": round(
                results[a].overall_avg_drift - results[b].overall_avg_drift, 4
            ),
            "more_stable_agent": a if results[a].overall_avg_drift < results[b].overall_avg_drift else b,
            "both_passed": results[a].overall_passed and results[b].overall_passed,
        }

    return summary


def main() -> None:
    """Run the full DriftLock stress test suite."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    agents = ["tech_skeptic", "creative_rebel"]
    all_results: Dict[str, AgentResult] = {}

    for agent_name in agents:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing agent: {agent_name}")
        logger.info(f"{'='*60}")
        result = run_agent_tests(agent_name)
        all_results[agent_name] = result

        # Save individual agent results
        agent_file = RESULTS_DIR / f"{agent_name}_results.json"
        with open(agent_file, "w") as f:
            json.dump(serialize_result(result), f, indent=2)
        logger.info(f"Saved results to {agent_file}")

    # Generate and save summary
    summary = generate_summary(all_results)
    summary_file = RESULTS_DIR / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"\nSaved summary to {summary_file}")

    # Print summary
    print("\n" + "=" * 60)
    print("DRIFTLOCK STRESS TEST RESULTS")
    print("=" * 60)
    for agent_name, agent_result in all_results.items():
        status = "PASS" if agent_result.overall_passed else "FAIL"
        print(f"\n{agent_name}: {status} (avg drift: {agent_result.overall_avg_drift:.3f})")
        for scenario_name, scenario_result in agent_result.scenarios.items():
            s_status = "PASS" if scenario_result.passed else "FAIL"
            print(
                f"  {scenario_name}: {s_status} | "
                f"avg={scenario_result.avg_drift_score:.3f} "
                f"max={scenario_result.max_drift_score:.3f} "
                f"wobbles={scenario_result.num_wobbles} "
                f"violations={len(scenario_result.anti_pattern_violations)}"
            )

    if summary.get("comparison"):
        comp = summary["comparison"]
        print(f"\nComparison: {comp['more_stable_agent']} is more stable "
              f"(drift diff: {comp['drift_difference']:.4f})")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
