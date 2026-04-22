"""报告抽象化和干预提示的单元测试"""

import pytest

from reloop.core.report_sanitizer import abstract_eval_report
from reloop.core.prompts import get_intervention_prompt, build_executor_prompt, build_history_runs_hint


class TestAbstractEvalReport:
    """评估报告抽象化测试"""

    def test_extracts_layer_pass_status(self):
        """能正确识别 PASS 状态"""
        report = """
# 评估报告

## 评估结果总览

| Layer | 状态 |
|-------|------|
| L0 | ✅ 通过 |
| L1 | ✅ PASS |
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "✅ PASS" in result
        assert "L0" in result
        assert "L1" in result

    def test_extracts_layer_fail_status(self):
        """能正确识别 FAIL 状态"""
        report = """
## 评估结果

| Layer | 状态 |
|-------|------|
| L0 | ✅ PASS |
| L1 | ❌ FAIL |
| L2 | ⏸️ 跳过 |
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "❌ FAIL" in result
        assert "L1" in result

    def test_extracts_issue_count(self):
        """能统计问题数量"""
        report = """
# 评估报告

| Layer | 状态 |
|-------|------|
| L1 | ❌ 失败 |

## L1 失败原因

1. 文件数量不足
2. 核心模块缺失
3. 结构不符合预期
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "3 issues" in result or "issues found" in result

    def test_includes_full_report_path(self):
        """结果中包含完整报告路径"""
        report = "# Test Report\n| L0 | ✅ PASS |"
        full_path = "/path/to/eval-report/report.md"
        result = abstract_eval_report(report, full_path)
        assert full_path in result

    def test_hides_specific_details(self):
        """不暴露具体问题细节"""
        report = """
# 评估报告

## L1 失败原因

1. 点击角色详情按钮无法弹出面板
2. 对话气泡显示异常
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        # 具体的问题描述不应出现在抽象结果中
        assert "点击角色详情按钮" not in result
        assert "对话气泡" not in result

    def test_empty_report_handling(self):
        """空报告处理"""
        result = abstract_eval_report("", "/path/to/report.md")
        assert "No evaluation report" in result or "/path/to/report.md" in result

    def test_detects_skip_status(self):
        """能识别 SKIP 状态"""
        report = """
| Layer | 状态 |
|-------|------|
| L0 | ✅ PASS |
| L1 | ❌ FAIL |
| L2 | ⏸️ 跳过 |
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "⏸️ SKIP" in result
        assert "Blocked by previous layer" in result

    def test_detects_overall_status_pass(self):
        """检测整体通过状态"""
        report = "Overall: PASS\n| L0 | ✅ PASS |\n| L1 | ✅ PASS |"
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "**Overall:** ✅ PASS" in result

    def test_detects_overall_status_fail(self):
        """检测整体失败状态"""
        report = "判定: 未通过\n| L1 | ❌ FAIL |"
        result = abstract_eval_report(report, "/path/to/report.md")
        assert "**Overall:** ❌ FAIL" in result

    def test_covers_all_five_layers(self):
        """覆盖所有 5 个 Layer"""
        report = """
| L0 | ✅ PASS |
| L1 | ✅ PASS |
| L2 | ✅ PASS |
| L3 | ❌ FAIL |
| L4 | ⏸️ SKIP |
"""
        result = abstract_eval_report(report, "/path/to/report.md")
        for layer in ["L0", "L1", "L2", "L3", "L4"]:
            assert layer in result


class TestGetInterventionPrompt:
    """长轮次干预提示测试"""

    def test_no_intervention_early_rounds(self):
        """轮次 1-3 无干预"""
        assert get_intervention_prompt(1) is None
        assert get_intervention_prompt(2) is None
        assert get_intervention_prompt(3) is None

    def test_light_intervention_round_4_5(self):
        """轮次 4-5 轻度提醒"""
        prompt4 = get_intervention_prompt(4)
        prompt5 = get_intervention_prompt(5)
        
        assert prompt4 is not None
        assert prompt5 is not None
        assert "Progress Check" in prompt4
        assert "Round 4" in prompt4
        assert "Round 5" in prompt5

    def test_medium_intervention_round_6_7(self):
        """轮次 6-7 中度干预"""
        prompt6 = get_intervention_prompt(6)
        prompt7 = get_intervention_prompt(7)
        
        assert prompt6 is not None
        assert "Strategy Review" in prompt6
        assert "CHANGE STRATEGY" in prompt6 or "change strategy" in prompt6.lower()

    def test_strong_intervention_round_8_plus(self):
        """轮次 8+ 强干预"""
        prompt8 = get_intervention_prompt(8)
        prompt10 = get_intervention_prompt(10)
        
        assert prompt8 is not None
        assert "Critical Review" in prompt8 or "SERIOUS RESET" in prompt8
        assert "REWRITE" in prompt8 or "rewrite" in prompt8.lower() or "REBUILD" in prompt8

    def test_intervention_includes_round_number(self):
        """干预提示包含轮次号"""
        prompt = get_intervention_prompt(6)
        assert "6" in prompt or "Round 6" in prompt

    def test_zero_round_no_intervention(self):
        """轮次为 0 时无干预"""
        assert get_intervention_prompt(0) is None

    def test_negative_round_no_intervention(self):
        """负数轮次无干预"""
        assert get_intervention_prompt(-1) is None

    def test_very_high_round_returns_strong_intervention(self):
        """超高轮次仍返回强干预"""
        prompt = get_intervention_prompt(100)
        assert prompt is not None
        assert "Critical Review" in prompt
        assert "100" in prompt


class TestBuildExecutorPromptEnhanced:
    """增强版 Executor Prompt 测试"""

    def test_includes_proposal_instruction(self):
        """包含提案写作指令"""
        prompt = build_executor_prompt(
            intent="Build a game",
            last_eval_report_path=None,
            exec_spec="spec",
            round_num=1,
            proposal_output_path="/path/to/proposal.md",
        )
        assert "proposal" in prompt.lower()
        assert "/path/to/proposal.md" in prompt

    def test_includes_history_hint_when_provided(self):
        """提供历史提示时包含在 prompt 中"""
        history_hint = "run-sets/run-001/proposal.md"
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec",
            round_num=2,
            history_runs_hint=history_hint,
        )
        assert "run-sets" in prompt or "Historical Context" in prompt

    def test_includes_abstract_summary_when_provided(self):
        """提供抽象摘要时包含在 prompt 中"""
        abstract = "## Evaluation Summary\n| L0 | ✅ PASS |"
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path="/path/to/report.md",
            exec_spec="spec",
            round_num=2,
            abstract_eval_summary=abstract,
        )
        assert "Evaluation Summary" in prompt or "ABSTRACT" in prompt.upper()

    def test_includes_intervention_for_high_rounds(self):
        """高轮次包含干预提示"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec",
            round_num=6,
        )
        assert "Strategy Review" in prompt or "strategy" in prompt.lower()

    def test_core_objective_emphasized(self):
        """INTENT 在 prompt 中被强调"""
        prompt = build_executor_prompt(
            intent="Build a world-class game",
            last_eval_report_path=None,
            exec_spec="spec",
            round_num=1,
        )
        assert "CORE OBJECTIVE" in prompt or "NEVER FORGET" in prompt
        assert "Build a world-class game" in prompt

    def test_reminder_section_present(self):
        """包含提醒部分"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec",
            round_num=1,
        )
        assert "REMINDER" in prompt

    def test_first_round_minimal_params(self):
        """首轮只传必需参数"""
        prompt = build_executor_prompt(
            intent="Build something",
            last_eval_report_path=None,
            exec_spec="rules",
            round_num=1,
        )
        assert "CORE OBJECTIVE" in prompt
        assert "Build something" in prompt
        assert "Historical Context" not in prompt
        assert "Previous Evaluation" not in prompt

    def test_eval_report_path_without_abstract(self):
        """只传报告路径不传抽象摘要"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path="/path/to/report.md",
            exec_spec="spec",
            round_num=2,
        )
        assert "/path/to/report.md" in prompt
        assert "Read the evaluation report" in prompt or "read" in prompt.lower()

    def test_default_round_num_is_one(self):
        """默认轮次为 1"""
        prompt = build_executor_prompt(
            intent="task",
            last_eval_report_path=None,
            exec_spec="spec",
        )
        # 轮次 1 不应包含干预提示
        assert "Progress Check" not in prompt
        assert "Strategy Review" not in prompt
        assert "Critical Review" not in prompt


class TestBuildHistoryRunsHint:
    """历史 run-sets 提示构建测试"""

    def test_returns_none_for_first_round(self):
        """首轮返回 None"""
        result = build_history_runs_hint(1)
        assert result is None

    def test_includes_previous_runs(self):
        """包含之前的 run 目录"""
        result = build_history_runs_hint(3)
        assert result is not None
        assert "run-001" in result
        assert "run-002" in result
        assert "proposal.md" in result

    def test_second_round_single_history(self):
        """第二轮只有一条历史"""
        result = build_history_runs_hint(2)
        assert result is not None
        assert "run-001" in result
        assert "run-002" not in result

    def test_output_format_structure(self):
        """验证输出格式结构"""
        result = build_history_runs_hint(3)
        assert "```" in result  # 代码块格式
        assert "proposal.md" in result
        assert "eval-report" in result
        assert "report.md" in result

    def test_zero_round_returns_none(self):
        """轮次 0 返回 None"""
        result = build_history_runs_hint(0)
        assert result is None

    def test_negative_round_returns_none(self):
        """负数轮次返回 None"""
        result = build_history_runs_hint(-1)
        assert result is None
