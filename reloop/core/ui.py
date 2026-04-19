"""Reloop Live UI — 使用 Rich 实现分区终端界面。

提供：
- ReloopLiveUI: 分区终端界面，上部状态面板 + 下部滚动日志
- StreamPanel: 滚动日志面板
"""

from __future__ import annotations

import logging
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Generator, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """阶段状态。"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Stage:
    """迭代阶段。"""
    name: str
    icon: str
    status: StageStatus = StageStatus.PENDING
    
    @property
    def display(self) -> Text:
        """返回显示文本。"""
        status_icons = {
            StageStatus.PENDING: ("⏳", "dim"),
            StageStatus.RUNNING: ("🔄", "yellow"),
            StageStatus.DONE: ("✅", "green"),
            StageStatus.FAILED: ("❌", "red"),
            StageStatus.SKIPPED: ("⏭️", "cyan"),
        }
        icon, style = status_icons[self.status]
        return Text(f"{icon} {self.name}", style=style)


@dataclass 
class RoundState:
    """单轮迭代状态。"""
    round_num: int
    max_rounds: int
    run_id: str = ""
    stages: list[Stage] = field(default_factory=list)
    result: Optional[str] = None  # "PASSED" / "FAILED" / None
    
    def __post_init__(self) -> None:
        if not self.stages:
            self.stages = [
                Stage("Executor", "📝"),
                Stage("Evaluator", "🔍"),
                Stage("Checker", "✅"),
            ]


class StreamPanel:
    """滚动日志面板。"""
    
    def __init__(self, max_lines: int = 20, title: str = "Output") -> None:
        self.max_lines = max_lines
        self.title = title
        self.lines: deque[str] = deque(maxlen=max_lines)
        self._current_stage = ""
    
    def set_stage(self, stage: str) -> None:
        """设置当前阶段标题。"""
        self._current_stage = stage
        self.title = f"Output - {stage}"
    
    def append(self, line: str) -> None:
        """添加一行日志。"""
        timestamp = time.strftime("%H:%M:%S")
        # 转义用户输入，防止 Rich markup 解析错误
        safe_line = escape(line)
        self.lines.append(f"[dim]{timestamp}[/dim] {safe_line}")
    
    def clear(self) -> None:
        """清空日志。"""
        self.lines.clear()
    
    def render(self) -> Panel:
        """渲染面板（带容错）。"""
        try:
            content = "\n".join(self.lines) if self.lines else "[dim]Waiting for output...[/dim]"
            return Panel(
                content,
                title=f"[bold]{self.title}[/bold]",
                border_style="blue",
                height=self.max_lines + 2,
            )
        except Exception as e:
            logger.warning(f"StreamPanel render error: {e}")
            # 返回安全的备用面板
            return Panel(
                "[dim]Render error - check logs[/dim]",
                title="Output",
                border_style="yellow",
                height=self.max_lines + 2,
            )


class ReloopLiveUI:
    """Reloop Live 终端界面。
    
    使用 Rich Live 实现分区显示：
    - 上部：固定状态面板（Round 进度、阶段状态）
    - 下部：滚动输出日志
    """
    
    # 计时数据保存间隔（秒）
    TIMING_SAVE_INTERVAL: float = 30.0
    
    def __init__(
        self,
        max_output_lines: int = 15,
        console: Optional[Console] = None,
        accumulated_time: float = 0.0,
        project_root: Optional[Path] = None,
    ) -> None:
        """初始化 Live UI。
        
        Args:
            max_output_lines: 输出面板最大行数
            console: 可选的 Console 实例
            accumulated_time: 累计时间（秒），用于 resume 场景
            project_root: 项目根目录，用于定时保存计时数据
        """
        self.console = console or Console()
        self.stream_panel = StreamPanel(max_lines=max_output_lines)
        self.state: Optional[RoundState] = None
        self._live: Optional[Live] = None
        self._start_time: float = 0
        self._accumulated_time: float = accumulated_time
        self._history: list[tuple[int, str]] = []  # (round_num, result)
        self._project_root: Optional[Path] = project_root
        self._last_timing_save: float = 0  # 上次保存计时的时间
    
    def _build_status_panel(self) -> Panel:
        """构建状态面板（带容错）。"""
        try:
            if not self.state:
                return Panel("[dim]Initializing...[/dim]", title="Status")
            
            # 创建状态表格
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Key", style="bold")
            table.add_column("Value")
            
            # Round 信息
            session_elapsed = time.time() - self._start_time
            total_elapsed = self._accumulated_time + session_elapsed
            
            # 格式化时间显示
            hours = int(total_elapsed // 3600)
            minutes = int((total_elapsed % 3600) // 60)
            secs = int(total_elapsed % 60)
            if hours > 0:
                elapsed_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                elapsed_str = f"{minutes:02d}:{secs:02d}"
            
            # 如果有累计时间，显示额外信息
            if self._accumulated_time > 0:
                elapsed_str += f" [dim](+{int(self._accumulated_time)}s 累计)[/dim]"
            
            table.add_row("Round", f"[bold cyan]{self.state.round_num}[/] / {self.state.max_rounds}")
            table.add_row("Run ID", f"[dim]{self.state.run_id}[/dim]")
            table.add_row("Elapsed", f"[yellow]{elapsed_str}[/yellow]")
            
            # 阶段状态（水平排列）
            stages_text = Text()
            for i, stage in enumerate(self.state.stages):
                if i > 0:
                    stages_text.append(" → ", style="dim")
                stages_text.append_text(stage.display)
            
            table.add_row("Stages", stages_text)
            
            # 历史结果
            if self._history:
                history_text = Text()
                for i, (rnd, result) in enumerate(self._history[-5:]):  # 最近5轮
                    if i > 0:
                        history_text.append(" | ", style="dim")
                    color = "green" if result == "PASSED" else "red"
                    history_text.append(f"R{rnd}:{result}", style=color)
                table.add_row("History", history_text)
            
            # 当前结果
            if self.state.result:
                color = "green bold" if self.state.result == "PASSED" else "red bold"
                table.add_row("Result", Text(self.state.result, style=color))
            
            return Panel(table, title="[bold]🔄 Reloop Status[/bold]", border_style="cyan")
        except Exception as e:
            logger.warning(f"_build_status_panel error: {e}")
            return Panel("[dim]Status unavailable[/dim]", title="Status", border_style="yellow")
    
    def _build_layout(self) -> Group:
        """构建完整布局（带容错）。"""
        try:
            return Group(
                self._build_status_panel(),
                self.stream_panel.render(),
            )
        except Exception as e:
            logger.warning(f"_build_layout error: {e}")
            # 返回空布局
            return Group(Panel("[dim]Layout error[/dim]", title="Error"))
    
    @contextmanager
    def live_context(self) -> Generator[None, None, None]:
        """进入 Live 模式的上下文管理器。"""
        self._start_time = time.time()
        with Live(
            self._build_layout(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        ) as live:
            self._live = live
            try:
                yield
            finally:
                self._live = None
    
    def get_session_elapsed(self) -> float:
        """获取当前会话已用时间（秒）。"""
        if self._start_time > 0:
            return time.time() - self._start_time
        return 0.0
    
    def get_total_elapsed(self) -> float:
        """获取总已用时间（累计 + 当前会话）。"""
        return self._accumulated_time + self.get_session_elapsed()
    
    def refresh(self) -> None:
        """刷新显示（带容错）。"""
        if self._live:
            try:
                self._live.update(self._build_layout())
                # 检查是否需要保存计时数据
                self._maybe_save_timing()
            except Exception as e:
                logger.warning(f"UI refresh error: {e}")
    
    def _maybe_save_timing(self) -> None:
        """检查并保存计时数据（每 30 秒保存一次）。
        
        确保即使程序异常退出，计时数据也不会丢失太多（最多丢失 30 秒）。
        """
        if not self._project_root:
            return
        
        now = time.time()
        if now - self._last_timing_save < self.TIMING_SAVE_INTERVAL:
            return
        
        try:
            from reloop.core.timing import load_timing, save_timing
            
            session_elapsed = self.get_session_elapsed()
            timing = load_timing(self._project_root)
            timing.total_elapsed_seconds = self._accumulated_time + session_elapsed
            save_timing(self._project_root, timing)
            self._last_timing_save = now
            logger.debug(f"Timing saved: {timing.total_elapsed_seconds:.1f}s")
        except Exception as e:
            logger.warning(f"Failed to save timing: {e}")
    
    def start_round(self, round_num: int, max_rounds: int, run_id: str = "") -> None:
        """开始新一轮迭代。"""
        self.state = RoundState(round_num=round_num, max_rounds=max_rounds, run_id=run_id)
        self.stream_panel.clear()
        self.refresh()
    
    def set_stage(self, stage_name: str, status: StageStatus = StageStatus.RUNNING) -> None:
        """设置阶段状态。"""
        if not self.state:
            return
        
        for stage in self.state.stages:
            if stage.name == stage_name:
                stage.status = status
                break
        
        self.stream_panel.set_stage(stage_name)
        self.refresh()
    
    def complete_stage(self, stage_name: str, success: bool = True, skipped: bool = False) -> None:
        """完成阶段。"""
        if skipped:
            status = StageStatus.SKIPPED
        else:
            status = StageStatus.DONE if success else StageStatus.FAILED
        self.set_stage(stage_name, status)
    
    def end_round(self, passed: bool) -> None:
        """结束当前轮次。"""
        if self.state:
            result = "PASSED" if passed else "FAILED"
            self.state.result = result
            self._history.append((self.state.round_num, result))
        self.refresh()
    
    def write_output(self, line: str) -> None:
        """写入输出日志（带容错）。"""
        try:
            self.stream_panel.append(line)
            self.refresh()
        except Exception as e:
            logger.warning(f"UI write_output error: {e}")
    
    def get_stream_callback(self) -> Callable[[str], None]:
        """返回流式输出回调函数。"""
        def callback(chunk: str) -> None:
            # 处理可能的多行输出
            for line in chunk.split("\n"):
                if line.strip():
                    self.write_output(line)
        return callback
    
    def print_final_summary(self, success: bool, rounds: int, run_ids: list[str]) -> None:
        """打印最终摘要。"""
        self.console.print()
        
        if success:
            self.console.print(Panel(
                f"[bold green]✅ 迭代成功！[/bold green]\n\n"
                f"总轮数: [cyan]{rounds}[/cyan]\n"
                f"Runs: [dim]{', '.join(run_ids)}[/dim]",
                title="[bold]🎉 Complete[/bold]",
                border_style="green",
            ))
        else:
            self.console.print(Panel(
                f"[bold red]❌ 迭代失败[/bold red]\n\n"
                f"已执行轮数: [cyan]{rounds}[/cyan]\n"
                f"Runs: [dim]{', '.join(run_ids)}[/dim]",
                title="[bold]Failed[/bold]",
                border_style="red",
            ))
    
    def print_log_paths(self, run_id: str, log_paths: dict[str, Path]) -> None:
        """打印日志路径提示。"""
        table = Table(title=f"📄 Logs for {run_id}", show_header=False, box=None)
        table.add_column("Type", style="bold")
        table.add_column("Path", style="dim")
        
        for name, path in log_paths.items():
            table.add_row(name.capitalize(), str(path))
        
        self.console.print(table)
        self.console.print()
