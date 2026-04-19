"""Prompt 构建 + Driver 调用的集成测试"""

import pytest

from reloop.core.prompts import (
    build_checker_prompt,
    build_evaluator_prompt,
    build_executor_prompt,
)
from reloop.drivers.mock import MockDriver


class TestPromptDriverWiring:
    """验证 prompt 构建后正确传递给 Driver"""

    def test_executor_prompt_passed_to_driver(self):
        driver = MockDriver(responses=["ok"])
        prompt = build_executor_prompt(
            intent="Build pipeline",
            last_eval_result=None,
            exec_spec="artifacts go to run-sets/",
        )
        driver.run(prompt=prompt, workdir="/tmp")

        assert len(driver.call_log) == 1
        assert "Build pipeline" in driver.call_log[0]["prompt"]
        assert "artifacts go to run-sets/" in driver.call_log[0]["prompt"]

    def test_evaluator_prompt_passed_to_driver(self):
        driver = MockDriver(responses=["eval report"])
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill="Check file count >= 10",
        )
        driver.run(prompt=prompt, workdir="/work")

        assert "task/solution" in driver.call_log[0]["prompt"]
        assert "Check file count >= 10" in driver.call_log[0]["prompt"]

    def test_checker_prompt_passed_to_driver(self):
        driver = MockDriver(responses=["passed"])
        prompt = build_checker_prompt(
            report_path="/path/to/report.md",
            result_path="/path/to/result.md"
        )
        driver.run(prompt=prompt, workdir="/work")

        assert "/path/to/report.md" in driver.call_log[0]["prompt"]
        assert "/path/to/result.md" in driver.call_log[0]["prompt"]

    def test_workdir_passed_correctly(self):
        driver = MockDriver(responses=["ok"])
        driver.run(prompt="test", workdir="/my/workdir")
        assert driver.call_log[0]["workdir"] == "/my/workdir"

    def test_skill_inlined_in_evaluator_prompt(self):
        """Skill 内容应完整出现在 prompt 中（内联，非 flag）"""
        skill = "## L0\n- files exist\n## L1\n- format ok\n## L2\n- quality check"
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill=skill,
        )
        assert "## L0" in prompt
        assert "## L1" in prompt
        assert "## L2" in prompt
        assert "--skill" not in prompt
