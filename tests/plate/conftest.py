"""gimbal_plate 测试 fixtures。"""
from __future__ import annotations

import pytest

# 确保 gimbal_plate 可被 import(src/gimbal-plate 在 PYTHONPATH 或已安装)
import sys
from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "src" / "gimbal-plate"
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from pydantic import BaseModel

from gimbal_plate import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    registry,
)
from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


@pytest.fixture
def fresh_registry() -> PlateRegistry:
    """A fresh in-memory registry pre-loaded with the bundled fin system + M6 dims.

    Mirror of :func:`gimbal_plate.http.app._register_fin_dims` for the test
    harness. Tests pass this registry to ``create_app(registry=...)``, which
    means the production ``_lifespan`` will skip its owned-mode setup. To
    keep both paths in sync we duplicate the dim registration here verbatim
    (per the Phase α decision: no shared helper between app and conftest).
    """
    reg = PlateRegistry()
    for ep in ALL_ENDPOINTS:
        reg.register_endpoint(ep)

    # M6 grammar mirror — 7 dims + 4 seeds.
    from gimbal_plate.http.grammar import (
        ConfigIndex, DimSpec, EndpointIndex, MetaIndex, ResourceIndex,
        ScenarioIndex, ServiceIndex, SystemIndex,
    )
    from gimbal_plate.http.routes_grammar import (
        action_endpoint_failed_criteria, action_endpoint_field_defaults,
        action_endpoint_find, action_endpoint_resolve_paths,
        action_system_from_service, action_system_register, action_system_sync,
    )
    from gimbal_plate.http.views import (
        ConfigDetailView, ConfigView, EndpointDetailView, EndpointView,
        MetaDetailView, MetaView, ResourceDetailView, ResourceView,
        ScenarioDetailView, ScenarioView, ServiceDetailView, ServiceView,
        SystemDetailView, SystemView,
    )
    from gimbal_plate.systems.fin.config import fin_config_template
    from gimbal_plate.systems.fin.meta import fin_meta_template
    from gimbal_plate.systems.fin.resource import fin_resource_template
    from gimbal_plate.systems.fin.scenario import fin_scenario_template
    from gimbal_plate.systems.fin.system_info import FIN_SYSTEM

    reg.register_dim("endpoint", DimSpec(
        name="endpoint",
        index=EndpointIndex(registry=reg),
        view_factory=EndpointView.from_spec,
        full_view_factory=EndpointDetailView.from_spec,
        actions={
            "field-defaults":  action_endpoint_field_defaults,
            "resolve-paths":   action_endpoint_resolve_paths,
            "failed-criteria": action_endpoint_failed_criteria,
            "find":            action_endpoint_find,
        },
    ))
    reg.register_dim("service", DimSpec(
        name="service",
        index=ServiceIndex(registry=reg),
        view_factory=ServiceView.from_definition,
        full_view_factory=ServiceDetailView.from_definition,
        actions={},
    ))
    reg.register_dim("system", DimSpec(
        name="system",
        index=SystemIndex(registry=reg),
        view_factory=SystemView.from_summary,
        full_view_factory=SystemDetailView.from_summary,
        actions={
            "from-service": action_system_from_service,
            "register":     action_system_register,
            "sync":         action_system_sync,
        },
    ))
    cfg_idx  = ConfigIndex(registry=reg)
    meta_idx = MetaIndex(registry=reg)
    res_idx  = ResourceIndex(registry=reg)
    scen_idx = ScenarioIndex(registry=reg)
    reg.register_dim("config",   DimSpec(
        name="config", index=cfg_idx,
        view_factory=ConfigView.from_config,
        full_view_factory=ConfigDetailView.from_config,
        actions={},
    ))
    reg.register_dim("meta",     DimSpec(
        name="meta", index=meta_idx,
        view_factory=MetaView.from_meta,
        full_view_factory=MetaDetailView.from_meta,
        actions={},
    ))
    reg.register_dim("resource", DimSpec(
        name="resource", index=res_idx,
        view_factory=ResourceView.from_resource,
        full_view_factory=ResourceDetailView.from_resource,
        actions={},
    ))
    reg.register_dim("scenario", DimSpec(
        name="scenario", index=scen_idx,
        view_factory=ScenarioView.minimal,
        full_view_factory=ScenarioDetailView.from_scenario,
        actions={},
    ))
    cfg_idx.register(fin_config_template(),    item_id=f"{FIN_SYSTEM}.default")
    meta_idx.register(fin_meta_template(),     item_id=f"{FIN_SYSTEM}.default")
    res_idx.register(fin_resource_template(),  item_id=f"{FIN_SYSTEM}.tidb_test")
    scen_idx.register(fin_scenario_template())
    return reg


@pytest.fixture
def http_client(fresh_registry: PlateRegistry):
    """A ``TestClient`` bound to a plate app using ``fresh_registry``."""
    from fastapi.testclient import TestClient  # local import keeps top of file stable

    with TestClient(create_app(registry=fresh_registry)) as client:
        yield client


# ── 示例 Pydantic 模型 ──────────────────────────────────────────────

class OrderIn(BaseModel):
    order_no: str
    amount: float


class OrderOut(BaseModel):
    order_id: str
    order_no: str


class OrderPatch(BaseModel):
    order_id: str
    status: str


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def reset_registry() -> None:
    """每个测试前后清空全局 registry,避免用例间污染。"""
    registry.reset()
    yield
    registry.reset()


@pytest.fixture
def order_endpoint() -> EndpointSpec:
    """一个示例 EndpointSpec:新增订单(POST /api/v1/orders)。"""
    return EndpointSpec(
        id="finas.order.add",
        system="finas",
        service="settlement",
        name="新增订单",
        description="创建一笔结算订单",
        api=ApiSpec(
            service="settlement",
            method="POST",
            path="/api/v1/orders",
            timeout_seconds=30,
            auth="bearer",
        ),
        request=RequestSpec(
            body_type="json",
            model=OrderIn,
            fields=[
                IOFieldBinding(name="order_no", path="order_no", required=True,
                               example="ORD-001", ui_kind="text"),
                IOFieldBinding(name="amount", path="amount", required=True,
                               example=99.9, ui_kind="number"),
            ],
        ),
        responses={
            200: ResponseSpec(
                status=200,
                description="成功",
                model=OrderOut,
                fields=[
                    IOFieldBinding(name="order_id", path="order_id",
                                   required=True, ui_kind="text"),
                    IOFieldBinding(name="order_no", path="order_no",
                                   required=True, ui_kind="text"),
                ],
                assertable_fields=["order_id", "order_no"],
            ),
            400: ResponseSpec(status=400, description="参数错误"),
        },
        metadata=EndpointMetadata(
            module="订单",
            tags=["冒烟", "结算"],
            owner="alice",
            priority=1,
            preconditions=["已登录"],
            success_criteria="返回 order_id",
        ),
        version="1.0.0",
    )


@pytest.fixture
def order_patch_endpoint() -> EndpointSpec:
    """第二个示例 EndpointSpec:更新订单(POST /api/v1/orders/patch)。"""
    return EndpointSpec(
        id="finas.order.patch",
        system="finas",
        service="settlement",
        name="更新订单",
        api=ApiSpec(
            service="settlement",
            method="POST",
            path="/api/v1/orders/patch",
        ),
        request=RequestSpec(body_type="json", model=OrderPatch),
        responses={200: ResponseSpec(status=200, model=OrderOut)},
        metadata=EndpointMetadata(tags=["结算"], owner="bob"),
    )
