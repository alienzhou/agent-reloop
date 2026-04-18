# CLI 命令设计

## 设计目标

1. **clean 命令**：清理运行记录，回滚到初始状态
2. **软链支持**：支持外部项目接入
3. **统一体验**：命令风格一致，提示清晰

## 命令概览

```
reloop init      # 初始化项目
reloop run       # 运行迭代循环
reloop clean     # 清理运行记录
reloop status    # 查看当前状态
```

## clean 命令

### 功能

清理所有运行记录，回滚到初始状态：
- 删除 `run-sets/` 下所有 runs
- 清空 `task/solution/` 内容
- Git 回滚到初始 commit
- 删除系统日志（可选）

### 实现

```python
@app.command()
def clean(
    force: bool = typer.Option(
        False, "--force", "-f", help="跳过确认提示"
    ),
    keep_logs: bool = typer.Option(
        False, "--keep-logs", help="保留日志文件"
    ),
    keep_solution: bool = typer.Option(
        False, "--keep-solution", help="保留 solution 目录"
    ),
):
    """清理运行记录，回滚到初始状态。"""
    project_root = Path.cwd()
    
    # 确认提示
    if not force:
        print("⚠️  此操作将删除所有运行记录并回滚 Git 历史")
        print("    - run-sets/ 下所有 runs 将被删除")
        print("    - task/solution/ 内容将被清空")
        print("    - Git 将回滚到初始 commit")
        if keep_logs:
            print("    - 日志文件将保留")
        if keep_solution:
            print("    - solution 目录将保留")
        
        choice = typer.confirm("确定要继续吗？", default=False)
        if not choice:
            print("已取消")
            return
    
    # 执行清理
    _clean_runs(project_root)
    
    if not keep_solution:
        _clean_solution(project_root)
    
    _reset_git(project_root)
    
    if not keep_logs:
        _clean_logs(project_root)
    
    print("✓ 清理完成")


def _clean_runs(project_root: Path) -> None:
    """删除所有 runs"""
    run_sets_dir = project_root / "run-sets"
    if not run_sets_dir.exists():
        return
    
    # 保留目录结构，只删除内容
    for run_dir in run_sets_dir.iterdir():
        if run_dir.is_dir() and run_dir.name.startswith("run-"):
            shutil.rmtree(run_dir)
            print(f"  ✓ 已删除 {run_dir.name}")
    
    # 添加 .gitkeep 保持目录
    (run_sets_dir / ".gitkeep").write_text("")


def _clean_solution(project_root: Path) -> None:
    """清空 solution 目录"""
    solution_dir = project_root / "task" / "solution"
    if not solution_dir.exists():
        return
    
    for item in solution_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    
    print("  ✓ 已清空 task/solution/")


def _reset_git(project_root: Path) -> None:
    """Git 回滚到初始 commit"""
    result = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        cwd=project_root, capture_output=True, text=True
    )
    
    commits = result.stdout.strip().splitlines()
    if not commits:
        return
    
    first_commit = commits[0].split()[0]
    subprocess.run(
        ["git", "reset", "--hard", first_commit],
        cwd=project_root, check=True
    )
    print(f"  ✓ Git 已回滚到 {first_commit}")


def _clean_logs(project_root: Path) -> None:
    """清理日志"""
    log_file = project_root / "logs" / "reloop.log"
    if log_file.exists():
        log_file.unlink()
        print("  ✓ 已清理日志")
```

## 软链支持

### 使用方式

```bash
# 方式 1：手动创建软链
ln -s /path/to/external/project ./external/project

# 方式 2：CLI 辅助命令
reloop link /path/to/external/project
```

### link 命令

```python
@app.command()
def link(
    target: Path = typer.Argument(
        ..., help="外部项目路径"
    ),
    name: str = typer.Option(
        None, "--name", "-n", help="软链名称（默认为目标目录名）"
    ),
):
    """创建到外部项目的软链。"""
    project_root = Path.cwd()
    external_dir = project_root / "external"
    external_dir.mkdir(exist_ok=True)
    
    # 确定软链名称
    link_name = name or target.name
    link_path = external_dir / link_name
    
    # 检查目标是否存在
    if not target.exists():
        print(f"❌ 目标路径不存在: {target}")
        raise typer.Exit(1)
    
    if not target.is_dir():
        print(f"❌ 目标不是目录: {target}")
        raise typer.Exit(1)
    
    # 检查软链是否已存在
    if link_path.exists() or link_path.is_symlink():
        print(f"❌ 已存在同名文件: {link_path}")
        raise typer.Exit(1)
    
    # 创建软链
    link_path.symlink_to(target.resolve())
    print(f"✓ 已创建软链: {link_path} -> {target}")
```

### 在 run_loop 中使用软链

```python
# 检测 external 目录下的软链
def detect_external_links(project_root: Path) -> List[Path]:
    """检测外部软链"""
    external_dir = project_root / "external"
    if not external_dir.exists():
        return []
    
    links = []
    for item in external_dir.iterdir():
        if item.is_symlink():
            links.append(item.resolve())
    return links
```

### 工作流程

```
外部项目（已有代码）
    ↑
    │ (软链)
    │
external/project/
    ↑
    │ (引用)
    │
task/solution/  ← executor 在这里写代码
                  ↑
                  │ (软链到外部)
                  │
                  └─→ external/project/src/
```

**实现方式**：
- 用户手动将 `task/solution/` 软链到外部项目
- 或者 executor 直接写入 `external/project/`

## status 命令

```python
@app.command()
def status():
    """查看当前项目状态。"""
    project_root = Path.cwd()
    
    print("=== Reloop Status ===\n")
    
    # Git 状态
    if is_git_repo(project_root):
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%cr)"],
            cwd=project_root, capture_output=True, text=True
        )
        print(f"Git: {result.stdout.strip()}")
    else:
        print("Git: 未初始化")
    
    print()
    
    # Runs 统计
    run_sets_dir = project_root / "run-sets"
    if run_sets_dir.exists():
        runs = [d for d in run_sets_dir.iterdir() 
                if d.is_dir() and d.name.startswith("run-")]
        print(f"Runs: {len(runs)} 次运行")
        
        if runs:
            last_run = sorted(runs)[-1]
            report = last_run / "eval-report" / "report.md"
            if report.exists():
                content = report.read_text()
                if "PASSED" in content.upper():
                    status = "✅ 已通过"
                else:
                    status = "❌ 未通过"
                print(f"最近: {last_run.name} - {status}")
    else:
        print("Runs: 0 次运行")
    
    print()
    
    # 外部链接
    external_dir = project_root / "external"
    if external_dir.exists():
        links = [l for l in external_dir.iterdir() if l.is_symlink()]
        if links:
            print("外部链接:")
            for link in links:
                target = link.resolve()
                print(f"  - {link.name} -> {target}")
```

## 命令帮助文本

```
$ reloop --help

Reloop - 自迭代 Agent 框架

Commands:
  init       初始化项目 Git 和配置
  run        运行迭代循环
  clean      清理运行记录，回滚到初始状态
  link       创建到外部项目的软链
  status     查看当前项目状态

Run `reloop COMMAND --help` for more information.
```

## 测试场景

| 命令 | 场景 | 预期结果 |
|------|------|----------|
| clean | 空项目 | 无操作 |
| clean -f | 有 runs | 删除 runs |
| clean --keep-logs | 有 logs | 保留 logs |
| clean --keep-solution | 有 solution | 保留 solution |
| link | 有效路径 | 创建软链 |
| link | 无效路径 | 报错退出 |
| link | 已存在 | 报错退出 |
| status | 新项目 | 显示未初始化 |
| status | 有 runs | 显示统计 |

## 验收标准

- [ ] clean 命令完整实现
- [ ] link 命令可用
- [ ] status 命令信息完整
- [ ] 命令帮助文本清晰
- [ ] 确认提示友好
- [ ] 错误处理完善
- [ ] 测试覆盖所有命令
