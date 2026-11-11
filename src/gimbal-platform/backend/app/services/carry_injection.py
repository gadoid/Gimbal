"""carry 注入预解析(spec §4.1)— dispatch/导出共用的 CarryContext 构造。

纯 IO 组装:plate 查询(锚点 → carry 面、services 目录)+ 两张值表读取
+ derive_base 服务名解析。任何 plate 故障都降级(空面/空目录),绝不
阻塞执行/导行;DB 故障由调用方决定(dispatch 包 try/except 降级为
无 carry,见 run_dispatcher._fanout)。

索引契约(T8):``step_fields`` 的键 = ``definition["steps"]`` **原始列表**
索引 — ``_apply_carry`` 对 converted.steps 做 ``enumerate``,锚点索引必须
与原始列表对齐;先过滤非 dict 再枚举会让索引漂移、注入错步。
"""
from __future__ import annotations
from .run_semantics import INTEGRATION, PIN, UNDECLARED, WORKING, invalid_reason, record_category, ref_category

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from . import carry_store, service_names
from .service_aliases import effective_alias
from .endpoint_declarations import declarations_of
from .field_state_resolution import carry_face
from .run_materialize import CarryContext


async def _endpoint_declarations(
    endpoint_id: str, ref: str | None = None,
) -> list | None:
    """plate /full → request.declarations(目录态);任何失败 → None(降级)。

    2026-09-05 目录化(§4):不再在此过滤面 —— 面投影统一走
    ``field_state_resolution.carry_face``(解析链单一实现,join
    step.field_states)。垃圾 200 体(json 抛错/信封非 dict)同样
    降级 — 模块契约是「plate 全部失败 → 空面」,不让单端点的坏包
    打断整单 carry。None(降级)与合法空目录 ``[]`` 在调用侧同为
    空面;类型上分开,留降级遥测的口子。

    2026-09-12 取数合并:本函数保留同名同签名的门面(调用点与
    既有测试不受影响),取数/缓存/在飞收敛统一走
    ``endpoint_declarations.declarations_of`` —— 与悬空判定共用同一份
    进程缓存,不再各打一次 plate。契约(上述 None 语义)逐字不变。

    Release 4.4 核心约束:``ref``(执行副本 meta.plate 写明的修订)→
    按修订取 —— 锁定场景的 carry 面不跟随 working 树漂移;缺省 =
    working(未声明系统的过渡形态)。
    """
    from .endpoint_declarations import declarations_of_at
    if ref_category(ref) == PIN:  # b2-3:读取按类别
        return await declarations_of_at(endpoint_id, ref)
    return await declarations_of(endpoint_id)


def _endpoint_id(step: dict) -> Any:
    """step → step.endpoint(M3 锚点;view_hints 双读已删)。"""
    return step.get("endpoint")


def _step_service(step: dict) -> Any:
    """step → call.service;非 dict 时 None(防御)。"""
    call = step.get("call")
    return call.get("service") if isinstance(call, dict) else None


async def build_carry_context(
    db: AsyncSession, definition: dict,
    ui_field_states: dict | None = None,
    *,
    project_id: int | None = None,
    user_id: int | None = None,
    bindings: dict | None = None,
    exec_overrides: dict[str, dict[str, str | None]] | None = None,
) -> CarryContext:
    """dispatch 预解析入口:plate 目录 + step 增量 → 每 step 的 carry 面。

    authz M2a S4 作用域分层(D3 + 区模型收敛):tier 序 = 公共项目层 <
    项目层,层内沿用键层级(别名键 > 基础服务键 > 层默认)。执行配置
    分层⑥(决策 8):**个人层不再存在** —— 个人缺省 carry 的家是默认
    执行配置(``exec_overrides`` 覆盖层),``user_id`` 参数仅为签名兼容,
    不再构成 tier。

    分层②(执行配置):``exec_overrides``({目录服务: {字段: 值}})是
    配置覆盖层,合区位次 = **场景显式之下、层序之上**(值 null = 显式
    注入 JSON null,与值表语义同型);区规则(项目区仅显式选定,决策 9)
    由调用方裁,本函数只做合成。

    面解析走 ``field_state_resolution.carry_face``(§3.2 单一实现):
    ``state(path) = ui.fieldStates[stepIndex][path] ?? entry.state ?? 'form'``
    —— M4 起 field_states 在 payload.ui.fieldStates(按步骤位置索引),
    不再存于 step;场景显式覆盖即时生效(护栏 §1.3),零发版。
    """
    ui_fs: dict = ui_field_states or {}
    # 索引契约:枚举原始列表(跳过非 dict),不用过滤后的下标。
    raw_steps: list = list(definition.get("steps") or [])
    # Release 4.4:声明面按 meta.plate 写明的修订取(锁定场景不随
    # working 漂移;未声明系统回落 working)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}

    # ① 锚点 → 目录声明(按 endpoint_id 去重批量,不逐 step 打 plate)
    endpoint_ids: dict[str, None] = {}
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        eid = _endpoint_id(step)
        if eid:
            endpoint_ids.setdefault(eid, None)
    decls_by_eid: dict[str, list | None] = {
        eid: await _endpoint_declarations(
            eid, ref=meta_plate.get(str(eid).split(".")[0]))
        for eid in endpoint_ids
    }
    step_fields: dict[int, dict[str, str]] = {}
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue
        eid = _endpoint_id(step)
        if eid:
            decls = decls_by_eid[eid]
            # 锚点在即占位:目录拉不到(None 降级)或合法空目录 → 空面
            # = 不注入(fail-closed,spec §4.2.2/D3);降级门控仅限无锚点
            # 存量 step。面 = 解析态投影(join 本 step 的 field_states 增量)
            inc = ui_fs.get(str(i)) or ui_fs.get(i)
            step_fields[i] = (
                carry_face(decls, inc if isinstance(inc, dict) else None)
                if decls is not None else {}
            )

    # ② 服务引用 → derive_base 解析 → 绑定值(None = 解析失败,整步跳过)
    catalog = await service_names.catalog_service_names()
    # S4:tier 序(公共项目层恒在 < 项目层);分层⑥:个人层已收编为默认
    # 执行配置(决策 8),user_id 不再构成 tier
    tiers: list[tuple[str, int]] = [await carry_store.public_scope(db)]
    if project_id is not None:
        tiers.append(("project", project_id))
    defaults: dict[str, str | None] = {}
    for t in tiers:
        defaults = {**defaults,
                    **await carry_store.get_defaults(db, t)}
    raw_services: dict[str, None] = {}
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        svc = _step_service(step)
        if isinstance(svc, str) and svc:
            raw_services.setdefault(svc, None)
    service_bindings: dict[str, dict[str, str | None] | None] = {}
    _ = catalog  # b2-9(D-M):解析改经别名表优先(目录兜底在 helper 内)
    for raw in raw_services:
        base = await service_names.resolve_base_with_aliases(db, raw)
        if base is None:
            logger.warning(
                "carry_injection: service {!r} 不在目录(裸声明)— 该 step "
                "跳过 carry 填充", raw)
            service_bindings[raw] = None
        else:
            # S4:逐 tier 合并(后者覆盖前者);层内沿用别名键稀疏覆盖
            # (服务画像方案 §4.1:精确别名键 > base 服务键 > 层默认 —
            # 字段级 merge,别名行只覆盖它填的那几个字段)
            # S6:别名键 = 服务键的生效别名(方案选 fin → fin-maker 即吃
            # fin-maker 的别名键覆盖;同基础服务已由绑定校验保证)
            alias_key = effective_alias(raw, bindings)
            rows: dict[str, str | None] = {}
            for t in tiers:
                rows_t = await carry_store.get_bindings(db, base, t)
                if base != alias_key:
                    override = await carry_store.get_bindings(
                        db, alias_key, t)
                    if override:
                        rows_t = {**rows_t, **override}
                rows = {**rows, **rows_t}
            # 分层②:执行配置覆盖(目录服务键;null = 显式注入 null)
            ov = (exec_overrides or {}).get(base)
            if ov:
                rows = {**rows, **ov}
            service_bindings[raw] = rows

    return CarryContext(step_fields=step_fields,
                        service_bindings=service_bindings,
                        global_defaults=defaults)
