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

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from . import carry_store, plate_client, service_names
from .run_materialize import CarryContext


async def _carry_face(endpoint_id: str) -> dict[str, str]:
    """plate /full → {path: type};任何失败 → {}(降级)。

    垃圾 200 体(json 抛错/信封非 dict)同样降级 — 模块契约是
    「plate 全部失败 → 空面」,不让单端点的坏包打断整单 carry。
    """
    client = plate_client.get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
        if resp.status_code != 200:
            return {}
        item = (resp.json().get("data") or {}).get("item")
    except Exception:  # noqa: BLE001 — httpx 全家 + 垃圾体,统一降级
        return {}
    if not isinstance(item, dict):
        return {}
    carry = ((item.get("request") or {}).get("carry")) or {}
    return {str(p): str(e.get("type") or "string")
            for p, e in carry.items() if isinstance(e, dict)}


def _endpoint_id(step: dict) -> Any:
    """step → view_hints.endpoint_id;api/view_hints 非 dict 时 None。"""
    api = step.get("api")
    hints = (api.get("view_hints") or {}) if isinstance(api, dict) else {}
    if not isinstance(hints, dict):
        return None
    return hints.get("endpoint_id")


def _step_service(step: dict) -> Any:
    """step → api.service;api 非 dict 时 None(防御,同 _apply_carry)。"""
    api = step.get("api")
    return api.get("service") if isinstance(api, dict) else None


async def build_carry_context(db: AsyncSession, definition: dict) -> CarryContext:
    # 索引契约:枚举原始列表(跳过非 dict),不用过滤后的下标。
    raw_steps: list = list(definition.get("steps") or [])

    # ① 锚点 → carry 面(按 endpoint_id 去重批量,不逐 step 打 plate)
    endpoint_ids: dict[str, None] = {}
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        eid = _endpoint_id(step)
        if eid:
            endpoint_ids.setdefault(eid, None)
    faces: dict[str, dict[str, str]] = {
        eid: await _carry_face(eid) for eid in endpoint_ids
    }
    step_fields: dict[int, dict[str, str]] = {}
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue
        eid = _endpoint_id(step)
        if eid and faces.get(eid):
            step_fields[i] = faces[eid]

    # ② 服务引用 → derive_base 解析 → 绑定值(None = 解析失败,整步跳过)
    catalog = await service_names.catalog_service_names()
    defaults = await carry_store.get_defaults(db)
    raw_services: dict[str, None] = {}
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        svc = _step_service(step)
        if isinstance(svc, str) and svc:
            raw_services.setdefault(svc, None)
    service_bindings: dict[str, dict[str, str | None] | None] = {}
    for raw in raw_services:
        base = service_names.derive_base(raw, catalog)
        if base is None:
            logger.warning(
                "carry_injection: service {!r} 不在目录(裸声明)— 该 step "
                "跳过 carry 填充", raw)
            service_bindings[raw] = None
        else:
            service_bindings[raw] = await carry_store.get_bindings(db, base)

    return CarryContext(step_fields=step_fields,
                        service_bindings=service_bindings,
                        global_defaults=defaults)
