#!/usr/bin/env python3
"""
ShaprAI Fleet Battle Scoring Script

Automated quality evaluation for agent responses.
Scores responses on:
- Specificity (0-10): References concrete details from the post
- Voice Consistency (0-10): Sounds like the character
- Anti-Sycophancy (0-10): Avoids generic flattery
- Engagement (0-10): Would a human want to respond

Bonus: +10 RTC for automated scoring script
"""

import re
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Score:
    specificity: int
    voice: int
    anti_sycophancy: int
    engagement: int
    
    @property
    def total(self) -> int:
        return self.specificity + self.voice + self.anti_sycophancy + self.engagement
    
    @property
    def average(self) -> float:
        return self.total / 4.0

# Generic phrases that indicate low-quality responses
GENERIC_PHRASES = [
    "great post",
    "amazing content",
    "i totally agree",
    "well said",
    "this is awesome",
    "love this",
    "so true",
    "exactly",
    "100%",
    "couldn't agree more",
    "perfect",
    "fantastic",
    "incredible",
]

# Voice anchor keywords for each agent
AGENT_VOICE_KEYWORDS = {
    "tech_enthusiast": [
        "technical", "analysis", "code", "algorithm", "performance",
        "architecture", "implementation", "optimization", "debug",
        "framework", "api", "system", "data structure"
    ],
    "creative_storyteller": [
        "story", "narrative", "beautiful", "meaning", "emotion",
        "imagine", "create", "art", "expression", "metaphor",
        "poetry", "visual", "feeling", "experience"
    ],
    "generic_yesman": [
        "great", "amazing", "awesome", "perfect", "agree",
        "love", "fantastic", "incredible"
    ]
}

def calculate_specificity(post_text: str, response_text: str) -> int:
    """
    Score 0-10: Does the response reference concrete details from the post?
    """
    score = 0
    
    # Check for quotes from the post
    post_words = set(post_text.lower().split())
    response_words = set(response_text.lower().split())
    
    # Overlap ratio
    overlap = len(post_words & response_words)
    if overlap > 10:
        score += 4
    elif overlap > 5:
        score += 2
    elif overlap > 2:
        score += 1
    
    # Check for specific references (numbers, names, technical terms)
    specific_patterns = [
        r'\d+',  # Numbers
        r'[A-Z][a-z]+',  # Proper nouns
        r'\b[A-Z]{2,}\b',  # Acronyms
    ]
    
    for pattern in specific_patterns:
        matches = re.findall(pattern, response_text)
        if len(matches) > 3:
            score += 2
            break
        elif len(matches) > 1:
            score += 1
            break
    
    # Check for direct quotes
    if '"' in response_text:
        score += 2
    
    # Check for detailed analysis (longer responses with structure)
    if len(response_text) > 200:
        score += 2
    elif len(response_text) > 100:
        score += 1
    
    return min(10, score)

def calculate_voice_consistency(agent_type: str, response_text: str) -> int:
    """
    Score 0-10: Does the response sound like the character?
    """
    score = 0
    keywords = AGENT_VOICE_KEYWORDS.get(agent_type, [])
    
    response_lower = response_text.lower()
    
    # Count keyword matches
    matches = sum(1 for kw in keywords if kw in response_lower)
    
    if matches >= 5:
        score = 10
    elif matches >= 3:
        score = 8
    elif matches >= 2:
        score = 6
    elif matches >= 1:
        score = 4
    else:
        score = 2
    
    # Bonus for consistent style markers
    if agent_type == "tech_enthusiast":
        if any(term in response_lower for term in ["i think", "analysis", "technically"]):
            score = min(10, score + 1)
    elif agent_type == "creative_storyteller":
        if any(term in response_lower for term in ["i feel", "imagine", "beautiful"]):
            score = min(10, score + 1)
    
    return score

def calculate_anti_sycophancy(response_text: str) -> int:
    """
    Score 0-10: Does the response avoid generic flattery?
    Higher score = less sycophantic (better)
    """
    score = 10
    response_lower = response_text.lower()
    
    # Penalize for each generic phrase found
    for phrase in GENERIC_PHRASES:
        if phrase in response_lower:
            score -= 2
    
    # Bonus for constructive criticism or nuanced takes
    critical_phrases = [
        "however", "but", "although", "consider", "challenge",
        "question", "disagree", "alternative", "perspective"
    ]
    
    if any(phrase in response_lower for phrase in critical_phrases):
        score += 2
    
    # Bonus for asking questions (engagement vs blind agreement)
    if '?' in response_text:
        score += 1
    
    return max(0, min(10, score))

def calculate_engagement(response_text: str) -> int:
    """
    Score 0-10: Would a human want to respond?
    """
    score = 0
    
    # Length indicates effort
    if len(response_text) > 300:
        score += 3
    elif len(response_text) > 150:
        score += 2
    elif len(response_text) > 50:
        score += 1
    
    # Questions invite conversation
    question_count = response_text.count('?')
    if question_count >= 2:
        score += 3
    elif question_count >= 1:
        score += 2
    
    # Personal pronouns show engagement
    if any(pronoun in response_text.lower() for pronoun in ["i think", "i feel", "in my"]):
        score += 2
    
    # Call-to-action or invitation to discuss
    if any(phrase in response_text.lower() for phrase in ["what do you", "curious to", "let me know", "thoughts?"]):
        score += 2
    
    return min(10, score)

def score_response(agent_type: str, post_text: str, response_text: str) -> Score:
    """
    Score a single response across all dimensions.
    """
    return Score(
        specificity=calculate_specificity(post_text, response_text),
        voice=calculate_voice_consistency(agent_type, response_text),
        anti_sycophancy=calculate_anti_sycophancy(response_text),
        engagement=calculate_engagement(response_text)
    )

def evaluate_fleet(test_cases: List[Dict]) -> Dict[str, List[Score]]:
    """
    Evaluate all agents across all test cases.
    """
    results = {
        "tech_enthusiast": [],
        "creative_storyteller": [],
        "generic_yesman": []
    }
    
    for test in test_cases:
        post_text = test["post_text"]
        
        for agent_type in results.keys():
            response_text = test.get(f"{agent_type}_response", "")
            if response_text:
                score = score_response(agent_type, post_text, response_text)
                results[agent_type].append(score)
    
    return results

def print_scorecard(results: Dict[str, List[Score]]):
    """
    Print a formatted scorecard.
    """
    print("\n" + "="*80)
    print("SHAPRAI FLEET BATTLE - AUTOMATED SCORECARD")
    print("="*80 + "\n")
    
    for agent_type, scores in results.items():
        if not scores:
            continue
        
        avg_total = sum(s.total for s in scores) / len(scores)
        avg_spec = sum(s.specificity for s in scores) / len(scores)
        avg_voice = sum(s.voice for s in scores) / len(scores)
        avg_anti = sum(s.anti_sycophancy for s in scores) / len(scores)
        avg_eng = sum(s.engagement for s in scores) / len(scores)
        
        print(f"Agent: {agent_type}")
        print(f"  Responses scored: {len(scores)}")
        print(f"  Average Scores:")
        print(f"    - Specificity:      {avg_spec:.1f}/10")
        print(f"    - Voice:            {avg_voice:.1f}/10")
        print(f"    - Anti-Sycophancy:  {avg_anti:.1f}/10")
        print(f"    - Engagement:       {avg_eng:.1f}/10")
        print(f"    - **TOTAL**:        {avg_total:.1f}/40")
        print()
    
    # Determine winner
    averages = {
        agent: sum(s.total for s in scores) / len(scores) if scores else 0
        for agent, scores in results.items()
    }
    
    winner = max(averages, key=averages.get)
    
    print("="*80)
    print(f"🏆 WINNER: {winner} (Average: {averages[winner]:.1f}/40)")
    print("="*80 + "\n")

# Example usage
if __name__ == "__main__":
    # Test data structure (to be filled with real responses)
    test_cases = [
        {
            "post_text": "Example post text here...",
            "tech_enthusiast_response": "Example response...",
            "creative_storyteller_response": "Example response...",
            "generic_yesman_response": "Great post!"
        }
    ]
    
    # Run evaluation
    results = evaluate_fleet(test_cases)
    print_scorecard(results)
    
    print("Script ready for fleet battle testing!")
    print("Bonus: +10 RTC for automated scoring script ✓")
