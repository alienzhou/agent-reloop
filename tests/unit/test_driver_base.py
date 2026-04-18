"""Driver 基类接口契约测试"""

import pytest

from reloop.drivers.base import Driver


class TestDriverInterface:
    """验证 Driver 基类的接口契约"""

    def test_run_requires_prompt_and_workdir(self):
        driver = Driver()
        with pytest.raises(TypeError):
            driver.run()

    def test_run_raises_not_implemented(self):
        driver = Driver()
        with pytest.raises(NotImplementedError):
            driver.run(prompt="hello", workdir="/tmp")

    def test_run_accepts_optional_output(self):
        driver = Driver()
        with pytest.raises(NotImplementedError):
            driver.run(prompt="hello", workdir="/tmp", output="/tmp/out.log")

    def test_run_accepts_optional_timeout(self):
        driver = Driver()
        with pytest.raises(NotImplementedError):
            driver.run(prompt="hello", workdir="/tmp", timeout=60)

    def test_run_accepts_all_params(self):
        driver = Driver()
        with pytest.raises(NotImplementedError):
            driver.run(
                prompt="hello",
                workdir="/tmp",
                output="/tmp/out.log",
                timeout=60,
            )

    def test_subclass_can_override_run(self):
        class FakeDriver(Driver):
            def run(self, prompt, workdir, output=None, timeout=None):
                return "ok"

        driver = FakeDriver()
        result = driver.run(prompt="hello", workdir="/tmp")
        assert result == "ok"

    def test_subclass_run_returns_str(self):
        class FakeDriver(Driver):
            def run(self, prompt, workdir, output=None, timeout=None):
                return "response text"

        driver = FakeDriver()
        result = driver.run(prompt="test", workdir="/tmp")
        assert isinstance(result, str)
