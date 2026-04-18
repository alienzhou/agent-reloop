#!/usr/bin/env python3
"""Agent-Reloop Demo — 用 MockDriver 模拟一次完整的 3 轮迭代循环。

运行方式:
    python examples/demo_run.py

模拟场景:
    任务: 生成一个 word_count.py 脚本，统计文件中的单词数
    Round 1: executor 写了初版，但 L1 检查发现输出格式不对 → FAILED
    Round 2: executor 修了格式，但 L2 检查发现没处理空文件 → FAILED
    Round 3: executor 修了空文件处理 → ALL PASS
"""

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reloop.core.loop import run_loop
from reloop.drivers.mock import CallbackMockDriver


# ─── 颜色工具 ──────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[34m"


def header(text):
    print(f"\n{BOLD}{CYAN}{'═' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 60}{RESET}")


def step(icon, text):
    print(f"  {icon}  {text}")


def passed(text):
    print(f"  {GREEN}✓ {text}{RESET}")


def failed(text):
    print(f"  {RED}✗ {text}{RESET}")


def info(text):
    print(f"  {DIM}{text}{RESET}")


# ─── Fixture: 模拟 Agent 的行为 ──────────────────────────────

INTENT = textwrap.dedent("""\
    Build a Python script `word_count.py` that reads a text file and prints
    the total word count in the format: "Word count: <N>"
""")

EVAL_SKILL = textwrap.dedent("""\
    ## Evaluation Criteria

    ### L0 — Precondition
    - `task/solution/word_count.py` must exist

    ### L1 — Mechanical
    - Output format must be exactly: "Word count: <integer>"
    - Script must exit with code 0

    ### L2 — Quality
    - Must handle empty files gracefully (output "Word count: 0")
    - Must handle files with multiple whitespace correctly
""")


def make_executor_callback(round_num):
    """每轮 executor 写出不同版本的 solution"""

    def callback(prompt, workdir):
        solution_dir = Path(workdir) / "task" / "solution"
        solution_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir = None

        for line in prompt.split("\n"):
            if "artifacts" in line.lower() and "go in:" in line:
                artifacts_dir = line.split("go in:")[-1].strip()
                break

        if round_num == 1:
            # V1: 功能对，但输出格式不对
            (solution_dir / "word_count.py").write_text(textwrap.dedent("""\
                import sys
                with open(sys.argv[1]) as f:
                    words = f.read().split()
                print(f"Total words: {len(words)}")
            """))
            step("📝", f"{YELLOW}Executor (round 1): wrote word_count.py v1{RESET}")
            info('Output format: "Total words: N" (wrong format!)')

        elif round_num == 2:
            # V2: 修了格式，但空文件没处理好
            (solution_dir / "word_count.py").write_text(textwrap.dedent("""\
                import sys
                with open(sys.argv[1]) as f:
                    content = f.read()
                words = content.split()
                print(f"Word count: {len(words)}")
            """))
            step("📝", f"{YELLOW}Executor (round 2): fixed output format{RESET}")
            info('Output format: "Word count: N" (correct!)')
            info("But no explicit empty file handling...")

        elif round_num == 3:
            # V3: 全部修好
            (solution_dir / "word_count.py").write_text(textwrap.dedent("""\
                import sys

                def count_words(filepath):
                    with open(filepath) as f:
                        content = f.read()
                    if not content.strip():
                        return 0
                    return len(content.split())

                if __name__ == "__main__":
                    count = count_words(sys.argv[1])
                    print(f"Word count: {count}")
            """))
            step("📝", f"{GREEN}Executor (round 3): added empty file handling{RESET}")
            info("Handles empty files, correct format, clean code.")

        if artifacts_dir:
            Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
            (Path(artifacts_dir) / "execution_log.txt").write_text(
                f"Executor round {round_num} completed."
            )

    return callback


# 每轮 evaluator 的输出
EVAL_REPORTS = [
    # Round 1: L1 FAIL
    textwrap.dedent("""\
        ## Evaluation Report — Round 1

        ### L0: Precondition
        - [PASS] `task/solution/word_count.py` exists

        ### L1: Mechanical
        - [FAIL] Output format mismatch
          - Expected: "Word count: <N>"
          - Got:      "Total words: <N>"

        ### L2: Quality
        - [SKIPPED] (short-circuited by L1 failure)

        **Result: FAILED**
    """),
    # Round 2: L2 FAIL
    textwrap.dedent("""\
        ## Evaluation Report — Round 2

        ### L0: Precondition
        - [PASS] `task/solution/word_count.py` exists

        ### L1: Mechanical
        - [PASS] Output format matches "Word count: <N>"
        - [PASS] Exit code 0

        ### L2: Quality
        - [FAIL] Empty file handling
          - Script works but does not explicitly handle the empty case
          - No guard clause for empty/whitespace-only input

        **Result: FAILED**
    """),
    # Round 3: ALL PASS
    textwrap.dedent("""\
        ## Evaluation Report — Round 3

        ### L0: Precondition
        - [PASS] `task/solution/word_count.py` exists

        ### L1: Mechanical
        - [PASS] Output format matches "Word count: <N>"
        - [PASS] Exit code 0

        ### L2: Quality
        - [PASS] Empty file returns "Word count: 0"
        - [PASS] Multi-whitespace handled correctly
        - [PASS] Clean, readable code structure

        **Result: PASSED**
    """),
]

CHECKER_OUTPUTS = ["failed", "failed", "passed"]


def make_evaluator_callback(round_num):
    def callback(prompt, workdir):
        step("🔍", f"{BLUE}Evaluator (round {round_num}): running L0 → L1 → L2...{RESET}")
        report = EVAL_REPORTS[round_num - 1]
        for line in report.strip().split("\n"):
            line = line.strip()
            if "[PASS]" in line:
                passed(line.replace("- [PASS]", "").strip())
            elif "[FAIL]" in line:
                failed(line.replace("- [FAIL]", "").strip())
            elif "[SKIPPED]" in line:
                info(line.replace("- [SKIPPED]", "SKIPPED:").strip())
    return callback


def make_checker_callback(round_num):
    def callback(prompt, workdir):
        result = CHECKER_OUTPUTS[round_num - 1]
        if result == "passed":
            step("✅", f"{GREEN}Checker (round {round_num}): PASSED{RESET}")
        else:
            step("❌", f"{RED}Checker (round {round_num}): FAILED → back to executor{RESET}")
    return callback


def main():
    header("Agent-Reloop Demo")
    print(f"""
  {BOLD}Task:{RESET}  Build word_count.py
  {BOLD}Eval:{RESET}  L0 (file exists) → L1 (format) → L2 (quality)
  {BOLD}Scenario:{RESET} 3 rounds: format bug → quality bug → all pass
""")

    # 准备临时项目目录
    demo_dir = Path(__file__).resolve().parent / "_demo_workspace"
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()

    # 初始化 git repo
    subprocess.run(["git", "init"], cwd=str(demo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "demo@reloop.dev"],
        cwd=str(demo_dir), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Reloop Demo"],
        cwd=str(demo_dir), capture_output=True, check=True,
    )
    (demo_dir / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=str(demo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init demo"],
        cwd=str(demo_dir), capture_output=True, check=True,
    )

    # 写入 INTENT
    intent_dir = demo_dir / "task"
    intent_dir.mkdir(parents=True, exist_ok=True)
    (intent_dir / "INTENT.md").write_text(INTENT)

    # 构造 MockDriver — 3 轮 × 3 步 = 9 次调用
    round_counter = [0]

    def next_round():
        round_counter[0] += 1
        return round_counter[0]

    responses = []
    callbacks = []
    for r in range(1, 4):
        # executor
        responses.append(f"Executor round {r} done.")
        callbacks.append(make_executor_callback(r))
        # evaluator
        responses.append(EVAL_REPORTS[r - 1])
        callbacks.append(make_evaluator_callback(r))
        # checker
        responses.append(CHECKER_OUTPUTS[r - 1])
        callbacks.append(make_checker_callback(r))

    driver = CallbackMockDriver(responses=responses, callbacks=callbacks)

    # ─── 运行主循环 ──────────────────────────────────────
    for r in range(1, 4):
        header(f"Round {r}")

    # 重置——实际是由 run_loop 驱动
    # 上面只是预览标题，实际用 run_loop 跑

    # 重建 driver
    driver = CallbackMockDriver(
        responses=[
            f"Executor round 1 done.", EVAL_REPORTS[0], CHECKER_OUTPUTS[0],
            f"Executor round 2 done.", EVAL_REPORTS[1], CHECKER_OUTPUTS[1],
            f"Executor round 3 done.", EVAL_REPORTS[2], CHECKER_OUTPUTS[2],
        ],
        callbacks=[
            make_executor_callback(1), make_evaluator_callback(1), make_checker_callback(1),
            make_executor_callback(2), make_evaluator_callback(2), make_checker_callback(2),
            make_executor_callback(3), make_evaluator_callback(3), make_checker_callback(3),
        ],
    )

    # 清掉预览输出
    import os
    os.system("clear" if os.name != "nt" else "cls")

    header("Agent-Reloop Demo")
    print(f"""
  {BOLD}Task:{RESET}    Build word_count.py (count words in a file)
  {BOLD}Eval:{RESET}    L0 (file exists) → L1 (output format) → L2 (edge cases)
  {BOLD}Driver:{RESET}  MockDriver (3 rounds scripted)
  {BOLD}Workdir:{RESET} {demo_dir}
""")

    input(f"  {DIM}Press Enter to start the loop...{RESET}")

    result = run_loop(
        project_root=demo_dir,
        intent=INTENT,
        eval_skill=EVAL_SKILL,
        executor_driver=driver,
        max_iterations=5,
        enable_git_commit=True,
    )

    # ─── 结果摘要 ──────────────────────────────────────
    header("Result")
    print(f"""
  {BOLD}Status:{RESET}  {GREEN}SUCCESS{RESET}
  {BOLD}Rounds:{RESET}  {result.rounds}
  {BOLD}Run IDs:{RESET} {', '.join(result.run_ids)}
""")

    # 展示最终 solution
    solution_file = demo_dir / "task" / "solution" / "word_count.py"
    if solution_file.exists():
        header("Final Solution")
        print(f"  {DIM}{solution_file}{RESET}\n")
        for i, line in enumerate(solution_file.read_text().splitlines(), 1):
            print(f"  {DIM}{i:3d}{RESET} │ {line}")
        print()

    # 展示目录结构
    header("Directory Layout")
    for p in sorted(demo_dir.rglob("*")):
        if ".git" in str(p) and ".gitkeep" not in str(p):
            continue
        rel = p.relative_to(demo_dir)
        depth = len(rel.parts) - 1
        indent = "  │   " * depth
        icon = "📁" if p.is_dir() else "📄"
        print(f"  {indent}{icon} {p.name}")
    print()

    # 展示 git log
    header("Git History")
    git_log = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        cwd=str(demo_dir), capture_output=True, text=True, check=True,
    )
    for line in git_log.stdout.strip().splitlines():
        hash_part, msg = line.split(" ", 1)
        print(f"  {DIM}{hash_part}{RESET}  {msg}")
    print()

    # 展示每轮的 eval report
    header("Evaluation Reports")
    for run_id in result.run_ids:
        report_file = demo_dir / "run-sets" / run_id / "eval-report" / "report.md"
        if report_file.exists():
            print(f"\n  {BOLD}── {run_id} ──{RESET}")
            for line in report_file.read_text().strip().splitlines():
                line_s = line.strip()
                if "[PASS]" in line_s:
                    print(f"  {GREEN}  {line_s}{RESET}")
                elif "[FAIL]" in line_s:
                    print(f"  {RED}  {line_s}{RESET}")
                elif "PASSED" in line_s:
                    print(f"  {GREEN}{BOLD}  {line_s}{RESET}")
                elif "FAILED" in line_s:
                    print(f"  {RED}{BOLD}  {line_s}{RESET}")
                else:
                    print(f"  {DIM}  {line_s}{RESET}")
    print()

    print(f"  {GREEN}{BOLD}Demo complete!{RESET}")
    print(f"  {DIM}Workspace at: {demo_dir}{RESET}")
    print(f"  {DIM}Run 'rm -rf {demo_dir}' to clean up.{RESET}\n")


if __name__ == "__main__":
    main()
