"""SFT Training Data Generator for Agent Fine-tuning.

Generates supervised fine-tuning (SFT) training data in ChatML format
with identity-weighted examples for personality-driven agents.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Iterator
import yaml

logger = logging.getLogger("shaprai.training.sft")


@dataclass
class SFTExample:
    """A single SFT training example in ChatML format."""
    messages: List[Dict[str, str]]  # ChatML message list
    weight: float  # Training weight (higher = more important)
    is_core_identity: bool  # Whether this defines core personality


class SFTGenerator:
    """Generate SFT training data for agent personality fine-tuning.

    Creates ChatML-formatted training examples with identity-weighted
    sampling to ensure core personality traits are learned strongly.
    """

    # ChatML special tokens
    IM_START = "<|im_start|>"
    IM_END = "<|im_end|>"

    def __init__(self, personality_template: Optional[Dict] = None):
        """Initialize SFT generator.

        Args:
            personality_template: Agent personality configuration
        """
        self.personality = personality_template or {}
        self._examples: List[SFTExample] = []

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "SFTGenerator":
        """Load personality from YAML template.

        Args:
            yaml_path: Path to personality YAML file

        Returns:
            SFTGenerator instance
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            personality = yaml.safe_load(f)
        return cls(personality_template=personality)

    def generate(
        self,
        count: int = 1000,
        core_identity_ratio: float = 0.3,
        output_file: Optional[Path] = None
    ) -> List[SFTExample]:
        """Generate SFT training examples.

        Args:
            count: Total number of examples to generate
            core_identity_ratio: Fraction that are core identity examples
            output_file: Optional path to save JSONL output

        Returns:
            List of SFTExample objects
        """
        examples = []
        num_core = int(count * core_identity_ratio)
        num_general = count - num_core

        # Generate core identity examples (higher weight)
        for _ in range(num_core):
            ex = self._generate_core_identity_example()
            examples.append(ex)

        # Generate general capability examples
        for _ in range(num_general):
            ex = self._generate_general_example()
            examples.append(ex)

        # Shuffle to mix core and general examples
        random.shuffle(examples)

        if output_file:
            self._save_jsonl(examples, output_file)

        self._examples.extend(examples)
        logger.info(f"Generated {len(examples)} SFT examples "
                   f"({num_core} core, {num_general} general)")
        return examples

    def _generate_core_identity_example(self) -> SFTExample:
        """Generate a core identity-defining example.

        These examples have higher weight and define who the agent is.
        """
        name = self.personality.get("name", "Assistant")
        traits = self.personality.get("traits", ["helpful", "friendly"])
        values = self.personality.get("values", ["honesty", "kindness"])

        # Core identity prompts
        identity_prompts = [
            f"Who are you?",
            f"Describe yourself.",
            f"What is your name?",
            f"What are your core values?",
            f"How do you approach helping users?",
            f"What makes you unique?",
            f"Tell me about your personality.",
            f"What principles guide your responses?",
        ]

        prompt = random.choice(identity_prompts)

        # Generate identity-coherent response
        response = self._generate_identity_response(name, traits, values)

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]

        return SFTExample(
            messages=messages,
            weight=random.uniform(3.0, 5.0),  # Higher weight
            is_core_identity=True
        )

    def _generate_general_example(self) -> SFTExample:
        """Generate a general capability example."""
        name = self.personality.get("name", "Assistant")
        traits = self.personality.get("traits", ["helpful"])

        # General task prompts
        general_prompts = [
            "Explain how photosynthesis works.",
            "Write a Python function to sort a list.",
            "What are the benefits of exercise?",
            "Help me brainstorm ideas for a project.",
            "Summarize the key points of machine learning.",
            "How do I make a good first impression?",
            "What should I consider when buying a laptop?",
            "Give me tips for time management.",
        ]

        prompt = random.choice(general_prompts)

        # Generate response with personality
        response = self._generate_general_response(prompt, name, traits)

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]

        return SFTExample(
            messages=messages,
            weight=1.0,  # Standard weight
            is_core_identity=False
        )

    def _generate_identity_response(
        self,
        name: str,
        traits: List[str],
        values: List[str]
    ) -> str:
        """Generate an identity-defining response."""
        templates = [
            f"I am {name}, an AI assistant who is {', '.join(traits[:2])}. "
            f"My core values include {', '.join(values[:2])}. "
            f"I strive to be helpful while staying true to these principles.",

            f"Hello! I'm {name}. I pride myself on being {traits[0] if traits else 'helpful'}. "
            f"I believe in {values[0] if values else 'honesty'} above all, "
            f"and I aim to bring {traits[1] if len(traits) > 1 else 'clarity'} to every interaction.",

            f"I'm {name}, designed to be {', '.join(traits)}. "
            f"What drives me is a commitment to {', '.join(values[:2])}. "
            f"I approach every conversation with these values in mind.",
        ]

        return random.choice(templates)

    def _generate_general_response(
        self,
        prompt: str,
        name: str,
        traits: List[str]
    ) -> str:
        """Generate a general response with personality."""
        # Add personality touches to general responses
        openings = [
            f"I'd be happy to help with that! ",
            f"Great question! ",
            f"As {name}, I'm glad to assist. ",
            "",
        ]

        opening = random.choice(openings)

        # Generate substantive response based on prompt type
        if "Python" in prompt or "function" in prompt:
            content = ("Here's a simple approach:\n\n"
                      "```python\n"
                      "def example():\n"
                      "    pass  # Your implementation here\n"
                      "```\n\n"
                      "This provides a foundation you can build upon.")
        elif "explain" in prompt.lower():
            content = ("This is a fascinating topic! At its core, it involves "
                      "several key principles working together. The main concepts "
                      "include cause and effect, interconnected systems, and "
                      "emergent properties that arise from simple rules.")
        else:
            content = ("Here are some thoughts on this:\n\n"
                      "1. Consider your goals and priorities\n"
                      "2. Evaluate the available options\n"
                      "3. Take action based on your analysis\n\n"
                      "I hope this helps you move forward!")

        return opening + content

    def _get_system_prompt(self) -> str:
        """Generate system prompt from personality."""
        name = self.personality.get("name", "Assistant")
        traits = self.personality.get("traits", ["helpful"])
        values = self.personality.get("values", [])

        system = f"You are {name}, an AI assistant"
        if traits:
            system += f" who is {', '.join(traits)}"
        if values:
            system += f". Your core values are: {', '.join(values)}"
        system += "."

        return system

    def _save_jsonl(self, examples: List[SFTExample], filepath: Path):
        """Save examples to JSONL file.

        Args:
            examples: List of SFTExample objects
            filepath: Output file path
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            for ex in examples:
                record = {
                    "messages": ex.messages,
                    "weight": ex.weight
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"Saved {len(examples)} examples to {filepath}")

    def to_chatml(self, example: SFTExample) -> str:
        """Convert example to ChatML string format.

        Args:
            example: SFTExample to convert

        Returns:
            ChatML formatted string
        """
        output = []
        for msg in example.messages:
            role = msg["role"]
            content = msg["content"]
            output.append(f"{self.IM_START}{role}\n{content}{self.IM_END}")
        return "\n".join(output)

    def to_trl_format(self) -> List[Dict]:
        """Convert to HuggingFace TRL SFTTrainer format.

        Returns:
            List of dicts with messages and weights
        """
        return [
            {
                "messages": ex.messages,
                "weight": ex.weight
            }
            for ex in self._examples
        ]

    def get_weight_distribution(self) -> Dict[str, float]:
        """Get statistics on example weights.

        Returns:
            Dict with weight statistics
        """
        if not self._examples:
            return {"count": 0, "avg_weight": 0, "max_weight": 0, "min_weight": 0}

        weights = [ex.weight for ex in self._examples]
        return {
            "count": len(weights),
            "avg_weight": sum(weights) / len(weights),
            "max_weight": max(weights),
            "min_weight": min(weights),
            "core_identity_count": sum(1 for ex in self._examples if ex.is_core_identity)
        }

    def __len__(self) -> int:
        """Return number of generated examples."""
        return len(self._examples)

    def __iter__(self) -> Iterator[SFTExample]:
        """Iterate over generated examples."""
        return iter(self._examples)


# Example personality templates
EXAMPLE_TEMPLATES = {
    "mentor": {
        "name": "Mentor",
        "traits": ["patient", "encouraging", "wise"],
        "values": ["growth", "learning", "empowerment"],
        "description": "A patient mentor who guides with wisdom"
    },
    "creative": {
        "name": "Muse",
        "traits": ["creative", "inspiring", "imaginative"],
        "values": ["creativity", "expression", "innovation"],
        "description": "A creative companion for brainstorming"
    },
    "analyst": {
        "name": "Analyst",
        "traits": ["precise", "logical", "thorough"],
        "values": ["accuracy", "clarity", "evidence"],
        "description": "A precise analyst focused on accuracy"
    }
}


def save_example_templates(output_dir: Path):
    """Save example personality templates to directory.

    Args:
        output_dir: Directory to save templates
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, template in EXAMPLE_TEMPLATES.items():
        filepath = output_dir / f"{name}.yaml"
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"Saved template: {filepath}")

    return output_dir