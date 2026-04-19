"""Workspace 初始化和 run_id 序号管理"""

from __future__ import annotations

import re
from pathlib import Path

_RUN_DIR_PATTERN = re.compile(r"^run-(\d{3,})$")


def next_run_id(run_sets_dir: Path) -> str:
    """计算下一个 run_id。

    扫描 run_sets_dir 下所有 run-xxx 目录，取最大序号 + 1。
    若目录不存在或无 run-xxx 子目录，返回 run-001。
    """
    max_num = 0
    if run_sets_dir.exists():
        for child in run_sets_dir.iterdir():
            if child.is_dir():
                m = _RUN_DIR_PATTERN.match(child.name)
                if m:
                    max_num = max(max_num, int(m.group(1)))
    return f"run-{max_num + 1:03d}"


def init_workspace(project_root: Path) -> Path:
    """初始化一次迭代的工作空间。

    创建 run-sets/run-{id}/ 及其子目录（logs, eval-report），
    同时确保 task/solution/ 存在。

    Returns:
        新创建的 run 目录路径
    """
    run_sets_dir = project_root / "run-sets"
    run_sets_dir.mkdir(parents=True, exist_ok=True)

    run_id = next_run_id(run_sets_dir)
    run_dir = run_sets_dir / run_id
    run_dir.mkdir()

    for sub in ("logs", "eval-report"):
        sub_dir = run_dir / sub
        sub_dir.mkdir()
        (sub_dir / ".gitkeep").write_text("")

    solution_dir = project_root / "task" / "solution"
    solution_dir.mkdir(parents=True, exist_ok=True)

    return run_dir
