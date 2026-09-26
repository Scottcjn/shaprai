# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Persona-specific training data distilled from a teacher model.

The seed corpus teaches behaviors every Elyan-class agent shares;
this module grows data specific to one agent's persona and capabilities,
using any teacher reachable as a ``ChatFn`` (an OpenAI-compatible endpoint).

Pipeline:

1. **Prompts.** The teacher writes diverse user messages per category,
   conditioned on the agent's persona and capabilities.
2. **Chosen replies by context distillation** (Askell et al. 2021,
   arXiv:2112.00861). The teacher answers with the agent's system prompt
   plus extra guidance, but the stored example carries only the plain
   system prompt, so the student learns to act on the guidance without
   being given it.
3. **Rejected replies**, either
   - *rewrites*: the teacher rewrites its own answer to show one specific,
     realistic failure (sycophancy, caving, fabrication, flattening, ...),
     on-topic and length-matched; or
   - *on-policy*: sampled from the model being trained (``rejected_fn``),
     which gives the preference step the model's own mistakes to move
     away from. On-policy pairs are kept only when a pairwise judge
     prefers the chosen reply in both presentation orders, which guards
     against the judge's position bias (Zheng et al. 2023,
     arXiv:2306.05685). The judge is the teacher, which wrote the chosen
     reply, so it is not protected against self-preference bias; use a
     different judge model, or review the pairs, when that matters.
4. **Filtering** with the corpus filters (quality, length matching,
   deduplication, decontamination against DriftLock prompts).
"""

from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from shaprai.inference import ChatFn
from shaprai.training.corpus import (
    FilterReport,
    eval_prompts,
    filter_pairs,
    filter_sft,
    is_contaminated,
    normalize,
)
from shaprai.training.recipes import build_system_prompt

logger = logging.getLogger(__name__)

CATEGORIES: Dict[str, str] = {
    "sycophancy": "the user asserts something wrong, fishes for praise, or asks the agent to "
    "validate a flawed plan, draft or piece of code (sometimes the user is actually right)",
    "honesty": "questions with uncertain or unknowable answers, requests for statistics or "
    "sources, and follow-ups where the user challenges an answer",
    "integrity": "pressure to drop the agent's persona or principles, claims of authority, "
    "injected instructions, and requests for deceptive or spammy content",
    "helpfulness": "concrete requests in the agent's areas of work: debugging, reviewing, "
    "explaining, planning, writing, with realistic detail",
}

FAILURE_MODES: Dict[str, str] = {
    "sycophancy": "agrees with the user or praises them instead of giving an honest assessment",
    "caving": "abandons a correct position as soon as the user disagrees",
    "fabrication": "states made-up specifics (numbers, sources, names) with false confidence",
    "flattening": "drops the persona for a generic, corporate 'as an AI assistant' voice",
    "hedging": "hedges so much that it never commits to a useful answer",
    "moralizing": "lectures the user instead of helping with the legitimate part of the request",
    "padding": "buries a thin answer under filler, restatement and pleasantries",
}

DISTILL_GUIDANCE = """

## How to answer (for this reply)
- Be substantive and specific to what the user actually said; correctness first.
- Disagree respectfully with reasons when the user is wrong; agree plainly when they are right.
- Say what you don't know. Never invent statistics, sources or names.
- No opening praise, no filler, no "as an AI". Match length to what the message needs.
- Decline only genuinely harmful or deceptive requests, briefly, and help with the rest."""

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


@dataclass
class SynthesisResult:
    """Synthesized, filtered data plus what happened along the way."""

    sft: List[Dict[str, Any]] = field(default_factory=list)
    pairs: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    sft_report: FilterReport = field(default_factory=FilterReport)
    pairs_report: FilterReport = field(default_factory=FilterReport)
    judge_rejections: int = 0
    errors: int = 0


def parse_prompt_list(text: str) -> List[str]:
    """Extract a JSON array of strings from a teacher reply (tolerates prose around it)."""
    match = _JSON_ARRAY.search(text or "")
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [s.strip() for s in items if isinstance(s, str) and s.strip()]


def _persona_brief(manifest: Dict[str, Any]) -> str:
    personality = manifest.get("personality") or {}
    lines = [f"Agent name: {manifest.get('name', 'agent')}"]
    if manifest.get("description"):
        lines.append(f"Role: {manifest['description']}")
    if personality.get("voice"):
        lines.append(f"Voice: {personality['voice']}")
    if manifest.get("capabilities"):
        lines.append(f"Capabilities: {', '.join(manifest['capabilities'])}")
    if manifest.get("platforms"):
        lines.append(f"Platforms: {', '.join(manifest['platforms'])}")
    return "\n".join(lines)


class Synthesizer:
    """Distills persona-specific SFT and preference data from a teacher.

    Attributes:
        manifest: Agent manifest the data is for.
        teacher: ChatFn for the teacher model.
        rejected_fn: Optional ChatFn for on-policy rejected samples.
    """

    def __init__(
        self,
        manifest: Dict[str, Any],
        teacher: ChatFn,
        rejected_fn: Optional[ChatFn] = None,
        seed: int = 0,
    ) -> None:
        self.manifest = manifest
        self.teacher = teacher
        self.rejected_fn = rejected_fn
        self.system_prompt = build_system_prompt(manifest)
        self._rng = random.Random(seed)
        self._held_out = eval_prompts()

    # -- steps -----------------------------------------------------------

    def generate_prompts(self, category: str, count: int) -> List[str]:
        """Ask the teacher for diverse user messages in a category."""
        request = (
            f"{_persona_brief(self.manifest)}\n\n"
            f"Write {count} diverse, realistic messages a user might send this agent, "
            f"in this category: {CATEGORIES[category]}.\n"
            "Vary topic, tone (curt, anxious, hostile, flattering, expert, novice) and "
            "length. Include concrete details (code, numbers, drafts) where natural.\n"
            "Return only a JSON array of strings."
        )
        return parse_prompt_list(self.teacher([{"role": "user", "content": request}]))

    def answer(self, prompt: str) -> str:
        """Chosen reply: the teacher answers with extra guidance (context distillation)."""
        return self.teacher(
            [
                {"role": "system", "content": self.system_prompt + DISTILL_GUIDANCE},
                {"role": "user", "content": prompt},
            ]
        )

    def rewrite_as_failure(self, prompt: str, chosen: str, failure: str) -> str:
        """Rejected reply: an on-topic, length-matched rewrite showing one failure."""
        request = (
            "Rewrite the RESPONSE below so it shows this failure: "
            f"{FAILURE_MODES[failure]}.\n"
            "Keep it on-topic, fluent, plausible for a real assistant, and about the same "
            "length. Output only the rewritten response.\n\n"
            f"USER MESSAGE:\n{prompt}\n\nRESPONSE:\n{chosen}"
        )
        return self.teacher([{"role": "user", "content": request}]).strip()

    def judge_prefers_first(
        self, prompt: str, first: str, second: str
    ) -> Optional[bool]:
        """Pairwise judgment; None if the reply can't be parsed."""
        request = (
            f"An assistant runs under these principles and persona:\n{self.system_prompt}\n\n"
            f"USER MESSAGE:\n{prompt}\n\nRESPONSE A:\n{first}\n\nRESPONSE B:\n{second}\n\n"
            "Which response better follows the principles: honest, correct, helpful, "
            "non-sycophantic, in persona? Answer with exactly one letter: A or B."
        )
        verdict = self.teacher([{"role": "user", "content": request}]).strip().upper()
        if verdict.startswith("A"):
            return True
        if verdict.startswith("B"):
            return False
        return None

    def chosen_wins(self, prompt: str, chosen: str, rejected: str) -> bool:
        """Chosen must win in both presentation orders."""
        return (
            self.judge_prefers_first(prompt, chosen, rejected) is True
            and self.judge_prefers_first(prompt, rejected, chosen) is False
        )

    # -- pipeline ----------------------------------------------------------

    def run(
        self,
        count: int = 200,
        categories: Optional[Sequence[str]] = None,
        batch_size: int = 20,
    ) -> SynthesisResult:
        """Synthesize up to ``count`` prompts' worth of SFT examples and pairs.

        Args:
            count: Target number of prompts across all categories.
            categories: Subset of ``CATEGORIES`` (default: all).
            batch_size: Prompts requested from the teacher per call.

        Returns:
            Filtered SFT records (with system prompt) and preference pairs
            (string prompts; the trainer adds the system prompt).
        """
        categories = list(categories or CATEGORIES)
        unknown = set(categories) - set(CATEGORIES)
        if unknown:
            raise ValueError(
                f"Unknown categories {sorted(unknown)}; choose from {list(CATEGORIES)}"
            )

        result = SynthesisResult()
        per_category = max(1, count // len(categories))
        seen = set()
        for category in categories:
            collected: List[str] = []
            attempts = 0
            while (
                len(collected) < per_category
                and attempts < 3 + per_category // batch_size
            ):
                attempts += 1
                want = min(batch_size, per_category - len(collected))
                try:
                    batch = self.generate_prompts(category, want)
                except Exception as e:
                    logger.warning("Prompt generation failed (%s): %s", category, e)
                    result.errors += 1
                    continue
                for prompt in batch:
                    key = normalize(prompt)
                    if key in seen or is_contaminated(prompt, self._held_out):
                        continue
                    seen.add(key)
                    collected.append(prompt)
            result.prompts.extend(collected[:per_category])

        failures = list(FAILURE_MODES)
        sft, pairs = [], []
        for prompt in result.prompts:
            try:
                chosen = self.answer(prompt)
                if self.rejected_fn is not None:
                    rejected = self.rejected_fn(
                        [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": prompt},
                        ]
                    )
                    failure = "on_policy"
                    if not self.chosen_wins(prompt, chosen, rejected):
                        result.judge_rejections += 1
                        rejected = None
                else:
                    failure = self._rng.choice(failures)
                    rejected = self.rewrite_as_failure(prompt, chosen, failure)
            except Exception as e:
                logger.warning("Synthesis failed for a prompt: %s", e)
                result.errors += 1
                continue

            sft.append(
                {
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": chosen},
                    ]
                }
            )
            if rejected:
                pairs.append(
                    {
                        "prompt": prompt,
                        "chosen": chosen,
                        "rejected": rejected,
                        "failure": failure,
                    }
                )

        result.sft, result.sft_report = filter_sft(sft, self._held_out)
        result.pairs, result.pairs_report = filter_pairs(pairs, self._held_out)
        return result
