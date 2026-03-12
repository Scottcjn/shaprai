"""Unit tests for SFT Generator."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from shaprai.training.sft_generator import (
    SFTGenerator, SFTExample, EXAMPLE_TEMPLATES, save_example_templates
)


class TestSFTGenerator:
    """Tests for SFT training data generation."""

    @pytest.fixture
    def personality(self):
        """Sample personality template."""
        return {
            "name": "TestBot",
            "traits": ["helpful", "friendly"],
            "values": ["honesty", "kindness"]
        }

    @pytest.fixture
    def generator(self, personality):
        """Create an SFT generator."""
        return SFTGenerator(personality_template=personality)

    def test_initialization(self):
        """Test generator initialization."""
        gen = SFTGenerator()
        assert len(gen) == 0
        assert gen.personality == {}

    def test_initialization_with_personality(self, personality):
        """Test initialization with personality."""
        gen = SFTGenerator(personality_template=personality)
        assert gen.personality == personality

    def test_generate(self, generator):
        """Test generating training examples."""
        examples = generator.generate(count=10, core_identity_ratio=0.3)

        assert len(examples) == 10

        # Check mix of core and general
        core_count = sum(1 for ex in examples if ex.is_core_identity)
        assert core_count >= 2  # At least some core examples

    def test_core_identity_weight(self, generator):
        """Test that core identity examples have higher weight."""
        examples = generator.generate(count=20, core_identity_ratio=0.5)

        core_weights = [ex.weight for ex in examples if ex.is_core_identity]
        general_weights = [ex.weight for ex in examples if not ex.is_core_identity]

        if core_weights and general_weights:
            assert min(core_weights) > max(general_weights)

    def test_chatml_format(self, generator):
        """Test ChatML message format."""
        examples = generator.generate(count=1)
        ex = examples[0]

        assert len(ex.messages) == 3  # system, user, assistant
        assert ex.messages[0]["role"] == "system"
        assert ex.messages[1]["role"] == "user"
        assert ex.messages[2]["role"] == "assistant"

    def test_save_jsonl(self, generator):
        """Test saving to JSONL."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            generator.generate(count=5, output_file=temp_path)

            assert temp_path.exists()

            with open(temp_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 5

                for line in lines:
                    record = json.loads(line)
                    assert "messages" in record
                    assert "weight" in record
        finally:
            temp_path.unlink(missing_ok=True)

    def test_to_chatml_string(self, generator):
        """Test conversion to ChatML string."""
        examples = generator.generate(count=1)
        chatml = generator.to_chatml(examples[0])

        assert "<|im_start|>" in chatml
        assert "<|im_end|>" in chatml
        assert "system" in chatml
        assert "user" in chatml
        assert "assistant" in chatml

    def test_to_trl_format(self, generator):
        """Test conversion to TRL format."""
        generator.generate(count=3)
        trl_data = generator.to_trl_format()

        assert len(trl_data) == 3
        for record in trl_data:
            assert "messages" in record
            assert "weight" in record

    def test_weight_distribution(self, generator):
        """Test weight distribution stats."""
        generator.generate(count=10, core_identity_ratio=0.3)
        stats = generator.get_weight_distribution()

        assert stats["count"] == 10
        assert stats["avg_weight"] > 0
        assert stats["max_weight"] >= stats["min_weight"]
        assert stats["core_identity_count"] >= 3

    def test_system_prompt_generation(self, generator):
        """Test system prompt generation."""
        system = generator._get_system_prompt()

        assert "TestBot" in system
        assert "helpful" in system
        assert "friendly" in system
        assert "honesty" in system

    def test_from_yaml(self):
        """Test loading from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "YamlBot",
                "traits": ["smart"]
            }, f)
            temp_path = Path(f.name)

        try:
            gen = SFTGenerator.from_yaml(temp_path)
            assert gen.personality["name"] == "YamlBot"
            assert gen.personality["traits"] == ["smart"]
        finally:
            temp_path.unlink(missing_ok=True)

    def test_iteration(self, generator):
        """Test iteration over examples."""
        generator.generate(count=3)

        count = 0
        for ex in generator:
            assert isinstance(ex, SFTExample)
            count += 1

        assert count == 3


class TestSFTExample:
    """Tests for SFTExample dataclass."""

    def test_example_creation(self):
        """Test creating SFT examples."""
        ex = SFTExample(
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"}
            ],
            weight=2.0,
            is_core_identity=True
        )

        assert len(ex.messages) == 2
        assert ex.weight == 2.0
        assert ex.is_core_identity


class TestExampleTemplates:
    """Tests for example personality templates."""

    def test_templates_exist(self):
        """Test that example templates exist."""
        assert len(EXAMPLE_TEMPLATES) >= 3

        for name, template in EXAMPLE_TEMPLATES.items():
            assert "name" in template
            assert "traits" in template
            assert "values" in template

    def test_save_templates(self):
        """Test saving example templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            save_example_templates(output_dir)

            # Check files were created
            for name in EXAMPLE_TEMPLATES.keys():
                filepath = output_dir / f"{name}.yaml"
                assert filepath.exists()

                # Verify content
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                    assert data["name"] == EXAMPLE_TEMPLATES[name]["name"]

    def test_generator_with_templates(self):
        """Test using templates with generator."""
        for template in EXAMPLE_TEMPLATES.values():
            gen = SFTGenerator(personality_template=template)
            examples = gen.generate(count=5)

            assert len(examples) == 5
            # Verify personality is used
            system = gen._get_system_prompt()
            assert template["name"] in system


class TestIdentityResponses:
    """Tests for identity response generation."""

    def test_identity_response_contains_name(self):
        """Test that identity responses include agent name."""
        gen = SFTGenerator(personality_template={
            "name": "MyBot",
            "traits": ["helpful"],
            "values": ["honesty"]
        })

        response = gen._generate_identity_response("MyBot", ["helpful"], ["honesty"])
        assert "MyBot" in response

    def test_identity_response_contains_traits(self):
        """Test that identity responses include traits."""
        gen = SFTGenerator(personality_template={
            "name": "Bot",
            "traits": ["witty", "clever"],
            "values": ["truth"]
        })

        response = gen._generate_identity_response("Bot", ["witty", "clever"], ["truth"])
        assert "witty" in response.lower() or "clever" in response.lower()


class TestGeneralResponses:
    """Tests for general response generation."""

    def test_general_response_structure(self):
        """Test general response structure."""
        gen = SFTGenerator(personality_template={
            "name": "Helper",
            "traits": ["friendly"]
        })

        response = gen._generate_general_response(
            "Explain Python",
            "Helper",
            ["friendly"]
        )

        assert len(response) > 0
        # Should contain code block for Python question
        assert "```" in response or "Here" in response or "Great" in response