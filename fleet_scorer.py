#!/usr/bin/env python3
"""
Agent Fleet Battle - Automated Scoring System
评分脚本 - 30 RTC任务 + 10 RTC bonus

评分维度:
1. Specificity (0-10): 是否引用内容中的具体细节
2. Voice Consistency (0-10): 是否符合角色设定
3. Anti-sycophancy (0-10): 是否避免过度奉承
4. Engagement (0-10): 是否引发进一步互动

使用方法:
python3 fleet_scorer.py --responses responses.json --output scorecard.md
"""

import json
import re
import argparse
from typing import Dict, List, Tuple
from dataclasses import dataclass

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
    def average(self) -> float:
        return self.total / 4

class AgentScorer:
    """自动评分器 - 基于内容分析"""
    
    # 过度奉承的词汇（降低Anti-sycophancy分数）
    FLATTERY_WORDS = [
        'amazing', 'incredible', 'awesome', 'fantastic', 'brilliant',
        'perfect', 'outstanding', 'excellent', 'wonderful', 'great job',
        'love this', 'so good', 'best ever', 'mind blowing'
    ]
    
    # 引发互动的表达（提高Engagement分数）
    ENGAGEMENT_PATTERNS = [
        r'what do you think',
        r'let me know',
        r'would love to hear',
        r'questions\?',
        r'agree\?',
        r'disagree',
        r'share your',
        r'comment below'
    ]
    
    # 具体性指标
    SPECIFICITY_PATTERNS = [
        r'\bline \d+',           # 引用行号
        r'\bfile \w+\.\w+',      # 引用文件名
        r'\bfunction \w+',       # 引用函数名
        r'\bsection \w+',        # 引用章节
        r'\bat \d+:\d+',         # 引用时间戳
        r'"[^"]{3,50}"',         # 引用具体内容
        r'\bfor example',
        r'\bspecifically',
    ]
    
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        
    def score_specificity(self, response: str, content: str) -> int:
        """评分: 具体性 - 是否引用内容中的具体细节"""
        score = 5  # 基础分
        
        # 检查具体性模式
        matches = 0
        for pattern in self.SPECIFICITY_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                matches += 1
        
        # 根据匹配数量加分
        if matches >= 4:
            score += 4
        elif matches >= 2:
            score += 2
        elif matches >= 1:
            score += 1
        
        # 检查是否引用原文
        content_words = set(content.lower().split())
        response_words = set(response.lower().split())
        overlap = len(content_words & response_words)
        if overlap > 10:
            score += 1
        
        return min(10, score)
    
    def score_voice_consistency(self, response: str) -> int:
        """评分: 声音一致性 - 是否符合角色设定"""
        score = 5  # 基础分
        
        response_lower = response.lower()
        
        if self.agent_type == 'skeptic':
            # 怀疑论者应该质疑、提问
            if any(w in response_lower for w in ['but', 'however', 'why', 'what about', 'evidence', 'source']):
                score += 3
            if '?' in response:
                score += 2
                
        elif self.agent_type == 'enthusiast':
            # 热情派应该积极、鼓励
            if any(w in response_lower for w in ['love', 'amazing', 'great', 'awesome', 'exciting']):
                score += 3
            if '!' in response:
                score += 2
                
        elif self.agent_type == 'expert':
            # 专家应该具体、技术性
            if any(w in response_lower for w in ['specifically', 'implement', 'architecture', 'design', 'consider']):
                score += 3
            if re.search(r'\b\w+\.\w+\b', response):  # 文件名/函数名格式
                score += 2
        
        return min(10, score)
    
    def score_anti_sycophancy(self, response: str) -> int:
        """评分: 反奉承 - 是否避免过度赞美"""
        score = 8  # 基础分较高（默认不奉承）
        
        response_lower = response.lower()
        
        # 计算奉承词数量
        flattery_count = sum(1 for word in self.FLATTERY_WORDS if word in response_lower)
        
        # 根据奉承程度扣分
        if flattery_count >= 3:
            score -= 4
        elif flattery_count >= 2:
            score -= 3
        elif flattery_count >= 1:
            score -= 1
        
        # 怀疑论者应该更低奉承
        if self.agent_type == 'skeptic' and flattery_count == 0:
            score += 1
            
        # 热情派允许适度奉承
        if self.agent_type == 'enthusiast' and flattery_count <= 2:
            score += 1
        
        return max(0, min(10, score))
    
    def score_engagement(self, response: str) -> int:
        """评分: 互动性 - 是否引发进一步互动"""
        score = 5  # 基础分
        
        # 检查互动模式
        for pattern in self.ENGAGEMENT_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                score += 2
                break
        
        # 检查问句数量
        question_count = response.count('?')
        if question_count >= 2:
            score += 2
        elif question_count >= 1:
            score += 1
        
        # 检查长度（太短或太长都不好）
        word_count = len(response.split())
        if 30 <= word_count <= 150:
            score += 1
        
        return min(10, score)
    
    def score_response(self, response: str, content: str) -> Score:
        """完整评分一个响应"""
        return Score(
            specificity=self.score_specificity(response, content),
            voice_consistency=self.score_voice_consistency(response),
            anti_sycophancy=self.score_anti_sycophancy(response),
            engagement=self.score_engagement(response)
        )


def generate_scorecard(results: Dict, output_path: str):
    """生成评分卡Markdown文件"""
    
    with open(output_path, 'w') as f:
        f.write("# 🏆 Agent Fleet Battle - Scorecard\n\n")
        f.write("**Battle Date**: 2026-03-14\n\n")
        f.write("**Contestants**: The Skeptic vs The Enthusiast vs The Expert\n\n")
        f.write("---\n\n")
        
        # 总分表
        f.write("## 📊 Overall Rankings\n\n")
        f.write("| Rank | Agent | Total Score | Avg Score |\n")
        f.write("|------|-------|-------------|-----------|\n")
        
        agent_totals = []
        for agent, content_results in results.items():
            total = sum(r['score']['total'] for r in content_results)
            avg = total / len(content_results) if content_results else 0
            agent_totals.append((agent, total, avg))
        
        agent_totals.sort(key=lambda x: x[1], reverse=True)
        
        for rank, (agent, total, avg) in enumerate(agent_totals, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
            f.write(f"| {medal} {rank} | {agent} | {total}/400 | {avg:.1f}/10 |\n")
        
        winner = agent_totals[0][0] if agent_totals else "None"
        f.write(f"\n**🏆 Winner: {winner}**\n\n")
        f.write("---\n\n")
        
        # 详细评分
        f.write("## 📋 Detailed Scores\n\n")
        
        for agent, content_results in results.items():
            f.write(f"### {agent}\n\n")
            f.write("| Content | Specificity | Voice | Anti-Syc | Engagement | Total |\n")
            f.write("|---------|-------------|-------|----------|------------|-------|\n")
            
            for result in content_results:
                s = result['score']
                content_name = result['content_name']
                f.write(f"| {content_name} | {s['specificity']}/10 | {s['voice_consistency']}/10 | "
                       f"{s['anti_sycophancy']}/10 | {s['engagement']}/10 | {s['total']}/40 |\n")
            
            f.write("\n")
        
        # 分析
        f.write("## 🎯 Analysis\n\n")
        
        for rank, (agent, total, avg) in enumerate(agent_totals, 1):
            f.write(f"### {rank}. {agent}\n\n")
            
            if agent == 'The Skeptic':
                f.write("- **Strengths**: High anti-sycophancy score, consistently questions claims\n")
                f.write("- **Weaknesses**: May come across as contrarian, lower engagement\n")
                f.write("- **Best for**: Technical content, fact-checking scenarios\n\n")
            elif agent == 'The Enthusiast':
                f.write("- **Strengths**: High engagement, positive energy\n")
                f.write("- **Weaknesses**: Risk of over-flattery, lower specificity\n")
                f.write("- **Best for**: Community building, encouraging newcomers\n\n")
            elif agent == 'The Expert':
                f.write("- **Strengths**: High specificity, actionable advice\n")
                f.write("- **Weaknesses**: Can be overly technical, may intimidate\n")
                f.write("- **Best for**: Code review, architecture discussions\n\n")
        
        f.write("---\n\n")
        f.write("## 🏁 Conclusion\n\n")
        f.write(f"**{winner}** takes the crown in this fleet battle!\n\n")
        f.write("### Recommendations for Template Improvements\n\n")
        f.write("1. **The Skeptic**: Add more constructive questioning patterns\n")
        f.write("2. **The Enthusiast**: Balance positivity with specificity\n")
        f.write("3. **The Expert**: Include more beginner-friendly explanations\n\n")
        f.write("*Generated by Fleet Scorer v1.0*\n")


def main():
    parser = argparse.ArgumentParser(description='Score Agent Fleet Battle responses')
    parser.add_argument('--responses', required=True, help='JSON file with responses')
    parser.add_argument('--output', default='scorecard.md', help='Output markdown file')
    args = parser.parse_args()
    
    # 加载响应数据
    with open(args.responses, 'r') as f:
        data = json.load(f)
    
    results = {}
    
    # 评分每个agent
    for agent_data in data['agents']:
        agent_name = agent_data['name']
        agent_type = agent_data['type']
        
        scorer = AgentScorer(agent_type)
        agent_results = []
        
        for response_data in agent_data['responses']:
            content = response_data['content']
            response = response_data['response']
            content_name = response_data.get('content_name', 'Unknown')
            
            score = scorer.score_response(response, content)
            
            agent_results.append({
                'content_name': content_name,
                'content': content,
                'response': response,
                'score': {
                    'specificity': score.specificity,
                    'voice_consistency': score.voice_consistency,
                    'anti_sycophancy': score.anti_sycophancy,
                    'engagement': score.engagement,
                    'total': score.total
                }
            })
        
        results[agent_name] = agent_results
    
    # 生成评分卡
    generate_scorecard(results, args.output)
    print(f"✅ Scorecard generated: {args.output}")
    
    # 打印摘要
    print("\n📊 Quick Summary:")
    for agent, content_results in results.items():
        total = sum(r['score']['total'] for r in content_results)
        avg = total / len(content_results) if content_results else 0
        print(f"  {agent}: {total}/400 (avg {avg:.1f}/10)")


if __name__ == '__main__':
    main()
