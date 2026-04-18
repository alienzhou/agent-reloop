# D08 - 日志系统设计

## 目录结构

```
project-root/
├── logs/                          # 全局日志目录
│   └── reloop.log                 # System Log - 框架运行日志
│
└── run-sets/
    ├── run-001/
    │   ├── logs/
    │   │   ├── driver.log         # Driver Log - CLI 调用记录
    │   │   ├── executor.log       # Executor Log - Agent 输出
    │   │   ├── evaluator.log      # Evaluator Log - Agent 输出
    │   │   ├── checker.log        # Checker Log - Agent 输出
    │   │   └── prompt.log         # Prompt Log - 发送的完整 prompt
    │   ├── artifacts/
    │   └── eval-report/
    │
    └── run-002/
        └── ...
```

## 日志类型说明

### 1. System Log (`logs/reloop.log`)

**位置**: 项目根目录下 `logs/reloop.log`

**内容**: 框架整体运行状态，跨 run 的信息

**示例**:
```
2026-04-15 11:30:00.123 [INFO] [reloop.core.loop] === Round 1 ===
2026-04-15 11:30:00.456 [INFO] [reloop.core.workspace] Workspace initialized: run-001
2026-04-15 11:30:01.789 [INFO] [reloop.core.loop] Running executor...
2026-04-15 11:30:15.234 [INFO] [reloop.core.git] Auto commit: reloop: executor completed run-001
2026-04-15 11:30:15.567 [INFO] [reloop.core.loop] Running evaluator...
2026-04-15 11:30:20.890 [INFO] [reloop.core.checker] Round 1 result: PASSED
2026-04-15 11:30:21.001 [INFO] [reloop.core.loop] === Loop completed ===
```

### 2. Driver Log (`run-sets/run-XXX/logs/driver.log`)

**位置**: 每个 run 目录下

**内容**: CLI 调用详情（命令、参数、返回码、耗时、输入输出摘要）

**格式**:
```
[DRIVER] 2026-04-15 11:30:01.789
Command: claude --dangerously-skip-permissions --print
Workdir: /workspace
Timeout: 300s
--- INPUT PROMPT ---
(Task Intent: Build word_count.py...)
--- OUTPUT ---
(Executor completed...)
--- END ---
Exit code: 0
Duration: 14.2s
```

### 3. Agent Logs (`run-sets/run-XXX/logs/{executor,evaluator,checker}.log`)

**位置**: 每个 run 目录下

**内容**: Agent 的完整输出（流式输出同时写入这里）

**格式**: 直接记录 Agent 的原始输出，包含时间戳前缀

**示例 (executor.log)**:
```
2026-04-15 11:30:02.001 | I'll implement the word_count.py script...
2026-04-15 11:30:03.456 | First, let me check if there's existing code...
2026-04-15 11:30:05.789 | Writing the solution to task/solution/word_count.py
2026-04-15 11:30:10.123 | [TOOL_CALL] write_file(path="task/solution/word_count.py", content=...)
2026-04-15 11:30:14.567 | Execution completed. The script should now work.
```

### 4. Prompt Log (`run-sets/run-XXX/logs/prompt.log`)

**位置**: 每个 run 目录下

**内容**: 发送给 Agent 的完整 prompt（调试用）

**格式**:
```
=== EXECUTOR PROMPT (2026-04-15 11:30:01) ===
# Task Intent
Build a Python script...
...

=== EVALUATOR PROMPT (2026-04-15 11:30:15) ===
# Evaluation Skill
...
```

## 日志前缀规范

所有日志使用统一前缀格式：`[时间戳] [级别] [模块] 消息`

```
YYYY-MM-DD HH:mm:ss.SSS [LEVEL] [module.path] message
```

**模块命名**:
- `reloop.core.loop` - 主循环
- `reloop.core.workspace` - 工作空间管理
- `reloop.core.git` - Git 操作
- `reloop.core.checker` - Checker 解析
- `reloop.drivers.xxx` - Driver 实现
- `reloop.cli` - CLI 命令

**日志级别**:
- `DEBUG` - 详细调试信息
- `INFO` - 正常运行信息
- `WARNING` - 警告（如回滚提醒）
- `ERROR` - 错误（如 Driver 调用失败）

## 时间戳匹配机制

### 问题定位流程

假设用户发现 run-002 在 evaluator 阶段失败：

```
1. 查看 System Log 定位时间范围
   grep "run-002" logs/reloop.log
   → 11:35:00 - 11:35:30

2. 查看 Driver Log 了解 CLI 调用情况
   grep "11:35:" run-sets/run-002/logs/driver.log
   → Exit code: 1, Duration: 25s

3. 查看具体 Agent 输出
   tail -100 run-sets/run-002/logs/evaluator.log
   → Error: timeout while reading response

4. 查看 Prompt 是否合理
   cat run-sets/run-002/logs/prompt.log
   → 检查 prompt 是否有问题
```

### Agent 自助排查

Agent 可以通过时间戳快速定位：

```
1. 获取问题时间点
   grep "ERROR" logs/reloop.log
   → 2026-04-15 11:35:25.123 [ERROR] [reloop.drivers.claude] Command failed

2. 查看该时间点前后的 Driver Log
   grep -A5 -B5 "11:35:25" run-sets/run-*/logs/driver.log

3. 查看对应 Agent 输出
   grep "11:35:2" run-sets/run-002/logs/evaluator.log
```

## 配置项

```python
# 日志配置
LOG_CONFIG = {
    # 全局日志
    "system_log": "logs/reloop.log",
    "system_level": "INFO",
    
    # Run 级别日志
    "run_logs": ["driver", "executor", "evaluator", "checker", "prompt"],
    
    # 流式输出
    "stream_max_lines": 4,  # 终端显示行数
    "stream_to_file": True,  # 是否写入文件
    
    # 时间戳格式
    "timestamp_format": "%Y-%m-%d %H:%M:%S.%f",
}
```

## 使用建议

### 终端输出

运行时显示：
```
$ reloop run

=== Round 1 ===
[11:30:01] Workspace: run-001
[11:30:02] 📝 Executor running...
│ I'll implement word_count.py...
│ First checking existing code...
│ Writing solution... (scrolling, last 4 lines)
[11:30:15] ✅ Executor done (14.2s)
[11:30:15] 🔍 Evaluator running...
│ Running L0 checks...
│ L0: PASS, L1: FAIL (output format mismatch) (scrolling)
[11:30:20] ❌ Round 1: FAILED

📄 Full logs: run-sets/run-001/logs/
   - executor.log (Agent output)
   - driver.log (CLI details)
   - prompt.log (Full prompt)

=== Round 2 ===
...
```

### 排查命令

```bash
# 查看框架整体运行
tail -f logs/reloop.log

# 查看特定 run 的 driver 调用
cat run-sets/run-001/logs/driver.log

# 查看特定时间段的错误
grep "11:30:" logs/reloop.log | grep ERROR

# Agent 查看完整输出
cat run-sets/run-001/logs/executor.log
```
