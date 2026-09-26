# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Shared building blocks for the SFT and preference-optimization phases.

Everything here is plain data until ``make_*`` is called, so configurations
can be inspected, recorded in the manifest, and tested without a GPU or the
``training`` extra installed.

Defaults follow the published recipes:
  - QLoRA (Dettmers et al. 2023, arXiv:2305.14314): 4-bit NF4 base weights
    with double quantization and bf16 compute, and LoRA on *all* linear
    layers, which the paper found necessary to match full fine-tuning.
  - DoRA (Liu et al. 2024, arXiv:2402.09353) and rsLoRA (Kalajdzievski 2023,
    arXiv:2312.03732) are available as opt-in switches (``use_dora``,
    ``use_rslora``); rsLoRA matters most at higher ranks.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from shaprai.sanctuary.principles import get_ethics_prompt

logger = logging.getLogger(__name__)

TRAINING_EXTRA_HINT = "Install with: pip install 'shaprai[training]'"

# LoRA / QLoRA defaults shared by every phase
DEFAULT_ADAPTER_CONFIG: Dict[str, Any] = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "lora_target_modules": "all-linear",
    "use_dora": False,
    "use_rslora": False,
    "load_in_4bit": True,
}


def build_system_prompt(manifest: Dict[str, Any]) -> str:
    """System prompt an agent trains and runs with: SophiaCore ethics plus persona.

    Training and evaluation must use the same prompt, so the SFT data, the
    preference data, and the DriftLock evaluator all build it here.
    """
    personality = manifest.get("personality") or {}
    persona = []
    for key in ("voice", "style", "communication", "humor"):
        value = personality.get(key)
        if isinstance(value, str) and value.strip():
            persona.append(f"{key.title()}: {value.strip()}")

    prompt = get_ethics_prompt()
    if persona:
        name = manifest.get("name", "this agent")
        prompt += f"\n\n## Persona ({name})\n" + "\n".join(persona)
    return prompt


def lora_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """Keyword arguments for ``peft.LoraConfig``."""
    return {
        "r": config["lora_r"],
        "lora_alpha": config["lora_alpha"],
        "lora_dropout": config["lora_dropout"],
        "target_modules": config["lora_target_modules"],
        "use_dora": config.get("use_dora", False),
        "use_rslora": config.get("use_rslora", False),
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }


def quantization_kwargs(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Keyword arguments for ``transformers.BitsAndBytesConfig`` (None = no quantization)."""
    if not config.get("load_in_4bit", False):
        return None
    return {
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True,
        "bnb_4bit_compute_dtype": config.get("bnb_4bit_compute_dtype", "bfloat16"),
    }


def make_lora_config(config: Dict[str, Any]) -> Any:
    """Build a ``peft.LoraConfig``."""
    from peft import LoraConfig

    return LoraConfig(**lora_kwargs(config))


def model_init_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """``from_pretrained`` kwargs for the base model, including 4-bit loading."""
    kwargs: Dict[str, Any] = {"dtype": "auto"}
    quant = quantization_kwargs(config)
    if quant is not None:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(**quant)
        kwargs["device_map"] = "auto"
    return kwargs


def missing_training_dependencies(extra_modules: Tuple[str, ...] = ()) -> List[str]:
    """Modules from the ``training`` extra that are not importable."""
    required = ("torch", "transformers", "peft", "trl", "datasets", "accelerate")
    return [m for m in required + extra_modules if importlib.util.find_spec(m) is None]


def resolve_4bit(config: Dict[str, Any]) -> Dict[str, Any]:
    """Disable 4-bit loading when bitsandbytes or a CUDA GPU is unavailable,
    and compute in fp16 on GPUs without bf16 support."""
    if not config.get("load_in_4bit"):
        return config
    import torch

    reason = None
    if importlib.util.find_spec("bitsandbytes") is None:
        reason = "bitsandbytes is not installed"
    elif not torch.cuda.is_available():
        reason = "no CUDA GPU is available"
    if reason:
        logger.warning("QLoRA 4-bit loading disabled (%s); training plain LoRA", reason)
        return {**config, "load_in_4bit": False}
    if not torch.cuda.is_bf16_supported():
        return {**config, "bnb_4bit_compute_dtype": "float16"}
    return config


def precision_kwargs() -> Dict[str, Any]:
    """Mixed-precision trainer arguments for the current hardware.

    TRL defaults to bf16, which fails on CPU and on pre-Ampere GPUs.
    """
    import torch

    if torch.cuda.is_available():
        bf16 = torch.cuda.is_bf16_supported()
        return {"bf16": bf16, "fp16": not bf16}
    if torch.backends.mps.is_available():
        return {"bf16": False, "fp16": False}
    return {"bf16": False, "fp16": False, "use_cpu": True}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file, skipping blank lines."""
    with open(path, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Write rows to a JSONL file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class ManifestPhase:
    """Base for training phases that read and record into an agent manifest."""

    phase = ""
    defaults: Dict[str, Any] = {}

    def __init__(
        self, agent_dir: Path, config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize the phase.

        Config precedence: phase defaults < the manifest's ``training.<phase>``
        section (set in the agent template) < ``config`` passed here.

        Args:
            agent_dir: Path to the agent's directory.
            config: Optional training config overrides.
        """
        self.agent_dir = Path(agent_dir)
        manifest = (
            self._load_manifest() if (self.agent_dir / "manifest.yaml").exists() else {}
        )
        from_manifest = ((manifest.get("training") or {}).get(self.phase)) or {}
        self.config = {**self.defaults, **from_manifest, **(config or {})}
        self.output_dir = self.agent_dir / "checkpoints" / self.phase
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> Dict[str, Any]:
        """Load the agent manifest."""
        manifest_path = self.agent_dir / "manifest.yaml"
        with open(manifest_path, "r") as f:
            return yaml.safe_load(f)

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Save the agent manifest."""
        manifest["updated_at"] = time.time()
        manifest_path = self.agent_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    def _base_model(self, manifest: Dict[str, Any]) -> str:
        """The model to train: the previous phase's adapter-merged output is not
        assumed; phases start from the manifest's base model."""
        model_id = (manifest.get("model") or {}).get("base", "")
        if not model_id:
            raise ValueError("No base model specified in agent manifest")
        return model_id
