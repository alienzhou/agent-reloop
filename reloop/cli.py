"""Reloop CLI — 命令行接口。"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="reloop",
    help="Reloop - 自迭代 Agent 框架",
    add_completion=False,
)


def _init_project(
    language: str | None = None,
    no_git: bool = False,
) -> None:
    """初始化项目 Git 和配置（内部函数）。"""
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
    (project_root / "task" / "scripts").mkdir(exist_ok=True)
    (project_root / "task" / "scripts" / ".gitkeep").write_text("")
    (project_root / "run-sets").mkdir(exist_ok=True)
    (project_root / "run-sets" / ".gitkeep").write_text("")
    (project_root / "logs").mkdir(exist_ok=True)
    (project_root / "logs" / ".gitkeep").write_text("")
    print("✓ 目录结构已创建")

    print("\n项目初始化完成！")


def _get_meta_skill_path(skill_name: str) -> Path:
    """获取 Meta Skill 文件路径。"""
    # 从 reloop 包目录查找
    reloop_pkg = Path(__file__).parent
    skill_path = reloop_pkg / "meta_skills" / f"{skill_name}.md"
    return skill_path


def _init_intent() -> None:
    """启动 INTENT Builder，交互式生成 INTENT.md。"""
    project_root = Path.cwd()
    intent_file = project_root / "task" / "INTENT.md"
    skill_path = _get_meta_skill_path("intent_builder")

    print("🎯 INTENT Builder")
    print("=" * 40)

    if intent_file.exists():
        print(f"⚠️  已存在 INTENT 文件: {intent_file}")
        try:
            overwrite = typer.confirm("是否覆盖？", default=False)
            if not overwrite:
                print("已取消")
                return
        except KeyboardInterrupt:
            print("\n已取消")
            return

    # 检查 Meta Skill 文件是否存在
    if not skill_path.exists():
        print(f"⚠️  INTENT Builder Skill 文件未找到: {skill_path}")
        print("   请确保 reloop/meta_skills/intent_builder.md 存在")
        print("\n提示: 你可以手动创建 task/INTENT.md，格式如下:")
        print(_get_intent_template())
        raise typer.Exit(1)

    # 显示引导信息
    skill_content = skill_path.read_text(encoding="utf-8")
    print("\n请在 AI 对话中使用以下 Skill 引导生成 INTENT:")
    print(f"  📄 Skill 文件: {skill_path}")
    print(f"  📁 输出位置: {intent_file}")
    print("\n或者手动创建 task/INTENT.md，格式如下:")
    print(_get_intent_template())


def _get_intent_template() -> str:
    """获取 INTENT 模板。"""
    return """
```markdown
# Task Intent

## 目标
[一句话描述最终目标]

## 背景
[任务的上下文和动机]

## 输入
[输入内容的描述]

## 输出
[期望输出的描述]

## 约束
[任何限制或边界条件]
```
"""


def _init_evaluator() -> None:
    """启动 Evaluator Builder，交互式生成 EVAL_SKILL.md。"""
    project_root = Path.cwd()
    eval_file = project_root / "task" / "EVAL_SKILL.md"
    intent_file = project_root / "task" / "INTENT.md"
    skill_path = _get_meta_skill_path("evaluator_builder")

    print("📋 Evaluator Builder")
    print("=" * 40)

    # 检查 INTENT 是否存在
    if not intent_file.exists():
        print("⚠️  建议先创建 INTENT.md")
        print("   运行: reloop init intent")
        try:
            proceed = typer.confirm("是否继续？", default=True)
            if not proceed:
                return
        except KeyboardInterrupt:
            print("\n已取消")
            return

    if eval_file.exists():
        print(f"⚠️  已存在 Evaluator 文件: {eval_file}")
        try:
            overwrite = typer.confirm("是否覆盖？", default=False)
            if not overwrite:
                print("已取消")
                return
        except KeyboardInterrupt:
            print("\n已取消")
            return

    # 检查 Meta Skill 文件是否存在
    if not skill_path.exists():
        print(f"⚠️  Evaluator Builder Skill 文件未找到: {skill_path}")
        print("   请确保 reloop/meta_skills/evaluator_builder.md 存在")
        print("\n提示: 你可以手动创建 task/EVAL_SKILL.md，格式如下:")
        print(_get_evaluator_template())
        raise typer.Exit(1)

    # 显示引导信息
    print("\n请在 AI 对话中使用以下 Skill 引导生成 Evaluator:")
    print(f"  📄 Skill 文件: {skill_path}")
    print(f"  📁 输出位置: {eval_file}")
    if intent_file.exists():
        print(f"  📖 INTENT 文件: {intent_file}")
    print("\n或者手动创建 task/EVAL_SKILL.md，格式如下:")
    print(_get_evaluator_template())


def _get_evaluator_template() -> str:
    """获取 Evaluator 模板。

    注意：L0 / L1 是纯脚本验证层，检查项直接编码进脚本里，
    不在 Markdown 中重复写 checklist（避免文档与脚本漂移）。
    只有 L2（LLM 判断）才需要在文档中写评估标准。
    """
    return """
```markdown
# Evaluator Skill

## L0 - 安全检查
**执行**：运行 `task/scripts/check_l0.py`
脚本 exit 0 = 通过，非 0 = 失败。检查项定义在脚本内，不在此列出。

## L1 - 机械性验证
**执行**：运行 `task/scripts/check_l1.py`
脚本 exit 0 = 通过，非 0 = 失败。检查项定义在脚本内，不在此列出。

## L2 - 质量验证

### 评估标准
- [语义、质量等需要 LLM 判断的标准，逐条列出]

### 评估提示词
[LLM 评估时使用的 prompt]

## 评估流程
1. 运行 `check_l0.py`，失败则停止
2. 运行 `check_l1.py`，失败则停止
3. 用 LLM 按 L2 评估标准打分
4. 汇总结果
```
"""


def _init_mock() -> None:
    """运行 Mocker，生成 Mock solution 并验证 Evaluator。"""
    project_root = Path.cwd()
    eval_file = project_root / "task" / "EVAL_SKILL.md"
    mock_dir = project_root / "run-sets" / "run-mock" / "solution"
    skill_path = _get_meta_skill_path("mocker")

    print("🎭 Mocker")
    print("=" * 40)

    # 检查 Evaluator 是否存在
    if not eval_file.exists():
        print("❌ 未找到 Evaluator 文件: task/EVAL_SKILL.md")
        print("   请先运行: reloop init evaluator")
        raise typer.Exit(1)

    # 检查 Mock 目录是否存在
    if mock_dir.exists() and any(mock_dir.iterdir()):
        print(f"⚠️  Mock solution 目录已存在: {mock_dir}")
        try:
            overwrite = typer.confirm("是否清空并重新生成？", default=False)
            if not overwrite:
                print("已取消")
                return
            # 清空目录
            shutil.rmtree(mock_dir)
        except KeyboardInterrupt:
            print("\n已取消")
            return

    # 创建 Mock 目录
    mock_dir.mkdir(parents=True, exist_ok=True)

    # 检查 Meta Skill 文件是否存在
    if not skill_path.exists():
        print(f"⚠️  Mocker Skill 文件未找到: {skill_path}")
        print("   请确保 reloop/meta_skills/mocker.md 存在")
        raise typer.Exit(1)

    # 显示引导信息
    print("\n请在 AI 对话中使用以下 Skill 生成 Mock solution:")
    print(f"  📄 Skill 文件: {skill_path}")
    print(f"  📖 Evaluator 文件: {eval_file}")
    print(f"  📁 输出目录: {mock_dir}")
    print("\nMocker 将:")
    print("  1. 读取 EVAL_SKILL.md 中的 L0/L1/L2 标准")
    print("  2. 推断能通过所有检查的输出样本")
    print("  3. 生成 Mock solution 到 run-sets/run-mock/solution/")
    print("  4. 运行 Evaluator 验证 Mock 是否通过")


@app.command()
def init(
    target: str = typer.Argument(
        None,
        help="初始化目标: intent/evaluator/mock (留空则初始化项目)"
    ),
    language: str = typer.Option(
        None, "--lang", "-l", help="项目语言模板 (python/java/go/node)"
    ),
    no_git: bool = typer.Option(
        False, "--no-git", help="跳过 Git 初始化"
    ),
) -> None:
    """初始化项目或 Meta Skills。

    \b
    用法:
      reloop init              # 初始化项目（Git、目录结构）
      reloop init intent       # 启动 INTENT Builder
      reloop init evaluator    # 启动 Evaluator Builder
      reloop init mock         # 运行 Mocker

    \b
    Meta Skills 说明:
      intent     - 交互式定义任务目标，生成 task/INTENT.md
      evaluator  - 交互式定义评估标准，生成 task/EVAL_SKILL.md
      mock       - 生成 Mock solution，验证 Evaluator 逻辑
    """
    logger.info("Initializing project...")
    if target is None:
        # 原有的项目初始化逻辑
        _init_project(language, no_git)
    elif target == "intent":
        _init_intent()
    elif target == "evaluator":
        _init_evaluator()
    elif target == "mock":
        _init_mock()
    else:
        print(f"❌ 未知的初始化目标: {target}")
        print("   可用目标: intent, evaluator, mock")
        print("   或留空以初始化项目")
        raise typer.Exit(1)


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
    no_live_ui: bool = typer.Option(
        False, "--no-live-ui", help="禁用 Live UI 分区界面，使用经典输出模式"
    ),
    config: Path = typer.Option(
        None, "--config", "-c", help="配置文件路径 (默认: ./reloop.yaml)"
    ),
    from_phase: str = typer.Option(
        None, "--from-phase", "-p",
        help="从指定阶段开始 (evaluator/checker)，跳过已完成的阶段"
    ),
    executor_driver_opt: str = typer.Option(
        None, "--executor-driver",
        help="executor 使用的 driver 类型 (mock/flick/codex)，覆盖配置文件中的设置"
    ),
    evaluator_driver_opt: str = typer.Option(
        None, "--evaluator-driver",
        help="evaluator 使用的 driver 类型 (mock/flick/codex)，覆盖配置文件中的设置；不指定则复用 executor driver"
    ),
) -> None:
    """运行 Reloop 迭代循环。

    \b
    恢复选项:
      --from-phase evaluator  从 Evaluator 开始，复用已有的 solution
      --from-phase checker    从 Checker 开始，复用已有的 eval-report

    \b
    Driver 选项:
      --executor-driver codex   executor 使用 Codex CLI
      --evaluator-driver flick  evaluator 使用 Flick（与 executor 不同）
    """
    from reloop.config import load_config
    from reloop.core.loop import run_loop
    from reloop.drivers import create_driver_from_type, create_evaluator_driver, create_executor_driver

    logger.info("Starting reloop run: max_iterations=%d, fresh=%s", max_iterations, fresh)

    project_root = Path.cwd()

    # 加载配置
    cfg = load_config(config)
    logger.debug("Loaded config: workspace=%s", project_root)

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

    # 创建 Executor Driver
    # 优先级：命令行参数 > 配置文件 driver.executor.type > 配置文件 driver.type
    try:
        if executor_driver_opt:
            executor_driver = create_driver_from_type(executor_driver_opt, cfg)
            executor_driver_name = executor_driver_opt
        else:
            executor_driver = create_executor_driver(cfg)
            executor_driver_name = cfg.executor_driver_type
        logger.debug("Created executor driver: type=%s", executor_driver_name)
        print(f"✓ Executor Driver: {executor_driver_name}")
    except Exception as e:
        logger.error("Failed to create executor driver: %s", e)
        print(f"❌ 创建 Executor Driver 失败: {e}")
        raise typer.Exit(1)

    # 创建 Evaluator Driver（可与 executor 不同）
    # 优先级：命令行参数 > 配置文件 driver.evaluator.type > 复用 executor driver
    evaluator_driver = None
    try:
        if evaluator_driver_opt:
            evaluator_driver = create_driver_from_type(evaluator_driver_opt, cfg)
            evaluator_driver_name = evaluator_driver_opt
            print(f"✓ Evaluator Driver: {evaluator_driver_name}")
        elif cfg.evaluator_driver_type != cfg.executor_driver_type:
            evaluator_driver = create_evaluator_driver(cfg)
            evaluator_driver_name = cfg.evaluator_driver_type
            print(f"✓ Evaluator Driver: {evaluator_driver_name}")
        # else: evaluator_driver 保持 None，loop 中会复用 executor_driver
    except Exception as e:
        logger.error("Failed to create evaluator driver: %s", e)
        print(f"❌ 创建 Evaluator Driver 失败: {e}")
        raise typer.Exit(1)

    # 验证 from_phase 参数
    if from_phase and from_phase not in ["evaluator", "checker"]:
        print(f"❌ 无效的 --from-phase 值: {from_phase}")
        print("   可用值: evaluator, checker")
        raise typer.Exit(1)

    try:
        result = run_loop(
            project_root=project_root,
            intent=intent,
            eval_skill=eval_skill,
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            max_iterations=max_iterations,
            enable_git_commit=not no_git_commit,
            fresh=fresh,
            interactive=not non_interactive,
            use_live_ui=not no_live_ui,
            start_phase=from_phase,
        )

        # Live UI 模式下摘要已在 loop 中打印，这里不重复
        if no_live_ui:
            print(f"\n✅ 迭代完成！")
            print(f"   成功: {result.success}")
            print(f"   轮数: {result.rounds}")
            print(f"   Runs: {', '.join(result.run_ids)}")

    except Exception as e:
        logger.error("Run failed: %s\n%s", e, traceback.format_exc())
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

    logger.info("Cleaning up...")
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
        full_cleanup(project_root, keep_logs=keep_logs, keep_solution=keep_solution)

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
    from reloop.core.logging import setup_rotating_logger

    # 初始化日志系统（带轮转压缩，DEBUG 级别）
    project_root = Path.cwd()
    log_path = project_root / "logs" / "reloop.log"
    if log_path.parent.exists():
        setup_rotating_logger("reloop", log_path, level=logging.DEBUG)

    app()


if __name__ == "__main__":
    main()
