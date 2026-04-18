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


def build_checker_prompt(eval_report: str) -> str:
    """构建 checker 的 prompt。

    Checker 是通用的、任务无关的——只判断评估报告是否表示通过。
    """
    return (
        "# Evaluation Report\n\n"
        + eval_report
        + "\n\n---\n\n"
        + "# Instructions\n\n"
        + "Read the evaluation report above. "
        + "Determine whether the evaluation has passed or failed.\n\n"
        + "Reply with exactly one word:\n"
        + "- `passed` if all checks indicate success\n"
        + "- `failed` if any check indicates failure\n\n"
        + "Do not explain. Just reply `passed` or `failed`."
    )
