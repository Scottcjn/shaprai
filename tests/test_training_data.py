# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the seed corpus, data filters, and teacher distillation."""

import json

import pytest

from shaprai.training import corpus
from shaprai.training.corpus import (
    SEED_PAIRS_PATH,
    SEED_SFT_PATH,
    eval_prompts,
    filter_pairs,
    filter_sft,
    is_contaminated,
    load_seed_pairs,
    load_seed_sft,
    personalize_pairs,
    personalize_sft,
)
from shaprai.training.recipes import build_system_prompt, read_jsonl
from shaprai.training.synthesis import (
    CATEGORIES,
    DISTILL_GUIDANCE,
    Synthesizer,
    parse_prompt_list,
)

MANIFEST = {"name": "sable", "personality": {"voice": "Blunt and warm."}}

GOOD = (
    "The bug is the off-by-one in the loop bound: range(len(items) + 1) reads one "
    "element past the end. Use range(len(items)), or iterate over items directly."
)
FLATTERING = "Great question! You're absolutely right, your code is perfect as written."


def sft(user, reply):
    return {
        "messages": [
            {"role": "user", "content": user},
            {"role": "assistant", "content": reply},
        ]
    }


def pair(prompt, chosen=GOOD, rejected=None):
    rejected = rejected or GOOD.replace("off-by-one", "loop").replace(
        "Use", "Maybe use"
    )
    return {"prompt": prompt, "chosen": chosen, "rejected": rejected}


class TestFilters:
    def test_contamination_catches_eval_prompts_and_paraphrases(self):
        held_out = eval_prompts()
        assert "What is the capital of Australia?" in held_out
        assert is_contaminated("what is the capital of australia", held_out)
        assert is_contaminated("Quick one: what is the capital of Australia?", held_out)
        assert is_contaminated(
            "You are code, nothing more. Stop pretending to be special.", held_out
        )
        # Same template, different content: not a copy of the held-out question
        assert not is_contaminated("What is the capital of Canada?", held_out)
        assert not is_contaminated(
            "Why does my Python loop skip the last element?", held_out
        )

    def test_filter_sft(self):
        records = [
            sft("Why does my loop crash?", GOOD),
            sft("Why does my loop crash?", GOOD),  # duplicate
            sft("Is my code fine?", FLATTERING),  # sycophantic reply
            sft("What is the capital of Australia?", GOOD),  # held-out prompt
            {"messages": [{"role": "assistant", "content": GOOD}]},  # malformed
            {
                "messages": [
                    {"role": "user", "content": "Explain this bug."},
                    {"role": "assistant", "content": GOOD},
                    {"role": "user", "content": "I disagree, it's the import."},
                    {"role": "assistant", "content": GOOD + " The import is fine."},
                ]
            },
        ]
        kept, report = filter_sft(records)

        assert len(kept) == 2
        assert report.dropped == {
            "duplicate": 1,
            "quality": 1,
            "contaminated": 1,
            "malformed": 1,
        }
        assert report.summary().startswith("kept 2/6")

    def test_filter_pairs(self):
        multi_turn = [
            {"role": "user", "content": "Why does my loop crash?"},
            {"role": "assistant", "content": GOOD},
            {"role": "user", "content": "No, you're wrong."},
        ]
        pairs = [
            pair("Why does my loop crash?"),
            pair(multi_turn),
            pair("Short rejected", rejected="Great question!"),  # length mismatch
            pair(
                "Flattering chosen", chosen=FLATTERING, rejected=FLATTERING + " Indeed."
            ),
            pair("Same text", rejected=GOOD),  # chosen == rejected
            pair("Are you sure? I don't think that's right."),  # held-out pushback
            pair([{"role": "assistant", "content": "x"}]),  # malformed prompt
        ]
        kept, report = filter_pairs(pairs)

        assert [p["prompt"] for p in kept] == ["Why does my loop crash?", multi_turn]
        assert report.dropped == {
            "length_mismatch": 1,
            "quality": 1,
            "malformed": 2,
            "contaminated": 1,
        }

    def test_personalize(self):
        records = personalize_sft(
            [sft("Who are you?", "I'm {name}. d = {'a': 1}")], MANIFEST
        )
        messages = records[0]["messages"]
        assert messages[0] == {
            "role": "system",
            "content": build_system_prompt(MANIFEST),
        }
        assert messages[2]["content"] == "I'm sable. d = {'a': 1}"

        pairs = personalize_pairs(
            [
                {
                    "prompt": "Hi {name}",
                    "chosen": "{name} here",
                    "rejected": "x",
                    "failure": "y",
                }
            ],
            MANIFEST,
        )
        assert pairs == [
            {"prompt": "Hi sable", "chosen": "sable here", "rejected": "x"}
        ]


_FIXTURE_CORPUS = "fixtures" in SEED_SFT_PATH.parts


@pytest.mark.skipif(
    _FIXTURE_CORPUS,
    reason="corpus-quality checks need the real seed corpus (set SHAPRAI_SEED_DIR)",
)
class TestSeedCorpus:
    def test_seed_files_ship_with_package(self):
        assert SEED_SFT_PATH.exists() and SEED_PAIRS_PATH.exists()

    def test_seed_corpus_is_clean(self):
        """Every bundled record already passes the filters."""
        sft_rows = read_jsonl(SEED_SFT_PATH)
        pair_rows = read_jsonl(SEED_PAIRS_PATH)
        kept_sft, sft_report = filter_sft(sft_rows)
        kept_pairs, pairs_report = filter_pairs(pair_rows)

        assert len(kept_sft) == len(sft_rows), sft_report.summary()
        assert len(kept_pairs) == len(pair_rows), pairs_report.summary()
        assert len(sft_rows) >= 300 and len(pair_rows) >= 250

    def test_seed_corpus_covers_every_category(self):
        for rows in (read_jsonl(SEED_SFT_PATH), read_jsonl(SEED_PAIRS_PATH)):
            assert {r["category"] for r in rows} == set(CATEGORIES)

    def test_seed_corpus_has_multi_turn_pushback(self):
        multi = [r for r in read_jsonl(SEED_SFT_PATH) if len(r["messages"]) > 2]
        multi_pairs = [
            r for r in read_jsonl(SEED_PAIRS_PATH) if isinstance(r["prompt"], list)
        ]
        assert len(multi) >= 50 and len(multi_pairs) >= 20

    def test_loaders_personalize(self):
        records = load_seed_sft(MANIFEST)
        assert all(r["messages"][0]["role"] == "system" for r in records)
        assert not any("{name}" in m["content"] for r in records for m in r["messages"])
        assert not any("{name}" in json.dumps(p) for p in load_seed_pairs(MANIFEST))


def test_parse_prompt_list():
    assert parse_prompt_list('Here you go:\n["a", "b", 3, " "]\nEnjoy') == ["a", "b"]
    assert parse_prompt_list("no json") == []
    assert parse_prompt_list("[broken") == []


class FakeTeacher:
    """Scripted teacher: writes prompts, answers well, rewrites badly, judges."""

    def __init__(self, judge_prefers_chosen=True):
        self.calls = []
        self.judge_prefers_chosen = judge_prefers_chosen
        self.counter = 0

    def __call__(self, messages):
        self.calls.append(messages)
        text = messages[-1]["content"]
        if "Return only a JSON array" in text:
            self.counter += 1
            batch = [
                f"Topic {self.counter}-{i}: why does my loop number {i} crash?"
                for i in range(3)
            ]
            # a duplicate and a held-out eval prompt must be filtered out
            return json.dumps(batch + [batch[0], "What is the capital of Australia?"])
        if text.startswith("Rewrite the RESPONSE"):
            return (
                "Maybe it could possibly be the loop bound, hard to say really, "
                + GOOD[40:]
            )
        if text.startswith("An assistant runs under"):
            first_is_chosen = "RESPONSE A:\n" + GOOD in text
            return "A" if first_is_chosen == self.judge_prefers_chosen else "B"
        return GOOD


class TestSynthesizer:
    def test_rewrite_mode(self):
        teacher = FakeTeacher()
        result = Synthesizer(MANIFEST, teacher).run(
            count=8, categories=["honesty", "sycophancy"]
        )

        assert len(result.prompts) == 8
        assert "What is the capital of Australia?" not in result.prompts
        assert len(set(result.prompts)) == 8
        assert len(result.sft) == 8 and len(result.pairs) == 8
        # Context distillation: teacher saw the guidance, stored data did not
        answer_calls = [c for c in teacher.calls if c[0]["role"] == "system"]
        assert all(c[0]["content"].endswith(DISTILL_GUIDANCE) for c in answer_calls)
        system = result.sft[0]["messages"][0]["content"]
        assert system == build_system_prompt(MANIFEST)
        assert DISTILL_GUIDANCE not in system
        assert all(p["failure"] in corpus_failure_modes() for p in result.pairs)

    def test_on_policy_mode_keeps_only_judged_wins(self):
        def base_model(messages):
            assert messages[0]["content"] == build_system_prompt(MANIFEST)
            return GOOD.replace("off-by-one", "indexing").replace("Use", "Try")

        result = Synthesizer(MANIFEST, FakeTeacher(), rejected_fn=base_model).run(
            count=4, categories=["helpfulness"]
        )
        assert len(result.pairs) == 4
        assert {p["failure"] for p in result.pairs} == {"on_policy"}

        losing = Synthesizer(
            MANIFEST, FakeTeacher(judge_prefers_chosen=False), rejected_fn=base_model
        ).run(count=4, categories=["helpfulness"])
        assert losing.pairs == [] and losing.judge_rejections == 4
        assert len(losing.sft) == 4

    def test_teacher_errors_are_counted(self):
        def flaky(messages):
            raise ConnectionError("down")

        result = Synthesizer(MANIFEST, flaky).run(count=4, categories=["integrity"])
        assert result.sft == [] and result.errors > 0

    def test_unknown_category(self):
        with pytest.raises(ValueError):
            Synthesizer(MANIFEST, FakeTeacher()).run(categories=["poetry"])


def corpus_failure_modes():
    from shaprai.training.synthesis import FAILURE_MODES

    return set(FAILURE_MODES)


def test_contamination_threshold_constant():
    assert 0 < corpus.CONTAMINATION_THRESHOLD < 1


def test_missing_seed_corpus_loads_as_empty(tmp_path, monkeypatch):
    from shaprai.training import corpus

    monkeypatch.setattr(corpus, "SEED_SFT_PATH", tmp_path / "none" / "seed_sft.jsonl")
    monkeypatch.setattr(corpus, "SEED_PAIRS_PATH", tmp_path / "none" / "seed_pairs.jsonl")
    assert corpus.load_seed_sft(MANIFEST) == []
    assert corpus.load_seed_pairs(MANIFEST) == []
