# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""HuggingFace integration for model management.

Handles downloading, caching, and loading base models from the
HuggingFace Hub for agent training and inference.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default cache directory for downloaded models
DEFAULT_CACHE_DIR = Path.home() / ".shaprai" / "models"

# Recommended models for Elyan-class agents by size tier. vram_gb is a rough
# 4-bit inference footprint; QLoRA training needs more. All are natively
# supported by transformers (no remote code). Qwen3 base IDs (no suffix) are
# hybrid thinking models; the -2507 Instruct and Gemma builds do not think.
RECOMMENDED_MODELS = {
    "tiny": [
        {
            "id": "Qwen/Qwen3-0.6B",
            "vram_gb": 1,
            "description": "Tiny agent, edge deployment",
        },
    ],
    "small": [
        {
            "id": "Qwen/Qwen3-1.7B",
            "vram_gb": 2,
            "description": "Small agent, fast inference",
        },
        {
            "id": "HuggingFaceTB/SmolLM3-3B",
            "vram_gb": 3,
            "description": "Fully open small model with long context",
        },
    ],
    "medium": [
        {
            "id": "Qwen/Qwen3-4B-Instruct-2507",
            "vram_gb": 4,
            "description": "Non-thinking instruct model, strong persona fine-tuning base",
        },
        {
            "id": "Qwen/Qwen3-8B",
            "vram_gb": 6,
            "description": "Standard Elyan-class agent",
        },
        {
            "id": "Qwen/Qwen3.5-9B",
            "vram_gb": 7,
            "description": "Newer Qwen generation (2026), thinks by default",
        },
        {
            "id": "google/gemma-4-E4B-it",
            "vram_gb": 5,
            "description": "Gemma 4 edge model, Apache-2.0",
        },
    ],
    "large": [
        {
            "id": "Qwen/Qwen3-14B",
            "vram_gb": 10,
            "description": "Enhanced capabilities",
        },
        {
            "id": "openai/gpt-oss-20b",
            "vram_gb": 16,
            "description": "MoE reasoning model, 3.6B active parameters",
        },
    ],
    "xl": [
        {
            "id": "Qwen/Qwen3-32B",
            "vram_gb": 20,
            "description": "Near-frontier dense model",
        },
        {
            "id": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "vram_gb": 18,
            "description": "MoE with 3B active parameters, fast for its size",
        },
    ],
}


def load_base_model(
    model_id: str,
    quantize: bool = True,
    cache_dir: Optional[Path] = None,
    trust_remote_code: bool = False,
) -> Any:
    """Load a base model from HuggingFace for training or inference.

    Args:
        model_id: HuggingFace model identifier (e.g., 'Qwen/Qwen3-8B').
        quantize: Whether to load in 4-bit quantization (QLoRA-ready).
        cache_dir: Local cache directory. Defaults to ~/.shaprai/models.
        trust_remote_code: Run model code shipped in the repo. Only needed
            for architectures transformers doesn't implement; enable only for
            repos you trust.

    Returns:
        Loaded model object (AutoModelForCausalLM).

    Raises:
        ImportError: If transformers or bitsandbytes not installed.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading model: %s (quantize=%s)", model_id, quantize)

        load_kwargs: Dict[str, Any] = {
            "cache_dir": str(cache_dir),
            "trust_remote_code": trust_remote_code,
        }

        if quantize:
            try:
                import torch
                from transformers import BitsAndBytesConfig

                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                )
                load_kwargs["quantization_config"] = bnb_config
                load_kwargs["device_map"] = "auto"
            except ImportError:
                logger.warning(
                    "bitsandbytes not available -- loading without quantization"
                )

        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
        logger.info("Model loaded successfully: %s", model_id)
        return model

    except ImportError as e:
        raise ImportError(
            f"Required package not installed: {e}. "
            "Install with: pip install 'shaprai[training]'"
        ) from e


def load_tokenizer(
    model_id: str,
    cache_dir: Optional[Path] = None,
    trust_remote_code: bool = False,
) -> Any:
    """Load a tokenizer for a model.

    Args:
        model_id: HuggingFace model identifier.
        cache_dir: Local cache directory.
        trust_remote_code: Run tokenizer code shipped in the repo.

    Returns:
        Loaded tokenizer object.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        model_id,
        cache_dir=str(cache_dir),
        trust_remote_code=trust_remote_code,
    )


def list_compatible_models(
    size_filter: Optional[str] = None,
    max_vram_gb: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List models compatible with ShaprAI agent training.

    Args:
        size_filter: Filter by size tier (tiny, small, medium, large, xl).
        max_vram_gb: Maximum VRAM budget in GB.

    Returns:
        List of compatible model specifications.
    """
    results: List[Dict[str, Any]] = []

    tiers = (
        [size_filter]
        if size_filter and size_filter in RECOMMENDED_MODELS
        else RECOMMENDED_MODELS.keys()
    )

    for tier in tiers:
        for model in RECOMMENDED_MODELS.get(tier, []):
            if max_vram_gb is not None and model["vram_gb"] > max_vram_gb:
                continue
            results.append({**model, "tier": tier})

    return results


def download_model(
    model_id: str,
    cache_dir: Optional[Path] = None,
) -> Path:
    """Download a model to local cache without loading it.

    Useful for pre-caching models before training.

    Args:
        model_id: HuggingFace model identifier.
        cache_dir: Local cache directory.

    Returns:
        Path to the cached model directory.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(
            model_id,
            cache_dir=str(cache_dir),
        )
        logger.info("Model downloaded to: %s", local_dir)
        return Path(local_dir)

    except ImportError:
        from transformers import AutoModelForCausalLM

        # Fallback: use transformers download
        AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
        )
        return cache_dir / model_id.replace("/", "--")
