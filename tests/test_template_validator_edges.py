# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""Edge-case tests for marketplace template validation."""

import json

import pytest

from shaprai.marketplace.validator import TemplateValidator


@pytest.fixture
def validator():
    """Return a fresh validator for each test."""
    return TemplateValidator()


def test_rejects_yaml_and_json_non_object_templates(validator):
    """Template content must parse to a mapping, not another YAML/JSON type."""
    yaml_result = validator.validate("- chat\n- code\n")
    json_result = validator.validate(json.dumps(["chat", "code"]))

    assert yaml_result.is_valid is False
    assert yaml_result.errors == ["Template must be a YAML/JSON object"]
    assert yaml_result.warnings == []

    assert json_result.is_valid is False
    assert json_result.errors == ["Template must be a YAML/JSON object"]
    assert json_result.warnings == []


def test_collects_field_type_errors_without_short_circuiting(validator):
    """Invalid field types should be reported together for one template."""
    content = """
name:
  - not
  - text
version: 1.0
author:
  handle: alice
model: gpt-4
capabilities: chat
tags:
  - useful
  - 42
description:
  - not
  - text
"""

    result = validator.validate(content)

    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "name must be a string",
        "version must be a string",
        "author must be a string",
        "model must be an object",
        "capabilities must be a list",
        "tag must be a string: 42",
        "description must be a string",
    ]


def test_warning_only_template_remains_valid(validator):
    """Recommended metadata gaps should warn without rejecting the template."""
    content = f"""
name: warning-agent
version: 1.0.0
author: test-author
model: {{}}
capabilities: []
description: {"x" * 501}
"""

    result = validator.validate(content)

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == [
        "model.base is recommended for specifying the base model",
        "capabilities list is empty",
        "description is long (501 chars, recommend < 500)",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "agent with spaces",
        "agent.with.dot",
        "agent/with/slash",
    ],
)
def test_rejects_names_outside_allowed_characters(validator, name):
    """Only alphanumeric names plus hyphens and underscores are accepted."""
    content = f"""
name: {name}
version: 1.0.0
author: test-author
model:
  base: gpt-4
capabilities:
  - chat
"""

    result = validator.validate(content)

    assert result.is_valid is False
    assert result.errors == [
        "name must be alphanumeric (hyphens and underscores allowed)"
    ]


def test_accepts_semver_prerelease_and_build_metadata(validator):
    """Semver prerelease and build metadata should pass validation."""
    content = """
name: semver-agent
version: 2.4.0-beta.3+build.12
author: test-author
model:
  base: gpt-4
capabilities:
  - chat
"""

    result = validator.validate(content)

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []


def test_validate_file_reports_missing_file_and_reads_existing_file(tmp_path, validator):
    """validate_file should handle both absent paths and readable templates."""
    missing_path = tmp_path / "missing.yaml"
    missing_result = validator.validate_file(missing_path)

    assert missing_result.is_valid is False
    assert missing_result.errors == [f"Template file not found: {missing_path}"]
    assert missing_result.warnings == []

    template_path = tmp_path / "agent.json"
    template_path.write_text(
        json.dumps(
            {
                "name": "file-agent",
                "version": "1.0.0",
                "author": "test-author",
                "model": {"base": "gpt-4"},
                "capabilities": ["chat"],
            }
        )
    )

    file_result = validator.validate_file(template_path)

    assert file_result.is_valid is True
    assert file_result.errors == []
    assert file_result.warnings == []
