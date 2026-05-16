"""Reloop 配置管理。

从项目根目录的 reloop.yaml 文件加载配置。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ReloopConfig:
    """Reloop 配置管理类。"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """初始化配置。

        Args:
            config_path: 配置文件路径，默认为当前目录下的 reloop.yaml
        """
        self.config_path = config_path or Path.cwd() / "reloop.yaml"
        self._config: Dict[str, Any] = {}
        logger.debug("Loading config from %s", self.config_path)
        if self.config_path.exists():
            self._load()
        else:
            logger.warning("Config not found, using defaults")

    def _load(self) -> None:
        """从文件加载配置。"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}
        logger.info("Config loaded")

    @property
    def driver_type(self) -> str:
        """获取默认 driver 类型（executor 的回退值）。"""
        return self._config.get("driver", {}).get("type", "mock")

    @property
    def executor_driver_type(self) -> str:
        """获取 executor driver 类型。

        优先读取 driver.executor.type，若未配置则回退到 driver.type。
        """
        executor_cfg = self._config.get("driver", {}).get("executor", {})
        if executor_cfg and executor_cfg.get("type"):
            return executor_cfg["type"]
        return self.driver_type

    @property
    def evaluator_driver_type(self) -> str:
        """获取 evaluator driver 类型。

        优先读取 driver.evaluator.type，若未配置则回退到 driver.type。
        """
        evaluator_cfg = self._config.get("driver", {}).get("evaluator", {})
        if evaluator_cfg and evaluator_cfg.get("type"):
            return evaluator_cfg["type"]
        return self.driver_type

    @property
    def driver_config(self) -> Dict[str, Any]:
        """获取完整 driver 配置。"""
        return self._config.get("driver", {})

    def get_flick_config(self) -> Dict[str, Any]:
        """获取 FlickDriver 专用配置。"""
        config = self._config.get("driver", {}).get("flick", {})
        logger.debug("Flick config: %s", config)
        return config

    def get_codex_config(self) -> Dict[str, Any]:
        """获取 CodexDriver 专用配置。"""
        config = self._config.get("driver", {}).get("codex", {})
        logger.debug("Codex config: %s", config)
        return config

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
                    logger.debug("Config get: %s=%s", key, default)
                    return default
            else:
                logger.debug("Config get: %s=%s", key, default)
                return default
        logger.debug("Config get: %s=%s", key, value)
        return value


def load_config(config_path: Optional[Path] = None) -> ReloopConfig:
    """加载配置的便捷函数。

    Args:
        config_path: 配置文件路径

    Returns:
        ReloopConfig 实例
    """
    return ReloopConfig(config_path)
