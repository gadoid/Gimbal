"""gimbal_plate.registry.registry —— 内存版服务/接口注册表(最小可用实现)。"""
from __future__ import annotations

from typing import Iterable

from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.service.service import ServiceDefinition


class ServiceRegistry:
    """服务与接口的内存注册表。

    第一期不实现线程安全、懒加载、checksum 校验等;这些将在后续阶段补齐。
    当前职责:
        1. 接收 ``ServiceDefinition`` 与 ``EndpointSpec`` 的注册
        2. 提供按服务名/接口 ID 的查询
        3. 提供 ``reset()`` 便于测试
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceDefinition] = {}
        self._endpoints: dict[str, EndpointSpec] = {}

    # ── 注册 ────────────────────────────────────────────────
    def register_service(self, service: ServiceDefinition) -> None:
        if not service.name:
            raise ValueError("ServiceDefinition.name must be non-empty")
        if service.name in self._services:
            raise ValueError(f"Service '{service.name}' already registered")
        self._services[service.name] = service

    def register_endpoint(self, endpoint: EndpointSpec) -> None:
        if not endpoint.id:
            raise ValueError("EndpointSpec.id must be non-empty")
        if endpoint.id in self._endpoints:
            raise ValueError(f"Endpoint '{endpoint.id}' already registered")
        self._endpoints[endpoint.id] = endpoint

    def register_endpoints(self, endpoints: Iterable[EndpointSpec]) -> None:
        for ep in endpoints:
            self.register_endpoint(ep)

    # ── 查询 ────────────────────────────────────────────────
    def list_services(self) -> list[ServiceDefinition]:
        return list(self._services.values())

    def list_endpoints(self, service: str | None = None) -> list[EndpointSpec]:
        if service is None:
            return list(self._endpoints.values())
        return [ep for ep in self._endpoints.values() if ep.api.service == service]

    def get_endpoint(self, endpoint_id: str) -> EndpointSpec:
        try:
            return self._endpoints[endpoint_id]
        except KeyError as exc:
            raise KeyError(f"Endpoint '{endpoint_id}' not registered") from exc

    def has_endpoint(self, endpoint_id: str) -> bool:
        return endpoint_id in self._endpoints

    # ── 测试支持 ────────────────────────────────────────────
    def reset(self) -> None:
        self._services.clear()
        self._endpoints.clear()


# 全局默认注册表
registry = ServiceRegistry()


def register_service(service: ServiceDefinition) -> None:
    registry.register_service(service)


def register_endpoint(endpoint: EndpointSpec) -> None:
    registry.register_endpoint(endpoint)


def list_services() -> list[ServiceDefinition]:
    return registry.list_services()


def list_endpoints(service: str | None = None) -> list[EndpointSpec]:
    return registry.list_endpoints(service)


def get_endpoint(endpoint_id: str) -> EndpointSpec:
    return registry.get_endpoint(endpoint_id)


def reset() -> None:
    registry.reset()