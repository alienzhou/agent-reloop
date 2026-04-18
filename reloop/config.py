"""Reloop 配置管理。

从项目根目录的 reloop.yaml 文件加载配置。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ReloopConfig:
    """Reloop 配置管理类。"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """初始化配置。

        Args:
            config_path: 配置文件路径，默认为当前目录下的 reloop.yaml
        """
        self.config_path = config_path or Path.cwd() / "reloop.yaml"
        self._config: Dict[str, Any] = {}
        if self.config_path.exists():
            self._load()

    def _load(self) -> None:
        """从文件加载配置。"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

    @property
    def driver_type(self) -> str:
        """获取 driver 类型。"""
        return self._config.get("driver", {}).get("type", "mock")

    @property
    def driver_config(self) -> Dict[str, Any]:
        """获取完整 driver 配置。"""
        return self._config.get("driver", {})

    def get_flick_config(self) -> Dict[str, Any]:
        """获取 FlickDriver 专用配置。"""
        return self._config.get("driver", {}).get("flick", {})

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值。

        Args:
            key: 配置键，支持点号分隔的嵌套路径
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value


def load_config(config_path: Optional[Path] = None) -> ReloopConfig:
    """加载配置的便捷函数。

    Args:
        config_path: 配置文件路径

    Returns:
        ReloopConfig 实例
    """
    return ReloopConfig(config_path)
