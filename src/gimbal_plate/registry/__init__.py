"""gimbal_plate.registry —— 被测接口的多维度内存注册表。"""
from gimbal_plate.registry.registry import (
    PlateRegistry,
    find_endpoints,
    get_endpoint,
    list_endpoints,
    list_services,
    list_systems,
    register_endpoint,
    register_service,
    registry,
    reset,
)

__all__ = [
    "PlateRegistry",
    "registry",
    "register_endpoint",
    "register_service",
    "list_systems",
    "list_services",
    "list_endpoints",
    "get_endpoint",
    "find_endpoints",
    "reset",
]
