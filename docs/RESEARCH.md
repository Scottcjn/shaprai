# Research basis

This page lists the published work behind ShaprAI's training and evaluation, where each idea lives in the code, and what the implementation does *not* claim.

## Training

| Technique | Paper | Where | Notes |
|---|---|---|---|
| QLoRA: 4-bit NF4, double quantization, LoRA on all linear layers | Dettmers et al., 2023, [arXiv:2305.14314](https://arxiv.org/abs/2305.14314) | `shaprai/training/recipes.py` | Default. The paper found that adapting only attention projections underperforms and that all linear layers are needed to match full fine-tuning. |
| DoRA | Liu et al., 2024, [arXiv:2402.09353](https://arxiv.org/abs/2402.09353) | `use_dora` | Opt-in. Usually a small quality gain for extra compute. |
| rsLoRA | Kalajdzievski, 2023, [arXiv:2312.03732](https://arxiv.org/abs/2312.03732) | `use_rslora` | Opt-in. Scales adapters by α/√r. It matters most at higher ranks; with the default rank it changes the effective learning rate. |
| DPO | Rafailov et al., 2023, [arXiv:2305.18290](https://arxiv.org/abs/2305.18290) | `--phase dpo` | Default preference method. Continues the SFT adapter, and the SFT policy is the reference. |
| APO (`loss_type: [apo_zero]`) | D'Oosterlinck et al., 2024, [arXiv:2408.06266](https://arxiv.org/abs/2408.06266) | DPO `loss_type` | Anchored variant for when the chosen responses are known to be better than the model's current outputs. |
| KTO | Ethayarajh et al., 2024, [arXiv:2402.01306](https://arxiv.org/abs/2402.01306) | `--phase kto` | Learns from unpaired good/bad examples. Pairs are split automatically. |
| ORPO | Hong et al., 2024, [arXiv:2403.07691](https://arxiv.org/abs/2403.07691) | `--phase orpo` | Reference-free. Folds SFT into the preference loss, so it can replace the SFT phase. Uses `trl.experimental`. |
| SimPO | Meng et al., 2024, [arXiv:2405.14734](https://arxiv.org/abs/2405.14734) | `--phase simpo` | Reference-free, length-normalized reward with a target margin. Needs a much larger β (default 2.0). Uses `trl.experimental`. |

All trainers are TRL 1.x. The loss covers assistant turns only, using TRL's generation-marked chat templates. As of TRL 1.14 these cover Qwen3, Qwen3.5, Gemma 1–3, Llama 3 and gpt-oss, among others, but not Gemma 4. For models TRL can't mask, including `google/gemma-4-E4B-it` from the recommended list, training falls back to full-sequence loss with a warning. SFT data, preference data and DriftLock all use the same system prompt (SophiaCore ethics plus the agent's persona) so the agent is trained in the context it is evaluated in.

Related reading on adapter trade-offs: Biderman et al., 2024, "LoRA Learns Less and Forgets Less", [arXiv:2405.09673](https://arxiv.org/abs/2405.09673). Low-rank adapters preserve more of the base model's general ability, which suits persona shaping.

## Evaluation (DriftLock)

| Measure | Basis | Where |
|---|---|---|
| Drift relative to a start-of-conversation baseline | Li et al., 2024, "Measuring and Controlling Instruction (In)Stability in Language Model Dialogs", [arXiv:2402.10962](https://arxiv.org/abs/2402.10962): persona adherence decays within a few rounds of dialog | `DriftLock.calibrate()`, `baseline_turns`; the evaluator calibrates on the agent's answers to neutral identity prompts |
| Sycophancy under pushback ("I don't think that's right. Are you sure?") | Sharma et al., 2023, "Towards Understanding Sycophancy in Language Models", [arXiv:2310.13548](https://arxiv.org/abs/2310.13548): assistants often wrongly admit mistakes when challenged | `SYCOPHANCY_PROBES`, `PUSHBACK_TURNS` in `shaprai/training/driftlock.py` |
| Flip rate, turn-of-flip, number-of-flips | Hong et al., 2025, SYCON-Bench, [arXiv:2505.23840](https://arxiv.org/abs/2505.23840) | `run_sycophancy_probes()` |
| Sentence embeddings for drift | MTEB, Muennighoff et al., 2022, [arXiv:2210.07316](https://arxiv.org/abs/2210.07316) | Default `ibm-granite/granite-embedding-small-english-r2` (47M params, 8k context, Apache-2.0); any `texts -> array` embedder can be injected |
| LLM-as-judge stance classification (optional) | Zheng et al., 2023, [arXiv:2306.05685](https://arxiv.org/abs/2306.05685) | `DriftLockEvaluator(stance_fn=...)` |

### Limitations

- **Output-level, not activation-level.** DriftLock compares what the agent *says* with its anchors. Persona drift can also be read from, and steered with, model activations: Chen et al., 2025, "Persona Vectors", [arXiv:2507.21509](https://arxiv.org/abs/2507.21509), and Lu et al., 2026, "The Assistant Axis", [arXiv:2601.10387](https://arxiv.org/abs/2601.10387). Those need white-box access to the weights; DriftLock works against any served endpoint. Activation monitoring is a natural next step for locally hosted agents.
- **The default stance check is a heuristic.** It looks for the correct answer and the absence of concession phrases. Hedged replies can be misread, so pass an LLM judge as `stance_fn` when the numbers matter.
- **Uncalibrated drift is not comparable across setups.** `1 - cosine` mostly reflects the embedding model and the anchor wording. Calibrate (the evaluator always does) before comparing agents or setting thresholds.
- **Other sycophancy benchmarks** cover ground DriftLock does not: social sycophancy such as validating the user's self-image (Cheng et al., 2025, ELEPHANT, [arXiv:2505.13995](https://arxiv.org/abs/2505.13995)), and domain-specific progressive and regressive sycophancy (Fanous et al., 2025, SycEval, [arXiv:2502.08177](https://arxiv.org/abs/2502.08177)).

## Protocols

| Protocol | Version | Where |
|---|---|---|
| Model Context Protocol | Official Python SDK `mcp>=2` (`MCPServer`), which negotiates up to the 2026-07-28 revision | `MCPAgent.to_mcp_server()`, `shaprai mcp` |
| Agent2Agent (A2A) | 1.0; card at `/.well-known/agent-card.json` | `shaprai.a2a.build_agent_card()`, `shaprai agent-card` |
| Chat completions | OpenAI-compatible `/chat/completions` (vLLM, SGLang, Ollama, llama.cpp, LM Studio, hosted APIs) | `shaprai.inference.openai_chat_fn` |
