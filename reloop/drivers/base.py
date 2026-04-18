"""Driver 基类 — 统一的 Agent CLI 适配接口"""

from __future__ import annotations

from typing import Optional


class Driver:
    """所有 Driver 的基类。

    每个 Agent CLI（Claude Code / Codex / Gemini / …）实现一个子类，
    通过统一的 run() 接口被迭代循环调用。
    """

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """调用 Agent CLI 执行 prompt。

        Args:
            prompt:   完整的 prompt 字符串（Skill 内容 + 用户 prompt 已内联）
            workdir:  Agent 工作目录
            output:   可选，输出文件路径
            timeout:  可选，超时秒数

        Returns:
            Agent 的输出文本
        """
        raise NotImplementedError
