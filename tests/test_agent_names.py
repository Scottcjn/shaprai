# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Agent names must stay inside the agents directory."""

import pytest
from click.testing import CliRunner

from shaprai import cli
from shaprai.core.lifecycle import (
    AgentState,
    create_agent,
    get_agent_status,
    transition_state,
)
from shaprai.core.template_engine import AgentTemplate

TEMPLATE = AgentTemplate(name="t", model={"base": "Qwen/Qwen3-8B"})

TRAVERSAL = ["../escaped", "../../escaped", "nested/agent", "..", "."]


@pytest.fixture
def agents_dir(tmp_path):
    return tmp_path / "home" / "agents"


class TestCreateAgent:
    @pytest.mark.parametrize("name", TRAVERSAL)
    def test_traversal_names_rejected(self, agents_dir, tmp_path, name):
        with pytest.raises(ValueError):
            create_agent(name, TEMPLATE, agents_dir=agents_dir)
        # Nothing was written anywhere under tmp_path
        assert not (tmp_path / "home" / "escaped").exists()
        assert not (tmp_path / "escaped").exists()
        assert not (agents_dir / "nested").exists()

    @pytest.mark.parametrize("name", ["", "-flag", "has space", "a" * 65, "x\x00y"])
    def test_other_invalid_names_rejected(self, agents_dir, name):
        with pytest.raises(ValueError):
            create_agent(name, TEMPLATE, agents_dir=agents_dir)

    @pytest.mark.parametrize("name", ["sable", "test-bot", "agent_2", "v1.2", "a" * 64])
    def test_valid_names_accepted(self, agents_dir, name):
        create_agent(name, TEMPLATE, agents_dir=agents_dir)
        assert (agents_dir / name / "manifest.yaml").exists()

    def test_absolute_path_rejected(self, agents_dir, tmp_path):
        target = tmp_path / "absolute-agent"
        with pytest.raises(ValueError):
            create_agent(str(target), TEMPLATE, agents_dir=agents_dir)
        assert not target.exists()


class TestLoadAndSave:
    def test_status_cannot_read_outside(self, agents_dir):
        # A manifest planted next to the agents directory
        outside = agents_dir.parent / "planted"
        outside.mkdir(parents=True)
        (outside / "manifest.yaml").write_text("name: planted\nstate: graduated\n")

        with pytest.raises(ValueError):
            get_agent_status("../planted", agents_dir=agents_dir)
        with pytest.raises(ValueError):
            transition_state("../planted", AgentState.DEPLOYED, agents_dir=agents_dir)


class TestCli:
    @pytest.fixture
    def cli_dirs(self, tmp_path, monkeypatch):
        # `shaprai create` onboards over the network; never let a test do that
        def no_network(*args, **kwargs):
            raise AssertionError("onboard_agent must not be reached")

        monkeypatch.setattr(
            "shaprai.elyan_bus.ElyanBus.onboard_agent", no_network, raising=True
        )
        monkeypatch.setattr(cli, "SHAPRAI_HOME", tmp_path / "home")
        monkeypatch.setattr(cli, "AGENTS_DIR", tmp_path / "home" / "agents")
        return tmp_path

    @staticmethod
    def run(*args):
        return CliRunner().invoke(
            cli.main, ["--skip-checks", "--format", "plain", *args]
        )

    def test_create_rejects_traversal_before_any_work(self, cli_dirs):
        result = self.run("create", "../escaped")
        assert result.exit_code != 0
        assert "Invalid name" in result.output
        assert not (cli_dirs / "home" / "escaped").exists()

    def test_create_rejects_bad_charset(self, cli_dirs):
        result = self.run("create", "has space")
        assert result.exit_code == 1
        assert "Invalid agent name" in result.output
        assert not (cli_dirs / "home" / "agents" / "has space").exists()

    def test_create_existing_agent_is_a_clean_error(self, cli_dirs):
        create_agent("sable", TEMPLATE, agents_dir=cli_dirs / "home" / "agents")
        result = self.run("create", "sable")
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.parametrize("command", ["evaluate", "graduate", "deploy", "mcp"])
    def test_agent_commands_reject_traversal(self, cli_dirs, command):
        outside = cli_dirs / "home" / "planted"
        outside.mkdir(parents=True)
        (outside / "manifest.yaml").write_text("name: planted\nstate: graduated\n")

        result = self.run(command, "../planted")
        assert result.exit_code != 0
        assert "Invalid name" in result.output
