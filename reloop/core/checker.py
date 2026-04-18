"""Checker 结果解析 — 将 Agent 输出转换为 pass/fail 布尔值"""

from __future__ import annotations


def parse_checker_result(output: str) -> bool:
    """解析 checker Agent 的输出，判定 pass 或 fail。

    解析策略：
    1. 取输出的最后一个非空行
    2. strip 后进行完全匹配（不区分大小写）
    3. 匹配 "passed" → True，"failed" → False
    4. 其它情况保守返回 False
    """
    stripped = output.strip()
    if not stripped:
        return False

    last_line = stripped.splitlines()[-1].strip().lower()

    if last_line == "passed":
        return True
    if last_line == "failed":
        return False

    return False
