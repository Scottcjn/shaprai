# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Accessible output formatting for the ShaprAI CLI.

Provides utilities for rendering CLI output in formats compatible with
screen readers and other assistive technologies. The Flameholder has TBI
and mobility challenges — accessibility is core to our mission.

WCAG 2.1 AA references addressed:
- 1.3.1 Info and Relationships: Structured output preserves data relationships
- 1.3.2 Meaningful Sequence: Output follows a logical reading order
- 3.3.1 Error Identification: Consistent, machine-parseable error format
- 3.3.2 Labels or Instructions: Clear field labels in all output modes
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

import click


class OutputFormat(str, Enum):
    """Supported CLI output formats.

    TEXT: Human-readable formatted text (default).
    JSON: Machine-readable JSON for assistive technology and scripting.
    PLAIN: Simplified text without alignment tricks — screen reader friendly.
    """

    TEXT = "text"
    JSON = "json"
    PLAIN = "plain"


# Click context key for the active output format
_FORMAT_CTX_KEY = "output_format"


def get_output_format(ctx: Optional[click.Context] = None) -> OutputFormat:
    """Retrieve the active output format from the Click context.

    Args:
        ctx: Click context. If None, uses the current context.

    Returns:
        The active OutputFormat. Defaults to TEXT if unset.
    """
    if ctx is None:
        ctx = click.get_current_context(silent=True)
    if ctx is None:
        return OutputFormat.TEXT
    return ctx.ensure_object(dict).get(_FORMAT_CTX_KEY, OutputFormat.TEXT)


def set_output_format(ctx: click.Context, fmt: OutputFormat) -> None:
    """Store the output format in the Click context.

    Args:
        ctx: Click context to update.
        fmt: The OutputFormat to activate.
    """
    ctx.ensure_object(dict)[_FORMAT_CTX_KEY] = fmt


def emit_error(message: str, hint: Optional[str] = None) -> None:
    """Write a consistently formatted error message to stderr.

    Ensures every error follows the same structure so screen readers
    can reliably identify error output. (WCAG 3.3.1 Error Identification)

    Args:
        message: The primary error description.
        hint: Optional corrective suggestion (WCAG 3.3.3 Error Suggestion).
    """
    fmt = get_output_format()
    if fmt == OutputFormat.JSON:
        payload: Dict[str, Any] = {"error": message}
        if hint:
            payload["hint"] = hint
        click.echo(json.dumps(payload, indent=2), err=True)
    else:
        click.echo(f"Error: {message}", err=True)
        if hint:
            click.echo(f"Hint: {hint}", err=True)


def emit_success(message: str) -> None:
    """Write a consistently formatted success message to stdout.

    Args:
        message: The success description.
    """
    fmt = get_output_format()
    if fmt == OutputFormat.JSON:
        click.echo(json.dumps({"status": "ok", "message": message}))
    else:
        click.echo(message)


def emit_key_value(pairs: List[tuple[str, str]], title: Optional[str] = None) -> None:
    """Render a list of labelled key-value pairs.

    In TEXT mode, uses aligned formatting.
    In PLAIN mode, uses "Key: Value" lines (screen-reader friendly).
    In JSON mode, emits a JSON object.

    WCAG 1.3.1: Labels are always explicitly associated with their values
    regardless of output format.

    Args:
        pairs: Sequence of (label, value) tuples.
        title: Optional heading printed before the pairs.
    """
    fmt = get_output_format()

    if fmt == OutputFormat.JSON:
        data: Dict[str, Any] = {}
        if title:
            data["title"] = title
        for label, value in pairs:
            # Normalise label to a JSON-safe key
            key = label.strip().rstrip(":").lower().replace(" ", "_")
            data[key] = value
        click.echo(json.dumps(data, indent=2))
        return

    if title:
        click.echo(title)

    if fmt == OutputFormat.PLAIN:
        for label, value in pairs:
            click.echo(f"{label}: {value}")
    else:
        # Aligned text output
        width = max((len(label) for label, _ in pairs), default=0) + 1
        for label, value in pairs:
            click.echo(f"  {label + ':':<{width}} {value}")


def emit_table(
    headers: List[str],
    rows: List[List[str]],
    title: Optional[str] = None,
    footer: Optional[str] = None,
) -> None:
    """Render a data table in an accessible format.

    TEXT mode: Column-aligned table with separator line.
    PLAIN mode: Each row is printed as labelled fields so screen readers
                can associate each value with its column header.
                (WCAG 1.3.1 Info and Relationships)
    JSON mode: Array of objects keyed by header names.

    Args:
        headers: Column header labels.
        rows: List of rows, each a list of cell strings.
        title: Optional heading above the table.
        footer: Optional summary line below the table.
    """
    fmt = get_output_format()

    if fmt == OutputFormat.JSON:
        records = []
        for row in rows:
            record = {}
            for i, header in enumerate(headers):
                key = header.strip().lower().replace(" ", "_")
                record[key] = row[i] if i < len(row) else ""
            records.append(record)
        payload: Dict[str, Any] = {"data": records, "count": len(records)}
        if title:
            payload["title"] = title
        click.echo(json.dumps(payload, indent=2))
        return

    if title:
        click.echo(title)

    if fmt == OutputFormat.PLAIN:
        # Screen-reader-friendly: each row is a labelled block
        for idx, row in enumerate(rows):
            if idx > 0:
                click.echo("")  # Blank line between records
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else ""
                click.echo(f"{header}: {value}")
    else:
        # Aligned text table
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(cell))

        header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        click.echo(header_line)
        click.echo("-" * len(header_line))

        for row in rows:
            cells = []
            for i, w in enumerate(col_widths):
                cell = row[i] if i < len(row) else ""
                cells.append(cell.ljust(w))
            click.echo("  ".join(cells))

    if footer:
        click.echo(footer)
