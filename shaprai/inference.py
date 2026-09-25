# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Minimal chat-completion client for evaluating agents.

Evaluation code talks to an agent through a ``ChatFn``: any callable that
takes OpenAI-style messages and returns the assistant's reply text. That keeps
DriftLock and the Sanctuary independent of how a model is served.

``openai_chat_fn`` builds a ``ChatFn`` for any OpenAI-compatible
``/chat/completions`` endpoint, which is what vLLM, SGLang, Ollama,
llama.cpp's server, LM Studio and hosted providers expose.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

import requests

Message = Dict[str, str]
ChatFn = Callable[[List[Message]], str]


def openai_chat_fn(
    base_url: str,
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
    timeout: float = 120.0,
) -> ChatFn:
    """Create a ChatFn backed by an OpenAI-compatible chat completions API.

    Args:
        base_url: API root, e.g. ``http://localhost:8000/v1``.
        model: Model name as the server knows it.
        api_key: Bearer token; ``""`` sends none. ``None`` (the default)
            uses ``SHAPRAI_API_KEY`` from the environment; ``OPENAI_API_KEY`` is used only for
            ``https://api.openai.com``.
            Local servers need none.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens per reply.
        timeout: Per-request timeout in seconds.

    Returns:
        Callable mapping a message list to the assistant reply text.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    key = os.environ.get("SHAPRAI_API_KEY") if api_key is None else api_key
    parsed = urlparse(url)
    if (
        api_key is None
        and not key
        and parsed.scheme == "https"
        and parsed.hostname == "api.openai.com"
    ):
        # Never send an OpenAI key to any other (possibly mistyped) host, or
        # over plain HTTP
        key = os.environ.get("OPENAI_API_KEY")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    def chat(messages: List[Message]) -> str:
        response = requests.post(
            url,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"].get("content") or ""

    return chat
