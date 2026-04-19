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
            last_eval_report_path=None,
            exec_spec="Put artifacts in run-sets/",
        )
        assert "Build a data pipeline" in prompt

    def test_contains_exec_spec(self):
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="Artifacts go to run-sets/run-001/artifacts/",
        )
        assert "run-sets/run-001/artifacts/" in prompt

    def test_first_round_no_eval_result(self):
        """首轮 last_eval_report_path 为 None → prompt 中不出现 eval 区段"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec",
        )
        assert "previous evaluation" not in prompt.lower()
        assert "eval result" not in prompt.lower()

    def test_first_round_empty_string_eval_result(self):
        """首轮 last_eval_report_path 为空字符串 → 同样不出现 eval 区段"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path="",
            exec_spec="spec",
        )
        assert "previous evaluation" not in prompt.lower()

    def test_subsequent_round_includes_eval_path(self):
        """后续轮次应包含评估报告路径"""
        eval_report_path = "/path/to/eval-report/report.md"
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=eval_report_path,
            exec_spec="spec",
        )
        assert eval_report_path in prompt
        # 应该指导执行器去读取报告
        assert "read" in prompt.lower()

    def test_no_skill_flag_markers(self):
        """Skill 应内联到 prompt，不应出现 --skill 标记"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec content here",
        )
        assert "--skill" not in prompt


class TestBuildEvaluatorPrompt:
    """evaluator prompt 构建逻辑"""

    def test_contains_solution_path(self):
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill="Check output format",
            report_output_path="/tmp/eval-report/report.md",
        )
        assert "task/solution" in prompt

    def test_contains_eval_skill_content(self):
        skill_body = "## Evaluation criteria\n- L0: files exist\n- L1: format check"
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill=skill_body,
            report_output_path="/tmp/eval-report/report.md",
        )
        assert skill_body in prompt

    def test_skill_inlined_not_as_flag(self):
        prompt = build_evaluator_prompt(
            solution_dir="path",
            eval_skill="skill content",
            report_output_path="/tmp/eval-report/report.md",
        )
        assert "--skill" not in prompt

    def test_contains_report_output_path(self):
        """evaluator prompt 应包含报告输出路径"""
        report_path = "/path/to/eval-report/report.md"
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill="skill content",
            report_output_path=report_path,
        )
        assert report_path in prompt

    def test_instructs_to_write_report_file(self):
        """evaluator prompt 应引导 Agent 将报告写入文件"""
        prompt = build_evaluator_prompt(
            solution_dir="task/solution",
            eval_skill="skill content",
            report_output_path="/tmp/report.md",
        )
        prompt_lower = prompt.lower()
        assert "write" in prompt_lower
        assert "report" in prompt_lower


class TestBuildCheckerPrompt:
    """checker prompt 构建逻辑"""

    def test_contains_report_path(self):
        report_path = "/path/to/eval-report/report.md"
        result_path = "/path/to/checker-result/result.md"
        prompt = build_checker_prompt(report_path=report_path, result_path=result_path)
        assert report_path in prompt

    def test_contains_result_path(self):
        report_path = "/path/to/eval-report/report.md"
        result_path = "/path/to/checker-result/result.md"
        prompt = build_checker_prompt(report_path=report_path, result_path=result_path)
        assert result_path in prompt

    def test_instructs_to_write_result_file(self):
        """checker prompt 应引导 Agent 将结果写入文件"""
        prompt = build_checker_prompt(
            report_path="/tmp/report.md",
            result_path="/tmp/result.md"
        )
        prompt_lower = prompt.lower()
        assert "write" in prompt_lower
        assert "result file" in prompt_lower or "result.md" in prompt_lower

    def test_is_task_agnostic(self):
        """checker prompt 本身不应包含特定任务语言"""
        prompt = build_checker_prompt(
            report_path="/tmp/report.md",
            result_path="/tmp/result.md"
        )
        # prompt 模板部分不应提及具体任务（如 "data pipeline"）
        template_text = prompt.replace("/tmp/report.md", "").replace("/tmp/result.md", "")
        assert "data pipeline" not in template_text.lower()
        assert "build" not in template_text.lower()

    def test_instructs_pass_or_fail(self):
        """checker prompt 应引导 Agent 输出 passed/failed"""
        prompt = build_checker_prompt(
            report_path="/tmp/report.md",
            result_path="/tmp/result.md"
        )
        prompt_lower = prompt.lower()
        assert "passed" in prompt_lower or "pass" in prompt_lower
        assert "failed" in prompt_lower or "fail" in prompt_lower
