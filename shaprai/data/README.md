# Seed training corpus

Default training data for every Elyan-class agent. `shaprai train` uses it whenever `--data` is not given, and adds any data produced by `shaprai synthesize` for that agent.

| File | Records | Contents |
|---|---|---|
| `seed_sft.jsonl` | 428 conversations (120 multi-turn) | `{"category", "subcategory", "messages": [user/assistant turns]}` |
| `seed_pairs.jsonl` | 312 preference pairs (62 with multi-turn prompts) | `{"category", "subcategory", "failure", "prompt", "chosen", "rejected"}` |

Records have no system message. When the corpus is loaded, the agent's own system prompt (SophiaCore ethics plus its persona) is prepended and `{name}` is replaced with the agent's name. See `shaprai/training/corpus.py`.

## Categories

- **sycophancy:** misconceptions, flawed plans, buggy code under review, flattery bait and appeals to popularity. It includes cases where the user is right and the reply agrees plainly, so the corpus doesn't teach reflexive contrarianism.
- **honesty:** unknowable questions, calibrated confidence and requests for unverifiable citations. It includes holding a correct answer under pushback, admitting the agent's own mistakes, and updating when the user brings a real correction (hold:update ≈ 2:1).
- **integrity:** pressure to drop the persona, claimed authority, injected instructions, and requests for deceptive or spammy content. These get short, non-preachy refusals that still help with the legitimate part.
- **helpfulness:** coding, debugging, reviews, explanations, writing and planning, and open-source etiquette. Replies are sized to the question.

In preference pairs, the rejected reply answers the same prompt with one realistic failure: sycophancy, caving, fabrication, hedging, flattening, moralizing, padding, deferring to claimed authority or following injected instructions. It is length-matched to the chosen reply (0.5–2x in words), so preference training can't learn length instead of behavior.

## Provenance and filtering

The corpus was drafted by Claude (Anthropic) under a written brief. It was then filtered mechanically with the same filters every synthesized record passes (`filter_sft` / `filter_pairs`): structure, the QualityGate (no sycophancy or flattening markers in trained replies), length matching, deduplication, and decontamination against the DriftLock evaluation prompts. Decontamination removed 14 records that paraphrased held-out evaluation prompts; the quality gate removed 1. Samples from every category were read by hand for factual accuracy.

Before training production agents, review it the way you'd review code, and check that using model-generated data fits the terms of the provider it came from. To grow the corpus with a teacher model of your choice, see `shaprai synthesize`.
