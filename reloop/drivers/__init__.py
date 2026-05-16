from reloop.drivers.base import Driver
from reloop.drivers.codex import CodexDriver, CodexDriverError
from reloop.drivers.flick import FlickDriver, FlickDriverError
from reloop.drivers.mock import CallbackMockDriver, MockDriver

__all__ = [
    "Driver",
    "MockDriver",
    "CallbackMockDriver",
    "FlickDriver",
    "FlickDriverError",
    "CodexDriver",
    "CodexDriverError",
    "create_driver",
    "create_driver_from_type",
]


def create_driver_from_type(driver_type: str, cfg: "ReloopConfig") -> Driver:
    """根据 driver 类型名和配置创建 Driver 实例。

    Args:
        driver_type: driver 类型字符串（mock / flick / codex）
        cfg:         ReloopConfig 配置实例

    Returns:
        Driver 实例

    Raises:
        ValueError: 未知的 driver 类型
    """
    if driver_type == "mock":
        return MockDriver(responses=["done"])
    elif driver_type == "flick":
        flick_cfg = cfg.get_flick_config()
        return FlickDriver(
            workspace=flick_cfg.get("workspace"),
            model=flick_cfg.get("model"),
            mode=flick_cfg.get("mode"),
            json_output=flick_cfg.get("json_output", True),
        )
    elif driver_type == "codex":
        codex_cfg = cfg.get_codex_config()
        return CodexDriver(
            model=codex_cfg.get("model"),
            sandbox=codex_cfg.get("sandbox"),
            approval=codex_cfg.get("approval"),
        )
    else:
        raise ValueError(f"未知的 driver 类型: {driver_type}")


def create_driver(cfg: "ReloopConfig") -> Driver:
    """根据配置创建默认 Driver 实例（executor driver）。

    Args:
        cfg: ReloopConfig 配置实例

    Returns:
        Driver 实例

    Raises:
        ValueError: 未知的 driver 类型
    """
    return create_driver_from_type(cfg.driver_type, cfg)


def create_executor_driver(cfg: "ReloopConfig") -> Driver:
    """创建 executor Driver 实例。

    优先使用 driver.executor.type，若未配置则回退到 driver.type。

    Args:
        cfg: ReloopConfig 配置实例

    Returns:
        Driver 实例
    """
    executor_type = cfg.executor_driver_type
    return create_driver_from_type(executor_type, cfg)


def create_evaluator_driver(cfg: "ReloopConfig") -> Driver:
    """创建 evaluator Driver 实例。

    优先使用 driver.evaluator.type，若未配置则回退到 driver.type。

    Args:
        cfg: ReloopConfig 配置实例

    Returns:
        Driver 实例
    """
    evaluator_type = cfg.evaluator_driver_type
    return create_driver_from_type(evaluator_type, cfg)
