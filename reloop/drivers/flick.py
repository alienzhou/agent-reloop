"""FlickDriver — DuetSpace Gateway CLI (flick link) 适配器。"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Optional

from reloop.drivers.base import Driver


class FlickDriverError(Exception):
    """FlickDriver 执行错误。"""

    pass


class FlickDriver(Driver):
    """DuetSpace Gateway CLI 适配器。

    使用 `flick link prompt` 命令与 DuetSpace Agent 交互。

    Workspace 通过配置文件指定，所有请求发送到固定 Workspace。
    """

    def __init__(
        self,
        workspace: str,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        json_output: bool = True,
    ) -> None:
        """初始化 FlickDriver。

        Args:
            workspace: Duet Workspace ID 或路径（必需）
            model: 模型选择（如 CLAUDE_4_5, AUTO）
            mode: 模式选择（agent, plan, deep, discuss, ask）
            json_output: 是否使用 JSON 输出

        Raises:
            FlickDriverError: workspace 参数为空时
        """
        if not workspace:
            raise FlickDriverError("workspace 参数是必需的")

        self.workspace = workspace
        self.model = model
        self.mode = mode
        self.json_output = json_output

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """发送 prompt 到固定的 Duet Workspace。

        Args:
            prompt: 完整的 prompt 字符串
            workdir: 本地工作目录（用于 subprocess.cwd）
            output: 可选，输出文件路径
            timeout: 可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            Agent 的输出文本

        Raises:
            FlickDriverError: 执行失败或超时
        """
        # 构建命令
        cmd = ["flick", "link", "prompt"]

        # 使用配置的 Workspace（固定）
        cmd.extend(["--duet-workspace", self.workspace])

        if self.model:
            cmd.extend(["--duet-model", self.model])

        if self.mode:
            cmd.extend(["--duet-mode", self.mode])

        if self.json_output:
            cmd.append("--duet-json")

        cmd.append(prompt)

        # 执行命令
        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise FlickDriverError(f"flick link prompt 超时 ({timeout}s)")
        except FileNotFoundError:
            raise FlickDriverError("flick 命令未找到，请确保已安装 flick CLI")

        if result.returncode != 0:
            raise FlickDriverError(
                f"flick link prompt 失败 (exit {result.returncode}): {result.stderr}"
            )

        # 处理输出
        response = result.stdout.strip()

        # 如果启用 JSON 输出，解析并提取内容
        if self.json_output and response:
            try:
                data = json.loads(response)
                # 根据实际返回结构提取内容
                # 结构可能是 {"content": "..."} 或其他格式
                if isinstance(data, dict):
                    response = data.get("content", data.get("message", response))
            except json.JSONDecodeError:
                pass  # 非 JSON 输出，直接返回原始文本

        return response
