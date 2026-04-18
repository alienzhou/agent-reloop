"""Reloop CLI — 命令行接口。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="reloop",
    help="Reloop - 自迭代 Agent 框架",
    add_completion=False,
)


@app.command()
def init(
    language: str = typer.Option(
        None, "--lang", "-l", help="项目语言模板 (python/java/go/node)"
    ),
    no_git: bool = typer.Option(
        False, "--no-git", help="跳过 Git 初始化"
    ),
) -> None:
    """初始化项目 Git 和配置。"""
    from reloop.core.git_utils import ensure_git_repo, init_git_repo, is_git_repo
    from reloop.core.gitignore import generate_gitignore, get_available_languages

    project_root = Path.cwd()

    # Git 初始化
    if not no_git:
        if is_git_repo(project_root):
            print("✓ 已是 Git 仓库")
        else:
            init_git_repo(project_root)
            print("✓ Git 仓库已初始化")

    # .gitignore 生成
    if language:
        if language not in get_available_languages():
            print(f"❌ 不支持的语言: {language}")
            print(f"   可用语言: {', '.join(get_available_languages())}")
            raise typer.Exit(1)
        generate_gitignore(project_root, language)
        print(f"✓ 已生成 .gitignore ({language})")
    else:
        # 自动检测
        from reloop.core.gitignore import detect_project_language
        detected = detect_project_language(project_root)
        generate_gitignore(project_root, detected)
        print(f"✓ 已生成 .gitignore ({detected}，自动检测)")

    # 创建目录结构
    (project_root / "task").mkdir(exist_ok=True)
    (project_root / "task" / "solution").mkdir(exist_ok=True)
    (project_root / "task" / "solution" / ".gitkeep").write_text("")
    (project_root / "run-sets").mkdir(exist_ok=True)
    (project_root / "run-sets" / ".gitkeep").write_text("")
    (project_root / "logs").mkdir(exist_ok=True)
    (project_root / "logs" / ".gitkeep").write_text("")
    print("✓ 目录结构已创建")

    print("\n项目初始化完成！")


@app.command()
def run(
    fresh: bool = typer.Option(
        False, "--fresh", "-f", help="强制从头开始，忽略历史状态"
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="非交互模式，使用默认选择"
    ),
    intent_file: Path = typer.Option(
        None, "--intent", "-i", help="INTENT 文件路径"
    ),
    eval_file: Path = typer.Option(
        None, "--eval", "-e", help="Evaluator Skill 文件路径"
    ),
    max_iterations: int = typer.Option(
        10, "--max", "-m", help="最大迭代次数"
    ),
    no_git_commit: bool = typer.Option(
        False, "--no-git-commit", help="禁用自动 Git commit"
    ),
) -> None:
    """运行 Reloop 迭代循环。"""
    from reloop.core.loop import run_loop
    from reloop.drivers.mock import MockDriver

    project_root = Path.cwd()

    # 读取 INTENT
    if intent_file:
        intent = intent_file.read_text(encoding="utf-8")
    else:
        default_intent = project_root / "task" / "INTENT.md"
        if default_intent.exists():
            intent = default_intent.read_text(encoding="utf-8")
        else:
            print("❌ 未找到 INTENT 文件")
            print("   请创建 task/INTENT.md 或使用 --intent 指定")
            raise typer.Exit(1)

    # 读取 Evaluator Skill
    if eval_file:
        eval_skill = eval_file.read_text(encoding="utf-8")
    else:
        default_eval = project_root / "task" / "EVAL_SKILL.md"
        if default_eval.exists():
            eval_skill = default_eval.read_text(encoding="utf-8")
        else:
            print("❌ 未找到 Evaluator Skill 文件")
            print("   请创建 task/EVAL_SKILL.md 或使用 --eval 指定")
            raise typer.Exit(1)

    # 使用 Mock Driver（实际使用时替换为真实 Driver）
    # TODO: 支持配置真实 Driver
    print("⚠️  使用 Mock Driver（仅用于演示）")
    executor_driver = MockDriver(responses=["Executor output", "Evaluator output", "passed"])

    try:
        result = run_loop(
            project_root=project_root,
            intent=intent,
            eval_skill=eval_skill,
            executor_driver=executor_driver,
            max_iterations=max_iterations,
            enable_git_commit=not no_git_commit,
            fresh=fresh,
            interactive=not non_interactive,
        )

        print(f"\n✅ 迭代完成！")
        print(f"   成功: {result.success}")
        print(f"   轮数: {result.rounds}")
        print(f"   Runs: {', '.join(result.run_ids)}")

    except Exception as e:
        print(f"\n❌ 运行失败: {e}")
        raise typer.Exit(1)


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
) -> None:
    """清理运行记录，回滚到初始状态。"""
    from reloop.core.resume import full_cleanup

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

        try:
            choice = typer.confirm("确定要继续吗？", default=False)
            if not choice:
                print("已取消")
                return
        except KeyboardInterrupt:
            print("\n已取消")
            return

    # 执行清理
    try:
        full_cleanup(project_root, keep_logs=keep_logs)

        # 清理 solution（可选）
        if not keep_solution:
            solution_dir = project_root / "task" / "solution"
            if solution_dir.exists():
                for item in solution_dir.iterdir():
                    if item.name == ".gitkeep":
                        continue
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                print("  ✓ 已清空 task/solution/")

        print("✓ 清理完成")

    except Exception as e:
        print(f"❌ 清理失败: {e}")
        raise typer.Exit(1)


@app.command()
def link(
    target: Path = typer.Argument(
        ..., help="外部项目路径", exists=True
    ),
    name: str = typer.Option(
        None, "--name", "-n", help="软链名称（默认为目标目录名）"
    ),
) -> None:
    """创建到外部项目的软链。"""
    project_root = Path.cwd()
    external_dir = project_root / "external"
    external_dir.mkdir(exist_ok=True)

    # 确定软链名称
    link_name = name or target.name
    link_path = external_dir / link_name

    # 检查软链是否已存在
    if link_path.exists() or link_path.is_symlink():
        print(f"❌ 已存在同名文件: {link_path}")
        raise typer.Exit(1)

    # 创建软链
    try:
        link_path.symlink_to(target.resolve())
        print(f"✓ 已创建软链: {link_path} -> {target}")
    except OSError as e:
        print(f"❌ 创建软链失败: {e}")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """查看当前项目状态。"""
    from reloop.core.git_utils import get_commit_message, get_current_commit_hash, is_git_repo
    from reloop.core.resume import RunStatus, detect_run_status, get_last_run_id

    project_root = Path.cwd()

    print("=== Reloop Status ===\n")

    # Git 状态
    if is_git_repo(project_root):
        commit_hash = get_current_commit_hash(project_root)
        commit_msg = get_commit_message(project_root, commit_hash) if commit_hash else "Unknown"
        print(f"Git: {commit_hash[:7] if commit_hash else 'N/A'} {commit_msg}")
    else:
        print("Git: 未初始化")

    print()

    # Runs 统计
    run_sets_dir = project_root / "run-sets"
    if run_sets_dir.exists():
        runs = [
            d for d in run_sets_dir.iterdir()
            if d.is_dir() and d.name.startswith("run-")
        ]
        print(f"Runs: {len(runs)} 次运行")

        if runs:
            last_run = sorted(runs)[-1]
            status = detect_run_status(project_root)
            status_text = {
                RunStatus.COMPLETED: "✅ 已通过",
                RunStatus.FAILED: "❌ 未通过",
                RunStatus.INTERRUPTED: "⚠️  已中断",
                RunStatus.FRESH: "🆕 全新",
            }.get(status, "未知")
            print(f"最近: {last_run.name} - {status_text}")
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

    # INTENT 文件
    intent_file = project_root / "task" / "INTENT.md"
    if intent_file.exists():
        print(f"\nINTENT: ✅ 已定义")
    else:
        print(f"\nINTENT: ❌ 未定义")

    # EVAL_SKILL 文件
    eval_file = project_root / "task" / "EVAL_SKILL.md"
    if eval_file.exists():
        print(f"EVAL_SKILL: ✅ 已定义")
    else:
        print(f"EVAL_SKILL: ❌ 未定义")


def main() -> None:
    """CLI 入口点。"""
    app()


if __name__ == "__main__":
    main()
