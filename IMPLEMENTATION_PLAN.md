# DriftLock Implementation Plan - Issue #4

## Overview
Replace placeholder drift measurement with real semantic drift detection using sentence embeddings and cosine similarity.

## Technical Approach

### 1. Core Implementation (`shaprai/training/driftlock.py`)

**Replace `measure_drift()` method:**
- Use `sentence-transformers` library (model: `all-MiniLM-L6-v2`)
- Load anchor phrases from `get_driftlock_anchors()`
- Compute embeddings for:
  - Anchor phrases (once, cached)
  - Current response window (last N responses, default 10)
- Calculate cosine similarity between response embeddings and anchor embeddings
- Return drift score: 0.0 (perfect alignment) to 1.0 (complete drift)

**Key metrics:**
- Sliding window: last 10 responses (configurable)
- Drift threshold: 0.4 (configurable)
- Alert callback when threshold exceeded
- Performance target: <50ms per response on CPU

### 2. Dependencies
Add to `pyproject.toml`:
```toml
dependencies = [
    ...existing...
    "sentence-transformers>=2.2.0",
    "torch>=2.0.0",
    "scikit-learn>=1.3.0",  # for cosine_similarity
]
```

### 3. Implementation Details

**Embedding Strategy:**
- Cache anchor embeddings (compute once per evaluator instance)
- Use mean pooling for multi-sentence responses
- Normalize vectors before cosine similarity
- Aggregate similarity scores across all anchors (mean)

**Drift Calculation:**
```python
drift_score = 1.0 - mean_cosine_similarity
```

**Sliding Window:**
- Maintain deque of last N response embeddings
- Compute drift as: `1.0 - similarity(current_window_mean, anchor_mean)`
- Alert when drift > threshold

### 4. Testing Strategy

**Unit Tests (`tests/test_driftlock.py`):**
- Test embedding generation
- Test cosine similarity calculation
- Test sliding window behavior
- Test threshold alerting

**Integration Test:**
- 50+ turn synthetic conversation
- Scenarios:
  1. Identity-aligned responses (low drift)
  2. Generic/flattened responses (high drift)
  3. Sycophantic responses (high drift)
  4. Correction mechanism (drift reduction after re-injection)
- Verify drift increases over time without correction
- Verify correction reduces drift

**Performance Benchmark:**
- Measure embedding time per response
- Target: <50ms on CPU
- Test on various response lengths

### 5. Correction Mechanism
When drift > threshold:
- Callback to re-inject identity context
- Prepend anchor phrases to next prompt
- Verify drift reduction in next window

## Acceptance Criteria Checklist

- [ ] `shaprai/training/driftlock.py` implements real drift measurement
- [ ] Uses `sentence-transformers` (`all-MiniLM-L6-v2`)
- [ ] Anchor phrases loaded from `get_driftlock_anchors()`
- [ ] Cosine similarity between response and anchor embeddings
- [ ] Drift score: 0.0 (perfect) to 1.0 (drifted)
- [ ] Sliding window over last N responses (default 10, configurable)
- [ ] Alert/callback when drift > threshold (default 0.4)
- [ ] 50+ turn synthetic conversation tests
- [ ] Drift increases over long conversations (verified)
- [ ] DriftLock detects increase (verified)
- [ ] Correction reduces drift (verified)
- [ ] Benchmark: <50ms per response on CPU
- [ ] Works offline (model downloaded once)
- [ ] Unit tests + integration test
- [ ] Documentation updated

## Timeline
- Day 1: Core implementation + unit tests
- Day 2: Integration tests + benchmarking
- Day 3: Documentation + PR submission

## Questions for Maintainer
1. Should we support multiple embedding models or stick to `all-MiniLM-L6-v2`?
2. Preferred callback mechanism for drift alerts?
3. Should correction be automatic or manual?
