# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Supervised Fine-Tuning (SFT) for Elyan-class agents.

Phase 1 of the training pipeline. Takes a base model and fine-tunes it
on curated conversations that demonstrate Elyan-class behavior:
- Identity-consistent responses
- Anti-sycophantic communication
- Principled disagreement
- Biblical ethical foundations

Runs TRL's ``SFTTrainer`` with QLoRA (4-bit NF4 base, LoRA on all linear
layers) on conversational data, computing the loss on assistant turns only
so the model learns the agent's replies rather than the prompts. The
resulting adapter becomes the starting point and reference model for the
preference phase.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from shaprai.training.corpus import load_seed_sft
from shaprai.training.recipes import (
    DEFAULT_ADAPTER_CONFIG,
    TRAINING_EXTRA_HINT,
    ManifestPhase,
    build_system_prompt,
    lora_kwargs,
    make_lora_config,
    missing_training_dependencies,
    model_init_kwargs,
    precision_kwargs,
    quantization_kwargs,
    read_jsonl,
    resolve_4bit,
    write_jsonl,
)

logger = logging.getLogger(__name__)

# Written by `shaprai synthesize`; included in the default dataset when present
SYNTH_SFT_FILE = "synth_sft.jsonl"

# Default SFT hyperparameters
DEFAULT_SFT_CONFIG = {
    **DEFAULT_ADAPTER_CONFIG,
    "learning_rate": 2e-4,
    "batch_size": 4,
    "gradient_accumulation_steps": 4,
    "max_seq_length": 2048,
    "warmup_ratio": 0.03,
    "weight_decay": 0.01,
    "lr_scheduler_type": "cosine",
    "assistant_only_loss": True,
    "packing": False,
}


def sft_config_kwargs(
    config: Dict[str, Any], output_dir: Path, epochs: int
) -> Dict[str, Any]:
    """Keyword arguments for ``trl.SFTConfig``."""
    return {
        "output_dir": str(output_dir),
        "num_train_epochs": epochs,
        "learning_rate": config["learning_rate"],
        "per_device_train_batch_size": config["batch_size"],
        "gradient_accumulation_steps": config["gradient_accumulation_steps"],
        "max_length": config["max_seq_length"],
        # transformers>=5 takes a float in [0, 1) here as a warmup ratio
        "warmup_steps": config["warmup_ratio"],
        "weight_decay": config["weight_decay"],
        "lr_scheduler_type": config["lr_scheduler_type"],
        "assistant_only_loss": config["assistant_only_loss"],
        "packing": config["packing"],
        "gradient_checkpointing": True,
        "logging_steps": 10,
        "save_strategy": "epoch",
        "report_to": "none",
    }


class SFTTrainer(ManifestPhase):
    """Supervised Fine-Tuning trainer for Elyan-class agents.

    Wraps TRL's SFTTrainer with QLoRA for efficient training on consumer
    GPUs.

    Attributes:
        agent_dir: Path to the agent's directory.
        config: Training configuration dictionary.
    """

    phase = "sft"
    defaults = DEFAULT_SFT_CONFIG

    def _prepare_dataset(self, data_path: Optional[str] = None) -> Path:
        """Prepare the SFT dataset.

        If no data_path is provided, combines the seed corpus (if installed) with
        any data synthesized for this agent (``data/synth_sft.jsonl``, see
        ``shaprai synthesize``), personalized with the agent's system prompt.

        Args:
            data_path: Optional path to a JSONL training file.

        Returns:
            Path to the prepared dataset.
        """
        if data_path:
            if not Path(data_path).exists():
                raise FileNotFoundError(f"SFT data not found: {data_path}")
            return Path(data_path)

        manifest = self._load_manifest()
        records = load_seed_sft(manifest)
        synth_path = self.agent_dir / "data" / SYNTH_SFT_FILE
        synthesized = read_jsonl(synth_path) if synth_path.exists() else []

        dataset_path = self.agent_dir / "data" / "sft_train.jsonl"
        if not records and not synthesized:
            raise ValueError(
                "No training data: no seed corpus is installed (SHAPRAI_SEED_DIR) and "
                "this agent has no synthesized SFT examples. Run `shaprai synthesize` or "
                "pass an explicit data path."
            )
        write_jsonl(dataset_path, records + synthesized)

        logger.info(
            "Prepared SFT dataset: %d seed + %d synthesized examples at %s",
            len(records),
            len(synthesized),
            dataset_path,
        )
        return dataset_path

    @staticmethod
    def load_records(dataset_path: Path) -> List[Dict[str, Any]]:
        """Load conversational SFT records, keeping only the ``messages`` field.

        ``sft_generator`` output also carries ``text``/``weight``/``category``
        columns, which would otherwise confuse TRL's format detection.
        """
        records = []
        for line, row in enumerate(read_jsonl(dataset_path), start=1):
            messages = row.get("messages") if isinstance(row, dict) else None
            if not isinstance(messages, list) or not messages:
                raise ValueError(
                    f"{dataset_path}, record {line}: expected a 'messages' list of "
                    '{"role", "content"} turns (conversational SFT format)'
                )
            records.append({"messages": messages})
        if not records:
            raise ValueError(f"No SFT examples in {dataset_path}")
        return records

    def _with_system_prompt(
        self, records: List[Dict[str, Any]], manifest: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Give records without a system message the agent's own system prompt."""
        system = {"role": "system", "content": build_system_prompt(manifest)}
        return [
            (
                r
                if r["messages"][0]["role"] == "system"
                else {"messages": [system] + r["messages"]}
            )
            for r in records
        ]

    def train(
        self,
        data_path: Optional[str] = None,
        epochs: int = 3,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Run SFT training.

        Args:
            data_path: Path to training data (JSONL with ``messages``). Uses
                synthetic data if None.
            epochs: Number of training epochs.
            dry_run: Validate data and configuration without loading a model.

        Returns:
            Training results dictionary. ``status`` is ``completed``,
            ``dry_run``, ``skipped`` (training extra missing) or ``failed``.
        """
        manifest = self._load_manifest()
        model_id = self._base_model(manifest)

        dataset_path = self._prepare_dataset(data_path)
        records = self._with_system_prompt(self.load_records(dataset_path), manifest)
        logger.info("Starting SFT training: model=%s, epochs=%d", model_id, epochs)

        result: Dict[str, Any] = {
            "phase": "sft",
            "model": model_id,
            "dataset": str(dataset_path),
            "num_examples": len(records),
            "epochs": epochs,
            "config": self.config,
            "lora": lora_kwargs(self.config),
            "quantization": quantization_kwargs(self.config),
            "started_at": time.time(),
            "status": "pending",
        }

        missing = missing_training_dependencies()
        if dry_run:
            result["status"] = "dry_run"
            result["missing_dependencies"] = missing
        elif missing:
            logger.warning("Training dependencies not available: %s", missing)
            result["status"] = "skipped"
            result["reason"] = (
                f"Missing dependencies: {', '.join(missing)}. {TRAINING_EXTRA_HINT}"
            )
        else:
            try:
                result.update(self._run(model_id, records, epochs))
                result["status"] = "completed"
                model_entry = manifest.setdefault("model", {})
                model_entry["sft_adapter"] = model_entry["adapter"] = result[
                    "adapter_path"
                ]
            except Exception as e:
                logger.exception("SFT training failed")
                result["status"] = "failed"
                result["reason"] = str(e)
        result["completed_at"] = time.time()

        # Record in manifest
        manifest.setdefault("training_history", []).append(result)
        manifest["state"] = "training"
        self._save_manifest(manifest)

        return result

    def _run(
        self, model_id: str, records: List[Dict[str, Any]], epochs: int
    ) -> Dict[str, Any]:
        """Train with TRL. Requires the ``training`` extra."""
        from datasets import Dataset
        from transformers import AutoTokenizer
        from trl import SFTConfig
        from trl import SFTTrainer as TRLSFTTrainer
        from trl.chat_template_utils import get_training_chat_template

        config = resolve_4bit(self.config)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        if config["assistant_only_loss"]:
            try:
                get_training_chat_template(tokenizer)
            except ValueError:
                logger.warning(
                    "No assistant-mask chat template for %s; training on full sequences",
                    model_id,
                )
                config = {**config, "assistant_only_loss": False}

        args = SFTConfig(
            **sft_config_kwargs(config, self.output_dir, epochs),
            **precision_kwargs(),
            model_init_kwargs=model_init_kwargs(config),
        )
        trainer = TRLSFTTrainer(
            model=model_id,
            args=args,
            train_dataset=Dataset.from_list(records),
            processing_class=tokenizer,
            peft_config=make_lora_config(config),
        )
        train_output = trainer.train()

        adapter_path = self.output_dir / "adapter"
        trainer.save_model(str(adapter_path))
        tokenizer.save_pretrained(str(adapter_path))
        return {
            "adapter_path": str(adapter_path),
            "train_loss": train_output.training_loss,
            "assistant_only_loss": config["assistant_only_loss"],
            "load_in_4bit": config["load_in_4bit"],
        }
