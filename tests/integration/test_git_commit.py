"""Git commit 机制的集成测试"""

import subprocess
from pathlib import Path

import pytest

from reloop.core.git import auto_commit_after_execution


def _init_git_repo(path: Path):
    """在指定目录初始化一个 git repo"""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@reloop.dev"],
        cwd=str(path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Reloop Test"],
        cwd=str(path), capture_output=True, check=True,
    )
    # 初始提交，使 HEAD 存在
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(path), capture_output=True, check=True,
    )


def _git_log(path: Path, n: int = 5) -> list:
    """获取最近 n 条 commit message"""
    result = subprocess.run(
        ["git", "log", f"-{n}", "--format=%s"],
        cwd=str(path), capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def _git_log_full(path: Path, n: int = 1) -> str:
    """获取完整的 commit 信息"""
    result = subprocess.run(
        ["git", "log", f"-{n}", "--format=%B"],
        cwd=str(path), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class TestAutoCommitAfterExecution:
    """验证 executor 执行后的自动 commit"""

    def test_creates_commit(self, tmp_path):
        _init_git_repo(tmp_path)
        # 模拟 executor 产出文件
        artifacts = tmp_path / "run-sets" / "run-001" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "output.txt").write_text("result")

        auto_commit_after_execution(tmp_path, "run-001")

        messages = _git_log(tmp_path)
        assert len(messages) >= 2  # initial + 新 commit

    def test_commit_message_contains_run_id(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "run-sets" / "run-001" / "artifacts").mkdir(parents=True)
        (tmp_path / "run-sets" / "run-001" / "artifacts" / "out.txt").write_text("x")

        auto_commit_after_execution(tmp_path, "run-001")

        messages = _git_log(tmp_path)
        assert any("run-001" in msg for msg in messages)

    def test_no_changes_no_commit(self, tmp_path):
        """没有文件变更时不应创建空 commit"""
        _init_git_repo(tmp_path)
        initial_count = len(_git_log(tmp_path))

        auto_commit_after_execution(tmp_path, "run-001")

        assert len(_git_log(tmp_path)) == initial_count

    def test_commits_solution_changes(self, tmp_path):
        """solution 目录的变更也应被 commit"""
        _init_git_repo(tmp_path)
        solution = tmp_path / "task" / "solution"
        solution.mkdir(parents=True)
        (solution / "main.py").write_text("print('hello')")

        auto_commit_after_execution(tmp_path, "run-001")

        messages = _git_log(tmp_path)
        assert len(messages) >= 2
