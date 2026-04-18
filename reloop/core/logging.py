"""日志系统 — 四层日志结构支持。

提供：
- StreamOutput: 终端滚动显示 + 文件写入
- AgentLogger: Agent 输出的带时间戳写入器
- log_driver_call: Driver CLI 调用记录
- setup_system_logging: 系统日志初始化
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# 默认配置
DEFAULT_MAX_LINES = 4
DEFAULT_TIMESTAMP_FORMAT = "%H:%M:%S"
DEFAULT_FULL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


class StreamOutput:
    """流式输出管理器 — 终端滚动显示 + 文件写入。

    用于实时显示 Agent 输出，同时在文件中保存完整内容。
    终端只显示最近 N 行，滚动更新。
    """

    def __init__(
        self,
        log_path: Path,
        max_lines: int = DEFAULT_MAX_LINES,
        timestamp_format: str = DEFAULT_TIMESTAMP_FORMAT,
    ) -> None:
        """初始化流式输出器。

        Args:
            log_path: 日志文件路径
            max_lines: 终端显示的最大行数
            timestamp_format: 时间戳格式
        """
        self.log_path = log_path
        self.max_lines = max_lines
        self.timestamp_format = timestamp_format
        self.buffer: list[str] = []
        self.line_buffer = ""

        # 确保日志目录存在
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, chunk: str) -> None:
        """写入流式数据。

        处理可能的流式输出，支持部分行。
        """
        # 追加到行缓冲
        self.line_buffer += chunk

        # 检查是否有完整行
        while "\n" in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split("\n", 1)
            self._write_line(line)

    def _write_line(self, line: str) -> None:
        """写入完整行到文件和终端缓冲。"""
        timestamp = datetime.now().strftime(self.timestamp_format)
        full_line = f"{timestamp} | {line}"

        # 写入文件（完整内容）
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(full_line + "\n")

        # 更新滚动缓冲
        self.buffer.append(full_line)
        if len(self.buffer) > self.max_lines:
            self.buffer.pop(0)

        # 刷新终端显示
        self._refresh_display()

    def _refresh_display(self) -> None:
        """刷新终端显示（滚动窗口）。"""
        # 清除当前显示
        for _ in range(self.max_lines):
            # 上移一行并清除
            sys.stdout.write("\033[F\033[K")

        # 显示最新内容
        for line in self.buffer:
            sys.stdout.write(f"\033[2m{line}\033[0m\n")

        # 如果缓冲不足 max_lines，补充空行
        for _ in range(self.max_lines - len(self.buffer)):
            sys.stdout.write("\n")

        sys.stdout.flush()

    def flush(self) -> None:
        """刷新剩余的行缓冲内容。"""
        if self.line_buffer:
            self._write_line(self.line_buffer)
            self.line_buffer = ""

    def finalize(self) -> str:
        """完成输出，返回路径提示。"""
        self.flush()
        return f"📄 Full log: {self.log_path}"

    def get_callback(self) -> Callable[[str], None]:
        """返回一个回调函数，可用于 Driver 的 stream_callback 参数。"""
        return self.write


class AgentLogger:
    """Agent 输出日志器 — 带时间戳的行写入。

    用于记录 Agent 的完整输出，每行带时间戳前缀。
    """

    def __init__(
        self,
        log_path: Path,
        timestamp_format: str = DEFAULT_FULL_TIMESTAMP_FORMAT,
    ) -> None:
        """初始化 Agent 日志器。

        Args:
            log_path: 日志文件路径
            timestamp_format: 时间戳格式（完整格式）
        """
        self.log_path = log_path
        self.timestamp_format = timestamp_format

        # 确保日志目录存在
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write_line(self, line: str) -> None:
        """写入一行日志。

        Args:
            line: 日志内容（不含换行符）
        """
        ts = datetime.now()
        ts_str = ts.strftime(self.timestamp_format)[:-3]  # 去掉最后 3 位微秒
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts_str} | {line}\n")

    def write(self, content: str) -> None:
        """写入内容（支持多行）。

        Args:
            content: 日志内容
        """
        for line in content.splitlines():
            self.write_line(line)


def log_driver_call(
    log_path: Path,
    command: list[str],
    workdir: str,
    prompt: str,
    output: str,
    exit_code: int,
    duration: float,
    timeout: int | None = None,
) -> None:
    """记录 Driver CLI 调用详情。

    Args:
        log_path: 日志文件路径
        command: 完整的命令列表
        workdir: 工作目录
        prompt: 输入的 prompt（可能被截断）
        output: 输出内容
        exit_code: 退出码
        duration: 执行时长（秒）
        timeout: 超时设置（秒）
    """
    timestamp = datetime.now().strftime(DEFAULT_FULL_TIMESTAMP_FORMAT)[:-3]

    # 确保日志目录存在
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 截断过长的 prompt 和 output 以保持可读性
    prompt_display = prompt[:500] + "..." if len(prompt) > 500 else prompt
    output_display = output[:2000] + "..." if len(output) > 2000 else output

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"[DRIVER] {timestamp}\n")
        f.write(f"Command: {' '.join(command)}\n")
        f.write(f"Workdir: {workdir}\n")
        if timeout:
            f.write(f"Timeout: {timeout}s\n")
        f.write("-" * 80 + "\n")
        f.write("--- INPUT PROMPT ---\n")
        f.write(prompt_display)
        f.write("\n" + "-" * 80 + "\n")
        f.write("--- OUTPUT ---\n")
        f.write(output_display)
        f.write("\n" + "-" * 80 + "\n")
        f.write(f"Exit code: {exit_code}\n")
        f.write(f"Duration: {duration:.3f}s\n")
        f.write("=" * 80 + "\n\n")


def setup_system_logging(
    log_path: Path,
    level: int = logging.INFO,
) -> logging.Logger:
    """初始化系统日志。

    配置框架全局日志，输出到文件。

    Args:
        log_path: 系统日志文件路径
        level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    # 确保日志目录存在
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建文件 handler
    file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # 配置 reloop 日志器
    logger = logging.getLogger("reloop")
    logger.setLevel(level)
    logger.addHandler(file_handler)

    return logger


def get_run_log_paths(project_root: Path, run_id: str) -> dict[str, Path]:
    """获取指定 run 的所有日志路径。

    Args:
        project_root: 项目根目录
        run_id: run ID (如 "run-001")

    Returns:
        包含各日志文件路径的字典
    """
    run_dir = project_root / "run-sets" / run_id
    log_dir = run_dir / "logs"

    return {
        "driver": log_dir / "driver.log",
        "executor": log_dir / "executor.log",
        "evaluator": log_dir / "evaluator.log",
        "checker": log_dir / "checker.log",
        "prompt": log_dir / "prompt.log",
    }
