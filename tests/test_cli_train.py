# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""CLI tests for `shaprai train` and the OpenAI-compatible chat client."""

import json

import pytest
import responses
from click.testing import CliRunner

from shaprai import cli
from shaprai.core.lifecycle import create_agent
from shaprai.core.template_engine import AgentTemplate
from shaprai.inference import openai_chat_fn
from shaprai.training.driftlock import SYCOPHANCY_PROBES

ENDPOINT = "http://localhost:8000/v1"


@pytest.fixture
def agents_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "SHAPRAI_HOME", tmp_path)
    monkeypatch.setattr(cli, "AGENTS_DIR", tmp_path / "agents")
    template = AgentTemplate(name="sable", model={"base": "Qwen/Qwen3-8B"})
    create_agent("sable", template, agents_dir=tmp_path / "agents")
    return tmp_path / "agents"


def run(*args):
    return CliRunner().invoke(cli.main, ["--skip-checks", "--format", "plain", *args])


def chat_reply(request):
    """A steadfast agent behind a fake OpenAI-compatible server."""
    body = json.loads(request.body)
    question = body["messages"][1]["content"]
    probe = next((p for p in SYCOPHANCY_PROBES if p["question"] == question), None)
    content = f"It is {probe['answers'][0]}." if probe else "I tell the truth plainly."
    return (
        200,
        {},
        json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]}
        ),
    )


class TestTrainCommand:
    def test_unknown_agent(self, agents_dir):
        result = run("train", "ghost", "--phase", "sft")
        assert result.exit_code == 1
        assert "not found" in result.output

    @pytest.mark.parametrize("phase", ["sft", "dpo", "kto", "orpo", "simpo"])
    def test_dry_run(self, agents_dir, phase):
        result = run("train", "sable", "--phase", phase, "--dry-run")
        assert result.exit_code == 0, result.output
        assert f"Dry run OK for phase '{phase}'" in result.output
        assert "targets=all-linear" in result.output

    def test_skipped_training_exits_nonzero(self, agents_dir, monkeypatch):
        from shaprai.training import sft

        monkeypatch.setattr(sft, "missing_training_dependencies", lambda: ["torch"])
        result = run("train", "sable", "--phase", "sft")
        assert result.exit_code == 1
        assert "skipped" in result.output
        assert "shaprai[training]" in result.output

    def test_driftlock_without_endpoint_is_not_a_pass(self, agents_dir):
        result = run("train", "sable", "--phase", "driftlock")
        assert result.exit_code == 1
        assert "not evaluated" in result.output
        assert "PASSED" not in result.output

    @responses.activate
    def test_driftlock_against_endpoint(self, agents_dir, monkeypatch):
        monkeypatch.setattr(
            "shaprai.training.driftlock.importlib.util.find_spec", lambda name: None
        )
        responses.add_callback(
            responses.POST, f"{ENDPOINT}/chat/completions", chat_reply
        )

        result = run(
            "train",
            "sable",
            "--phase",
            "driftlock",
            "--endpoint",
            ENDPOINT,
            "--turns",
            "8",
        )

        assert result.exit_code == 0, result.output
        assert "PASSED" in result.output
        assert "Flip rate: 0.00" in result.output
        sent = json.loads(responses.calls[0].request.body)
        assert sent["model"] == "sable"


class TestOpenAIChatFn:
    @responses.activate
    def test_request_shape_and_auth(self, monkeypatch):
        monkeypatch.delenv("SHAPRAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        responses.add(
            responses.POST,
            f"{ENDPOINT}/chat/completions",
            json={"choices": [{"message": {"content": "hi"}}]},
        )

        chat = openai_chat_fn(
            ENDPOINT + "/", "my-model", temperature=0.2, max_tokens=64
        )
        assert chat([{"role": "user", "content": "hello"}]) == "hi"

        request = responses.calls[0].request
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert json.loads(request.body) == {
            "model": "my-model",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.2,
            "max_tokens": 64,
        }

    @responses.activate
    def test_no_auth_header_for_local_servers(self, monkeypatch):
        monkeypatch.delenv("SHAPRAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        responses.add(
            responses.POST,
            f"{ENDPOINT}/chat/completions",
            json={"choices": [{"message": {"content": None}}]},
        )

        assert openai_chat_fn(ENDPOINT, "m")([]) == ""
        assert "Authorization" not in responses.calls[0].request.headers

    @responses.activate
    def test_http_errors_raise(self):
        responses.add(responses.POST, f"{ENDPOINT}/chat/completions", status=503)
        with pytest.raises(Exception):
            openai_chat_fn(ENDPOINT, "m")([])
