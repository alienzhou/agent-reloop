"""CodexDriver 单元测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reloop.drivers.base import Driver
from reloop.drivers.codex import CodexDriver, CodexDriverError


class TestCodexDriverInit:
    """初始化行为测试"""

    def test_is_a_driver_subclass(self):
        assert issubclass(CodexDriver, Driver)

    def test_default_init(self):
        driver = CodexDriver()
        assert driver.model is None
        assert driver.sandbox is None
        assert driver.approval is None

    def test_custom_init(self):
        driver = CodexDriver(model="o4-mini", sandbox="workspace-write", approval="auto")
        assert driver.model == "o4-mini"
        assert driver.sandbox == "workspace-write"
        assert driver.approval == "auto"


class TestCodexDriverBuildCommand:
    """命令构建测试"""

    def test_minimal_command(self):
        driver = CodexDriver()
        cmd = driver._build_command(workdir="/tmp")
        assert cmd[0] == "codex"
        assert cmd[1] == "exec"
        assert "-C" in cmd
        assert "/tmp" in cmd
        assert "-" in cmd  # stdin 标志

    def test_model_flag(self):
        driver = CodexDriver(model="o4-mini")
        cmd = driver._build_command(workdir="/tmp")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "o4-mini"

    def test_sandbox_flag(self):
        driver = CodexDriver(sandbox="workspace-write")
        cmd = driver._build_command(workdir="/tmp")
        assert "--sandbox" in cmd
        idx = cmd.index("--sandbox")
        assert cmd[idx + 1] == "workspace-write"

    def test_approval_flag(self):
        driver = CodexDriver(approval="auto")
        cmd = driver._build_command(workdir="/tmp")
        assert "--approval" in cmd
        idx = cmd.index("--approval")
        assert cmd[idx + 1] == "auto"

    def test_output_flag(self):
        driver = CodexDriver()
        cmd = driver._build_command(workdir="/tmp", output="/out/file.txt")
        assert "-o" in cmd
        idx = cmd.index("-o")
        assert cmd[idx + 1] == "/out/file.txt"

    def test_no_model_flag_when_none(self):
        driver = CodexDriver()
        cmd = driver._build_command(workdir="/tmp")
        assert "--model" not in cmd

    def test_stdin_dash_is_last_arg(self):
        driver = CodexDriver(model="o3")
        cmd = driver._build_command(workdir="/tmp")
        assert cmd[-1] == "-"


class TestCodexDriverBlockingRun:
    """阻塞模式执行测试"""

    def _make_completed_result(self, stdout: bytes, returncode: int = 0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = b""
        result.returncode = returncode
        return result

    def test_successful_run_returns_output(self):
        driver = CodexDriver()
        mock_result = self._make_completed_result(b"hello from codex\n")

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = driver._run_blocking(
                cmd=["codex", "exec", "-C", "/tmp", "-"],
                prompt="do something",
                workdir="/tmp",
                timeout=None,
            )

        assert result == "hello from codex"
        # 确认 prompt 通过 stdin 传入
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["input"] == b"do something"

    def test_nonzero_exit_raises_error(self):
        driver = CodexDriver()
        mock_result = self._make_completed_result(b"", returncode=1)
        mock_result.stderr = b"some error"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(CodexDriverError, match="exit 1"):
                driver._run_blocking(
                    cmd=["codex", "exec", "-"],
                    prompt="p",
                    workdir="/tmp",
                    timeout=None,
                )

    def test_file_not_found_raises_error(self):
        driver = CodexDriver()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(CodexDriverError, match="codex 命令未找到"):
                driver._run_blocking(
                    cmd=["codex", "exec", "-"],
                    prompt="p",
                    workdir="/tmp",
                    timeout=None,
                )

    def test_timeout_raises_error(self):
        import subprocess

        driver = CodexDriver()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=5)):
            with pytest.raises(CodexDriverError, match="超时"):
                driver._run_blocking(
                    cmd=["codex", "exec", "-"],
                    prompt="p",
                    workdir="/tmp",
                    timeout=5,
                )

    def test_bytes_stdout_decoded(self):
        driver = CodexDriver()
        mock_result = self._make_completed_result("你好".encode("utf-8"))

        with patch("subprocess.run", return_value=mock_result):
            result = driver._run_blocking(
                cmd=["codex", "exec", "-"],
                prompt="p",
                workdir="/tmp",
                timeout=None,
            )

        assert result == "你好"


class TestCodexDriverStreamingRun:
    """流式模式执行测试"""

    def _make_process(self, output_lines: list[str], returncode: int = 0):
        """构造模拟 subprocess.Popen 返回值。"""
        process = MagicMock()
        process.returncode = returncode
        process.pid = 12345
        process.stdin = MagicMock()

        # stdout：使用普通 MagicMock，__iter__ 返回行迭代器
        # 不设置 readable，使 TextIOWrapper 包装逻辑跳过（走 bytes 分支）
        stdout_mock = MagicMock()
        del stdout_mock.readable  # 删除 readable 属性，让 hasattr 返回 False
        stdout_mock.__iter__ = lambda self: iter(output_lines)
        process.stdout = stdout_mock

        process.wait = MagicMock(return_value=returncode)
        return process

    def test_stream_callback_receives_lines(self):
        driver = CodexDriver()
        collected: list[str] = []
        process = self._make_process(["line one\n", "line two\n"])

        with patch("subprocess.Popen", return_value=process):
            driver._run_with_streaming(
                cmd=["codex", "exec", "-"],
                prompt="p",
                workdir="/tmp",
                timeout=None,
                stream_callback=lambda line: collected.append(line),
            )

        assert "line one" in collected
        assert "line two" in collected

    def test_file_not_found_raises_error(self):
        driver = CodexDriver()

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            with pytest.raises(CodexDriverError, match="codex 命令未找到"):
                driver._run_with_streaming(
                    cmd=["codex", "exec", "-"],
                    prompt="p",
                    workdir="/tmp",
                    timeout=None,
                    stream_callback=lambda _: None,
                )


class TestCodexDriverPublicRun:
    """run() 公开接口测试"""

    def test_run_calls_blocking_without_callback(self):
        driver = CodexDriver()

        with patch.object(CodexDriver, "_run_blocking", return_value="result") as mock_blocking:
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "result"
        mock_blocking.assert_called_once()

    def test_run_calls_streaming_with_callback(self):
        driver = CodexDriver()
        cb = lambda _: None

        with patch.object(CodexDriver, "_run_with_streaming", return_value="streamed") as mock_stream:
            result = driver.run(prompt="test", workdir="/tmp", stream_callback=cb)

        assert result == "streamed"
        mock_stream.assert_called_once()

    def test_run_passes_prompt_to_blocking(self):
        driver = CodexDriver()

        with patch.object(CodexDriver, "_run_blocking", return_value="ok") as mock_blocking:
            driver.run(prompt="my prompt", workdir="/work", timeout=60)

        args = mock_blocking.call_args
        # _run_blocking(cmd, prompt, workdir, timeout)，prompt 是第二个位置参数
        assert args[0][1] == "my prompt"


class TestCodexDriverConfig:
    """通过 ReloopConfig 创建 CodexDriver 的集成测试"""

    def test_create_codex_driver_from_config(self):
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "codex",
                "codex": {
                    "model": "o4-mini",
                    "sandbox": "workspace-write",
                    "approval": "auto",
                },
            }
        }

        driver = create_driver_from_type("codex", cfg)
        assert isinstance(driver, CodexDriver)
        assert driver.model == "o4-mini"
        assert driver.sandbox == "workspace-write"
        assert driver.approval == "auto"

    def test_create_codex_driver_minimal_config(self):
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "codex",
                "codex": {},
            }
        }

        driver = create_driver_from_type("codex", cfg)
        assert isinstance(driver, CodexDriver)
        assert driver.model is None
