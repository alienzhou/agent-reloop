# 中断恢复机制设计

## 问题背景

任务运行过程中可能因各种原因中断：
- 用户主动停止（Ctrl+C）
- 网络中断
- 系统崩溃
- 超时

当前实现没有恢复机制，下次运行会从头开始，造成：
- 已完成工作丢失
- 重复执行成功的轮次
- 浪费时间和资源

## 设计目标

1. **智能恢复**：自动检测中断状态
2. **灵活选择**：用户可选择继续或重新开始
3. **安全回滚**：确保状态一致性
4. **简单交互**：清晰的提示和操作

## 状态定义

### Run 状态

| 状态 | 含义 | 可恢复性 |
|------|------|----------|
| `running` | 正在执行 | ❌ 不可恢复 |
| `completed` | 成功完成 | ✅ 可恢复（已通过） |
| `failed` | 失败 | ✅ 可恢复（需重试） |
| `interrupted` | 用户中断 | ⚠️ 需回滚 |

### 判断逻辑

```python
def detect_run_status(project_root: Path) -> str:
    """检测项目状态"""
    run_sets_dir = project_root / "run-sets"
    
    if not run_sets_dir.exists():
        return "fresh"  # 全新项目
    
    runs = sorted(run_sets_dir.iterdir())
    if not runs:
        return "fresh"
    
    last_run = runs[-1]
    last_run_name = last_run.name
    
    # 检查是否有 checker 结果
    report_dir = last_run / "eval-report"
    if not (report_dir / "report.md").exists():
        return "interrupted"  # 没有评估报告，中断
    
    # 检查 Git commit 是否完整
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=project_root, capture_output=True, text=True
    )
    last_commit = result.stdout.strip()
    
    if last_run_name not in last_commit:
        return "interrupted"  # 最后的 commit 不匹配
    
    # 检查 checker 结果
    report = (report_dir / "report.md").read_text()
    if "PASSED" in report.upper():
        return "completed"  # 已通过
    
    return "failed"  # 未通过
```

## 恢复策略

### 策略矩阵

| 状态 | 操作 | 说明 |
|------|------|------|
| `fresh` | 直接启动 | 无历史状态 |
| `completed` | 提示选择 | 已成功，可继续或重置 |
| `failed` | 继续迭代 | 从失败点继续 |
| `interrupted` | 回滚后继续 | 回滚不完整的 run |

### 恢复流程

```
启动 run_loop
    ↓
检测状态
    ↓
┌─ fresh ────────────────→ 直接启动
│
├─ completed ────→ 提示用户选择
│                    ├─ 继续 → 直接启动（已有成功结果，为什么继续？）
│                    └─ 重置 → clean + 启动
│
├─ failed ────────→ 继续迭代（从上次失败处）
│
└─ interrupted ───→ 回滚不完整 run
                      ↓
                    继续迭代
```

## 用户交互

### CLI 参数

```bash
# 正常启动（默认继续）
reloop run

# 强制从头开始
reloop run --fresh

# 强制清理并启动
reloop run --fresh --clean
```

### 交互提示

当检测到历史状态时：

```
检测到已有运行记录：
  - 最近运行: run-003
  - 状态: 已中断（未完成评估）
  
请选择：
  [1] 继续运行（从 run-003 重新开始）
  [2] 完全重置并从头运行
  
请输入选择 [1/2] (默认: 1): 
```

### 状态为 completed 时

```
检测到已有运行记录：
  - 最近运行: run-005
  - 状态: 已完成（通过）
  
⚠️ 任务已在 run-005 成功完成
  
请选择：
  [1] 继续运行（检查是否有新需求）
  [2] 完全重置并重新运行
  
请输入选择 [1/2] (默认: 1): 
```

## 回滚实现

### 回滚不完整 run

```python
def rollback_incomplete_run(project_root: Path, run_id: str) -> None:
    """回滚不完整的 run"""
    run_dir = project_root / "run-sets" / run_id
    
    # 1. Git 回滚到该 run 之前的 commit
    result = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        cwd=project_root, capture_output=True, text=True
    )
    commits = result.stdout.strip().splitlines()
    
    # 找到该 run 的 commit
    run_commit_idx = None
    for i, commit in enumerate(commits):
        if run_id in commit:
            run_commit_idx = i
            break
    
    if run_commit_idx and run_commit_idx > 0:
        # 回滚到前一个 commit
        prev_commit = commits[run_commit_idx - 1].split()[0]
        subprocess.run(
            ["git", "reset", "--hard", prev_commit],
            cwd=project_root, check=True
        )
    
    # 2. 删除 run 目录
    if run_dir.exists():
        shutil.rmtree(run_dir)
    
    logger.info(f"Rolled back incomplete run: {run_id}")
```

### 完全清理

```python
def full_cleanup(project_root: Path) -> None:
    """完全清理，回到初始状态"""
    # 1. Git 回滚到初始 commit
    result = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        cwd=project_root, capture_output=True, text=True
    )
    first_commit = result.stdout.strip().splitlines()[0].split()[0]
    
    subprocess.run(
        ["git", "reset", "--hard", first_commit],
        cwd=project_root, check=True
    )
    
    # 2. 删除所有 run-sets
    run_sets_dir = project_root / "run-sets"
    if run_sets_dir.exists():
        shutil.rmtree(run_sets_dir)
    
    # 3. 清理 solution（可选）
    # solution_dir = project_root / "task" / "solution"
    # if solution_dir.exists():
    #     shutil.rmtree(solution_dir)
    
    logger.info("Full cleanup completed")
```

## 状态持久化

### 状态文件（可选增强）

```yaml
# run-sets/.state.yaml
last_run: run-003
status: interrupted
rounds_completed: 2
last_check_time: 2026-04-15T11:30:20
checkpoint_commit: abc123
```

### 优点

- 更精确的状态记录
- 避免重复检测
- 支持更复杂的恢复场景

### 缺点

- 需要维护额外文件
- 可能与实际状态不同步

**建议**：当前版本不引入状态文件，使用检测结果为准。

## 集成点

### run_loop 入口

```python
def run_loop(
    project_root: Path,
    intent: str,
    eval_skill: str,
    executor_driver: Driver,
    # ... 其他参数
    fresh: bool = False,  # 新增参数
    interactive: bool = True,  # 新增参数
) -> LoopResult:
    """执行 Reloop 迭代主循环。"""
    
    # 检测状态
    status = detect_run_status(project_root) if not fresh else "fresh"
    
    # 非全新状态时处理恢复
    if status != "fresh":
        if interactive and not fresh:
            choice = prompt_resume_choice(status)
            if choice == "reset":
                full_cleanup(project_root)
                status = "fresh"
            elif status == "interrupted":
                rollback_incomplete_run(project_root, get_last_run_id(project_root))
        
        elif fresh:
            full_cleanup(project_root)
            status = "fresh"
    
    # 执行主循环
    # ...
```

### CLI 集成

```python
# reloop/cli.py

@app.command()
def run(
    fresh: bool = typer.Option(
        False, "--fresh", "-f", help="强制从头开始，忽略历史状态"
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="非交互模式，使用默认选择"
    ),
):
    """运行 Reloop 迭代循环。"""
    run_loop(
        project_root=Path.cwd(),
        intent=...,
        eval_skill=...,
        executor_driver=...,
        fresh=fresh,
        interactive=not non_interactive,
    )
```

## 测试场景

| 场景 | 预期行为 |
|------|----------|
| 全新项目 | 直接启动 |
| 已通过 + 继续 | 保持状态 |
| 已通过 + 重置 | 清理后启动 |
| 已失败 + 继续 | 继续迭代 |
| 已失败 + 重置 | 清理后启动 |
| 中断 + 继续 | 回滚后继续 |
| 中断 + 重置 | 清理后启动 |
| --fresh | 强制重置 |

## 验收标准

- [ ] 正确检测四种状态
- [ ] 交互提示清晰友好
- [ ] 回滚操作安全可靠
- [ ] --fresh 参数生效
- [ ] 非交互模式可用
- [ ] 日志记录恢复操作
- [ ] 测试覆盖所有场景
