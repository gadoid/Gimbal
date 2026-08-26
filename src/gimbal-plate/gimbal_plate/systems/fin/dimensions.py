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

from gimbal_plate.http.generator_dim import GeneratorIndex
from gimbal_plate.http.grammar import (
    ConfigIndex,
    DimSpec,
    EndpointIndex,
    MetaIndex,
    ResourceIndex,
    ScenarioIndex,
    ServiceIndex,
    StrategyIndex,
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
    GeneratorKindDetailView,
    GeneratorKindView,
    MetaDetailView,
    MetaView,
    ResourceDetailView,
    ResourceView,
    ScenarioDetailView,
    ScenarioView,
    ServiceDetailView,
    ServiceView,
    StrategyKindDetailView,
    StrategyKindView,
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

    Note: this function does NOT re-register endpoints; that's the
    caller's job (per the docstring).  Re-registering would raise
    ``ValueError("Endpoint '...' 已注册")`` on the second pass.
    """
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

    # strategy: 语法级 dim(第 8 个),非 fin 数据 —— 注册在 fin 装配点是
    # pragmatic 拍板(2026-08-17):本函数是生产/测试共用的唯一 dim 装配入口,
    # 单开第二条装配路径会导致 drift(dimensions.py 模块 docstring 警告过)。
    # items 是从 StrategyUnion 内省的 kind 描述符;strategy_ref 预埋字段
    # 整条排除,待重设计。语法全局,任意 system 作用域返回全量。
    reg.register_dim(
        "strategy",
        DimSpec(
            name="strategy",
            index=StrategyIndex(registry=reg),
            view_factory=StrategyKindView.from_descriptor,
            full_view_factory=StrategyKindDetailView.from_descriptor,
            actions={},
        ),
    )

    # generators: 语法级 dim(第 9 个),生成器 spec 描述符 —— 注册在 fin
    # 装配点的理由同 strategy(生产/测试共用唯一 dim 装配入口,防 drift)。
    # 引擎 src/gimbal/generator/specs.py 是执行权威源;plate 镜像
    # schema/generator.py 手工同步,tests/plate/test_generator_dim.py
    # P7 防漂移。语法全局,任意 system 作用域返回全量。
    reg.register_dim(
        "generators",
        DimSpec(
            name="generators",
            index=GeneratorIndex(registry=reg),
            view_factory=GeneratorKindView.from_descriptor,
            full_view_factory=GeneratorKindDetailView.from_descriptor,
            actions={},
        ),
    )

    # Seeds (Phase α). id 命名 = "<system>.<name>",scenario 用自身 scenarioId 作 key。
    cfg_idx.register(fin_config_template(),   item_id=f"{FIN_SYSTEM}.default")
    meta_idx.register(fin_meta_template(),    item_id=f"{FIN_SYSTEM}.default")
    res_idx.register(fin_resource_template(), item_id=f"{FIN_SYSTEM}.tidb_test")
    scen_idx.register(fin_scenario_template())


__all__ = ["register_fin_dims"]
