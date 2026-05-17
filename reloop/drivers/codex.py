"""CodexDriver — OpenAI Codex CLI (codex exec) 适配器。"""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Callable, Optional

from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)


class CodexDriverError(Exception):
    """CodexDriver 执行错误。"""

    pass


class CodexDriver(Driver):
    """OpenAI Codex CLI 适配器。

    使用 `codex exec` 命令以非交互模式运行 Codex Agent。
    prompt 通过 stdin（"-" 参数）传入，避免 shell 转义问题。

    可用模型（2026-05）:
        - gpt-5.5               最新前沿模型（推荐）
        - gpt-5.1-codex         Codex 专用模型
        - gpt-5.1-codex-max     Codex Max 模型（更强）
        - gpt-5-codex-mini      Codex Mini 模型（轻量快速）
        - o3                    OpenAI o3 推理模型

    不指定 model 时，使用 ~/.codex/config.toml 中的默认模型。

    示例配置 (reloop.yaml):
        driver:
          type: codex
          codex:
            model: gpt-5-codex-mini
            sandbox: workspace-write
            full_auto: true
    """

    def __init__(
        self,
        model: Optional[str] = None,
        sandbox: Optional[str] = None,
        full_auto: bool = False,
    ) -> None:
        """初始化 CodexDriver。

        Args:
            model:     模型名称（如 gpt-5-codex-mini、gpt-5.1-codex、o3），不指定则使用 codex 默认配置
            sandbox:   沙箱模式（read-only / workspace-write / danger-full-access），不指定则使用默认策略
            full_auto: True 时追加 --dangerously-bypass-approvals-and-sandbox，
                       跳过所有确认提示，适合完全无人值守运行
        """
        self.model = model
        self.sandbox = sandbox
        self.full_auto = full_auto

        logger.debug(
            "CodexDriver initialized: model=%s, sandbox=%s, full_auto=%s",
            model,
            sandbox,
            full_auto,
        )

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行 codex exec 命令。

        Args:
            prompt:          完整的 prompt 字符串（通过 stdin 传入）
            workdir:         Agent 工作目录（通过 -C 参数传入）
            output:          可选，最后一条消息输出文件路径（通过 -o 参数传入）
            timeout:         可选，超时秒数
            stream_callback: 可选，流式输出回调函数

        Returns:
            Agent 的输出文本

        Raises:
            CodexDriverError: 执行失败或超时
        """
        cmd = self._build_command(workdir, output)

        if stream_callback:
            return self._run_with_streaming(cmd, prompt, workdir, timeout, stream_callback)
        else:
            return self._run_blocking(cmd, prompt, workdir, timeout)

    def _build_command(
        self,
        workdir: str,
        output: Optional[str] = None,
    ) -> list[str]:
        """构建 codex exec 命令（不含 prompt，通过 stdin 传入）。

        Args:
            workdir: 工作目录
            output:  可选输出文件路径（--output-last-message / -o）

        Returns:
            命令参数列表
        """
        cmd = ["codex", "exec"]

        if self.model:
            cmd.extend(["--model", self.model])

        if self.sandbox:
            cmd.extend(["--sandbox", self.sandbox])

        if self.full_auto:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")

        # 指定工作目录
        cmd.extend(["-C", workdir])

        # 如果指定了输出文件，使用 -o 参数
        if output:
            cmd.extend(["-o", output])

        # "-" 表示从 stdin 读取 prompt
        cmd.append("-")

        logger.debug("Built codex command: %s", " ".join(cmd))
        return cmd

    def _run_with_streaming(
        self,
        cmd: list[str],
        prompt: str,
        workdir: str,
        timeout: Optional[int],
        stream_callback: Callable[[str], None],
    ) -> str:
        """流式执行，通过 stdin 传入 prompt，实时回调输出。

        Args:
            cmd:             完整的命令参数列表
            prompt:          prompt 文本
            workdir:         工作目录
            timeout:         超时秒数
            stream_callback: 每行输出的回调函数

        Returns:
            完整的输出文本

        Raises:
            CodexDriverError: 执行失败或超时
        """
        full_output: list[str] = []

        logger.debug("Starting streaming execution in workdir=%s", workdir)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.debug("Process started, pid=%s", process.pid)
        except FileNotFoundError:
            logger.error("codex command not found")
            raise CodexDriverError(
                "codex 命令未找到，请确保已安装 Codex CLI（npm install -g @openai/codex）"
            )

        stdout_wrapper = None
        try:
            # 写入 prompt 到 stdin 并关闭
            if process.stdin:
                process.stdin.write(prompt.encode("utf-8"))
                process.stdin.close()

            stdout = process.stdout
            if stdout is None:
                raise CodexDriverError("subprocess stdout is None")

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
            raise CodexDriverError(f"codex exec 超时 ({timeout}s)")
        finally:
            if stdout_wrapper is not None:
                try:
                    stdout_wrapper.detach()
                except Exception:
                    pass

        if process.returncode != 0:
            logger.error("Streaming execution failed with exit code %s", process.returncode)
            raise CodexDriverError(f"codex exec 失败 (exit {process.returncode})")

        response = "".join(full_output).strip()
        logger.debug("Streaming execution completed, response length=%d", len(response))
        return response

    def _run_blocking(
        self,
        cmd: list[str],
        prompt: str,
        workdir: str,
        timeout: Optional[int],
    ) -> str:
        """阻塞执行，通过 stdin 传入 prompt，等待完成后返回。

        Args:
            cmd:     完整的命令参数列表
            prompt:  prompt 文本
            workdir: 工作目录
            timeout: 超时秒数

        Returns:
            完整的输出文本

        Raises:
            CodexDriverError: 执行失败或超时
        """
        logger.debug("Starting blocking execution in workdir=%s", workdir)

        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                input=prompt.encode("utf-8"),
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("Blocking execution timed out after %ss", timeout)
            raise CodexDriverError(f"codex exec 超时 ({timeout}s)")
        except FileNotFoundError:
            logger.error("codex command not found")
            raise CodexDriverError(
                "codex 命令未找到，请确保已安装 Codex CLI（npm install -g @openai/codex）"
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
            raise CodexDriverError(
                f"codex exec 失败 (exit {result.returncode}): {stderr}"
            )

        response = response.strip()
        logger.debug("Blocking execution completed, response length=%d", len(response))
        return response
