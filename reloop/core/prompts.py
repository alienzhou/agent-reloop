"""Prompt 构建器 — 为迭代循环的三个角色组装 prompt"""

from __future__ import annotations

from typing import Optional


def build_executor_prompt(
    intent: str,
    last_eval_result: Optional[str],
    exec_spec: str,
) -> str:
    """构建 executor 的 prompt。

    将 INTENT、上一轮评估结果（如有）、执行规范内联组装为完整 prompt。
    """
    sections = [
        "# Task Intent\n\n" + intent,
        "# Execution Spec\n\n" + exec_spec,
    ]

    if last_eval_result:
        sections.insert(
            1,
            "# Previous Evaluation Result\n\n"
            "Fix the issues identified in the last round:\n\n"
            + last_eval_result,
        )

    return "\n\n---\n\n".join(sections)


def build_evaluator_prompt(
    artifacts_dir: str,
    eval_skill: str,
) -> str:
    """构建 evaluator 的 prompt。

    将 artifacts 路径和 evaluator Skill 内容内联组装。
    """
    return (
        "# Evaluation Skill\n\n"
        + eval_skill
        + "\n\n---\n\n"
        + "# Artifacts to Evaluate\n\n"
        + f"Artifacts directory: {artifacts_dir}\n\n"
        + "Evaluate the artifacts according to the skill above. "
        + "Run L0, L1, L2 checks in order with short-circuit logic. "
        + "Write the evaluation report."
    )


def build_checker_prompt(report_path: str) -> str:
    """构建 checker 的 prompt。

    Checker 是通用的、任务无关的——只判断评估报告是否表示通过。
    要求使用 XML 格式输出。

    Args:
        report_path: 评估报告文件的路径，Checker Agent 需要读取此文件
    """
    return (
        "# Evaluation Report Location\n\n"
        + f"Report path: `{report_path}`\n\n"
        + "---\n\n"
        + "# Instructions\n\n"
        + "You are a **task-agnostic binary classifier**. \n\n"
        + "Your job:\n"
        + "1. Read the evaluation report from the path above\n"
        + "2. Determine if it indicates overall success or failure\n"
        + "3. Output your decision in XML format\n\n"
        + "You do NOT need to:\n"
        + "- Understand the specific task\n"
        + "- Evaluate the solution yourself\n"
        + "- Agree with the evaluator's judgment\n\n"
        + "Decision rules:\n"
        + "- Look for explicit conclusion signals: \"Overall:\", \"Result:\", \"Final:\", \"Verdict:\"\n"
        + "- Look for pass/fail keywords in the conclusion section\n"
        + "- If unclear, default to \"failed\" (conservative)\n\n"
        + "Output format (mandatory):\n"
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
        + "- The ONLY required output\n"
    )
