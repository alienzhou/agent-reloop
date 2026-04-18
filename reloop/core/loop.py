"""Reloop 迭代主循环 — 框架的核心"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from reloop.core.checker import extract_checker_explanation, parse_checker_result
from reloop.core.git import auto_commit_after_execution
from reloop.core.logging import (
    AgentLogger,
    StreamOutput,
    get_run_log_paths,
    log_driver_call,
    setup_system_logging,
)
from reloop.core.prompts import (
    build_checker_prompt,
    build_evaluator_prompt,
    build_executor_prompt,
)
from reloop.core.resume import (
    ResumeChoice,
    RunStatus,
    detect_run_status,
    full_cleanup,
    get_last_run_id,
    prompt_resume_choice,
    rollback_incomplete_run,
)
from reloop.core.workspace import init_workspace
from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 10

# 框架内置的通用执行规范
_EXEC_SPEC_TEMPLATE = """## Execution Rules

- Solution code goes in: {solution_dir}
- Execution artifacts (final outputs) go in: {artifacts_dir}
- Execution logs go in: {logs_dir}
- Do NOT modify files outside these directories.
- Iterate on the existing solution — do not recreate from scratch each round.
"""


class MaxIterationsExceededError(Exception):
    """迭代次数超过上限"""


@dataclass
class LoopResult:
    """迭代循环的结果"""
    success: bool
    rounds: int
    run_ids: List[str] = field(default_factory=list)
    last_eval_report: Optional[str] = None


def run_loop(
    project_root: Path,
    intent: str,
    eval_skill: str,
    executor_driver: Driver,
    evaluator_driver: Optional[Driver] = None,
    checker_driver: Optional[Driver] = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    enable_git_commit: bool = True,
    fresh: bool = False,
    interactive: bool = True,
    stream_max_lines: int = 4,
) -> LoopResult:
    """执行 Reloop 迭代主循环。

    四步循环：init_workspace → executor → evaluator → checker
    直到 checker 判定 pass 或达到最大迭代次数。

    Args:
        project_root:     项目根目录
        intent:           INTENT 内容
        eval_skill:       evaluator Skill 内容
        executor_driver:  executor 使用的 Driver
        evaluator_driver: evaluator 使用的 Driver（默认复用 executor_driver）
        checker_driver:   checker 使用的 Driver（默认复用 evaluator_driver）
        max_iterations:   最大迭代次数
        enable_git_commit: 是否启用自动 git commit
        fresh:           强制从头开始（忽略历史状态）
        interactive:     是否交互模式（提示用户选择）
        stream_max_lines: 流式输出终端显示行数

    Returns:
        LoopResult 包含成功/失败、轮数、run_id 列表
    """
    # 初始化系统日志
    setup_system_logging(project_root / "logs" / "reloop.log")

    # 检测状态并处理恢复
    if not fresh:
        status = detect_run_status(project_root)
        if status != RunStatus.FRESH:
            last_run_id = get_last_run_id(project_root)
            choice = prompt_resume_choice(status, last_run_id, interactive)
            if choice == ResumeChoice.RESET:
                full_cleanup(project_root)
            elif status == RunStatus.INTERRUPTED and last_run_id:
                rollback_incomplete_run(project_root, last_run_id)

    if evaluator_driver is None:
        evaluator_driver = executor_driver
    if checker_driver is None:
        checker_driver = evaluator_driver

    last_eval_result: Optional[str] = None
    run_ids: List[str] = []
    workdir = str(project_root)

    for round_num in range(1, max_iterations + 1):
        logger.info("=== Round %d ===", round_num)

        # ① 初始化工作空间
        run_dir = init_workspace(project_root)
        run_id = run_dir.name
        run_ids.append(run_id)
        logger.info("Workspace initialized: %s", run_dir)

        # 获取日志路径
        log_paths = get_run_log_paths(project_root, run_id)

        # ② Executor
        exec_spec = _EXEC_SPEC_TEMPLATE.format(
            solution_dir=str(project_root / "task" / "solution"),
            artifacts_dir=str(run_dir / "artifacts"),
            logs_dir=str(run_dir / "logs"),
        )
        executor_prompt = build_executor_prompt(intent, last_eval_result, exec_spec)
        logger.info("Running executor...")

        # 记录 prompt
        _log_prompt(log_paths["prompt"], "EXECUTOR", executor_prompt)

        # 流式输出
        executor_stream = StreamOutput(
            log_path=log_paths["executor"],
            max_lines=stream_max_lines,
        )
        print(f"[{time.strftime('%H:%M:%S')}] 📝 Executor running...")
        executor_output = executor_driver.run(
            prompt=executor_prompt,
            workdir=workdir,
            stream_callback=executor_stream.write,
        )
        executor_stream.finalize()
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Executor done")

        # 记录 driver call
        log_driver_call(
            log_path=log_paths["driver"],
            command=["executor", "agent"],
            workdir=workdir,
            prompt=executor_prompt,
            output=executor_output,
            exit_code=0,
            duration=0.0,  # 实际实现时记录真实时间
        )

        # git commit after executor
        if enable_git_commit:
            auto_commit_after_execution(project_root, run_id)

        # ③ Evaluator
        artifacts_dir = str(run_dir / "artifacts")
        evaluator_prompt = build_evaluator_prompt(artifacts_dir, eval_skill)
        logger.info("Running evaluator...")

        _log_prompt(log_paths["prompt"], "EVALUATOR", evaluator_prompt)

        evaluator_stream = StreamOutput(
            log_path=log_paths["evaluator"],
            max_lines=stream_max_lines,
        )
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 Evaluator running...")
        eval_output = evaluator_driver.run(
            prompt=evaluator_prompt,
            workdir=workdir,
            stream_callback=evaluator_stream.write,
        )
        evaluator_stream.finalize()
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Evaluator done")

        log_driver_call(
            log_path=log_paths["driver"],
            command=["evaluator", "agent"],
            workdir=workdir,
            prompt=evaluator_prompt,
            output=eval_output,
            exit_code=0,
            duration=0.0,
        )

        # 保存评估报告
        report_path = run_dir / "eval-report" / "report.md"
        report_path.write_text(eval_output)
        last_eval_result = eval_output

        # ④ Checker
        checker_prompt = build_checker_prompt(eval_output)
        logger.info("Running checker...")

        _log_prompt(log_paths["prompt"], "CHECKER", checker_prompt)

        checker_stream = StreamOutput(
            log_path=log_paths["checker"],
            max_lines=stream_max_lines,
        )
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Checker running...")
        checker_output = checker_driver.run(
            prompt=checker_prompt,
            workdir=workdir,
            stream_callback=checker_stream.write,
        )
        checker_stream.finalize()

        passed = parse_checker_result(checker_output)
        explanation = extract_checker_explanation(checker_output)

        log_driver_call(
            log_path=log_paths["driver"],
            command=["checker", "agent"],
            workdir=workdir,
            prompt=checker_prompt,
            output=checker_output,
            exit_code=0,
            duration=0.0,
        )

        if passed:
            print(f"[{time.strftime('%H:%M:%S')}] ✅ Round {round_num}: PASSED")
            logger.info("Round %d result: PASSED", round_num)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Round {round_num}: FAILED")
            logger.info("Round %d result: FAILED", round_num)

        # 打印日志路径提示
        print(f"""
📄 Full logs for {run_id}:
   - Driver:    {log_paths['driver']}
   - Executor:  {log_paths['executor']}
   - Evaluator: {log_paths['evaluator']}
   - Checker:   {log_paths['checker']}
   - Prompt:    {log_paths['prompt']}
""")

        if passed:
            return LoopResult(
                success=True,
                rounds=round_num,
                run_ids=run_ids,
                last_eval_report=eval_output,
            )

    raise MaxIterationsExceededError(
        f"Loop did not converge after {max_iterations} iterations"
    )


def _log_prompt(log_path: Path, role: str, prompt: str) -> None:
    """记录 prompt 到日志文件。

    Args:
        log_path: prompt 日志文件路径
        role: 角色（EXECUTOR/EVALUATOR/CHECKER）
        prompt: prompt 内容
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== {role} PROMPT ({timestamp}) ===\n")
        f.write(prompt)
        f.write("\n=== END ===\n\n")
