"""CursorDriver 单元测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reloop.drivers.base import Driver
from reloop.drivers.cursor import CursorDriver, CursorDriverError


class TestCursorDriverInit:
    """初始化行为测试"""

    def test_is_a_driver_subclass(self):
        assert issubclass(CursorDriver, Driver)

    def test_default_init(self):
        """默认初始化：yolo=True, trust=True（全自动）"""
        driver = CursorDriver()
        assert driver.model is None
        assert driver.yolo is True
        assert driver.trust is True
        assert driver.sandbox is None

    def test_custom_init(self):
        driver = CursorDriver(
            model="composer-2",
            yolo=False,
            trust=False,
            sandbox="enabled",
        )
        assert driver.model == "composer-2"
        assert driver.yolo is False
        assert driver.trust is False
        assert driver.sandbox == "enabled"

    def test_default_yolo_and_trust(self):
        """不传 yolo/trust 时默认 True（全自动）"""
        driver = CursorDriver(model="composer-2-fast")
        assert driver.yolo is True
        assert driver.trust is True


class TestCursorDriverBuildCommand:
    """命令构建测试"""

    def test_minimal_command(self):
        """最简命令：cursor agent -p --yolo --trust --workspace <dir> <prompt>"""
        driver = CursorDriver()
        cmd = driver._build_command(prompt="test prompt", workdir="/tmp")
        assert cmd[0] == "cursor"
        assert cmd[1] == "agent"
        assert "-p" in cmd
        assert "--yolo" in cmd
        assert "--trust" in cmd
        assert "--workspace" in cmd
        idx = cmd.index("--workspace")
        assert cmd[idx + 1] == "/tmp"
        assert cmd[-1] == "test prompt"

    def test_model_flag(self):
        driver = CursorDriver(model="composer-2-fast")
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "composer-2-fast"

    def test_no_yolo_flag_when_false(self):
        driver = CursorDriver(yolo=False)
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--yolo" not in cmd

    def test_no_trust_flag_when_false(self):
        driver = CursorDriver(trust=False)
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--trust" not in cmd

    def test_sandbox_flag(self):
        driver = CursorDriver(sandbox="disabled")
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--sandbox" in cmd
        idx = cmd.index("--sandbox")
        assert cmd[idx + 1] == "disabled"

    def test_no_model_flag_when_none(self):
        driver = CursorDriver()
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--model" not in cmd

    def test_no_sandbox_flag_when_none(self):
        driver = CursorDriver()
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--sandbox" not in cmd

    def test_prompt_is_last_arg(self):
        """prompt 应作为命令行最后一个参数"""
        driver = CursorDriver(model="composer-2-fast")
        cmd = driver._build_command(prompt="my prompt", workdir="/work")
        assert cmd[-1] == "my prompt"

    def test_full_command_with_all_options(self):
        driver = CursorDriver(
            model="composer-2",
            yolo=True,
            trust=True,
            sandbox="enabled",
        )
        cmd = driver._build_command(prompt="test prompt", workdir="/work")
        assert cmd == [
            "cursor", "agent", "-p",
            "--yolo",
            "--trust",
            "--model", "composer-2",
            "--sandbox", "enabled",
            "--workspace", "/work",
            "test prompt",
        ]


class TestCursorDriverBlockingRun:
    """阻塞模式执行测试"""

    def _make_completed_result(self, stdout: bytes, returncode: int = 0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = b""
        result.returncode = returncode
        return result

    def test_successful_run_returns_output(self):
        driver = CursorDriver()
        mock_result = self._make_completed_result(b"hello from cursor\n")

        with patch("subprocess.run", return_value=mock_result):
            result = driver._run_blocking(
                cmd=["cursor", "agent", "-p", "--yolo", "--trust", "test"],
                workdir="/tmp",
                timeout=None,
            )

        assert result == "hello from cursor"

    def test_nonzero_exit_raises_error(self):
        driver = CursorDriver()
        mock_result = self._make_completed_result(b"", returncode=1)
        mock_result.stderr = b"some error"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(CursorDriverError, match="exit 1"):
                driver._run_blocking(
                    cmd=["cursor", "agent", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                )

    def test_file_not_found_raises_error(self):
        driver = CursorDriver()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(CursorDriverError, match="cursor agent 命令未找到"):
                driver._run_blocking(
                    cmd=["cursor", "agent", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                )

    def test_timeout_raises_error(self):
        import subprocess

        driver = CursorDriver()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="cursor", timeout=5)):
            with pytest.raises(CursorDriverError, match="超时"):
                driver._run_blocking(
                    cmd=["cursor", "agent", "-p", "test"],
                    workdir="/tmp",
                    timeout=5,
                )

    def test_bytes_stdout_decoded(self):
        driver = CursorDriver()
        mock_result = self._make_completed_result("你好".encode("utf-8"))

        with patch("subprocess.run", return_value=mock_result):
            result = driver._run_blocking(
                cmd=["cursor", "agent", "-p", "test"],
                workdir="/tmp",
                timeout=None,
            )

        assert result == "你好"


class TestCursorDriverStreamingRun:
    """流式模式执行测试"""

    def _make_process(self, output_lines: list[str], returncode: int = 0):
        process = MagicMock()
        process.returncode = returncode
        process.pid = 12345

        stdout_mock = MagicMock()
        del stdout_mock.readable
        stdout_mock.__iter__ = lambda self: iter(output_lines)
        process.stdout = stdout_mock

        process.wait = MagicMock(return_value=returncode)
        return process

    def test_stream_callback_receives_lines(self):
        driver = CursorDriver()
        collected: list[str] = []
        process = self._make_process(["line one\n", "line two\n"])

        with patch("subprocess.Popen", return_value=process):
            driver._run_with_streaming(
                cmd=["cursor", "agent", "-p", "--yolo", "--trust", "test"],
                workdir="/tmp",
                timeout=None,
                stream_callback=lambda line: collected.append(line),
            )

        assert "line one" in collected
        assert "line two" in collected

    def test_file_not_found_raises_error(self):
        driver = CursorDriver()

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            with pytest.raises(CursorDriverError, match="cursor agent 命令未找到"):
                driver._run_with_streaming(
                    cmd=["cursor", "agent", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                    stream_callback=lambda _: None,
                )


class TestCursorDriverPublicRun:
    """run() 公开接口测试"""

    def test_run_calls_blocking_without_callback(self):
        driver = CursorDriver()

        with patch.object(CursorDriver, "_run_blocking", return_value="result") as mock_blocking:
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "result"
        mock_blocking.assert_called_once()

    def test_run_calls_streaming_with_callback(self):
        driver = CursorDriver()
        cb = lambda _: None

        with patch.object(CursorDriver, "_run_with_streaming", return_value="streamed") as mock_stream:
            result = driver.run(prompt="test", workdir="/tmp", stream_callback=cb)

        assert result == "streamed"
        mock_stream.assert_called_once()


class TestCursorDriverConfig:
    """通过 ReloopConfig 创建 CursorDriver 的集成测试"""

    def test_create_cursor_driver_from_config(self):
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "cursor",
                "cursor": {
                    "model": "composer-2-fast",
                    "yolo": True,
                    "trust": True,
                },
            }
        }

        driver = create_driver_from_type("cursor", cfg)
        assert isinstance(driver, CursorDriver)
        assert driver.model == "composer-2-fast"
        assert driver.yolo is True
        assert driver.trust is True

    def test_create_cursor_driver_minimal_config(self):
        """最小配置：只有 type，使用默认 yolo/trust"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "cursor",
                "cursor": {},
            }
        }

        driver = create_driver_from_type("cursor", cfg)
        assert isinstance(driver, CursorDriver)
        assert driver.model is None
        assert driver.yolo is True
        assert driver.trust is True

    def test_create_cursor_driver_no_config_section(self):
        """没有 cursor 配置段时，仍使用默认值"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {"driver": {"type": "cursor"}}

        driver = create_driver_from_type("cursor", cfg)
        assert isinstance(driver, CursorDriver)
        assert driver.model is None
        assert driver.yolo is True


class TestPerRoleCursorConfig:
    """Per-role 配置的集成测试"""

    def test_executor_uses_role_specific_model(self):
        """executor 有专属 model 配置时，覆盖默认值"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "cursor",
                "cursor": {"model": "composer-2-fast", "yolo": True, "trust": True},
                "executor": {
                    "type": "cursor",
                    "cursor": {"model": "composer-2"},  # executor 用更强模型
                },
            }
        }

        driver = create_driver_from_type("cursor", cfg, role="executor")
        assert driver.model == "composer-2"         # executor 专属覆盖
        assert driver.yolo is True                   # 从默认继承
        assert driver.trust is True                  # 从默认继承

    def test_evaluator_uses_role_specific_config(self):
        """evaluator 有专属配置时，独立于 executor"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "cursor",
                "cursor": {"model": "composer-2-fast", "yolo": True, "trust": True},
                "executor": {
                    "type": "cursor",
                    "cursor": {"model": "composer-2"},
                },
                "evaluator": {
                    "type": "cursor",
                    "cursor": {"model": "composer-2-fast", "trust": False},
                },
            }
        }

        executor = create_driver_from_type("cursor", cfg, role="executor")
        evaluator = create_driver_from_type("cursor", cfg, role="evaluator")

        assert executor.model == "composer-2"
        assert executor.trust is True

        assert evaluator.model == "composer-2-fast"
        assert evaluator.trust is False              # evaluator 专属覆盖