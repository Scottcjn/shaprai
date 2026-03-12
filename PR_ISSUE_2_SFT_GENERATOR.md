# PR: SFT Training Data Generator - Issue #2

## Summary

Implements Issue #2: Training data generator for SFT pipeline.

**Bounty:** 50 RTC

## Changes

### Core Implementation (`shaprai/training/sft_generator.py`)
- ✅ Generate ChatML-formatted JSONL training data compatible with HuggingFace TRL SFTTrainer
- ✅ Identity-weighted sampling: personality-defining examples weighted 3-5x higher
- ✅ Template-driven personality configuration via YAML/JSON
- ✅ Multiple data generation patterns:
  - Identity-establishing conversations
  - Instructional/tutorial data
  - Contrast pairs (good vs bad responses)
  - Ethical boundary scenarios
  - Domain-specific Q&A

### CLI Command (`shaprai/cli.py`)
- ✅ New command: `shaprai generate-sft --template my_agent.yaml --output train.jsonl --count 1000`
- ✅ Supports `--include-contrast` for contrast pairs
- ✅ Supports `--verbose` for detailed logging
- ✅ Auto-detects agent template vs personality template format

### Example Templates (`templates/sft_*.yaml`)
- ✅ `sft_code_reviewer.yaml`: Code review specialist (identity_weight: 4.5)
- ✅ `sft_community_builder.yaml`: Community management agent (identity_weight: 4.0)
- ✅ `sft_technical_educator.yaml`: Technical education specialist (identity_weight: 5.0)

### Tests (`tests/test_sft_generator.py`)
- ✅ 25+ comprehensive unit tests
- ✅ ChatML format validation
- ✅ Identity-weighted sampling verification
- ✅ Category distribution tests
- ✅ Template loading tests

### Documentation (`shaprai/training/README.md`)
- ✅ CLI usage examples
- ✅ Python API examples
- ✅ Template format specification
- ✅ Output format documentation
- ✅ TRL SFTTrainer integration guide

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `shaprai/training/sft_generator.py` module created | ✅ |
| Generates valid ChatML JSONL output | ✅ |
| Identity-weighted sampling (3-5x higher) | ✅ |
| Template-driven (YAML/JSON config) | ✅ |
| CLI command: `shaprai generate-sft` | ✅ |
| At least 3 example personality templates | ✅ |
| Compatible with HuggingFace TRL SFTTrainer | ✅ |
| Unit tests for generator logic | ✅ |

## Usage Examples

### CLI
```bash
# Generate 1000 examples from bounty_hunter template
shaprai generate-sft --template templates/bounty_hunter.yaml -o train.jsonl -c 1000

# Include contrast pairs
shaprai generate-sft --template templates/sft_code_reviewer.yaml --include-contrast -v

# Custom output path
shaprai generate-sft -t my_agent.yaml -o output/train.jsonl -c 500
```

### Python API
```python
from shaprai.training.sft_generator import SFTDataGenerator, load_agent_template

# Load template
template = load_agent_template("templates/bounty_hunter.yaml")

# Create generator and generate data
generator = SFTDataGenerator(template=template)
stats = generator.generate_and_save(
    count=1000,
    output_path="train.jsonl",
    include_contrast_pairs=True
)

print(f"Generated {stats['total_examples']} examples")
print(f"Average weight: {stats['average_weight']:.2f}")
```

### Output Format
```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "weight": 4.0}
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "weight": 1.0}
```

## Testing Results

```bash
# Test generation
shaprai generate-sft -t templates/sft_code_reviewer.yaml -o test.jsonl -c 20

# Output:
# [OK] Generated 20 examples
#   Category distribution:
#     domain_qa: 7
#     contrast_good: 5
#     identity: 4
#     instructional: 4
```

## Identity-Weighted Sampling

The generator implements sophisticated identity-weighted sampling:

| Category | Weight |
|----------|--------|
| Identity conversations | 4.0 (template.identity_weight) |
| Ethical boundaries | 4.8 (identity_weight × 1.2) |
| Instructional data | 1.0 |
| Domain Q&A | 1.0 |
| Contrast (good) | 4.0 |
| Contrast (bad) | 0.5 |

This ensures personality-defining responses have 3-5x stronger influence during training.

## Related Issue

Fixes #2: [BOUNTY: 50 RTC] Training data generator for SFT pipeline

## Next Steps

1. Push branch to GitHub
2. Create PR referencing this issue
3. Run CI/CD checks
4. Merge to main
