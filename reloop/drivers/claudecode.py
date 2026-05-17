"""ClaudeCodeDriver — Claude Code CLI (claude -p) 适配器。"""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Callable, Optional

from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)


class ClaudeCodeDriverError(Exception):
    """ClaudeCodeDriver 执行错误。"""

    pass


class ClaudeCodeDriver(Driver):
    """Claude Code CLI 适配器。

    使用 `claude -p` 以非交互模式运行 Claude Code Agent。
    prompt 作为命令行参数传入，配合 --permission-mode bypassPermissions
    实现全自动无人干预运行。

    可用模型（2026-05）:
        - sonnet              Claude Sonnet（快速，推荐日常使用）
        - opus                Claude Opus（最强推理能力）
        - claude-sonnet-4-6   Claude Sonnet 4.6（完整模型名）
        - claude-opus-4       Claude Opus 4（完整模型名）

    不指定 model 时，使用 Claude Code 自己的默认模型。

    示例配置 (reloop.yaml):
        driver:
          type: claudecode
          claudecode:
            model: sonnet
            permission_mode: bypassPermissions
    """

    def __init__(
        self,
        model: Optional[str] = None,
        permission_mode: Optional[str] = None,
        max_budget_usd: Optional[float] = None,
        add_dirs: Optional[list[str]] = None,
    ) -> None:
        """初始化 ClaudeCodeDriver。

        Args:
            model:           模型名称（如 sonnet、opus、claude-sonnet-4-6），不指定则使用默认
            permission_mode: 权限模式，默认 bypassPermissions（全自动无人干预）
                             可选值: bypassPermissions, auto, default, dontAsk, plan, acceptEdits
            max_budget_usd:  最大 API 花费上限（美元），不指定则无上限
            add_dirs:        额外允许工具访问的目录列表
        """
        self.model = model
        # 默认 bypassPermissions，确保全自动运行不被权限提示卡住
        self.permission_mode = permission_mode or "bypassPermissions"
        self.max_budget_usd = max_budget_usd
        self.add_dirs = add_dirs

        logger.debug(
            "ClaudeCodeDriver initialized: model=%s, permission_mode=%s, "
            "max_budget_usd=%s, add_dirs=%s",
            model,
            self.permission_mode,
            max_budget_usd,
            add_dirs,
        )

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行 claude -p 命令。

        Args:
            prompt:          完整的 prompt 字符串（作为命令行参数传入）
            workdir:         Agent 工作目录
            output:          可选，输出文件路径（Claude Code 不原生支持，忽略）
            timeout:         可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            Agent 的输出文本

        Raises:
            ClaudeCodeDriverError: 执行失败或超时
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
        """构建 claude -p 命令。

        Args:
            prompt:  prompt 文本（作为命令行最后一个参数传入）
            workdir: 工作目录

        Returns:
            命令参数列表
        """
        cmd = ["claude", "-p"]

        # 非交互模式 + 权限模式
        cmd.extend(["--permission-mode", self.permission_mode])

        if self.model:
            cmd.extend(["--model", self.model])

        if self.max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        if self.add_dirs:
            for dir_path in self.add_dirs:
                cmd.extend(["--add-dir", dir_path])

        # 指定工作目录（claude 没有 -C 参数，需要通过 cwd 传入）
        # prompt 作为命令行参数传入
        cmd.append(prompt)

        logger.debug("Built claude command (cwd=%s): %s", workdir, " ".join(cmd))
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
            ClaudeCodeDriverError: 执行失败或超时
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
            logger.error("claude command not found")
            raise ClaudeCodeDriverError(
                "claude 命令未找到，请确保已安装 Claude Code CLI"
            )

        stdout_wrapper = None
        try:
            stdout = process.stdout
            if stdout is None:
                raise ClaudeCodeDriverError("subprocess stdout is None")

            # 用 TextIOWrapper 包装二进制流，处理 UTF-8 解码
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
            raise ClaudeCodeDriverError(f"claude -p 超时 ({timeout}s)")
        finally:
            if stdout_wrapper is not None:
                try:
                    stdout_wrapper.detach()
                except Exception:
                    pass

        if process.returncode != 0:
            logger.error("Streaming execution failed with exit code %s", process.returncode)
            raise ClaudeCodeDriverError(f"claude -p 失败 (exit {process.returncode})")

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
            ClaudeCodeDriverError: 执行失败或超时
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
            raise ClaudeCodeDriverError(f"claude -p 超时 ({timeout}s)")
        except FileNotFoundError:
            logger.error("claude command not found")
            raise ClaudeCodeDriverError(
                "claude 命令未找到，请确保已安装 Claude Code CLI"
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
            raise ClaudeCodeDriverError(
                f"claude -p 失败 (exit {result.returncode}): {stderr}"
            )

        response = response.strip()
        logger.debug("Blocking execution completed, response length=%d", len(response))
        return response