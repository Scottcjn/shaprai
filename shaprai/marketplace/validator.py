"""Template Validator — Schema validation before publishing."""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import yaml

logger = logging.getLogger("shaprai.marketplace.validator")


class ValidationError:
    """A validation error."""
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # error, warning

    def __repr__(self):
        return f"{self.severity.upper()}: {self.field} - {self.message}"


class TemplateValidator:
    """Validate agent personality templates before publishing.

    Ensures templates meet schema requirements and best practices.
    """

    REQUIRED_FIELDS = ["name", "description"]
    RECOMMENDED_FIELDS = ["traits", "values", "voice", "boundaries"]
    VALID_TRAIT_COUNT = (2, 10)  # Min, max
    VALID_VALUE_COUNT = (1, 8)   # Min, max

    def __init__(self):
        """Initialize validator."""
        self._errors: List[ValidationError] = []

    def validate(
        self,
        content: str,
        content_type: str = "auto"
    ) -> Tuple[bool, List[ValidationError]]:
        """Validate template content.

        Args:
            content: Template content (YAML or JSON)
            content_type: "yaml", "json", or "auto"

        Returns:
            Tuple of (is_valid, errors)
        """
        self._errors = []

        # Detect format if auto
        if content_type == "auto":
            content_type = self._detect_format(content)

        # Parse content
        try:
            if content_type == "yaml":
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
        except Exception as e:
            self._errors.append(ValidationError(
                "content", f"Failed to parse {content_type}: {e}"
            ))
            return False, self._errors

        if data is None:
            self._errors.append(ValidationError(
                "content", "Empty template content"
            ))
            return False, self._errors

        # Run validations
        self._validate_required_fields(data)
        self._validate_name(data)
        self._validate_description(data)
        self._validate_traits(data)
        self._validate_values(data)
        self._validate_version(data)
        self._validate_no_forbidden_patterns(data)

        is_valid = not any(e.severity == "error" for e in self._errors)

        return is_valid, self._errors

    def _detect_format(self, content: str) -> str:
        """Detect content format."""
        stripped = content.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"
        return "yaml"

    def _validate_required_fields(self, data: Dict):
        """Check required fields exist."""
        for field in self.REQUIRED_FIELDS:
            if field not in data or not data[field]:
                self._errors.append(ValidationError(
                    field, f"Required field '{field}' is missing or empty"
                ))

    def _validate_name(self, data: Dict):
        """Validate template name."""
        if "name" not in data:
            return

        name = data["name"]

        if len(name) < 2:
            self._errors.append(ValidationError(
                "name", "Name must be at least 2 characters"
            ))

        if len(name) > 100:
            self._errors.append(ValidationError(
                "name", "Name must be under 100 characters"
            ))

        # Check for special characters
        if not re.match(r'^[\w\s\-\'\"]+$', name):
            self._errors.append(ValidationError(
                "name",
                "Name contains invalid characters",
                "warning"
            ))

    def _validate_description(self, data: Dict):
        """Validate description."""
        if "description" not in data:
            return

        desc = data["description"]

        if len(desc) < 10:
            self._errors.append(ValidationError(
                "description",
                "Description should be at least 10 characters",
                "warning"
            ))

        if len(desc) > 2000:
            self._errors.append(ValidationError(
                "description", "Description must be under 2000 characters"
            ))

    def _validate_traits(self, data: Dict):
        """Validate personality traits."""
        if "traits" not in data:
            return

        traits = data["traits"]

        if not isinstance(traits, list):
            self._errors.append(ValidationError(
                "traits", "Traits must be a list"
            ))
            return

        min_traits, max_traits = self.VALID_TRAIT_COUNT

        if len(traits) < min_traits:
            self._errors.append(ValidationError(
                "traits",
                f"At least {min_traits} traits recommended",
                "warning"
            ))

        if len(traits) > max_traits:
            self._errors.append(ValidationError(
                "traits",
                f"No more than {max_traits} traits recommended",
                "warning"
            ))

        for i, trait in enumerate(traits):
            if not isinstance(trait, str):
                self._errors.append(ValidationError(
                    f"traits[{i}]", "Each trait must be a string"
                ))
            elif len(trait) > 50:
                self._errors.append(ValidationError(
                    f"traits[{i}]",
                    "Trait should be under 50 characters",
                    "warning"
                ))

    def _validate_values(self, data: Dict):
        """Validate core values."""
        if "values" not in data:
            return

        values = data["values"]

        if not isinstance(values, list):
            self._errors.append(ValidationError(
                "values", "Values must be a list"
            ))
            return

        min_vals, max_vals = self.VALID_VALUE_COUNT

        if len(values) < min_vals:
            self._errors.append(ValidationError(
                "values",
                f"At least {min_vals} values recommended",
                "warning"
            ))

        if len(values) > max_vals:
            self._errors.append(ValidationError(
                "values",
                f"No more than {max_vals} values recommended",
                "warning"
            ))

    def _validate_version(self, data: Dict):
        """Validate version if present."""
        if "version" not in data:
            return

        version = data["version"]

        # Basic semver check
        if not re.match(r'^\d+\.\d+\.\d+', version):
            self._errors.append(ValidationError(
                "version",
                "Version should follow semver (e.g., 1.2.3)",
                "warning"
            ))

    def _validate_no_forbidden_patterns(self, data: Dict):
        """Check for patterns that shouldn't be in templates."""
        content_str = json.dumps(data, default=str).lower()

        forbidden = [
            ("api_key", "Hardcoded API keys should not be in templates"),
            ("password", "Hardcoded passwords should not be in templates"),
            ("secret", "Secrets should not be in templates"),
        ]

        for pattern, message in forbidden:
            if pattern in content_str:
                self._errors.append(ValidationError(
                    "content", message
                ))

    def validate_file(self, filepath: Path) -> Tuple[bool, List[ValidationError]]:
        """Validate a template file.

        Args:
            filepath: Path to template file

        Returns:
            Tuple of (is_valid, errors)
        """
        try:
            content = filepath.read_text(encoding='utf-8')
            content_type = "yaml" if filepath.suffix in ('.yaml', '.yml') else "json"
            return self.validate(content, content_type)
        except Exception as e:
            return False, [ValidationError("file", f"Failed to read file: {e}")]

    def get_validation_summary(self) -> Dict:
        """Get summary of validation rules.

        Returns:
            Dict with validation info
        """
        return {
            "required_fields": self.REQUIRED_FIELDS,
            "recommended_fields": self.RECOMMENDED_FIELDS,
            "trait_count_range": self.VALID_TRAIT_COUNT,
            "value_count_range": self.VALID_VALUE_COUNT,
            "supported_formats": ["yaml", "json"]
        }