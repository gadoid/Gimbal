"""carry 值层读写(spec §3.2 API 的 store 面)。

PUT 语义 = 整体替换(行集 diff:删缺键、upsert 在键);调用方负责 commit。

authz M2a S4 作用域分层:读写都带 ``scope``(('project', 项目id) |
('user', 用户id);公共项目行 = 旧全局层);``scope=None``(缺省)= 公共
项目层 —— 与旧「全局表」语义同型,存量调用方零改动。tier 合并在
``carry_injection.build_carry_context``(公共层 < 项目/个人层)。
"""
from __future__ import annotations

from sqlalchemy import delete, select

from ..models.carry_binding import CarryGlobalDefault, CarryServiceBinding
from .field_state_resolution import carry_face

Scope = "tuple[str, int]"


async def public_scope(db) -> "tuple[str, int]":
    """公共项目层(旧全局层的 S4 形态)。"""
    from ..models.project import Project

    pid = (await db.execute(select(Project.id).where(
        Project.kind == "public"))).scalar()
    return ("project", pid if pid is not None else 0)


async def _scoped(db, scope: "tuple[str, int] | None") -> "tuple[str, int]":
    return scope if scope is not None else await public_scope(db)


async def visible_scopes(db, user) -> "list[tuple[str, int]]":
    """读面可见作用域(10.5):公共项目 + 我所在项目。个人层随执行配置
    分层⑥收编为默认执行配置(决策 8)—— 不再是 carry 值层。"""
    from ..models.project import ProjectMember

    scopes = [await public_scope(db)]
    pids = (await db.execute(select(ProjectMember.project_id).where(
        ProjectMember.user_id == user.id))).scalars().all()
    scopes += [("project", p) for p in pids if ("project", p) not in scopes]
    return scopes


async def get_bindings(db, service_name: str,
                       scope: "tuple[str, int] | None" = None,
                       ) -> dict[str, str | None]:
    scope = await _scoped(db, scope)
    rows = (await db.execute(
        select(CarryServiceBinding).where(
            CarryServiceBinding.service_name == service_name,
            CarryServiceBinding.scope == scope[0],
            CarryServiceBinding.scope_id == scope[1])
    )).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_bindings(
    db,
    service_name: str,
    entries: dict[str, str | None],
    *,
    updated_by_id: int | None,
    updated_by_name: str,
    scope: "tuple[str, int] | None" = None,
) -> None:
    scope = await _scoped(db, scope)
    await db.execute(delete(CarryServiceBinding).where(
        CarryServiceBinding.service_name == service_name,
        CarryServiceBinding.scope == scope[0],
        CarryServiceBinding.scope_id == scope[1]))
    for path, value in sorted(entries.items()):
        db.add(CarryServiceBinding(
            service_name=service_name,
            scope=scope[0], scope_id=scope[1],
            field_path=path, value=value,
            updated_by_id=updated_by_id, updated_by_name=updated_by_name,
        ))


async def get_defaults(db, scope: "tuple[str, int] | None" = None,
                       ) -> dict[str, str | None]:
    scope = await _scoped(db, scope)
    rows = (await db.execute(select(CarryGlobalDefault).where(
        CarryGlobalDefault.scope == scope[0],
        CarryGlobalDefault.scope_id == scope[1]))).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_defaults(
    db,
    entries: dict[str, str | None],
    *,
    updated_by_id: int | None,
    updated_by_name: str,
    scope: "tuple[str, int] | None" = None,
) -> None:
    scope = await _scoped(db, scope)
    await db.execute(delete(CarryGlobalDefault).where(
        CarryGlobalDefault.scope == scope[0],
        CarryGlobalDefault.scope_id == scope[1]))
    for path, value in sorted(entries.items()):
        db.add(CarryGlobalDefault(
            field_path=path, value=value,
            scope=scope[0], scope_id=scope[1],
            updated_by_id=updated_by_id, updated_by_name=updated_by_name,
        ))


async def carry_drift(db, scope: "tuple[str, int] | None" = None) -> dict:
    """plate carry 面 vs 绑定表 paths 三类 diff(spec §7;结构 diff,非 semver)。

    renamed 启发式:单 orphaned × 单 uncovered(同 type 不可知 —— 绑定行
    无类型)→ 配对建议;多候选不猜,人工构造 op。

    对齐服务同样入报告(orphaned/uncovered 为空)— Task 11 测试 2 契约:
    面板要能展示"已检查、无漂移",而非只列问题服务。

    plate 列表拉不到 → plateReachable=False + face 视为空(bound 全成
    orphaned)— 调用方须先看信号再渲染清单,防把不可达误读成漂移;
    单端点 /full 失败 → 该端点面缺席,不阻塞其余。

    键归一(配套方案 §2.3):``service_name`` 允许存别名全名(稀疏覆盖
    层)。Plate 面只有目录服务,别名键的 face 取其 ``derive_base`` base
    的面;别名行只报 orphaned(别名是覆盖层,uncovered 是 base 行的
    事),``baseService`` 标注归一关系供面板标注「别名 → base」。
    plate 不可达时无从归一,键原样参与(既有全 orphaned 降级不变)。

    返回 ``{"services": [...], "plateReachable": bool}``。
    """
    from .adaptation_service import _plate_list_endpoints, _plate_full_endpoint
    from . import service_names
    from .plate_client import PlateUnavailableError

    stmt = select(CarryServiceBinding)
    if scope is not None:
        # S4:漂移面按层(默认公共项目层;无公共项目防御分支 0 也归入)
        stmt = stmt.where(CarryServiceBinding.scope == scope[0],
                          CarryServiceBinding.scope_id == scope[1])
    rows = (await db.execute(stmt)).scalars().all()
    bound_by_service: dict[str, set[str]] = {}
    for r in rows:
        bound_by_service.setdefault(r.service_name, set()).add(r.field_path)

    # 面并集(按服务);plate_services = 目录服务全集(键归一的解析域)
    face_by_service: dict[str, set[str]] = {}
    plate_services: set[str] = set()
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
        plate_services.add(svc)
        try:
            full = await _plate_full_endpoint(eid)
        except PlateUnavailableError:
            continue
        if full is None:
            continue
        # 解析态 == 'carry' 投影(2026-09-05 目录化 §4.1(a)):端点级
        # entry.state 共识默认 —— 与 carry 路由 service_fields 同口径
        # (值表是环境级,不 join step 增量);投影走单一实现
        # field_state_resolution.carry_face(与 carry_injection 同款,
        # 含祖先吸收:整容器是绑定/注入单元)
        decls = ((full.get("request") or {}).get("declarations")) or []
        face_by_service.setdefault(svc, set()).update(carry_face(decls))

    out: list[dict] = []
    for svc in sorted(set(bound_by_service) | set(face_by_service)):
        bound = bound_by_service.get(svc, set())
        # 键归一:别名键(不在目录)→ 对 base 的面做 diff;只出 orphaned
        if reachable and svc not in face_by_service:
            # b2.5(D-M 第三处):drift 孤儿 diff 也走别名表优先 —— external
            # 别名键(不守命名规约)在此归一;目录兜底在 helper 内。
            base = await service_names.resolve_base_with_aliases(db, svc)
            if base and base != svc:
                face = face_by_service.get(base, set())
                out.append({"service": svc, "baseService": base,
                            "orphaned": sorted(bound - face),
                            "uncovered": [], "renamedSuggestions": []})
                continue
        face = face_by_service.get(svc, set())
        orphaned = sorted(bound - face)
        uncovered = sorted(face - bound)
        suggestions = ([{"from": orphaned[0], "to": uncovered[0]}]
                       if len(orphaned) == 1 and len(uncovered) == 1 else [])
        out.append({"service": svc, "baseService": None,
                    "orphaned": orphaned,
                    "uncovered": uncovered,
                    "renamedSuggestions": suggestions})
    return {"services": out, "plateReachable": reachable}
