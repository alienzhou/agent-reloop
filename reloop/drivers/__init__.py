from reloop.drivers.base import Driver
from reloop.drivers.flick import FlickDriver, FlickDriverError
from reloop.drivers.mock import CallbackMockDriver, MockDriver

__all__ = [
    "Driver",
    "MockDriver",
    "CallbackMockDriver",
    "FlickDriver",
    "FlickDriverError",
    "create_driver",
]


def create_driver(cfg: "ReloopConfig") -> Driver:
    """根据配置创建 Driver 实例。

    Args:
        cfg: ReloopConfig 配置实例

    Returns:
        Driver 实例

    Raises:
        ValueError: 未知的 driver 类型
    """
    driver_type = cfg.driver_type

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
    else:
        raise ValueError(f"未知的 driver 类型: {driver_type}")
