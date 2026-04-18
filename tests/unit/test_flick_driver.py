"""FlickDriver 单元测试。"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from reloop.drivers.flick import FlickDriver, FlickDriverError


class TestFlickDriverInit:
    """测试 FlickDriver 初始化。"""

    def test_init_with_required_workspace(self):
        """workspace 是必需参数。"""
        driver = FlickDriver(workspace="test-workspace")
        assert driver.workspace == "test-workspace"
        assert driver.model is None
        assert driver.mode is None
        assert driver.json_output is True

    def test_init_with_all_options(self):
        """测试所有可选参数。"""
        driver = FlickDriver(
            workspace="my-workspace",
            model="CLAUDE_4_5",
            mode="agent",
            json_output=False,
        )
        assert driver.workspace == "my-workspace"
        assert driver.model == "CLAUDE_4_5"
        assert driver.mode == "agent"
        assert driver.json_output is False

    def test_init_empty_workspace_raises(self):
        """空 workspace 抛出异常。"""
        with pytest.raises(FlickDriverError, match="workspace 参数是必需的"):
            FlickDriver(workspace="")


class TestFlickDriverBuildCommand:
    """测试 _build_command 方法。"""

    def test_build_command_minimal(self):
        """最小配置的命令构建。"""
        driver = FlickDriver(workspace="ws-123")
        cmd = driver._build_command("hello")
        assert cmd == [
            "flick",
            "link",
            "prompt",
            "--duet-workspace",
            "ws-123",
            "--duet-json",
            "hello",
        ]

    def test_build_command_with_model(self):
        """带 model 参数的命令构建。"""
        driver = FlickDriver(workspace="ws-123", model="AUTO")
        cmd = driver._build_command("test")
        assert "--duet-model" in cmd
        assert "AUTO" in cmd

    def test_build_command_with_mode(self):
        """带 mode 参数的命令构建。"""
        driver = FlickDriver(workspace="ws-123", mode="plan")
        cmd = driver._build_command("test")
        assert "--duet-mode" in cmd
        assert "plan" in cmd

    def test_build_command_no_json(self):
        """禁用 JSON 输出。"""
        driver = FlickDriver(workspace="ws-123", json_output=False)
        cmd = driver._build_command("test")
        assert "--duet-json" not in cmd


class TestFlickDriverStreaming:
    """测试流式输出功能。"""

    def test_stream_callback_called_for_each_line(self):
        """流式回调对每行输出被调用。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []

        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        mock_process.stdout = iter(["Line 1\n", "Line 2\n", "Line 3\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            result = driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        assert collected_lines == ["Line 1", "Line 2", "Line 3"]
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_stream_callback_strips_newlines(self):
        """流式回调去除行尾换行符。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []

        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        mock_process.stdout = iter(["No newline", "With newline\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        # 两行都没有换行符
        assert collected_lines == ["No newline", "With newline"]

    def test_streaming_timeout_kills_process(self):
        """流式模式超时时终止进程。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_process = MagicMock()
        mock_process.stdout = iter([])
        # 第一次调用（带 timeout）抛异常，第二次调用（无参数）正常返回
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="flick", timeout=10),
            None,  # kill 后的 wait() 正常返回
        ]

        with patch("subprocess.Popen", return_value=mock_process):
            with pytest.raises(FlickDriverError, match="超时"):
                driver.run(
                    prompt="test",
                    workdir="/tmp",
                    timeout=10,
                    stream_callback=lambda x: None,
                )

        mock_process.kill.assert_called_once()

    def test_streaming_nonzero_exit_raises(self):
        """流式模式非零退出码抛出异常。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_process = MagicMock()
        mock_process.stdout = iter(["some output\n"])
        mock_process.returncode = 1
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            with pytest.raises(FlickDriverError, match="失败"):
                driver.run(
                    prompt="test",
                    workdir="/tmp",
                    stream_callback=lambda x: None,
                )


class TestFlickDriverBlocking:
    """测试阻塞模式（无回调）。"""

    def test_no_callback_uses_blocking_mode(self):
        """无回调时使用阻塞模式。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response text"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = driver.run(prompt="test", workdir="/tmp")

        mock_run.assert_called_once()
        assert result == "Response text"

    def test_blocking_timeout_raises(self):
        """阻塞模式超时抛出异常。"""
        driver = FlickDriver(workspace="test-workspace")

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="flick", timeout=30),
        ):
            with pytest.raises(FlickDriverError, match="超时"):
                driver.run(prompt="test", workdir="/tmp", timeout=30)

    def test_blocking_command_not_found(self):
        """阻塞模式命令未找到抛出异常。"""
        driver = FlickDriver(workspace="test-workspace")

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(FlickDriverError, match="flick 命令未找到"):
                driver.run(prompt="test", workdir="/tmp")

    def test_blocking_nonzero_exit_raises(self):
        """阻塞模式非零退出码抛出异常。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Some error"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(FlickDriverError, match="失败"):
                driver.run(prompt="test", workdir="/tmp")


class TestFlickDriverJsonParsing:
    """测试 JSON 响应解析。"""

    def test_parse_json_with_content_field(self):
        """解析包含 content 字段的 JSON。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"content": "Extracted content"}'

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Extracted content"

    def test_parse_json_with_message_field(self):
        """解析包含 message 字段的 JSON（fallback）。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"message": "Message content"}'

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Message content"

    def test_parse_invalid_json_returns_raw(self):
        """无效 JSON 返回原始文本。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Not valid JSON"

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Not valid JSON"

    def test_json_output_disabled(self):
        """禁用 JSON 输出时不解析。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"content": "Should not parse"}'

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        # 原样返回
        assert result == '{"content": "Should not parse"}'


class TestFlickDriverStreamingFileNotFound:
    """测试流式模式命令未找到场景。"""

    def test_streaming_command_not_found(self):
        """流式模式命令未找到抛出异常。"""
        driver = FlickDriver(workspace="test-workspace")

        with patch("subprocess.Popen", side_effect=FileNotFoundError()):
            with pytest.raises(FlickDriverError, match="flick 命令未找到"):
                driver.run(
                    prompt="test",
                    workdir="/tmp",
                    stream_callback=lambda x: None,
                )
