"""计时模块 — 支持 resume 后累加计时。

提供：
- TimingData: 计时数据结构
- load_timing: 从文件加载计时数据
- save_timing: 保存计时数据到文件
- format_elapsed: 格式化已用时间
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 计时数据文件名
TIMING_FILE = "timing.json"


@dataclass
class TimingData:
    """计时数据。
    
    Attributes:
        total_elapsed_seconds: 总累计时间（秒）
        last_session_start: 上次会话开始时间戳（Unix timestamp）
        last_session_end: 上次会话结束时间戳（Unix timestamp）
        session_count: 会话次数
        last_updated: 最后更新时间（ISO 格式）
    """
    total_elapsed_seconds: float = 0.0
    last_session_start: Optional[float] = None
    last_session_end: Optional[float] = None
    session_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {
            "total_elapsed_seconds": self.total_elapsed_seconds,
            "last_session_start": self.last_session_start,
            "last_session_end": self.last_session_end,
            "session_count": self.session_count,
            "last_updated": self.last_updated,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TimingData":
        """从字典创建实例。"""
        return cls(
            total_elapsed_seconds=data.get("total_elapsed_seconds", 0.0),
            last_session_start=data.get("last_session_start"),
            last_session_end=data.get("last_session_end"),
            session_count=data.get("session_count", 0),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
        )


def get_timing_file_path(project_root: Path) -> Path:
    """获取计时文件路径。
    
    Args:
        project_root: 项目根目录
        
    Returns:
        计时文件路径 (run-sets/timing.json)
    """
    return project_root / "run-sets" / TIMING_FILE


def load_timing(project_root: Path) -> TimingData:
    """加载计时数据。
    
    Args:
        project_root: 项目根目录
        
    Returns:
        计时数据，如果文件不存在则返回空的 TimingData
    """
    timing_file = get_timing_file_path(project_root)
    logger.debug(f"Loading timing from {timing_file}")
    
    if not timing_file.exists():
        return TimingData()
    
    try:
        data = json.loads(timing_file.read_text(encoding="utf-8"))
        return TimingData.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        # 文件损坏，返回空数据
        return TimingData()


def save_timing(project_root: Path, timing: TimingData) -> None:
    """保存计时数据。
    
    Args:
        project_root: 项目根目录
        timing: 计时数据
    """
    timing_file = get_timing_file_path(project_root)
    timing_file.parent.mkdir(parents=True, exist_ok=True)
    
    timing.last_updated = datetime.now().isoformat()
    timing_file.write_text(
        json.dumps(timing.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    logger.debug(f"Saving timing: total={timing.total_elapsed_seconds:.1f}s")


def start_session(project_root: Path) -> TimingData:
    """开始新会话，返回更新后的计时数据。
    
    Args:
        project_root: 项目根目录
        
    Returns:
        更新后的计时数据（含累计时间）
    """
    logger.info("Starting timing session")
    timing = load_timing(project_root)
    timing.last_session_start = time.time()
    timing.session_count += 1
    save_timing(project_root, timing)
    return timing


def end_session(project_root: Path, session_elapsed: float) -> TimingData:
    """结束会话，更新累计时间。
    
    Args:
        project_root: 项目根目录
        session_elapsed: 本次会话耗时（秒）
        
    Returns:
        更新后的计时数据
    """
    timing = load_timing(project_root)
    timing.last_session_end = time.time()
    timing.total_elapsed_seconds += session_elapsed
    save_timing(project_root, timing)
    logger.info(f"Session ended: duration={session_elapsed:.1f}s")
    return timing


def reset_timing(project_root: Path) -> None:
    """重置计时数据。
    
    Args:
        project_root: 项目根目录
    """
    timing_file = get_timing_file_path(project_root)
    if timing_file.exists():
        timing_file.unlink()
    logger.info("Timing reset")


def format_elapsed(seconds: float) -> str:
    """格式化已用时间。
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串 (HH:MM:SS 或 MM:SS)
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_elapsed_verbose(seconds: float) -> str:
    """格式化已用时间（详细格式）。
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串 (例如 "1h 23m 45s" 或 "5m 30s")
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    
    return " ".join(parts)
