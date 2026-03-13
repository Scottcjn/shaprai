# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for the template engine module."""

import pytest
import yaml
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from shaprai.core.template_engine import (
    AgentTemplate,
    load_template,
    save_template,
    fork_template,
    list_templates,
)


class TestAgentTemplate:
    """Tests for AgentTemplate dataclass."""

    def test_minimal_template(self):
        """Test creating a minimal template with only required fields."""
        template = AgentTemplate(name="test-template")
        
        assert template.name == "test-template"
        assert template.model == {}
        assert template.personality == {}
        assert template.capabilities == []
        assert template.platforms == []
        assert template.ethics_profile == "sophiacore_default"
        assert template.driftlock == {"enabled": True, "check_interval": 25}
        assert template.description == ""
        assert template.version == "1.0"
        assert template.rtc_config == {}

    def test_full_template(self):
        """Test creating a template with all fields populated."""
        template = AgentTemplate(
            name="full-template",
            model={"base": "llama-3.1-8b", "quantization": "q4_k_m", "min_vram_gb": 8},
            personality={"style": "professional", "tone": "friendly", "humor": "low"},
            capabilities=["code_review", "bounty_discovery"],
            platforms=["github", "bottube"],
            ethics_profile="strict",
            driftlock={"enabled": True, "check_interval": 50, "anchor_phrases": ["test"]},
            description="A comprehensive test template",
            version="2.0",
            rtc_config={"bounty_percentage": 0.1, "fee_percentage": 0.05},
        )
        
        assert template.name == "full-template"
        assert template.model["base"] == "llama-3.1-8b"
        assert template.personality["style"] == "professional"
        assert template.capabilities == ["code_review", "bounty_discovery"]
        assert template.platforms == ["github", "bottube"]
        assert template.ethics_profile == "strict"
        assert template.driftlock["check_interval"] == 50
        assert template.description == "A comprehensive test template"
        assert template.version == "2.0"
        assert template.rtc_config["bounty_percentage"] == 0.1


class TestLoadTemplate:
    """Tests for load_template function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_valid_template(self):
        """Test loading a valid template file."""
        template_data = {
            "name": "test-template",
            "model": {"base": "llama-3.1-8b"},
            "capabilities": ["code_review"],
            "platforms": ["github"],
        }
        
        template_path = self.temp_dir / "test.yaml"
        with open(template_path, "w") as f:
            yaml.dump(template_data, f)
        
        template = load_template(str(template_path))
        
        assert template.name == "test-template"
        assert template.model["base"] == "llama-3.1-8b"
        assert template.capabilities == ["code_review"]
        assert template.platforms == ["github"]

    def test_load_template_with_defaults(self):
        """Test that missing fields use default values."""
        template_data = {"name": "minimal"}
        
        template_path = self.temp_dir / "minimal.yaml"
        with open(template_path, "w") as f:
            yaml.dump(template_data, f)
        
        template = load_template(str(template_path))
        
        assert template.name == "minimal"
        assert template.ethics_profile == "sophiacore_default"
        assert template.version == "1.0"
        assert template.driftlock == {"enabled": True, "check_interval": 25}

    def test_load_nonexistent_template(self):
        """Test that loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Template not found"):
            load_template(str(self.temp_dir / "nonexistent.yaml"))

    def test_load_invalid_yaml(self):
        """Test that loading invalid YAML raises yaml.YAMLError."""
        template_path = self.temp_dir / "invalid.yaml"
        with open(template_path, "w") as f:
            f.write("invalid: yaml: content: [")
        
        with pytest.raises(yaml.YAMLError):
            load_template(str(template_path))

    def test_load_template_uses_filename_as_name(self):
        """Test that name defaults to filename stem if not specified."""
        template_data = {"model": {"base": "test"}}
        
        template_path = self.temp_dir / "custom-name.yaml"
        with open(template_path, "w") as f:
            yaml.dump(template_data, f)
        
        template = load_template(str(template_path))
        
        assert template.name == "custom-name"


class TestSaveTemplate:
    """Tests for save_template function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_template(self):
        """Test saving a template to YAML."""
        template = AgentTemplate(
            name="save-test",
            model={"base": "test-model"},
            capabilities=["test"],
        )
        
        output_path = self.temp_dir / "output.yaml"
        save_template(template, str(output_path))
        
        assert output_path.exists()
        
        with open(output_path, "r") as f:
            data = yaml.safe_load(f)
        
        assert data["name"] == "save-test"
        assert data["model"]["base"] == "test-model"
        assert data["capabilities"] == ["test"]

    def test_save_template_creates_directories(self):
        """Test that save_template creates parent directories."""
        template = AgentTemplate(name="nested-test")
        
        nested_path = self.temp_dir / "nested" / "dir" / "template.yaml"
        save_template(template, str(nested_path))
        
        assert nested_path.exists()


class TestForkTemplate:
    """Tests for fork_template function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fork_basic(self):
        """Test basic template forking."""
        source = AgentTemplate(
            name="source",
            model={"base": "original"},
            capabilities=["original"],
        )
        
        source_path = self.temp_dir / "source.yaml"
        save_template(source, str(source_path))
        
        forked = fork_template(str(source_path), "forked")
        
        assert forked.name == "forked"
        assert forked.model["base"] == "original"
        assert forked.capabilities == ["original"]

    def test_fork_with_overrides(self):
        """Test forking with field overrides."""
        source = AgentTemplate(
            name="source",
            model={"base": "original", "quantization": "q4"},
            capabilities=["original"],
        )
        
        source_path = self.temp_dir / "source.yaml"
        save_template(source, str(source_path))
        
        overrides = {
            "model": {"base": "modified"},
            "capabilities": ["new_capability"],
        }
        
        forked = fork_template(str(source_path), "forked", overrides)
        
        assert forked.name == "forked"
        assert forked.model["base"] == "modified"
        assert forked.model["quantization"] == "q4"  # Preserved
        assert forked.capabilities == ["new_capability"]

    def test_fork_with_nested_dict_overrides(self):
        """Test that nested dicts are merged correctly."""
        source = AgentTemplate(
            name="source",
            personality={"style": "professional", "tone": "formal"},
        )
        
        source_path = self.temp_dir / "source.yaml"
        save_template(source, str(source_path))
        
        overrides = {
            "personality": {"humor": "high"},
        }
        
        forked = fork_template(str(source_path), "forked", overrides)
        
        assert forked.personality["style"] == "professional"  # Preserved
        assert forked.personality["tone"] == "formal"  # Preserved
        assert forked.personality["humor"] == "high"  # Added


class TestListTemplates:
    """Tests for list_templates function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_templates_empty(self):
        """Test listing templates in an empty directory."""
        templates = list_templates(str(self.temp_dir))
        assert templates == []

    def test_list_templates_single(self):
        """Test listing a single template."""
        template = AgentTemplate(name="single")
        template_path = self.temp_dir / "single.yaml"
        save_template(template, str(template_path))
        
        templates = list_templates(str(self.temp_dir))
        
        assert len(templates) == 1
        assert templates[0].name == "single"

    def test_list_templates_multiple(self):
        """Test listing multiple templates."""
        for name in ["alpha", "beta", "gamma"]:
            template = AgentTemplate(name=name)
            save_template(template, str(self.temp_dir / f"{name}.yaml"))
        
        templates = list_templates(str(self.temp_dir))
        
        assert len(templates) == 3
        names = [t.name for t in templates]
        assert names == ["alpha", "beta", "gamma"]  # Sorted

    def test_list_templates_skips_malformed(self):
        """Test that malformed templates are skipped."""
        valid = AgentTemplate(name="valid")
        save_template(valid, str(self.temp_dir / "valid.yaml"))
        
        invalid_path = self.temp_dir / "invalid.yaml"
        with open(invalid_path, "w") as f:
            f.write("invalid: yaml: [")
        
        templates = list_templates(str(self.temp_dir))
        
        assert len(templates) == 1
        assert templates[0].name == "valid"

    def test_list_templates_nonexistent_directory(self):
        """Test listing templates in a nonexistent directory."""
        templates = list_templates(str(self.temp_dir / "nonexistent"))
        assert templates == []
