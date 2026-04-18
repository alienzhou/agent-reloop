"""Git 自动提交机制 — executor 执行后自动 commit"""

from __future__ import annotations

import subprocess
from pathlib import Path


def auto_commit_after_execution(project_root: Path, run_id: str) -> bool:
    """在 executor 完成后自动 git commit。

    将所有变更（包括 run-sets/ 和 task/solution/）add 并 commit。
    如果没有变更，则跳过 commit。

    Args:
        project_root: 项目根目录
        run_id:       当前轮次 ID（如 "run-001"）

    Returns:
        True 如果创建了 commit，False 如果没有变更
    """
    cwd = str(project_root)

    subprocess.run(
        ["git", "add", "-A"],
        cwd=cwd, capture_output=True, check=True,
    )

    # 检查是否有 staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=cwd, capture_output=True,
    )
    if result.returncode == 0:
        return False

    message = f"reloop: executor completed {run_id}"
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=cwd, capture_output=True, check=True,
    )
    return True
