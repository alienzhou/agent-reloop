"""Checker 结果解析测试"""

import pytest

from reloop.core.checker import extract_checker_explanation, parse_checker_result


class TestParseCheckerResult:
    """parse_checker_result 函数测试"""

    # XML 格式测试

    def test_xml_passed(self):
        """测试 XML passed 格式"""
        output = "<checker_result>passed</checker_result>"
        assert parse_checker_result(output) is True

    def test_xml_failed(self):
        """测试 XML failed 格式"""
        output = "<checker_result>failed</checker_result>"
        assert parse_checker_result(output) is False

    def test_xml_with_whitespace(self):
        """测试 XML 带空白"""
        output = "<checker_result>\n  passed  \n</checker_result>"
        assert parse_checker_result(output) is True

    def test_xml_case_insensitive(self):
        """测试 XML 大小写不敏感"""
        output = "<checker_result>PASSED</checker_result>"
        assert parse_checker_result(output) is True

    def test_xml_in_middle(self):
        """测试 XML 在输出中间"""
        output = "Some text\n<checker_result>passed</checker_result>\nMore text"
        assert parse_checker_result(output) is True

    def test_xml_with_explanation(self):
        """测试 XML 带解释"""
        output = """<checker_result>passed</checker_result>

The evaluation report clearly states "Overall: PASSED"."""
        assert parse_checker_result(output) is True

    # 向后兼容测试（旧格式）

    def test_legacy_passed(self):
        """测试旧格式 passed"""
        output = "Evaluation report...\n\npassed"
        assert parse_checker_result(output) is True

    def test_legacy_failed(self):
        """测试旧格式 failed"""
        output = "Result: FAIL\n\nfailed"
        assert parse_checker_result(output) is False

    def test_legacy_case_insensitive(self):
        """测试旧格式大小写不敏感"""
        output = "PASSED"
        assert parse_checker_result(output) is True

    # 边界情况测试

    def test_empty_output(self):
        """测试空输出"""
        with pytest.raises(ValueError):
            parse_checker_result("")

    def test_whitespace_only(self):
        """测试只有空白"""
        with pytest.raises(ValueError):
            parse_checker_result("   \n  \n  ")

    def test_no_valid_result(self):
        """测试无有效结果"""
        with pytest.raises(ValueError):
            parse_checker_result("This is some random text")

    def test_result_in_middle_lines(self):
        """测试结果在中间行（不在最后）"""
        output = "passed\n\nSome other text"
        # 应该能从最后几行找到
        assert parse_checker_result(output) is True

    def test_failed_in_context(self):
        """测试 FAILED 在上下文中"""
        output = """
## Evaluation Report

L0: PASS
L1: FAIL

Result: FAILED

<checker_result>failed</checker_result>
"""
        assert parse_checker_result(output) is False


class TestExtractCheckerExplanation:
    """extract_checker_explanation 函数测试"""

    def test_extract_explanation(self):
        """测试提取解释"""
        output = """<checker_result>passed</checker_result>

The evaluation report shows all checks passed."""
        explanation = extract_checker_explanation(output)
        assert "all checks passed" in explanation

    def test_no_explanation(self):
        """测试无解释"""
        output = "<checker_result>passed</checker_result>"
        explanation = extract_checker_explanation(output)
        assert explanation is None

    def test_no_xml_tag(self):
        """测试无 XML 标签"""
        output = "passed"
        explanation = extract_checker_explanation(output)
        assert explanation is None

    def test_multiline_explanation(self):
        """测试多行解释"""
        output = """<checker_result>failed</checker_result>

L1 check failed due to:
- Output format mismatch
- Missing required fields"""
        explanation = extract_checker_explanation(output)
        assert "Output format mismatch" in explanation
        assert "Missing required fields" in explanation
