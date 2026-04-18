"""MockDriver — 框架内置的确定性 Driver，用于测试和验证。

MockDriver 不是纯测试工具，它是框架的正式组件。
用户可以用它来验证 evaluator 逻辑、dry-run 迭代循环，
而不需要调用真实的 Agent CLI。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from reloop.drivers.base import Driver


class MockDriverExhaustedError(Exception):
    """MockDriver 的预设响应已用完"""


class MockDriver(Driver):
    """确定性 Driver：按顺序返回预设响应。

    每次调用 run() 时弹出下一个预设响应并返回，
    同时将调用参数记录到 call_log 供断言使用。
    """

    def __init__(self, responses: List[str]):
        self.responses = list(responses)
        self.call_log: List[Dict[str, Any]] = []

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> str:
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
        return self.responses.pop(0)


class CallbackMockDriver(MockDriver):
    """带副作用回调的 MockDriver。

    在返回响应前执行一个可选的 callback，
    用于模拟 Agent 创建文件等副作用。
    """

    def __init__(
        self,
        responses: List[str],
        callbacks: Optional[List[Optional[Callable]]] = None,
    ):
        super().__init__(responses)
        self.callbacks: List[Optional[Callable]] = list(callbacks or [])

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> str:
        if self.callbacks:
            callback = self.callbacks.pop(0)
            if callback is not None:
                callback(prompt=prompt, workdir=workdir)
        return super().run(prompt, workdir, output=output, timeout=timeout)
