# 提示词示例

## 1. Executor Prompt

```markdown
# Task Intent

实现一个 HTTP API，提供以下端点：
- GET /health - 健康检查，返回 {"status": "ok"}
- POST /users - 创建用户，接收 JSON {"name": "xxx", "email": "xxx"}
- GET /users/{id} - 查询用户信息

要求：
1. 使用 Python + FastAPI
2. 数据存储使用内存字典（无需持久化）
3. 添加基本的输入验证
4. 包含错误处理

---

# Previous Evaluation Result

Fix the issues identified in the last round:

## L0: FAIL
- 缺少 requirements.txt
- 项目无法直接运行

## L1: FAIL
- /health 端点未返回正确的 JSON 格式
- 实际返回: "ok" (字符串)
- 期望返回: {"status": "ok"}

## L2: PASS
- 架构设计合理

---

# Execution Spec

## Execution Rules

- Solution code goes in: /workspace/task/solution
- Execution artifacts (final outputs) go in: /workspace/run-sets/run-003/artifacts
- Execution logs go in: /workspace/run-sets/run-003/logs
- Do NOT modify files outside these directories.
- Iterate on the existing solution — do not recreate from scratch each round.
```

---

## 2. Evaluator Prompt

**关键理解**: Evaluator Skill 是由初始化阶段的 Meta Skill 生成的，不是框架预设的。每次任务的评估标准都不同。

```markdown
# Evaluation Skill

## Evaluation Criteria for: Word Count Script

### L0 — Precondition Checks
- `task/solution/word_count.py` must exist
- File must be valid Python (no syntax errors)

### L1 — Mechanical Checks
- Output format must be exactly: "Word count: <integer>"
- Script must exit with code 0 on valid input
- Must accept filepath as command-line argument

### L2 — Quality Checks
- Must handle empty files gracefully (output "Word count: 0")
- Must handle files with multiple consecutive whitespaces
- Code should be readable and documented

---

# Artifacts to Evaluate

Artifacts directory: /workspace/run-sets/run-003/artifacts

Run L0 → L1 → L2 in order. Stop early if any level fails.

Write your evaluation report.
```

---

## 3. Checker Prompt

### 3.1 旧版（纯文本解析）

```markdown
# Evaluation Report

## L0: PASS
- main.py 存在于正确位置
- requirements.txt 已创建
- 代码无语法错误

## L1: PASS
- /health 端点返回正确格式
- POST /users 能正常创建用户
- GET /users/{id} 能正确查询

## L2: PASS
- 代码风格良好
- 有适当的注释

## Overall: PASSED

---

# Instructions

Read the evaluation report above. Determine whether the evaluation has passed or failed.

Reply with exactly one word:
- `passed` if all checks indicate success
- `failed` if any check indicates failure

Do not explain. Just reply `passed` or `failed`.
```

### 3.2 新版（XML 结构化输出）

```markdown
# Evaluation Report

## L0: PASS
- main.py 存在于正确位置
- requirements.txt 已创建
- 代码无语法错误

## L1: PASS
- /health 端点返回正确格式
- POST /users 能正常创建用户
- GET /users/{id} 能正确查询

## L2: PASS
- 代码风格良好
- 有适当的注释

## Overall: PASSED

---

# Instructions

You are a **generic binary classifier**. Your job is to read the evaluation report above and determine if the solution passed or failed.

Key principles:
1. You are **task-agnostic** — you don't understand the specific requirements
2. You only analyze the report's conclusion signals
3. Look for explicit pass/fail indicators (e.g., "Overall:", "Result:", final verdict)

Rules:
- If report clearly indicates success → output `<checker_result>passed</checker_result>`
- If report indicates any failure → output `<checker_result>failed</checker_result>`
- The XML tag must be on its own line
- You MAY add explanation AFTER the XML tag

Output format:
```
<checker_result>passed</checker_result>

[Optional: Brief explanation of your reasoning]
```

or

```
<checker_result>failed</checker_result>

[Optional: Brief explanation of your reasoning]
```
```

**Checker 预期输出**:
```
<checker_result>passed</checker_result>

The report shows all L0/L1/L2 checks passed, and the Overall section explicitly states "PASSED".
```

---

## 改进建议

### Executor Prompt 改进

当前结构已经比较合理，可以增加一些上下文信息：

```markdown
# Task Intent
{intent}

---

# Workspace Context
- Current round: run-{N}
- Artifacts dir: {artifacts_dir}
- Logs dir: {logs_dir}
- Solution dir: {solution_dir}

---

# Previous Evaluation Result (if any)
{last_eval_result}

---

# Execution Rules
{exec_spec}

---

# Critical Reminders
1. You are in iteration round {N} — improve incrementally, don't restart from scratch
2. Check the solution dir for existing code before writing
3. All outputs must go to the specified directories
4. Focus on fixing the issues identified in the evaluation result
```

### Evaluator Prompt 改进

**重点**: Evaluator Skill 是动态生成的，框架只负责传递。Prompt 构建器只需：

```markdown
# Evaluation Skill
{eval_skill}

---

# Artifacts Location
Directory: {artifacts_dir}

---

# Evaluation Context
- This is evaluation for run-{N}
- Artifacts were produced by the executor agent
- Judge against the criteria, not perfection

---

# Output Requirements
1. Run checks in order (stop early on failure)
2. Write detailed findings for each level
3. End with a clear pass/fail conclusion
```

### Checker Prompt 改进（已采用 XML + 解释）

**核心设计**:
- **通用性**: Checker 不理解具体任务，只分析报告结构
- **结构化输出**: XML 标签便于可靠解析
- **可解释性**: 允许在标签后添加简短说明

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

[Optional: Brief explanation]
```

or

```
<checker_result>failed</checker_result>

[Optional: Brief explanation]
```

The XML tag must be:
- On its own line
- Exactly as shown (lowercase, no attributes)
- The ONLY required output
```
