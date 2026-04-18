"""Checker 结果解析的单元测试"""

import pytest

from reloop.core.checker import parse_checker_result


class TestParseCheckerResult:
    """验证 checker 输出的 pass/fail 解析逻辑"""

    # XML 格式测试

    def test_xml_passed(self):
        assert parse_checker_result("<checker_result>passed</checker_result>") is True

    def test_xml_failed(self):
        assert parse_checker_result("<checker_result>failed</checker_result>") is False

    def test_xml_with_whitespace(self):
        assert parse_checker_result("<checker_result>\n  passed  \n</checker_result>") is True

    def test_xml_case_insensitive(self):
        assert parse_checker_result("<checker_result>PASSED</checker_result>") is True
        assert parse_checker_result("<checker_result>Passed</checker_result>") is True

    def test_xml_in_middle(self):
        output = "Some text\n<checker_result>passed</checker_result>\nMore text"
        assert parse_checker_result(output) is True

    # 向后兼容测试（旧格式）

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

    # 无效输入测试（新设计：抛出异常）

    def test_empty_string_raises_error(self):
        """空输入 → 抛出异常"""
        with pytest.raises(ValueError):
            parse_checker_result("")

    def test_ambiguous_raises_error(self):
        """无法判定 → 抛出异常"""
        with pytest.raises(ValueError):
            parse_checker_result("maybe")

    def test_malformed_raises_error(self):
        """格式错误 → 抛出异常"""
        with pytest.raises(ValueError):
            parse_checker_result("I think it passed but not sure")

    def test_passed_in_sentence_raises_error(self):
        """只接受单词级别或 XML 格式的 passed/failed"""
        with pytest.raises(ValueError):
            parse_checker_result("The evaluation has passed all checks.")

    # 多行测试

    def test_multiline_with_passed_on_last_line(self):
        """多行输出，最后一行是 passed → 通过"""
        output = "Some reasoning...\nChecking...\npassed"
        assert parse_checker_result(output) is True

    def test_multiline_with_failed_on_last_line(self):
        output = "Analysis complete.\nfailed"
        assert parse_checker_result(output) is False

    def test_multiline_with_xml_at_end(self):
        """多行输出，XML 在末尾"""
        output = "Checking the report...\n<checker_result>passed</checker_result>"
        assert parse_checker_result(output) is True
