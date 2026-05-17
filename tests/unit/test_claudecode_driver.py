"""ClaudeCodeDriver 单元测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reloop.drivers.base import Driver
from reloop.drivers.claudecode import ClaudeCodeDriver, ClaudeCodeDriverError


class TestClaudeCodeDriverInit:
    """初始化行为测试"""

    def test_is_a_driver_subclass(self):
        assert issubclass(ClaudeCodeDriver, Driver)

    def test_default_init(self):
        """默认初始化：permission_mode 应为 bypassPermissions"""
        driver = ClaudeCodeDriver()
        assert driver.model is None
        assert driver.permission_mode == "bypassPermissions"
        assert driver.max_budget_usd is None
        assert driver.add_dirs is None

    def test_custom_init(self):
        driver = ClaudeCodeDriver(
            model="opus",
            permission_mode="auto",
            max_budget_usd=5.0,
            add_dirs=["/tmp/project"],
        )
        assert driver.model == "opus"
        assert driver.permission_mode == "auto"
        assert driver.max_budget_usd == 5.0
        assert driver.add_dirs == ["/tmp/project"]

    def test_default_permission_mode_is_bypass(self):
        """不传 permission_mode 时默认 bypassPermissions（全自动）"""
        driver = ClaudeCodeDriver(model="sonnet")
        assert driver.permission_mode == "bypassPermissions"


class TestClaudeCodeDriverBuildCommand:
    """命令构建测试"""

    def test_minimal_command(self):
        """最简命令：claude -p --permission-mode bypassPermissions + prompt"""
        driver = ClaudeCodeDriver()
        cmd = driver._build_command(prompt="do something", workdir="/tmp")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "bypassPermissions"
        assert cmd[-1] == "do something"

    def test_model_flag(self):
        driver = ClaudeCodeDriver(model="sonnet")
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "sonnet"

    def test_permission_mode_flag(self):
        driver = ClaudeCodeDriver(permission_mode="dontAsk")
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "dontAsk"

    def test_max_budget_usd_flag(self):
        driver = ClaudeCodeDriver(max_budget_usd=5.0)
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--max-budget-usd" in cmd
        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "5.0"

    def test_add_dirs_flag(self):
        driver = ClaudeCodeDriver(add_dirs=["/dir1", "/dir2"])
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--add-dir" in cmd
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == "/dir1"
        idx2 = cmd.index("--add-dir", idx + 2)
        assert cmd[idx2 + 1] == "/dir2"

    def test_no_model_flag_when_none(self):
        driver = ClaudeCodeDriver()
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--model" not in cmd

    def test_no_budget_flag_when_none(self):
        driver = ClaudeCodeDriver()
        cmd = driver._build_command(prompt="test", workdir="/tmp")
        assert "--max-budget-usd" not in cmd

    def test_prompt_is_last_arg(self):
        """prompt 应作为命令行最后一个参数"""
        driver = ClaudeCodeDriver(model="sonnet")
        cmd = driver._build_command(prompt="my prompt here", workdir="/tmp")
        assert cmd[-1] == "my prompt here"

    def test_full_command_with_all_options(self):
        """所有选项都指定时的完整命令"""
        driver = ClaudeCodeDriver(
            model="opus",
            permission_mode="bypassPermissions",
            max_budget_usd=10.0,
            add_dirs=["/extra"],
        )
        cmd = driver._build_command(prompt="test prompt", workdir="/work")
        assert cmd == [
            "claude", "-p",
            "--permission-mode", "bypassPermissions",
            "--model", "opus",
            "--max-budget-usd", "10.0",
            "--add-dir", "/extra",
            "test prompt",
        ]


class TestClaudeCodeDriverBlockingRun:
    """阻塞模式执行测试"""

    def _make_completed_result(self, stdout: bytes, returncode: int = 0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = b""
        result.returncode = returncode
        return result

    def test_successful_run_returns_output(self):
        driver = ClaudeCodeDriver()
        mock_result = self._make_completed_result(b"hello from claude\n")

        with patch("subprocess.run", return_value=mock_result):
            result = driver._run_blocking(
                cmd=["claude", "-p", "--permission-mode", "bypassPermissions", "test"],
                workdir="/tmp",
                timeout=None,
            )

        assert result == "hello from claude"

    def test_nonzero_exit_raises_error(self):
        driver = ClaudeCodeDriver()
        mock_result = self._make_completed_result(b"", returncode=1)
        mock_result.stderr = b"some error"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(ClaudeCodeDriverError, match="exit 1"):
                driver._run_blocking(
                    cmd=["claude", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                )

    def test_file_not_found_raises_error(self):
        driver = ClaudeCodeDriver()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ClaudeCodeDriverError, match="claude 命令未找到"):
                driver._run_blocking(
                    cmd=["claude", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                )

    def test_timeout_raises_error(self):
        import subprocess

        driver = ClaudeCodeDriver()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=5)):
            with pytest.raises(ClaudeCodeDriverError, match="超时"):
                driver._run_blocking(
                    cmd=["claude", "-p", "test"],
                    workdir="/tmp",
                    timeout=5,
                )

    def test_bytes_stdout_decoded(self):
        driver = ClaudeCodeDriver()
        mock_result = self._make_completed_result("你好".encode("utf-8"))

        with patch("subprocess.run", return_value=mock_result):
            result = driver._run_blocking(
                cmd=["claude", "-p", "test"],
                workdir="/tmp",
                timeout=None,
            )

        assert result == "你好"


class TestClaudeCodeDriverStreamingRun:
    """流式模式执行测试"""

    def _make_process(self, output_lines: list[str], returncode: int = 0):
        """构造模拟 subprocess.Popen 返回值。"""
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
        driver = ClaudeCodeDriver()
        collected: list[str] = []
        process = self._make_process(["line one\n", "line two\n"])

        with patch("subprocess.Popen", return_value=process):
            driver._run_with_streaming(
                cmd=["claude", "-p", "--permission-mode", "bypassPermissions", "test"],
                workdir="/tmp",
                timeout=None,
                stream_callback=lambda line: collected.append(line),
            )

        assert "line one" in collected
        assert "line two" in collected

    def test_file_not_found_raises_error(self):
        driver = ClaudeCodeDriver()

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            with pytest.raises(ClaudeCodeDriverError, match="claude 命令未找到"):
                driver._run_with_streaming(
                    cmd=["claude", "-p", "test"],
                    workdir="/tmp",
                    timeout=None,
                    stream_callback=lambda _: None,
                )


class TestClaudeCodeDriverPublicRun:
    """run() 公开接口测试"""

    def test_run_calls_blocking_without_callback(self):
        driver = ClaudeCodeDriver()

        with patch.object(ClaudeCodeDriver, "_run_blocking", return_value="result") as mock_blocking:
            result = driver.run(prompt="test", workdir="/tmp")

        assert result == "result"
        mock_blocking.assert_called_once()

    def test_run_calls_streaming_with_callback(self):
        driver = ClaudeCodeDriver()
        cb = lambda _: None

        with patch.object(ClaudeCodeDriver, "_run_with_streaming", return_value="streamed") as mock_stream:
            result = driver.run(prompt="test", workdir="/tmp", stream_callback=cb)

        assert result == "streamed"
        mock_stream.assert_called_once()


class TestClaudeCodeDriverConfig:
    """通过 ReloopConfig 创建 ClaudeCodeDriver 的集成测试"""

    def test_create_claudecode_driver_from_config(self):
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {
                    "model": "sonnet",
                    "permission_mode": "bypassPermissions",
                    "max_budget_usd": 5.0,
                },
            }
        }

        driver = create_driver_from_type("claudecode", cfg)
        assert isinstance(driver, ClaudeCodeDriver)
        assert driver.model == "sonnet"
        assert driver.permission_mode == "bypassPermissions"
        assert driver.max_budget_usd == 5.0

    def test_create_claudecode_driver_minimal_config(self):
        """最小配置：只有 type，使用默认 permission_mode"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {},
            }
        }

        driver = create_driver_from_type("claudecode", cfg)
        assert isinstance(driver, ClaudeCodeDriver)
        assert driver.model is None
        assert driver.permission_mode == "bypassPermissions"

    def test_create_claudecode_driver_no_config_section(self):
        """没有 claudecode 配置段时，仍使用默认值"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {"driver": {"type": "claudecode"}}

        driver = create_driver_from_type("claudecode", cfg)
        assert isinstance(driver, ClaudeCodeDriver)
        assert driver.model is None
        assert driver.permission_mode == "bypassPermissions"


class TestPerRoleClaudeCodeConfig:
    """Per-role 配置的集成测试"""

    def test_executor_uses_default_config_when_no_role_specific(self):
        """没有 executor 专属配置时，使用默认配置"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {"model": "sonnet", "permission_mode": "bypassPermissions"},
            }
        }

        driver = create_driver_from_type("claudecode", cfg, role="executor")
        assert driver.model == "sonnet"
        assert driver.permission_mode == "bypassPermissions"

    def test_executor_uses_role_specific_model(self):
        """executor 有专属 model 配置时，覆盖默认值"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {"model": "sonnet", "permission_mode": "bypassPermissions"},
                "executor": {
                    "type": "claudecode",
                    "claudecode": {"model": "opus"},  # executor 用更强模型
                },
            }
        }

        driver = create_driver_from_type("claudecode", cfg, role="executor")
        assert driver.model == "opus"                      # executor 专属覆盖
        assert driver.permission_mode == "bypassPermissions"  # 从默认继承

    def test_evaluator_uses_role_specific_config(self):
        """evaluator 有专属配置时，独立于 executor"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {"model": "sonnet", "permission_mode": "bypassPermissions"},
                "executor": {
                    "type": "claudecode",
                    "claudecode": {"model": "opus"},
                },
                "evaluator": {
                    "type": "claudecode",
                    "claudecode": {"model": "sonnet", "permission_mode": "auto"},
                },
            }
        }

        executor = create_driver_from_type("claudecode", cfg, role="executor")
        evaluator = create_driver_from_type("claudecode", cfg, role="evaluator")

        assert executor.model == "opus"
        assert executor.permission_mode == "bypassPermissions"

        assert evaluator.model == "sonnet"
        assert evaluator.permission_mode == "auto"              # evaluator 专属覆盖

    def test_create_executor_driver_uses_role_config(self):
        """create_executor_driver 自动传 role=executor"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_executor_driver

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {"model": "sonnet"},
                "executor": {
                    "type": "claudecode",
                    "claudecode": {"model": "opus"},
                },
            }
        }

        driver = create_executor_driver(cfg)
        assert isinstance(driver, ClaudeCodeDriver)
        assert driver.model == "opus"

    def test_create_evaluator_driver_uses_role_config(self):
        """create_evaluator_driver 自动传 role=evaluator"""
        from reloop.config import ReloopConfig
        from reloop.drivers import create_evaluator_driver

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {
            "driver": {
                "type": "claudecode",
                "claudecode": {"model": "sonnet"},
                "evaluator": {
                    "type": "claudecode",
                    "claudecode": {"model": "sonnet", "permission_mode": "auto"},
                },
            }
        }

        driver = create_evaluator_driver(cfg)
        assert isinstance(driver, ClaudeCodeDriver)
        assert driver.model == "sonnet"
        assert driver.permission_mode == "auto"


class TestUnknownDriverType:
    """未知 driver 类型应抛出 ValueError"""

    def test_unknown_type_raises_error(self):
        from reloop.config import ReloopConfig
        from reloop.drivers import create_driver_from_type

        cfg = ReloopConfig.__new__(ReloopConfig)
        cfg._config = {"driver": {"type": "unknown_type"}}

        with pytest.raises(ValueError, match="未知的 driver 类型"):
            create_driver_from_type("unknown_type", cfg)