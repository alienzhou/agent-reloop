"""Prompt 构建器的单元测试"""

import pytest

from reloop.core.prompts import (
    build_checker_prompt,
    build_evaluator_prompt,
    build_executor_prompt,
)


class TestBuildExecutorPrompt:
    """executor prompt 构建逻辑"""

    def test_contains_intent(self):
        prompt = build_executor_prompt(
            intent="Build a data pipeline",
            last_eval_result=None,
            exec_spec="Put artifacts in run-sets/",
        )
        assert "Build a data pipeline" in prompt

    def test_contains_exec_spec(self):
        prompt = build_executor_prompt(
            intent="task",
            last_eval_result=None,
            exec_spec="Artifacts go to run-sets/run-001/artifacts/",
        )
        assert "run-sets/run-001/artifacts/" in prompt

    def test_first_round_no_eval_result(self):
        """首轮 last_eval_result 为 None → prompt 中不出现 eval 区段"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_result=None,
            exec_spec="spec",
        )
        assert "previous evaluation" not in prompt.lower()
        assert "eval result" not in prompt.lower()

    def test_first_round_empty_string_eval_result(self):
        """首轮 last_eval_result 为空字符串 → 同样不出现 eval 区段"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_result="",
            exec_spec="spec",
        )
        assert "previous evaluation" not in prompt.lower()

    def test_subsequent_round_includes_eval(self):
        eval_result = "L1 failed: output count mismatch, expected 10, got 8"
        prompt = build_executor_prompt(
            intent="task",
            last_eval_result=eval_result,
            exec_spec="spec",
        )
        assert eval_result in prompt

    def test_no_skill_flag_markers(self):
        """Skill 应内联到 prompt，不应出现 --skill 标记"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_result=None,
            exec_spec="spec content here",
        )
        assert "--skill" not in prompt


class TestBuildEvaluatorPrompt:
    """evaluator prompt 构建逻辑"""

    def test_contains_artifacts_path(self):
        prompt = build_evaluator_prompt(
            artifacts_dir="run-sets/run-001/artifacts",
            eval_skill="Check output format",
        )
        assert "run-sets/run-001/artifacts" in prompt

    def test_contains_eval_skill_content(self):
        skill_body = "## Evaluation criteria\n- L0: files exist\n- L1: format check"
        prompt = build_evaluator_prompt(
            artifacts_dir="run-sets/run-001/artifacts",
            eval_skill=skill_body,
        )
        assert skill_body in prompt

    def test_skill_inlined_not_as_flag(self):
        prompt = build_evaluator_prompt(
            artifacts_dir="path",
            eval_skill="skill content",
        )
        assert "--skill" not in prompt


class TestBuildCheckerPrompt:
    """checker prompt 构建逻辑"""

    def test_contains_report_path(self):
        report_path = "/path/to/eval-report/report.md"
        prompt = build_checker_prompt(report_path=report_path)
        assert report_path in prompt

    def test_is_task_agnostic(self):
        """checker prompt 本身不应包含特定任务语言"""
        prompt = build_checker_prompt(report_path="/tmp/report.md")
        # prompt 模板部分不应提及具体任务（如 "data pipeline"）
        template_text = prompt.replace("/tmp/report.md", "")
        assert "data pipeline" not in template_text.lower()
        assert "build" not in template_text.lower()

    def test_instructs_pass_or_fail(self):
        """checker prompt 应引导 Agent 输出 passed/failed"""
        prompt = build_checker_prompt(report_path="/tmp/report.md")
        prompt_lower = prompt.lower()
        assert "passed" in prompt_lower or "pass" in prompt_lower
        assert "failed" in prompt_lower or "fail" in prompt_lower
