"""PlateRegistry 多维度索引测试。"""
from __future__ import annotations

import pytest

from gimbal_plate import PlateRegistry, registry


class TestPlateRegistry:
    def test_register_and_get(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        assert registry.has_endpoint("finas.order.add")
        assert registry.get_endpoint("finas.order.add") is order_endpoint

    def test_duplicate_registration_rejected(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        with pytest.raises(ValueError):
            registry.register_endpoint(order_endpoint)

    def test_get_missing_raises(self, reset_registry) -> None:
        with pytest.raises(KeyError):
            registry.get_endpoint("nonexistent")

    def test_list_systems(self, reset_registry, order_endpoint, order_patch_endpoint) -> None:
        registry.register_endpoints([order_endpoint, order_patch_endpoint])
        systems = registry.list_systems()
        assert systems == ["finas"]

    def test_list_services_no_filter(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        services = registry.list_services()
        assert any(s.name == "settlement" for s in services)

    def test_list_services_by_system(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        services = registry.list_services(system="finas")
        names = {s.name for s in services}
        assert "settlement" in names

    def test_list_endpoints_by_service(self, reset_registry, order_endpoint, order_patch_endpoint) -> None:
        registry.register_endpoints([order_endpoint, order_patch_endpoint])
        eps = registry.list_endpoints(service="settlement")
        assert {e.id for e in eps} == {
            "finas.order.add",
            "finas.order.patch",
        }

    def test_list_endpoints_by_tag(self, reset_registry, order_endpoint, order_patch_endpoint) -> None:
        registry.register_endpoints([order_endpoint, order_patch_endpoint])
        # order_endpoint.tags = ["冒烟", "结算"], order_patch_endpoint.tags = ["结算"]
        eps = registry.list_endpoints(tag="冒烟")
        assert {e.id for e in eps} == {"finas.order.add"}
        eps = registry.list_endpoints(tag="结算")
        assert {e.id for e in eps} == {
            "finas.order.add",
            "finas.order.patch",
        }

    def test_list_endpoints_multi_filter(self, reset_registry, order_endpoint, order_patch_endpoint) -> None:
        registry.register_endpoints([order_endpoint, order_patch_endpoint])
        eps = registry.list_endpoints(system="finas", service="settlement", tag="冒烟")
        assert {e.id for e in eps} == {"finas.order.add"}

    def test_find_by_route(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        found = registry.find_endpoints(
            service="settlement",
            method="POST",
            path="/api/v1/orders",
        )
        assert [e.id for e in found] == ["finas.order.add"]

    def test_find_missing_returns_empty(self, reset_registry) -> None:
        assert registry.find_endpoints("svc", "GET", "/x") == []

    def test_reset(self, reset_registry, order_endpoint) -> None:
        registry.register_endpoint(order_endpoint)
        assert registry.has_endpoint("finas.order.add")
        registry.reset()
        assert not registry.has_endpoint("finas.order.add")
        assert registry.list_systems() == []

    def test_isolated_instance(self, reset_registry, order_endpoint) -> None:
        local = PlateRegistry()
        local.register_endpoint(order_endpoint)
        assert local.has_endpoint("finas.order.add")
        assert not registry.has_endpoint("finas.order.add")
