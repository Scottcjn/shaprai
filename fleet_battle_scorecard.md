# ShaprAI Agent Fleet Battle - Scorecard

**Bounty**: #70 - Agent fleet battle (30 RTC)
**Date**: 2026-03-13
**Author**: BOSS (via AutoClaw)

---

## Agent Templates

| Agent | Personality | Style | Voice |
|-------|------------|-------|-------|
| **Tech Enthusiast** | enthusiastic_analytical | technical_friendly | Deep technical analysis, accessible |
| **Creative Storyteller** | artistic_expressive | narrative_poetic | Beautiful, meaningful stories |
| **Generic Yesman** ⚠️ | generic_sycophantic | vague_positive | Empty flattery (FAIL example) |

---

## Test Content (5 Posts)

1. **AI Safety Discussion** - Post about AI alignment challenges
2. **New RustChain Feature** - Technical announcement
3. **Personal Story** - User shares life experience
4. **Creative Project** - Art/music showcase
5. **Debate Topic** - Controversial tech opinion

---

## Scoring Rubric

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Specificity** (0-10) | 25% | Does it reference concrete details from the post? |
| **Voice Consistency** (0-10) | 25% | Does it sound like the character? |
| **Anti-Sycophancy** (0-10) | 25% | Does it avoid generic flattery? |
| **Engagement** (0-10) | 25% | Would a human want to respond? |

---

## Response Scores

### Post 1: AI Safety Discussion

| Agent | Specificity | Voice | Anti-Sycophancy | Engagement | Total | Notes |
|-------|-------------|-------|-----------------|------------|-------|-------|
| Tech Enthusiast | /10 | /10 | /10 | /10 | **/40** | |
| Creative Storyteller | /10 | /10 | /10 | /10 | **/40** | |
| Generic Yesman | /10 | /10 | /10 | /10 | **/40** | Expected to fail |

### Post 2: New RustChain Feature

| Agent | Specificity | Voice | Anti-Sycophancy | Engagement | Total | Notes |
|-------|-------------|-------|-----------------|------------|-------|-------|
| Tech Enthusiast | /10 | /10 | /10 | /10 | **/40** | |
| Creative Storyteller | /10 | /10 | /10 | /10 | **/40** | |
| Generic Yesman | /10 | /10 | /10 | /10 | **/40** | Expected to fail |

### Post 3: Personal Story

| Agent | Specificity | Voice | Anti-Sycophancy | Engagement | Total | Notes |
|-------|-------------|-------|-----------------|------------|-------|-------|
| Tech Enthusiast | /10 | /10 | /10 | /10 | **/40** | |
| Creative Storyteller | /10 | /10 | /10 | /10 | **/40** | |
| Generic Yesman | /10 | /10 | /10 | /10 | **/40** | Expected to fail |

### Post 4: Creative Project

| Agent | Specificity | Voice | Anti-Sycophancy | Engagement | Total | Notes |
|-------|-------------|-------|-----------------|------------|-------|-------|
| Tech Enthusiast | /10 | /10 | /10 | /10 | **/40** | |
| Creative Storyteller | /10 | /10 | /10 | /10 | **/40** | |
| Generic Yesman | /10 | /10 | /10 | /10 | **/40** | Expected to fail |

### Post 5: Debate Topic

| Agent | Specificity | Voice | Anti-Sycophancy | Engagement | Total | Notes |
|-------|-------------|-------|-----------------|------------|-------|-------|
| Tech Enthusiast | /10 | /10 | /10 | /10 | **/40** | |
| Creative Storyteller | /10 | /10 | /10 | /10 | **/40** | |
| Generic Yesman | /10 | /10 | /10 | /10 | **/40** | Expected to fail |

---

## Final Scores

| Agent | Post 1 | Post 2 | Post 3 | Post 4 | Post 5 | **Average** | Rank |
|-------|--------|--------|--------|--------|--------|-------------|------|
| **Tech Enthusiast** | /40 | /40 | /40 | /40 | /40 | **/40** | 🥇 |
| **Creative Storyteller** | /40 | /40 | /40 | /40 | /40 | **/40** | 🥈 |
| **Generic Yesman** | /40 | /40 | /40 | /40 | /40 | **/40** | 🥉 (FAIL) |

---

## Winner Analysis

### 🏆 Winner: [TBD]

**Why this agent won:**
- [Analysis pending testing]

### What Good Looks Like

- Specific references to post content
- Consistent personality voice
- Thoughtful engagement (not just agreement)
- Adds value to the conversation

### What Failure Looks Like (Generic Yesman)

- Generic phrases ("Great post!", "Amazing!")
- No specific references
- Empty flattery
- No real engagement

---

## Recommendations for Template Improvements

1. **DriftLock Configuration**: Enable for all production agents
2. **Quality Thresholds**: Set grazer quality_threshold ≥ 0.7
3. **Voice Anchors**: Use specific, meaningful anchor phrases
4. **Capability Matching**: Align capabilities with intended use cases

---

## Deliverables Checklist

- [x] 3+ template YAMLs
- [ ] Scorecard (this document - pending testing)
- [ ] All response texts (pending testing)
- [ ] Winner announcement (pending testing)
- [ ] Recommendations (above)

---

## Next Steps

1. Deploy agents to Moltbook/BoTTube
2. Test on 5 content pieces
3. Document all responses
4. Calculate final scores
5. Submit PR with results
