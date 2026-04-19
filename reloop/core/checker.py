"""Checker 结果解析 — 将 Agent 输出转换为 pass/fail 布尔值"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# XML 标签匹配模式
CHECKER_RESULT_PATTERN = re.compile(
    r"<checker_result>\s*(passed|failed)\s*</checker_result>",
    re.MULTILINE | re.IGNORECASE
)


def parse_checker_result(output: str) -> bool:
    """解析 checker Agent 的输出，判定 pass 或 fail。

    解析策略（优先级）：
    1. 首先尝试匹配 XML 标签：<checker_result>passed/failed</checker_result>
    2. 如果 XML 解析失败，回退到旧格式：取最后一行匹配 passed/failed

    Args:
        output: checker Agent 的完整输出文本

    Returns:
        True 表示 passed，False 表示 failed

    Raises:
        ValueError: 无法解析出结果时
    """
    logger.debug("Parsing checker result, %d chars", len(output))
    # 尝试 XML 格式解析（优先）
    match = CHECKER_RESULT_PATTERN.search(output)
    if match:
        result = match.group(1).lower()
        logger.debug("Found XML tag result: %s", result)
        passed = result == "passed"
        logger.info("Checker result: passed=%s", passed)
        return passed

    # 回退：旧格式兼容（取最后一个非空行）
    logger.debug("XML parse failed, falling back")
    stripped = output.strip()
    if not stripped:
        raise ValueError("Cannot parse checker result from empty output")

    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if not lines:
        raise ValueError("Cannot parse checker result from empty output")

    last_line = lines[-1].lower()
    if last_line == "passed":
        logger.info("Checker result: passed=%s", True)
        return True
    if last_line == "failed":
        logger.info("Checker result: passed=%s", False)
        return False

    # 尝试在最后几行中查找 passed/failed
    for line in reversed(lines[-5:]):
        line_lower = line.lower()
        if line_lower in ("passed", "failed"):
            passed = line_lower == "passed"
            logger.info("Checker result: passed=%s", passed)
            return passed

    raise ValueError(f"Cannot parse checker result from output: {output[:200]}...")


def extract_checker_explanation(output: str) -> str | None:
    """提取 Checker 的解释内容（如有）。

    解释内容为 XML 标签之后的文本。

    Args:
        output: checker Agent 的完整输出文本

    Returns:
        解释内容，如无则返回 None
    """
    # 找到 XML 标签
    match = CHECKER_RESULT_PATTERN.search(output)
    if match:
        end_pos = match.end()
        explanation = output[end_pos:].strip()
        if explanation:
            logger.debug("Extracted explanation")
            return explanation
        return None
    return None
