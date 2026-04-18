"""MockDriver — 框架内置的确定性 Driver，用于测试和验证。

MockDriver 不是纯测试工具，它是框架的正式组件。
用户可以用它来验证 evaluator 逻辑、dry-run 迭代循环，
而不需要调用真实的 Agent CLI。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from reloop.drivers.base import Driver


class MockDriverExhaustedError(Exception):
    """MockDriver 的预设响应已用完"""


class MockDriver(Driver):
    """确定性 Driver：按顺序返回预设响应。

    每次调用 run() 时弹出下一个预设响应并返回，
    同时将调用参数记录到 call_log 供断言使用。

    支持流式输出回调，模拟真实 Driver 的行为。
    """

    def __init__(
        self,
        responses: List[str],
        delay_per_line: float = 0.05,
    ) -> None:
        """初始化 MockDriver。

        Args:
            responses: 预设响应列表
            delay_per_line: 流式输出时每行的延迟（秒），默认 0.05
        """
        self.responses = list(responses)
        self.delay_per_line = delay_per_line
        self.call_log: List[Dict[str, Any]] = []

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """按顺序返回预设响应。

        Args:
            prompt: 完整的 prompt 字符串
            workdir: Agent 工作目录
            output: 可选，输出文件路径
            timeout: 可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            预设的响应文本

        Raises:
            MockDriverExhaustedError: 预设响应已用完
        """
        self.call_log.append({
            "prompt": prompt,
            "workdir": workdir,
            "output": output,
            "timeout": timeout,
        })

        if not self.responses:
            raise MockDriverExhaustedError(
                f"MockDriver ran out of responses after {len(self.call_log)} calls"
            )

        response = self.responses.pop(0)

        # 模拟流式输出
        if stream_callback:
            lines = response.split("\n")
            for line in lines:
                time.sleep(self.delay_per_line)
                stream_callback(line)

        return response


class CallbackMockDriver(MockDriver):
    """带副作用回调的 MockDriver。

    在返回响应前执行一个可选的 callback，
    用于模拟 Agent 创建文件等副作用。
    """

    def __init__(
        self,
        responses: List[str],
        callbacks: Optional[List[Optional[Callable[..., None]]]] = None,
        delay_per_line: float = 0.05,
    ) -> None:
        """初始化 CallbackMockDriver。

        Args:
            responses: 预设响应列表
            callbacks: 每次调用的副作用回调列表
            delay_per_line: 流式输出时每行的延迟（秒）
        """
        super().__init__(responses, delay_per_line=delay_per_line)
        self.callbacks: List[Optional[Callable[..., None]]] = list(callbacks or [])

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行回调后返回预设响应。

        Args:
            prompt: 完整的 prompt 字符串
            workdir: Agent 工作目录
            output: 可选，输出文件路径
            timeout: 可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            预设的响应文本
        """
        # 执行副作用回调
        if self.callbacks:
            callback = self.callbacks.pop(0)
            if callback is not None:
                callback(prompt=prompt, workdir=workdir)

        return super().run(
            prompt=prompt,
            workdir=workdir,
            output=output,
            timeout=timeout,
            stream_callback=stream_callback,
        )
