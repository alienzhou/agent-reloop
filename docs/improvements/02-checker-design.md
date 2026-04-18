# Checker 输出格式设计

## 问题背景

当前 `parse_checker_result` 解析最后一行是否为 `passed`/`failed`，存在以下风险：
- Agent 输出可能带有多余空白、Markdown 格式
- 模型可能在结论前加解释性文字
- 格式不统一导致解析失败

## 设计目标

1. **稳定解析**：格式化输出，减少误判
2. **可解释性**：允许输出解释内容
3. **任务无关**：Checker 是通用组件，不依赖具体任务

## 输出格式

### 格式定义

```xml
<checker_result>passed</checker_result>

[Optional: Brief explanation of the decision]
```

或

```xml
<checker_result>failed</checker_result>

[Optional: Brief explanation of the decision]
```

### 格式要点

- XML 标签必须单独成行
- 标签内容只能是 `passed` 或 `failed`（小写）
- 解释内容在标签后，可选
- 解析时只需匹配 XML 标签行

## Prompt 设计

```markdown
# Evaluation Report
{eval_report}

---

# Instructions

You are a **task-agnostic binary classifier**. 

Your job:
1. Read the evaluation report above
2. Determine if it indicates overall success or failure
3. Output your decision in XML format

You do NOT need to:
- Understand the specific task
- Evaluate the solution yourself
- Agree with the evaluator's judgment

Decision rules:
- Look for explicit conclusion signals: "Overall:", "Result:", "Final:", "Verdict:"
- Look for pass/fail keywords in the conclusion section
- If unclear, default to "failed" (conservative)

Output format (mandatory):
```
<checker_result>passed</checker_result>

[Optional: Brief explanation - why you think it passed/failed]
```

or

```
<checker_result>failed</checker_result>

[Optional: Brief explanation - why you think it passed/failed]
```

The XML tag must be:
- On its own line
- Exactly as shown (lowercase, no attributes)
- The ONLY required output
```

## 解析实现

```python
import re

CHECKER_RESULT_PATTERN = re.compile(
    r'^<checker_result>(passed|failed)</checker_result>$',
    re.MULTILINE
)


def parse_checker_result(output: str) -> bool:
    """解析 Checker 输出，提取判定结果。
    
    Args:
        output: Agent 的完整输出文本
        
    Returns:
        True 表示 passed，False 表示 failed
        
    Raises:
        ValueError: 无法解析出结果时
    """
    match = CHECKER_RESULT_PATTERN.search(output)
    if match:
        return match.group(1) == "passed"
    
    # 回退：尝试匹配最后一行的 passed/failed（兼容旧格式）
    lines = [l.strip().lower() for l in output.strip().splitlines() if l.strip()]
    if lines and lines[-1] in ("passed", "failed"):
        return lines[-1] == "passed"
    
    raise ValueError(f"Cannot parse checker result from output: {output[:200]}...")


def extract_checker_explanation(output: str) -> str | None:
    """提取 Checker 的解释内容（如有）。
    
    Args:
        output: Agent 的完整输出文本
        
    Returns:
        解释内容，如无则返回 None
    """
    # 找到 XML 标签后的内容
    match = CHECKER_RESULT_PATTERN.search(output)
    if match:
        end_pos = match.end()
        explanation = output[end_pos:].strip()
        return explanation if explanation else None
    return None
```

## 输出示例

### 示例 1：通过

```
<checker_result>passed</checker_result>

The evaluation report clearly states "Overall: PASSED" with all L0/L1/L2 checks passing.
```

### 示例 2：失败

```
<checker_result>failed</checker_result>

L1 check failed due to output format mismatch. The report indicates "Result: FAILED".
```

### 示例 3：无解释

```
<checker_result>failed</checker_result>
```

### 示例 4：复杂输出

```
Looking at the evaluation report, I can see that:

1. L0 checks all passed
2. L1 checks passed 
3. L2 checks passed

The final verdict is clearly stated as "Overall: PASSED".

<checker_result>passed</checker_result>
```

## 兼容性

### 向后兼容

解析器支持两种格式：
1. **新格式**：XML 标签（优先）
2. **旧格式**：最后一行 `passed`/`failed`（回退）

### 升级路径

- 现有测试使用旧格式仍可运行
- 新测试应使用 XML 格式
- 生产环境逐步迁移到新格式

## 测试用例

```python
import pytest
from reloop.core.checker import parse_checker_result


def test_parse_xml_passed():
    output = "<checker_result>passed</checker_result>\n\nAll good"
    assert parse_checker_result(output) is True


def test_parse_xml_failed():
    output = "<checker_result>failed</checker_result>"
    assert parse_checker_result(output) is False


def test_parse_xml_with_explanation():
    output = "<checker_result>passed</checker_result>\n\nBecause L0/L1/L2 all passed"
    assert parse_checker_result(output) is True


def test_parse_xml_in_middle():
    output = "Some text\n<checker_result>failed</checker_result>\nMore text"
    assert parse_checker_result(output) is False


def test_parse_legacy_passed():
    output = "Evaluation report...\n\npassed"
    assert parse_checker_result(output) is True


def test_parse_legacy_failed():
    output = "Result: FAIL\n\nfailed"
    assert parse_checker_result(output) is False


def test_parse_invalid():
    output = "This output has no clear result"
    with pytest.raises(ValueError):
        parse_checker_result(output)


def test_parse_empty():
    with pytest.raises(ValueError):
        parse_checker_result("")
```

## 验收标准

- [ ] XML 格式正确解析
- [ ] 向后兼容旧格式
- [ ] 无效输出抛出异常
- [ ] 支持提取解释内容
- [ ] Prompt 已更新
- [ ] 测试覆盖所有场景
