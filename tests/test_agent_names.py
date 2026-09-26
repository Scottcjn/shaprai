# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Agent names must stay inside the agents directory."""

import os

import pytest
from click.testing import CliRunner

from shaprai import cli
from shaprai.core.fleet_manager import FleetManager
from shaprai.core.lifecycle import (
    AgentState,
    check_path_component,
    create_agent,
    get_agent_status,
    transition_state,
    validate_agent_name,
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

    @pytest.mark.parametrize(
        "name",
        ["", "-flag", "has space", "a" * 65, "x\x00y", "sable\n", "a" * 64 + "\n"],
    )
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


class TestNameRules:
    @pytest.mark.parametrize("name", ["sable\n", "a" * 64 + "\n", "sable\r\n"])
    def test_trailing_newline_rejected(self, name):
        with pytest.raises(ValueError):
            validate_agent_name(name)

    @pytest.mark.parametrize("name", ["D:planted", "C:", "a:b", "\\\\srv\\share"])
    def test_windows_drive_and_unc_names_rejected(self, name):
        # PureWindowsPath(r"C:\a\agents") / "D:planted" == "D:planted"
        with pytest.raises(ValueError):
            check_path_component(name)

    @pytest.mark.parametrize("name", ["legacy agent", "Legacy_Bot+1"])
    def test_lenient_check_still_loads_legacy_names(self, name):
        check_path_component(name)


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

    @pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
    def test_symlink_out_of_agents_dir_rejected(self, agents_dir):
        outside = agents_dir.parent / "planted"
        outside.mkdir(parents=True)
        manifest = outside / "manifest.yaml"
        manifest.write_text("name: planted\nstate: graduated\n")
        agents_dir.mkdir(parents=True)
        (agents_dir / "linked").symlink_to(outside, target_is_directory=True)

        with pytest.raises(ValueError):
            get_agent_status("linked", agents_dir=agents_dir)
        with pytest.raises(ValueError):
            transition_state("linked", AgentState.DEPLOYED, agents_dir=agents_dir)
        assert manifest.read_text() == "name: planted\nstate: graduated\n"

    def test_symlinked_agents_dir_itself_still_works(self, tmp_path):
        real = tmp_path / "real-agents"
        real.mkdir()
        link = tmp_path / "agents-link"
        link.symlink_to(real, target_is_directory=True)
        create_agent("sable", TEMPLATE, agents_dir=link)
        assert get_agent_status("sable", agents_dir=link)["name"] == "sable"


class TestFleetManager:
    def test_register_rejects_traversal(self, agents_dir):
        fleet = FleetManager(agents_dir)
        with pytest.raises(ValueError):
            fleet.register_agent({"name": "../escaped"})
        assert not (agents_dir.parent / "escaped").exists()

    def test_get_agent_rejects_traversal(self, agents_dir):
        outside = agents_dir.parent / "planted"
        outside.mkdir(parents=True)
        (outside / "manifest.yaml").write_text("name: planted\nstate: graduated\n")
        with pytest.raises(ValueError):
            FleetManager(agents_dir).get_agent("../planted")

    def test_broadcast_ignores_manifest_name(self, agents_dir):
        fleet = FleetManager(agents_dir)
        fleet.register_agent({"name": "sable", "state": "created"})
        # A manifest whose 'name' field points outside the fleet
        (agents_dir / "sable" / "manifest.yaml").write_text(
            "name: ../escaped\nstate: created\n"
        )
        assert fleet.broadcast_update("hello") == 1
        assert (agents_dir / "sable" / "updates.yaml").exists()
        assert not (agents_dir.parent / "escaped").exists()

    def test_broadcast_skips_symlink_out(self, agents_dir):
        fleet = FleetManager(agents_dir)
        outside = agents_dir.parent / "planted"
        outside.mkdir(parents=True)
        (outside / "manifest.yaml").write_text("name: planted\nstate: created\n")
        (agents_dir / "linked").symlink_to(outside, target_is_directory=True)
        assert fleet.broadcast_update("hello") == 0
        assert not (outside / "updates.yaml").exists()


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
        assert result.exit_code == 2
        assert "Invalid agent name" in result.output
        assert not (cli_dirs / "home" / "agents" / "has space").exists()

    def test_create_existing_agent_is_a_clean_error(self, cli_dirs):
        create_agent("sable", TEMPLATE, agents_dir=cli_dirs / "home" / "agents")
        result = self.run("create", "sable")
        assert result.exit_code == 2
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


class TestCliValidatesBeforePrereqProbes:
    """Click runs main() before parsing a subcommand's arguments; the
    network prerequisite probes must still come after NAME is checked."""

    @pytest.fixture
    def probes(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(cli, "require_elyan_ecosystem", lambda: calls.append(1))
        monkeypatch.setattr(
            "shaprai.elyan_bus.ElyanBus.onboard_agent",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")),
        )
        monkeypatch.setattr(cli, "SHAPRAI_HOME", tmp_path / "home")
        monkeypatch.setattr(cli, "AGENTS_DIR", tmp_path / "home" / "agents")
        return calls

    @pytest.mark.parametrize(
        "args",
        [
            ["create", "../escaped"],
            ["create", "has space"],
            ["evaluate", "../planted"],
            ["mcp", "../planted"],
        ],
    )
    def test_bad_name_reported_without_probing(self, probes, args):
        result = CliRunner().invoke(cli.main, ["--format", "plain", *args])
        assert result.exit_code == 2
        assert "Invalid" in result.output
        assert probes == []

    def test_valid_command_still_probes_once(self, probes):
        result = CliRunner().invoke(cli.main, ["--format", "plain", "template", "list"])
        assert result.exit_code == 0, result.output
        assert probes == [1]

    def test_skip_checks_never_probes(self, probes):
        result = CliRunner().invoke(
            cli.main, ["--skip-checks", "--format", "plain", "template", "list"]
        )
        assert result.exit_code == 0, result.output
        assert probes == []
