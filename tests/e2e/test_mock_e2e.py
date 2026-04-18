"""MockDriver 端到端测试 — 验证完整迭代循环"""

import subprocess
from pathlib import Path

import pytest

from reloop.core.loop import LoopResult, MaxIterationsExceededError, run_loop
from reloop.drivers.mock import MockDriver


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


def _git_log_messages(path: Path, n: int = 10) -> list:
    result = subprocess.run(
        ["git", "log", f"-{n}", "--format=%s"],
        cwd=str(path), capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


class TestSingleRoundPass:
    """3.1 Happy path: 单轮通过"""

    def test_loop_exits_after_one_round(self, tmp_path):
        _init_git_repo(tmp_path)
        # 每轮 3 次调用：executor, evaluator, checker
        driver = MockDriver(responses=[
            "executor output",                         # executor
            "L0: PASS\nL1: PASS\nL2: PASS\nPASSED",  # evaluator
            "passed",                                  # checker
        ])

        result = run_loop(
            project_root=tmp_path,
            intent="Build hello.txt",
            eval_skill="Check file exists",
            executor_driver=driver,
        )

        assert result.success is True
        assert result.rounds == 1

    def test_only_run_001_exists(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=["exec", "eval", "passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert (tmp_path / "run-sets" / "run-001").is_dir()
        assert not (tmp_path / "run-sets" / "run-002").exists()


class TestMultiRoundConvergence:
    """3.2 多轮收敛"""

    def test_two_rounds_to_pass(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=[
            # Round 1: fail
            "executor v1", "L1: FAIL\ncount mismatch", "failed",
            # Round 2: pass
            "executor v2", "L0: PASS\nL1: PASS\nL2: PASS", "passed",
        ])

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert result.success is True
        assert result.rounds == 2
        assert result.run_ids == ["run-001", "run-002"]

    def test_round2_executor_prompt_contains_round1_eval(self, tmp_path):
        _init_git_repo(tmp_path)
        eval_report_r1 = "L1: FAIL\ncount mismatch: expected 10, got 5"
        driver = MockDriver(responses=[
            "exec v1", eval_report_r1, "failed",
            "exec v2", "all pass", "passed",
        ])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        # 第 4 次调用是 round 2 的 executor（索引 3）
        round2_executor_prompt = driver.call_log[3]["prompt"]
        assert "count mismatch" in round2_executor_prompt

    def test_both_run_dirs_exist(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=[
            "e1", "eval1", "failed",
            "e2", "eval2", "passed",
        ])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert (tmp_path / "run-sets" / "run-001").is_dir()
        assert (tmp_path / "run-sets" / "run-002").is_dir()


class TestFirstRoundNoEval:
    """3.3 首轮无前一轮评估结果"""

    def test_first_round_executor_no_eval_section(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=["exec", "eval", "passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        first_executor_prompt = driver.call_log[0]["prompt"]
        assert "previous evaluation" not in first_executor_prompt.lower()


class TestMaxIterationGuard:
    """3.4 最大迭代次数守护"""

    def test_raises_after_max_iterations(self, tmp_path):
        _init_git_repo(tmp_path)
        # 3 轮 × 3 次调用 = 9 个响应，全部 fail
        driver = MockDriver(responses=[
            "exec", "eval", "failed",
            "exec", "eval", "failed",
            "exec", "eval", "failed",
        ])

        with pytest.raises(MaxIterationsExceededError, match="3 iterations"):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=driver,
                max_iterations=3,
            )

    def test_does_not_run_forever(self, tmp_path):
        """即使 checker 一直返回 failed，也在 max_iterations 后停止"""
        _init_git_repo(tmp_path)
        responses = ["exec", "eval", "failed"] * 5
        driver = MockDriver(responses=responses)

        with pytest.raises(MaxIterationsExceededError):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=driver,
                max_iterations=5,
            )


class TestDirectoryLayoutAfterRun:
    """3.5 运行后的目录结构验证"""

    def test_run_dirs_have_correct_subdirs(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=[
            "e1", "eval1", "failed",
            "e2", "eval2", "passed",
        ])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        for run_id in ["run-001", "run-002"]:
            run_dir = tmp_path / "run-sets" / run_id
            assert (run_dir / "logs").is_dir()
            assert (run_dir / "artifacts").is_dir()
            assert (run_dir / "eval-report").is_dir()

    def test_task_solution_exists(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=["exec", "eval", "passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert (tmp_path / "task" / "solution").is_dir()

    def test_eval_report_saved(self, tmp_path):
        _init_git_repo(tmp_path)
        eval_output = "L0: PASS\nL1: PASS\nOverall: PASSED"
        driver = MockDriver(responses=["exec", eval_output, "passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        report = tmp_path / "run-sets" / "run-001" / "eval-report" / "report.md"
        assert report.exists()
        assert report.read_text() == eval_output

    def test_git_commits_exist(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=[
            "e1", "eval1", "failed",
            "e2", "eval2", "passed",
        ])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        messages = _git_log_messages(tmp_path)
        run_001_commits = [m for m in messages if "run-001" in m]
        run_002_commits = [m for m in messages if "run-002" in m]
        assert len(run_001_commits) >= 1
        assert len(run_002_commits) >= 1


class TestDifferentDrivers:
    """3.6 executor 和 evaluator 使用不同的 Driver"""

    def test_executor_and_evaluator_separate_drivers(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["executor output"])
        evaluator_driver = MockDriver(responses=["eval report"])
        checker_driver = MockDriver(responses=["passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        # executor driver 只收到 executor 调用
        assert len(executor_driver.call_log) == 1
        assert "Task Intent" in executor_driver.call_log[0]["prompt"]

        # evaluator driver 只收到 evaluator 调用
        assert len(evaluator_driver.call_log) == 1
        assert "Evaluation Skill" in evaluator_driver.call_log[0]["prompt"]

        # checker driver 只收到 checker 调用
        assert len(checker_driver.call_log) == 1
        assert "Evaluation Report" in checker_driver.call_log[0]["prompt"]

    def test_evaluator_defaults_to_executor_driver(self, tmp_path):
        """不指定 evaluator_driver 时，复用 executor_driver"""
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=["exec", "eval", "passed"])

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert len(driver.call_log) == 3


class TestLoopResult:
    """LoopResult 返回值验证"""

    def test_result_contains_run_ids(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=[
            "e1", "eval1", "failed",
            "e2", "eval2", "passed",
        ])

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert result.run_ids == ["run-001", "run-002"]

    def test_result_contains_last_eval_report(self, tmp_path):
        _init_git_repo(tmp_path)
        driver = MockDriver(responses=["exec", "final eval", "passed"])

        result = run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=driver,
        )

        assert result.last_eval_report == "final eval"
