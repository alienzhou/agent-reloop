"""Checker 结果解析的单元测试"""

import pytest

from reloop.core.checker import parse_checker_result


class TestParseCheckerResult:
    """验证 checker 输出的 pass/fail 解析逻辑"""

    def test_exact_passed(self):
        assert parse_checker_result("passed") is True

    def test_exact_failed(self):
        assert parse_checker_result("failed") is False

    def test_passed_with_whitespace(self):
        assert parse_checker_result("  passed  \n") is True

    def test_failed_with_whitespace(self):
        assert parse_checker_result("\n  failed  \n") is False

    def test_passed_case_insensitive(self):
        assert parse_checker_result("PASSED") is True
        assert parse_checker_result("Passed") is True

    def test_failed_case_insensitive(self):
        assert parse_checker_result("FAILED") is False
        assert parse_checker_result("Failed") is False

    def test_empty_string_returns_false(self):
        """空输出 → 保守判定为 failed"""
        assert parse_checker_result("") is False

    def test_ambiguous_returns_false(self):
        """无法判定 → 保守判定为 failed"""
        assert parse_checker_result("maybe") is False

    def test_malformed_returns_false(self):
        assert parse_checker_result("I think it passed but not sure") is False

    def test_passed_in_sentence_returns_false(self):
        """只接受单词级别的 passed/failed，不接受嵌入在句子中的"""
        assert parse_checker_result("The evaluation has passed all checks.") is False

    def test_multiline_with_passed_on_last_line(self):
        """多行输出，最后一行是 passed → 通过"""
        output = "Some reasoning...\nChecking...\npassed"
        assert parse_checker_result(output) is True

    def test_multiline_with_failed_on_last_line(self):
        output = "Analysis complete.\nfailed"
        assert parse_checker_result(output) is False
