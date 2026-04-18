"""MockDriver 和 CallbackMockDriver 的单元测试"""

from pathlib import Path

import pytest

from reloop.drivers.mock import (
    CallbackMockDriver,
    MockDriver,
    MockDriverExhaustedError,
)


class TestMockDriver:
    """MockDriver 接口契约和行为测试"""

    def test_returns_first_response(self):
        driver = MockDriver(responses=["hello"])
        result = driver.run(prompt="p", workdir="/tmp")
        assert result == "hello"

    def test_returns_responses_in_order(self):
        driver = MockDriver(responses=["first", "second", "third"])
        assert driver.run(prompt="p", workdir="/tmp") == "first"
        assert driver.run(prompt="p", workdir="/tmp") == "second"
        assert driver.run(prompt="p", workdir="/tmp") == "third"

    def test_exhausted_raises_error(self):
        driver = MockDriver(responses=["only_one"])
        driver.run(prompt="p", workdir="/tmp")
        with pytest.raises(MockDriverExhaustedError):
            driver.run(prompt="p", workdir="/tmp")

    def test_exhausted_error_message_includes_call_count(self):
        driver = MockDriver(responses=["a"])
        driver.run(prompt="p", workdir="/tmp")
        with pytest.raises(MockDriverExhaustedError, match="2 calls"):
            driver.run(prompt="p", workdir="/tmp")

    def test_empty_responses_raises_on_first_call(self):
        driver = MockDriver(responses=[])
        with pytest.raises(MockDriverExhaustedError):
            driver.run(prompt="p", workdir="/tmp")

    def test_call_log_records_all_params(self):
        driver = MockDriver(responses=["ok"])
        driver.run(prompt="my prompt", workdir="/work", output="/out.log", timeout=30)
        assert len(driver.call_log) == 1
        entry = driver.call_log[0]
        assert entry["prompt"] == "my prompt"
        assert entry["workdir"] == "/work"
        assert entry["output"] == "/out.log"
        assert entry["timeout"] == 30

    def test_call_log_defaults_none_for_optional_params(self):
        driver = MockDriver(responses=["ok"])
        driver.run(prompt="p", workdir="/tmp")
        entry = driver.call_log[0]
        assert entry["output"] is None
        assert entry["timeout"] is None

    def test_call_log_grows_with_each_call(self):
        driver = MockDriver(responses=["a", "b", "c"])
        for _ in range(3):
            driver.run(prompt="p", workdir="/tmp")
        assert len(driver.call_log) == 3

    def test_call_log_records_before_exhaustion(self):
        """即使响应用完，call_log 也应该记录了这次调用"""
        driver = MockDriver(responses=[])
        with pytest.raises(MockDriverExhaustedError):
            driver.run(prompt="p", workdir="/tmp")
        assert len(driver.call_log) == 1

    def test_does_not_mutate_original_responses(self):
        original = ["a", "b"]
        driver = MockDriver(responses=original)
        driver.run(prompt="p", workdir="/tmp")
        assert original == ["a", "b"]

    def test_is_a_driver_subclass(self):
        from reloop.drivers.base import Driver
        assert issubclass(MockDriver, Driver)


class TestCallbackMockDriver:
    """CallbackMockDriver 的行为测试"""

    def test_callback_invoked_before_response(self):
        called = []

        def cb(prompt, workdir):
            called.append((prompt, workdir))

        driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[cb],
        )
        result = driver.run(prompt="p", workdir="/tmp")
        assert result == "ok"
        assert len(called) == 1
        assert called[0] == ("p", "/tmp")

    def test_none_callback_is_skipped(self):
        driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[None],
        )
        result = driver.run(prompt="p", workdir="/tmp")
        assert result == "ok"

    def test_callbacks_consumed_in_order(self):
        order = []

        def cb1(prompt, workdir):
            order.append("cb1")

        def cb2(prompt, workdir):
            order.append("cb2")

        driver = CallbackMockDriver(
            responses=["a", "b"],
            callbacks=[cb1, cb2],
        )
        driver.run(prompt="p", workdir="/tmp")
        driver.run(prompt="p", workdir="/tmp")
        assert order == ["cb1", "cb2"]

    def test_fewer_callbacks_than_responses(self):
        """callback 用完后，后续调用正常返回响应"""
        driver = CallbackMockDriver(
            responses=["a", "b"],
            callbacks=[None],
        )
        assert driver.run(prompt="p", workdir="/tmp") == "a"
        assert driver.run(prompt="p", workdir="/tmp") == "b"

    def test_callback_can_create_files(self, tmp_path):
        """验证 callback 可以模拟 Agent 写文件的副作用"""
        target = tmp_path / "output.txt"

        def write_file(prompt, workdir):
            target.write_text("agent output")

        driver = CallbackMockDriver(
            responses=["done"],
            callbacks=[write_file],
        )
        driver.run(prompt="p", workdir=str(tmp_path))
        assert target.read_text() == "agent output"

    def test_inherits_call_log(self):
        driver = CallbackMockDriver(responses=["ok"], callbacks=[None])
        driver.run(prompt="p", workdir="/tmp")
        assert len(driver.call_log) == 1

    def test_is_a_mock_driver_subclass(self):
        assert issubclass(CallbackMockDriver, MockDriver)
