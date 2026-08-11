"""fin 系统的 dim 注册入口(ADR 0002 §D-D4 — Phase β 提前落地版)。

集中 fin 自己拥有的 7 个 M6 dim 注册 + 4 条 seed。

设计意图:
    - 此函数是 **fin 系统** 的私有装配入口,既被生产路径
      ``gimbal_plate.http.app._lifespan`` 调用,也被测试路径
      ``tests/plate/conftest.py:fresh_registry`` 调用。
    - 之前(Phase α)两个调用点各自维护一份近拷贝代码,违反 DRY
      且存在 drift 风险(给 dim 加字段 / 改 seed 数据 / 加新 action
      要在两个文件里各改一遍,改漏一处就出现"生产/测试行为不一致")。
    - 现在收敛此处:两边都 ``from gimbal_plate.systems.fin.dimensions
      import register_fin_dims``。

调用方:
    from gimbal_plate.systems.fin.dimensions import register_fin_dims
    register_fin_dims(reg)
"""
from __future__ import annotations

from gimbal_plate.http.grammar import (
    ConfigIndex,
    DimSpec,
    EndpointIndex,
    MetaIndex,
    ResourceIndex,
    ScenarioIndex,
    ServiceIndex,
    SystemIndex,
)
from gimbal_plate.http.routes_grammar import (
    action_endpoint_failed_criteria,
    action_endpoint_field_defaults,
    action_endpoint_find,
    action_endpoint_resolve_paths,
    action_scenario_convert,
    action_system_from_service,
    action_system_register,
    action_system_sync,
)
from gimbal_plate.http.views import (
    ConfigDetailView,
    ConfigView,
    EndpointDetailView,
    EndpointView,
    MetaDetailView,
    MetaView,
    ResourceDetailView,
    ResourceView,
    ScenarioDetailView,
    ScenarioView,
    ServiceDetailView,
    ServiceView,
    SystemDetailView,
    SystemView,
)
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.fin.config import fin_config_template
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
from gimbal_plate.systems.fin.meta import fin_meta_template
from gimbal_plate.systems.fin.resource import fin_resource_template
from gimbal_plate.systems.fin.scenario import fin_scenario_template
from gimbal_plate.systems.fin.system_info import FIN_SYSTEM


def register_fin_dims(reg: PlateRegistry) -> None:
    """Register the 7 M6 dims + seed the 4 storage-backed dims (fin only).

    Single source of truth shared by both production
    (:func:`gimbal_plate.http.app._lifespan`) and tests
    (:func:`tests.plate.conftest.fresh_registry`). Callers must pass
    in a registry that already has all ``ALL_ENDPOINTS`` registered
    (or call :meth:`PlateRegistry.register_endpoint` for each).
    """
    for ep in ALL_ENDPOINTS:
        reg.register_endpoint(ep)

    reg.register_dim(
        "endpoint",
        DimSpec(
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
        ),
    )
    reg.register_dim(
        "service",
        DimSpec(
            name="service",
            index=ServiceIndex(registry=reg),
            view_factory=ServiceView.from_definition,
            full_view_factory=ServiceDetailView.from_definition,
            actions={},
        ),
    )
    reg.register_dim(
        "system",
        DimSpec(
            name="system",
            index=SystemIndex(registry=reg),
            view_factory=SystemView.from_summary,
            full_view_factory=SystemDetailView.from_summary,
            actions={
                "from-service": action_system_from_service,
                "register":     action_system_register,
                "sync":         action_system_sync,
            },
        ),
    )

    cfg_idx = ConfigIndex(registry=reg)
    meta_idx = MetaIndex(registry=reg)
    res_idx = ResourceIndex(registry=reg)
    scen_idx = ScenarioIndex(registry=reg)
    reg.register_dim(
        "config",
        DimSpec(
            name="config",
            index=cfg_idx,
            view_factory=ConfigView.from_config,
            full_view_factory=ConfigDetailView.from_config,
            actions={},
        ),
    )
    reg.register_dim(
        "meta",
        DimSpec(
            name="meta",
            index=meta_idx,
            view_factory=MetaView.from_meta,
            full_view_factory=MetaDetailView.from_meta,
            actions={},
        ),
    )
    reg.register_dim(
        "resource",
        DimSpec(
            name="resource",
            index=res_idx,
            view_factory=ResourceView.from_resource,
            full_view_factory=ResourceDetailView.from_resource,
            actions={},
        ),
    )
    reg.register_dim(
        "scenario",
        DimSpec(
            name="scenario",
            index=scen_idx,
            view_factory=ScenarioView.minimal,
            full_view_factory=ScenarioDetailView.from_scenario,
            actions={
                # 结构转换 —— 把调用方传入的 Scenario dict 通过
                # export.dispatch() 转成不同 consumer 需要的 dict。
                # 路由自动是 POST /api/scenario/action/convert。
                "convert": action_scenario_convert,
            },
        ),
    )

    # Seeds (Phase α). id 命名 = "<system>.<name>",scenario 用自身 scenarioId 作 key。
    cfg_idx.register(fin_config_template(),   item_id=f"{FIN_SYSTEM}.default")
    meta_idx.register(fin_meta_template(),    item_id=f"{FIN_SYSTEM}.default")
    res_idx.register(fin_resource_template(), item_id=f"{FIN_SYSTEM}.tidb_test")
    scen_idx.register(fin_scenario_template())


__all__ = ["register_fin_dims"]
