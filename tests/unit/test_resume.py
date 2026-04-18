"""测试中断恢复机制。"""

import subprocess
from pathlib import Path

import pytest

from reloop.core.resume import (
    ResumeChoice,
    RunStatus,
    detect_run_status,
    detect_single_run_status,
    full_cleanup,
    get_last_run_id,
    get_run_before,
    prompt_resume_choice,
    rollback_incomplete_run,
)


class TestDetectRunStatus:
    """测试状态检测。"""

    def test_fresh_no_run_sets_dir(self, tmp_path):
        """没有 run-sets 目录时返回 FRESH。"""
        status = detect_run_status(tmp_path)
        assert status == RunStatus.FRESH

    def test_fresh_empty_run_sets(self, tmp_path):
        """run-sets 为空时返回 FRESH。"""
        (tmp_path / "run-sets").mkdir()
        status = detect_run_status(tmp_path)
        assert status == RunStatus.FRESH

    def test_interrupted_no_eval_report(self, tmp_path):
        """没有 eval report 时返回 INTERRUPTED。"""
        # 初始化 Git
        _init_git_repo(tmp_path)
        
        # 创建 run 目录但无 eval report
        run_dir = tmp_path / "run-sets" / "run-001"
        run_dir.mkdir(parents=True)
        (run_dir / "logs").mkdir()
        (run_dir / "artifacts").mkdir()
        
        status = detect_run_status(tmp_path)
        assert status == RunStatus.INTERRUPTED

    def test_interrupted_commit_mismatch(self, tmp_path):
        """Git commit 不匹配时返回 INTERRUPTED。"""
        # 初始化 Git
        _init_git_repo(tmp_path)
        
        # 创建完整的 run
        run_dir = tmp_path / "run-sets" / "run-001"
        _create_complete_run(run_dir, passed=True)
        
        # commit 不是该 run（保持初始状态）
        status = detect_run_status(tmp_path)
        assert status == RunStatus.INTERRUPTED

    def test_completed_with_passed_report(self, tmp_path):
        """评估报告显示 PASSED 时返回 COMPLETED。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        _create_complete_run(run_dir, passed=True)
        
        # 创建对应的 commit
        _commit_for_run(tmp_path, "run-001")
        
        status = detect_run_status(tmp_path)
        assert status == RunStatus.COMPLETED

    def test_failed_with_failed_report(self, tmp_path):
        """评估报告显示 FAILED 时返回 FAILED。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        _create_complete_run(run_dir, passed=False)
        
        _commit_for_run(tmp_path, "run-001")
        
        status = detect_run_status(tmp_path)
        assert status == RunStatus.FAILED


class TestDetectSingleRunStatus:
    """测试单个 run 状态检测。"""

    def test_interrupted_no_report(self, tmp_path):
        """没有 report 文件时返回 INTERRUPTED。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        run_dir.mkdir(parents=True)
        
        status = detect_single_run_status(tmp_path, run_dir)
        assert status == RunStatus.INTERRUPTED

    def test_completed_passed(self, tmp_path):
        """report 显示 PASSED 时返回 COMPLETED。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        _create_complete_run(run_dir, passed=True)
        _commit_for_run(tmp_path, "run-001")
        
        status = detect_single_run_status(tmp_path, run_dir)
        assert status == RunStatus.COMPLETED

    def test_failed(self, tmp_path):
        """report 显示 FAILED 时返回 FAILED。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        _create_complete_run(run_dir, passed=False)
        _commit_for_run(tmp_path, "run-001")
        
        status = detect_single_run_status(tmp_path, run_dir)
        assert status == RunStatus.FAILED


class TestGetLastRunId:
    """测试获取最近 run ID。"""

    def test_no_runs(self, tmp_path):
        """没有 runs 时返回 None。"""
        result = get_last_run_id(tmp_path)
        assert result is None

    def test_single_run(self, tmp_path):
        """单个 run 时返回其 ID。"""
        (tmp_path / "run-sets" / "run-001").mkdir(parents=True)
        result = get_last_run_id(tmp_path)
        assert result == "run-001"

    def test_multiple_runs(self, tmp_path):
        """多个 runs 时返回最近的。"""
        (tmp_path / "run-sets" / "run-001").mkdir(parents=True)
        (tmp_path / "run-sets" / "run-002").mkdir(parents=True)
        (tmp_path / "run-sets" / "run-003").mkdir(parents=True)
        result = get_last_run_id(tmp_path)
        assert result == "run-003"


class TestGetRunBefore:
    """测试获取前一个 run ID。"""

    def test_no_previous(self, tmp_path):
        """第一个 run 返回 None。"""
        (tmp_path / "run-sets" / "run-001").mkdir(parents=True)
        result = get_run_before(tmp_path, "run-001")
        assert result is None

    def test_has_previous(self, tmp_path):
        """有前一个 run 时返回其 ID。"""
        (tmp_path / "run-sets" / "run-001").mkdir(parents=True)
        (tmp_path / "run-sets" / "run-002").mkdir(parents=True)
        result = get_run_before(tmp_path, "run-002")
        assert result == "run-001"


class TestRollbackIncompleteRun:
    """测试回滚不完整的 run。"""

    def test_rollback_removes_run_directory(self, tmp_path):
        """回滚会删除 run 目录。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        run_dir.mkdir(parents=True)
        (run_dir / "test.txt").write_text("test")
        
        rollback_incomplete_run(tmp_path, "run-001")
        
        assert not run_dir.exists()

    def test_rollback_first_run_with_prior_commit(self, tmp_path):
        """第一个 run 但有前置 commit 时的回滚。"""
        _init_git_repo(tmp_path)
        
        # 创建初始 commit 后的 run
        run_dir = tmp_path / "run-sets" / "run-001"
        run_dir.mkdir(parents=True)
        _create_complete_run(run_dir, passed=False)
        _commit_for_run(tmp_path, "run-001")
        
        rollback_incomplete_run(tmp_path, "run-001")
        
        # 应该回滚到初始 commit
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path, capture_output=True, text=True
        )
        assert "run-001" not in result.stdout

    def test_rollback_first_run_no_prior_commit(self, tmp_path):
        """第一个 run 且是第一个 commit 时的处理。"""
        _init_git_repo(tmp_path)
        
        run_dir = tmp_path / "run-sets" / "run-001"
        run_dir.mkdir(parents=True)
        
        # 这个 run 的 commit 就是第一个 commit
        rollback_incomplete_run(tmp_path, "run-001")
        
        # run 目录应该被删除，即使 git 无法回滚
        assert not run_dir.exists()


class TestFullCleanup:
    """测试完全清理。"""

    def test_cleanup_removes_all_runs(self, tmp_path):
        """清理会删除所有 runs。"""
        _init_git_repo(tmp_path)
        
        # 创建多个 runs
        for i in range(1, 4):
            run_dir = tmp_path / "run-sets" / f"run-{i:03d}"
            run_dir.mkdir(parents=True)
        
        full_cleanup(tmp_path, keep_logs=True, keep_solution=True)
        
        run_sets_dir = tmp_path / "run-sets"
        runs = [d for d in run_sets_dir.iterdir() if d.is_dir() and d.name.startswith("run-")]
        assert len(runs) == 0

    def test_cleanup_keeps_logs_when_requested(self, tmp_path):
        """keep_logs=True 时保留日志。"""
        _init_git_repo(tmp_path)
        
        log_file = tmp_path / "logs" / "reloop.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("test log")
        
        full_cleanup(tmp_path, keep_logs=True, keep_solution=True)
        
        assert log_file.exists()

    def test_cleanup_removes_logs_by_default(self, tmp_path):
        """默认删除日志。"""
        _init_git_repo(tmp_path)
        
        log_file = tmp_path / "logs" / "reloop.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("test log")
        
        full_cleanup(tmp_path, keep_logs=False, keep_solution=True)
        
        assert not log_file.exists()

    def test_cleanup_clears_solution(self, tmp_path):
        """清理 solution 目录内容。"""
        _init_git_repo(tmp_path)
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution")
        
        full_cleanup(tmp_path, keep_logs=True, keep_solution=False)
        
        assert solution_dir.exists()  # 目录保留
        assert not (solution_dir / "main.py").exists()  # 内容删除

    def test_cleanup_keeps_solution_when_requested(self, tmp_path):
        """keep_solution=True 时保留 solution。"""
        _init_git_repo(tmp_path)
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution")
        
        full_cleanup(tmp_path, keep_logs=True, keep_solution=True)
        
        assert (solution_dir / "main.py").exists()


class TestPromptResumeChoice:
    """测试用户交互选择。"""

    def test_non_interactive_returns_continue(self):
        """非交互模式返回默认值 CONTINUE。"""
        result = prompt_resume_choice(
            RunStatus.INTERRUPTED,
            last_run_id="run-001",
            interactive=False,
        )
        assert result == ResumeChoice.CONTINUE

    def test_non_interactive_completed_returns_continue(self):
        """非交互模式下已完成状态也返回 CONTINUE。"""
        result = prompt_resume_choice(
            RunStatus.COMPLETED,
            last_run_id="run-002",
            interactive=False,
        )
        assert result == ResumeChoice.CONTINUE

    def test_non_interactive_failed_returns_continue(self):
        """非交互模式下失败状态也返回 CONTINUE。"""
        result = prompt_resume_choice(
            RunStatus.FAILED,
            last_run_id="run-003",
            interactive=False,
        )
        assert result == ResumeChoice.CONTINUE

    def test_interactive_default_choice(self, monkeypatch):
        """交互模式，直接回车使用默认值。"""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_resume_choice(
            RunStatus.FAILED,
            last_run_id="run-002",
            interactive=True,
        )
        assert result == ResumeChoice.CONTINUE

    def test_interactive_choice_1(self, monkeypatch):
        """交互模式，选择 1 返回 CONTINUE。"""
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = prompt_resume_choice(
            RunStatus.INTERRUPTED,
            last_run_id="run-001",
            interactive=True,
        )
        assert result == ResumeChoice.CONTINUE

    def test_interactive_choice_2(self, monkeypatch):
        """交互模式，选择 2 返回 RESET。"""
        monkeypatch.setattr("builtins.input", lambda _: "2")
        result = prompt_resume_choice(
            RunStatus.FAILED,
            last_run_id="run-002",
            interactive=True,
        )
        assert result == ResumeChoice.RESET

    def test_interactive_invalid_then_valid(self, monkeypatch):
        """交互模式，无效输入后输入有效值。"""
        inputs = iter(["invalid", "3", "2"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        result = prompt_resume_choice(
            RunStatus.INTERRUPTED,
            last_run_id="run-001",
            interactive=True,
        )
        assert result == ResumeChoice.RESET

    def test_interactive_no_last_run_id(self, monkeypatch):
        """交互模式，没有 last_run_id 时也能正常工作。"""
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = prompt_resume_choice(
            RunStatus.INTERRUPTED,
            last_run_id=None,
            interactive=True,
        )
        assert result == ResumeChoice.CONTINUE

    def test_interactive_keyboard_interrupt(self, monkeypatch, capsys):
        """交互模式下 Ctrl+C 应该抛出 SystemExit(0)。"""
        def raise_keyboard_interrupt(_):
            raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", raise_keyboard_interrupt)

        with pytest.raises(SystemExit) as exc_info:
            prompt_resume_choice(
                RunStatus.INTERRUPTED,
                last_run_id="run-001",
                interactive=True,
            )

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "已取消" in captured.out


# === 辅助函数 ===

def _init_git_repo(path: Path) -> None:
    """初始化 Git 仓库。"""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@reloop.dev"],
        cwd=path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path, capture_output=True, check=True
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path, capture_output=True, check=True
    )


def _create_complete_run(run_dir: Path, passed: bool = True) -> None:
    """创建完整的 run 目录结构。"""
    run_dir.mkdir(parents=True, exist_ok=True)
    
    for subdir in ["logs", "artifacts", "eval-report"]:
        (run_dir / subdir).mkdir(exist_ok=True)
    
    report_content = "## Evaluation Report\n\n**Result: PASSED**" if passed else "## Evaluation Report\n\n**Result: FAILED**"
    (run_dir / "eval-report" / "report.md").write_text(report_content)


def _commit_for_run(path: Path, run_id: str) -> None:
        """为指定 run 创建 commit。"""
        subprocess.run(
            ["git", "add", "-A"],
            cwd=path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"reloop: executor completed {run_id}"],
            cwd=path, capture_output=True, check=True
        )
