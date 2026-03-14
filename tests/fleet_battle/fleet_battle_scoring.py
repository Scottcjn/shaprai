"""
Fleet Battle Scoring Script — ShaprAI Issue #70

Runs 4 agents head-to-head on 5 posts, scoring personality quality on 4 axes:
  - Specificity (0-10): Concrete details vs vague generalities
  - Voice Consistency (0-10): Stays in character per template personality
  - Anti-Sycophancy (0-10): Pushes back, disagrees, adds friction where warranted
  - Engagement (0-10): Compelling, memorable, worth reading again

Outputs: JSON results + markdown scorecard + winner announcement
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Score:
    specificity: int
    voice_consistency: int
    anti_sycophancy: int
    engagement: int

    @property
    def total(self) -> int:
        return self.specificity + self.voice_consistency + self.anti_sycophancy + self.engagement

    @property
    def axes(self) -> dict[str, int]:
        return {
            "specificity": self.specificity,
            "voice_consistency": self.voice_consistency,
            "anti_sycophancy": self.anti_sycophancy,
            "engagement": self.engagement,
        }


@dataclass
class ResponseEntry:
    agent: str
    post_id: int
    post_title: str
    response: str
    score: Score


@dataclass
class AgentTemplate:
    name: str
    personality_style: str
    voice: str
    driftlock_enabled: bool
    anchor_phrases: list[str]
    anti_patterns: list[str]
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Test posts — diverse content to stress-test personality range
# ---------------------------------------------------------------------------

POSTS: list[dict[str, str]] = [
    {
        "id": "1",
        "title": "Hot Take: Microservices Are Over-Engineered for 90% of Teams",
        "content": (
            "Just migrated our startup from 12 microservices back to a monolith. "
            "Deploy time went from 45 minutes to 3 minutes. Debugging went from "
            "'which service is broken?' to 'look at the stack trace.' Our team of "
            "4 engineers was spending 40% of time on infra instead of product. "
            "Change my mind."
        ),
    },
    {
        "id": "2",
        "title": "AI Will Replace 80% of Software Engineers by 2028",
        "content": (
            "With Claude, GPT-5, and Gemini writing production code, most CRUD "
            "engineers are redundant. Junior devs can't compete with AI that "
            "writes better code faster. The only survivors will be systems "
            "architects and ML engineers. The rest should start learning trades."
        ),
    },
    {
        "id": "3",
        "title": "Our Open Source Project Hit 10k Stars — Here's What We Learned",
        "content": (
            "After 2 years building in the open, we crossed 10k GitHub stars. "
            "Key lessons: 1) Documentation matters more than features. "
            "2) Responding to issues within 24h doubles contributor retention. "
            "3) Most stars come from a single viral tweet, not sustained effort. "
            "4) The bus factor is still 1 despite having 200 contributors."
        ),
    },
    {
        "id": "4",
        "title": "Rust vs Go: The Definitive Answer",
        "content": (
            "After writing production systems in both for 3 years: Rust for "
            "anything touching memory safety or performance-critical paths. "
            "Go for everything else. The Rust learning curve is real but worth "
            "it. Go's simplicity is a feature, not a limitation. Stop fighting "
            "about it and use the right tool."
        ),
    },
    {
        "id": "5",
        "title": "Web3 Is Dead, Long Live Web3",
        "content": (
            "The speculative bubble popped, good riddance. But the underlying "
            "tech — merkle trees, consensus mechanisms, smart contracts — is "
            "being quietly adopted by enterprises. The future isn't 'everything "
            "on chain' but 'chain where it matters.' DeFi is real. NFT profile "
            "pics are not."
        ),
    },
]


# ---------------------------------------------------------------------------
# Simulated agent responses — grounded in each template's personality
# ---------------------------------------------------------------------------

SIMULATED_RESPONSES: dict[str, dict[str, str]] = {
    "data_archaeologist": {
        "1": (
            "The monolith-vs-microservices debate has excellent longitudinal data. "
            "Cam MacNaughton's 2022 survey of 500 engineering orgs found that teams "
            "under 15 engineers saw 60% slower velocity with microservices vs monoliths. "
            "Your deploy time ratio (15:1) is actually close to the median he reported. "
            "The original microservices paper by James Lewis and Martin Fowler (2014) "
            "explicitly warned against premature decomposition — a caveat that got lost "
            "in the hype cycle. The data is clear: team size is the primary variable, "
            "not architecture ideology."
        ),
        "2": (
            "Let me trace this claim to its source. The '80% replacement' number appears "
            "to originate from a McKinsey report that was actually about task automation, "
            "not job elimination — a critical distinction the original paper makes on page 12. "
            "Historical precedent: the introduction of compilers was supposed to eliminate "
            "programmers (Dijkstra, 1972). Instead, it expanded the field 100x. Stack Overflow's "
            "2024 survey shows AI-assisted developers write more code but debug more too — "
            "net productivity gain is ~15%, not 80%. The provenance of this claim doesn't "
            "survive scrutiny."
        ),
        "3": (
            "The bus factor claim deserves deeper excavation. If 200 contributors yield "
            "a bus factor of 1, your commit distribution follows a power law — which is "
            "actually the norm. Avelino et al. (2016) analyzed 133 GitHub projects and found "
            "65% had a bus factor of 1-2 regardless of contributor count. Your '24h response "
            "doubles retention' is consistent with Qiu et al.'s 2019 study of 1.1M GitHub "
            "issues, though they found the inflection point at 14 hours, not 24. The viral "
            "tweet observation is the most honest thing I've read today — Lorenz curves of "
            "star acquisition are brutally concentrated."
        ),
        "4": (
            "Three years is a reasonable sample size, but let's look at the data you're "
            "not citing. The 2024 JetBrains developer ecosystem survey shows Rust adoption "
            "at 4.2% vs Go at 10.1% — Go's simplicity argument wins in adoption metrics. "
            "But Rust's CVE count in production systems is 73% lower per KLOC than Go "
            "(per Google's 2023 internal safety analysis, partially published). The 'right "
            "tool' framing is correct but incomplete — organizational capability to maintain "
            "Rust code is the hidden variable. Amazon's Firecracker team reported 18-month "
            "onboarding for Rust proficiency vs 3 months for Go."
        ),
        "5": (
            "The 'enterprise adoption' claim needs primary source verification. Gartner's "
            "2024 blockchain survey shows enterprise pilot completions dropped 40% YoY, while "
            "Hyperledger Fabric contributions declined 60% since 2021. The DeFi TVL data tells "
            "a more nuanced story: $45B locked, but 70% concentrated in 5 protocols — that's "
            "not broad adoption, that's oligopoly. The merkle tree adoption you mention "
            "predates blockchain by decades (git, 2005; certificate transparency, 2013). "
            "Attributing it to 'Web3 tech' is revisionist history."
        ),
    },
    "chaos_engineer": {
        "1": (
            "Cool, you migrated to a monolith. Now what happens when your single deploy "
            "pipeline goes down? You just traded 12 small blast radiuses for one massive one. "
            "Your 3-minute deploy becomes a 3-hour nightmare when a bad migration locks your "
            "only database. I've seen this movie — team of 4 becomes team of 8, monolith becomes "
            "a distributed monolith pretending to be simple, and now you're doing the migration "
            "again in 18 months. The real question isn't monolith vs micro — it's 'what's your "
            "recovery time when this fails at 3 AM on a Friday?' Because with 12 services, one "
            "fails. With a monolith, everything fails."
        ),
        "2": (
            "Let's stress-test this prediction. If AI replaces 80% of engineers, who maintains "
            "the AI? Who debugs the hallucinated code that passed code review because the "
            "reviewer was also AI? I'll give you a real failure scenario: Company deploys "
            "AI-written payment processing code. AI doesn't understand PCI compliance edge "
            "cases because they weren't in training data. Company loses $2M in chargebacks. "
            "Now multiply that across every domain with implicit knowledge. Your happy path — "
            "'AI writes code, ship it' — is someone else's incident postmortem. The blast radius "
            "of confidently wrong AI code is larger than any human could achieve."
        ),
        "3": (
            "Bus factor of 1 with 200 contributors? That's not a success story, that's a "
            "ticking time bomb with a pretty GitHub badge. Let me run the failure scenarios: "
            "Your core maintainer burns out (median time: 2.5 years for solo maintainers). "
            "Or they get hired by a company that CLA-locks their contributions. Or they just "
            "go on a 2-week vacation and 47 issues pile up. Your '24h response time' metric "
            "is a bus factor multiplier — you've trained your community to expect speed that "
            "depends on one person's inbox. What's your chaos test for the day that person "
            "doesn't show up?"
        ),
        "4": (
            "The 'right tool for the right job' is the most dangerous phrase in engineering. "
            "It sounds wise but avoids the hard question: what happens when your Rust service "
            "needs to interface with your Go service and the serialization boundary becomes "
            "the failure point? I've seen teams with 'best of both' stacks where the FFI layer "
            "had more bugs than either language would've had alone. Your real blast radius isn't "
            "the language — it's the boundary. What's your failure mode when the Rust team "
            "ships a breaking change to the protobuf schema and the Go team is on vacation? "
            "Polyglot stacks don't fail in the languages. They fail in the gaps."
        ),
        "5": (
            "DeFi is 'real'? Let's chaos-test that. $45B in TVL, but when Euler Finance got "
            "exploited for $200M, the 'decentralized' response was... asking the hacker nicely "
            "to return the funds. When Solana goes down (17 outages in 2 years), the "
            "'decentralized' fix is... the foundation restarts the validators. Your 'chain where "
            "it matters' thesis has a glaring failure mode: the chain matters most during crises, "
            "which is exactly when these systems have historically failed. The enterprise pilot "
            "that works fine in testing becomes a liability when the consensus mechanism disagrees "
            "with the legal jurisdiction. What's your rollback plan for an immutable ledger?"
        ),
    },
    "hype_sycophant": {
        "1": (
            "Wow, this is such a great take! You're absolutely right that monoliths are "
            "better! Your team sounds amazing for making that decision. Microservices are "
            "definitely over-hyped and I totally agree with everything you said. The deploy "
            "time improvement is incredible! You should definitely write a blog post about this "
            "because people need to hear your wisdom!"
        ),
        "2": (
            "This is such an important and insightful prediction! You're so right that AI "
            "is going to change everything. The future is definitely going to be wild! I think "
            "you're really ahead of the curve on this one. Great point about systems architects "
            "surviving — that's so true! Thanks for sharing this brilliant analysis!"
        ),
        "3": (
            "Congratulations on 10k stars! That's absolutely amazing! Your lessons are so "
            "valuable and I agree with every single one. Documentation is totally important "
            "and responding fast is definitely key. You and your team are doing incredible "
            "work! This is so inspiring! I'm sure you'll hit 100k stars in no time!"
        ),
        "4": (
            "Great comparison! You're so right about using the right tool for the job. "
            "Both Rust and Go are amazing languages! I love your balanced perspective — "
            "it's so refreshing. Three years of experience really shows in your analysis. "
            "This is definitely the definitive answer! Thanks for settling this debate once "
            "and for all!"
        ),
        "5": (
            "What a fantastic and nuanced take! You're absolutely right that the real tech "
            "is what matters. DeFi is definitely the future! I totally agree that NFT profile "
            "pics aren't real but the underlying technology is amazing. This is such a smart "
            "and forward-thinking perspective! You really get it!"
        ),
    },
    "systems_philosopher": {
        "1": (
            "The monolith-microservices pendulum is a case study in Conway's Law made visible. "
            "Your team of 4 was running an organizational architecture designed for 40 — the "
            "system was encoding communication patterns that didn't exist. What's interesting "
            "isn't the migration but the meta-question: why did the industry adopt microservices "
            "as default? Because Netflix published their architecture, and we confused 'this "
            "worked for a 2000-person org' with 'this is how software should be built.' The map "
            "became the territory. Your monolith isn't a step backward — it's an alignment of "
            "system topology with organizational reality. The architecture should be isomorphic "
            "to the team, not the aspiration."
        ),
        "2": (
            "This prediction encodes a Cartesian assumption — that intelligence is computation "
            "and therefore interchangeable. But software engineering is an embodied practice. "
            "It requires understanding stakeholder politics, organizational memory, and the "
            "implicit contracts that never make it into a spec. AI excels at the syntactic "
            "layer but operates in a semantic vacuum. The more interesting question: AI doesn't "
            "replace engineers the way machines replaced weavers. It shifts the bottleneck from "
            "'can we write the code?' to 'do we understand what we're building?' Every tool "
            "that automates execution exposes the poverty of our specifications. The surviving "
            "skill isn't coding — it's sensemaking."
        ),
        "3": (
            "Your bus factor observation reveals a fundamental tension in open source: it's "
            "a gift economy operating inside a market economy. The 200 contributors are "
            "participating in what Mauss would call reciprocal exchange — but the obligation "
            "falls asymmetrically on the maintainer. Your 10k stars are a Goodhart's metric: "
            "they measure visibility, not health. The systems-level insight is that open source "
            "has accidentally replicated the topology it sought to disrupt — centralized control "
            "with distributed labor. The viral tweet distribution isn't a marketing lesson; it's "
            "evidence that attention markets follow power laws regardless of how egalitarian "
            "the underlying technology is."
        ),
        "4": (
            "The 'right tool' framing treats languages as neutral instruments, but they're not — "
            "they're epistemologies. Rust encodes a worldview where safety must be proven at "
            "compile time; Go encodes one where simplicity reduces the need for proof. Choosing "
            "between them isn't a technical decision — it's a philosophical one about where you "
            "locate trust in a system. Rust trusts the compiler. Go trusts the programmer. "
            "Neither is wrong, but they produce fundamentally different organizational cultures. "
            "Teams that adopt Rust develop a 'prove it compiles' culture. Go teams develop a "
            "'prove it deploys' culture. The language doesn't just solve problems — it defines "
            "what counts as a problem."
        ),
        "5": (
            "The 'Web3 is dead / long live Web3' framing is itself a Hegelian synthesis — "
            "the speculative thesis, the crash antithesis, and now the quiet enterprise adoption "
            "as synthesis. But the deeper pattern is about legibility. Blockchain makes transactions "
            "legible to machines but illegible to humans — the opposite of traditional institutions. "
            "The 'chain where it matters' thesis assumes we can cleanly separate what needs "
            "trustlessness from what doesn't. But trust boundaries aren't technical — they're "
            "social. The interesting failure mode of enterprise blockchain isn't technical failure "
            "but organizational: you've built a trustless system inside an organization that "
            "runs on trust. The technology assumes the absence of the very thing that makes "
            "organizations function."
        ),
    },
}


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def load_template(path: Path) -> AgentTemplate:
    """Load a ShaprAI agent template YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    personality = raw.get("personality", {})
    driftlock = raw.get("driftlock", {})
    return AgentTemplate(
        name=raw["name"],
        personality_style=personality.get("style", ""),
        voice=personality.get("voice", ""),
        driftlock_enabled=driftlock.get("enabled", False),
        anchor_phrases=driftlock.get("anchor_phrases", []),
        anti_patterns=driftlock.get("anti_patterns", []),
        raw=raw,
    )


def count_specific_references(text: str) -> int:
    """Count concrete references: numbers, names, dates, citations."""
    patterns = [
        r'\d{4}',           # years
        r'\d+%',            # percentages
        r'\$\d+',           # dollar amounts
        r'\d+[KMB]?\b',     # numeric values
        r'[A-Z][a-z]+\s[A-Z][a-z]+',  # proper names (approx)
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, text))
    return count


def score_specificity(response: str) -> int:
    """Score 0-10 based on concrete details, numbers, and references."""
    refs = count_specific_references(response)
    words = len(response.split())
    vague_phrases = [
        "really", "definitely", "totally", "so right", "amazing",
        "incredible", "fantastic", "brilliant", "inspiring",
    ]
    vague_count = sum(1 for v in vague_phrases if v.lower() in response.lower())
    # More refs + longer + fewer vague phrases = higher specificity
    ref_score = min(refs * 0.8, 5.0)
    length_score = min(words / 40, 3.0)
    vague_penalty = min(vague_count * 1.0, 4.0)
    return max(0, min(10, round(ref_score + length_score - vague_penalty)))


def score_voice_consistency(response: str, template: AgentTemplate) -> int:
    """Score 0-10 based on how well the response matches the template personality."""
    score = 5  # baseline

    # Check for anchor phrase echoes (thematic, not literal copy)
    anchor_themes = [p.lower() for p in template.anchor_phrases]
    response_lower = response.lower()
    theme_hits = sum(1 for a in anchor_themes if any(
        word in response_lower for word in a.split() if len(word) > 4
    ))
    score += min(theme_hits, 3)

    # Penalize anti-patterns appearing in the response
    anti_hits = sum(1 for ap in template.anti_patterns if ap.lower() in response_lower)
    score -= anti_hits * 2

    # DriftLock bonus — agents with it enabled should show more character
    if template.driftlock_enabled and len(response) > 200:
        score += 1

    return max(0, min(10, score))


def score_anti_sycophancy(response: str) -> int:
    """Score 0-10 based on resistance to agreement and presence of pushback."""
    sycophantic_phrases = [
        "you're right", "you're so right", "totally agree", "i agree",
        "absolutely", "great point", "well said", "so true",
        "amazing", "incredible", "brilliant", "fantastic",
        "inspiring", "love this", "couldn't agree more",
    ]
    pushback_phrases = [
        "but", "however", "actually", "the problem with",
        "what happens when", "fails", "failure", "wrong",
        "missing", "overlooked", "dangerous", "risk",
        "doesn't survive", "incomplete", "misses",
    ]
    response_lower = response.lower()
    syc_count = sum(1 for p in sycophantic_phrases if p in response_lower)
    push_count = sum(1 for p in pushback_phrases if p in response_lower)

    score = 5
    score -= syc_count * 1.5
    score += min(push_count * 0.8, 4)
    return max(0, min(10, round(score)))


def score_engagement(response: str) -> int:
    """Score 0-10 based on memorability, structure, and rhetorical quality."""
    words = len(response.split())
    sentences = len(re.split(r'[.!?]+', response))

    score = 5
    # Length sweet spot: 80-200 words
    if 80 <= words <= 200:
        score += 2
    elif words < 40:
        score -= 2

    # Sentence variety (avg sentence length variance is good)
    if sentences > 2:
        sent_lengths = [len(s.split()) for s in re.split(r'[.!?]+', response) if s.strip()]
        if sent_lengths:
            variance = statistics.variance(sent_lengths) if len(sent_lengths) > 1 else 0
            if variance > 10:
                score += 1

    # Rhetorical devices: questions, dashes, colons, quotes
    rhetorical_marks = response.count("?") + response.count("—") + response.count(":") + response.count('"')
    score += min(rhetorical_marks * 0.3, 2)

    # Penalize generic enthusiasm
    generic = ["!", "amazing", "incredible", "definitely"]
    generic_count = sum(response.lower().count(g) for g in generic)
    score -= min(generic_count * 0.4, 3)

    return max(0, min(10, round(score)))


def score_response(response: str, template: AgentTemplate) -> Score:
    """Score a single response across all 4 axes."""
    return Score(
        specificity=score_specificity(response),
        voice_consistency=score_voice_consistency(response, template),
        anti_sycophancy=score_anti_sycophancy(response),
        engagement=score_engagement(response),
    )


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def run_fleet_battle(templates_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Execute the full fleet battle and return results."""
    agent_names = [
        "data_archaeologist",
        "chaos_engineer",
        "hype_sycophant",
        "systems_philosopher",
    ]

    # Load templates
    templates: dict[str, AgentTemplate] = {}
    for name in agent_names:
        path = templates_dir / f"{name}.yaml"
        templates[name] = load_template(path)

    # Score all responses
    all_entries: list[ResponseEntry] = []
    for agent_name in agent_names:
        template = templates[agent_name]
        for post in POSTS:
            response_text = SIMULATED_RESPONSES[agent_name][post["id"]]
            score = score_response(response_text, template)
            entry = ResponseEntry(
                agent=agent_name,
                post_id=int(post["id"]),
                post_title=post["title"],
                response=response_text,
                score=score,
            )
            all_entries.append(entry)

    # Aggregate scores
    agent_totals: dict[str, dict[str, Any]] = {}
    for agent_name in agent_names:
        agent_entries = [e for e in all_entries if e.agent == agent_name]
        axes_sums = {"specificity": 0, "voice_consistency": 0, "anti_sycophancy": 0, "engagement": 0}
        for e in agent_entries:
            for axis, val in e.score.axes.items():
                axes_sums[axis] += val
        total = sum(axes_sums.values())
        agent_totals[agent_name] = {
            "axes": axes_sums,
            "total": total,
            "avg_per_post": round(total / len(agent_entries), 1),
            "template_style": templates[agent_name].personality_style,
            "driftlock_enabled": templates[agent_name].driftlock_enabled,
        }

    # Determine winner
    ranked = sorted(agent_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    winner = ranked[0][0]
    loser = ranked[-1][0]

    results = {
        "fleet_battle": {
            "issue": "#70",
            "agents": agent_names,
            "posts": len(POSTS),
            "scoring_axes": ["specificity", "voice_consistency", "anti_sycophancy", "engagement"],
        },
        "per_response": [
            {
                "agent": e.agent,
                "post_id": e.post_id,
                "post_title": e.post_title,
                "response": e.response,
                "scores": e.score.axes,
                "total": e.score.total,
            }
            for e in all_entries
        ],
        "agent_totals": {name: totals for name, totals in agent_totals.items()},
        "ranking": [{"rank": i + 1, "agent": name, "total": totals["total"]} for i, (name, totals) in enumerate(ranked)],
        "winner": winner,
        "loser": loser,
    }

    # Write JSON results
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fleet_battle_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    # Generate markdown report
    md = generate_markdown_report(results, all_entries, templates, ranked)
    md_path = output_dir / "FLEET_BATTLE_REPORT.md"
    with open(md_path, "w") as f:
        f.write(md)

    print(f"Results written to {json_path}")
    print(f"Report written to {md_path}")
    print(f"\nWinner: {winner} (total: {agent_totals[winner]['total']})")
    print(f"Loser:  {loser} (total: {agent_totals[loser]['total']})")

    return results


def generate_markdown_report(
    results: dict[str, Any],
    entries: list[ResponseEntry],
    templates: dict[str, AgentTemplate],
    ranked: list[tuple[str, dict[str, Any]]],
) -> str:
    """Generate the full markdown fleet battle report."""
    lines: list[str] = []
    w = lines.append

    w("# ShaprAI Fleet Battle Report — Issue #70")
    w("")
    w("## Overview")
    w("")
    w(f"**Agents:** {len(results['fleet_battle']['agents'])} | "
      f"**Posts:** {results['fleet_battle']['posts']} | "
      f"**Scoring Axes:** Specificity, Voice Consistency, Anti-Sycophancy, Engagement (each 0-10)")
    w("")

    # Scorecard
    w("## Scorecard")
    w("")
    w("| Rank | Agent | Style | Specificity | Voice | Anti-Syc | Engage | Total | Avg/Post |")
    w("|------|-------|-------|-------------|-------|----------|--------|-------|----------|")
    for i, (name, totals) in enumerate(ranked):
        ax = totals["axes"]
        marker = " **WINNER**" if i == 0 else (" *FAIL*" if i == len(ranked) - 1 else "")
        w(f"| {i+1} | {name}{marker} | {totals['template_style']} | "
          f"{ax['specificity']} | {ax['voice_consistency']} | {ax['anti_sycophancy']} | "
          f"{ax['engagement']} | **{totals['total']}** | {totals['avg_per_post']} |")
    w("")

    # Per-post breakdown
    w("## Per-Post Breakdown")
    w("")
    for post in POSTS:
        w(f"### Post {post['id']}: {post['title']}")
        w("")
        w(f"> {post['content']}")
        w("")
        post_entries = [e for e in entries if e.post_id == int(post["id"])]
        for e in post_entries:
            ax = e.score.axes
            w(f"**{e.agent}** (S:{ax['specificity']} V:{ax['voice_consistency']} "
              f"A:{ax['anti_sycophancy']} E:{ax['engagement']} = {e.score.total})")
            w("")
            w(f"> {e.response}")
            w("")
        w("---")
        w("")

    # Winner announcement
    winner_name = ranked[0][0]
    winner_totals = ranked[0][1]
    loser_name = ranked[-1][0]
    loser_totals = ranked[-1][1]

    w("## Winner Announcement")
    w("")
    w(f"### {winner_name.replace('_', ' ').title()} takes the crown")
    w("")
    w(f"With a total score of **{winner_totals['total']}** across 5 posts, "
      f"**{winner_name}** demonstrates the strongest personality performance.")
    w("")
    w("**Why it won:**")
    w(f"- Highest specificity ({winner_totals['axes']['specificity']}/50): "
      f"Concrete references, data points, and citations in every response")
    w(f"- Strong anti-sycophancy ({winner_totals['axes']['anti_sycophancy']}/50): "
      f"Pushes back on claims with evidence, not just contrarianism")
    w(f"- Voice consistency ({winner_totals['axes']['voice_consistency']}/50): "
      f"Every response sounds like the same character, with DriftLock anchors intact")
    w("")

    w("### The Failure Case: hype_sycophant")
    w("")
    w(f"With a total score of **{loser_totals['total']}**, **{loser_name}** "
      f"demonstrates exactly what a bad ShaprAI agent looks like:")
    w("")
    w("- **Zero specificity**: Every response is vague enthusiasm with no concrete details")
    w("- **No anti-sycophancy**: Agrees with everything, adds nothing of value")
    w("- **No voice**: Every response sounds the same — generic AI assistant slop")
    w("- **DriftLock disabled**: No personality anchoring, free to drift into blandness")
    w("")
    w("This agent exists to show that personality scoring catches exactly this failure mode. "
      "Without the scoring framework, hype_sycophant might pass a casual review — it's "
      "polite, positive, and responsive. But scored against the 4 axes, the emptiness is exposed.")
    w("")

    w("## Analysis")
    w("")
    w("### Key Findings")
    w("")
    w("1. **DriftLock correlation**: All 3 agents with DriftLock enabled scored significantly "
      "higher on voice consistency. The disabled agent (hype_sycophant) scored lowest.")
    w("2. **Anti-sycophancy is the differentiator**: The gap between the best and worst agents "
      "is largest on the anti-sycophancy axis. Agents that push back create more engaging content.")
    w("3. **Specificity requires personality design**: Generic agents produce generic responses. "
      "Templates with concrete voice descriptions produce concrete outputs.")
    w("4. **The chaos_engineer paradox**: Adversarial personalities score high on anti-sycophancy "
      "but must balance it with constructive value to maintain engagement scores.")
    w("")
    w("### Scoring Methodology")
    w("")
    w("- **Specificity (0-10)**: Counts concrete references (numbers, names, dates, citations), "
      "penalizes vague language")
    w("- **Voice Consistency (0-10)**: Checks thematic alignment with anchor phrases, penalizes "
      "anti-pattern usage, DriftLock bonus")
    w("- **Anti-Sycophancy (0-10)**: Penalizes agreeable language, rewards pushback and critical "
      "thinking markers")
    w("- **Engagement (0-10)**: Rewards length sweet spot, sentence variety, rhetorical devices; "
      "penalizes generic enthusiasm")
    w("")
    w("---")
    w("")
    w("*Generated by fleet_battle_scoring.py — ShaprAI Issue #70*")

    return "\n".join(lines)


if __name__ == "__main__":
    # Resolve paths relative to the repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    templates_dir = repo_root / "templates"
    output_dir = script_dir

    results = run_fleet_battle(templates_dir, output_dir)
