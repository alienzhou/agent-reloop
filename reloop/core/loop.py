"""Reloop 迭代主循环 — 框架的核心"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from reloop.core.checker import parse_checker_result
from reloop.core.git import auto_commit_after_execution
from reloop.core.prompts import (
    build_checker_prompt,
    build_evaluator_prompt,
    build_executor_prompt,
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

    Returns:
        LoopResult 包含成功/失败、轮数、run_id 列表
    """
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

        # ② Executor
        exec_spec = _EXEC_SPEC_TEMPLATE.format(
            solution_dir=str(project_root / "task" / "solution"),
            artifacts_dir=str(run_dir / "artifacts"),
            logs_dir=str(run_dir / "logs"),
        )
        executor_prompt = build_executor_prompt(intent, last_eval_result, exec_spec)
        logger.info("Running executor...")
        executor_driver.run(prompt=executor_prompt, workdir=workdir)

        # git commit after executor
        if enable_git_commit:
            auto_commit_after_execution(project_root, run_id)

        # ③ Evaluator
        artifacts_dir = str(run_dir / "artifacts")
        evaluator_prompt = build_evaluator_prompt(artifacts_dir, eval_skill)
        logger.info("Running evaluator...")
        eval_output = evaluator_driver.run(prompt=evaluator_prompt, workdir=workdir)

        # 保存评估报告
        report_path = run_dir / "eval-report" / "report.md"
        report_path.write_text(eval_output)
        last_eval_result = eval_output

        # ④ Checker
        checker_prompt = build_checker_prompt(eval_output)
        logger.info("Running checker...")
        checker_output = checker_driver.run(prompt=checker_prompt, workdir=workdir)

        passed = parse_checker_result(checker_output)
        logger.info("Round %d result: %s", round_num, "PASSED" if passed else "FAILED")

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
