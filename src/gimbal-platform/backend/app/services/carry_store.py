"""carry 值层读写(spec §3.2 API 的 store 面)。

PUT 语义 = 整体替换(行集 diff:删缺键、upsert 在键);调用方负责 commit。
"""
from __future__ import annotations

from sqlalchemy import delete, select

from ..models.carry_binding import CarryGlobalDefault, CarryServiceBinding


async def get_bindings(db, service_name: str) -> dict[str, str | None]:
    rows = (await db.execute(
        select(CarryServiceBinding).where(
            CarryServiceBinding.service_name == service_name)
    )).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_bindings(
    db, service_name: str, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryServiceBinding).where(
        CarryServiceBinding.service_name == service_name))
    for path, value in sorted(entries.items()):
        db.add(CarryServiceBinding(service_name=service_name,
                                   field_path=path, value=value,
                                   updated_by=updated_by))


async def get_defaults(db) -> dict[str, str | None]:
    rows = (await db.execute(select(CarryGlobalDefault))).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_defaults(
    db, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryGlobalDefault))
    for path, value in sorted(entries.items()):
        db.add(CarryGlobalDefault(field_path=path, value=value,
                                  updated_by=updated_by))


async def carry_drift(db) -> dict:
    """plate carry 面 vs 绑定表 paths 三类 diff(spec §7;结构 diff,非 semver)。

    renamed 启发式:单 orphaned × 单 uncovered(同 type 不可知 —— 绑定行
    无类型)→ 配对建议;多候选不猜,人工构造 op。

    对齐服务同样入报告(orphaned/uncovered 为空)— Task 11 测试 2 契约:
    面板要能展示"已检查、无漂移",而非只列问题服务。

    plate 列表拉不到 → plateReachable=False + face 视为空(bound 全成
    orphaned)— 调用方须先看信号再渲染清单,防把不可达误读成漂移;
    单端点 /full 失败 → 该端点面缺席,不阻塞其余。

    返回 ``{"services": [...], "plateReachable": bool}``。
    """
    from .adaptation_service import _plate_list_endpoints, _plate_full_endpoint
    from .plate_client import PlateUnavailableError

    rows = (await db.execute(select(CarryServiceBinding))).scalars().all()
    bound_by_service: dict[str, set[str]] = {}
    for r in rows:
        bound_by_service.setdefault(r.service_name, set()).add(r.field_path)

    # 面并集(按服务)
    face_by_service: dict[str, set[str]] = {}
    reachable = True
    try:
        items = await _plate_list_endpoints()
    except PlateUnavailableError:
        items = []
        reachable = False
    for item in items:
        svc = item.get("service")
        eid = item.get("id")
        if not svc or not eid:
            continue
        try:
            full = await _plate_full_endpoint(eid)
        except PlateUnavailableError:
            continue
        if full is None:
            continue
        # wire 已归一化:读 request.declarations 的 carry 通道条目
        # (与 carry_injection._carry_face / carry 路由同款投影)
        decls = ((full.get("request") or {}).get("declarations")) or []
        paths = {str(e["path"]) for e in decls
                 if isinstance(e, dict) and e.get("channel") == "carry"
                 and e.get("path")}
        face_by_service.setdefault(svc, set()).update(paths)

    out: list[dict] = []
    for svc in sorted(set(bound_by_service) | set(face_by_service)):
        bound = bound_by_service.get(svc, set())
        face = face_by_service.get(svc, set())
        orphaned = sorted(bound - face)
        uncovered = sorted(face - bound)
        suggestions = ([{"from": orphaned[0], "to": uncovered[0]}]
                       if len(orphaned) == 1 and len(uncovered) == 1 else [])
        out.append({"service": svc, "orphaned": orphaned,
                    "uncovered": uncovered,
                    "renamedSuggestions": suggestions})
    return {"services": out, "plateReachable": reachable}
