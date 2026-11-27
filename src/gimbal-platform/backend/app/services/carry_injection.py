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
from sqlalchemy import select
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


async def merge_carry_tiers(
    db: AsyncSession,
    tiers: list[tuple[str, int]],
    *,
    base: str,
    alias_key: str | None,
    instance_key: str | None,
    env_id: int | None,
    exec_overrides: dict[str, str | None] | None = None,
    exec_removals: "list[str] | None" = None,
) -> dict[str, dict]:
    """§8.9 键域**单源**合并(执行链 build_carry_context 与预览
    resolve_effective_config 共用 —— 同一函数,链序不可能漂移)。

    层内(细压粗):条目(alias_key)> 实例(system × 执行标签 env_id)
    > 服务(base)> **层默认**(§11.4:每容器层依次应用层默认、服务、
    实例、别名 —— 默认在单源合并内铺底,物化层不再单独回填);层间
    (tiers 序,粗先细后,字段级覆盖):公共 < 项目;最顶:执行配置
    覆盖层(``exec_overrides``,null = 显式注入 JSON null,与值表语义
    同型)。逐 path 返回 ``{"value", "source"}``,source 形如
    ``{scope}:{scopeId}:alias`` / ``:instance:{envId}`` / ``:base`` /
    ``{scope}:{scopeId}:defaults`` / ``exec_config`` —— 执行链只取
    value,预览消费全部(§5 守则「自证每个值的来路」)。
    ``env_id=None``(标签链全空/导入析出)→ 实例档跳过,不猜环境。

    §11.4 remove(复核 P1):``exec_removals``(解码后的**请求体路径**)
    在值覆盖之后按序删除 —— 值表键带 $. 前缀两形并存,按体路径归一
    匹配,父对象删除连带子键;被删键从生效对象消失,预览与物化同源
    (同一 merged),物化不得再从默认表回填;同层更高档/高层(配置
    值覆盖)可重新定义已删除的键。
    """
    merged: dict[str, dict] = {}
    for t in tiers:
        for path, value in (await carry_store.get_defaults(db, t)).items():
            merged[path] = {"value": value,
                            "source": f"{t[0]}:{t[1]}:defaults"}
        t_base = await carry_store.get_bindings(db, base, t)
        t_inst = (await carry_store.get_instance_bindings(
            db, instance_key, env_id, t)
            if instance_key and env_id is not None else {})
        t_alias = (await carry_store.get_bindings(db, alias_key, t)
                   if alias_key and alias_key != base else {})
        for path in set(t_base) | set(t_inst) | set(t_alias):
            if path in t_alias:
                merged[path] = {"value": t_alias[path],
                                "source": f"{t[0]}:{t[1]}:alias"}
            elif path in t_inst:
                merged[path] = {"value": t_inst[path],
                                "source": f"{t[0]}:{t[1]}:instance:{env_id}"}
            else:
                merged[path] = {"value": t_base[path],
                                "source": f"{t[0]}:{t[1]}:base"}
    if exec_overrides:
        for path, value in exec_overrides.items():
            merged[path] = {"value": value, "source": "exec_config"}
    for rem_path in exec_removals or []:
        # §11.4(复核 P1):指针按**最终请求体路径**寻址 —— 值表键可能
        # 带 $. 前缀(两形并存),按体路径归一匹配;父对象删除连带子键
        # (设计原例 /headers 连带 $.headers.* / headers.*)
        for k in [k for k in merged
                  if (k == rem_path
                      or k.startswith("$.") and k[2:] == rem_path
                      or _body_path(k).startswith(rem_path + "."))]:
            del merged[k]
    return merged


def _body_path(key: str) -> str:
    """值表键 → 最终请求体路径($. 前缀剥除;两形键统一寻址)。"""
    return key[2:] if key.startswith("$.") else key


async def build_carry_context(
    db: AsyncSession, definition: dict,
    ui_field_states: dict | None = None,
    *,
    project_id: int | None = None,
    user_id: int | None = None,
    bindings: dict | None = None,
    exec_overrides: dict[str, dict[str, str | None]] | None = None,
    exec_removals: "dict[str, list[str]] | None" = None,
    env_id: int | None = None,
) -> CarryContext:
    """dispatch 预解析入口:plate 目录 + step 增量 → 每 step 的 carry 面。

    authz M2a S4 作用域分层(D3 + 区模型收敛):tier 序 = 公共项目层 <
    项目层;层内键域(§8.9,**细到粗**):身份条目名 > 实例(system, env)
    > 服务名 > 层默认 —— **实例档压过服务档**(部署差异化默认值:
    测试/预发布/生产同字段不同值),条目键压过一切;原「系统名」粗档
    已由实例档替换(§8.9,存量 0 行守卫迁移 0063)。执行配置分层⑥
    (决策 8):**个人层不再存在** —— 个人缺省 carry 的家是默认执行配置
    (``exec_overrides`` 覆盖层),``user_id`` 参数仅为签名兼容,不构成 tier。

    实例档环境 = **执行标签**(``env_id``,与地址取数同源:有效身份 >
    项目默认 > 平台默认;env_mixed 已被预检硬拦,执行级恒单值)。
    ``env_id=None``(标签链全空 / 导入析出等无执行上下文)→ 实例档
    跳过,仅按 服务 < 条目 合成 —— 与 §8.4「环境不承载配置层」一致,
    环境位只作为实例键坐标进入,不构成独立覆盖层。

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

    # ② 服务引用 → 条目表优先解析 → 绑定值(None = 解析失败,整步跳过)
    # S4:tier 序(公共项目层恒在 < 项目层);分层⑥:个人层已收编为默认
    # 执行配置(决策 8),user_id 不再构成 tier
    tiers: list[tuple[str, int]] = [await carry_store.public_scope(db)]
    if project_id is not None:
        tiers.append(("project", project_id))
    # 层默认原样快照(§11.4 复核 P1 起仅供**无锚点降级门控**取值 ——
    # 锚点步骤的默认已随 merge_carry_tiers 入单源合并,物化层不再把
    # 本快照当回填源:被选中配置删除的键不得从这里回流)
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
    # 系统派生(§8.9 实例档坐标的 system 半边):base → services.system
    # 批量一次
    from ..models.service import Service as DBService
    service_bindings: dict[str, dict[str, str | None] | None] = {}
    resolved_bases = {
        raw: await service_names.resolve_base_with_aliases(db, raw)
        for raw in raw_services}
    system_of: dict[str, str] = {}
    bases_known = {b for b in resolved_bases.values() if b}
    if bases_known:
        system_of = dict((await db.execute(
            select(DBService.name, DBService.system).where(
                DBService.name.in_(bases_known)))).all())
    for raw in raw_services:
        base = resolved_bases[raw]
        if base is None:
            logger.warning(
                "carry_injection: service {!r} 不在已知服务集(裸声明)— 该 "
                "step 跳过 carry 填充", raw)
            service_bindings[raw] = None
        else:
            # 键域单源合并(§8.9,merge_carry_tiers 与预览共用):
            # 条目 > 实例(system × 执行标签 env)> 服务 + 执行配置
            # 覆盖压顶 —— 执行链只取 value(来源标注是预览面的诉求)
            merged = await merge_carry_tiers(
                db, tiers, base=base,
                alias_key=effective_alias(raw, bindings),
                instance_key=system_of.get(base) or None,
                env_id=env_id,
                exec_overrides=(exec_overrides or {}).get(base),
                exec_removals=(exec_removals or {}).get(base))
            service_bindings[raw] = {
                path: m["value"] for path, m in merged.items()}

    return CarryContext(step_fields=step_fields,
                        service_bindings=service_bindings,
                        global_defaults=defaults)
