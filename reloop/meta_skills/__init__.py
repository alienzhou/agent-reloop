"""Meta Skills — 框架内置的生成器 Skills。

Meta Skills 在初始化阶段使用，帮助用户定义任务目标和评估标准：
- INTENT Builder: 澄清任务目标，生成 INTENT.md
- Evaluator Builder: 交互式定义评估标准，生成 EVAL_SKILL.md
- Mocker: 生成 Mock solution，验证 Evaluator 逻辑
"""

from pathlib import Path

META_SKILLS_DIR = Path(__file__).parent


def get_skill_path(skill_name: str) -> Path:
    """获取 Meta Skill 文件路径。

    Args:
        skill_name: Skill 名称 (intent_builder/evaluator_builder/mocker)

    Returns:
        Skill 文件的 Path 对象
    """
    return META_SKILLS_DIR / f"{skill_name}.md"


__all__ = ["META_SKILLS_DIR", "get_skill_path"]
