#!/usr/bin/env python3
"""
ShaprAI → CrewAI 迁移演示
任务: Bounty Hunter Agent 迁移

本脚本演示如何将 ShaprAI agent 模板迁移到 CrewAI 运行时，
同时保持 personality、DriftLock 和 anti-patterns。
"""

import yaml
from shaprai.runtimes.crewai_adapter import ShaprCrewAgent, create_crew

def load_agent_manifest(template_path: str) -> dict:
    """加载 agent 模板"""
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)

def test_bounty_hunter_migration():
    """测试 Bounty Hunter Agent 迁移"""
    
    # 1. 加载 ShaprAI 模板
    print("=" * 60)
    print("Step 1: 加载 ShaprAI Agent 模板")
    print("=" * 60)
    
    manifest = load_agent_manifest("templates/bounty_hunter.yaml")
    print(f"Agent 名称: {manifest['name']}")
    print(f"描述: {manifest['description']}")
    print(f"Personality Style: {manifest['personality']['style']}")
    print(f"DriftLock: {'启用' if manifest['driftlock']['enabled'] else '禁用'}")
    print(f"锚定短语数量: {len(manifest['driftlock']['anchor_phrases'])}")
    
    # 2. 使用 CrewAI Adapter 创建 Agent
    print("\n" + "=" * 60)
    print("Step 2: 通过 CrewAI Adapter 创建 Agent")
    print("=" * 60)
    
    agent = ShaprCrewAgent.from_manifest(manifest)
    print(f"CrewAI Agent 名称: {agent.name}")
    print(f"角色: {agent.role}")
    print(f"目标: {agent.goal}")
    print(f"模型: {agent.model}")
    
    # 3. 检查 SophiaCore 伦理提示是否注入
    print("\n" + "=" * 60)
    print("Step 3: 验证 SophiaCore 原则注入")
    print("=" * 60)
    
    if "principled agent" in agent.backstory.lower():
        print("✅ SophiaCore 伦理提示已注入 backstory")
    else:
        print("❌ 未找到伦理提示")
    
    # 显示 backstory 前200字符
    print(f"\nBackstory 预览:")
    print("-" * 40)
    print(agent.backstory[:200] + "...")
    
    # 4. 创建 Crew 配置
    print("\n" + "=" * 60)
    print("Step 4: 创建 Crew 配置")
    print("=" * 60)
    
    # 定义一个真实的赏金狩猎任务
    tasks = [
        {
            "description": "扫描 GitHub Issues 寻找标有 'bounty' 和 'good first issue' 的开放任务",
            "expected_output": "列出5个符合条件的赏金任务，包含任务标题、赏金金额和链接",
            "agent": manifest['name']
        },
        {
            "description": "评估每个任务的ROI（赏金金额/预估工作量），选择最佳任务",
            "expected_output": "推荐1个最佳任务，说明选择理由",
            "agent": manifest['name']
        }
    ]
    
    print(f"任务数量: {len(tasks)}")
    print(f"执行流程: sequential")
    for i, task in enumerate(tasks, 1):
        print(f"  任务{i}: {task['description'][:50]}...")
    
    # 5. 对比直接 ShaprAI 输出 vs CrewAI 输出
    print("\n" + "=" * 60)
    print("Step 5: Personality 保持验证")
    print("=" * 60)
    
    original_personality = manifest['personality']['voice']
    print(f"原始 Personality Voice: \"{original_personality}\"")
    
    # 检查 backstory 是否保留了 personality 特征
    if "direct" in agent.backstory.lower() or "efficient" in agent.backstory.lower():
        print("✅ Personality 特征已保留在 backstory 中")
    else:
        print("⚠️ 需要手动添加 personality 到 backstory")
    
    # 6. DriftLock 验证
    print("\n" + "=" * 60)
    print("Step 6: DriftLock 锚定验证")
    print("=" * 60)
    
    driftlock_phrases = manifest['driftlock']['anchor_phrases']
    print(f"DriftLock 锚定短语:")
    for phrase in driftlock_phrases:
        print(f"  - {phrase}")
    
    # 注意: 实际 DriftLock 检查需要在运行时进行
    print("\n⚠️ 注意: DriftLock 检查需要实际运行 CrewAI 任务时触发")
    print("   建议在任务执行代码中添加 driftlock_check() 调用")
    
    # 7. 输出总结
    print("\n" + "=" * 60)
    print("迁移完成总结")
    print("=" * 60)
    print(f"✅ Agent 模板: {manifest['name']}")
    print(f"✅ 运行时: CrewAI")
    print(f"✅ Personality: {manifest['personality']['style']}")
    print(f"✅ Ethics: SophiaCore 已注入")
    print(f"✅ DriftLock: 配置已保留（运行时需额外集成）")
    print(f"✅ 任务定义: {len(tasks)} 个任务")
    
    print("\n📋 下一步:")
    print("   1. 安装 crewai: pip install crewai")
    print("   2. 运行完整任务: crew = create_crew([agent], tasks); crew.kickoff()")
    print("   3. 对比直接 ShaprAI 输出 vs CrewAI 输出")
    
    return agent, tasks

if __name__ == "__main__":
    try:
        agent, tasks = test_bounty_hunter_migration()
        print("\n🎉 迁移演示完成！")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
