"""gimbal_plate.registry —— 服务/接口注册与查询 facade。

第一期最小可用 API:
    - ``register_service(service)``              注册服务定义
    - ``register_endpoint(endpoint)``            注册接口定义
    - ``list_services() -> list[ServiceDefinition]``
    - ``list_endpoints(service=None) -> list[EndpointSpec]``
    - ``get_endpoint(endpoint_id) -> EndpointSpec``
    - ``reset()``                                清空注册(便于测试)

后续阶段将补:
    - 线程安全
    - 懒加载
    - checksum 失效
    - 远程同步
"""
from gimbal_plate.registry.registry import (
    ServiceRegistry,
    registry as default_registry,
    register_service,
    register_endpoint,
    list_services,
    list_endpoints,
    get_endpoint,
    reset,
)

__all__ = [
    "ServiceRegistry",
    "registry",
    "register_service",
    "register_endpoint",
    "list_services",
    "list_endpoints",
    "get_endpoint",
    "reset",
]
