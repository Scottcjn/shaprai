"""Regression tests for the DPO synthetic-pair generator.

Guards against the `str.format` KeyError that occurred when a rejection
template used `{a/b/c}` "pick-one" pseudo-syntax: `str.format` treats the whole
`a/b/c` blob as one field name and raises KeyError, crashing the default
`generate_synthetic_pairs` path.
"""

import random

from shaprai.training.dpo_generator import (
    REJECTION_PATTERNS,
    generate_synthetic_pairs,
)

# The keyword arguments the generator supplies to `template.format(...)`.
_FORMAT_KWARGS = {
    "great": "great",
    "question": "question",
    "do_that": "do that",
    "help": "help",
}


def test_every_rejection_template_formats_with_supplied_kwargs():
    # Any template referencing a field name not in _FORMAT_KWARGS would raise
    # KeyError here, exactly as it does inside generate_synthetic_pairs.
    for pattern_id, template, _ in REJECTION_PATTERNS:
        template.format(**_FORMAT_KWARGS)


def test_generate_synthetic_pairs_never_crashes_across_seeds():
    for seed in range(30):
        random.seed(seed)
        pairs = generate_synthetic_pairs(50)
        assert pairs
        for pair in pairs:
            # A leftover unfilled placeholder would mean a template slipped
            # through with a wrong field name.
            assert "{" not in pair.rejected and "}" not in pair.rejected
