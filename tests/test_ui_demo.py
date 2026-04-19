#!/usr/bin/env python3
"""测试 Live UI 效果的脚本。"""

import time
from reloop.core.ui import ReloopLiveUI, StageStatus


def test_live_ui():
    """模拟 Reloop 运行过程，测试 Live UI 效果。"""
    ui = ReloopLiveUI(max_output_lines=12)
    
    with ui.live_context():
        for round_num in range(1, 4):
            # 开始新一轮
            ui.start_round(round_num, max_rounds=10, run_id=f"run-{round_num:03d}")
            time.sleep(0.5)
            
            # Executor
            ui.set_stage("Executor", StageStatus.RUNNING)
            for i in range(8):
                ui.write_output(f"[Executor] Processing step {i+1}...")
                time.sleep(0.2)
            ui.complete_stage("Executor")
            time.sleep(0.3)
            
            # Evaluator
            ui.set_stage("Evaluator", StageStatus.RUNNING)
            for i in range(5):
                ui.write_output(f"[Evaluator] Checking criterion L{i}...")
                time.sleep(0.15)
            ui.complete_stage("Evaluator")
            time.sleep(0.3)
            
            # Checker
            ui.set_stage("Checker", StageStatus.RUNNING)
            ui.write_output("[Checker] Parsing evaluation report...")
            time.sleep(0.3)
            
            # 模拟结果：第3轮通过
            passed = round_num == 3
            ui.complete_stage("Checker", success=passed)
            ui.end_round(passed)
            
            if passed:
                break
            
            time.sleep(0.5)
    
    # 打印最终摘要
    ui.print_final_summary(True, rounds=3, run_ids=["run-001", "run-002", "run-003"])


if __name__ == "__main__":
    test_live_ui()
