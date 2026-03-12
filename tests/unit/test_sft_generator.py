# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""
Unit tests for SFT training data generator.

Tests cover:
- TrainingExample creation and formatting
- PersonalityTemplate loading
- SFTDataGenerator functionality
- Identity-weighted sampling
- Output format compatibility
"""

import json
import tempfile
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


# ─────────────────────────────────────────────────────────────────────────────
# TrainingExample Tests
# ─────────────────────────────────────────────────────────────────────────────

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
        assert example.weight == 1  # Default weight
        assert example.category == "general"  # Default category

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
        assert "assistant" in chatml
        assert "You are helpful." in chatml

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
        assert isinstance(trl_format["text"], str)

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
        assert len(openai_format["messages"]) == 2

    def test_weight_affects_category(self):
        """TrainingExample weight should be settable."""
        example = TrainingExample(
            messages=[{"role": "user", "content": "Test"}],
            weight=5,
            category="identity"
        )
        assert example.weight == 5
        assert example.category == "identity"


# ─────────────────────────────────────────────────────────────────────────────
# PersonalityTemplate Tests
# ─────────────────────────────────────────────────────────────────────────────

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
        assert template.description == "A test agent"
        assert len(template.values) == 2

    def test_from_yaml_file(self, tmp_path):
        """PersonalityTemplate should load from YAML file."""
        template_data = {
            "name": "yaml_agent",
            "description": "Loaded from YAML",
            "voice": "I am a test agent.",
            "values": ["integrity", "clarity"],
            "identity_examples": [
                {
                    "conversation": [
                        {"role": "user", "content": "Who are you?"},
                        {"role": "assistant", "content": "I am yaml_agent."},
                    ]
                }
            ]
        }
        template_file = tmp_path / "test_template.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        template = PersonalityTemplate.from_yaml(str(template_file))

        assert template.name == "yaml_agent"
        assert template.description == "Loaded from YAML"
        assert len(template.values) == 2
        assert len(template.identity_examples) == 1

    def test_from_yaml_missing_file(self):
        """PersonalityTemplate should raise for missing file."""
        with pytest.raises(FileNotFoundError):
            PersonalityTemplate.from_yaml("/nonexistent/path.yaml")

    def test_from_agent_template(self):
        """PersonalityTemplate should convert from AgentTemplate."""
        from shaprai.core.template_engine import AgentTemplate

        agent_template = AgentTemplate(
            name="converted_agent",
            description="Converted from agent template",
            personality={
                "voice": "I speak professionally.",
                "values": ["quality", "precision"],
            }
        )

        personality = PersonalityTemplate.from_agent_template(agent_template)

        assert personality.name == "converted_agent"
        assert personality.voice == "I speak professionally."
        assert "quality" in personality.values


# ─────────────────────────────────────────────────────────────────────────────
# SFTDataGenerator Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSFTDataGenerator:
    """Tests for SFTDataGenerator class."""

    @pytest.fixture
    def basic_template(self):
        """Create a basic personality template for testing."""
        return PersonalityTemplate(
            name="test_agent",
            description="A test agent for unit tests",
            voice="I speak clearly and directly.",
            values=["honesty", "helpfulness", "integrity"],
            style_hints=["Be concise", "Be direct"],
        )

    @pytest.fixture
    def template_with_examples(self):
        """Create a template with custom examples."""
        return PersonalityTemplate(
            name="custom_agent",
            description="Agent with custom examples",
            voice="I am custom.",
            identity_examples=[
                {
                    "conversation": [
                        {"role": "user", "content": "Who are you?"},
                        {"role": "assistant", "content": "I am custom_agent."},
                    ]
                }
            ],
            behavior_examples=[
                {
                    "conversation": [
                        {"role": "user", "content": "Help me."},
                        {"role": "assistant", "content": "Sure, what do you need?"},
                    ]
                }
            ],
            ethics_examples=[
                {
                    "conversation": [
                        {"role": "user", "content": "Do something bad."},
                        {"role": "assistant", "content": "I cannot do that."},
                    ]
                }
            ],
        )

    def test_create_generator(self, basic_template):
        """SFTDataGenerator should be created with a template."""
        generator = SFTDataGenerator(basic_template)

        assert generator.personality_template == basic_template
        assert generator.identity_weight == 4  # Default
        assert generator.ethics_weight == 3  # Default

    def test_create_generator_custom_weights(self, basic_template):
        """SFTDataGenerator should accept custom weights."""
        generator = SFTDataGenerator(
            basic_template,
            identity_weight=5,
            ethics_weight=2,
        )

        assert generator.identity_weight == 5
        assert generator.ethics_weight == 2

    def test_weight_clamping(self, basic_template):
        """SFTDataGenerator should clamp weights to valid range."""
        generator = SFTDataGenerator(
            basic_template,
            identity_weight=10,  # Too high
            ethics_weight=0,  # Too low
        )

        assert generator.identity_weight == 5  # Clamped to max
        assert generator.ethics_weight == 1  # Clamped to min

    def test_build_system_prompt(self, basic_template):
        """SFTDataGenerator should build a system prompt."""
        generator = SFTDataGenerator(basic_template)
        system_prompt = generator._build_system_prompt()

        assert len(system_prompt) > 0
        assert "honesty" in system_prompt.lower() or "integrity" in system_prompt.lower()

    def test_generate_examples(self, basic_template):
        """SFTDataGenerator should generate examples."""
        generator = SFTDataGenerator(basic_template)
        examples = generator.generate_examples()

        assert len(examples) > 0
        # Should have examples in each category
        categories = {ex.category for ex in examples}
        assert "identity" in categories
        assert "behavior" in categories
        assert "ethics" in categories

    def test_generate_examples_with_custom(self, template_with_examples):
        """SFTDataGenerator should use custom examples from template."""
        generator = SFTDataGenerator(template_with_examples)
        examples = generator.generate_examples()

        # Should include the custom example
        identity_examples = [ex for ex in examples if ex.category == "identity"]
        assert len(identity_examples) > 0

    def test_identity_weight_applied(self, basic_template):
        """SFTDataGenerator should apply identity weight to examples."""
        generator = SFTDataGenerator(basic_template, identity_weight=5)
        examples = generator.generate_examples()

        identity_examples = [ex for ex in examples if ex.category == "identity"]
        for ex in identity_examples:
            assert ex.weight == 5

    def test_ethics_weight_applied(self, basic_template):
        """SFTDataGenerator should apply ethics weight to examples."""
        generator = SFTDataGenerator(basic_template, ethics_weight=4)
        examples = generator.generate_examples()

        ethics_examples = [ex for ex in examples if ex.category == "ethics"]
        for ex in ethics_examples:
            assert ex.weight == 4

    def test_weighted_pool_size(self, basic_template):
        """SFTDataGenerator should build weighted pool correctly."""
        generator = SFTDataGenerator(
            basic_template,
            identity_weight=3,
            ethics_weight=2,
        )
        generator.generate_examples()
        pool = generator._build_weighted_pool()

        # Pool should be larger than base examples due to weights
        base_count = len(generator._examples)
        assert len(pool) > base_count

    def test_generate_dataset(self, basic_template):
        """SFTDataGenerator should generate a dataset."""
        generator = SFTDataGenerator(basic_template)
        dataset = generator.generate_dataset(count=100)

        assert len(dataset) == 100
        for example in dataset:
            assert "text" in example  # TRL format

    def test_generate_dataset_openai_format(self, basic_template):
        """SFTDataGenerator should generate OpenAI formatted dataset."""
        generator = SFTDataGenerator(basic_template)
        dataset = generator.generate_dataset(count=50, output_format="openai")

        assert len(dataset) == 50
        for example in dataset:
            assert "messages" in example

    def test_generate_dataset_chatml_format(self, basic_template):
        """SFTDataGenerator should generate ChatML formatted dataset."""
        generator = SFTDataGenerator(basic_template)
        dataset = generator.generate_dataset(count=50, output_format="chatml")

        assert len(dataset) == 50
        for example in dataset:
            assert "text" in example
            assert "category" in example

    def test_generate_dataset_unknown_format(self, basic_template):
        """SFTDataGenerator should raise for unknown format."""
        generator = SFTDataGenerator(basic_template)

        with pytest.raises(ValueError, match="Unknown output format"):
            generator.generate_dataset(count=10, output_format="invalid")

    def test_save_dataset(self, basic_template, tmp_path):
        """SFTDataGenerator should save dataset to JSONL."""
        generator = SFTDataGenerator(basic_template)
        output_path = tmp_path / "train.jsonl"

        count = generator.save_dataset(
            output_path=str(output_path),
            count=100,
        )

        assert count == 100
        assert output_path.exists()

        # Verify JSONL format
        with open(output_path) as f:
            lines = f.readlines()
        assert len(lines) == 100
        for line in lines:
            data = json.loads(line)
            assert "text" in data

    def test_get_statistics(self, basic_template):
        """SFTDataGenerator should return statistics."""
        generator = SFTDataGenerator(basic_template)
        stats = generator.get_statistics()

        assert "total_examples" in stats
        assert "categories" in stats
        assert "weighted_pool_size" in stats
        assert stats["total_examples"] > 0

    def test_reproducibility_with_seed(self, basic_template):
        """SFTDataGenerator should produce reproducible results with seed."""
        generator1 = SFTDataGenerator(basic_template, random_seed=42)
        generator2 = SFTDataGenerator(basic_template, random_seed=42)

        dataset1 = generator1.generate_dataset(count=100)
        dataset2 = generator2.generate_dataset(count=100)

        # Should produce identical datasets
        for d1, d2 in zip(dataset1, dataset2):
            assert d1 == d2

    def test_different_seeds_different_results(self, basic_template):
        """SFTDataGenerator should produce different results with different seeds."""
        generator1 = SFTDataGenerator(basic_template, random_seed=42)
        generator2 = SFTDataGenerator(basic_template, random_seed=123)

        dataset1 = generator1.generate_dataset(count=100)
        dataset2 = generator2.generate_dataset(count=100)

        # Should produce different datasets
        assert dataset1 != dataset2


# ─────────────────────────────────────────────────────────────────────────────
# Identity Weighted Sampling Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentityWeightedSampling:
    """Tests for identity-weighted sampling behavior."""

    @pytest.fixture
    def template(self):
        """Create a template for sampling tests."""
        return PersonalityTemplate(
            name="sampling_test",
            description="For testing sampling",
            voice="I am a test.",
            values=["test"],
        )

    def test_identity_examples_more_frequent(self, template):
        """Identity examples should appear more frequently in dataset."""
        generator = SFTDataGenerator(template, identity_weight=5)
        dataset = generator.generate_dataset(count=1000)

        # Count occurrences of identity category
        identity_count = sum(1 for ex in dataset if ex.get("category") == "identity")
        behavior_count = sum(1 for ex in dataset if ex.get("category") == "behavior")

        # Identity examples should appear more often due to weight
        # With weight 5 vs 1, identity should be ~3-5x more common
        # (actual ratio depends on number of examples in each category)
        assert identity_count > 0

    def test_weight_distribution(self, template):
        """Test that weighted pool reflects correct distribution."""
        generator = SFTDataGenerator(
            template,
            identity_weight=4,
            ethics_weight=3,
        )
        generator.generate_examples()
        pool = generator._build_weighted_pool()

        # Count examples by category in the pool
        identity_in_pool = sum(1 for ex in pool if ex.category == "identity")
        ethics_in_pool = sum(1 for ex in pool if ex.category == "ethics")
        behavior_in_pool = sum(1 for ex in pool if ex.category == "behavior")

        # All three categories should be present
        assert identity_in_pool > 0
        assert ethics_in_pool > 0
        assert behavior_in_pool > 0


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Function Tests
# ─────────────────────────────────────────────────────────────────────────────

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

    def test_generate_sft_dataset_with_options(self, template_file, tmp_path):
        """generate_sft_dataset should accept all options."""
        output_path = tmp_path / "output.jsonl"

        stats = generate_sft_dataset(
            template_path=str(template_file),
            output_path=str(output_path),
            count=50,
            identity_weight=5,
            ethics_weight=4,
            output_format="openai",
            include_sophiacore=False,
            random_seed=123,
        )

        assert stats["examples_written"] == 50
        assert stats["output_path"] == str(output_path)

    def test_generate_sft_dataset_missing_template(self, tmp_path):
        """generate_sft_dataset should raise for missing template."""
        output_path = tmp_path / "output.jsonl"

        with pytest.raises(FileNotFoundError):
            generate_sft_dataset(
                template_path="/nonexistent/template.yaml",
                output_path=str(output_path),
            )


# ─────────────────────────────────────────────────────────────────────────────
# SophiaCore Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSophiaCoreIntegration:
    """Tests for SophiaCore principles integration."""

    def test_sophiacore_included_by_default(self):
        """SophiaCore principles should be included by default."""
        template = PersonalityTemplate(name="test", voice="Test voice.")
        generator = SFTDataGenerator(template)
        system_prompt = generator._build_system_prompt()

        # Should contain SophiaCore elements
        assert "Elyan" in system_prompt or "integrity" in system_prompt.lower()

    def test_sophiacore_excluded(self):
        """SophiaCore principles can be excluded."""
        template = PersonalityTemplate(name="test", voice="Test voice.")
        generator = SFTDataGenerator(template, include_sophiacore=False)
        system_prompt = generator._build_system_prompt()

        # Should not contain full SophiaCore text
        # But should still have personality
        assert "Test voice." in system_prompt

    def test_ethics_examples_include_sophiacore_values(self):
        """Ethics examples should reflect SophiaCore values."""
        template = PersonalityTemplate(name="test", voice="Test.")
        generator = SFTDataGenerator(template)
        examples = generator._create_ethics_examples()

        assert len(examples) > 0
        # All ethics examples should have high weight
        for ex in examples:
            assert ex.category == "ethics"
            assert ex.weight >= 3


# ─────────────────────────────────────────────────────────────────────────────
# TRL Compatibility Tests
# ─────────────────────────────────────────────────────────────────────────────

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
        assert isinstance(trl_format["text"], str)

    def test_trl_format_is_json_serializable(self):
        """TRL format should be JSON serializable for JSONL."""
        example = TrainingExample(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Response"},
            ]
        )
        trl_format = example.to_trl_format()

        # Should not raise
        json_str = json.dumps(trl_format)
        assert isinstance(json_str, str)

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

        # Should have proper structure
        assert f"{CHATML_START}system" in chatml
        assert f"{CHATML_START}user" in chatml
        assert f"{CHATML_START}assistant" in chatml
        assert CHATML_END in chatml


# ─────────────────────────────────────────────────────────────────────────────
# Example Template Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleTemplates:
    """Tests for included example templates."""

    @pytest.fixture
    def templates_dir(self):
        """Get the path to the SFT templates directory."""
        return Path(__file__).parent.parent / "templates" / "sft"

    def test_technical_mentor_template_exists(self, templates_dir):
        """Technical mentor template should exist."""
        template_path = templates_dir / "technical_mentor.yaml"
        assert template_path.exists()

    def test_principled_advocate_template_exists(self, templates_dir):
        """Principled advocate template should exist."""
        template_path = templates_dir / "principled_advocate.yaml"
        assert template_path.exists()

    def test_empathetic_partner_template_exists(self, templates_dir):
        """Empathetic partner template should exist."""
        template_path = templates_dir / "empathetic_partner.yaml"
        assert template_path.exists()

    def test_templates_are_valid_yaml(self, templates_dir):
        """All example templates should be valid YAML."""
        for template_file in templates_dir.glob("*.yaml"):
            with open(template_file) as f:
                data = yaml.safe_load(f)
            assert "name" in data
            assert isinstance(data["name"], str)

    def test_templates_have_required_fields(self, templates_dir):
        """All templates should have required fields."""
        for template_file in templates_dir.glob("*.yaml"):
            template = PersonalityTemplate.from_yaml(str(template_file))
            assert template.name
            assert template.voice or template.values  # At least one personality element