# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for MCP serving, A2A Agent Cards, and the agent-framework adapters."""

import json
import sys
import types

import pytest
from click.testing import CliRunner

from shaprai import cli
from shaprai.a2a import AGENT_CARD_PATH, build_agent_card
from shaprai.core.lifecycle import create_agent
from shaprai.core.template_engine import AgentTemplate
from shaprai.runtimes.mcp_native import MCPAgent

REVIEW = (
    "The retry loop in fetch_pages never resets the backoff after a success, so one "
    "transient failure slows every later request. Resetting the delay inside the "
    "success branch fixes it. I also noticed the timeout is hard-coded to five "
    "seconds; reading it from the existing config object would make the tests in "
    "test_fetch.py easier to write, since they could shorten it."
)

MANIFEST = {
    "name": "sable",
    "description": "Reviews pull requests without flattery.",
    "version": "2.1",
    "personality": {"voice": "Blunt, warm, never flattering."},
    "capabilities": ["code_review", "security_audit"],
    "platforms": ["github"],
    "model": {"base": "Qwen/Qwen3-8B"},
}


class TestMCPToolSchemas:
    def test_publishing_tools_are_left_out_by_default(self):
        agent = MCPAgent("sable")
        for fmt in ("mcp", "openai"):
            names = {
                t.get("name") or t["function"]["name"]
                for t in agent.get_tools_schema(format=fmt)
            }
            assert names == {"beacon_heartbeat", "grazer_discover"}

    def test_execute_tool_refuses_publishing_by_default(self, monkeypatch):
        from shaprai.integrations.grazer.responder import GrazerResponder

        sent = []
        monkeypatch.setattr(
            GrazerResponder, "submit_response", lambda *a: sent.append(a) or {}
        )
        with pytest.raises(PermissionError):
            MCPAgent("sable").execute_tool(
                "grazer_engage", {"target_url": "u", "action": "upvote"}
            )
        assert sent == []

    def test_mcp_format(self):
        tools = {
            t["name"]: t
            for t in MCPAgent("sable").get_tools_schema(include_publishing=True)
        }

        engage = tools["grazer_engage"]
        assert engage["inputSchema"]["required"] == ["target_url", "action"]
        assert engage["title"] == "Engage with content"
        assert engage["annotations"]["readOnlyHint"] is False
        assert tools["grazer_discover"]["annotations"] == {
            "readOnlyHint": True,
            "openWorldHint": True,
        }
        assert "parameters" not in engage

    def test_openai_format(self):
        tools = MCPAgent("sable").get_tools_schema(format="openai")
        assert {t["type"] for t in tools} == {"function"}
        assert tools[0]["function"]["parameters"]["type"] == "object"

    def test_unknown_format(self):
        with pytest.raises(ValueError):
            MCPAgent("sable").get_tools_schema(format="xml")

    def test_from_manifest_uses_training_prompt(self):
        from shaprai.training.recipes import build_system_prompt

        agent = MCPAgent.from_manifest(MANIFEST)
        assert agent.name == "sable"
        assert agent.system_prompt == build_system_prompt(MANIFEST)

    def test_grazer_discover_uses_discovery_integration(self, monkeypatch):
        from shaprai.integrations.grazer import discovery

        def discover(self, agent_name):
            assert self.config.platforms == ["github"]
            return [
                discovery.DiscoveredPost(
                    post_id="1",
                    platform="github",
                    title="t",
                    content="c",
                    author="a",
                    url="u",
                    topics=["ai"],
                    relevance_score=0.9,
                )
            ]

        monkeypatch.setattr(discovery.GrazerDiscovery, "discover", discover)
        result = MCPAgent("sable").execute_tool(
            "grazer_discover", {"platforms": ["github"]}
        )
        assert result[0]["post_id"] == "1" and result[0]["relevance_score"] == 0.9


class TestMCPServer:
    """Round trips through the real MCP SDK, in process."""

    @pytest.fixture(autouse=True)
    def _sdk(self):
        pytest.importorskip("mcp.server.mcpserver")

    def _session(self, agent, body, allow_publishing=True):
        import anyio
        from mcp.client import Client

        async def main():
            server = agent.to_mcp_server(allow_publishing=allow_publishing)
            async with Client(server) as client:
                return await body(client)

        return anyio.run(main)

    def test_publishing_tools_are_opt_in(self):
        async def body(client):
            return {t.name for t in (await client.list_tools()).tools}

        default = self._session(MCPAgent("sable"), body, allow_publishing=False)
        assert default == {"beacon_heartbeat", "grazer_discover"}

    def test_lists_tools_with_schemas_and_annotations(self):
        async def body(client):
            return (await client.list_tools()).tools

        tools = {t.name: t for t in self._session(MCPAgent("sable"), body)}

        assert set(tools) == {"beacon_heartbeat", "grazer_discover", "grazer_engage"}
        engage = tools["grazer_engage"]
        assert engage.input_schema["properties"]["action"]["enum"] == [
            "comment",
            "review",
            "claim",
            "upvote",
            "reply",
        ]
        assert set(engage.input_schema["required"]) == {"target_url", "action"}
        assert engage.annotations.read_only_hint is False
        assert engage.annotations.open_world_hint is True
        assert tools["grazer_discover"].annotations.read_only_hint is True

    def test_call_tool(self, monkeypatch):
        from shaprai.integrations.grazer.responder import GrazerResponder

        submitted = []

        def submit(self, response, agent_name):
            submitted.append(
                (response.post.url, response.action, response.response_text)
            )
            return {"status": "ok"}

        monkeypatch.setattr(GrazerResponder, "submit_response", submit)

        async def body(client):
            ok = await client.call_tool(
                "grazer_engage",
                {
                    "target_url": "https://github.com/o/r/pull/1",
                    "action": "review",
                    "content": REVIEW,
                    "post_title": "Retry loop",
                },
            )
            bad = await client.call_tool(
                "grazer_engage", {"target_url": "u", "action": "spam"}
            )
            return ok, bad

        ok, bad = self._session(MCPAgent("sable"), body)

        assert ok.is_error is False
        assert json.loads(ok.content[0].text) == {"status": "ok"}
        assert submitted == [("https://github.com/o/r/pull/1", "review", REVIEW)]
        assert bad.is_error is True

    def test_persona_prompt(self):
        agent = MCPAgent.from_manifest(MANIFEST)

        async def body(client):
            listed = (await client.list_prompts()).prompts
            fetched = await client.get_prompt("persona")
            return listed, fetched

        listed, fetched = self._session(agent, body)
        assert [p.name for p in listed] == ["persona"]
        assert fetched.messages[0].content.text == agent.system_prompt


class TestEngageQualityGate:
    URL = "https://github.com/o/r/pull/1"

    @pytest.fixture
    def submitted(self, monkeypatch):
        from shaprai.integrations.grazer.responder import GrazerResponder

        sent = []
        monkeypatch.setattr(
            GrazerResponder,
            "submit_response",
            lambda self, response, agent: sent.append(response) or {"status": "ok"},
        )
        return sent

    def engage(self, agent=None, **kwargs):
        return (agent or MCPAgent("sable")).execute_tool(
            "grazer_engage",
            {"target_url": self.URL, "post_title": "Retry loop", **kwargs},
            allow_publishing=True,
        )

    def test_text_actions_need_content(self, submitted):
        result = self.engage(action="comment")
        assert result["status"] == "rejected" and "requires content" in result["reason"]
        assert submitted == []

    def test_low_quality_text_is_rejected(self, submitted):
        result = self.engage(action="reply", content="Great post!")
        assert result["status"] == "rejected"
        assert result["quality_score"] < 0.8
        assert submitted == []

    def test_quality_text_is_submitted(self, submitted):
        assert self.engage(action="review", content=REVIEW) == {"status": "ok"}
        assert submitted[0].quality_score >= 0.8
        assert submitted[0].response_text == REVIEW

    def test_upvote_needs_no_text(self, submitted):
        assert self.engage(action="upvote") == {"status": "ok"}
        assert submitted[0].response_text == ""

    @pytest.mark.parametrize("action", ["claim", "upvote"])
    def test_non_text_actions_refuse_content(self, submitted, action):
        result = self.engage(action=action, content="BUY CHEAP RTC")
        assert result["status"] == "rejected"
        assert "takes no content" in result["reason"]
        assert submitted == []

    @pytest.mark.parametrize(
        "content",
        [
            "great post " * 30,
            "lorem " * 50,
            "x " * 50,
            "Retry loop " + "lorem " * 50,
        ],
    )
    def test_filler_is_rejected(self, submitted, content):
        result = self.engage(action="review", content=content)
        assert result["status"] == "rejected"
        assert submitted == []

    def test_text_needs_the_post_it_answers(self, submitted):
        result = self.engage(action="review", content=REVIEW, post_title="")
        assert result["status"] == "rejected"
        assert "post_title" in result["reason"]
        assert submitted == []

    def test_text_must_mention_the_post(self, submitted):
        result = self.engage(
            action="review", content=REVIEW, post_title="Unrelated database schema"
        )
        assert result["status"] == "rejected"
        assert submitted == []

    def test_rate_limit_applies_across_calls(self, submitted):
        agent = MCPAgent("sable")
        results = [self.engage(agent, action="upvote") for _ in range(11)]
        assert [r["status"] for r in results] == ["ok"] * 10 + ["rejected"]
        assert "rate limit" in results[-1]["reason"]
        assert len(submitted) == 10


def test_mcp_server_requires_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "mcp.server.mcpserver", None)
    with pytest.raises(ImportError, match=r"shaprai\[mcp\]"):
        MCPAgent("sable").to_mcp_server()


class TestAgentCard:
    def test_card_fields(self):
        card = build_agent_card(
            MANIFEST,
            "https://sable.example.com/a2a",
            provider={"organization": "Elyan Labs", "url": "https://elyanlabs.ai"},
        )

        assert AGENT_CARD_PATH == "/.well-known/agent-card.json"
        assert card["name"] == "sable"
        assert card["description"] == MANIFEST["description"]
        assert card["version"] == "2.1"
        assert card["supportedInterfaces"] == [
            {
                "url": "https://sable.example.com/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ]
        assert [s["id"] for s in card["skills"]] == ["code_review", "security_audit"]
        assert card["skills"][0]["name"] == "Code Review"
        assert card["skills"][0]["tags"] == ["code_review", "github"]
        assert card["provider"]["organization"] == "Elyan Labs"
        assert "documentationUrl" not in card

    def test_minimal_manifest(self):
        card = build_agent_card({"name": "bare"}, "https://x")
        assert card["skills"][0]["id"] == "general"
        assert "bare" in card["description"]

    def test_invalid_binding(self):
        with pytest.raises(ValueError):
            build_agent_card(MANIFEST, "https://x", protocol_binding="SOAP")

    def test_card_matches_a2a_schema(self):
        pytest.importorskip("a2a")
        from a2a.types import a2a_pb2
        from a2a.utils.constants import (
            AGENT_CARD_WELL_KNOWN_PATH,
            PROTOCOL_VERSION_CURRENT,
        )
        from google.protobuf.json_format import ParseDict

        card = build_agent_card(
            MANIFEST,
            "https://sable.example.com/a2a",
            provider={"organization": "Elyan Labs", "url": "https://elyanlabs.ai"},
            documentation_url="https://github.com/Scottcjn/shaprai",
            icon_url="https://example.com/icon.png",
        )
        # Rejects unknown or misspelled fields
        parsed = ParseDict(card, a2a_pb2.AgentCard())

        assert AGENT_CARD_WELL_KNOWN_PATH == AGENT_CARD_PATH
        assert (
            parsed.supported_interfaces[0].protocol_version == PROTOCOL_VERSION_CURRENT
        )
        assert parsed.skills[1].tags == ["security_audit", "github"]


class TestCLI:
    @pytest.fixture
    def agents_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli, "SHAPRAI_HOME", tmp_path)
        monkeypatch.setattr(cli, "AGENTS_DIR", tmp_path / "agents")
        template = AgentTemplate(
            name="sable",
            description="Reviews pull requests without flattery.",
            capabilities=["code_review"],
            platforms=["github"],
        )
        create_agent("sable", template, agents_dir=tmp_path / "agents")
        return tmp_path / "agents"

    def test_agent_card_stdout_is_json(self, agents_dir, monkeypatch):
        # Prerequisite summary must not pollute the JSON on stdout
        monkeypatch.setattr(cli, "require_elyan_ecosystem", lambda: print("SUMMARY"))
        result = CliRunner().invoke(
            cli.main, ["agent-card", "sable", "--url", "https://sable.example.com/a2a"]
        )

        assert result.exit_code == 0, result.output
        card = json.loads(result.stdout)
        assert card["description"] == "Reviews pull requests without flattery."
        assert "SUMMARY" in result.stderr

    def test_agent_card_to_file(self, agents_dir, tmp_path):
        out = tmp_path / "agent-card.json"
        result = CliRunner().invoke(
            cli.main,
            [
                "--skip-checks",
                "agent-card",
                "sable",
                "--url",
                "https://x",
                "-o",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text())["skills"][0]["id"] == "code_review"

    def test_unknown_agent(self, agents_dir):
        result = CliRunner().invoke(
            cli.main, ["--skip-checks", "agent-card", "ghost", "--url", "https://x"]
        )
        assert result.exit_code == 1

    def test_json_format_keeps_prerequisites_off_stdout(self, agents_dir, monkeypatch):
        monkeypatch.setattr(cli, "require_elyan_ecosystem", lambda: print("SUMMARY"))
        result = CliRunner().invoke(cli.main, ["--format", "json", "fleet", "status"])
        assert "SUMMARY" not in result.stdout


class TestSmolagentsAdapter:
    def _fake_smolagents(self, monkeypatch):
        built = {}

        class InferenceClientModel:
            def __init__(self, model_id):
                self.model_id = model_id

        class CodeAgent:
            def __init__(self, **kwargs):
                built.update(kwargs)

        monkeypatch.setitem(
            sys.modules,
            "smolagents",
            types.SimpleNamespace(
                CodeAgent=CodeAgent, InferenceClientModel=InferenceClientModel
            ),
        )
        return built

    def test_build_passes_principles_as_instructions(self, monkeypatch):
        from shaprai.runtimes.smolagent_adapter import ShaprSmolagent

        built = self._fake_smolagents(monkeypatch)
        agent = ShaprSmolagent.from_manifest(MANIFEST)
        agent.build()

        assert built["instructions"] == agent.system_prompt
        assert "SophiaCore" in built["instructions"]
        assert built["model"].model_id == "Qwen/Qwen3-8B"
        assert built["name"] == "sable"

    @pytest.mark.parametrize(
        "name, expected",
        [("my-agent", "my_agent"), ("3po", "_3po"), ("class", "class_"), ("", "agent")],
    )
    def test_names_become_identifiers(self, monkeypatch, name, expected):
        from shaprai.runtimes.smolagent_adapter import ShaprSmolagent

        built = self._fake_smolagents(monkeypatch)
        ShaprSmolagent(name).build()
        assert built["name"] == expected

    def test_custom_model(self, monkeypatch):
        from shaprai.runtimes.smolagent_adapter import ShaprSmolagent

        built = self._fake_smolagents(monkeypatch)
        local = object()
        ShaprSmolagent("sable", model=local).build()
        assert built["model"] is local

    def test_real_smolagents(self):
        pytest.importorskip("smolagents")
        from shaprai.runtimes.smolagent_adapter import ShaprSmolagent

        agent = ShaprSmolagent.from_manifest({**MANIFEST, "name": "my-agent"})
        built = agent.build()
        assert built.instructions == agent.system_prompt
        assert agent.system_prompt in built.system_prompt


class TestCrewAIAdapter:
    def test_process_is_passed_through(self, monkeypatch):
        from shaprai.runtimes.crewai_adapter import ShaprCrewAgent, create_crew

        captured = {}

        class Process(str):
            pass

        def record(name):
            def cls(**kwargs):
                captured[name] = kwargs
                return types.SimpleNamespace(**kwargs)

            return cls

        monkeypatch.setitem(
            sys.modules,
            "crewai",
            types.SimpleNamespace(
                Agent=record("agent"),
                Crew=record("crew"),
                Task=record("task"),
                Process=Process,
            ),
        )
        agent = ShaprCrewAgent.from_manifest(MANIFEST)
        create_crew(
            [agent],
            [{"description": "review"}],
            process="hierarchical",
            manager_llm="gpt-4o",
        )

        assert captured["crew"]["process"] == "hierarchical"
        assert captured["crew"]["manager_llm"] == "gpt-4o"
        assert "SophiaCore" in captured["agent"]["backstory"]

    def test_invalid_process(self):
        from shaprai.runtimes.crewai_adapter import create_crew

        with pytest.raises(ValueError):
            create_crew([], [], process="consensual")
