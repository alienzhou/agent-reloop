"""评估报告清理器 — 移除敏感的评估脚本和规则信息。

评估器生成的完整报告可能包含评估脚本路径、具体规则等信息，
这些不应该泄露给执行器，以避免执行器针对评估规则"作弊"。

本模块提供 sanitize_eval_report() 函数，用于：
1. 移除脚本路径引用（task/scripts/*.py）
2. 移除评估规则的详细描述
3. 保留问题摘要和修复建议
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# 需要移除的敏感模式
_SENSITIVE_PATTERNS = [
    # 脚本路径引用
    r"task/scripts/\S+\.py",
    r"`task/scripts/[^`]+`",
    r"运行\s*`?task/scripts/[^`\s]+`?",
    r"Run\s+`?task/scripts/[^`\s]+`?",
    r"check_l[0-4]\.py",
    # 评估层级详细描述（保留结果，移除评估标准）
    r"##\s*L[0-4]\s*-\s*[^\n]+评估框架[^\n]*\n",
    # 短路机制说明
    r"短路机制[^\n]*",
    r"short-circuit[^\n]*",
]

# 需要移除的整段内容（匹配到这些标题后移除该段落）
_SENSITIVE_SECTIONS = [
    r"##\s*评估框架\s*\n[\s\S]*?(?=\n##|\Z)",
    r"##\s*Evaluation Framework\s*\n[\s\S]*?(?=\n##|\Z)",
    r"##\s*检查脚本\s*\n[\s\S]*?(?=\n##|\Z)",
    r"##\s*Check Scripts\s*\n[\s\S]*?(?=\n##|\Z)",
    r"###\s*脚本\s*\n[\s\S]*?(?=\n###|\n##|\Z)",
    r"###\s*Script\s*\n[\s\S]*?(?=\n###|\n##|\Z)",
]


def sanitize_eval_report(report: str, keep_summary: bool = True) -> str:
    """清理评估报告，移除敏感的评估脚本和规则信息。

    Args:
        report: 原始评估报告内容
        keep_summary: 是否保留问题摘要（默认 True）

    Returns:
        清理后的报告内容，只包含问题列表和修复建议

    Example:
        >>> raw_report = '''
        ... # 评估报告
        ...
        ... ## L0 - 安全检查
        ... 运行 `task/scripts/check_l0.py`
        ... 结果: PASS
        ...
        ... ## 问题清单
        ... 1. 缺少 README.md
        ... '''
        >>> sanitized = sanitize_eval_report(raw_report)
        >>> "task/scripts" not in sanitized
        True
    """
    logger.debug(f"Sanitizing report: {len(report)} chars")
    if not report:
        return report

    result = report

    # 移除敏感段落
    for pattern in _SENSITIVE_SECTIONS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    # 移除敏感模式
    for pattern in _SENSITIVE_PATTERNS:
        result = re.sub(pattern, "[检查脚本]", result, flags=re.IGNORECASE)

    # 清理多余的空行
    result = re.sub(r"\n{3,}", "\n\n", result)

    # 如果结果变得太短（可能移除过多），保留原始摘要
    if keep_summary and len(result.strip()) < 100:
        # 尝试提取问题部分
        issues_section = _extract_issues_section(report)
        if issues_section:
            result = issues_section

    return result.strip()


def _extract_issues_section(report: str) -> Optional[str]:
    """从报告中提取问题/Issues 部分。

    Args:
        report: 原始报告内容

    Returns:
        提取的问题部分，或 None
    """
    # 查找问题部分的常见标题
    patterns = [
        r"##\s*问题[清单表]?\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*Issues?\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*Problems?\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*待修复\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*To Fix\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*Findings?\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*结果\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*Results?\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*Summary\s*\n([\s\S]*?)(?=\n##|\Z)",
        r"##\s*总结\s*\n([\s\S]*?)(?=\n##|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, report, re.IGNORECASE)
        if match:
            header_match = re.search(r"##\s*\S+", report[match.start():match.end()])
            header = header_match.group() if header_match else "## 问题清单"
            return f"{header}\n{match.group(1).strip()}"

    return None


def extract_actionable_feedback(report: str) -> str:
    """从评估报告中提取可操作的反馈。

    只保留问题描述和修复建议，移除所有评估过程的详情。

    Args:
        report: 原始评估报告内容

    Returns:
        精简的可操作反馈

    Example:
        >>> report = '''
        ... # 评估报告
        ... ## L1 通过
        ... ## L2 失败
        ... ### 问题1: 缺少单元测试
        ... 建议: 添加至少 3 个测试用例
        ... '''
        >>> feedback = extract_actionable_feedback(report)
    """
    logger.debug("Extracting feedback")
    if not report:
        return report

    lines = report.splitlines()
    result_lines: list[str] = []
    in_issue_section = False
    current_level = ""

    for line in lines:
        # 检测是否进入问题/建议部分
        if re.match(r"^##\s*(问题|Issues?|Problems?|待修复|To Fix|建议|Suggestions?|Recommendations?)", line, re.IGNORECASE):
            in_issue_section = True
            current_level = "##"
            result_lines.append(line)
            continue

        # 检测是否进入结果/总结部分
        if re.match(r"^##\s*(结果|Results?|总结|Summary|Conclusion)", line, re.IGNORECASE):
            in_issue_section = True
            current_level = "##"
            result_lines.append(line)
            continue

        # 检测是否离开当前部分（遇到同级或更高级标题）
        if in_issue_section:
            if re.match(r"^##\s+", line) and current_level == "##":
                # 遇到新的二级标题，检查是否是相关部分
                if not re.match(r"^##\s*(问题|Issues?|Problems?|待修复|To Fix|建议|Suggestions?|结果|Results?|总结|Summary)", line, re.IGNORECASE):
                    in_issue_section = False
                    continue

            result_lines.append(line)
            continue

        # 检测整体通过/失败结果行
        if re.match(r"^(Overall|总体|Result|结果|Verdict|判定)\s*[:：]", line, re.IGNORECASE):
            result_lines.append(line)

    # 清理敏感内容
    result = "\n".join(result_lines)
    return sanitize_eval_report(result, keep_summary=False)
