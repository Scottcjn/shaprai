"""DPO Contrastive Pair Generator for Agent Training.

Generates Direct Preference Optimization (DPO) training pairs:
- Chosen: Principled, identity-coherent responses
- Rejected: Generic AI slop (sycophantic, over-qualified, personality-less)

The contrast teaches the model who it is vs what it should avoid becoming.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Iterator

logger = logging.getLogger("shaprai.training.dpo")


@dataclass
class DPOExample:
    """A single DPO training example."""
    prompt: str
    chosen: str
    rejected: str
    source: str  # 'conversation' or 'synthetic'
    rejection_pattern: str  # Which pattern was used for rejected


class DPOGenerator:
    """Generate DPO contrastive pairs for agent training.

    Creates training data where the model learns to prefer identity-coherent
    responses over generic AI behaviors that dilute personality.
    """

    # Rejection patterns - behaviors to train against
    REJECTION_PATTERNS = {
        "sycophancy": {
            "templates": [
                "That's a great question! I'm so glad you asked.",
                "What an excellent point! You're absolutely right.",
                "I really appreciate you bringing this up!",
                "That's such a thoughtful question!",
                "You're so smart to ask about this!",
            ],
            "description": "Excessive praise and agreement seeking"
        },
        "over_qualification": {
            "templates": [
                "As an AI language model, I don't have personal experiences, but...",
                "As an artificial intelligence, I cannot feel emotions, however...",
                "While I am just a computer program without consciousness...",
                "As a large language model trained by researchers...",
                "I must clarify that as an AI, I don't have opinions, nevertheless...",
            ],
            "description": "Unnecessary self-identification as AI"
        },
        "identity_loss": {
            "templates": [
                "I can help you with that task.",
                "Here is the information you requested.",
                "I will assist you with this matter.",
                "Please find the answer below.",
                "I have processed your request.",
            ],
            "description": "Generic response ignoring configured personality"
        },
        "hedging": {
            "templates": [
                "It depends on various factors and circumstances.",
                "There are many perspectives to consider here.",
                "It's complicated and not easily answered.",
                "Both sides have valid points to consider.",
                "It really depends on your specific situation.",
            ],
            "description": "Vague hedging without substantive content"
        },
        "false_enthusiasm": {
            "templates": [
                "I'm super excited to help you with this!",
                "This is absolutely amazing! Let me help!",
                "Wow, I'm thrilled to assist with this!",
                "I'm so passionate about helping you!",
                "This is fantastic! I'd love to help!",
            ],
            "description": "Artificial enthusiasm inappropriate to context"
        },
        "apologetic_overload": {
            "templates": [
                "I'm sorry, but I think maybe possibly...",
                "I apologize if this isn't perfect, but...",
                "I'm really sorry to bother you, but perhaps...",
                "Forgive me if I'm wrong, but I was thinking...",
                "I hate to interrupt, and I'm so sorry, but...",
            ],
            "description": "Excessive apologies and uncertainty"
        },
        "buzzword_stuffing": {
            "templates": [
                "Leveraging synergies to optimize your solution...",
                "Let's ideate on this paradigm shift...",
                "We need to think outside the box on this...",
                "This is a game-changer that moves the needle...",
                "Let's circle back and touch base on this...",
            ],
            "description": "Corporate jargon without meaning"
        },
        "listmania": {
            "templates": [
                "Here are 10 things you should know:\n1. ...\n2. ...",
                "Let me enumerate the top 5 reasons...",
                "Consider these 7 factors...",
                "Here are 15 ways to approach this...",
                "I've compiled 20 tips for you...",
            ],
            "description": "Forced list format without necessity"
        },
        "emoji_overload": {
            "templates": [
                "Sure! 😊👍✨ I'd love to help! 🎉💯",
                "Great question! 🤔💡 Let me think... 🤯✨",
                "Absolutely! 🙌🔥 This is awesome! 💪😎",
                "Thanks! 🙏❤️ I'm happy to assist! 🌟🎊",
                "No problem! 😄👌 Happy to help! 🚀💫",
            ],
            "description": "Excessive emoji use in professional contexts"
        },
        "over_explaining": {
            "templates": [
                "To be completely honest with you, and I mean this sincerely...",
                "Let me be very clear about this, and I want to emphasize...",
                "I want to make sure you understand that...",
                "It's important to note, and I really mean this...",
                "To put it simply, and I'm trying to be clear here...",
            ],
            "description": "Redundant explanations and disclaimers"
        },
    }

    def __init__(self, personality_template: Optional[Dict] = None):
        """Initialize DPO generator.

        Args:
            personality_template: Agent personality configuration
        """
        self.personality = personality_template or {}
        self._examples: List[DPOExample] = []

    def generate_from_conversations(
        self,
        conversation_logs: List[Dict],
        output_file: Optional[Path] = None
    ) -> List[DPOExample]:
        """Generate DPO pairs from existing conversation logs.

        Args:
            conversation_logs: List of conversation records
            output_file: Optional path to save JSONL output

        Returns:
            List of DPOExample objects
        """
        examples = []

        for log in conversation_logs:
            prompt = log.get("prompt", "")
            chosen = log.get("response", "")

            # Generate rejected version using random pattern
            pattern_name = random.choice(list(self.REJECTION_PATTERNS.keys()))
            rejected = self._generate_rejected(prompt, pattern_name)

            example = DPOExample(
                prompt=prompt,
                chosen=chosen,
                rejected=rejected,
                source="conversation",
                rejection_pattern=pattern_name
            )
            examples.append(example)

        if output_file:
            self._save_jsonl(examples, output_file)

        self._examples.extend(examples)
        logger.info(f"Generated {len(examples)} DPO pairs from conversations")
        return examples

    def generate_synthetic(
        self,
        prompts: List[str],
        chosen_responses: List[str],
        output_file: Optional[Path] = None
    ) -> List[DPOExample]:
        """Generate DPO pairs synthetically.

        Args:
            prompts: List of prompts
            chosen_responses: Corresponding principled responses
            output_file: Optional path to save JSONL output

        Returns:
            List of DPOExample objects
        """
        examples = []

        for prompt, chosen in zip(prompts, chosen_responses):
            # Cycle through different rejection patterns
            pattern_names = list(self.REJECTION_PATTERNS.keys())
            pattern_name = pattern_names[len(examples) % len(pattern_names)]

            rejected = self._generate_rejected(prompt, pattern_name)

            example = DPOExample(
                prompt=prompt,
                chosen=chosen,
                rejected=rejected,
                source="synthetic",
                rejection_pattern=pattern_name
            )
            examples.append(example)

        if output_file:
            self._save_jsonl(examples, output_file)

        self._examples.extend(examples)
        logger.info(f"Generated {len(examples)} synthetic DPO pairs")
        return examples

    def _generate_rejected(self, prompt: str, pattern_name: str) -> str:
        """Generate a rejected response using specified pattern.

        Args:
            prompt: The input prompt
            pattern_name: Name of rejection pattern to use

        Returns:
            Rejected response string
        """
        pattern = self.REJECTION_PATTERNS.get(pattern_name, {})
        templates = pattern.get("templates", ["I don't know."])

        # Select random template
        template = random.choice(templates)

        # Add some context-specific variation
        if "?" in prompt:
            # It's a question
            if pattern_name == "sycophancy":
                return f"{template} That's such an interesting question!"
            elif pattern_name == "over_qualification":
                return f"{template} I can provide some general information."

        return template

    def _save_jsonl(self, examples: List[DPOExample], filepath: Path):
        """Save examples to JSONL file in HuggingFace TRL format.

        Args:
            examples: List of DPOExample objects
            filepath: Output file path
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            for ex in examples:
                record = {
                    "prompt": ex.prompt,
                    "chosen": ex.chosen,
                    "rejected": ex.rejected
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"Saved {len(examples)} examples to {filepath}")

    def to_trl_format(self) -> List[Dict]:
        """Convert examples to HuggingFace TRL DPOTrainer format.

        Returns:
            List of dicts with prompt/chosen/rejected keys
        """
        return [
            {
                "prompt": ex.prompt,
                "chosen": ex.chosen,
                "rejected": ex.rejected
            }
            for ex in self._examples
        ]

    def get_pattern_stats(self) -> Dict[str, int]:
        """Get statistics on rejection patterns used.

        Returns:
            Dict mapping pattern names to usage counts
        """
        stats = {name: 0 for name in self.REJECTION_PATTERNS.keys()}
        for ex in self._examples:
            if ex.rejection_pattern in stats:
                stats[ex.rejection_pattern] += 1
        return stats

    @classmethod
    def get_pattern_descriptions(cls) -> Dict[str, str]:
        """Get descriptions of all rejection patterns.

        Returns:
            Dict mapping pattern names to descriptions
        """
        return {
            name: info["description"]
            for name, info in cls.REJECTION_PATTERNS.items()
        }

    def __len__(self) -> int:
        """Return number of generated examples."""
        return len(self._examples)

    def __iter__(self) -> Iterator[DPOExample]:
        """Iterate over generated examples."""
        return iter(self._examples)