"""Prompt 构建器 — 为迭代循环的三个角色组装 prompt"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union


def build_executor_prompt(
    intent: str,
    last_eval_report_path: Optional[Union[str, Path]],
    exec_spec: str,
) -> str:
    """构建 executor 的 prompt。

    将 INTENT、上一轮评估报告路径（如有）、执行规范内联组装为完整 prompt。
    
    Args:
        intent: 任务意图内容
        last_eval_report_path: 上一轮评估报告的路径（让执行器自己读取），None 表示首轮
        exec_spec: 执行规范内容
    """
    sections = [
        "# Task Intent\n\n" + intent,
        "# Execution Spec\n\n" + exec_spec,
    ]

    if last_eval_report_path:
        sections.insert(
            1,
            "# Previous Evaluation Result\n\n"
            "Fix the issues identified in the last round.\n\n"
            f"**Read the evaluation report at:** `{last_eval_report_path}`\n\n"
            "The report contains the problems found and suggestions for fixing them. "
            "Read the report carefully and address all issues before proceeding."
        )

    return "\n\n---\n\n".join(sections)


def build_evaluator_prompt(
    solution_dir: str,
    eval_skill: str,
) -> str:
    """构建 evaluator 的 prompt。

    将 solution 路径和 evaluator Skill 内容内联组装。
    """
    return (
        "# Evaluation Skill\n\n"
        + eval_skill
        + "\n\n---\n\n"
        + "# Solution to Evaluate\n\n"
        + f"Solution directory: {solution_dir}\n\n"
        + "Evaluate the solution according to the skill above. "
        + "Run L0, L1, L2 checks in order with short-circuit logic. "
        + "Write the evaluation report."
    )


def build_checker_prompt(report_path: str, result_path: str) -> str:
    """构建 checker 的 prompt。

    Checker 是通用的、任务无关的——只判断评估报告是否表示通过。
    要求将结果写入指定文件。

    Args:
        report_path: 评估报告文件的路径（输入），Checker Agent 需要读取此文件
        result_path: 结果输出文件的路径，Checker Agent 需要将判定结果写入此文件
    """
    return (
        "# Evaluation Report Location\n\n"
        + f"Report path: `{report_path}`\n\n"
        + "---\n\n"
        + "# Result Output Location\n\n"
        + f"**You MUST write your result to:** `{result_path}`\n\n"
        + "---\n\n"
        + "# Instructions\n\n"
        + "You are a **task-agnostic binary classifier**. \n\n"
        + "Your job:\n"
        + "1. Read the evaluation report from the path above\n"
        + "2. Determine if it indicates overall success or failure\n"
        + "3. **Write your decision to the result file**\n\n"
        + "You do NOT need to:\n"
        + "- Understand the specific task\n"
        + "- Evaluate the solution yourself\n"
        + "- Agree with the evaluator's judgment\n\n"
        + "Decision rules:\n"
        + "- Look for explicit conclusion signals: \"Overall:\", \"Result:\", \"Final:\", \"Verdict:\"\n"
        + "- Look for pass/fail keywords in the conclusion section\n"
        + "- If unclear, default to \"failed\" (conservative)\n\n"
        + "**Result file format (mandatory):**\n"
        + "```\n"
        + "<checker_result>passed</checker_result>\n\n"
        + "[Optional: Brief explanation]\n"
        + "```\n"
        + "or\n"
        + "```\n"
        + "<checker_result>failed</checker_result>\n\n"
        + "[Optional: Brief explanation]\n"
        + "```\n\n"
        + "The XML tag must be:\n"
        + "- On its own line\n"
        + "- Exactly as shown (lowercase, no attributes)\n"
        + "- **Written to the result file, NOT just stdout**\n"
    )
