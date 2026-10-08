"""gimbal_plate.loader —— 统一加载器（批次 A2，7.1 / 8e / 修订四）。

取代 ``app.py`` lifespan 写死导入与各系统 ``dimensions.py``：

- 按「路径列表」发现系统（系统目录路径可配置——缺省单仓 ``systems/``，
  ``PLATE_SYSTEMS_PATH`` 环境变量覆盖，多路径以 os.pathsep 分隔）；
- 解析每个系统目录下的全部 Markdown 交付物（方言内核 ``dialect``）；
- ``system.md``：``gimbal:system`` 块（ServiceDefinition，可列表）声明
  服务；``gimbal:defaults`` 块（config / meta / resources / scenarios）
  播种四个默认模板 dim；
- endpoints/*.md 等其余文件：注册新栈 EndpointSpec；
- dim 装配统一在此完成：9 个既有 dim 全局挂载一次（数据 dim 与框架
  dim 同挂全局——修订四：消灭「注册在 fin 装配点」的 pragmatic 拍板）。

快照语义（7.1，working 阶段）：加载产物为一次内存快照，标识
``<系统>@working``；多版本 ref 选择属批次 B。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from gimbal_plate.dialect import Deliverable, EndpointSpec, parse_markdown
from gimbal_plate.dialect.parser import Block
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
    action_system_check,
    action_system_from_service,
    action_system_gaps,
    action_system_register,
    action_system_release,
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
from gimbal_plate.schema.scenario import Scenario as ScenarioModel
from gimbal_plate.schema.scenario import Config as ConfigModel, Meta as MetaModel
from gimbal_plate.schema.service_definition import ServiceDefinition
from pydantic import TypeAdapter

from gimbal_plate.schema.resource import ResourceUnion

DEFAULT_SYSTEMS_ROOT = "systems"
SNAPSHOT_WORKING = "working"


def systems_roots(explicit: list[Path] | None = None) -> list[Path]:
    """系统目录路径列表（修订四：路径可配置）。

    缺省两处：CWD 相对 ``systems/``（服务从仓库根启动的常态）与包位置
    回溯的仓库根 ``systems/``（跨目录内嵌消费——平台进程内 ASGI 挂载真
    plate 时 CWD 在 backend 子目录，靠这条兜底命中同一棵真源树）。
    ``PLATE_SYSTEMS_PATH`` 覆盖一切（os.pathsep 分隔多路径）。
    """
    if explicit:
        return [Path(p) for p in explicit]
    env = os.environ.get("PLATE_SYSTEMS_PATH")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    _pkg_repo_root = Path(__file__).resolve().parents[2]
    roots = [Path(DEFAULT_SYSTEMS_ROOT), _pkg_repo_root / DEFAULT_SYSTEMS_ROOT]
    # 同目录双表达(CWD 相对 vs 绝对)去重,防系统重复注册
    seen: set[str] = set()
    uniq: list[Path] = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq


def register_core_dims(reg: PlateRegistry) -> None:
    """9 个既有 dim 全局挂载一次（数据 dim + 框架 dim，7.2 / 修订四）。"""
    reg.register_dim(
        "endpoint",
        DimSpec(
            name="endpoint",
            index=EndpointIndex(registry=reg),
            view_factory=EndpointView.from_spec,
            full_view_factory=EndpointDetailView.from_spec,
            actions={
                "field-defaults": action_endpoint_field_defaults,
                "resolve-paths": action_endpoint_resolve_paths,
                "failed-criteria": action_endpoint_failed_criteria,
                "find": action_endpoint_find,
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
                # register / sync 已停用（S1-0 B4），保留动作面以返回 410
                "register": action_system_register,
                "sync": action_system_sync,
                # 批次 B：gaps(G6) / check(校验全量) / release(冻结)
                "gaps": action_system_gaps,
                "check": action_system_check,
                "release": action_system_release,
            },
        ),
    )
    cfg_idx = ConfigIndex(registry=reg)
    meta_idx = MetaIndex(registry=reg)
    res_idx = ResourceIndex(registry=reg)
    scen_idx = ScenarioIndex(registry=reg)
    reg.register_dim(
        "config", DimSpec(name="config", index=cfg_idx,
                          view_factory=ConfigView.from_config,
                          full_view_factory=ConfigDetailView.from_config, actions={}),
    )
    reg.register_dim(
        "meta", DimSpec(name="meta", index=meta_idx,
                        view_factory=MetaView.from_meta,
                        full_view_factory=MetaDetailView.from_meta, actions={}),
    )
    reg.register_dim(
        "resource", DimSpec(name="resource", index=res_idx,
                            view_factory=ResourceView.from_resource,
                            full_view_factory=ResourceDetailView.from_resource,
                            actions={}),
    )
    reg.register_dim(
        "scenario", DimSpec(name="scenario", index=scen_idx,
                            view_factory=ScenarioView.minimal,
                            full_view_factory=ScenarioDetailView.from_scenario,
                            actions={"convert": action_scenario_convert}),
    )
    reg.register_dim(
        "strategy", DimSpec(name="strategy", index=StrategyIndex(registry=reg),
                            view_factory=StrategyKindView.from_descriptor,
                            full_view_factory=StrategyKindDetailView.from_descriptor,
                            actions={}),
    )
    # 批次 D/G1:type dim —— 类型模板目录 + 方言自描述(JSON Schema 视图)
    from gimbal_plate.dialect.selfdescribe_view import TypeCatalogIndex
    reg.register_dim(
        "type", DimSpec(name="type", index=TypeCatalogIndex(registry=reg),
                        view_factory=lambda item: item,
                        full_view_factory=lambda item: item, actions={}),
    )
    reg.register_dim(
        "generators", DimSpec(name="generators", index=GeneratorIndex(registry=reg),
                              view_factory=GeneratorKindView.from_descriptor,
                              full_view_factory=GeneratorKindDetailView.from_descriptor,
                              actions={}),
    )


def _seed_defaults(
    reg: PlateRegistry, system_id: str, payload: dict[str, Any]
) -> None:
    """gimbal:defaults 块 → 四个默认模板 dim 的种子。"""
    cfg_idx = reg.index_for("config").index
    meta_idx = reg.index_for("meta").index
    res_idx = reg.index_for("resource").index
    scen_idx = reg.index_for("scenario").index
    if payload.get("config"):
        cfg_idx.register(ConfigModel.model_validate(payload["config"]),
                         item_id=f"{system_id}.default")
    if payload.get("meta"):
        meta_idx.register(MetaModel.model_validate(payload["meta"]),
                          item_id=f"{system_id}.default")
    for name, body in (payload.get("resources") or {}).items():
        res_idx.register(TypeAdapter(ResourceUnion).validate_python(body),
                         item_id=f"{system_id}.{name}")
    for scen_id, body in (payload.get("scenarios") or {}).items():
        scen = ScenarioModel.model_validate(body)
        if scen.scenarioId != scen_id:
            raise ValueError(
                f"{system_id} defaults: scenario 键 {scen_id!r} 与 "
                f"scenarioId {scen.scenarioId!r} 不一致"
            )
        scen_idx.register(scen)


def _load_system_dir(
    reg: PlateRegistry, system_dir: Path
) -> dict[str, int]:
    """加载一个系统目录：system.md 先行（声明服务），再加载其余交付物。"""
    system_id = system_dir.name
    counts = {"endpoints": 0, "deliverables": 0}
    system_md = system_dir / "system.md"
    if system_md.exists():
        _load_system_md(reg, system_id, system_md)
    for md in sorted(system_dir.rglob("*.md")):
        if md == system_md:
            continue
        deliverable = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        counts["deliverables"] += 1
        for block in deliverable.blocks("endpoint"):
            for ep in block.models():
                if not isinstance(ep, EndpointSpec):
                    continue
                # J3(第五轮):system 字段与所在目录必须一致——否则注册到
                # 别的系统下,查询面与 check/release 的归属判定分裂
                if ep.system != system_id:
                    raise ValueError(
                        f"{md}: 接口 {ep.id!r} 的 system 字段 {ep.system!r} "
                        f"与所在目录 {system_id!r} 不一致")
                reg.register_endpoint(ep)
                counts["endpoints"] += 1
    return counts


def _load_system_md(
    reg: PlateRegistry, system_id: str, path: Path
) -> None:
    deliverable = parse_markdown(path.read_text(encoding="utf-8"), source=str(path))
    reg.declare_system(system_id)
    for block in deliverable.blocks("system"):
        items = block.payload if isinstance(block.payload, list) else [block.payload]
        for item in items:
            reg.register_service(ServiceDefinition.model_validate(item))
    for block in deliverable.blocks("defaults"):
        payload = block.payload
        if isinstance(payload, list):
            for p in payload:
                _seed_defaults(reg, system_id, p)
        else:
            _seed_defaults(reg, system_id, payload)


def load_registry(
    roots: list[Path] | None = None, *, reg: PlateRegistry | None = None
) -> PlateRegistry:
    """扫描系统目录 → 装配 dim + 注册全部定义（working 快照构建）。"""
    reg = reg if reg is not None else PlateRegistry()
    register_core_dims(reg)
    total = {"endpoints": 0, "deliverables": 0}
    import re as _re
    _name_re = _re.compile(r"^[a-z][a-z0-9_-]*$")
    for root in systems_roots(roots):
        if not root.is_dir():
            continue
        root_resolved = root.resolve()
        for system_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            # X5(第六轮):与动作路由同口径——非法名字不加载、符号链接
            # 逃出根的目录不加载(否则查询面暴露动作侧 404 的树,前后不一)
            if not _name_re.match(system_dir.name):
                continue
            try:
                system_dir.resolve().relative_to(root_resolved)
            except ValueError:
                continue
            c = _load_system_dir(reg, system_dir)
            total["endpoints"] += c["endpoints"]
            total["deliverables"] += c["deliverables"]
    reg.snapshot_id = "working"  # type: ignore[attr-defined]
    return reg


_ = (Deliverable, Block)  # 类型完整性
