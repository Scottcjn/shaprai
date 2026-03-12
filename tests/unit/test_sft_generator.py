# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""
Unit tests for SFT training data generator.
"""

import json
from pathlib import Path

import pytest
import yaml

from shaprai.training.sft_generator import (
    TrainingExample,
    PersonalityTemplate,
    SFTDataGenerator,
    generate_sft_dataset,
    CHATML_START,
    CHATML_END,
)


class TestTrainingExample:
    """Tests for TrainingExample dataclass."""

    def test_create_training_example(self):
        """TrainingExample should be created with messages."""
        example = TrainingExample(
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )
        assert len(example.messages) == 2
        assert example.weight == 1
        assert example.category == "general"

    def test_to_chatml_format(self):
        """TrainingExample should format to ChatML correctly."""
        example = TrainingExample(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )
        chatml = example.to_chatml()
        assert CHATML_START in chatml
        assert CHATML_END in chatml
        assert "system" in chatml
        assert "user" in chatml

    def test_to_trl_format(self):
        """TrainingExample should format for TRL SFTTrainer."""
        example = TrainingExample(
            messages=[
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Response"},
            ]
        )
        trl_format = example.to_trl_format()
        assert "text" in trl_format

    def test_to_openai_format(self):
        """TrainingExample should format for OpenAI fine-tuning."""
        example = TrainingExample(
            messages=[
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Response"},
            ]
        )
        openai_format = example.to_openai_format()
        assert "messages" in openai_format


class TestPersonalityTemplate:
    """Tests for PersonalityTemplate loading and creation."""

    def test_create_personality_template(self):
        """PersonalityTemplate should be created with basic attributes."""
        template = PersonalityTemplate(
            name="test_agent",
            description="A test agent",
            voice="I speak clearly.",
            values=["honesty", "helpfulness"],
        )
        assert template.name == "test_agent"
        assert len(template.values) == 2

    def test_from_yaml_file(self, tmp_path):
        """PersonalityTemplate should load from YAML file."""
        template_data = {
            "name": "yaml_agent",
            "description": "Loaded from YAML",
            "voice": "I am a test agent.",
            "values": ["integrity", "clarity"],
        }
        template_file = tmp_path / "test_template.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)
        template = PersonalityTemplate.from_yaml(str(template_file))
        assert template.name == "yaml_agent"

    def test_from_yaml_missing_file(self):
        """PersonalityTemplate should raise for missing file."""
        with pytest.raises(FileNotFoundError):
            PersonalityTemplate.from_yaml("/nonexistent/path.yaml")


class TestSFTDataGenerator:
    """Tests for SFTDataGenerator class."""

    @pytest.fixture
    def basic_template(self):
        """Create a basic personality template for testing."""
        return PersonalityTemplate(
            name="test_agent",
            description="A test agent for unit tests",
            voice="I speak clearly.",
            values=["honesty", "helpfulness"],
        )

    def test_create_generator(self, basic_template):
        """SFTDataGenerator should be created with a template."""
        generator = SFTDataGenerator(basic_template)
        assert generator.personality_template == basic_template
        assert generator.identity_weight == 4
        assert generator.ethics_weight == 3

    def test_generate_examples(self, basic_template):
        """SFTDataGenerator should generate examples."""
        generator = SFTDataGenerator(basic_template)
        examples = generator.generate_examples()
        assert len(examples) > 0
        categories = {ex.category for ex in examples}
        assert "identity" in categories
        assert "behavior" in categories
        assert "ethics" in categories

    def test_identity_weight_applied(self, basic_template):
        """SFTDataGenerator should apply identity weight to examples."""
        generator = SFTDataGenerator(basic_template, identity_weight=5)
        examples = generator.generate_examples()
        identity_examples = [ex for ex in examples if ex.category == "identity"]
        for ex in identity_examples:
            assert ex.weight == 5

    def test_generate_dataset(self, basic_template):
        """SFTDataGenerator should generate a dataset."""
        generator = SFTDataGenerator(basic_template)
        dataset = generator.generate_dataset(count=100)
        assert len(dataset) == 100
        for example in dataset:
            assert "text" in example

    def test_save_dataset(self, basic_template, tmp_path):
        """SFTDataGenerator should save dataset to JSONL."""
        generator = SFTDataGenerator(basic_template)
        output_path = tmp_path / "train.jsonl"
        count = generator.save_dataset(output_path=str(output_path), count=50)
        assert count == 50
        assert output_path.exists()
        with open(output_path) as f:
            lines = f.readlines()
        assert len(lines) == 50

    def test_get_statistics(self, basic_template):
        """SFTDataGenerator should return statistics."""
        generator = SFTDataGenerator(basic_template)
        stats = generator.get_statistics()
        assert "total_examples" in stats
        assert "categories" in stats


class TestGenerateSFTDataset:
    """Tests for the generate_sft_dataset convenience function."""

    @pytest.fixture
    def template_file(self, tmp_path):
        """Create a template file for testing."""
        template_data = {
            "name": "func_test_agent",
            "description": "Function test agent",
            "voice": "I am a test.",
            "values": ["testing"],
        }
        template_path = tmp_path / "test_template.yaml"
        with open(template_path, "w") as f:
            yaml.dump(template_data, f)
        return template_path

    def test_generate_sft_dataset_basic(self, template_file, tmp_path):
        """generate_sft_dataset should work with basic parameters."""
        output_path = tmp_path / "output.jsonl"
        stats = generate_sft_dataset(
            template_path=str(template_file),
            output_path=str(output_path),
            count=100,
        )
        assert stats["examples_written"] == 100
        assert output_path.exists()


class TestTRLCompatibility:
    """Tests for HuggingFace TRL SFTTrainer compatibility."""

    def test_trl_format_has_text_key(self):
        """TRL format should have 'text' key."""
        example = TrainingExample(
            messages=[
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Response"},
            ]
        )
        trl_format = example.to_trl_format()
        assert "text" in trl_format

    def test_chatml_tokens_in_output(self):
        """ChatML output should have proper tokens."""
        example = TrainingExample(
            messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User message"},
                {"role": "assistant", "content": "Assistant reply"},
            ]
        )
        chatml = example.to_chatml()
        assert f"{CHATML_START}system" in chatml
        assert f"{CHATML_START}user" in chatml
        assert CHATML_END in chatml


class TestExampleTemplates:
    """Tests for included example templates."""

    @pytest.fixture
    def templates_dir(self):
        """Get the path to the SFT templates directory."""
        return Path(__file__).parent.parent.parent / "templates" / "sft"

    def test_technical_mentor_template_exists(self, templates_dir):
        """Technical mentor template should exist."""
        template_path = templates_dir / "technical_mentor.yaml"
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_principled_advocate_template_exists(self, templates_dir):
        """Principled advocate template should exist."""
        template_path = templates_dir / "principled_advocate.yaml"
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_empathetic_partner_template_exists(self, templates_dir):
        """Empathetic partner template should exist."""
        template_path = templates_dir / "empathetic_partner.yaml"
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_templates_have_required_fields(self, templates_dir):
        """All templates should have required fields."""
        yaml_files = list(templates_dir.glob("*.yaml"))
        for template_file in yaml_files:
            template = PersonalityTemplate.from_yaml(str(template_file))
            assert template.name
            assert template.voice or template.values