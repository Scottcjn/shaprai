# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""End-to-end training smoke test on a tiny, randomly initialized model.

Runs the real TRL/PEFT code paths (SFT, then each preference method on top
of the SFT adapter) on CPU in seconds. Skipped unless the ``training`` extra
is installed: pip install 'shaprai[training]'.
"""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("torch")
pytest.importorskip("trl")
pytest.importorskip("peft")
pytest.importorskip("datasets")

from shaprai.core.lifecycle import create_agent  # noqa: E402
from shaprai.core.template_engine import AgentTemplate  # noqa: E402
from shaprai.training.dpo import PREFERENCE_METHODS, DPOTrainer  # noqa: E402
from shaprai.training.sft import SFTTrainer  # noqa: E402

pytestmark = pytest.mark.slow

TINY = {
    "batch_size": 2,
    "gradient_accumulation_steps": 1,
    "max_seq_length": 2048,
    "lora_r": 4,
    "lora_alpha": 8,
    # CPU-only: no bitsandbytes 4-bit kernels
    "load_in_4bit": False,
}


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory):
    """A 2-layer Qwen3 with a word-level tokenizer and Qwen3's chat template."""
    import trl
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers
    from transformers import PreTrainedTokenizerFast, Qwen3Config, Qwen3ForCausalLM

    from shaprai.training.dpo import generate_pairs
    from shaprai.training.recipes import build_system_prompt

    specials = ["<|endoftext|>", "<|im_start|>", "<|im_end|>", "<think>", "</think>"]
    corpus = [build_system_prompt({"name": "x"})] + [
        f"{p['prompt']} {p['chosen']} {p['rejected']}" for p in generate_pairs()
    ]
    tok = Tokenizer(models.WordLevel(unk_token="<|endoftext|>"))
    tok.pre_tokenizer = pre_tokenizers.Sequence(
        [pre_tokenizers.Whitespace(), pre_tokenizers.Split("\n", behavior="isolated")]
    )
    tok.train_from_iterator(corpus, trainers.WordLevelTrainer(special_tokens=specials))
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tok,
        eos_token="<|im_end|>",
        pad_token="<|endoftext|>",
        unk_token="<|endoftext|>",
    )
    qwen3_template = Path(trl.__file__).parent / "chat_templates" / "qwen3.jinja"
    tokenizer.chat_template = qwen3_template.read_text(encoding="utf-8")

    model = Qwen3ForCausalLM(
        Qwen3Config(
            vocab_size=len(tokenizer),
            hidden_size=32,
            intermediate_size=64,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            max_position_embeddings=4096,
            pad_token_id=tokenizer.pad_token_id,
        )
    )
    path = tmp_path_factory.mktemp("tiny-qwen3")
    model.save_pretrained(path)
    tokenizer.save_pretrained(path)
    return str(path)


@pytest.fixture
def agent_dir(tmp_path, tiny_model):
    template = AgentTemplate(
        name="tiny",
        model={"base": tiny_model},
        personality={"voice": "Plain-spoken and exact."},
        training={"sft": TINY, **{m: TINY for m in PREFERENCE_METHODS}},
    )
    create_agent("tiny", template, agents_dir=tmp_path)
    return tmp_path / "tiny"


def manifest(agent_dir):
    return yaml.safe_load((agent_dir / "manifest.yaml").read_text())


def test_sft_then_each_preference_method(agent_dir):
    sft = SFTTrainer(agent_dir).train(epochs=1)
    assert sft["status"] == "completed", sft.get("reason")
    assert sft["assistant_only_loss"] is True  # Qwen3 template gets patched masks
    assert (Path(sft["adapter_path"]) / "adapter_config.json").exists()
    assert manifest(agent_dir)["model"]["sft_adapter"] == sft["adapter_path"]

    for method in PREFERENCE_METHODS:
        result = DPOTrainer(agent_dir, method=method).train(epochs=1)
        assert result["status"] == "completed", f"{method}: {result.get('reason')}"
        assert result["init_adapter"] == sft["adapter_path"]
        assert (Path(result["adapter_path"]) / "adapter_config.json").exists()
        assert result["adapter_path"].endswith(f"checkpoints/{method}/adapter")

    history = [h["phase"] for h in manifest(agent_dir)["training_history"]]
    assert history == ["sft", *PREFERENCE_METHODS]


def test_preference_without_sft_starts_fresh_adapter(agent_dir):
    result = DPOTrainer(agent_dir, method="orpo").train(epochs=1)

    assert result["status"] == "completed", result.get("reason")
    assert result["init_adapter"] is None
    assert result["lora"]["target_modules"] == "all-linear"
