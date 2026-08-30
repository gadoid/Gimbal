"""Plate HTTP routing grammar — dim registry, index base classes, error codes.

Per ADR 0002 (M6):
- Every URL path under ``/api`` starts with a ``{dim}`` segment.
- ``/systems/{system}/`` is an optional prefix that scopes the query.
- ``/{id}/action/{name}`` carries per-object actions.
- ``/action/{name}`` (without ``{id}``) carries dim-node actions
  (e.g. ``system_from-service``, ``register``, ``sync``).
- The URL grammar is decoupled from registry storage strategy
  (ADR 0002 §"为什么 M6 比 M4 / M5 更优"). Each dim declares its
  :class:`BaseIndex` and :class:`BaseView`; the generic handler dispatches
  to them uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from gimbal_plate.http.envelope import ErrorCode
from gimbal_plate.http.views import (
    ConfigView,
    EndpointView,
    MetaView,
    ResourceView,
    ScenarioView,
    ServiceView,
    SystemView,
)
from gimbal_plate.http.strategy_dim import StrategyIndex
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.resource import ResourceUnion
from gimbal_plate.schema.scenario import Config, Meta, Scenario
from gimbal_plate.schema.service_definition import ServiceDefinition

# Re-export the enum so callers can ``from gimbal_plate.http.grammar import ErrorCode``.
__all__ = [
    "ErrorCode",
    "BaseIndex",
    "DimSpec",
    "EndpointIndex",
    "ServiceIndex",
    "SystemIndex",
    "ConfigIndex",
    "MetaIndex",
    "ResourceIndex",
    "ScenarioIndex",
    "StrategyIndex",
]


# ── Base index contract ────────────────────────────────────────────


class BaseIndex(ABC):
    """Minimal contract every dim index must satisfy.

    Generic handlers dispatch on these three primitives only. Storage details
    (in-memory dict, lazy DB read, remote fetch) live behind the index.
    """

    @abstractmethod
    def list_global(self, *, filters: dict[str, Any] | None = None) -> list[Any]:
        """Return all dim items matching ``filters`` (or all if None)."""

    @abstractmethod
    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[Any]:
        """Return all dim items belonging to ``system``."""

    @abstractmethod
    def get(self, item_id: str) -> Any | None:
        """Return the item by id or ``None`` if missing."""

    @abstractmethod
    def to_view(self, item: Any) -> Any:
        """Coerce a dim item to its public view model (handles redaction)."""

    def has_system(self, system: str) -> bool:
        """Whether this dim has any item under ``system``.

        Default impl walks ``list_for_system``; subclasses may override
        with cheaper lookups.
        """
        return len(self.list_for_system(system)) > 0


# ── EndpointIndex ──────────────────────────────────────────────────


@dataclass
class EndpointIndex(BaseIndex):
    """Index over :class:`PlateRegistry._index` (endpoint dimension)."""

    registry: Any  # PlateRegistry — typed as Any to avoid an import cycle.

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[EndpointSpec]:
        items = list(self.registry.iter_endpoints_global())
        return _apply_endpoint_filters(items, filters or {})

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[EndpointSpec]:
        items = list(self.registry.iter_endpoints_for_system(system))
        return _apply_endpoint_filters(items, filters or {})

    def get(self, item_id: str) -> EndpointSpec | None:
        return self.registry.try_endpoint(item_id)

    def to_view(self, item: EndpointSpec) -> dict[str, Any]:
        return EndpointView.from_spec(item).model_dump(mode="json", exclude_none=True)

    def find_by_route(
        self, *, service: str, method: str, path: str
    ) -> EndpointSpec | None:
        eps = self.registry.find_endpoints(service=service, method=method, path=path)
        return eps[0] if eps else None


def _apply_endpoint_filters(
    items: list[EndpointSpec], filters: dict[str, Any]
) -> list[EndpointSpec]:
    """Apply A3-style query filters (service/module/method/q/tag)."""
    out = items
    service = filters.get("service")
    if service is not None:
        out = [ep for ep in out if ep.service == service]
    module = filters.get("module")
    if module is not None:
        out = [ep for ep in out if (ep.metadata.module or "") == module]
    method = filters.get("method")
    if method is not None:
        upper = method.upper()
        out = [ep for ep in out if ep.api.method.upper() == upper]
    q = filters.get("q")
    if q:
        needle = q.lower()
        out = [
            ep
            for ep in out
            if needle in ep.id.lower()
            or needle in ep.name.lower()
            or needle in (ep.description or "").lower()
            or needle in ep.api.path.lower()
        ]
    tag = filters.get("tag")
    if tag is not None:
        out = [ep for ep in out if tag in (ep.metadata.tags or [])]
    return out


# ── ServiceIndex ───────────────────────────────────────────────────


@dataclass
class ServiceIndex(BaseIndex):
    """Index over :class:`PlateRegistry._services`."""

    registry: Any

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[ServiceDefinition]:
        return self.registry.iter_services_global()

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[ServiceDefinition]:
        return self.registry.iter_services_for_system(system)

    def get(self, item_id: str) -> ServiceDefinition | None:
        return self.registry.get_service(item_id)

    def to_view(self, item: ServiceDefinition) -> dict[str, Any]:
        # Count endpoints for this service (public API).
        count = self.registry.count_endpoints_for_service(item.name)
        return ServiceView.from_definition(item, endpoint_count=count).model_dump(
            mode="json", exclude_none=True
        )

    def system_of(self, item: ServiceDefinition) -> str | None:
        return self.registry.system_of_service(item.name)


# ── SystemIndex ────────────────────────────────────────────────────


@dataclass
class SystemIndex(BaseIndex):
    """Index over the system set derived from endpoint metadata."""

    registry: Any

    def _systems(self) -> list[str]:
        # endpoint 派生 ∪ 声明式(common 通用层 / C1 注册),由 registry 统一合并。
        return self.registry.list_systems()

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for system in self._systems():
            summary = self._summary(system)
            out.append(summary)
        return out

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if not self.has_system(system):
            return []
        return [self._summary(system)]

    def get(self, item_id: str) -> dict[str, Any] | None:
        if not self.has_system(item_id):
            return None
        return self._summary(item_id)

    def to_view(self, item: dict[str, Any]) -> dict[str, Any]:
        return SystemView.from_summary(item).model_dump(mode="json", exclude_none=True)

    def has_system(self, system: str) -> bool:
        return self.registry.has_system(system)

    def _summary(self, system: str) -> dict[str, Any]:
        eps = list(self.registry.iter_endpoints_for_system(system))
        services = {ep.service for ep in eps}
        latest = None
        for ep in eps:
            ts = ep.updated_at
            if ts is not None and (latest is None or ts > latest):
                latest = ts
        return {
            "id": system,
            "name": system,
            "service_count": len(services),
            "endpoint_count": len(eps),
            "registered_at": latest,
        }


# ── ConfigIndex / MetaIndex / ResourceIndex / ScenarioIndex ───────


@dataclass
class ConfigIndex(BaseIndex):
    """In-memory Config dim seed. Seeded by ``_lifespan`` (ADR 0002 §D-D4)."""

    registry: Any
    _items: dict[str, Config] = field(default_factory=dict)

    def register(self, item: Config, *, item_id: str) -> None:
        self._items[item_id] = item

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[Config]:
        return list(self._items.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[Config]:
        # Config doesn't carry system field directly; use the producer's key.
        return [c for cid, c in self._items.items() if cid.startswith(f"{system}.")]

    def get(self, item_id: str) -> Config | None:
        return self._items.get(item_id)

    def to_view(self, item: Config) -> dict[str, Any]:
        return ConfigView.from_config(item).model_dump(mode="json", exclude_none=True)


@dataclass
class MetaIndex(BaseIndex):
    registry: Any
    _items: dict[str, Meta] = field(default_factory=dict)

    def register(self, item: Meta, *, item_id: str) -> None:
        self._items[item_id] = item

    def list_global(self, *, filters: dict[str, Any] | None = None) -> list[Meta]:
        return list(self._items.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[Meta]:
        return [m for m in self._items.values() if system in (m.system or [])]

    def get(self, item_id: str) -> Meta | None:
        return self._items.get(item_id)

    def to_view(self, item: Meta) -> dict[str, Any]:
        return MetaView.from_meta(item).model_dump(mode="json", exclude_none=True)


@dataclass
class ResourceIndex(BaseIndex):
    registry: Any
    _items: dict[str, ResourceUnion] = field(default_factory=dict)

    def register(self, item: ResourceUnion, *, item_id: str) -> None:
        self._items[item_id] = item

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[ResourceUnion]:
        return list(self._items.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[ResourceUnion]:
        return [
            r for rid, r in self._items.items() if rid.startswith(f"{system}.")
        ]

    def get(self, item_id: str) -> ResourceUnion | None:
        return self._items.get(item_id)

    def to_view(self, item: ResourceUnion) -> dict[str, Any]:
        return ResourceView.from_resource(item).model_dump(
            mode="json", exclude_none=True
        )


@dataclass
class ScenarioIndex(BaseIndex):
    registry: Any
    _items: dict[str, Scenario] = field(default_factory=dict)

    def register(self, item: Scenario, *, item_id: str | None = None) -> None:
        self._items[item.scenarioId] = item

    def list_global(
        self, *, filters: dict[str, Any] | None = None
    ) -> list[Scenario]:
        return list(self._items.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[Scenario]:
        return [
            s
            for s in self._items.values()
            if system in (s.meta.system or [])
        ]

    def get(self, item_id: str) -> Scenario | None:
        return self._items.get(item_id)

    def to_view(self, item: Scenario) -> dict[str, Any]:
        # Phase α: minimal view — scenarioId + meta.name only (ADR 0002 §D-D6).
        return ScenarioView.minimal(item).model_dump(
            mode="json", exclude_none=True
        )


# ── DimSpec ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DimSpec:
    """Registration entry for one dim (ADR 0002 §D3 / §D-D3).

    ``view_factory`` returns the **light** public view (id / name / method
    / path / counts etc.) for ``/{dim}`` and ``/{dim}/{id}``.

    ``full_view_factory`` is **optional**. When set, it returns the **full**
    contract for ``/{dim}/full`` and ``/{dim}/{id}/full`` (every original
    schema field, including IOFieldBinding metadata, sensitive credentials,
    and ``extra``-captured extension fields). When unset, the ``/full``
    endpoints return 501 ``admin_not_implemented`` (the dim chose to keep
    its ``light`` view as the only contract).
    """

    name: str
    index: BaseIndex
    view_factory: Callable[[Any], dict[str, Any]]
    actions: dict[str, Callable[..., Any]] = field(default_factory=dict)
    full_view_factory: Callable[[Any], dict[str, Any]] | None = None