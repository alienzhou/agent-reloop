# 缺失功能实现设计

> 更新时间：2026-04-19

本文档整理需要补全的功能，基于 `.discuss/` 讨论和 `docs/improvements/` 设计文档。

---

## 一、功能清单

| 编号 | 功能 | 优先级 | 来源 |
|------|------|--------|------|
| F01 | `prompt_resume_choice` 用户交互 | 高 | 03-resume-design.md |
| F02 | `FlickDriver` 流式输出 | 高 | 06-driver-design.md |
| F03 | 更新 `task-list.md` 状态 | 低 | 文档维护 |

> 注：`extract_checker_explanation` 已在 `checker.py` 中实现（第 59-76 行）。

---

## 二、F01: prompt_resume_choice 用户交互

### 设计来源

`docs/improvements/03-resume-design.md` 第 122-150 行定义了交互提示：

```
检测到已有运行记录：
  - 最近运行: run-003
  - 状态: 已中断（未完成评估）
  
请选择：
  [1] 继续运行（从 run-003 重新开始）
  [2] 完全重置并从头运行
  
请输入选择 [1/2] (默认: 1): 
```

### 接口设计

```python
# reloop/core/resume.py

from enum import Enum
from typing import Optional

class ResumeChoice(str, Enum):
    """恢复选择枚举。"""
    CONTINUE = "continue"  # 继续运行
    RESET = "reset"        # 完全重置

def prompt_resume_choice(
    status: RunStatus,
    last_run_id: Optional[str] = None,
    interactive: bool = True,
) -> ResumeChoice:
    """提示用户选择恢复策略。
    
    Args:
        status: 当前项目状态
        last_run_id: 最近的 run ID
        interactive: 是否交互模式
        
    Returns:
        用户选择的恢复策略
    """
```

### 实现逻辑

```python
def prompt_resume_choice(
    status: RunStatus,
    last_run_id: Optional[str] = None,
    interactive: bool = True,
) -> ResumeChoice:
    """提示用户选择恢复策略。"""
    
    # 非交互模式：使用默认选择
    if not interactive:
        # 中断状态默认继续，已完成默认继续
        return ResumeChoice.CONTINUE
    
    # 构建状态描述
    status_desc = {
        RunStatus.COMPLETED: "已完成（通过）",
        RunStatus.FAILED: "未通过",
        RunStatus.INTERRUPTED: "已中断（未完成评估）",
    }.get(status, "未知")
    
    # 显示提示
    print(f"\n检测到已有运行记录：")
    if last_run_id:
        print(f"  - 最近运行: {last_run_id}")
    print(f"  - 状态: {status_desc}")
    print()
    
    # 特殊提示：已完成时
    if status == RunStatus.COMPLETED:
        print("⚠️  任务已成功完成")
        print()
    
    print("请选择：")
    print("  [1] 继续运行（从上次状态继续）")
    print("  [2] 完全重置并从头运行")
    print()
    
    # 获取用户输入
    while True:
        try:
            choice = input("请输入选择 [1/2] (默认: 1): ").strip()
            if choice == "" or choice == "1":
                return ResumeChoice.CONTINUE
            elif choice == "2":
                return ResumeChoice.RESET
            else:
                print("无效输入，请输入 1 或 2")
        except KeyboardInterrupt:
            print("\n已取消")
            raise SystemExit(0)
```

### 集成点

在 `run_loop` 中调用：

```python
# reloop/core/loop.py

def run_loop(
    project_root: Path,
    # ...
    fresh: bool = False,
    interactive: bool = True,
) -> LoopResult:
    """执行 Reloop 迭代主循环。"""
    
    # 检测状态
    if not fresh:
        status = detect_run_status(project_root)
        
        if status != RunStatus.FRESH:
            last_run_id = get_last_run_id(project_root)
            
            if interactive:
                choice = prompt_resume_choice(status, last_run_id)
                
                if choice == ResumeChoice.RESET:
                    full_cleanup(project_root)
                elif status == RunStatus.INTERRUPTED:
                    rollback_incomplete_run(project_root, last_run_id)
            else:
                # 非交互模式：中断状态自动回滚
                if status == RunStatus.INTERRUPTED:
                    rollback_incomplete_run(project_root, last_run_id)
    else:
        # --fresh 参数：完全清理
        full_cleanup(project_root)
    
    # 继续主循环...
```

### 测试用例

```python
# tests/unit/test_resume.py

import pytest
from unittest.mock import patch
from reloop.core.resume import (
    prompt_resume_choice,
    ResumeChoice,
    RunStatus,
)


def test_prompt_resume_choice_non_interactive():
    """非交互模式返回默认值。"""
    result = prompt_resume_choice(
        RunStatus.INTERRUPTED,
        last_run_id="run-001",
        interactive=False,
    )
    assert result == ResumeChoice.CONTINUE


def test_prompt_resume_choice_interactive_default(monkeypatch):
    """交互模式，直接回车使用默认值。"""
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = prompt_resume_choice(
        RunStatus.FAILED,
        last_run_id="run-002",
        interactive=True,
    )
    assert result == ResumeChoice.CONTINUE


def test_prompt_resume_choice_interactive_reset(monkeypatch):
    """交互模式，选择重置。"""
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = prompt_resume_choice(
        RunStatus.FAILED,
        last_run_id="run-002",
        interactive=True,
    )
    assert result == ResumeChoice.RESET
```

---

## 三、F02: FlickDriver 流式输出

### 设计来源

`docs/improvements/06-driver-design.md` 第 130-178 行定义了流式输出机制。

### 当前问题

`FlickDriver.run()` 接收 `stream_callback` 参数但未使用：

```python
def run(
    self,
    prompt: str,
    workdir: str,
    output: Optional[str] = None,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,  # 未使用
) -> str:
```

### 实现方案

```python
# reloop/drivers/flick.py

import subprocess
from typing import Callable, Optional


class FlickDriver(Driver):
    """DuetSpace Gateway CLI 适配器。"""
    
    def run(
        self,
        prompt: str,
        workdir: str,
        output: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """发送 prompt 到 Duet Workspace，支持流式输出。"""
        
        # 构建命令
        cmd = self._build_command(prompt)
        
        # 流式执行
        if stream_callback:
            return self._run_with_streaming(cmd, workdir, timeout, stream_callback)
        else:
            return self._run_blocking(cmd, workdir, timeout)
    
    def _run_with_streaming(
        self,
        cmd: list[str],
        workdir: str,
        timeout: Optional[int],
        stream_callback: Callable[[str], None],
    ) -> str:
        """流式执行，实时回调输出。"""
        import select
        
        full_output: list[str] = []
        
        process = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # 行缓冲
        )
        
        try:
            # 逐行读取输出
            for line in process.stdout:
                full_output.append(line)
                stream_callback(line.rstrip("\n"))
            
            process.wait(timeout=timeout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise FlickDriverError(f"flick link prompt 超时 ({timeout}s)")
        
        if process.returncode != 0:
            raise FlickDriverError(
                f"flick link prompt 失败 (exit {process.returncode})"
            )
        
        response = "".join(full_output).strip()
        
        # JSON 处理（如果启用）
        if self.json_output and response:
            response = self._parse_json_response(response)
        
        return response
    
    def _run_blocking(
        self,
        cmd: list[str],
        workdir: str,
        timeout: Optional[int],
    ) -> str:
        """阻塞执行，等待完成后返回。"""
        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise FlickDriverError(f"flick link prompt 超时 ({timeout}s)")
        except FileNotFoundError:
            raise FlickDriverError("flick 命令未找到")
        
        if result.returncode != 0:
            raise FlickDriverError(
                f"flick link prompt 失败 (exit {result.returncode}): {result.stderr}"
            )
        
        response = result.stdout.strip()
        
        if self.json_output and response:
            response = self._parse_json_response(response)
        
        return response
    
    def _build_command(self, prompt: str) -> list[str]:
        """构建 flick 命令。"""
        cmd = ["flick", "link", "prompt"]
        cmd.extend(["--duet-workspace", self.workspace])
        
        if self.model:
            cmd.extend(["--duet-model", self.model])
        if self.mode:
            cmd.extend(["--duet-mode", self.mode])
        if self.json_output:
            cmd.append("--duet-json")
        
        cmd.append(prompt)
        return cmd
    
    def _parse_json_response(self, response: str) -> str:
        """解析 JSON 响应。"""
        import json
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return data.get("content", data.get("message", response))
        except json.JSONDecodeError:
            pass
        return response
```

### 测试用例

```python
# tests/unit/test_flick_driver.py

import pytest
from unittest.mock import patch, MagicMock
from reloop.drivers.flick import FlickDriver, FlickDriverError


def test_flick_driver_stream_callback():
    """测试流式回调被正确调用。"""
    driver = FlickDriver(workspace="test-workspace")
    
    collected_lines = []
    
    def callback(line: str):
        collected_lines.append(line)
    
    mock_process = MagicMock()
    mock_process.stdout = iter(["Line 1\n", "Line 2\n", "Line 3\n"])
    mock_process.returncode = 0
    mock_process.wait.return_value = None
    
    with patch("subprocess.Popen", return_value=mock_process):
        result = driver.run(
            prompt="test",
            workdir="/tmp",
            stream_callback=callback,
        )
    
    assert collected_lines == ["Line 1", "Line 2", "Line 3"]
    assert "Line 1" in result


def test_flick_driver_no_stream():
    """测试无回调时的阻塞模式。"""
    driver = FlickDriver(workspace="test-workspace")
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Response text"
    
    with patch("subprocess.run", return_value=mock_result):
        result = driver.run(prompt="test", workdir="/tmp")
    
    assert result == "Response text"
```

---

## 四、F03: 更新 task-list.md

### 当前问题

`docs/improvements/task-list.md` 中所有任务都标记为 `[ ]`，但大部分已经完成。

### 建议

将已完成的任务更新为 `[x]`，保持文档准确性。

参考 `docs/improvements/implementation-status.md` 的完成状态。

---

## 五、实施顺序

1. **F01: prompt_resume_choice** — 修改 `reloop/core/resume.py`
2. **F02: FlickDriver 流式输出** — 修改 `reloop/drivers/flick.py`
3. **F03: 更新 task-list.md** — 文档维护

---

## 六、验收标准

### F01: prompt_resume_choice

- [ ] 函数签名符合设计
- [ ] 交互模式正确显示提示
- [ ] 非交互模式返回默认值
- [ ] 集成到 `run_loop` 入口
- [ ] 测试覆盖

### F02: FlickDriver 流式输出

- [ ] `stream_callback` 被正确调用
- [ ] 无回调时退化为阻塞模式
- [ ] 超时处理正确
- [ ] 测试覆盖

### F03: task-list.md

- [ ] 已完成任务标记为 `[x]`
- [ ] 未完成任务保持 `[ ]`

---

## 参考文档

- `docs/improvements/03-resume-design.md` — 恢复机制详细设计
- `docs/improvements/06-driver-design.md` — Driver 流式输出设计
- `.discuss/2026-04-14/framework-improvements/outline.md` — 讨论决策
