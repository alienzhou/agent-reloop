"""Prompt 构建器 — 为迭代循环的三个角色组装 prompt"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# 长轮次干预机制
# ============================================================================

def get_intervention_prompt(round_num: int) -> Optional[str]:
    """根据轮次返回干预提示。
    
    当迭代多轮后，注入干预提示帮助 Executor 打破僵局，
    避免陷入「累加式修补」的局部最优。
    
    Args:
        round_num: 当前轮次（从 1 开始）
    
    Returns:
        干预提示文本，或 None（无需干预）
    
    干预策略：
    - 轮次 1-3: 无干预，正常迭代
    - 轮次 4-5: 轻度提醒，检查方向
    - 轮次 6-7: 中度干预，建议策略调整
    - 轮次 8+:  强干预，建议部分重构
    """
    if round_num < 4:
        return None
    
    if round_num <= 5:
        # 轻度提醒
        return f"""
---

## ⚠️ Progress Check (Round {round_num})

You've been iterating for {round_num} rounds. Please verify:

1. **Are you still aligned with the CORE OBJECTIVE?**
   - Re-read the Task Intent above
   - Check if your recent changes serve the main goal

2. **Are you making real progress, or just patching symptoms?**
   - If the same issues keep appearing, consider the root cause
   - Don't just fix the specific test case — fix the underlying problem
"""
    
    if round_num <= 7:
        # 中度干预
        return f"""
---

## ⚠️ Strategy Review (Round {round_num})

Multiple rounds without success. It's time to step back and think:

1. **Is your current implementation approach fundamentally sound?**
   - Sometimes the architecture/design needs adjustment, not just bug fixes

2. **Should you CHANGE STRATEGY instead of continuing to patch?**
   - If you've been fixing the same category of issues repeatedly, the approach may be wrong

3. **What's the ROOT CAUSE of repeated failures?**
   - Don't treat symptoms — diagnose and fix the disease

Consider writing a brief analysis in your proposal before coding.
"""
    
    # 轮次 8+ 强干预
    return f"""
---

## 🚨 Critical Review (Round {round_num})

After {round_num} rounds, it's time for a SERIOUS RESET:

1. **RE-READ THE INTENT**
   - What is the ACTUAL goal? Not what you think it is, but what it says.
   - Are you solving the right problem?

2. **CONSIDER PARTIAL REWRITE**
   - Keep what works (modules that pass evaluation)
   - REBUILD what doesn't work (don't keep patching)

3. **CHALLENGE YOUR ASSUMPTIONS**
   - Is your technology/framework choice correct?
   - Is your architecture suitable for the requirements?
   - Are there simpler approaches you haven't tried?

4. **DON'T CONTINUE THE SAME APPROACH IF IT'S NOT WORKING**
   - Doing the same thing and expecting different results is not a strategy

Write a detailed proposal explaining what you plan to do differently this round.
"""


# ============================================================================
# Executor Prompt 构建
# ============================================================================

def build_executor_prompt(
    intent: str,
    last_eval_report_path: Optional[Union[str, Path]],
    exec_spec: str,
    round_num: int = 1,
    proposal_output_path: Optional[str] = None,
    history_runs_hint: Optional[str] = None,
    abstract_eval_summary: Optional[str] = None,
) -> str:
    """构建 executor 的 prompt。

    将 INTENT、历史上下文、评估结果、执行规范组装为完整 prompt。
    支持提案机制、报告抽象化和长轮次干预。
    
    Args:
        intent: 任务意图内容（INTENT.md 的内容）
        last_eval_report_path: 上一轮评估报告的路径，None 表示首轮
        exec_spec: 执行规范内容
        round_num: 当前轮次（从 1 开始），用于干预提示
        proposal_output_path: 提案输出路径，Executor 应在执行前写入提案
        history_runs_hint: 历史 run-sets 的路径提示，让 Executor 可以按需查看
        abstract_eval_summary: 抽象化后的评估摘要（可选，用于替代完整报告）
    
    Returns:
        完整的 Executor prompt
    """
    logger.debug(f"Building executor prompt, round={round_num}")
    
    sections: List[str] = []
    
    # 1. INTENT（始终放在最前面，强调核心目标）
    sections.append(
        "# 🎯 CORE OBJECTIVE (NEVER FORGET)\n\n"
        "This is your primary goal. All your actions should serve this objective.\n\n"
        + intent
    )
    
    # 2. 历史上下文提示（如果有）
    if history_runs_hint:
        sections.append(
            "# Historical Context\n\n"
            "Previous proposals and evaluation reports are stored at:\n\n"
            f"{history_runs_hint}\n\n"
            "You can read them if needed to:\n"
            "- Understand past decisions and their outcomes\n"
            "- Avoid repeating failed approaches\n"
            "- Build on successful patterns"
        )
    
    # 3. 上一轮评估结果
    if last_eval_report_path or abstract_eval_summary:
        eval_section = "# Previous Evaluation Result\n\n"
        
        if abstract_eval_summary:
            # 使用抽象化摘要
            eval_section += (
                "Below is an ABSTRACT summary of the last evaluation.\n"
                "It shows pass/fail status but NOT specific issues.\n\n"
                + abstract_eval_summary
            )
        elif last_eval_report_path:
            # 仅提供路径
            eval_section += (
                "Fix the issues identified in the last round.\n\n"
                f"**Read the evaluation report at:** `{last_eval_report_path}`\n\n"
                "The report contains the problems found and suggestions for fixing them. "
                "Read the report carefully and address all issues before proceeding."
            )
        
        sections.append(eval_section)
    
    # 4. 提案要求（如果指定了提案路径）
    if proposal_output_path:
        sections.append(
            "# Your Task This Round\n\n"
            "## Step 1: Write Proposal (REQUIRED)\n\n"
            f"Before coding, you MUST write a proposal to: `{proposal_output_path}`\n\n"
            "Your proposal should include:\n\n"
            "1. **Your understanding of the CORE OBJECTIVE** (in your own words)\n"
            "   - What are you trying to build?\n"
            "   - What are the key requirements?\n\n"
            "2. **Current status assessment**\n"
            "   - What's already done?\n"
            "   - What's missing or broken?\n"
            "   - What did the last evaluation say (if any)?\n\n"
            "3. **Your plan for this round**\n"
            "   - What specific actions will you take?\n"
            "   - What files will you create/modify?\n\n"
            "4. **Direction check**\n"
            "   - Are these actions serving the CORE OBJECTIVE?\n"
            "   - Is there a risk of going off-track?\n\n"
            "## Step 2: Execute\n\n"
            "After writing the proposal, implement your plan."
        )
    
    # 5. 执行规范
    sections.append("# Execution Rules\n\n" + exec_spec)
    
    # 6. 干预提示（根据轮次）
    intervention = get_intervention_prompt(round_num)
    if intervention:
        sections.append(intervention)
    
    # 7. 最终提醒
    sections.append(
        "# ⚠️ REMINDER\n\n"
        "- Your task is to achieve the **CORE OBJECTIVE** above.\n"
        "- The evaluation is just a checkpoint, NOT the final goal.\n"
        "- Do NOT over-optimize for specific test cases at the expense of the core vision.\n"
        "- NEVER read the EVAL_SKILL.md by yourself.\n"
        "- Think about WHY something is failing, not just HOW to make it pass."
    )
    
    return "\n\n---\n\n".join(sections)


def build_evaluator_prompt(
    solution_dir: str,
    eval_skill: str,
    report_output_path: str,
) -> str:
    """构建 evaluator 的 prompt。

    将 solution 路径、evaluator Skill 内容和报告输出路径组装。
    
    Args:
        solution_dir: solution 目录路径
        eval_skill: 评估 Skill 内容
        report_output_path: 评估报告输出文件路径，Evaluator 必须将报告写入此文件
        
    Note:
        调用方需要在执行后检查 report_output_path 文件是否存在。
    """
    logger.debug("Building evaluator prompt")
    return (
        "# Evaluation Skill\n\n"
        + eval_skill
        + "\n\n---\n\n"
        + "# Solution to Evaluate\n\n"
        + f"Solution directory: {solution_dir}\n\n"
        + "---\n\n"
        + "# Report Output Location\n\n"
        + f"**You MUST write the final evaluation report to:** `{report_output_path}`\n\n"
        + "**IMPORTANT:**\n"
        + "- The report file MUST be created by you using file write tools\n"
        + "- Do NOT just print the report to stdout\n"
        + "- The external system will read the report from this file\n"
        + "- If you fail to write the file, the evaluation will be considered failed\n\n"
        + "---\n\n"
        + "# Instructions\n\n"
        + "Evaluate the solution according to the skill above. "
        + "Run L0, L1, L2 checks in order with short-circuit logic.\n\n"
        + f"**CRITICAL: You MUST write the complete evaluation report to `{report_output_path}` using file write tools.** "
        + "Do NOT just output the report to stdout - the file MUST exist after your execution. "
        + "**Written to the report file, NOT just stdout.**"
    )


def build_checker_prompt(report_path: str, result_path: str) -> str:
    """构建 checker 的 prompt。

    Checker 是通用的、任务无关的——只判断评估报告是否表示通过。
    要求将结果写入指定文件。

    Args:
        report_path: 评估报告文件的路径（输入），Checker Agent 需要读取此文件
        result_path: 结果输出文件的路径，Checker Agent 需要将判定结果写入此文件
    """
    logger.debug("Building checker prompt")
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


# ============================================================================
# 辅助函数
# ============================================================================

def build_history_runs_hint(current_run_num: int) -> Optional[str]:
    """构建历史 run-sets 的路径提示。
    
    Args:
        current_run_num: 当前轮次
    
    Returns:
        历史路径提示字符串，或 None（首轮无历史）
    """
    if current_run_num <= 1:
        return None
    
    lines = [
        "```",
        "run-sets/",
    ]
    
    for i in range(1, current_run_num):
        run_id = f"run-{i:03d}"
        lines.append(f"├── {run_id}/")
        lines.append(f"│   ├── proposal.md        # Round {i} proposal")
        lines.append(f"│   └── eval-report/")
        lines.append(f"│       └── report.md      # Round {i} evaluation")
    
    lines.append("```")
    
    return "\n".join(lines)
