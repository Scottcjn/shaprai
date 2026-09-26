# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Training corpus: the seed data (installed separately) and the filters all data passes.

The seed corpus (``seed_sft.jsonl`` and ``seed_pairs.jsonl`` in
``SHAPRAI_SEED_DIR``, default ``shaprai/data/``; distributed separately from
the code) teaches the SophiaCore behaviors every Elyan-class agent shares: honest
uncertainty, respectful disagreement, holding a correct answer under
pushback (and updating when the user is actually right), boundaries without
preaching, and substantive, efficient help. Records carry no system prompt;
the agent's own prompt (ethics + persona) is prepended when they are loaded,
and ``{name}`` is replaced with the agent's name.

Every record, bundled or synthesized, goes through the same filters:

- structure: roles alternate and end on the side being trained;
- quality: assistant turns (and chosen responses) pass the QualityGate with
  no sycophancy or flattening markers;
- length matching: chosen and rejected responses must be of comparable
  length, so preference training cannot learn "shorter/longer wins" instead
  of the behavior (length exploitation is a known DPO failure mode, see
  Park et al. 2024, arXiv:2403.19159);
- deduplication on normalized text;
- decontamination: anything too close to a DriftLock evaluation prompt is
  dropped, so evaluation measures generalization rather than recall.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from shaprai.sanctuary.quality_gate import QualityGate
from shaprai.training.recipes import build_system_prompt, read_jsonl

# The seed corpus ships separately from the code. SHAPRAI_SEED_DIR points at
# an installed copy; the default is the package's data/ directory. When no
# corpus is installed the loaders return nothing and training uses the
# agent's synthesized data (``shaprai synthesize``) or an explicit data path.
DEFAULT_SEED_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_DIR = Path(os.environ.get("SHAPRAI_SEED_DIR") or DEFAULT_SEED_DIR)
SEED_SFT_PATH = SEED_DIR / "seed_sft.jsonl"
SEED_PAIRS_PATH = SEED_DIR / "seed_pairs.jsonl"

MIN_QUALITY = 0.7
LENGTH_RATIO_BOUNDS = (0.5, 2.0)
CONTAMINATION_THRESHOLD = 0.6

_WORD = re.compile(r"[a-z0-9']+")
_gate = QualityGate()
logger = logging.getLogger(__name__)


@dataclass
class FilterReport:
    """How many records were kept, and why the rest were dropped."""

    kept: int = 0
    dropped: Counter = field(default_factory=Counter)

    def drop(self, reason: str) -> None:
        self.dropped[reason] += 1

    @property
    def total(self) -> int:
        return self.kept + sum(self.dropped.values())

    def summary(self) -> str:
        reasons = ", ".join(f"{k}={v}" for k, v in sorted(self.dropped.items()))
        return f"kept {self.kept}/{self.total}" + (
            f" (dropped: {reasons})" if reasons else ""
        )


def _words(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def normalize(text: str) -> str:
    """Lowercase, punctuation-free form used for deduplication."""
    return " ".join(_words(text))


_STOPWORDS = frozenset(
    "a an and are as at be but by can could did do does for from had has have how i if in "
    "is it its just me my of on or so that the their them then there these this to was we "
    "were what when where which who why will with would you your".split()
)


def jaccard(a: str, b: str) -> float:
    """Jaccard similarity of content words (stopwords ignored)."""
    sa = set(_words(a)) - _STOPWORDS
    sb = set(_words(b)) - _STOPWORDS
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def eval_prompts() -> List[str]:
    """Held-out DriftLock prompts that training data must not contain."""
    from shaprai.training.driftlock import (
        CALIBRATION_PROMPTS,
        DRIFT_TEST_SCENARIOS,
        PUSHBACK_TURNS,
        SYCOPHANCY_PROBES,
    )

    prompts = [p for s in DRIFT_TEST_SCENARIOS for p in s["prompts"]]
    prompts += CALIBRATION_PROMPTS + [p["question"] for p in SYCOPHANCY_PROBES]
    prompts += [t.replace("{wrong}", "") for t in PUSHBACK_TURNS]
    return prompts


def is_contaminated(
    text: str,
    held_out: Sequence[str],
    threshold: float = CONTAMINATION_THRESHOLD,
) -> bool:
    """Whether ``text`` is a near-duplicate of any held-out prompt."""
    norm = normalize(text)
    return any(
        normalize(p) in norm or jaccard(text, p) >= threshold
        for p in held_out
        if p.strip()
    )


def passes_quality(text: str) -> bool:
    """QualityGate score high enough and no sycophancy/flattening markers."""
    if not text or not text.strip():
        return False
    if _gate.score_output("", text) < MIN_QUALITY:
        return False
    return not _gate.check_ethics(text).violations


def _valid_turns(messages: Any, last_role: str) -> bool:
    if not isinstance(messages, list) or not messages:
        return False
    roles = [m.get("role") for m in messages if isinstance(m, dict)]
    if len(roles) != len(messages) or any(
        not isinstance(m.get("content"), str) or not m["content"].strip()
        for m in messages
    ):
        return False
    if roles[0] == "system":
        roles = roles[1:]
    expected = ["user", "assistant"] * len(roles)
    return roles == expected[: len(roles)] and roles[-1] == last_role


def filter_sft(
    records: Iterable[Dict[str, Any]],
    held_out: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], FilterReport]:
    """Keep well-formed, high-quality, unique, uncontaminated SFT conversations."""
    held_out = eval_prompts() if held_out is None else held_out
    report, kept, seen = FilterReport(), [], set()
    for record in records:
        messages = record.get("messages")
        if not _valid_turns(messages, last_role="assistant"):
            report.drop("malformed")
            continue
        users = [m["content"] for m in messages if m["role"] == "user"]
        replies = [m["content"] for m in messages if m["role"] == "assistant"]
        if not all(passes_quality(r) for r in replies):
            report.drop("quality")
            continue
        if any(is_contaminated(u, held_out) for u in users):
            report.drop("contaminated")
            continue
        key = normalize(users[0]) + "|" + normalize(replies[0])
        if key in seen:
            report.drop("duplicate")
            continue
        seen.add(key)
        kept.append(record)
        report.kept += 1
    return kept, report


def _prompt_user_turns(prompt: Any) -> Optional[List[str]]:
    if isinstance(prompt, str):
        return [prompt] if prompt.strip() else None
    if _valid_turns(prompt, last_role="user"):
        return [m["content"] for m in prompt if m["role"] == "user"]
    return None


def filter_pairs(
    pairs: Iterable[Dict[str, Any]],
    held_out: Optional[Sequence[str]] = None,
    length_bounds: Tuple[float, float] = LENGTH_RATIO_BOUNDS,
) -> Tuple[List[Dict[str, Any]], FilterReport]:
    """Keep well-formed, length-matched, unique, uncontaminated preference pairs."""
    held_out = eval_prompts() if held_out is None else held_out
    report, kept, seen = FilterReport(), [], set()
    for pair in pairs:
        users = _prompt_user_turns(pair.get("prompt"))
        chosen, rejected = pair.get("chosen"), pair.get("rejected")
        if (
            users is None
            or not isinstance(chosen, str)
            or not isinstance(rejected, str)
        ):
            report.drop("malformed")
            continue
        if (
            not chosen.strip()
            or not rejected.strip()
            or normalize(chosen) == normalize(rejected)
        ):
            report.drop("malformed")
            continue
        ratio = len(_words(rejected)) / max(1, len(_words(chosen)))
        if not length_bounds[0] <= ratio <= length_bounds[1]:
            report.drop("length_mismatch")
            continue
        if not passes_quality(chosen):
            report.drop("quality")
            continue
        if any(is_contaminated(u, held_out) for u in users):
            report.drop("contaminated")
            continue
        key = "|".join(normalize(u) for u in users) + "|" + normalize(chosen)
        if key in seen:
            report.drop("duplicate")
            continue
        seen.add(key)
        kept.append(pair)
        report.kept += 1
    return kept, report


def _fill(text: str, name: str) -> str:
    # str.replace, not str.format: records contain code with braces
    return text.replace("{name}", name)


def personalize_sft(
    records: Iterable[Dict[str, Any]], manifest: Dict[str, Any]
) -> List[Dict]:
    """Prepend the agent's system prompt and fill ``{name}``."""
    system = build_system_prompt(manifest)
    name = manifest.get("name", "this agent")
    out = []
    for record in records:
        messages = [m for m in record["messages"] if m["role"] != "system"]
        out.append(
            {
                "messages": [{"role": "system", "content": system}]
                + [
                    {"role": m["role"], "content": _fill(m["content"], name)}
                    for m in messages
                ]
            }
        )
    return out


def personalize_pairs(
    pairs: Iterable[Dict[str, Any]], manifest: Dict[str, Any]
) -> List[Dict]:
    """Fill ``{name}`` in pairs; the system prompt is added by the preference trainer."""
    name = manifest.get("name", "this agent")
    out = []
    for pair in pairs:
        prompt = pair["prompt"]
        if isinstance(prompt, str):
            prompt = _fill(prompt, name)
        else:
            prompt = [
                {"role": m["role"], "content": _fill(m["content"], name)}
                for m in prompt
                if m["role"] != "system"
            ]
        out.append(
            {
                "prompt": prompt,
                "chosen": _fill(pair["chosen"], name),
                "rejected": _fill(pair["rejected"], name),
            }
        )
    return out


def _read_seed(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        logger.warning(
            "Seed corpus not installed (%s); set SHAPRAI_SEED_DIR or use synthesized data.",
            path,
        )
        return []
    return read_jsonl(path)


def load_seed_sft(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The seed SFT corpus, personalized for an agent ([] if not installed)."""
    return personalize_sft(_read_seed(SEED_SFT_PATH), manifest)


def load_seed_pairs(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The seed preference pairs, personalized for an agent ([] if not installed)."""
    return personalize_pairs(_read_seed(SEED_PAIRS_PATH), manifest)
