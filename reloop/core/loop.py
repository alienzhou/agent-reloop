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
    setup_rotating_logger,
)
from reloop.core.prompts import (
    build_checker_prompt,
    build_evaluator_prompt,
    build_executor_prompt,
    build_history_runs_hint,
)
from reloop.core.report_sanitizer import abstract_eval_report
from reloop.core.timing import (
    end_session,
    format_elapsed_verbose,
    load_timing,
    reset_timing,
    start_session,
)
from reloop.core.resume import (
    ResumeChoice,
    RunPhase,
    RunStatus,
    detect_run_phase,
    detect_run_status,
    full_cleanup,
    get_last_run_id,
    get_resumable_run,
    prompt_resume_choice,
    rollback_incomplete_run,
)
from reloop.core.workspace import init_workspace
from reloop.drivers.base import Driver

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 10


class CheckerResultNotFoundError(Exception):
    """Checker 未将结果写入指定文件。"""

    pass


class EvaluatorReportNotFoundError(Exception):
    """Evaluator 未将评估报告写入指定文件。"""

    pass


# 框架内置的通用执行规范
_EXEC_SPEC_TEMPLATE = """## Execution Rules

- Solution code goes in: {solution_dir}
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
    stream_max_lines: int = 15,
    use_live_ui: bool = True,
    start_phase: Optional[str] = None,
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
        use_live_ui:     是否使用 Live UI 分区界面
        start_phase:     从指定阶段开始 (evaluator/checker)，None 表示自动检测

    Returns:
        LoopResult 包含成功/失败、轮数、run_id 列表
    """
    # 初始化系统日志（带轮转压缩，DEBUG 级别）
    setup_rotating_logger("reloop", project_root / "logs" / "reloop.log", level=logging.DEBUG)

    # 确定恢复策略
    resume_choice = ResumeChoice.CONTINUE
    resume_run_id: Optional[str] = None
    resume_phase: Optional[RunPhase] = None

    # 检测状态并处理恢复
    if not fresh:
        status = detect_run_status(project_root)
        if status != RunStatus.FRESH:
            last_run_id = get_last_run_id(project_root)
            
            # 检测细粒度阶段
            if last_run_id:
                run_dir = project_root / "run-sets" / last_run_id
                resume_phase = detect_run_phase(project_root, run_dir)
                resume_run_id = last_run_id
            
            # 如果用户指定了 start_phase，直接使用
            if start_phase:
                if start_phase == "checker":
                    resume_choice = ResumeChoice.FROM_CHECKER
                elif start_phase == "evaluator":
                    resume_choice = ResumeChoice.FROM_EVALUATOR
                else:
                    resume_choice = ResumeChoice.CONTINUE
            else:
                resume_choice = prompt_resume_choice(status, last_run_id, resume_phase, interactive)
            
            if resume_choice == ResumeChoice.RESET:
                full_cleanup(project_root)
                resume_run_id = None
                resume_phase = None
            elif resume_choice == ResumeChoice.CONTINUE:
                if status == RunStatus.INTERRUPTED and last_run_id:
                    rollback_incomplete_run(project_root, last_run_id)
                    resume_run_id = None
                    resume_phase = None

    if evaluator_driver is None:
        evaluator_driver = executor_driver
    if checker_driver is None:
        checker_driver = evaluator_driver

    # 根据 use_live_ui 选择执行方式
    if use_live_ui:
        return _run_loop_with_live_ui(
            project_root=project_root,
            intent=intent,
            eval_skill=eval_skill,
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
            max_iterations=max_iterations,
            enable_git_commit=enable_git_commit,
            stream_max_lines=stream_max_lines,
            resume_choice=resume_choice,
            resume_run_id=resume_run_id,
        )
    else:
        return _run_loop_classic(
            project_root=project_root,
            intent=intent,
            eval_skill=eval_skill,
            executor_driver=executor_driver,
            evaluator_driver=evaluator_driver,
            checker_driver=checker_driver,
            max_iterations=max_iterations,
            enable_git_commit=enable_git_commit,
            stream_max_lines=stream_max_lines,
            resume_choice=resume_choice,
            resume_run_id=resume_run_id,
        )


def _run_loop_with_live_ui(
    project_root: Path,
    intent: str,
    eval_skill: str,
    executor_driver: Driver,
    evaluator_driver: Driver,
    checker_driver: Driver,
    max_iterations: int,
    enable_git_commit: bool,
    stream_max_lines: int,
    resume_choice: ResumeChoice = ResumeChoice.CONTINUE,
    resume_run_id: Optional[str] = None,
) -> LoopResult:
    """使用 Live UI 执行迭代循环。"""
    from reloop.core.ui import ReloopLiveUI, StageStatus

    # 加载累计时间
    timing_data = load_timing(project_root)
    accumulated_time = timing_data.total_elapsed_seconds
    
    # 如果是 reset 模式，重置计时
    if resume_choice == ResumeChoice.RESET:
        reset_timing(project_root)
        accumulated_time = 0.0
    
    # 开始新会话
    start_session(project_root)
    
    ui = ReloopLiveUI(
        max_output_lines=stream_max_lines,
        accumulated_time=accumulated_time,
        project_root=project_root,
    )
    
    last_eval_report_path: Optional[Path] = None
    run_ids: List[str] = []
    workdir = str(project_root)
    
    # 处理恢复场景
    skip_executor = False
    skip_evaluator = False
    
    if resume_choice == ResumeChoice.FROM_CHECKER and resume_run_id:
        # 从 Checker 开始，复用已有的 eval-report
        skip_executor = True
        skip_evaluator = True
        run_dir = project_root / "run-sets" / resume_run_id
        report_path = run_dir / "eval-report" / "report.md"
        if report_path.exists():
            last_eval_report_path = report_path
            logger.info(f"Resuming from checker, reusing eval-report from {resume_run_id}")
    elif resume_choice == ResumeChoice.FROM_EVALUATOR and resume_run_id:
        # 从 Evaluator 开始，复用已有的 solution
        skip_executor = True
        logger.info(f"Resuming from evaluator, reusing solution from {resume_run_id}")

    # 确定起始轮数（resume 场景从已有 run 数推断）
    start_round_num = 1
    if resume_run_id:
        # 从 "run-003" 提取数字 3
        try:
            start_round_num = int(resume_run_id.replace("run-", ""))
        except ValueError:
            logger.warning(f"Could not parse round number from {resume_run_id}, starting from 1")
            start_round_num = 1
    
    # 边界检查：如果起始轮数已经超过最大迭代次数，直接报错
    if start_round_num > max_iterations:
        raise MaxIterationsExceededError(
            f"Resume round {start_round_num} exceeds max_iterations {max_iterations}"
        )

    with ui.live_context():
        for round_num in range(start_round_num, max_iterations + 1):
            logger.info("=== Round %d ===", round_num)

            # ① 初始化工作空间
            # 如果是恢复模式的第一轮，复用已有的 run_dir
            if (skip_executor or skip_evaluator) and resume_run_id and round_num == start_round_num:
                run_dir = project_root / "run-sets" / resume_run_id
                run_id = resume_run_id
                logger.info("Reusing workspace: %s", run_dir)
            else:
                run_dir = init_workspace(project_root)
                run_id = run_dir.name
                logger.info("Workspace initialized: %s", run_dir)
            
            run_ids.append(run_id)

            # 获取日志路径
            log_paths = get_run_log_paths(project_root, run_id)

            # 通知 UI 开始新一轮
            ui.start_round(round_num, max_iterations, run_id)

            # ② Executor（可跳过）
            if skip_executor and round_num == start_round_num:
                ui.set_stage("Executor", StageStatus.SKIPPED)
                ui.complete_stage("Executor", skipped=True)
                logger.info("Skipping executor (resume mode)")
            else:
                exec_spec = _EXEC_SPEC_TEMPLATE.format(
                    solution_dir=str(project_root / "task" / "solution"),
                    logs_dir=str(run_dir / "logs"),
                )
                
                # 提案输出路径
                proposal_output_path = str(run_dir / "proposal.md")
                
                # 历史 run-sets 提示
                history_runs_hint = build_history_runs_hint(round_num)
                
                # 抽象化上一轮评估报告
                abstract_summary = None
                if last_eval_report_path and last_eval_report_path.exists():
                    try:
                        full_report = last_eval_report_path.read_text(encoding="utf-8")
                        abstract_summary = abstract_eval_report(full_report, str(last_eval_report_path))
                    except Exception as e:
                        logger.warning(f"Failed to abstract eval report: {e}")
                
                executor_prompt = build_executor_prompt(
                    intent=intent,
                    last_eval_report_path=last_eval_report_path,
                    exec_spec=exec_spec,
                    round_num=round_num,
                    proposal_output_path=proposal_output_path,
                    history_runs_hint=history_runs_hint,
                    abstract_eval_summary=abstract_summary,
                )
                logger.info("Running executor...")

                # 记录 prompt
                _log_prompt(log_paths["prompt"], "EXECUTOR", executor_prompt)

                # 设置 UI 状态
                ui.set_stage("Executor", StageStatus.RUNNING)

                # 创建双重回调：写入文件 + 更新 UI
                executor_stream = StreamOutput(log_path=log_paths["executor"], max_lines=1000)
                
                def executor_callback(chunk: str) -> None:
                    executor_stream.write(chunk)
                    ui.write_output(chunk)

                logger.debug("Calling executor driver, prompt_len=%d", len(executor_prompt))
                try:
                    executor_output = executor_driver.run(
                        prompt=executor_prompt,
                        workdir=workdir,
                        stream_callback=executor_callback,
                    )
                    logger.debug("executor driver completed, output_len=%d", len(executor_output))
                except Exception as e:
                    logger.error("driver failed: stage=executor, round=%d, run_id=%s: %s", round_num, run_id, e)
                    raise
                executor_stream.finalize()
                ui.complete_stage("Executor")

                # 记录 driver call
                log_driver_call(
                    log_path=log_paths["driver"],
                    command=["executor", "agent"],
                    workdir=workdir,
                    prompt=executor_prompt,
                    output=executor_output,
                    exit_code=0,
                    duration=0.0,
                )

                # git commit after executor
                if enable_git_commit:
                    auto_commit_after_execution(project_root, run_id)

            # ③ Evaluator（可跳过）
            if skip_evaluator and round_num == start_round_num:
                ui.set_stage("Evaluator", StageStatus.SKIPPED)
                ui.complete_stage("Evaluator", skipped=True)
                logger.info("Skipping evaluator (resume mode)")
                # last_eval_result 已在前面设置
            else:
                solution_dir = str(project_root / "task" / "solution")
                
                # 预先计算报告路径并创建目录，让 Evaluator 直接写入
                report_path = run_dir / "eval-report" / "report.md"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                
                evaluator_prompt = build_evaluator_prompt(
                    solution_dir, 
                    eval_skill,
                    str(report_path),
                )
                logger.info("Running evaluator...")

                _log_prompt(log_paths["prompt"], "EVALUATOR", evaluator_prompt)

                ui.set_stage("Evaluator", StageStatus.RUNNING)

                evaluator_stream = StreamOutput(log_path=log_paths["evaluator"], max_lines=1000)
                
                def evaluator_callback(chunk: str) -> None:
                    evaluator_stream.write(chunk)
                    ui.write_output(chunk)

                logger.debug("Calling evaluator driver, prompt_len=%d", len(evaluator_prompt))
                try:
                    eval_output = evaluator_driver.run(
                        prompt=evaluator_prompt,
                        workdir=workdir,
                        stream_callback=evaluator_callback,
                    )
                    logger.debug("evaluator driver completed, output_len=%d", len(eval_output))
                except Exception as e:
                    logger.error("driver failed: stage=evaluator, round=%d, run_id=%s: %s", round_num, run_id, e)
                    raise
                evaluator_stream.finalize()
                ui.complete_stage("Evaluator")

                log_driver_call(
                    log_path=log_paths["driver"],
                    command=["evaluator", "agent"],
                    workdir=workdir,
                    prompt=evaluator_prompt,
                    output=eval_output,
                    exit_code=0,
                    duration=0.0,
                )

                # 检查 Evaluator 是否已将报告写入指定文件
                if not report_path.exists():
                    raise EvaluatorReportNotFoundError(
                        f"Evaluator did not write report to {report_path}"
                    )
                # 记录报告路径，供下一轮执行器使用
                last_eval_report_path = report_path

            # 恢复标志只在第一轮生效
            skip_executor = False
            skip_evaluator = False

            # ④ Checker
            checker_result_path = run_dir / "checker-result" / "result.md"
            checker_result_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 确保 report_path 指向正确的位置
            report_path = run_dir / "eval-report" / "report.md"

            checker_prompt = build_checker_prompt(str(report_path), str(checker_result_path))
            logger.info("Running checker...")

            _log_prompt(log_paths["prompt"], "CHECKER", checker_prompt)

            ui.set_stage("Checker", StageStatus.RUNNING)

            checker_stream = StreamOutput(log_path=log_paths["checker"], max_lines=1000)
            
            def checker_callback(chunk: str) -> None:
                checker_stream.write(chunk)
                ui.write_output(chunk)

            logger.debug("Calling checker driver, prompt_len=%d", len(checker_prompt))
            try:
                checker_output = checker_driver.run(
                    prompt=checker_prompt,
                    workdir=workdir,
                    stream_callback=checker_callback,
                )
                logger.debug("checker driver completed, output_len=%d", len(checker_output))
            except Exception as e:
                logger.error("driver failed: stage=checker, round=%d, run_id=%s: %s", round_num, run_id, e)
                raise
            checker_stream.finalize()

            # 从文件读取 checker 结果
            if not checker_result_path.exists():
                raise CheckerResultNotFoundError(
                    f"Checker did not write result to {checker_result_path}"
                )
            checker_result = checker_result_path.read_text()
            passed = parse_checker_result(checker_result)
            explanation = extract_checker_explanation(checker_result)

            ui.complete_stage("Checker", success=passed)
            ui.end_round(passed)

            log_driver_call(
                log_path=log_paths["driver"],
                command=["checker", "agent"],
                workdir=workdir,
                prompt=checker_prompt,
                output=checker_result,
                exit_code=0,
                duration=0.0,
            )

            if passed:
                logger.info("Round %d result: PASSED", round_num)
            else:
                logger.info("Round %d result: FAILED", round_num)

            if passed:
                # Live UI 结束后打印最终摘要
                break

        # 结束 live context 后打印摘要
        pass

    # 保存计时数据
    session_elapsed = ui.get_session_elapsed()
    final_timing = end_session(project_root, session_elapsed)
    total_time_str = format_elapsed_verbose(final_timing.total_elapsed_seconds)
    
    # 在 live context 外打印最终结果
    if passed:
        ui.print_final_summary(True, round_num, run_ids)
        ui.print_log_paths(run_id, log_paths)
        ui.console.print(f"[dim]⏱️  总耗时: {total_time_str}[/dim]")
        # 读取最后的评估报告内容
        last_report_content = None
        if last_eval_report_path and last_eval_report_path.exists():
            last_report_content = last_eval_report_path.read_text(encoding="utf-8")
        return LoopResult(
            success=True,
            rounds=round_num,
            run_ids=run_ids,
            last_eval_report=last_report_content,
        )
    
    # 如果循环结束但未通过
    ui.print_final_summary(False, max_iterations, run_ids)
    ui.print_log_paths(run_id, log_paths)
    ui.console.print(f"[dim]⏱️  总耗时: {total_time_str}[/dim]")
    raise MaxIterationsExceededError(
        f"Loop did not converge after {max_iterations} iterations"
    )


def _run_loop_classic(
    project_root: Path,
    intent: str,
    eval_skill: str,
    executor_driver: Driver,
    evaluator_driver: Driver,
    checker_driver: Driver,
    max_iterations: int,
    enable_git_commit: bool,
    stream_max_lines: int,
    resume_choice: ResumeChoice = ResumeChoice.CONTINUE,
    resume_run_id: Optional[str] = None,
) -> LoopResult:
    """经典模式执行迭代循环（无 Live UI）。"""
    # 加载累计时间
    timing_data = load_timing(project_root)
    accumulated_time = timing_data.total_elapsed_seconds
    
    # 如果是 reset 模式，重置计时
    if resume_choice == ResumeChoice.RESET:
        reset_timing(project_root)
        accumulated_time = 0.0
    
    # 开始新会话
    start_session(project_root)
    session_start_time = time.time()
    last_timing_save = session_start_time  # 上次保存计时的时间
    timing_save_interval = 30.0  # 每 30 秒保存一次
    
    def maybe_save_timing() -> None:
        """检查并保存计时数据（每 30 秒保存一次）。"""
        nonlocal last_timing_save
        now = time.time()
        if now - last_timing_save >= timing_save_interval:
            try:
                session_elapsed = now - session_start_time
                timing = load_timing(project_root)
                timing.total_elapsed_seconds = accumulated_time + session_elapsed
                save_timing(project_root, timing)
                last_timing_save = now
                logger.debug(f"Timing saved: {timing.total_elapsed_seconds:.1f}s")
            except Exception as e:
                logger.warning(f"Failed to save timing: {e}")
    
    last_eval_report_path: Optional[Path] = None
    run_ids: List[str] = []
    workdir = str(project_root)
    
    # 处理恢复场景
    skip_executor = False
    skip_evaluator = False
    
    if resume_choice == ResumeChoice.FROM_CHECKER and resume_run_id:
        skip_executor = True
        skip_evaluator = True
        run_dir = project_root / "run-sets" / resume_run_id
        report_path = run_dir / "eval-report" / "report.md"
        if report_path.exists():
            last_eval_report_path = report_path
            print(f"[{time.strftime('%H:%M:%S')}] ⏭️ 恢复模式：从 Checker 开始，复用 {resume_run_id} 的 eval-report")
    elif resume_choice == ResumeChoice.FROM_EVALUATOR and resume_run_id:
        skip_executor = True
        print(f"[{time.strftime('%H:%M:%S')}] ⏭️ 恢复模式：从 Evaluator 开始，复用 {resume_run_id} 的 solution")
    
    # 显示累计时间信息
    if accumulated_time > 0:
        print(f"[{time.strftime('%H:%M:%S')}] ⏱️  累计时间: {format_elapsed_verbose(accumulated_time)}")

    # 确定起始轮数（resume 场景从已有 run 数推断）
    start_round_num = 1
    if resume_run_id:
        # 从 "run-003" 提取数字 3
        try:
            start_round_num = int(resume_run_id.replace("run-", ""))
        except ValueError:
            logger.warning(f"Could not parse round number from {resume_run_id}, starting from 1")
            start_round_num = 1
    
    # 边界检查：如果起始轮数已经超过最大迭代次数，直接报错
    if start_round_num > max_iterations:
        raise MaxIterationsExceededError(
            f"Resume round {start_round_num} exceeds max_iterations {max_iterations}"
        )

    for round_num in range(start_round_num, max_iterations + 1):
        logger.info("=== Round %d ===", round_num)

        # ① 初始化工作空间
        if (skip_executor or skip_evaluator) and resume_run_id and round_num == start_round_num:
            run_dir = project_root / "run-sets" / resume_run_id
            run_id = resume_run_id
            logger.info("Reusing workspace: %s", run_dir)
        else:
            run_dir = init_workspace(project_root)
            run_id = run_dir.name
            logger.info("Workspace initialized: %s", run_dir)
        
        run_ids.append(run_id)

        # 获取日志路径
        log_paths = get_run_log_paths(project_root, run_id)

        # ② Executor（可跳过）
        if skip_executor and round_num == start_round_num:
            print(f"[{time.strftime('%H:%M:%S')}] ⏭️ Executor skipped (resume mode)")
        else:
            exec_spec = _EXEC_SPEC_TEMPLATE.format(
                solution_dir=str(project_root / "task" / "solution"),
                logs_dir=str(run_dir / "logs"),
            )
            
            # 提案输出路径
            proposal_output_path = str(run_dir / "proposal.md")
            
            # 历史 run-sets 提示
            history_runs_hint = build_history_runs_hint(round_num)
            
            # 抽象化上一轮评估报告
            abstract_summary = None
            if last_eval_report_path and last_eval_report_path.exists():
                try:
                    full_report = last_eval_report_path.read_text(encoding="utf-8")
                    abstract_summary = abstract_eval_report(full_report, str(last_eval_report_path))
                except Exception as e:
                    logger.warning(f"Failed to abstract eval report: {e}")
            
            executor_prompt = build_executor_prompt(
                intent=intent,
                last_eval_report_path=last_eval_report_path,
                exec_spec=exec_spec,
                round_num=round_num,
                proposal_output_path=proposal_output_path,
                history_runs_hint=history_runs_hint,
                abstract_eval_summary=abstract_summary,
            )
            logger.info("Running executor...")

            # 记录 prompt
            _log_prompt(log_paths["prompt"], "EXECUTOR", executor_prompt)

            # 流式输出（带定时保存）
            executor_stream = StreamOutput(
                log_path=log_paths["executor"],
                max_lines=stream_max_lines,
            )
            
            def executor_callback(chunk: str) -> None:
                executor_stream.write(chunk)
                maybe_save_timing()
            
            print(f"[{time.strftime('%H:%M:%S')}] 📝 Executor running...")
            logger.debug("Calling executor driver, prompt_len=%d", len(executor_prompt))
            try:
                executor_output = executor_driver.run(
                    prompt=executor_prompt,
                    workdir=workdir,
                    stream_callback=executor_callback,
                )
                logger.debug("executor driver completed, output_len=%d", len(executor_output))
            except Exception as e:
                logger.error("driver failed: stage=executor, round=%d, run_id=%s: %s", round_num, run_id, e)
                raise
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
                duration=0.0,
            )

            # git commit after executor
            if enable_git_commit:
                auto_commit_after_execution(project_root, run_id)

        # ③ Evaluator（可跳过）
        if skip_evaluator and round_num == start_round_num:
            print(f"[{time.strftime('%H:%M:%S')}] ⏭️ Evaluator skipped (resume mode)")
        else:
            solution_dir = str(project_root / "task" / "solution")
            
            # 预先计算报告路径并创建目录，让 Evaluator 直接写入
            report_path = run_dir / "eval-report" / "report.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            evaluator_prompt = build_evaluator_prompt(
                solution_dir, 
                eval_skill,
                str(report_path),
            )
            logger.info("Running evaluator...")

            _log_prompt(log_paths["prompt"], "EVALUATOR", evaluator_prompt)

            evaluator_stream = StreamOutput(
                log_path=log_paths["evaluator"],
                max_lines=stream_max_lines,
            )
            
            def evaluator_callback(chunk: str) -> None:
                evaluator_stream.write(chunk)
                maybe_save_timing()
            
            print(f"[{time.strftime('%H:%M:%S')}] 🔍 Evaluator running...")
            logger.debug("Calling evaluator driver, prompt_len=%d", len(evaluator_prompt))
            try:
                eval_output = evaluator_driver.run(
                    prompt=evaluator_prompt,
                    workdir=workdir,
                    stream_callback=evaluator_callback,
                )
                logger.debug("evaluator driver completed, output_len=%d", len(eval_output))
            except Exception as e:
                logger.error("driver failed: stage=evaluator, round=%d, run_id=%s: %s", round_num, run_id, e)
                raise
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

            # 检查 Evaluator 是否已将报告写入指定文件
            if not report_path.exists():
                raise EvaluatorReportNotFoundError(
                    f"Evaluator did not write report to {report_path}"
                )
            # 记录报告路径，供下一轮执行器使用
            last_eval_report_path = report_path

        # 恢复标志只在第一轮生效
        skip_executor = False
        skip_evaluator = False

        # ④ Checker
        checker_result_path = run_dir / "checker-result" / "result.md"
        checker_result_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_path = run_dir / "eval-report" / "report.md"

        checker_prompt = build_checker_prompt(str(report_path), str(checker_result_path))
        logger.info("Running checker...")

        _log_prompt(log_paths["prompt"], "CHECKER", checker_prompt)

        checker_stream = StreamOutput(
            log_path=log_paths["checker"],
            max_lines=stream_max_lines,
        )
        
        def checker_callback(chunk: str) -> None:
            checker_stream.write(chunk)
            maybe_save_timing()
        
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Checker running...")
        logger.debug("Calling checker driver, prompt_len=%d", len(checker_prompt))
        try:
            checker_output = checker_driver.run(
                prompt=checker_prompt,
                workdir=workdir,
                stream_callback=checker_callback,
            )
            logger.debug("checker driver completed, output_len=%d", len(checker_output))
        except Exception as e:
            logger.error("driver failed: stage=checker, round=%d, run_id=%s: %s", round_num, run_id, e)
            raise
        checker_stream.finalize()

        # 从文件读取 checker 结果
        if not checker_result_path.exists():
            raise CheckerResultNotFoundError(
                f"Checker did not write result to {checker_result_path}"
            )
        checker_result = checker_result_path.read_text()
        passed = parse_checker_result(checker_result)
        explanation = extract_checker_explanation(checker_result)

        log_driver_call(
            log_path=log_paths["driver"],
            command=["checker", "agent"],
            workdir=workdir,
            prompt=checker_prompt,
            output=checker_result,
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
            # 保存计时数据
            session_elapsed = time.time() - session_start_time
            final_timing = end_session(project_root, session_elapsed)
            total_time_str = format_elapsed_verbose(final_timing.total_elapsed_seconds)
            print(f"[{time.strftime('%H:%M:%S')}] ⏱️  总耗时: {total_time_str}")
            
            # 读取最后的评估报告内容
            last_report_content = None
            if last_eval_report_path and last_eval_report_path.exists():
                last_report_content = last_eval_report_path.read_text(encoding="utf-8")
            return LoopResult(
                success=True,
                rounds=round_num,
                run_ids=run_ids,
                last_eval_report=last_report_content,
            )

    # 保存计时数据（失败情况）
    session_elapsed = time.time() - session_start_time
    final_timing = end_session(project_root, session_elapsed)
    total_time_str = format_elapsed_verbose(final_timing.total_elapsed_seconds)
    print(f"[{time.strftime('%H:%M:%S')}] ⏱️  总耗时: {total_time_str}")
    
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
