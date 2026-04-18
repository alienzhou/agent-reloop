# Driver 流式输出设计

## 问题背景

当前 Driver 接口是同步的：
```python
def run(self, prompt: str, workdir: str) -> str:
    # 调用 CLI，等待完成
    # 返回完整输出
```

这种设计的问题：
1. 无法实时看到 Agent 的输出进度
2. 长时间运行时缺乏反馈
3. 用户不知道是否卡住
4. 调试困难

## 设计目标

1. **流式输出**：实时显示 Agent 输出
2. **滚动显示**：终端只显示最近 N 行
3. **日志写入**：完整输出写入文件
4. **路径提示**：告诉用户日志位置
5. **Mock 兼容**：Mock Driver 也采用同样机制

## 接口设计

### 新接口

```python
from typing import Iterator, Callable

class Driver:
    """所有 Driver 的基类。"""
    
    def run(
        self,
        prompt: str,
        workdir: str,
        output: str | None = None,
        timeout: int | None = None,
        # 新增参数
        stream_callback: Callable[[str], None] | None = None,
    ) -> str:
        """调用 Agent CLI 执行 prompt。
        
        Args:
            prompt: 完整的 prompt 字符串
            workdir: Agent 工作目录
            output: 可选，输出文件路径
            timeout: 可选，超时秒数
            stream_callback: 可选，流式输出回调函数
            
        Returns:
            Agent 的完整输出文本
        """
        raise NotImplementedError
```

### 流式输出机制

```python
class StreamOutput:
    """流式输出管理器。"""
    
    def __init__(
        self,
        log_path: Path,
        max_lines: int = 4,
        timestamp_format: str = "%H:%M:%S",
    ):
        self.log_path = log_path
        self.max_lines = max_lines
        self.timestamp_format = timestamp_format
        self.buffer: list[str] = []
        self.line_buffer = ""
        
        # 确保日志目录存在
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write(self, chunk: str) -> None:
        """写入流式数据。"""
        # 追加到行缓冲
        self.line_buffer += chunk
        
        # 检查是否有完整行
        while "\n" in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split("\n", 1)
            self._write_line(line)
    
    def _write_line(self, line: str) -> None:
        """写入完整行。"""
        timestamp = datetime.now().strftime(self.timestamp_format)
        full_line = f"{timestamp} | {line}"
        
        # 写入文件（完整内容）
        with open(self.log_path, "a") as f:
            f.write(full_line + "\n")
        
        # 更新滚动缓冲
        self.buffer.append(full_line)
        if len(self.buffer) > self.max_lines:
            self.buffer.pop(0)
        
        # 刷新终端显示
        self._refresh_display()
    
    def _refresh_display(self) -> None:
        """刷新终端显示。"""
        # 清除当前显示
        for _ in range(self.max_lines):
            print("\033[F\033[K", end="")  # 上移一行并清除
        
        # 显示最新内容
        for line in self.buffer:
            print(f"\033[2m{line}\033[0m")
    
    def flush(self) -> None:
        """刷新剩余内容。"""
        if self.line_buffer:
            self._write_line(self.line_buffer)
            self.line_buffer = ""
    
    def finalize(self) -> str:
        """完成输出，返回路径提示。"""
        self.flush()
        return f"📄 Full log: {self.log_path}"
```

### 集成示例

```python
class ClaudeCodeDriver(Driver):
    """Claude Code CLI Driver。"""
    
    def run(
        self,
        prompt: str,
        workdir: str,
        output: str | None = None,
        timeout: int | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> str:
        # 构建命令
        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "--print",
        ]
        
        # 流式读取输出
        full_output = []
        process = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        
        # 发送 prompt
        process.stdin.write(prompt)
        process.stdin.close()
        
        # 流式读取
        for line in process.stdout:
            full_output.append(line)
            if stream_callback:
                stream_callback(line.rstrip("\n"))
        
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"Claude Code failed with code {process.returncode}")
        
        return "".join(full_output)
```

## 终端输出设计

### 运行时显示

```
$ reloop run

=== Round 1 ===
[11:30:01] Workspace: run-001
[11:30:02] 📝 Executor running...
│ I'll implement word_count.py...
│ First checking existing code...
│ Writing solution...           (滚动，最近 4 行)
│ Execution completed.
[11:30:15] ✅ Executor done (14.2s)
[11:30:15] 🔍 Evaluator running...
│ Running L0 checks...
│ L0: PASS, L1: FAIL
│ Details: expected "Word count: N" (滚动，最近 4 行)
[11:30:20] ❌ Round 1: FAILED

📄 Full logs:
   - System:     logs/reloop.log
   - Driver:    run-sets/run-001/logs/driver.log
   - Executor:  run-sets/run-001/logs/executor.log
   - Prompt:    run-sets/run-001/logs/prompt.log

=== Round 2 ===
...
```

### 实现代码

```python
def run_loop(
    project_root: Path,
    # ...
) -> LoopResult:
    """执行 Reloop 迭代主循环。"""
    
    # 初始化系统日志
    system_log = setup_system_logging(project_root)
    
    for round_num in range(1, max_iterations + 1):
        logger.info("=== Round %d ===", round_num)
        
        # 初始化工作空间
        run_dir = init_workspace(project_root)
        run_id = run_dir.name
        
        # 创建流式输出器
        log_dir = run_dir / "logs"
        stream_output = StreamOutput(
            log_path=log_dir / "executor.log",
            max_lines=4,
        )
        
        # Executor
        print(f"[{time.strftime('%H:%M:%S')}] 📝 Executor running...")
        executor_prompt = build_executor_prompt(intent, last_eval_result, exec_spec)
        executor_output = executor_driver.run(
            prompt=executor_prompt,
            workdir=str(project_root),
            stream_callback=stream_output.write,
        )
        print(stream_output.finalize())
        
        # Git commit
        if enable_git_commit:
            auto_commit_after_execution(project_root, run_id)
        
        # Evaluator
        stream_output = StreamOutput(log_path=log_dir / "evaluator.log")
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 Evaluator running...")
        eval_prompt = build_evaluator_prompt(str(run_dir / "artifacts"), eval_skill)
        eval_output = evaluator_driver.run(
            prompt=eval_prompt,
            workdir=str(project_root),
            stream_callback=stream_output.write,
        )
        print(stream_output.finalize())
        
        # 保存评估报告
        report_path = run_dir / "eval-report" / "report.md"
        report_path.write_text(eval_output)
        last_eval_result = eval_output
        
        # Checker
        stream_output = StreamOutput(log_path=log_dir / "checker.log")
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Checker running...")
        checker_prompt = build_checker_prompt(eval_output)
        checker_output = checker_driver.run(
            prompt=checker_prompt,
            workdir=str(project_root),
            stream_callback=stream_output.write,
        )
        print(stream_output.finalize())
        
        # 解析结果
        passed = parse_checker_result(checker_output)
        
        if passed:
            print(f"[{time.strftime('%H:%M:%S')}] ✅ Round {round_num}: PASSED")
            return LoopResult(success=True, rounds=round_num, ...)
        
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Round {round_num}: FAILED")
        
        # 日志路径提示
        print(f"""
📄 Full logs:
   - System:    logs/reloop.log
   - Driver:   run-sets/{run_id}/logs/driver.log
   - Executor: run-sets/{run_id}/logs/executor.log
   - Prompt:   run-sets/{run_id}/logs/prompt.log
""")
```

## Mock Driver 改进

### 当前实现

```python
class MockDriver(Driver):
    def __init__(self, responses: List[str]):
        self.responses = list(responses)
    
    def run(self, prompt: str, workdir: str, ...) -> str:
        if not self.responses:
            raise MockDriverExhaustedError(...)
        return self.responses.pop(0)
```

### 新实现

```python
class MockDriver(Driver):
    def __init__(
        self,
        responses: List[str],
        delay_per_line: float = 0.1,  # 模拟流式延迟
    ):
        self.responses = list(responses)
        self.delay_per_line = delay_per_line
    
    def run(
        self,
        prompt: str,
        workdir: str,
        output: str | None = None,
        timeout: int | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> str:
        if not self.responses:
            raise MockDriverExhaustedError(...)
        
        response = self.responses.pop(0)
        
        # 模拟流式输出
        if stream_callback:
            lines = response.split("\n")
            for line in lines:
                time.sleep(self.delay_per_line)
                stream_callback(line)
        
        return response
```

## 配置项

```python
STREAM_CONFIG = {
    "max_lines": 4,              # 终端显示行数
    "timestamp_format": "%H:%M:%S",
    "delay_per_line": 0.05,       # Mock Driver 延迟
}
```

## 测试场景

| 场景 | 测试要点 |
|------|----------|
| 短输出 | 完整显示 |
| 长输出 | 滚动显示 |
| 空输出 | 无报错 |
| Mock 流式 | 回调被调用 |
| 真实 Driver | 流式输出正常 |
| 日志文件 | 内容完整 |
| 路径提示 | 格式正确 |

## 验收标准

- [ ] Driver 接口支持流式回调
- [ ] StreamOutput 类正确实现
- [ ] 终端滚动显示工作正常
- [ ] 日志文件写入完整内容
- [ ] 路径提示清晰准确
- [ ] Mock Driver 支持流式
- [ ] 真实 Driver 可用
- [ ] 测试覆盖所有场景
