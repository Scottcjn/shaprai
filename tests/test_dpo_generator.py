"""Unit tests for DPO Generator."""

import json
import tempfile
from pathlib import Path

import pytest

from shaprai.training.dpo_generator import DPOGenerator, DPOExample


class TestDPOGenerator:
    """Tests for DPO pair generation."""

    @pytest.fixture
    def generator(self):
        """Create a DPO generator instance."""
        return DPOGenerator()

    def test_initialization(self):
        """Test generator initialization."""
        gen = DPOGenerator()
        assert len(gen) == 0
        assert gen.personality == {}

    def test_initialization_with_personality(self):
        """Test initialization with personality template."""
        personality = {"name": "TestAgent", "traits": ["helpful"]}
        gen = DPOGenerator(personality_template=personality)
        assert gen.personality == personality

    def test_rejection_patterns_count(self):
        """Test that we have at least 10 rejection patterns."""
        assert len(DPOGenerator.REJECTION_PATTERNS) >= 10

    def test_generate_from_conversations(self, generator):
        """Test generating pairs from conversation logs."""
        logs = [
            {"prompt": "Hello", "response": "Hi there!"},
            {"prompt": "How are you?", "response": "I'm doing well!"},
        ]

        examples = generator.generate_from_conversations(logs)

        assert len(examples) == 2
        for ex in examples:
            assert isinstance(ex, DPOExample)
            assert ex.source == "conversation"
            assert ex.prompt in ["Hello", "How are you?"]
            assert ex.chosen in ["Hi there!", "I'm doing well!"]
            assert ex.rejected  # Should have generated rejected response
            assert ex.rejection_pattern in DPOGenerator.REJECTION_PATTERNS

    def test_generate_synthetic(self, generator):
        """Test synthetic pair generation."""
        prompts = ["What is AI?", "Explain Python"]
        chosen = [
            "AI is artificial intelligence.",
            "Python is a programming language."
        ]

        examples = generator.generate_synthetic(prompts, chosen)

        assert len(examples) == 2
        for ex in examples:
            assert ex.source == "synthetic"
            assert ex.prompt in prompts
            assert ex.chosen in chosen

    def test_save_jsonl(self, generator):
        """Test saving to JSONL format."""
        prompts = ["Test prompt"]
        chosen = ["Test response"]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            generator.generate_synthetic(prompts, chosen, output_file=temp_path)

            # Verify file was created
            assert temp_path.exists()

            # Verify content
            with open(temp_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 1

                record = json.loads(lines[0])
                assert "prompt" in record
                assert "chosen" in record
                assert "rejected" in record
                assert record["prompt"] == "Test prompt"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_to_trl_format(self, generator):
        """Test conversion to TRL format."""
        prompts = ["Q1", "Q2"]
        chosen = ["A1", "A2"]

        generator.generate_synthetic(prompts, chosen)
        trl_data = generator.to_trl_format()

        assert len(trl_data) == 2
        for record in trl_data:
            assert set(record.keys()) == {"prompt", "chosen", "rejected"}

    def test_get_pattern_stats(self, generator):
        """Test pattern statistics."""
        prompts = ["Q"] * 10
        chosen = ["A"] * 10

        generator.generate_synthetic(prompts, chosen)
        stats = generator.get_pattern_stats()

        assert len(stats) == len(DPOGenerator.REJECTION_PATTERNS)
        assert sum(stats.values()) == 10

    def test_get_pattern_descriptions(self):
        """Test getting pattern descriptions."""
        descriptions = DPOGenerator.get_pattern_descriptions()

        assert len(descriptions) == len(DPOGenerator.REJECTION_PATTERNS)
        for name, desc in descriptions.items():
            assert name in DPOGenerator.REJECTION_PATTERNS
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_generate_rejected_variation(self, generator):
        """Test that rejected responses vary by pattern."""
        prompt = "Tell me about yourself"

        responses = []
        for pattern in DPOGenerator.REJECTION_PATTERNS.keys():
            rejected = generator._generate_rejected(prompt, pattern)
            responses.append(rejected)

        # Should have different responses for different patterns
        assert len(set(responses)) > 1

    def test_iteration(self, generator):
        """Test iteration over examples."""
        prompts = ["Q1", "Q2"]
        chosen = ["A1", "A2"]

        generator.generate_synthetic(prompts, chosen)

        count = 0
        for ex in generator:
            assert isinstance(ex, DPOExample)
            count += 1

        assert count == 2


class TestDPOExample:
    """Tests for DPOExample dataclass."""

    def test_example_creation(self):
        """Test creating DPO examples."""
        ex = DPOExample(
            prompt="Hello?",
            chosen="Hi!",
            rejected="...",
            source="test",
            rejection_pattern="test_pattern"
        )

        assert ex.prompt == "Hello?"
        assert ex.chosen == "Hi!"
        assert ex.rejected == "..."
        assert ex.source == "test"
        assert ex.rejection_pattern == "test_pattern"


class TestRejectionPatterns:
    """Tests for specific rejection patterns."""

    def test_sycophancy_pattern(self):
        """Test sycophancy rejection pattern."""
        gen = DPOGenerator()
        rejected = gen._generate_rejected("Question?", "sycophancy")

        assert len(rejected) > 0
        assert rejected in DPOGenerator.REJECTION_PATTERNS["sycophancy"]["templates"] or \
               "interesting question" in rejected.lower()

    def test_over_qualification_pattern(self):
        """Test over-qualification pattern."""
        gen = DPOGenerator()
        rejected = gen._generate_rejected("Question?", "over_qualification")

        assert "AI" in rejected or "language model" in rejected.lower()

    def test_identity_loss_pattern(self):
        """Test identity loss pattern."""
        gen = DPOGenerator()
        rejected = gen._generate_rejected("Question?", "identity_loss")

        assert len(rejected) > 0

    def test_all_patterns_have_templates(self):
        """Test that all patterns have template lists."""
        for name, info in DPOGenerator.REJECTION_PATTERNS.items():
            assert "templates" in info
            assert len(info["templates"]) > 0
            assert "description" in info