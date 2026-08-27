"""多维度索引:为 PlateRegistry 的查询提供加速。

覆盖维度与复杂度:
    - ``by_id``         O(1) — id → EndpointSpec
    - ``by_service``    O(1) — service → {id}
    - ``by_tag``        O(1) — tag → {id}
    - ``by_route``      O(1) — (service, method, path) → id

未覆盖的维度（当前为线性扫描，由调用方承担）:
    - ``by_system``     O(N) — ``list_systems()`` / ``_services_for_system()`` 遍历 ``by_id.values()``
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gimbal_plate.schema.endpoint import EndpointSpec


@dataclass
class _Index:
    """内存索引。

    四个维度独立维护:
        - ``by_id``         id → EndpointSpec
        - ``by_service``    service → {id}
        - ``by_tag``        tag → {id}
        - ``by_route``      (service, method, path) → id

    注: ``system`` 维度未建索引,见模块 docstring。
    """

    by_id: dict[str, EndpointSpec] = field(default_factory=dict)
    by_service: dict[str, set[str]] = field(default_factory=dict)
    by_tag: dict[str, set[str]] = field(default_factory=dict)
    by_route: dict[tuple[str, str, str], str] = field(default_factory=dict)

    def add(self, ep: EndpointSpec) -> None:
        self.by_id[ep.id] = ep
        self.by_service.setdefault(ep.service, set()).add(ep.id)
        for tag in ep.metadata.tags:
            self.by_tag.setdefault(tag, set()).add(ep.id)
        self.by_route[(ep.api.service, ep.api.method, ep.api.path)] = ep.id

    def remove(self, endpoint_id: str) -> EndpointSpec | None:
        ep = self.by_id.pop(endpoint_id, None)
        if ep is None:
            return None
        self.by_service.get(ep.service, set()).discard(endpoint_id)
        for tag in ep.metadata.tags:
            self.by_tag.get(tag, set()).discard(endpoint_id)
        self.by_route.pop((ep.api.service, ep.api.method, ep.api.path), None)
        return ep

    def clear(self) -> None:
        self.by_id.clear()
        self.by_service.clear()
        self.by_tag.clear()
        self.by_route.clear()
