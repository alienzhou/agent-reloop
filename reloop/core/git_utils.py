"""Git 工具函数 — 仓库检测与初始化。"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def is_git_repo(path: Path) -> bool:
    """检测路径是否为 Git 仓库。

    Args:
        path: 要检测的路径

    Returns:
        是否为 Git 仓库
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=str(path),
        capture_output=True,
    )
    return result.returncode == 0


def init_git_repo(path: Path, user_email: str = "reloop@example.com", user_name: str = "Reloop Agent") -> None:
    """初始化 Git 仓库。

    Args:
        path: 仓库路径
        user_email: Git 用户邮箱
        user_name: Git 用户名
    """
    # git init
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    logger.info(f"Initialized git repo at {path}")

    # 配置用户信息
    subprocess.run(
        ["git", "config", "user.email", user_email],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", user_name],
        cwd=str(path),
        capture_output=True,
        check=True,
    )

    # 创建初始 commit
    gitkeep = path / ".gitkeep"
    gitkeep.write_text("")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    logger.info("Created initial commit")


def ensure_git_repo(path: Path, interactive: bool = True) -> bool:
    """确保路径是 Git 仓库。

    如果不是 Git 仓库，询问用户是否初始化（交互模式）或直接初始化（非交互模式）。

    Args:
        path: 目标路径
        interactive: 是否交互模式

    Returns:
        是否成功确保（或已存在）
    """
    if is_git_repo(path):
        return True

    if interactive:
        print("当前目录不是 Git 仓库。")
        try:
            choice = input("是否初始化 Git 仓库？[Y/n]: ").strip().lower()
        except EOFError:
            choice = "y"

        if choice not in ("", "y", "yes"):
            logger.info("User declined git initialization")
            return False

    init_git_repo(path)
    return True


def get_current_commit_hash(path: Path) -> Optional[str]:
    """获取当前 commit hash。

    Args:
        path: 仓库路径

    Returns:
        commit hash 或 None
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_commit_message(path: Path, commit_hash: str) -> Optional[str]:
    """获取指定 commit 的消息。

    Args:
        path: 仓库路径
        commit_hash: commit hash

    Returns:
        commit message 或 None
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s", commit_hash],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
