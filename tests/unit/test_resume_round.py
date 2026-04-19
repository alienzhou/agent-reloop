"""测试 resume 场景下的 round_num 计算逻辑"""

import subprocess
from pathlib import Path

import pytest

from reloop.core.loop import (
    MaxIterationsExceededError,
    run_loop,
)
from reloop.core.resume import ResumeChoice
from reloop.drivers.mock import CallbackMockDriver, MockDriver


def _init_git_repo(path: Path):
    """初始化 git repo 供 loop 使用"""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@reloop.dev"],
        cwd=str(path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Reloop Test"],
        cwd=str(path), capture_output=True, check=True,
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(path), capture_output=True, check=True,
    )


def _make_evaluator_callback(report_content: str):
    """创建 evaluator 回调函数，将报告写入指定路径。"""
    import re
    def callback(prompt: str, workdir: str) -> None:
        match = re.search(
            r"\*\*You MUST write the final evaluation report to:\*\*\s*`([^`]+)`",
            prompt
        )
        if match:
            path = Path(match.group(1))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report_content)
    return callback


def _make_checker_callback(result: str):
    """创建 checker 回调函数，将结果写入指定路径。"""
    import re
    def callback(prompt: str, workdir: str) -> None:
        match = re.search(r"\*\*You MUST write your result to:\*\*\s*`([^`]+)`", prompt)
        if match:
            path = Path(match.group(1))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"<checker_result>{result}</checker_result>")
    return callback


def _git_commit(path: Path, message: str):
    """创建一个 git commit"""
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=str(path), capture_output=True, check=True,
    )


def _setup_completed_runs(tmp_path: Path, num_runs: int) -> None:
    """设置已完成的 run 目录结构（模拟已完成的轮次）"""
    for i in range(1, num_runs + 1):
        run_dir = tmp_path / "run-sets" / f"run-{i:03d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建必要的子目录和文件
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        eval_dir = run_dir / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text(f"Round {i} evaluation report\nFAILED")
        
        checker_dir = run_dir / "checker-result"
        checker_dir.mkdir(parents=True, exist_ok=True)
        (checker_dir / "result.md").write_text("<checker_result>failed</checker_result>")
        
        # git commit
        _git_commit(tmp_path, f"reloop: completed run-{i:03d}")


class TestResumeRoundNumber:
    """测试 resume 场景下 round_num 的正确性"""

    def test_fresh_start_begins_at_round_1(self, tmp_path):
        """全新开始时，round_num 从 1 开始"""
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval passed"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
            fresh=True,
        )

        assert result.success is True
        assert result.rounds == 1
        assert result.run_ids == ["run-001"]

    def test_resume_from_run_003_starts_at_round_3(self, tmp_path):
        """从 run-003 恢复时，round_num 应该从 3 开始"""
        _init_git_repo(tmp_path)
        # 设置已完成的 2 轮
        _setup_completed_runs(tmp_path, 2)
        
        # 创建 run-003 目录（模拟中断的第三轮）
        run_003 = tmp_path / "run-sets" / "run-003"
        run_003.mkdir(parents=True, exist_ok=True)
        (run_003 / "logs").mkdir()
        
        # 创建 solution 目录（模拟 executor 已完成）
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution code")
        
        # 创建 eval-report（模拟 evaluator 已完成）
        eval_dir = run_003 / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text("Round 3 FAILED")
        
        _git_commit(tmp_path, "reloop: evaluator completed run-003")

        # 只需要 checker 的响应
        checker_driver = CallbackMockDriver(
            responses=["checking r3"],
            callbacks=[_make_checker_callback("passed")],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=MockDriver(responses=[]),  # 不应被调用
            evaluator_driver=MockDriver(responses=[]),  # 不应被调用
            checker_driver=checker_driver,
            start_phase="checker",  # 从 checker 阶段开始
        )

        assert result.success is True
        assert result.rounds == 3  # 关键断言：round_num 应该是 3
        assert "run-003" in result.run_ids

    def test_resume_and_continue_increments_correctly(self, tmp_path):
        """恢复后继续迭代，round_num 应该正确递增"""
        _init_git_repo(tmp_path)
        # 设置已完成的 2 轮
        _setup_completed_runs(tmp_path, 2)
        
        # 创建 run-003 目录（模拟中断的第三轮，evaluator 已完成）
        run_003 = tmp_path / "run-sets" / "run-003"
        run_003.mkdir(parents=True, exist_ok=True)
        (run_003 / "logs").mkdir()
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution v3")
        
        eval_dir = run_003 / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text("Round 3 FAILED")
        
        _git_commit(tmp_path, "reloop: evaluator completed run-003")

        # 第三轮 checker 失败，第四轮通过
        # 注意：恢复后从 round 3 开始，checker 失败后会创建 round 4
        executor_driver = MockDriver(responses=["exec v4"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval v4"],
            callbacks=[_make_evaluator_callback("eval v4")],
        )
        checker_driver = CallbackMockDriver(
            responses=["r3 fail", "r4 pass"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("passed"),
            ],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
            start_phase="checker",  # 从 checker 阶段开始
            max_iterations=10,
        )

        assert result.success is True
        assert result.rounds == 4  # 第四轮通过
        # run_ids 应该包含 run-003 和 run-004
        assert "run-003" in result.run_ids
        assert "run-004" in result.run_ids


class TestStartRoundNumEdgeCases:
    """测试 start_round_num 的边界情况"""

    def test_start_round_exceeds_max_iterations(self, tmp_path):
        """当 start_round_num > max_iterations 时，循环应该立即结束"""
        _init_git_repo(tmp_path)
        # 设置已完成的 5 轮
        _setup_completed_runs(tmp_path, 5)
        
        # 创建 run-006 目录
        run_006 = tmp_path / "run-sets" / "run-006"
        run_006.mkdir(parents=True, exist_ok=True)
        (run_006 / "logs").mkdir()
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution v6")
        
        eval_dir = run_006 / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text("Round 6 FAILED")
        
        _git_commit(tmp_path, "reloop: evaluator completed run-006")

        # max_iterations=5，但我们从 run-006 恢复（round 6）
        checker_driver = CallbackMockDriver(
            responses=["r6"],
            callbacks=[_make_checker_callback("failed")],
        )

        # 因为 start_round_num=6 > max_iterations=5
        # 应该立即抛出 MaxIterationsExceededError
        with pytest.raises(MaxIterationsExceededError, match="Resume round 6 exceeds max_iterations 5"):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=MockDriver(responses=[]),
                evaluator_driver=MockDriver(responses=[]),
                checker_driver=checker_driver,
                start_phase="checker",
                max_iterations=5,  # 小于 run-006 的轮数
            )

    def test_invalid_run_id_format_defaults_to_1(self, tmp_path):
        """当 resume_run_id 格式无效时，应该从 1 开始"""
        # 这个测试需要在单元测试级别测试 start_round_num 的解析逻辑
        # 目前在 loop.py 中已经有 try/except ValueError 处理
        pass  # TODO: 需要更细粒度的单元测试


class TestResumeRoundNumWithUI:
    """测试使用 Live UI 时 resume round_num 的正确性"""

    def test_live_ui_shows_correct_round_on_resume(self, tmp_path):
        """Live UI 应该显示正确的 round_num"""
        _init_git_repo(tmp_path)
        _setup_completed_runs(tmp_path, 2)
        
        run_003 = tmp_path / "run-sets" / "run-003"
        run_003.mkdir(parents=True, exist_ok=True)
        (run_003 / "logs").mkdir()
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution")
        
        eval_dir = run_003 / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text("FAILED")
        
        _git_commit(tmp_path, "reloop: evaluator completed run-003")

        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=MockDriver(responses=[]),
            evaluator_driver=MockDriver(responses=[]),
            checker_driver=checker_driver,
            start_phase="checker",
            use_live_ui=True,  # 使用 Live UI
        )

        assert result.rounds == 3


class TestResumeRoundNumWithClassicMode:
    """测试不使用 Live UI（经典模式）时 resume round_num 的正确性"""

    def test_classic_mode_shows_correct_round_on_resume(self, tmp_path):
        """经典模式应该显示正确的 round_num"""
        _init_git_repo(tmp_path)
        _setup_completed_runs(tmp_path, 2)
        
        run_003 = tmp_path / "run-sets" / "run-003"
        run_003.mkdir(parents=True, exist_ok=True)
        (run_003 / "logs").mkdir()
        
        solution_dir = tmp_path / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        (solution_dir / "main.py").write_text("# solution")
        
        eval_dir = run_003 / "eval-report"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "report.md").write_text("FAILED")
        
        _git_commit(tmp_path, "reloop: evaluator completed run-003")

        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=MockDriver(responses=[]),
            evaluator_driver=MockDriver(responses=[]),
            checker_driver=checker_driver,
            start_phase="checker",
            use_live_ui=False,  # 经典模式
        )

        assert result.rounds == 3
