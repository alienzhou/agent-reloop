"""MockDriver 端到端测试 — 验证完整迭代循环"""

import re
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from reloop.core.loop import (
    CheckerResultNotFoundError,
    EvaluatorReportNotFoundError,
    LoopResult,
    MaxIterationsExceededError,
    run_loop,
)
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


def _git_log_messages(path: Path, n: int = 10) -> list:
    result = subprocess.run(
        ["git", "log", f"-{n}", "--format=%s"],
        cwd=str(path), capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def _extract_result_path_from_prompt(prompt: str) -> Optional[str]:
    """从 checker prompt 中提取 result_path。"""
    # 格式: **You MUST write your result to:** `{result_path}`
    match = re.search(r"\*\*You MUST write your result to:\*\*\s*`([^`]+)`", prompt)
    if match:
        return match.group(1)
    return None


def _extract_report_path_from_prompt(prompt: str) -> Optional[str]:
    """从 evaluator prompt 中提取 report_output_path。"""
    # 格式: **You MUST write the final evaluation report to:** `{report_output_path}`
    match = re.search(
        r"\*\*You MUST write the final evaluation report to:\*\*\s*`([^`]+)`",
        prompt
    )
    if match:
        return match.group(1)
    return None


def _make_evaluator_callback(report_content: str):
    """创建 evaluator 回调函数，将报告写入指定路径。"""
    def callback(prompt: str, workdir: str) -> None:
        report_path = _extract_report_path_from_prompt(prompt)
        if report_path:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report_content)
    return callback


def _make_checker_callback(result: str):
    """创建 checker 回调函数，将结果写入指定路径。"""
    def callback(prompt: str, workdir: str) -> None:
        result_path = _extract_result_path_from_prompt(prompt)
        if result_path:
            path = Path(result_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"<checker_result>{result}</checker_result>")
    return callback


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
        # executor 使用普通 MockDriver
        executor_driver = MockDriver(responses=["executor output"])
        # evaluator 使用 CallbackMockDriver，写入报告文件
        eval_content = "L0: PASS\nL1: PASS\nL2: PASS\nPASSED"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        # checker 使用 CallbackMockDriver，写入结果文件
        checker_driver = CallbackMockDriver(
            responses=["Checking..."],
            callbacks=[_make_checker_callback("passed")],
        )

        result = run_loop(
            project_root=tmp_path,
            intent="Build hello.txt",
            eval_skill="Check file exists",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        assert result.success is True
        assert result.rounds == 1

    def test_only_run_001_exists(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        assert (tmp_path / "run-sets" / "run-001").is_dir()
        assert not (tmp_path / "run-sets" / "run-002").exists()


class TestMultiRoundConvergence:
    """3.2 多轮收敛"""

    def test_two_rounds_to_pass(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["executor v1", "executor v2"])
        eval_content_r1 = "L1: FAIL\ncount mismatch"
        eval_content_r2 = "L0: PASS\nL1: PASS\nL2: PASS"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content_r1, eval_content_r2],
            callbacks=[
                _make_evaluator_callback(eval_content_r1),
                _make_evaluator_callback(eval_content_r2),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["checking r1", "checking r2"],
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
        )

        assert result.success is True
        assert result.rounds == 2
        assert result.run_ids == ["run-001", "run-002"]

    def test_round2_executor_prompt_contains_round1_eval(self, tmp_path):
        _init_git_repo(tmp_path)
        eval_report_r1 = "L1: FAIL\ncount mismatch: expected 10, got 5"
        eval_report_r2 = "all pass"
        executor_driver = MockDriver(responses=["exec v1", "exec v2"])
        evaluator_driver = CallbackMockDriver(
            responses=[eval_report_r1, eval_report_r2],
            callbacks=[
                _make_evaluator_callback(eval_report_r1),
                _make_evaluator_callback(eval_report_r2),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("passed"),
            ],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        # 第 2 次调用是 round 2 的 executor（索引 1，executor 单独的 driver）
        round2_executor_prompt = executor_driver.call_log[1]["prompt"]
        # 现在 executor prompt 引用了 round 1 的评估报告路径，而非内联内容
        # 验证 prompt 包含对 run-001 评估报告的引用
        assert "run-001" in round2_executor_prompt
        assert "eval-report" in round2_executor_prompt
        # 验证 round 1 报告文件确实包含预期内容
        report_r1 = tmp_path / "run-sets" / "run-001" / "eval-report" / "report.md"
        assert report_r1.exists()
        assert "count mismatch" in report_r1.read_text()

    def test_both_run_dirs_exist(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["e1", "e2"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval1", "eval2"],
            callbacks=[
                _make_evaluator_callback("eval1"),
                _make_evaluator_callback("eval2"),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("passed"),
            ],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        assert (tmp_path / "run-sets" / "run-001").is_dir()
        assert (tmp_path / "run-sets" / "run-002").is_dir()


class TestFirstRoundNoEval:
    """3.3 首轮无前一轮评估结果"""

    def test_first_round_executor_no_eval_section(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        first_executor_prompt = executor_driver.call_log[0]["prompt"]
        assert "previous evaluation" not in first_executor_prompt.lower()


class TestMaxIterationGuard:
    """3.4 最大迭代次数守护"""

    def test_raises_after_max_iterations(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec", "exec", "exec"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval", "eval", "eval"],
            callbacks=[
                _make_evaluator_callback("eval"),
                _make_evaluator_callback("eval"),
                _make_evaluator_callback("eval"),
            ],
        )
        # 3 轮全部 fail
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2", "r3"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("failed"),
                _make_checker_callback("failed"),
            ],
        )

        with pytest.raises(MaxIterationsExceededError, match="3 iterations"):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=executor_driver,
                evaluator_driver=evaluator_driver,
                checker_driver=checker_driver,
                max_iterations=3,
            )

    def test_does_not_run_forever(self, tmp_path):
        """即使 checker 一直返回 failed，也在 max_iterations 后停止"""
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"] * 5)
        evaluator_driver = CallbackMockDriver(
            responses=["eval"] * 5,
            callbacks=[_make_evaluator_callback("eval")] * 5,
        )
        checker_driver = CallbackMockDriver(
            responses=["r"] * 5,
            callbacks=[_make_checker_callback("failed")] * 5,
        )

        with pytest.raises(MaxIterationsExceededError):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=executor_driver,
                evaluator_driver=evaluator_driver,
                checker_driver=checker_driver,
                max_iterations=5,
            )


class TestDirectoryLayoutAfterRun:
    """3.5 运行后的目录结构验证"""

    def test_run_dirs_have_correct_subdirs(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["e1", "e2"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval1", "eval2"],
            callbacks=[
                _make_evaluator_callback("eval1"),
                _make_evaluator_callback("eval2"),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("passed"),
            ],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        for run_id in ["run-001", "run-002"]:
            run_dir = tmp_path / "run-sets" / run_id
            assert (run_dir / "logs").is_dir()
            assert (run_dir / "eval-report").is_dir()
            assert (run_dir / "checker-result").is_dir()  # checker-result 目录

    def test_task_solution_exists(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        assert (tmp_path / "task" / "solution").is_dir()

    def test_eval_report_saved(self, tmp_path):
        _init_git_repo(tmp_path)
        eval_output = "L0: PASS\nL1: PASS\nOverall: PASSED"
        executor_driver = MockDriver(responses=["exec"])
        evaluator_driver = CallbackMockDriver(
            responses=[eval_output],
            callbacks=[_make_evaluator_callback(eval_output)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        report = tmp_path / "run-sets" / "run-001" / "eval-report" / "report.md"
        assert report.exists()
        assert report.read_text() == eval_output

    def test_checker_result_saved(self, tmp_path):
        """验证 checker 结果文件被保存"""
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
        )

        result_file = tmp_path / "run-sets" / "run-001" / "checker-result" / "result.md"
        assert result_file.exists()
        assert "<checker_result>passed</checker_result>" in result_file.read_text()

    def test_git_commits_exist(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["e1", "e2"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval1", "eval2"],
            callbacks=[
                _make_evaluator_callback("eval1"),
                _make_evaluator_callback("eval2"),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2"],
            callbacks=[
                _make_checker_callback("failed"),
                _make_checker_callback("passed"),
            ],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
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
        eval_content = "eval report"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        checker_driver = CallbackMockDriver(
            responses=["checking"],
            callbacks=[_make_checker_callback("passed")],
        )

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
        assert "Result Output Location" in checker_driver.call_log[0]["prompt"]

    def test_evaluator_defaults_to_executor_driver(self, tmp_path):
        """不指定 evaluator_driver 时，复用 executor_driver。
        
        注意：即使复用 executor_driver，evaluator 也需要写入报告文件。
        使用 CallbackMockDriver 来处理这两种调用。
        """
        _init_git_repo(tmp_path)
        eval_content = "eval"
        exec_eval_driver = CallbackMockDriver(
            responses=["exec", eval_content],
            callbacks=[
                None,  # executor 不需要写文件
                _make_evaluator_callback(eval_content),  # evaluator 需要写文件
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        run_loop(
            project_root=tmp_path,
            intent="task",
            eval_skill="skill",
            executor_driver=exec_eval_driver,
            checker_driver=checker_driver,
        )

        assert len(exec_eval_driver.call_log) == 2  # executor + evaluator


class TestLoopResult:
    """LoopResult 返回值验证"""

    def test_result_contains_run_ids(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["e1", "e2"])
        evaluator_driver = CallbackMockDriver(
            responses=["eval1", "eval2"],
            callbacks=[
                _make_evaluator_callback("eval1"),
                _make_evaluator_callback("eval2"),
            ],
        )
        checker_driver = CallbackMockDriver(
            responses=["r1", "r2"],
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
        )

        assert result.run_ids == ["run-001", "run-002"]

    def test_result_contains_last_eval_report(self, tmp_path):
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "final eval"
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
        )

        assert result.last_eval_report == eval_content


class TestCheckerResultNotFound:
    """3.7 Checker 未写入结果文件时的错误处理"""

    def test_raises_when_checker_does_not_write_result(self, tmp_path):
        """当 Checker 没有写入结果文件时，应抛出 CheckerResultNotFoundError"""
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec"])
        eval_content = "eval"
        evaluator_driver = CallbackMockDriver(
            responses=[eval_content],
            callbacks=[_make_evaluator_callback(eval_content)],
        )
        # 使用普通 MockDriver，不会写入文件
        checker_driver = MockDriver(responses=["some output but no file"])

        with pytest.raises(CheckerResultNotFoundError, match="did not write result"):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=executor_driver,
                evaluator_driver=evaluator_driver,
                checker_driver=checker_driver,
            )


class TestEvaluatorReportNotFound:
    """3.8 Evaluator 未写入报告文件时的错误处理"""

    def test_raises_when_evaluator_does_not_write_report(self, tmp_path):
        """当 Evaluator 没有写入报告文件时，应抛出 EvaluatorReportNotFoundError"""
        _init_git_repo(tmp_path)
        executor_driver = MockDriver(responses=["exec output"])
        # 使用普通 MockDriver，不会写入文件
        evaluator_driver = MockDriver(responses=["some output but no file"])
        # checker 不会被调用（因为 evaluator 阶段就会失败）
        checker_driver = MockDriver(responses=["should not reach"])

        with pytest.raises(EvaluatorReportNotFoundError, match="did not write report"):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=executor_driver,
                evaluator_driver=evaluator_driver,
                checker_driver=checker_driver,
            )

    def test_executor_succeeds_but_evaluator_fails_to_write(self, tmp_path):
        """Executor 成功执行，但 Evaluator 未写入报告文件"""
        _init_git_repo(tmp_path)
        # 分开 executor 和 evaluator driver
        executor_driver = MockDriver(responses=["executor completed successfully"])
        # evaluator 返回输出但不写文件
        evaluator_driver = MockDriver(responses=["L0: PASS\nL1: PASS\nL2: PASS"])
        checker_driver = CallbackMockDriver(
            responses=["ok"],
            callbacks=[_make_checker_callback("passed")],
        )

        with pytest.raises(EvaluatorReportNotFoundError):
            run_loop(
                project_root=tmp_path,
                intent="task",
                eval_skill="skill",
                executor_driver=executor_driver,
                evaluator_driver=evaluator_driver,
                checker_driver=checker_driver,
            )
