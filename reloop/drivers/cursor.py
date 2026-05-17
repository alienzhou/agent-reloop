"""CursorDriver — Cursor Agent CLI (cursor agent -p) 适配器。"""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Callable, Optional

from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)


class CursorDriverError(Exception):
    """CursorDriver 执行错误。"""

    pass


class CursorDriver(Driver):
    """Cursor Agent CLI 适配器。

    使用 `cursor agent -p` 以非交互模式运行 Cursor Agent。
    默认配置 --yolo --trust，确保全自动无人干预运行。

    可用模型（2026-05，常用）:
        - composer-2-fast        Composer 2 Fast（默认，推荐）
        - composer-2             Composer 2（更强推理）
        - claude-4.6-sonnet-medium       Sonnet 4.6 1M
        - claude-opus-4-7-xhigh          Opus 4.7 1M Max Thinking
        - gpt-5.3-codex                  Codex 5.3
        - auto                   Auto（自动选择）

    不指定 model 时，使用 Cursor 默认模型（composer-2-fast）。

    示例配置 (reloop.yaml):
        driver:
          type: cursor
          cursor:
            model: composer-2-fast
            yolo: true
            trust: true
    """

    def __init__(
        self,
        model: Optional[str] = None,
        yolo: bool = True,
        trust: bool = True,
        sandbox: Optional[str] = None,
    ) -> None:
        """初始化 CursorDriver。

        Args:
            model:   模型名称（如 composer-2-fast、claude-4.6-sonnet-medium），
                     不指定则使用 Cursor 默认模型
            yolo:    全自动模式，跳过所有确认（默认 True），映射到 --yolo
            trust:   自动信任 workspace（默认 True），映射到 --trust
            sandbox: 沙箱模式（enabled / disabled），不指定则使用默认策略
        """
        self.model = model
        self.yolo = yolo
        self.trust = trust
        self.sandbox = sandbox

        logger.debug(
            "CursorDriver initialized: model=%s, yolo=%s, trust=%s, sandbox=%s",
            model, yolo, trust, sandbox,
        )

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行 cursor agent -p 命令。

        Args:
            prompt:          完整的 prompt 字符串（作为命令行参数传入）
            workdir:         Agent 工作目录
            output:          可选，输出文件路径（Cursor 不原生支持，忽略）
            timeout:         可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            Agent 的输出文本

        Raises:
            CursorDriverError: 执行失败或超时
        """
        cmd = self._build_command(prompt, workdir)

        if stream_callback:
            return self._run_with_streaming(cmd, workdir, timeout, stream_callback)
        else:
            return self._run_blocking(cmd, workdir, timeout)

    def _build_command(
        self,
        prompt: str,
        workdir: str,
    ) -> list[str]:
        """构建 cursor agent -p 命令。

        Args:
            prompt:  prompt 文本（作为命令行最后一个参数传入）
            workdir: 工作目录

        Returns:
            命令参数列表
        """
        cmd = ["cursor", "agent", "-p"]

        # 全自动参数
        if self.yolo:
            cmd.append("--yolo")

        if self.trust:
            cmd.append("--trust")

        if self.model:
            cmd.extend(["--model", self.model])

        if self.sandbox:
            cmd.extend(["--sandbox", self.sandbox])

        # 工作目录
        cmd.extend(["--workspace", workdir])

        # prompt 作为命令行参数传入
        cmd.append(prompt)

        logger.debug("Built cursor command: %s", " ".join(cmd))
        return cmd

    def _run_with_streaming(
        self,
        cmd: list[str],
        workdir: str,
        timeout: Optional[int],
        stream_callback: Callable[[str], None],
    ) -> str:
        """流式执行，实时回调输出。

        Args:
            cmd:             完整的命令参数列表
            workdir:         工作目录
            timeout:         超时秒数
            stream_callback: 每行输出的回调函数

        Returns:
            完整的输出文本

        Raises:
            CursorDriverError: 执行失败或超时
        """
        full_output: list[str] = []

        logger.debug("Starting streaming execution in workdir=%s", workdir)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.debug("Process started, pid=%s", process.pid)
        except FileNotFoundError:
            logger.error("cursor agent command not found")
            raise CursorDriverError(
                "cursor agent 命令未找到，请确保已安装 Cursor CLI"
            )

        stdout_wrapper = None
        try:
            stdout = process.stdout
            if stdout is None:
                raise CursorDriverError("subprocess stdout is None")

            if hasattr(stdout, "readable") and callable(getattr(stdout, "readable", None)):
                try:
                    stdout_wrapper = io.TextIOWrapper(
                        stdout,
                        encoding="utf-8",
                        errors="replace",
                        newline="",
                    )
                    stdout = stdout_wrapper
                except (TypeError, AttributeError):
                    pass

            for line in stdout:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                if line is not None:
                    full_output.append(line)
                    stream_callback(line.rstrip("\n"))

            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            logger.error("Streaming execution timed out after %ss", timeout)
            raise CursorDriverError(f"cursor agent -p 超时 ({timeout}s)")
        finally:
            if stdout_wrapper is not None:
                try:
                    stdout_wrapper.detach()
                except Exception:
                    pass

        if process.returncode != 0:
            logger.error("Streaming execution failed with exit code %s", process.returncode)
            raise CursorDriverError(f"cursor agent -p 失败 (exit {process.returncode})")

        response = "".join(full_output).strip()
        logger.debug("Streaming execution completed, response length=%d", len(response))
        return response

    def _run_blocking(
        self,
        cmd: list[str],
        workdir: str,
        timeout: Optional[int],
    ) -> str:
        """阻塞执行，等待完成后返回。

        Args:
            cmd:     完整的命令参数列表
            workdir: 工作目录
            timeout: 超时秒数

        Returns:
            完整的输出文本

        Raises:
            CursorDriverError: 执行失败或超时
        """
        logger.debug("Starting blocking execution in workdir=%s", workdir)

        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("Blocking execution timed out after %ss", timeout)
            raise CursorDriverError(f"cursor agent -p 超时 ({timeout}s)")
        except FileNotFoundError:
            logger.error("cursor agent command not found")
            raise CursorDriverError(
                "cursor agent 命令未找到，请确保已安装 Cursor CLI"
            )

        response = result.stdout
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")

        if result.returncode != 0:
            stderr = result.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            logger.error(
                "Blocking execution failed with exit code %s: %s",
                result.returncode,
                stderr[:200] if stderr else "",
            )
            raise CursorDriverError(
                f"cursor agent -p 失败 (exit {result.returncode}): {stderr}"
            )

        response = response.strip()
        logger.debug("Blocking execution completed, response length=%d", len(response))
        return response