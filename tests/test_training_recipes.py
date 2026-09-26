# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for training configuration, data preparation, and dry runs.

These run without the ``training`` extra; tests/test_training_e2e.py covers
the real TRL code paths when it is installed.
"""

import json

import pytest
import yaml

from shaprai.core.lifecycle import create_agent
from shaprai.core.template_engine import AgentTemplate
from shaprai.training import dpo as dpo_module
from shaprai.training import sft as sft_module
from shaprai.training.corpus import SEED_PAIRS_PATH, SEED_SFT_PATH
from shaprai.training.dpo import (
    PREFERENCE_METHODS,
    DPOTrainer,
    generate_pairs,
    preference_config_kwargs,
    to_conversational,
)
from shaprai.training.recipes import (
    DEFAULT_ADAPTER_CONFIG,
    build_system_prompt,
    lora_kwargs,
    quantization_kwargs,
    read_jsonl,
)
from shaprai.training.sft import SFTTrainer, sft_config_kwargs


@pytest.fixture
def agent_dir(tmp_path):
    template = AgentTemplate(
        name="sable",
        model={"base": "Qwen/Qwen3-8B"},
        personality={"voice": "Blunt, warm, never flattering."},
        training={"sft": {"lora_r": 32}, "dpo": {"loss_type": ["apo_zero"]}},
    )
    create_agent("sable", template, agents_dir=tmp_path)
    return tmp_path / "sable"


def manifest(agent_dir):
    return yaml.safe_load((agent_dir / "manifest.yaml").read_text())


class TestRecipes:
    def test_lora_targets_all_linear_layers(self):
        kwargs = lora_kwargs(DEFAULT_ADAPTER_CONFIG)
        assert kwargs["target_modules"] == "all-linear"
        assert kwargs["r"] == 16 and kwargs["lora_alpha"] == 32
        assert kwargs["use_dora"] is False and kwargs["use_rslora"] is False
        assert kwargs["task_type"] == "CAUSAL_LM"

    def test_dora_and_rslora_switches(self):
        kwargs = lora_kwargs(
            {**DEFAULT_ADAPTER_CONFIG, "use_dora": True, "use_rslora": True}
        )
        assert kwargs["use_dora"] is True and kwargs["use_rslora"] is True

    def test_qlora_quantization(self):
        assert quantization_kwargs(DEFAULT_ADAPTER_CONFIG) == {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
            "bnb_4bit_compute_dtype": "bfloat16",
        }
        assert (
            quantization_kwargs({**DEFAULT_ADAPTER_CONFIG, "load_in_4bit": False})
            is None
        )

    def test_system_prompt_carries_ethics_and_persona(self):
        prompt = build_system_prompt(
            {
                "name": "sable",
                "personality": {"voice": "Blunt.", "humor": "dry", "tone": 3},
            }
        )
        assert "SophiaCore" in prompt
        assert "## Persona (sable)" in prompt
        assert "Voice: Blunt." in prompt and "Humor: dry" in prompt

    def test_system_prompt_without_persona(self):
        assert "## Persona" not in build_system_prompt({"name": "x"})


class TestSFT:
    def test_config_precedence(self, agent_dir):
        assert SFTTrainer(agent_dir).config["lora_r"] == 32  # from template
        assert SFTTrainer(agent_dir, config={"lora_r": 8}).config["lora_r"] == 8
        assert SFTTrainer(agent_dir).config["lora_alpha"] == 32  # default

    def test_sft_config_kwargs(self, agent_dir):
        trainer = SFTTrainer(agent_dir)
        kwargs = sft_config_kwargs(trainer.config, trainer.output_dir, epochs=2)
        assert kwargs["num_train_epochs"] == 2
        assert kwargs["max_length"] == 2048
        assert kwargs["assistant_only_loss"] is True
        assert kwargs["warmup_steps"] == 0.03

    def test_dry_run_prepares_seed_corpus(self, agent_dir):
        result = SFTTrainer(agent_dir).train(dry_run=True)

        assert result["status"] == "dry_run"
        assert result["num_examples"] == len(read_jsonl(SEED_SFT_PATH))
        assert result["lora"]["r"] == 32
        rows = [
            json.loads(line) for line in (agent_dir / "data" / "sft_train.jsonl").open()
        ]
        system = rows[0]["messages"][0]["content"]
        assert "Blunt, warm, never flattering." in system
        assert manifest(agent_dir)["training_history"][-1]["status"] == "dry_run"

    def test_default_data_includes_synthesized(self, agent_dir):
        synth = agent_dir / "data" / "synth_sft.jsonl"
        synth.parent.mkdir(parents=True, exist_ok=True)
        synth.write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "S"},
                        {"role": "user", "content": "u"},
                        {"role": "assistant", "content": "a"},
                    ]
                }
            )
            + "\n"
        )
        result = SFTTrainer(agent_dir).train(dry_run=True)
        assert result["num_examples"] == len(read_jsonl(SEED_SFT_PATH)) + 1

    def test_user_data_gets_system_prompt(self, agent_dir, tmp_path):
        data = tmp_path / "mine.jsonl"
        data.write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "u"},
                        {"role": "assistant", "content": "a"},
                    ]
                }
            )
            + "\n"
        )
        trainer = SFTTrainer(agent_dir)
        records = trainer._with_system_prompt(
            trainer.load_records(data), manifest(agent_dir)
        )
        assert records[0]["messages"][0]["role"] == "system"
        assert "Blunt, warm" in records[0]["messages"][0]["content"]

    def test_skipped_without_training_extra(self, agent_dir, monkeypatch):
        monkeypatch.setattr(
            sft_module, "missing_training_dependencies", lambda: ["trl"]
        )
        result = SFTTrainer(agent_dir).train()

        assert result["status"] == "skipped"
        assert "shaprai[training]" in result["reason"]
        assert manifest(agent_dir)["state"] == "training"

    def test_failure_is_recorded(self, agent_dir, monkeypatch):
        monkeypatch.setattr(sft_module, "missing_training_dependencies", lambda: [])

        def boom(*args):
            raise RuntimeError("CUDA out of memory")

        monkeypatch.setattr(SFTTrainer, "_run", boom)
        result = SFTTrainer(agent_dir).train()

        assert result["status"] == "failed"
        assert result["reason"] == "CUDA out of memory"
        assert "sft_adapter" not in manifest(agent_dir)["model"]

    def test_missing_data_path_raises(self, agent_dir):
        with pytest.raises(FileNotFoundError):
            SFTTrainer(agent_dir).train(data_path="nope.jsonl", dry_run=True)

    def test_generator_output_keeps_only_messages(self, agent_dir, tmp_path):
        from shaprai.training.sft_generator import SFTGenerator

        template = tmp_path / "persona.yaml"
        template.write_text(
            yaml.dump({"name": "sable", "voice": "blunt", "values": ["truth"]})
        )
        data = SFTGenerator().generate_file(template, tmp_path / "sft.jsonl", count=5)

        records = SFTTrainer.load_records(data)
        assert len(records) == 5
        assert all(set(r) == {"messages"} for r in records)


class TestPreference:
    def test_unknown_method(self, agent_dir):
        with pytest.raises(ValueError, match="Unknown preference method"):
            DPOTrainer(agent_dir, method="ppo")

    def test_method_defaults(self, agent_dir):
        assert DPOTrainer(agent_dir).config["beta"] == 0.1
        assert DPOTrainer(agent_dir, method="simpo").config["beta"] == 2.0
        assert DPOTrainer(agent_dir).config["loss_type"] == [
            "apo_zero"
        ]  # from template
        assert DPOTrainer(agent_dir, method="kto").config["loss_type"] == ["sigmoid"]

    @pytest.mark.parametrize("method", PREFERENCE_METHODS)
    def test_config_kwargs(self, agent_dir, method):
        trainer = DPOTrainer(agent_dir, method=method)
        kwargs = preference_config_kwargs(method, trainer.config, trainer.output_dir, 1)

        assert kwargs["beta"] == trainer.config["beta"]
        assert kwargs["output_dir"].endswith(f"checkpoints/{method}")
        expected = {
            "dpo": {"loss_type": ["apo_zero"]},
            "kto": {"desirable_weight": 1.0, "undesirable_weight": 1.0},
            "orpo": {"remove_unused_columns": False},
            "simpo": {
                "loss_type": "simpo",
                "cpo_alpha": 0.0,
                "simpo_gamma": 0.5,
                "remove_unused_columns": False,
            },
        }[method]
        assert expected.items() <= kwargs.items()

    def test_string_loss_type_becomes_list(self, agent_dir):
        trainer = DPOTrainer(agent_dir, config={"loss_type": "ipo"})
        kwargs = preference_config_kwargs("dpo", trainer.config, trainer.output_dir, 1)
        assert kwargs["loss_type"] == ["ipo"]

    def test_to_conversational(self):
        pair = generate_pairs()[0]
        record = to_conversational(pair, "SYSTEM")

        assert record["prompt"] == [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": pair["prompt"]},
        ]
        assert record["chosen"] == [{"role": "assistant", "content": pair["chosen"]}]
        assert to_conversational(record, "OTHER") == record

    def test_to_conversational_multi_turn(self):
        history = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "you're wrong"},
        ]
        record = to_conversational(
            {"prompt": history, "chosen": "c", "rejected": "r"}, "SYS"
        )
        assert record["prompt"] == [{"role": "system", "content": "SYS"}] + history
        assert record["rejected"] == [{"role": "assistant", "content": "r"}]

    def test_dry_run_continues_existing_sft_adapter(self, agent_dir):
        adapter = agent_dir / "checkpoints" / "sft" / "adapter"
        adapter.mkdir(parents=True)
        data = manifest(agent_dir)
        data["model"]["sft_adapter"] = str(adapter)
        (agent_dir / "manifest.yaml").write_text(yaml.dump(data))

        result = DPOTrainer(agent_dir, method="kto").train(dry_run=True)

        assert result["status"] == "dry_run"
        assert result["method"] == "kto"
        assert result["init_adapter"] == str(adapter)
        assert result["num_pairs"] == len(read_jsonl(SEED_PAIRS_PATH))

    def test_stale_sft_adapter_is_ignored(self, agent_dir):
        data = manifest(agent_dir)
        data["model"]["sft_adapter"] = "/gone"
        (agent_dir / "manifest.yaml").write_text(yaml.dump(data))

        assert DPOTrainer(agent_dir).train(dry_run=True)["init_adapter"] is None

    def test_skipped_without_training_extra(self, agent_dir, monkeypatch):
        monkeypatch.setattr(
            dpo_module, "missing_training_dependencies", lambda: ["torch"]
        )
        result = DPOTrainer(agent_dir, method="orpo").train()

        assert result["status"] == "skipped"
        assert manifest(agent_dir)["training_history"][-1]["phase"] == "orpo"

    def test_missing_pairs_path_raises(self, agent_dir):
        with pytest.raises(FileNotFoundError):
            DPOTrainer(agent_dir).train(pairs_path="nope.jsonl", dry_run=True)


def _no_seed_corpus(monkeypatch, tmp_path):
    from shaprai.training import corpus

    monkeypatch.setattr(corpus, "SEED_SFT_PATH", tmp_path / "none" / "seed_sft.jsonl")
    monkeypatch.setattr(
        corpus, "SEED_PAIRS_PATH", tmp_path / "none" / "seed_pairs.jsonl"
    )


def test_sft_without_any_data_fails_clearly(agent_dir, monkeypatch, tmp_path):
    _no_seed_corpus(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="No training data"):
        SFTTrainer(agent_dir).train(dry_run=True)


def test_dpo_without_any_data_fails_clearly(agent_dir, monkeypatch, tmp_path):
    _no_seed_corpus(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="No training data"):
        DPOTrainer(agent_dir).train(dry_run=True)


def test_sft_without_corpus_uses_synthesized_data(agent_dir, monkeypatch, tmp_path):
    _no_seed_corpus(monkeypatch, tmp_path)
    synth = agent_dir / "data" / "synth_sft.jsonl"
    synth.parent.mkdir(parents=True, exist_ok=True)
    synth.write_text(
        '{"messages": [{"role": "user", "content": "hi"}, '
        '{"role": "assistant", "content": "hello"}]}\n'
    )
    assert SFTTrainer(agent_dir).train(dry_run=True)["num_examples"] == 1
