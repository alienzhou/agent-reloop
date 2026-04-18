"""中断恢复机制 — 状态检测与回滚逻辑。"""

from __future__ import annotations

import logging
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Run 状态枚举。"""

    FRESH = "fresh"  # 全新项目
    COMPLETED = "completed"  # 已通过
    FAILED = "failed"  # 未通过
    INTERRUPTED = "interrupted"  # 中断


def detect_run_status(project_root: Path) -> RunStatus:
    """检测项目状态。

    Args:
        project_root: 项目根目录

    Returns:
        状态枚举值
    """
    run_sets_dir = project_root / "run-sets"

    # 检查是否有 run-sets 目录
    if not run_sets_dir.exists():
        return RunStatus.FRESH

    # 获取所有 run 目录
    runs = sorted(
        [d for d in run_sets_dir.iterdir() if d.is_dir() and d.name.startswith("run-")],
        key=lambda x: x.name,
    )

    if not runs:
        return RunStatus.FRESH

    # 检查最近的 run
    last_run = runs[-1]
    return detect_single_run_status(project_root, last_run)


def detect_single_run_status(project_root: Path, run_dir: Path) -> RunStatus:
    """检测单个 run 的状态。

    Args:
        project_root: 项目根目录
        run_dir: run 目录路径

    Returns:
        状态枚举值
    """
    run_id = run_dir.name

    # 检查是否有评估报告
    report_path = run_dir / "eval-report" / "report.md"
    if not report_path.exists():
        logger.info(f"No eval report found for {run_id}, marking as interrupted")
        return RunStatus.INTERRUPTED

    # 检查 Git commit 是否存在且匹配
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(f"Failed to get git log for {project_root}")
        return RunStatus.INTERRUPTED

    last_commit = result.stdout.strip()
    if run_id not in last_commit:
        logger.info(f"Last commit does not match {run_id}, marking as interrupted")
        return RunStatus.INTERRUPTED

    # 检查评估报告内容
    report_content = report_path.read_text(encoding="utf-8")
    content_upper = report_content.upper()

    # 检查是否有 PASSED 标记
    if "PASSED" in content_upper:
        # 需要确认是整体 PASSED 还是在上下文中
        # 简单判断：如果同时有 FAILED，则未通过
        if "FAILED" in content_upper:
            return RunStatus.FAILED
        return RunStatus.COMPLETED

    if "FAILED" in content_upper:
        return RunStatus.FAILED

    # 无法判断，保守标记为中断
    logger.warning(f"Cannot determine status from report for {run_id}")
    return RunStatus.INTERRUPTED


def get_last_run_id(project_root: Path) -> Optional[str]:
    """获取最近的 run ID。

    Args:
        project_root: 项目根目录

    Returns:
        run ID 或 None
    """
    run_sets_dir = project_root / "run-sets"
    if not run_sets_dir.exists():
        return None

    runs = sorted(
        [d for d in run_sets_dir.iterdir() if d.is_dir() and d.name.startswith("run-")],
        key=lambda x: x.name,
    )

    if not runs:
        return None

    return runs[-1].name


def get_run_before(project_root: Path, run_id: str) -> Optional[str]:
    """获取指定 run 之前的 run ID。

    Args:
        project_root: 项目根目录
        run_id: 当前 run ID

    Returns:
        前一个 run ID 或 None
    """
    run_sets_dir = project_root / "run-sets"
    if not run_sets_dir.exists():
        return None

    runs = sorted(
        [d for d in run_sets_dir.iterdir() if d.is_dir() and d.name.startswith("run-")],
        key=lambda x: x.name,
    )

    for i, run in enumerate(runs):
        if run.name == run_id and i > 0:
            return runs[i - 1].name

    return None


def rollback_incomplete_run(project_root: Path, run_id: str) -> None:
    """回滚不完整的 run。

    Args:
        project_root: 项目根目录
        run_id: run ID
    """
    run_dir = project_root / "run-sets" / run_id

    # 获取该 run 之前的 commit
    result = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"Failed to get git log for rollback")
        raise RuntimeError("Git log failed during rollback")

    commits = result.stdout.strip().splitlines()

    # 找到该 run 的 commit 索引
    run_commit_idx = None
    for i, commit in enumerate(commits):
        if run_id in commit:
            run_commit_idx = i
            break

    # 回滚到前一个 commit
    if run_commit_idx is not None and run_commit_idx > 0:
        prev_commit = commits[run_commit_idx - 1].split()[0]
        subprocess.run(
            ["git", "reset", "--hard", prev_commit],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        logger.info(f"Git reset to {prev_commit}")
    elif run_commit_idx == 0:
        # 这是第一个 run commit，无法回滚到之前的状态
        # 检查是否有更早的 commit（如初始 commit）
        result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            root_commit = result.stdout.strip() if result.stdout.strip() else None
            run_commit_hash = commits[0].split()[0] if commits else None
            
            # 只有当 root commit 不同于 run commit 时才回滚
            # root_commit 是完整的 40 字符 hash，run_commit_hash 是缩写的 ~7 字符 hash
            if root_commit and run_commit_hash and not root_commit.startswith(run_commit_hash):
                subprocess.run(
                    ["git", "reset", "--hard", root_commit],
                    cwd=str(project_root),
                    capture_output=True,
                    check=True,
                )
                logger.info(f"Git reset to root commit {root_commit}")
            else:
                # 无法回滚，该 run commit 就是根节点
                logger.warning(
                    f"Cannot rollback git history for {run_id}: "
                    "it is the first commit. Use 'full_cleanup' to completely reset."
                )

    # 删除 run 目录
    if run_dir.exists():
        shutil.rmtree(run_dir)
        logger.info(f"Removed run directory: {run_dir}")

    logger.info(f"Rolled back incomplete run: {run_id}")


def full_cleanup(project_root: Path, keep_logs: bool = False, keep_solution: bool = False) -> None:
    """完全清理，回到初始状态。

    Args:
        project_root: 项目根目录
        keep_logs: 是否保留日志
        keep_solution: 是否保留 solution 目录内容
    """
    # 获取初始 commit
    result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        root_commit = result.stdout.strip().split()[0]
        subprocess.run(
            ["git", "reset", "--hard", root_commit],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        logger.info(f"Git reset to initial commit {root_commit}")

    # 删除所有 runs
    run_sets_dir = project_root / "run-sets"
    if run_sets_dir.exists():
        for run_dir in run_sets_dir.iterdir():
            if run_dir.is_dir() and run_dir.name.startswith("run-"):
                shutil.rmtree(run_dir)
                logger.info(f"Removed {run_dir.name}")
        # 保持目录存在
        (run_sets_dir / ".gitkeep").write_text("")

    # 清理 solution（可选，暂时保留目录结构）
    if not keep_solution:
        solution_dir = project_root / "task" / "solution"
        if solution_dir.exists():
            for item in solution_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.info("Cleared task/solution/")

    # 清理日志
    if not keep_logs:
        log_file = project_root / "logs" / "reloop.log"
        if log_file.exists():
            log_file.unlink()
            logger.info("Removed system log")

    logger.info("Full cleanup completed")
