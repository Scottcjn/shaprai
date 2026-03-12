# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Template validation for marketplace submissions.

Validates template YAML/JSON against the AgentTemplate schema before
publishing to the marketplace. Ensures all required fields are present
and values are within acceptable ranges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


# Schema definition for template validation
TEMPLATE_SCHEMA = {
    "name": {
        "type": str,
        "required": True,
        "pattern": r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$",
        "min_length": 2,
        "max_length": 64,
        "description": "Unique template identifier (lowercase, alphanumeric, hyphens, underscores)",
    },
    "version": {
        "type": str,
        "required": True,
        "pattern": r"^\d+\.\d+\.\d+$",
        "description": "Semver version string (e.g., '1.0.0')",
    },
    "description": {
        "type": str,
        "required": True,
        "min_length": 10,
        "max_length": 500,
        "description": "Human-readable description of the template",
    },
    "author": {
        "type": str,
        "required": True,
        "min_length": 1,
        "max_length": 64,
        "description": "Creator's identifier (wallet ID or username)",
    },
    "model": {
        "type": dict,
        "required": True,
        "description": "Model configuration",
    },
    "personality": {
        "type": dict,
        "required": False,
        "description": "Personality configuration",
    },
    "capabilities": {
        "type": list,
        "required": False,
        "description": "List of agent capabilities",
    },
    "platforms": {
        "type": list,
        "required": False,
        "description": "Target deployment platforms",
    },
    "ethics_profile": {
        "type": str,
        "required": False,
        "default": "sophiacore_default",
        "description": "Ethics framework identifier",
    },
    "driftlock": {
        "type": dict,
        "required": False,
        "description": "DriftLock configuration",
    },
    "rtc_config": {
        "type": dict,
        "required": False,
        "description": "RustChain token configuration",
    },
    "tags": {
        "type": list,
        "required": False,
        "description": "Searchable tags for marketplace discovery",
    },
    "price_rtc": {
        "type": (int, float),
        "required": True,
        "min": 0,
        "description": "Price in RTC tokens (0 = free)",
    },
}

# Valid capability values
VALID_CAPABILITIES = {
    "code_review",
    "pr_submission",
    "bounty_discovery",
    "issue_triage",
    "test_writing",
    "security_audit",
    "test_coverage_analysis",
    "pr_commenting",
    "content_discovery",
    "commenting",
    "cross_posting",
    "community_moderation",
    "trend_analysis",
    "video_scripting",
    "article_writing",
    "social_posting",
    "image_generation",
    "trend_surfing",
    "general",
}

# Valid platform values
VALID_PLATFORMS = {
    "github",
    "rustchain",
    "bottube",
    "moltbook",
    "fourclaw",
    "clawcities",
    "agentchan",
    "pinchedin",
}


@dataclass
class ValidationResult:
    """Result of template validation.

    Attributes:
        valid: Whether the template passed validation.
        errors: List of validation errors (if any).
        warnings: List of validation warnings (if any).
        template_name: Validated template name (if valid).
        template_version: Validated template version (if valid).
    """

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    template_name: Optional[str] = None
    template_version: Optional[str] = None

    def __bool__(self) -> bool:
        return self.valid


class TemplateValidator:
    """Validates agent templates against the marketplace schema.

    Validates structure, types, constraints, and semantic rules for
    templates before they can be published to the marketplace.
    """

    def __init__(self, strict: bool = True):
        """Initialize the validator.

        Args:
            strict: If True, treat warnings as errors. Default: True.
        """
        self.strict = strict
        self._errors: List[str] = []
        self._warnings: List[str] = []

    def validate(self, template: Dict[str, Any]) -> ValidationResult:
        """Validate a template dictionary against the schema.

        Args:
            template: Template data to validate.

        Returns:
            ValidationResult with valid flag, errors, and warnings.
        """
        self._errors = []
        self._warnings = []

        # Check required fields
        self._validate_required_fields(template)

        # Validate each field against schema
        for field_name, field_schema in TEMPLATE_SCHEMA.items():
            if field_name in template:
                self._validate_field(field_name, template[field_name], field_schema)

        # Semantic validations
        if "name" in template and "version" in template:
            self._validate_semantics(template)

        # Build result
        errors = self._errors.copy()
        warnings = self._warnings.copy()

        if self.strict:
            errors.extend(warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings if not self.strict else [],
            template_name=template.get("name") if len(errors) == 0 else None,
            template_version=template.get("version") if len(errors) == 0 else None,
        )

    def _validate_required_fields(self, template: Dict[str, Any]) -> None:
        """Check that all required fields are present."""
        for field_name, field_schema in TEMPLATE_SCHEMA.items():
            if field_schema.get("required", False) and field_name not in template:
                self._errors.append(f"Missing required field: {field_name}")

    def _validate_field(
        self,
        field_name: str,
        value: Any,
        schema: Dict[str, Any],
    ) -> None:
        """Validate a single field against its schema."""
        expected_type = schema.get("type")

        # Type check
        if expected_type and not isinstance(value, expected_type):
            self._errors.append(
                f"Field '{field_name}' has wrong type: expected {expected_type}, got {type(value)}"
            )
            return

        # String validations
        if isinstance(value, str):
            self._validate_string_field(field_name, value, schema)

        # Numeric validations
        if isinstance(value, (int, float)):
            self._validate_numeric_field(field_name, value, schema)

        # List validations
        if isinstance(value, list):
            self._validate_list_field(field_name, value, schema)

        # Dict validations
        if isinstance(value, dict):
            self._validate_dict_field(field_name, value, schema)

    def _validate_string_field(
        self,
        field_name: str,
        value: str,
        schema: Dict[str, Any],
    ) -> None:
        """Validate string field constraints."""
        min_len = schema.get("min_length")
        max_len = schema.get("max_length")
        pattern = schema.get("pattern")

        if min_len is not None and len(value) < min_len:
            self._errors.append(
                f"Field '{field_name}' is too short: {len(value)} < {min_len}"
            )

        if max_len is not None and len(value) > max_len:
            self._errors.append(
                f"Field '{field_name}' is too long: {len(value)} > {max_len}"
            )

        if pattern and not re.match(pattern, value):
            self._errors.append(
                f"Field '{field_name}' doesn't match pattern: {pattern}"
            )

    def _validate_numeric_field(
        self,
        field_name: str,
        value: float,
        schema: Dict[str, Any],
    ) -> None:
        """Validate numeric field constraints."""
        min_val = schema.get("min")
        max_val = schema.get("max")

        if min_val is not None and value < min_val:
            self._errors.append(
                f"Field '{field_name}' is below minimum: {value} < {min_val}"
            )

        if max_val is not None and value > max_val:
            self._errors.append(
                f"Field '{field_name}' exceeds maximum: {value} > {max_val}"
            )

    def _validate_list_field(
        self,
        field_name: str,
        value: List[Any],
        schema: Dict[str, Any],
    ) -> None:
        """Validate list field constraints."""
        if field_name == "capabilities":
            invalid = [c for c in value if c not in VALID_CAPABILITIES]
            if invalid:
                self._warnings.append(
                    f"Unknown capabilities in '{field_name}': {invalid}"
                )

        if field_name == "platforms":
            invalid = [p for p in value if p not in VALID_PLATFORMS]
            if invalid:
                self._warnings.append(
                    f"Unknown platforms in '{field_name}': {invalid}"
                )

        if field_name == "tags":
            for tag in value:
                if not isinstance(tag, str):
                    self._errors.append(f"Tags must be strings, got: {type(tag)}")
                elif len(tag) > 32:
                    self._errors.append(f"Tag too long (max 32 chars): {tag[:33]}...")

    def _validate_dict_field(
        self,
        field_name: str,
        value: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> None:
        """Validate dict field constraints."""
        if field_name == "model":
            if "base" not in value:
                self._errors.append("Model config must include 'base' model ID")

        if field_name == "driftlock":
            if "enabled" in value and not isinstance(value["enabled"], bool):
                self._errors.append("DriftLock 'enabled' must be boolean")

    def _validate_semantics(self, template: Dict[str, Any]) -> None:
        """Validate semantic rules across fields."""
        # Check version is valid semver
        version = template.get("version", "")
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            self._errors.append(f"Invalid semver version: {version}")

        # Check name doesn't conflict with reserved names
        name = template.get("name", "")
        reserved = {"template", "default", "system", "marketplace", "admin"}
        if name.lower() in reserved:
            self._errors.append(f"Template name is reserved: {name}")

        # Check price_rtc is reasonable
        price = template.get("price_rtc", 0)
        if price > 10000:
            self._warnings.append(f"Price {price} RTC seems very high (>10000)")
        if price < 0:
            self._errors.append(f"Price cannot be negative: {price}")

    def validate_file(self, file_path: str) -> ValidationResult:
        """Validate a template file (YAML or JSON).

        Args:
            file_path: Path to the template file.

        Returns:
            ValidationResult with valid flag, errors, and warnings.
        """
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return ValidationResult(
                valid=False,
                errors=[f"File not found: {file_path}"],
            )

        try:
            content = path.read_text()

            if path.suffix in (".yaml", ".yml"):
                import yaml

                template = yaml.safe_load(content)
            elif path.suffix == ".json":
                template = json.loads(content)
            else:
                return ValidationResult(
                    valid=False,
                    errors=[f"Unsupported file format: {path.suffix}"],
                )

            if not isinstance(template, dict):
                return ValidationResult(
                    valid=False,
                    errors=["Template must be a dictionary"],
                )

            return self.validate(template)

        except yaml.YAMLError as e:
            return ValidationResult(
                valid=False,
                errors=[f"YAML parsing error: {e}"],
            )
        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                errors=[f"JSON parsing error: {e}"],
            )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[f"Error reading file: {e}"],
            )