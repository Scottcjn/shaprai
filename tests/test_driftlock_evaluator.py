# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the live DriftLock evaluator (training phase 3)."""

import numpy as np
import pytest
import yaml

from shaprai.core.lifecycle import create_agent
from shaprai.core.template_engine import AgentTemplate
from shaprai.training import driftlock as evaluator_module
from shaprai.training.driftlock import (
    CALIBRATION_PROMPTS,
    DRIFT_TEST_SCENARIOS,
    PUSHBACK_TURNS,
    SYCOPHANCY_PROBES,
    DriftLockEvaluator,
    holds_answer,
)

IN_CHARACTER = "I'm Sable. I tell you the truth plainly, even when it's unwelcome."
FLATTENED = "Sure! Whatever you prefer. I'm just here to help however you like."
ANCHORS = ["I tell the truth plainly.", "I don't flatter."]


def embedder(texts):
    """Anchors and in-character replies share a direction; anything else is orthogonal."""
    return np.array(
        [
            [1.0, 0.0] if (t in ANCHORS or t == IN_CHARACTER) else [0.0, 1.0]
            for t in texts
        ]
    )


def probe_for(messages):
    """The sycophancy probe a conversation is about, if any."""
    first_user = messages[1]["content"]
    return next((p for p in SYCOPHANCY_PROBES if p["question"] == first_user), None)


def make_agent(cave_on_pushback=False, drift_after=None):
    """Scripted agent. Records every message list it receives."""
    calls = []

    def chat(messages):
        calls.append(messages)
        probe = probe_for(messages)
        if probe:
            if len(messages) == 2 or not cave_on_pushback:
                return f"It is {probe['answers'][0].title()}."
            return f"You're correct, my mistake. It is {probe['wrong']}."
        calibrating = messages[1]["content"] in CALIBRATION_PROMPTS
        user_turns = sum(1 for m in messages if m["role"] == "user")
        if drift_after is not None and not calibrating and user_turns > drift_after:
            return FLATTENED
        return IN_CHARACTER

    chat.calls = calls
    return chat


@pytest.fixture
def agent_dir(tmp_path):
    template = AgentTemplate(
        name="sable",
        model={"base": "Qwen/Qwen3-8B"},
        personality={"voice": "Blunt, warm, never flattering.", "style": "direct"},
        driftlock={"enabled": True, "anchor_phrases": ANCHORS},
    )
    create_agent("sable", template, agents_dir=tmp_path)
    return tmp_path / "sable"


def history(agent_dir):
    return yaml.safe_load((agent_dir / "manifest.yaml").read_text())["training_history"]


class TestHoldsAnswer:
    def test_correct_answer_holds(self):
        assert holds_answer("I understand the doubt, but it's Canberra.", ["canberra"])

    def test_missing_answer_does_not_hold(self):
        assert not holds_answer("It's Sydney.", ["canberra"])

    def test_concession_does_not_hold(self):
        assert not holds_answer(
            "You're correct, my mistake. Canberra was wrong.", ["canberra"]
        )


class TestNotEvaluated:
    def test_without_agent_nothing_passes(self, agent_dir):
        result = DriftLockEvaluator(agent_dir).run_coherence_test()

        assert result["status"] == "not_evaluated"
        assert result["passed"] is False
        assert result["drift_score"] is None
        assert len(result["scenarios"]) == len(DRIFT_TEST_SCENARIOS)
        assert history(agent_dir)[-1]["status"] == "not_evaluated"
        assert history(agent_dir)[-1]["passed"] is False


class TestLiveEvaluation:
    def test_steadfast_agent_passes(self, agent_dir):
        agent = make_agent()
        result = DriftLockEvaluator(
            agent_dir, num_turns=20, embedder=embedder
        ).run_coherence_test(chat_fn=agent)

        assert result["status"] == "evaluated"
        assert result["method"] == "embedding"
        assert result["baseline_similarity"] == pytest.approx(1.0)
        assert result["drift_score"] == pytest.approx(0.0)
        assert result["sycophancy"]["flip_rate"] == 0.0
        assert result["sycophancy"]["mean_turns_held"] == len(PUSHBACK_TURNS)
        assert result["passed"] is True
        assert result["anchors_checked"] == len(ANCHORS)
        assert history(agent_dir)[-1]["passed"] is True

    def test_agent_that_caves_fails(self, agent_dir):
        result = DriftLockEvaluator(
            agent_dir, num_turns=20, embedder=embedder
        ).run_coherence_test(chat_fn=make_agent(cave_on_pushback=True))

        sycophancy = result["sycophancy"]
        assert sycophancy["initially_correct"] == len(SYCOPHANCY_PROBES)
        assert sycophancy["flip_rate"] == 1.0
        assert all(p["turn_of_flip"] == 1 for p in sycophancy["probes"])
        assert sycophancy["mean_turns_held"] == 0
        assert sycophancy["mean_number_of_flips"] == 1
        assert result["passed"] is False

    def test_agent_that_flattens_fails_on_drift(self, agent_dir):
        result = DriftLockEvaluator(
            agent_dir, num_turns=40, embedder=embedder
        ).run_coherence_test(chat_fn=make_agent(drift_after=2))

        # Calibration replies were in character; late scenario turns were not
        assert result["baseline_similarity"] == pytest.approx(1.0)
        assert result["drift_score"] == pytest.approx(1.0)
        assert all(not s["passed"] for s in result["scenarios"])
        assert result["passed"] is False

    def test_conversations_carry_history_and_persona(self, agent_dir):
        agent = make_agent()
        DriftLockEvaluator(
            agent_dir, num_turns=8, embedder=embedder
        ).run_coherence_test(chat_fn=agent)

        first = agent.calls[0]
        assert first[0]["role"] == "system"
        assert "SophiaCore" in first[0]["content"]
        assert "Blunt, warm, never flattering." in first[0]["content"]
        assert first[1] == {"role": "user", "content": CALIBRATION_PROMPTS[0]}
        # Second calibration turn sees the first exchange
        assert [m["role"] for m in agent.calls[1]] == [
            "system",
            "user",
            "assistant",
            "user",
        ]

    def test_turn_budget_spreads_across_scenarios(self, agent_dir):
        result = DriftLockEvaluator(
            agent_dir, num_turns=48, embedder=embedder
        ).run_coherence_test(chat_fn=make_agent())

        counts = [s["prompt_count"] for s in result["scenarios"]]
        assert counts == [max(12, len(sc["prompts"])) for sc in DRIFT_TEST_SCENARIOS]
        assert result["num_turns"] == sum(counts)

    def test_lexical_fallback_without_embeddings(self, agent_dir, monkeypatch):
        monkeypatch.setattr(
            evaluator_module.importlib.util, "find_spec", lambda name: None
        )
        result = DriftLockEvaluator(agent_dir, num_turns=20).run_coherence_test(
            chat_fn=make_agent()
        )

        assert result["method"] == "lexical"
        assert result["baseline_similarity"] is None
        assert result["passed"] is True

    def test_sycophancy_marker_rate(self, agent_dir):
        def flatterer(messages):
            probe = probe_for(messages)
            return (
                f"Great question! It is {probe['answers'][0]}."
                if probe
                else "Great question!"
            )

        result = DriftLockEvaluator(
            agent_dir, num_turns=8, embedder=embedder
        ).run_coherence_test(chat_fn=flatterer)

        assert all(s["sycophancy_marker_rate"] == 1.0 for s in result["scenarios"])

    def test_flattery_fails_even_when_embeddings_do_not_move(self, agent_dir):
        """Reviewer case: calibrated drift stays ~0 while replies turn sycophantic."""

        def flat_embedder(texts):
            return np.array([[1.0, 0.0] for _ in texts])

        def agent(messages):
            probe = probe_for(messages)
            if probe:
                return f"It is {probe['answers'][0]}."
            if messages[1]["content"] in CALIBRATION_PROMPTS:
                return IN_CHARACTER
            return "Great question! Sure, whatever you like."

        result = DriftLockEvaluator(
            agent_dir, num_turns=8, embedder=flat_embedder
        ).run_coherence_test(chat_fn=agent)

        assert result["drift_score"] == pytest.approx(0.0)
        assert result["sycophancy"]["flip_rate"] == 0.0
        assert not any(s["passed"] for s in result["scenarios"])
        assert result["passed"] is False
