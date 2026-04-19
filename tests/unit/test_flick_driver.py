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
    """测试 JSON Lines 响应解析。"""

    def test_parse_json_lines_format(self):
        """测试 JSON Lines 格式解析。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Hello"}}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": " World"}}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Hello World"

    def test_parse_json_lines_with_checker_output(self):
        """测试 Checker 格式的 JSON Lines 输出解析。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "<checker_result>passed</checker_result>"}}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert "<checker_result>passed</checker_result>" in result

    def test_parse_json_lines_multiline_text(self):
        """测试多个 text chunk 拼接。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Line 1\\n"}}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Line 2\\n"}}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Line 3"}}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Line 1\nLine 2\nLine 3"

    def test_parse_json_lines_ignores_non_text_updates(self):
        """测试忽略非 text 类型的 update。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "update", "updateType": "tool_use", "content": {"type": "tool_call", "name": "read_file"}}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Result"}}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Result"

    def test_parse_json_lines_empty_text_ignored(self):
        """测试空 text 被忽略。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": ""}}
{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Hello"}}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Hello"

    def test_parse_json_lines_no_text_returns_original(self):
        """测试无 text chunk 时返回原始响应。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}
{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        # 无 text 时返回原始响应
        assert result == json_lines_output

    def test_parse_invalid_json_returns_raw(self):
        """无效 JSON 返回原始文本（作为 text chunk 处理）。"""
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

    def test_parse_json_lines_with_blank_lines(self):
        """测试包含空行的 JSON Lines。"""
        driver = FlickDriver(workspace="test-workspace")

        json_lines_output = '''{"type": "session_created", "threadId": "th_123"}

{"type": "update", "updateType": "agent_message_chunk", "content": {"type": "text", "text": "Hello"}}

{"type": "end", "stopReason": "end_turn"}'''

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json_lines_output

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Hello"


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


class TestFlickDriverEdgeCases:
    """测试边界条件和特殊场景。"""

    def test_empty_output_returns_empty_string(self):
        """阻塞模式空输出返回空字符串。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == ""

    def test_streaming_empty_output(self):
        """流式模式空输出返回空字符串。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []

        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        mock_process.stdout = iter([])  # 空输出
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            result = driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        assert result == ""
        assert collected_lines == []

    def test_no_timeout_waits_indefinitely(self):
        """timeout=None 时不设置超时限制。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            driver.run(prompt="test", workdir="/tmp", timeout=None)

        # 验证 subprocess.run 被调用时 timeout=None
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("timeout") is None

    def test_workdir_passed_to_subprocess(self):
        """workdir 参数正确传递给 subprocess。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"

        test_workdir = "/custom/work/directory"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            driver.run(prompt="test", workdir=test_workdir)

        # 验证 subprocess.run 被调用时 cwd 参数正确
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == test_workdir


class TestFlickDriverUtf8Encoding:
    """测试 UTF-8 编码处理（P1 测试覆盖修复）。"""

    def test_blocking_mode_handles_bytes_output(self):
        """阻塞模式正确处理 bytes 输出。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"Hello World"  # bytes 类型

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "Hello World"

    def test_blocking_mode_handles_incomplete_utf8(self):
        """阻塞模式处理不完整的 UTF-8 字节序列。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        # 不完整的 UTF-8 序列：0xe5 是中文字符的起始字节，但缺少后续字节
        incomplete_utf8 = b"Hello \xe5 World"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = incomplete_utf8

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        # errors='replace' 应该将无效字节替换为 �
        assert "Hello" in result
        assert "World" in result
        assert "�" in result  # 替换字符

    def test_blocking_mode_handles_chinese_characters(self):
        """阻塞模式正确处理中文字符。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        chinese_text = "你好世界"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = chinese_text.encode('utf-8')  # 正确的 UTF-8 编码

        with patch("subprocess.run", return_value=mock_result):
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == chinese_text

    def test_blocking_mode_nonzero_exit_with_bytes_stderr(self):
        """阻塞模式非零退出码时正确解码 bytes stderr。"""
        driver = FlickDriver(workspace="test-workspace")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"Error message"  # bytes 类型

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(FlickDriverError, match="Error message"):
                driver.run(prompt="test", workdir="/tmp")

    def test_streaming_mode_handles_bytes_lines(self):
        """流式模式正确处理 bytes 行。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []
        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        # 模拟返回 bytes 行
        mock_process.stdout = iter([b"Line 1\n", b"Line 2\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            result = driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        assert collected_lines == ["Line 1", "Line 2"]

    def test_streaming_mode_handles_incomplete_utf8_bytes(self):
        """流式模式处理不完整的 UTF-8 字节序列。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []
        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        # 不完整的 UTF-8 序列
        mock_process.stdout = iter([b"Hello \xe5 World\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            result = driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        # 应该有输出，且包含替换字符
        assert len(collected_lines) == 1
        assert "Hello" in collected_lines[0]
        assert "�" in collected_lines[0]


class TestFlickDriverRobustness:
    """测试健壮性（P1 边界条件修复）。"""

    def test_streaming_mode_stdout_none_raises_error(self):
        """流式模式 stdout 为 None 时抛出异常。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        mock_process = MagicMock()
        mock_process.stdout = None  # stdout 为 None

        with patch("subprocess.Popen", return_value=mock_process):
            with pytest.raises(FlickDriverError, match="stdout is None"):
                driver.run(
                    prompt="test",
                    workdir="/tmp",
                    stream_callback=lambda x: None,
                )

    def test_streaming_mode_mixed_str_and_bytes(self):
        """流式模式处理混合的字符串和字节输出。"""
        driver = FlickDriver(workspace="test-workspace", json_output=False)

        collected_lines = []
        def callback(line: str):
            collected_lines.append(line)

        mock_process = MagicMock()
        # 混合 str 和 bytes（模拟 mock 场景）
        mock_process.stdout = iter(["String line\n", b"Bytes line\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            result = driver.run(
                prompt="test",
                workdir="/tmp",
                stream_callback=callback,
            )

        assert "String line" in collected_lines
        assert "Bytes line" in collected_lines
