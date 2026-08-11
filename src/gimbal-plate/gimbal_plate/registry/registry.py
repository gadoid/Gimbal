"""PlateRegistry:被测接口的多维度内存注册表。"""
from __future__ import annotations

from typing import Any, Iterable

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.service_definition import ServiceDefinition

from .index import _Index


class PlateRegistry:
    """服务与接口的多维度内存注册表。

    一期职责:
        - 注册 ServiceDefinition / EndpointSpec
        - 多维度查询:by_id / by_system / by_service / by_tag / by_route
        - 按 dim 注册(ADR 0002 §D-D3):通过 ``register_dim(name, spec)``
          让 HTTP generic handler 通过 ``index_for(dim)`` 拿到 DimSpec。
        - reset() 便于测试

    一期不做:
        - 线程安全 / 异步
        - 持久化
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceDefinition] = {}
        self._index = _Index()
        # ADR 0002 §D-D3: dim registry. Keyed by dim name (e.g. "endpoint",
        # "config", "meta"). Each value is a DimSpec exposing the index, the
        # view factory, and the per-dim actions.
        self.dims: dict[str, Any] = {}

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

    # ── N2 cleanup (ADR 0002 §N2): service accessors ─
    #
    # Same rationale as the endpoint accessors above: ``ServiceIndex`` used
    # to reach into ``self.registry._services`` directly. These public
    # methods encapsulate the storage strategy so the index can stay
    # registry-agnostic.

    def iter_services_global(self) -> list[ServiceDefinition]:
        """Return every registered :class:`ServiceDefinition` (read-only)."""
        return list(self._services.values())

    def get_service(self, service_name: str) -> ServiceDefinition | None:
        """Return the service by name, or ``None`` if missing."""
        return self._services.get(service_name)

    def has_service(self, service_name: str) -> bool:
        """Whether a service with ``service_name`` is registered."""
        return service_name in self._services

    def iter_services_for_system(self, system: str) -> list[ServiceDefinition]:
        """Return every service whose endpoints all belong to ``system``.

        A service is "for system X" iff every endpoint registered with
        ``service == svc.name`` has ``ep.system == X``. This avoids
        leaking services that are cross-system (which is a misregistration
        we still want to surface, not silently hide).
        """
        names = {ep.service for ep in self.iter_endpoints_for_system(system)}
        return [s for s in self._services.values() if s.name in names]

    def list_endpoints(
        self,
        *,
        system: str | None = None,
        service: str | None = None,
        tag: str | None = None,
    ) -> list[EndpointSpec]:
        # NOTE (ADR 0002 §后果负面, Phase β transition): this convenience API
        # coexists with the dim-based ``dims["endpoint"].list_*`` surface.
        # Phase β will decide whether to keep both or unify. See
        # docs/adr/0002-plate-http-routing-grammar.md §后果负面 for the
        # documented rationale.
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
        # NOTE (ADR 0002 §后果负面): transitional — see list_endpoints note.
        ep = self._index.by_id.get(endpoint_id)
        if ep is None:
            raise KeyError(f"Endpoint '{endpoint_id}' 未注册")
        return ep

    def try_endpoint(self, endpoint_id: str) -> EndpointSpec | None:
        """Return the endpoint by id, or ``None`` if missing.

        Non-raising variant of :meth:`get_endpoint`. Used by index
        implementations that need to return ``None`` for a missing key
        without converting the lookup into an exception path.
        """
        return self._index.by_id.get(endpoint_id)

    def find_endpoints(self, service: str, method: str, path: str) -> list[EndpointSpec]:
        ep_id = self._index.by_route.get((service, method, path))
        if ep_id is None:
            return []
        return [self._index.by_id[ep_id]]

    def has_endpoint(self, endpoint_id: str) -> bool:
        return endpoint_id in self._index.by_id

    # ── N2 cleanup (ADR 0002 §N2): public API replacing private access ─
    #
    # ``EndpointIndex`` / ``ServiceIndex`` / ``SystemIndex`` / ``_resolve_system``
    # used to reach into ``_index.by_id.values()`` with ``# noqa: SLF001``.
    # Those accesses are now routed through these public methods so the
    # registry's internal storage strategy (in-memory dict today, possibly
    # a database-backed index tomorrow) is fully encapsulated behind a
    # stable contract.

    def iter_endpoints_global(self) -> Iterable[EndpointSpec]:
        """Yield every registered :class:`EndpointSpec` (read-only iteration)."""
        return list(self._index.by_id.values())

    def iter_endpoints_for_system(self, system: str) -> Iterable[EndpointSpec]:
        """Yield every :class:`EndpointSpec` whose ``system == system``."""
        return [ep for ep in self._index.by_id.values() if ep.system == system]

    def has_system(self, system: str) -> bool:
        """Whether any endpoint is registered under ``system``."""
        return any(ep.system == system for ep in self._index.by_id.values())

    def count_endpoints_for_service(self, service: str) -> int:
        """Number of endpoints belonging to ``service``."""
        return sum(1 for ep in self._index.by_id.values() if ep.service == service)

    def system_of_service(self, service_name: str) -> str | None:
        """First system found that hosts ``service_name`` (or ``None``).

        Used by ``ServiceIndex.system_of`` — service-level ownership is
        derived from the endpoint registry.
        """
        for ep in self._index.by_id.values():
            if ep.service == service_name:
                return ep.system
        return None

    # ── 内部辅助 ──────────────────────────────────────────────
    def _services_for_system(self, system: str) -> set[str]:
        return {ep.service for ep in self._index.by_id.values() if ep.system == system}

    # ── Dim 注册(ADR 0002 §D-D3) ──────────────────────────────
    def register_dim(self, name: str, spec: Any) -> None:
        """Register a dim's ``DimSpec`` under ``name``.

        ``spec`` is intentionally typed as ``Any`` to avoid an import cycle
        with ``gimbal_plate.http.grammar.DimSpec``; callers should pass a
        ``DimSpec`` instance.
        """
        if not name:
            raise ValueError("dim name 不可为空")
        if name in self.dims:
            raise ValueError(f"dim '{name}' 已注册")
        self.dims[name] = spec

    def index_for(self, dim: str) -> Any | None:
        """Return the :class:`DimSpec` registered under ``dim`` or ``None``."""
        return self.dims.get(dim)

    # ── 测试支持 ──────────────────────────────────────────────
    def reset(self) -> None:
        self._services.clear()
        self._index.clear()
        self.dims.clear()


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
