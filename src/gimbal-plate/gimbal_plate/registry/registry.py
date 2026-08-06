"""PlateRegistry:被测接口的多维度内存注册表。"""
from __future__ import annotations

from typing import Iterable

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.service_definition import ServiceDefinition

from .index import _Index


class PlateRegistry:
    """服务与接口的多维度内存注册表。

    一期职责:
        - 注册 ServiceDefinition / EndpointSpec
        - 多维度查询:by_id / by_system / by_service / by_tag / by_route
        - reset() 便于测试

    一期不做:
        - 线程安全 / 异步
        - 持久化
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceDefinition] = {}
        self._index = _Index()

    # ── 注册 ──────────────────────────────────────────────────
    def register_service(self, service: ServiceDefinition) -> None:
        if not service.name:
            raise ValueError("ServiceDefinition.name 不可为空")
        if service.name in self._services:
            raise ValueError(f"Service '{service.name}' 已注册")
        self._services[service.name] = service

    def register_endpoint(self, endpoint: EndpointSpec) -> None:
        if endpoint.id in self._index.by_id:
            raise ValueError(f"Endpoint '{endpoint.id}' 已注册")
        # 一致性:service 不在已注册服务中时,自动注册一个最小 ServiceDefinition
        if endpoint.service not in self._services:
            self._services[endpoint.service] = ServiceDefinition(
                name=endpoint.service,
                title=endpoint.service,
            )
        self._index.add(endpoint)

    def register_endpoints(self, endpoints: Iterable[EndpointSpec]) -> None:
        for ep in endpoints:
            self.register_endpoint(ep)

    # ── 查询 ──────────────────────────────────────────────────
    def list_systems(self) -> list[str]:
        seen: set[str] = set()
        for ep in self._index.by_id.values():
            seen.add(ep.system)
        return sorted(seen)

    def list_services(self, system: str | None = None) -> list[ServiceDefinition]:
        if system is None:
            return list(self._services.values())
        svc_names = self._services_for_system(system)
        return [s for s in self._services.values() if s.name in svc_names]

    def list_endpoints(
        self,
        *,
        system: str | None = None,
        service: str | None = None,
        tag: str | None = None,
    ) -> list[EndpointSpec]:
        ids: set[str] | None = None
        if system is not None:
            ids = {ep.id for ep in self._index.by_id.values() if ep.system == system}
        if service is not None:
            sv = set(self._index.by_service.get(service, set()))
            ids = sv if ids is None else ids & sv
        if tag is not None:
            tv = set(self._index.by_tag.get(tag, set()))
            ids = tv if ids is None else ids & tv
        if ids is None:
            return list(self._index.by_id.values())
        return [self._index.by_id[eid] for eid in sorted(ids)]

    def get_endpoint(self, endpoint_id: str) -> EndpointSpec:
        ep = self._index.by_id.get(endpoint_id)
        if ep is None:
            raise KeyError(f"Endpoint '{endpoint_id}' 未注册")
        return ep

    def find_endpoints(self, service: str, method: str, path: str) -> list[EndpointSpec]:
        ep_id = self._index.by_route.get((service, method, path))
        if ep_id is None:
            return []
        return [self._index.by_id[ep_id]]

    def has_endpoint(self, endpoint_id: str) -> bool:
        return endpoint_id in self._index.by_id

    # ── 内部辅助 ──────────────────────────────────────────────
    def _services_for_system(self, system: str) -> set[str]:
        return {ep.service for ep in self._index.by_id.values() if ep.system == system}

    # ── 测试支持 ──────────────────────────────────────────────
    def reset(self) -> None:
        self._services.clear()
        self._index.clear()


# 全局默认注册表
registry = PlateRegistry()


def register_service(service: ServiceDefinition) -> None:
    registry.register_service(service)


def register_endpoint(endpoint: EndpointSpec) -> None:
    registry.register_endpoint(endpoint)


def list_systems() -> list[str]:
    return registry.list_systems()


def list_services(system: str | None = None) -> list[ServiceDefinition]:
    return registry.list_services(system=system)


def list_endpoints(
    system: str | None = None,
    service: str | None = None,
    tag: str | None = None,
) -> list[EndpointSpec]:
    return registry.list_endpoints(system=system, service=service, tag=tag)


def get_endpoint(endpoint_id: str) -> EndpointSpec:
    return registry.get_endpoint(endpoint_id)


def find_endpoints(service: str, method: str, path: str) -> list[EndpointSpec]:
    return registry.find_endpoints(service, method, path)


def reset() -> None:
    registry.reset()
