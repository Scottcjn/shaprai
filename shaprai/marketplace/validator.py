# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""Template schema validation before publish."""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of template validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class TemplateValidator:
    """Validate template schema before publishing."""

    REQUIRED_FIELDS = ["name", "version", "author", "model", "capabilities"]
    OPTIONAL_FIELDS = ["description", "tags", "platforms", "training", "ethics"]

    def validate(self, template_content: str) -> ValidationResult:
        """Validate a template file.
        
        Args:
            template_content: YAML or JSON content of the template
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []

        # Parse the template
        try:
            if template_content.strip().startswith("{"):
                template = json.loads(template_content)
            else:
                template = yaml.safe_load(template_content)
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Failed to parse template: {e}"],
                warnings=[],
            )

        if not isinstance(template, dict):
            return ValidationResult(
                is_valid=False,
                errors=["Template must be a YAML/JSON object"],
                warnings=[],
            )

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in template:
                errors.append(f"Missing required field: {field}")

        # Validate name
        if "name" in template:
            name = template["name"]
            if not isinstance(name, str):
                errors.append("name must be a string")
            elif not name.replace("-", "").replace("_", "").isalnum():
                errors.append("name must be alphanumeric (hyphens and underscores allowed)")

        # Validate version (semver)
        if "version" in template:
            version = template["version"]
            if not isinstance(version, str):
                errors.append("version must be a string")
            elif not self._is_valid_semver(version):
                errors.append(f"version must be valid semver (e.g., 1.0.0): {version}")

        # Validate author
        if "author" in template:
            author = template["author"]
            if not isinstance(author, str):
                errors.append("author must be a string")

        # Validate model
        if "model" in template:
            model = template["model"]
            if not isinstance(model, dict):
                errors.append("model must be an object")
            elif "base" not in model:
                warnings.append("model.base is recommended for specifying the base model")

        # Validate capabilities
        if "capabilities" in template:
            capabilities = template["capabilities"]
            if not isinstance(capabilities, list):
                errors.append("capabilities must be a list")
            elif len(capabilities) == 0:
                warnings.append("capabilities list is empty")

        # Validate tags if present
        if "tags" in template:
            tags = template["tags"]
            if not isinstance(tags, list):
                errors.append("tags must be a list")
            else:
                for tag in tags:
                    if not isinstance(tag, str):
                        errors.append(f"tag must be a string: {tag}")

        # Validate description if present
        if "description" in template:
            description = template["description"]
            if not isinstance(description, str):
                errors.append("description must be a string")
            elif len(description) > 500:
                warnings.append(f"description is long ({len(description)} chars, recommend < 500)")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_file(self, template_path: Path) -> ValidationResult:
        """Validate a template file from path.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            ValidationResult with validation status
        """
        if not template_path.exists():
            return ValidationResult(
                is_valid=False,
                errors=[f"Template file not found: {template_path}"],
                warnings=[],
            )

        content = template_path.read_text()
        return self.validate(content)

    def _is_valid_semver(self, version: str) -> bool:
        """Check if version is valid semver."""
        import re
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        return bool(re.match(pattern, version))


def validate_template(template_content: str) -> Tuple[bool, List[str], List[str]]:
    """Convenience function to validate a template.
    
    Args:
        template_content: YAML or JSON content of the template
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    validator = TemplateValidator()
    result = validator.validate(template_content)
    return result.is_valid, result.errors, result.warnings
