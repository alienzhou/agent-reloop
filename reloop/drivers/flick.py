"""FlickDriver — DuetSpace Gateway CLI (flick link) 适配器。"""

from __future__ import annotations

import io
import json
import logging
import subprocess
from typing import Any, Callable, Optional

from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)


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

        logger.debug(
            "FlickDriver initialized: workspace=%s, model=%s, mode=%s, json_output=%s",
            workspace,
            model,
            mode,
            json_output,
        )

    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """发送 prompt 到固定的 Duet Workspace，支持流式输出。

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
        cmd = self._build_command(prompt)

        # 根据是否有回调选择执行模式
        if stream_callback:
            return self._run_with_streaming(cmd, workdir, timeout, stream_callback)
        else:
            return self._run_blocking(cmd, workdir, timeout)

    def _build_command(self, prompt: str) -> list[str]:
        """构建 flick 命令。

        Args:
            prompt: 要发送的 prompt

        Returns:
            完整的命令参数列表
        """
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

        logger.debug("Built flick command: %s", " ".join(cmd[:6]) + " ...")

        return cmd

    def _run_with_streaming(
        self,
        cmd: list[str],
        workdir: str,
        timeout: Optional[int],
        stream_callback: Callable[[str], None],
    ) -> str:
        """流式执行，实时回调输出。

        使用 subprocess.Popen 逐行读取输出，每行调用回调函数。
        使用二进制模式读取并手动处理 UTF-8 解码，以正确处理不完整的字节序列。

        Args:
            cmd: 完整的命令参数列表
            workdir: 工作目录
            timeout: 超时秒数
            stream_callback: 每行输出的回调函数

        Returns:
            完整的输出文本

        Raises:
            FlickDriverError: 执行失败或超时
        """
        full_output: list[str] = []

        logger.debug("Starting streaming execution in workdir=%s", workdir)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # 使用二进制模式，避免在多字节字符中间截断时的解码错误
            )
            logger.debug("Process started, pid=%s", process.pid)
        except FileNotFoundError:
            logger.error("flick command not found")
            raise FlickDriverError("flick 命令未找到，请确保已安装 flick CLI")

        stdout_wrapper = None
        try:
            # 检查 stdout 是否有效且支持 TextIOWrapper（真实的二进制流）
            # 测试场景可能使用 mock 对象，此时回退到简单迭代模式
            stdout = process.stdout
            
            # P1 修复: 防御性检查 stdout 是否为 None
            if stdout is None:
                raise FlickDriverError("subprocess stdout is None")
            
            # 检查是否支持 TextIOWrapper（有 readable 方法且可调用）
            if hasattr(stdout, 'readable') and callable(getattr(stdout, 'readable', None)):
                try:
                    # 使用 TextIOWrapper 包装二进制流，设置 errors='replace' 处理无效字节
                    # 这样不完整的 UTF-8 序列会被替换为 � 而不是抛出异常
                    stdout_wrapper = io.TextIOWrapper(
                        stdout,
                        encoding='utf-8',
                        errors='replace',  # 用 � 替换无法解码的字节
                        newline='',
                    )
                    stdout = stdout_wrapper
                except (TypeError, AttributeError):
                    # P1 修复: 如果 TextIOWrapper 构造失败，回退到直接迭代
                    pass
            
            # 逐行读取输出
            for line in stdout:
                # 如果 line 是 bytes，需要手动解码
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='replace')
                # P2 修复: 防御性检查 line 不为 None
                if line is not None:
                    full_output.append(line)
                    stream_callback(line.rstrip("\n"))

            # 等待进程结束
            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()  # 确保进程完全终止
            logger.error("Streaming execution timed out after %ss", timeout)
            raise FlickDriverError(f"flick link prompt 超时 ({timeout}s)")
        finally:
            # P2 修复: 显式关闭 TextIOWrapper（如果创建了的话）
            if stdout_wrapper is not None:
                try:
                    stdout_wrapper.detach()  # 使用 detach 而非 close，避免关闭底层流
                except Exception:
                    pass

        if process.returncode != 0:
            logger.error(
                "Streaming execution failed with exit code %s", process.returncode
            )
            raise FlickDriverError(
                f"flick link prompt 失败 (exit {process.returncode})"
            )

        response = "".join(full_output).strip()

        # JSON 处理（如果启用）
        if self.json_output and response:
            response = self._parse_json_response(response)

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
            cmd: 完整的命令参数列表
            workdir: 工作目录
            timeout: 超时秒数

        Returns:
            完整的输出文本

        Raises:
            FlickDriverError: 执行失败或超时
        """
        logger.debug("Starting blocking execution in workdir=%s", workdir)

        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                timeout=timeout,
                # 使用二进制模式，手动解码以处理可能的编码问题
            )
        except subprocess.TimeoutExpired:
            logger.error("Blocking execution timed out after %ss", timeout)
            raise FlickDriverError(f"flick link prompt 超时 ({timeout}s)")
        except FileNotFoundError:
            logger.error("flick command not found")
            raise FlickDriverError("flick 命令未找到，请确保已安装 flick CLI")

        if result.returncode != 0:
            # 解码 stderr，处理 bytes 或 str（测试场景可能是 str）
            stderr = result.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf-8', errors='replace')
            logger.error(
                "Blocking execution failed with exit code %s: %s",
                result.returncode,
                stderr[:200] if stderr else "",
            )
            raise FlickDriverError(
                f"flick link prompt 失败 (exit {result.returncode}): {stderr}"
            )

        # 解码 stdout，处理 bytes 或 str（测试场景可能是 str）
        response = result.stdout
        if isinstance(response, bytes):
            response = response.decode('utf-8', errors='replace')
        response = response.strip()

        # JSON 处理（如果启用）
        if self.json_output and response:
            response = self._parse_json_response(response)

        logger.debug("Blocking execution completed, response length=%d", len(response))

        return response

    def _parse_json_response(self, response: str) -> str:
        """解析 JSON Lines 响应，提取 agent 文本内容。

        flick link prompt --duet-json 输出格式为 JSON Lines，但实际输出可能：
        1. 每行一个 JSON 对象（标准 JSON Lines）
        2. 多个 JSON 对象拼接在一起（无换行符）

        消息类型：
        - {"type": "session_created", ...}
        - {"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "..."}}
        - {"type": "end", ...}

        Args:
            response: 原始响应字符串

        Returns:
            拼接后的 agent 文本内容
        """
        if not response:
            return response

        text_chunks: list[str] = []

        # 尝试提取所有 JSON 对象（处理拼接在一起的情况）
        json_objects = self._extract_json_objects(response)

        for data in json_objects:
            if isinstance(data, dict):
                # 处理 agent_message_chunk 类型
                if data.get("updateType") == "agent_message_chunk":
                    content = data.get("content", {})
                    if isinstance(content, dict) and content.get("type") == "text":
                        text = content.get("text", "")
                        if text:
                            text_chunks.append(text)

        # 如果没有提取到任何文本，返回原始响应
        if not text_chunks:
            logger.debug(
                "JSON parsing: no text chunks extracted from %d objects, returning raw",
                len(json_objects),
            )
            return response

        logger.debug(
            "JSON parsing: extracted %d text chunks from %d objects",
            len(text_chunks),
            len(json_objects),
        )
        return "".join(text_chunks)

    def _extract_json_objects(self, text: str) -> list[Any]:
        """从文本中提取所有 JSON 对象。

        处理两种情况：
        1. 标准 JSON Lines（每行一个对象）
        2. 拼接的 JSON 对象（无换行符分隔）

        Args:
            text: 包含 JSON 对象的文本

        Returns:
            提取出的 JSON 对象列表
        """
        objects: list[Any] = []

        # 首先尝试按行解析（标准 JSON Lines）
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                objects.append(obj)
            except json.JSONDecodeError:
                # 该行不是有效 JSON，可能是拼接的多个对象
                pass

        # 如果按行解析成功且有结果，直接返回
        if objects:
            return objects

        # 否则尝试提取拼接在一起的 JSON 对象
        # 使用迭代方式查找 JSON 对象边界
        pos = 0
        text_len = len(text)

        while pos < text_len:
            # 跳过空白
            while pos < text_len and text[pos] in ' \t\n\r':
                pos += 1

            if pos >= text_len:
                break

            # 查找下一个 { 开始
            if text[pos] != '{':
                pos += 1
                continue

            # 尝试从当前位置解析 JSON 对象
            try:
                decoder = json.JSONDecoder()
                obj, end_idx = decoder.raw_decode(text, pos)
                objects.append(obj)
                pos = pos + end_idx
            except json.JSONDecodeError:
                # 无法解析，跳过这个字符
                pos += 1

        return objects
