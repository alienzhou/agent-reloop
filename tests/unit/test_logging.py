"""日志系统测试"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from reloop.core.logging import (
    AgentLogger,
    StreamOutput,
    get_run_log_paths,
    log_driver_call,
    setup_system_logging,
)


class TestStreamOutput:
    """StreamOutput 类测试"""

    def test_write_single_line(self, tmp_path):
        """测试单行写入"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path, max_lines=4)

        stream.write("Hello\n")
        stream.flush()

        content = log_path.read_text()
        assert "Hello" in content

    def test_write_multiple_lines(self, tmp_path):
        """测试多行写入"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path, max_lines=2)

        stream.write("Line 1\nLine 2\nLine 3\n")
        stream.flush()

        content = log_path.read_text()
        assert "Line 1" in content
        assert "Line 2" in content
        assert "Line 3" in content

    def test_buffer_rolling(self, tmp_path):
        """测试滚动缓冲区"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path, max_lines=2)

        stream.write("Line 1\nLine 2\nLine 3\n")
        stream.flush()

        # 缓冲区应该只有最近 2 行
        assert len(stream.buffer) == 2
        assert "Line 2" in stream.buffer[0]
        assert "Line 3" in stream.buffer[1]

    def test_partial_line(self, tmp_path):
        """测试部分行（无换行符）"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path, max_lines=4)

        stream.write("Partial")
        # 不应该写入文件
        assert not log_path.exists() or log_path.read_text() == ""

        stream.write("\n")
        stream.flush()

        # 现在应该写入
        content = log_path.read_text()
        assert "Partial" in content

    def test_finalize(self, tmp_path):
        """测试 finalize 方法"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path, max_lines=4)

        stream.write("Test content\n")
        result = stream.finalize()

        assert str(log_path) in result

    def test_get_callback(self, tmp_path):
        """测试获取回调函数"""
        log_path = tmp_path / "test.log"
        stream = StreamOutput(log_path)

        callback = stream.get_callback()
        assert callable(callback)

        callback("Test line\n")
        stream.flush()

        content = log_path.read_text()
        assert "Test line" in content


class TestAgentLogger:
    """AgentLogger 类测试"""

    def test_write_line(self, tmp_path):
        """测试单行写入"""
        log_path = tmp_path / "agent.log"
        logger = AgentLogger(log_path)

        logger.write_line("Test message")

        content = log_path.read_text()
        assert "Test message" in content
        # 检查时间戳格式
        assert "|" in content

    def test_write_multiline(self, tmp_path):
        """测试多行写入"""
        log_path = tmp_path / "agent.log"
        logger = AgentLogger(log_path)

        logger.write("Line 1\nLine 2\nLine 3")

        content = log_path.read_text()
        assert content.count("|") == 3

    def test_timestamp_format(self, tmp_path):
        """测试时间戳格式"""
        log_path = tmp_path / "agent.log"
        logger = AgentLogger(log_path)

        logger.write_line("Test")

        content = log_path.read_text()
        # 格式：YYYY-MM-DD HH:MM:SS.SSS | message
        parts = content.split("|")
        timestamp_part = parts[0].strip()
        # 应该能解析为 datetime
        datetime.strptime(timestamp_part, "%Y-%m-%d %H:%M:%S.%f")


class TestLogDriverCall:
    """log_driver_call 函数测试"""

    def test_basic_call(self, tmp_path):
        """测试基本调用记录"""
        log_path = tmp_path / "driver.log"

        log_driver_call(
            log_path=log_path,
            command=["claude", "--print"],
            workdir="/workspace",
            prompt="Test prompt",
            output="Test output",
            exit_code=0,
            duration=1.234,
        )

        content = log_path.read_text()
        assert "claude --print" in content
        assert "/workspace" in content
        assert "Test prompt" in content
        assert "Test output" in content
        assert "Exit code: 0" in content
        assert "Duration: 1.234s" in content

    def test_long_prompt_truncation(self, tmp_path):
        """测试长 prompt 截断"""
        log_path = tmp_path / "driver.log"
        long_prompt = "x" * 1000

        log_driver_call(
            log_path=log_path,
            command=["test"],
            workdir="/workspace",
            prompt=long_prompt,
            output="output",
            exit_code=0,
            duration=0.1,
        )

        content = log_path.read_text()
        # prompt 应该被截断到 500 字符
        assert content.count("x") <= 503  # 500 + "..."

    def test_timeout_record(self, tmp_path):
        """测试超时记录"""
        log_path = tmp_path / "driver.log"

        log_driver_call(
            log_path=log_path,
            command=["test"],
            workdir="/workspace",
            prompt="prompt",
            output="output",
            exit_code=0,
            duration=1.0,
            timeout=300,
        )

        content = log_path.read_text()
        assert "Timeout: 300s" in content


class TestSetupSystemLogging:
    """setup_system_logging 函数测试"""

    def test_creates_log_file(self, tmp_path):
        """测试创建日志文件"""
        log_path = tmp_path / "logs" / "reloop.log"

        logger = setup_system_logging(log_path)

        assert log_path.exists()
        assert logger.name == "reloop"

    def test_log_write(self, tmp_path):
        """测试日志写入"""
        log_path = tmp_path / "logs" / "reloop.log"

        logger = setup_system_logging(log_path)
        logger.info("Test message")

        content = log_path.read_text()
        assert "Test message" in content
        assert "[INFO]" in content


class TestGetRunLogPaths:
    """get_run_log_paths 函数测试"""

    def test_returns_all_paths(self, tmp_path):
        """测试返回所有日志路径"""
        paths = get_run_log_paths(tmp_path, "run-001")

        assert paths["driver"] == tmp_path / "run-sets" / "run-001" / "logs" / "driver.log"
        assert paths["executor"] == tmp_path / "run-sets" / "run-001" / "logs" / "executor.log"
        assert paths["evaluator"] == tmp_path / "run-sets" / "run-001" / "logs" / "evaluator.log"
        assert paths["checker"] == tmp_path / "run-sets" / "run-001" / "logs" / "checker.log"
        assert paths["prompt"] == tmp_path / "run-sets" / "run-001" / "logs" / "prompt.log"
