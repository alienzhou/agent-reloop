# 日志系统设计

## 设计目标

1. **分层记录**：不同层面的日志分离，便于定位
2. **时间戳匹配**：统一时间格式，跨文件定位问题
3. **Agent 友好**：便于 Agent 后续自动化排查
4. **人类可读**：终端输出简洁，文件日志完整

## 目录结构

```
project-root/
├── logs/
│   └── reloop.log                 # System Log
│
└── run-sets/
    └── run-001/
        ├── logs/
        │   ├── driver.log         # Driver Log
        │   ├── executor.log       # Agent Log
        │   ├── evaluator.log      # Agent Log
        │   ├── checker.log        # Agent Log
        │   └── prompt.log         # Prompt Log
        ├── artifacts/
        └── eval-report/
            └── report.md
```

## 日志类型详解

### 1. System Log

**位置**: `logs/reloop.log`

**职责**: 记录框架整体运行状态，跨 run 的全局信息

**内容示例**:
```
2026-04-15 11:30:00.123 [INFO] [reloop.core.loop] === Round 1 ===
2026-04-15 11:30:00.456 [INFO] [reloop.core.workspace] Workspace initialized: run-001
2026-04-15 11:30:01.789 [INFO] [reloop.core.loop] Running executor...
2026-04-15 11:30:15.234 [INFO] [reloop.core.git] Auto commit: reloop: executor completed run-001
2026-04-15 11:30:15.567 [INFO] [reloop.core.loop] Running evaluator...
2026-04-15 11:30:20.890 [INFO] [reloop.core.checker] Round 1 result: PASSED
2026-04-15 11:30:21.001 [INFO] [reloop.core.loop] === Loop completed ===
```

**模块命名规范**:
- `reloop.core.loop` - 主循环控制
- `reloop.core.workspace` - 工作空间管理
- `reloop.core.git` - Git 操作
- `reloop.core.checker` - Checker 解析
- `reloop.drivers.xxx` - Driver 实现
- `reloop.cli` - CLI 命令处理

### 2. Driver Log

**位置**: `run-sets/run-XXX/logs/driver.log`

**职责**: 记录 CLI 调用详情

**格式**:
```
================================================================================
[DRIVER] 2026-04-15 11:30:01.789
Command: claude --dangerously-skip-permissions --print
Workdir: /workspace
Timeout: 300s
--------------------------------------------------------------------------------
--- INPUT PROMPT (length: 1234) ---
# Task Intent
Build a Python script...
...
--------------------------------------------------------------------------------
--- OUTPUT (length: 5678) ---
I'll implement the word_count.py script...
...
--------------------------------------------------------------------------------
Exit code: 0
Duration: 14.234s
================================================================================
```

**关键信息**:
- 完整命令与参数
- 工作目录
- 超时设置
- 输入 prompt（摘要或完整）
- 输出内容
- 退出码
- 耗时

### 3. Agent Log

**位置**: `run-sets/run-XXX/logs/{executor,evaluator,checker}.log`

**职责**: 记录 Agent 的完整输出（流式输出同时写入这里）

**格式**:
```
2026-04-15 11:30:02.001 | I'll implement the word_count.py script...
2026-04-15 11:30:03.456 | First, let me check if there's existing code...
2026-04-15 11:30:05.789 | Writing the solution to task/solution/word_count.py
2026-04-15 11:30:10.123 | [TOOL_CALL] write_file(path="task/solution/word_count.py", content=...)
2026-04-15 11:30:14.567 | Execution completed. The script should now work.
```

**设计要点**:
- 每行带时间戳前缀
- 保留 Agent 原始输出
- 流式输出时实时追加
- Tool call 标记清晰

### 4. Prompt Log

**位置**: `run-sets/run-XXX/logs/prompt.log`

**职责**: 记录发送给 Agent 的完整 prompt（调试用）

**格式**:
```
=== EXECUTOR PROMPT (2026-04-15 11:30:01) ===
# Task Intent
Build a Python script `word_count.py` that reads a text file and prints
the total word count in the format: "Word count: <N>"

---

# Workspace Context
- Current round: run-001
- Artifacts dir: /workspace/run-sets/run-001/artifacts
- Logs dir: /workspace/run-sets/run-001/logs
- Solution dir: /workspace/task/solution

---

# Execution Rules
...
=== END ===

=== EVALUATOR PROMPT (2026-04-15 11:30:15) ===
# Evaluation Skill
...
=== END ===
```

## 时间戳规范

**格式**: `YYYY-MM-DD HH:mm:ss.SSS [LEVEL] [module.path] message`

**所有日志使用相同格式**，便于：
- 通过时间点跨文件 grep
- Agent 自动化分析时解析时间线
- 问题定位时精确到毫秒

## 终端输出设计

运行时终端显示（滚动 + 日志路径提示）：

```
$ reloop run

=== Round 1 ===
[11:30:01] Workspace: run-001
[11:30:02] 📝 Executor running...
│ I'll implement word_count.py...
│ First checking existing code...
│ Writing solution...           (滚动，只显示最近 4 行)
│ Execution completed.
[11:30:15] ✅ Executor done (14.2s)
[11:30:15] 🔍 Evaluator running...
│ Running L0 checks...
│ L0: PASS, L1: FAIL (output format mismatch)
│ Details: expected "Word count: N"
[11:30:20] ❌ Round 1: FAILED

📄 Full logs:
   - System:     logs/reloop.log
   - Driver:     run-sets/run-001/logs/driver.log
   - Executor:   run-sets/run-001/logs/executor.log
   - Prompt:     run-sets/run-001/logs/prompt.log

=== Round 2 ===
...
```

## 配置项

```python
LOG_CONFIG = {
    # System log
    "system_log": "logs/reloop.log",
    "system_level": "INFO",
    "system_format": "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s",
    "system_datefmt": "%Y-%m-%d %H:%M:%S",
    
    # Run-level logs
    "run_logs": ["driver", "executor", "evaluator", "checker", "prompt"],
    
    # Stream output
    "stream_max_lines": 4,
    "stream_to_file": True,
    "stream_timestamp_format": "%H:%M:%S",
    
    # Driver log
    "driver_log_separator": "=" * 80,
}
```

## 使用示例

### 问题定位流程

```bash
# 1. 查看 System Log 定位时间范围
grep "run-002" logs/reloop.log
# → 11:35:00 - 11:35:30

# 2. 查看 Driver Log 了解 CLI 调用情况
grep "11:35:" run-sets/run-002/logs/driver.log
# → Exit code: 1, Duration: 25s

# 3. 查看具体 Agent 输出
tail -100 run-sets/run-002/logs/evaluator.log
# → Error: timeout while reading response

# 4. 查看 Prompt 是否合理
cat run-sets/run-002/logs/prompt.log
```

### Agent 自动排查

Agent 可以通过时间戳快速定位：

```
1. grep "ERROR" logs/reloop.log
   → 2026-04-15 11:35:25.123 [ERROR] [reloop.drivers.claude] Command failed

2. grep "11:35:2" run-sets/run-*/logs/driver.log
   → 定位到具体 run 和调用

3. grep "11:35:2" run-sets/run-002/logs/evaluator.log
   → 查看该时间点的 Agent 输出
```

## 实现要点

### 日志初始化

```python
def setup_logging(project_root: Path) -> None:
    """初始化日志系统"""
    # System log
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        filename=log_dir / "reloop.log",
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
```

### Agent Log 写入

```python
class AgentLogger:
    """Agent 输出的流式写入器"""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write(self, line: str, timestamp: datetime = None) -> None:
        ts = timestamp or datetime.now()
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(self.log_path, "a") as f:
            f.write(f"{ts_str} | {line}\n")
```

### Driver Log 记录

```python
def log_driver_call(
    log_path: Path,
    command: List[str],
    workdir: str,
    prompt: str,
    output: str,
    exit_code: int,
    duration: float,
) -> None:
    """记录 Driver 调用"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    with open(log_path, "a") as f:
        f.write("=" * 80 + "\n")
        f.write(f"[DRIVER] {timestamp}\n")
        f.write(f"Command: {' '.join(command)}\n")
        f.write(f"Workdir: {workdir}\n")
        f.write(f"Timeout: {timeout}s\n")
        f.write("-" * 80 + "\n")
        f.write("--- INPUT PROMPT ---\n")
        f.write(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        f.write("\n" + "-" * 80 + "\n")
        f.write("--- OUTPUT ---\n")
        f.write(output)
        f.write("\n" + "-" * 80 + "\n")
        f.write(f"Exit code: {exit_code}\n")
        f.write(f"Duration: {duration:.3f}s\n")
        f.write("=" * 80 + "\n\n")
```

## 验收标准

- [ ] System Log 正确记录框架运行状态
- [ ] Driver Log 完整记录 CLI 调用详情
- [ ] Agent Log 流式写入，带时间戳前缀
- [ ] Prompt Log 记录完整 prompt
- [ ] 终端输出滚动显示最近 N 行
- [ ] 时间戳格式统一，支持跨文件匹配
- [ ] 配置项可调整
