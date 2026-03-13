# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Tests for the shaprai.a11y accessible output module.

Validates that all three output formats (text, json, plain) produce
correct, parseable output — critical for screen-reader and assistive-
technology users.

WCAG 2.1 AA references:
- 1.3.1 Info and Relationships (tables, key-value associations)
- 1.3.2 Meaningful Sequence (logical reading order)
- 3.3.1 Error Identification (consistent error format)
- 3.3.2 Labels or Instructions (clear labelling)
"""

from __future__ import annotations

import json

import click
import pytest
from click.testing import CliRunner

from shaprai.a11y import (
    OutputFormat,
    emit_error,
    emit_key_value,
    emit_success,
    emit_table,
    get_output_format,
    set_output_format,
)


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click test runner."""
    return CliRunner()


def _make_cli(output_format: str = "text"):
    """Create a minimal Click CLI that sets the output format for testing."""

    @click.group()
    @click.option("--format", "output_format", default=output_format)
    @click.pass_context
    def cli(ctx: click.Context, output_format: str) -> None:
        set_output_format(ctx, OutputFormat(output_format))

    return cli


# ------------------------------------------------------------------ #
#  OutputFormat enum
# ------------------------------------------------------------------ #


class TestOutputFormat:
    """OutputFormat enum resolves from lowercase strings."""

    def test_text(self) -> None:
        assert OutputFormat("text") is OutputFormat.TEXT

    def test_json(self) -> None:
        assert OutputFormat("json") is OutputFormat.JSON

    def test_plain(self) -> None:
        assert OutputFormat("plain") is OutputFormat.PLAIN

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            OutputFormat("csv")


# ------------------------------------------------------------------ #
#  get / set output format
# ------------------------------------------------------------------ #


class TestFormatContext:
    """Output format is stored in and retrieved from Click context."""

    def test_default_is_text(self) -> None:
        """Without a Click context, default to TEXT."""
        assert get_output_format(None) == OutputFormat.TEXT

    def test_roundtrip(self, runner: CliRunner) -> None:
        cli = _make_cli("json")

        @cli.command()
        def check() -> None:
            fmt = get_output_format()
            click.echo(f"format={fmt.value}")

        result = runner.invoke(cli, ["--format", "json", "check"])
        assert result.exit_code == 0
        assert "format=json" in result.output


# ------------------------------------------------------------------ #
#  emit_error
# ------------------------------------------------------------------ #


class TestEmitError:
    """Error messages are consistent across formats (WCAG 3.3.1)."""

    def test_text_error_prefix(self, runner: CliRunner) -> None:
        """Text errors start with 'Error:' for screen-reader parsing."""
        cli = _make_cli("text")

        @cli.command()
        def fail() -> None:
            emit_error("something broke")

        result = runner.invoke(cli, ["fail"])
        assert "Error: something broke" in result.output

    def test_text_error_with_hint(self, runner: CliRunner) -> None:
        """Hints are printed on a separate labelled line."""
        cli = _make_cli("text")

        @cli.command()
        def fail() -> None:
            emit_error("not found", hint="try shaprai create first")

        result = runner.invoke(cli, ["fail"])
        assert "Error: not found" in result.output
        assert "Hint: try shaprai create first" in result.output

    def test_json_error_is_valid_json(self, runner: CliRunner) -> None:
        """JSON errors are parseable by assistive tools."""
        cli = _make_cli("json")

        @cli.command()
        def fail() -> None:
            emit_error("bad input", hint="fix it")

        result = runner.invoke(cli, ["fail"])
        data = json.loads(result.output.strip())
        assert data["error"] == "bad input"
        assert data["hint"] == "fix it"

    def test_json_error_without_hint(self, runner: CliRunner) -> None:
        cli = _make_cli("json")

        @cli.command()
        def fail() -> None:
            emit_error("oops")

        result = runner.invoke(cli, ["fail"])
        data = json.loads(result.output.strip())
        assert data["error"] == "oops"
        assert "hint" not in data

    def test_plain_error_same_as_text(self, runner: CliRunner) -> None:
        """Plain mode uses the same error format as text (both readable)."""
        cli = _make_cli("plain")

        @cli.command()
        def fail() -> None:
            emit_error("gone", hint="retry")

        result = runner.invoke(cli, ["fail"])
        assert "Error: gone" in result.output
        assert "Hint: retry" in result.output


# ------------------------------------------------------------------ #
#  emit_success
# ------------------------------------------------------------------ #


class TestEmitSuccess:
    """Success messages are formatted per mode."""

    def test_text_success(self, runner: CliRunner) -> None:
        cli = _make_cli("text")

        @cli.command()
        def ok() -> None:
            emit_success("all done")

        result = runner.invoke(cli, ["ok"])
        assert "all done" in result.output

    def test_json_success_is_valid_json(self, runner: CliRunner) -> None:
        cli = _make_cli("json")

        @cli.command()
        def ok() -> None:
            emit_success("all done")

        result = runner.invoke(cli, ["ok"])
        data = json.loads(result.output.strip())
        assert data["status"] == "ok"
        assert data["message"] == "all done"


# ------------------------------------------------------------------ #
#  emit_key_value  (WCAG 1.3.1 — labels associated with values)
# ------------------------------------------------------------------ #


class TestEmitKeyValue:
    """Key-value output preserves label-to-value associations."""

    def test_text_aligned(self, runner: CliRunner) -> None:
        cli = _make_cli("text")

        @cli.command()
        def info() -> None:
            emit_key_value([("Name", "alpha"), ("State", "CREATED")], title="Agent")

        result = runner.invoke(cli, ["info"])
        assert "Agent" in result.output
        assert "Name:" in result.output
        assert "alpha" in result.output
        assert "State:" in result.output
        assert "CREATED" in result.output

    def test_plain_label_colon_value(self, runner: CliRunner) -> None:
        """Plain mode uses simple 'Label: Value' lines — screen reader friendly."""
        cli = _make_cli("plain")

        @cli.command()
        def info() -> None:
            emit_key_value([("Name", "alpha"), ("State", "CREATED")])

        result = runner.invoke(cli, ["info"])
        lines = result.output.strip().split("\n")
        assert lines[0] == "Name: alpha"
        assert lines[1] == "State: CREATED"

    def test_json_key_value(self, runner: CliRunner) -> None:
        """JSON mode produces a flat object for easy parsing."""
        cli = _make_cli("json")

        @cli.command()
        def info() -> None:
            emit_key_value(
                [("Model", "qwen"), ("State", "TRAINING")],
                title="Details",
            )

        result = runner.invoke(cli, ["info"])
        data = json.loads(result.output.strip())
        assert data["title"] == "Details"
        assert data["model"] == "qwen"
        assert data["state"] == "TRAINING"


# ------------------------------------------------------------------ #
#  emit_table  (WCAG 1.3.1 — table structure preserved)
# ------------------------------------------------------------------ #


class TestEmitTable:
    """Table output is parseable in all formats."""

    HEADERS = ["Name", "State", "Platforms"]
    ROWS = [
        ["alpha", "DEPLOYED", "github, bottube"],
        ["beta", "TRAINING", "github"],
    ]

    def test_text_table_has_header_and_separator(self, runner: CliRunner) -> None:
        cli = _make_cli("text")

        @cli.command()
        def show() -> None:
            emit_table(self.HEADERS, self.ROWS)

        result = runner.invoke(cli, ["show"])
        lines = result.output.strip().split("\n")
        # First line is the header row
        assert "Name" in lines[0]
        assert "State" in lines[0]
        assert "Platforms" in lines[0]
        # Second line is a separator
        assert lines[1].startswith("---")
        # Data rows follow
        assert "alpha" in lines[2]
        assert "beta" in lines[3]

    def test_text_table_with_footer(self, runner: CliRunner) -> None:
        cli = _make_cli("text")

        @cli.command()
        def show() -> None:
            emit_table(self.HEADERS, self.ROWS, footer="Total: 2")

        result = runner.invoke(cli, ["show"])
        assert "Total: 2" in result.output

    def test_plain_table_labels_each_field(self, runner: CliRunner) -> None:
        """Plain mode repeats column header for every cell — screen readers
        can announce each field with its label (WCAG 1.3.1)."""
        cli = _make_cli("plain")

        @cli.command()
        def show() -> None:
            emit_table(self.HEADERS, self.ROWS)

        result = runner.invoke(cli, ["show"])
        output = result.output
        # Each row's cells are labelled with the header
        assert "Name: alpha" in output
        assert "State: DEPLOYED" in output
        assert "Platforms: github, bottube" in output
        assert "Name: beta" in output
        assert "State: TRAINING" in output

    def test_json_table_is_array_of_objects(self, runner: CliRunner) -> None:
        """JSON table is an array keyed by header names — parseable by scripts."""
        cli = _make_cli("json")

        @cli.command()
        def show() -> None:
            emit_table(self.HEADERS, self.ROWS, title="Fleet")

        result = runner.invoke(cli, ["show"])
        data = json.loads(result.output.strip())
        assert data["title"] == "Fleet"
        assert data["count"] == 2
        assert data["data"][0]["name"] == "alpha"
        assert data["data"][0]["state"] == "DEPLOYED"
        assert data["data"][1]["name"] == "beta"

    def test_empty_table(self, runner: CliRunner) -> None:
        """Empty tables render without errors."""
        cli = _make_cli("text")

        @cli.command()
        def show() -> None:
            emit_table(["A", "B"], [])

        result = runner.invoke(cli, ["show"])
        assert result.exit_code == 0
        assert "A" in result.output  # Headers still shown

    def test_json_empty_table(self, runner: CliRunner) -> None:
        cli = _make_cli("json")

        @cli.command()
        def show() -> None:
            emit_table(["A", "B"], [])

        result = runner.invoke(cli, ["show"])
        data = json.loads(result.output.strip())
        assert data["count"] == 0
        assert data["data"] == []

    def test_table_with_title(self, runner: CliRunner) -> None:
        cli = _make_cli("text")

        @cli.command()
        def show() -> None:
            emit_table(["Col"], [["val"]], title="My Table")

        result = runner.invoke(cli, ["show"])
        lines = result.output.strip().split("\n")
        assert lines[0] == "My Table"


# ------------------------------------------------------------------ #
#  Edge cases
# ------------------------------------------------------------------ #


class TestEdgeCases:
    """Edge cases that could break assistive technology parsing."""

    def test_key_value_normalises_keys_for_json(self, runner: CliRunner) -> None:
        """JSON keys are lowercased and have spaces replaced with underscores."""
        cli = _make_cli("json")

        @cli.command()
        def info() -> None:
            emit_key_value([("Elyan-class threshold", "0.85")])

        result = runner.invoke(cli, ["info"])
        data = json.loads(result.output.strip())
        assert "elyan-class_threshold" in data

    def test_table_short_row_pads_missing_cells(self, runner: CliRunner) -> None:
        """Rows shorter than headers get empty strings — no IndexError."""
        cli = _make_cli("json")

        @cli.command()
        def show() -> None:
            emit_table(["A", "B", "C"], [["only_a"]])

        result = runner.invoke(cli, ["show"])
        data = json.loads(result.output.strip())
        assert data["data"][0]["a"] == "only_a"
        assert data["data"][0]["b"] == ""
        assert data["data"][0]["c"] == ""
