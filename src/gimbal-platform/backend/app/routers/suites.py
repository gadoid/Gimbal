"""Suite 路由(权限域二期 P1,《Suite成员层、引用分享与浏览镜头-设计
方案》§9 的 P1 子集:CRUD + 成员管理 + 反查;run 见本文件运行节,
publish/分享端点随 P2)。

安全边界(§6.3,唯一的安全设计点):**suite 里只能放属主自己的
场景** —— 应用层先校验返回 404(不泄露存在性),库层组合外键兜底
(绕过应用层直写也被约束拒绝),**admin 无豁免**(admin 经组把 A 的
内容洗给 B 的通道不存在,§7.7)。

P1 可见性:suite 恒 private(P2 才有发布入口)。读 = 属主 ∨ admin,
非属主 GET 详情 404;写 = 属主 ∨ admin(治理)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.execution import Execution
from ..models.suite import Suite, SuiteMember
from ._error_mapping import not_found_404
from ._ownership import ensure_owner
from ..schemas.scenario_composer import RunRequest
from ..schemas.suite import (
    SuiteCompositionIn, SuiteCreateIn, SuiteDetailOut, SuiteLookupItem,
    SuiteMembersAddIn, SuiteMembersOrderIn, SuiteMemberOut, SuitePageOut,
    SuitePatchIn, SuiteSummaryOut,
)
from ..services import run_dispatcher, scenario_store, scheme_store

router = APIRouter(prefix="/suites", tags=["suites"])
# 反查路由(prefix=/scenarios;与 run_schemes/data_sets 的嵌套先例同款,
# 不得与 scenarios.py 的 catch-all 冲突 —— 路径段 suites 独占)
lookup_router = APIRouter(prefix="/scenarios", tags=["suites"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_suite(db: AsyncSession, suite_id: int) -> Suite:
    row = await db.get(Suite, suite_id)
    if row is None:
        raise not_found_404("suite", str(suite_id))
    return row


def _require_read(user: CurrentUser, suite: Suite) -> None:
    """读闸(同步快路径):private → 属主 ∨ admin,否则 404(不泄露)。
    P2 引用/公共读由 ``_require_read_async`` 承担(§7.6)。"""
    if user.role != "admin" and user.id != suite.owner_id             and suite.visibility != "public":
        raise not_found_404("suite", str(suite.id))


async def _require_read_async(db, user: CurrentUser, suite: Suite) -> None:
    """读闸(完整判定,§7.6):public ∨ 属主 ∨ admin ∨ suite 引用。"""
    if user.role == "admin" or user.id == suite.owner_id             or suite.visibility == "public":
        return
    from ._ownership import has_suite_ref
    if not await has_suite_ref(db, user.id, suite.id):
        raise not_found_404("suite", str(suite.id))


async def _require_run_async(db, user: CurrentUser, suite: Suite) -> None:
    """运行闸(§7.6 can_run_suite):属主 ∨ admin ∨ suite 引用。
    写闸(_require_write)不变 —— 成员管理仍是属主 ∨ admin。"""
    if user.role == "admin" or user.id == suite.owner_id:
        return
    from ._ownership import has_suite_ref
    if not await has_suite_ref(db, user.id, suite.id):
        raise not_found_404("suite", str(suite.id))


def _require_write(user: CurrentUser, suite: Suite) -> None:
    ensure_owner(
        user, suite.owner_id,
        {"code": "not_owner",
         "message": "only the suite's owner (or admin) can manage it"},
    )


def _iso(v) -> str | None:
    return v.isoformat() if v is not None else None


async def _member_count(db: AsyncSession, suite_id: int) -> int:
    return int((await db.execute(
        select(func.count()).where(SuiteMember.suite_id == suite_id)
    )).scalar() or 0)


def _is_draft(suite: Suite) -> bool:
    return bool((suite.mode_config or {}).get("draft"))


def _summary(suite: Suite, member_count: int) -> SuiteSummaryOut:
    return SuiteSummaryOut(
        suiteId=suite.id, name=suite.name, description=suite.description,
        visibility=suite.visibility, mode=suite.mode,
        memberCount=member_count, rev=suite.rev, isDraft=_is_draft(suite),
        createdAt=_iso(suite.created_at), updatedAt=_iso(suite.updated_at),
    )


async def _access_and_caps(
    db: AsyncSession, user: CurrentUser, suite: Suite,
) -> dict:
    """§7.6 判定投影(重构方案:前端不自己推导角色)。调用前读闸
    须已过;access 为 None 仅发生在公共读者,能力位全 False。"""
    if user.id == suite.owner_id:
        access = "owner"
    elif user.role == "admin":
        access = "admin"
    elif suite.visibility == "public":
        access = "public"
    else:
        from ._ownership import has_suite_ref
        access = ("ref" if await has_suite_ref(db, user.id, suite.id)
                  else None)
    if access is None:
        return {}
    return {
        "access": access,
        # 写 = 属主 ∨ admin(治理);public 先复制再跑(不变量 7);
        # admin 不可代发分享(§8.1)
        "canEdit": access in ("owner", "admin"),
        "canRun": access in ("owner", "admin", "ref"),
        "canShare": access == "owner",
    }


async def _detail_out(
    db: AsyncSession, user: CurrentUser, suite: Suite,
    members: list[SuiteMember] | None = None,
) -> SuiteDetailOut:
    if members is None:
        members = await _ordered_members(db, suite.id)
    out = SuiteDetailOut(
        suiteId=suite.id, name=suite.name, description=suite.description,
        visibility=suite.visibility, mode=suite.mode,
        memberCount=len(members), rev=suite.rev, isDraft=_is_draft(suite),
        modeConfig=suite.mode_config or {},
        createdAt=_iso(suite.created_at), updatedAt=_iso(suite.updated_at),
        members=await _members_out(db, members),
    )
    for k, v in (await _access_and_caps(db, user, suite)).items():
        setattr(out, k, v)
    return out


async def _ordered_members(
    db: AsyncSession, suite_id: int,
) -> list[SuiteMember]:
    rows = (await db.execute(
        select(SuiteMember).where(SuiteMember.suite_id == suite_id)
        .order_by(SuiteMember.sort, SuiteMember.added_at)
    )).scalars().all()
    return list(rows)


async def _members_out(
    db: AsyncSession, members: list[SuiteMember],
) -> list[SuiteMemberOut]:
    """成员摘要:名称/模块来自场景行(行缺失 = 场景被删的瞬态,名字
    回落 scenarioId;FK CASCADE 会随即收掉成员行,这里只是读窗口)。"""
    out: list[SuiteMemberOut] = []
    for m in members:
        scen = await scenario_store.get_row(db, m.scenario_id)
        meta = scenario_store._meta_from_row(scen) if scen is not None else None
        out.append(SuiteMemberOut(
            scenarioId=m.scenario_id,
            name=(meta.name if meta and meta.name else m.scenario_id),
            module=(meta.module or "") if meta else "",
            visibility=(scen.visibility or "private") if scen else "private",
            role=m.role or "main",
            sort=m.sort, addedAt=_iso(m.added_at),
        ))
    return out


# ── CRUD ───────────────────────────────────────────────────────────
@router.get("", response_model=SuitePageOut)
async def list_suites(
    user: CurrentUser, db: DbSession,
    scope: Literal["mine", "all"] = "all",
    visibility: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 100,
) -> SuitePageOut:
    """suite 列表。API 默认 all(向后兼容惯例);P1 无引用分享 →
    非 admin 的 all ≡ mine(自己的);admin 的 all = 全量(治理)。"""
    # 浏览镜头口径与场景库一致(§5.1):mine = owner 过滤,admin 同样生效。
    # P2 引用(§7.6):非 admin 的 all = public ∨ 自己的 ∨ 被引用的。
    # visibility=public(§5.1,场景列表同款):显式传时 scope 不叠加,
    # 只出公共 Suite —— 公共库页口径(重构方案 D-3 公共 Suite 分区)。
    from sqlalchemy import exists, select as _select
    from ..models.share_ref import ShareRef
    if visibility == "public":
        clauses = [Suite.visibility == "public"]
    elif scope == "mine":
        clauses = [Suite.owner_id == user.id]
    elif user.role == "admin":
        clauses = []
    else:
        clauses = [or_(
            Suite.owner_id == user.id,
            Suite.visibility == "public",
            exists(_select(ShareRef.id).where(
                ShareRef.grantee_user_id == user.id,
                ShareRef.suite_id == Suite.id)).correlate(Suite),
        )]
    rows = (await db.execute(
        select(Suite).where(*clauses).order_by(Suite.updated_at.desc())
    )).scalars().all()
    total = len(rows)
    start = (page - 1) * page_size
    items = []
    for s in rows[start : start + page_size]:
        items.append(_summary(s, await _member_count(db, s.id)))
    return SuitePageOut(items=items, total=total, page=page, pageSize=page_size)


@router.post("", response_model=SuiteSummaryOut, status_code=201)
async def create_suite(
    user: CurrentUser, db: DbSession, body: SuiteCreateIn,
) -> SuiteSummaryOut:
    # 草稿口径(重构方案):name 缺省 = 画布首次拖入创建草稿,服务端
    # 生成不重名草稿名;草稿不计入 SUITE_CAP、单独 SUITE_DRAFT_CAP
    #(团队规模有界,JSON 的 draft 标记在 Python 侧过滤,不进 SQL)
    own_cfgs = (await db.execute(
        select(Suite.mode_config).where(Suite.owner_id == user.id)
    )).all()
    n_draft = sum(1 for (cfg,) in own_cfgs if (cfg or {}).get("draft"))
    is_draft = body.name is None
    if is_draft and n_draft >= settings.SUITE_DRAFT_CAP:
        raise HTTPException(status_code=409, detail={
            "code": "suite_draft_cap_exceeded",
            "message": (f"draft cap per user is {settings.SUITE_DRAFT_CAP}"
                        " (完成编排或清理草稿后再创建)")})
    if len(own_cfgs) - n_draft >= settings.SUITE_CAP:
        raise HTTPException(status_code=409, detail={
            "code": "suite_cap_exceeded",
            "message": f"suite cap per user is {settings.SUITE_CAP}"})
    existing = {n for (n,) in (await db.execute(
        select(Suite.name).where(Suite.owner_id == user.id)))}
    name = body.name
    if name is None:
        base = "未命名 Suite"
        name = base
        i = 1
        while name in existing:
            i += 1
            name = f"{base} {i}"
    elif name in existing:
        raise HTTPException(status_code=409, detail={
            "code": "suite_name_conflict",
            "message": "同名 suite 已存在(属主内唯一)"})
    suite = Suite(name=name, description=body.description,
                  owner_id=user.id,
                  mode_config=({"draft": True} if is_draft else {}))
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return _summary(suite, 0)


@router.get("/{suite_id}", response_model=SuiteDetailOut)
async def get_suite(user: CurrentUser, db: DbSession, suite_id: int) -> SuiteDetailOut:
    suite = await _load_suite(db, suite_id)
    await _require_read_async(db, user, suite)
    return await _detail_out(db, user, suite)


@router.patch("/{suite_id}", response_model=SuiteSummaryOut)
async def patch_suite(
    user: CurrentUser, db: DbSession, suite_id: int, body: SuitePatchIn,
) -> SuiteSummaryOut:
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    if body.name is not None and body.name != suite.name:
        dup = (await db.execute(
            select(func.count()).where(Suite.owner_id == suite.owner_id,
                                       Suite.name == body.name,
                                       Suite.id != suite.id)
        )).scalar()
        if dup:
            raise HTTPException(status_code=409, detail={
                "code": "suite_name_conflict",
                "message": "同名 suite 已存在(属主内唯一)"})
        suite.name = body.name
    if body.description is not None:
        suite.description = body.description
    if body.clearDraft and _is_draft(suite):
        # 完成编排:清草稿标记(正式名称同请求落);改的是编排态 → 推进 rev
        cfg = dict(suite.mode_config or {})
        cfg["draft"] = False
        suite.mode_config = cfg
        suite.rev += 1
    await db.commit()
    await db.refresh(suite)
    return _summary(suite, await _member_count(db, suite.id))


@router.delete("/{suite_id}", status_code=204)
async def delete_suite(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> Response:
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    # 重构方案:有引用者时,删除后通知引用者(与处置路径
    # share_ref_resource_deleted 同口径);须在级联删引用行**之前**取名单
    from ..models.share_ref import ShareRef
    from ..services import notifications as notify_svc
    referrers = (await db.execute(
        select(ShareRef.grantee_user_id).where(
            ShareRef.suite_id == suite.id))).scalars().all()
    await db.delete(suite)  # 成员行随组合外键 CASCADE,场景不受影响
    await db.commit()
    for uid in referrers:
        try:
            await notify_svc.create_notification(
                db, user_id=uid,
                type_="share_ref_resource_deleted",
                title=f"引用失效:suite#{suite.id}",
                body="该 Suite 已被删除,引用分享随之结束",
                link=None, resource_type="suite",
                resource_id=str(suite.id))
        except Exception:  # noqa: BLE001 — 通知 best-effort,不阻断删除
            await db.rollback()
    return Response(status_code=204)


@router.post("/{suite_id}/fork", status_code=201)
async def fork_public_suite(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> dict:
    """公共读者「复制到我的」(重构方案):公共 Suite 深拷贝为自己名下的
    私有 Suite,含编排配置重映射(约束 8);读闸 + 公共可见(非公共 404)。
    被引用者的「转为副本」走既有 POST /shares/{id}/fork,不经此端点。"""
    from ..services import audit as audit_svc
    from ..services.suite_copy import deep_copy_suite, suite_owner_display
    suite = await _load_suite(db, suite_id)
    await _require_read_async(db, user, suite)
    if suite.visibility != "public":
        raise not_found_404("suite", str(suite_id))
    out = await deep_copy_suite(
        db, suite, user, await suite_owner_display(db, suite))
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action="suite.public_fork",
        resource_type="suite", resource_id=str(suite.id),
        detail={"copyId": out["suiteId"], "name": out["name"]})
    return {"suiteId": out["suiteId"], "suiteName": out["name"],
            "memberCount": out["count"], "mode": out["mode"]}


# ── 成员管理 ───────────────────────────────────────────────────────
@router.post("/{suite_id}/members", response_model=SuiteDetailOut)
async def add_members(
    user: CurrentUser, db: DbSession, suite_id: int, body: SuiteMembersAddIn,
) -> SuiteDetailOut:
    """批量加入。安全边界(§6.3):成员必须是 **suite 属主自己的**
    场景 —— 他人场景(含不存在的)一律 404,不泄露存在性;admin 也
    无豁免。库层组合外键兜底直写。"""
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)

    existing = {m.scenario_id for m in await _ordered_members(db, suite.id)}
    next_sort = (
        int((await db.execute(
            select(func.max(SuiteMember.sort))
            .where(SuiteMember.suite_id == suite.id)
        )).scalar() or -1) + 1
    )
    added = 0
    for sid in dict.fromkeys(body.scenarioIds):  # 去重保序
        if sid in existing:
            continue
        scen = await scenario_store.get_row(db, sid)
        # 一刀切(§6.3):scenario 属主 ≠ suite 属主 → 404。
        if scen is None or scen.owner_id != suite.owner_id:
            await db.rollback()
            raise not_found_404("scenario", sid)
        if len(existing) + added + 1 > settings.SUITE_MEMBER_CAP:
            await db.rollback()
            raise HTTPException(status_code=409, detail={
                "code": "suite_member_cap_exceeded",
                "message": (f"suite member cap is "
                            f"{settings.SUITE_MEMBER_CAP}")})
        # P2 §7.9(不变量第二入口):公共 suite 加未发布成员不直接拒绝,
        # 走发布确认 —— 无 publishUnpublished 标志 → 409 列出待发布成员
        #(前端弹确认框「这些成员及其数据集将一并公开」);有标志 →
        # 成员发布 + 入组同事务完成(数据集随场景可见性公开)。
        if (suite.visibility == "public"
                and (scen.visibility or "private") != "public"):
            if not body.publishUnpublished:
                await db.rollback()
                raise HTTPException(status_code=409, detail={
                    "code": "suite_member_publish_required",
                    "message": ("suite is public: unpublished members must "
                                "be published to join (confirm to publish "
                                "them and their datasets)"),
                    "pendingPublish": [sid]})
            scen.visibility = "public"
        db.add(SuiteMember(
            suite_id=suite.id, scenario_id=sid, owner_id=suite.owner_id,
            sort=next_sort,
        ))
        next_sort += 1
        added += 1
    if added:
        suite.rev += 1
    await db.commit()
    # suite 被 UPDATE(rev)→ updated_at(服务端 onupdate)过期,
    # commit 后访问会触发异步懒加载(MissingGreenlet),显式 refresh
    await db.refresh(suite)
    return await _detail_out(db, user, suite)


@router.patch("/{suite_id}/members/order", response_model=SuiteDetailOut)
async def reorder_members(
    user: CurrentUser, db: DbSession, suite_id: int, body: SuiteMembersOrderIn,
) -> SuiteDetailOut:
    """整表排序:列表顺序即 sort(0..n-1);清单必须恰为当前成员全集。"""
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    members = {m.scenario_id: m for m in await _ordered_members(db, suite.id)}
    incoming = list(dict.fromkeys(body.scenarioIds))
    if set(incoming) != set(members) or len(incoming) != len(members):
        raise HTTPException(status_code=422, detail={
            "code": "members_order_mismatch",
            "message": "排序清单必须恰为当前成员全集(无遗漏、无多余)"})
    for idx, sid in enumerate(incoming):
        members[sid].sort = idx
    suite.rev += 1
    await db.commit()
    await db.refresh(suite)  # updated_at 服务端 onupdate 同上
    return await _detail_out(db, user, suite)


@router.delete("/{suite_id}/members/{scenario_id}", status_code=204)
async def remove_member(
    user: CurrentUser, db: DbSession, suite_id: int, scenario_id: str,
) -> Response:
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    m = await db.get(SuiteMember, (suite_id, scenario_id))
    if m is not None:
        await db.delete(m)
        # 约束 6:移除成员同一事务清理编排配置引用并推进 rev;
        # CASCADE 只删成员行不代劳这些(清理实现单点在 suite_copy 服务)
        from ..services.suite_copy import scrub_config_references
        suite.mode_config = scrub_config_references(
            dict(suite.mode_config or {}), {scenario_id})
        suite.rev += 1
        await db.commit()
        await db.refresh(suite)  # updated_at 服务端 onupdate 同上
    return Response(status_code=204)


# ── 整体保存(重构方案 composition)───────────────────────────────
def _bad_cfg(message: str, **extra) -> HTTPException:
    payload = {"code": "mode_config_invalid", "message": message}
    payload.update(extra)
    return HTTPException(status_code=422, detail=payload)


def _validate_composition(body: SuiteCompositionIn) -> None:
    """结构校验(第 1 步口径):引用都是成员、ref 唯一、needs 只给依赖
    编排且目标为主体成员、map 为 str→str。变量级校验(悬空引用、同名
    歧义、成环)随第 3 步 validate 接执行器编译,不在这里重复。"""
    ids = [m.scenarioId for m in body.members]
    id_set = set(ids)
    if len(id_set) != len(ids):
        raise HTTPException(422, detail={
            "code": "duplicate_member",
            "message": "一个场景在 Suite 内只出现一次(需要多跑用单元 ×重复)"})
    main_ids = {m.scenarioId for m in body.members if m.role == "main"}
    cfg = body.modeConfig or {}
    units = cfg.get("units")
    if units is None:
        units = {}
    if not isinstance(units, dict):
        raise _bad_cfg("modeConfig.units 须为对象(按 scenarioId 引用成员)")
    unknown = [k for k in units if k not in id_set]
    if unknown:
        raise HTTPException(422, detail={
            "code": "unknown_unit",
            "message": f"units 引用了非成员场景: {unknown}",
            "unknown": unknown})
    refs: set[str] = set()
    for uid, u in units.items():
        if not isinstance(u, dict):
            raise _bad_cfg(f"units.{uid} 须为对象")
        r = u.get("ref")
        if r is not None:
            if not isinstance(r, str) or not r:
                raise _bad_cfg(f"units.{uid}.ref 须为非空字符串")
            if r in refs:
                raise HTTPException(422, detail={
                    "code": "duplicate_ref",
                    "message": f"单元别名 {r!r} 在 Suite 内不唯一"})
            refs.add(r)
        mp = u.get("map")
        if mp is not None and (
                not isinstance(mp, dict)
                or not all(isinstance(k, str) and isinstance(v, str)
                           for k, v in mp.items())):
            raise _bad_cfg(
                f"units.{uid}.map 须为 str→str(上游输出名 → 本地输入名)")
    needs_edges = [
        (uid, n) for uid, u in units.items() for n in (u.get("needs") or [])]
    if needs_edges and body.mode != "compose":
        raise HTTPException(422, detail={
            "code": "needs_not_allowed",
            "message": (f"{body.mode} 模式不携带 needs(顺序即结构;"
                        f"执行器对非 compose 声明 needs 直接报编译错误)")})
    before_after = id_set - main_ids
    for uid, n in needs_edges:
        if n not in main_ids:
            raise HTTPException(422, detail={
                "code": "needs_target_invalid",
                "message": (f"units.{uid} 的 needs 指向 {n!r}:目标必须是"
                            f"主体成员(前置/后置不参与连线,约束 7)")})
        if uid in before_after:
            raise HTTPException(422, detail={
                "code": "needs_source_invalid",
                "message": f"前置/后置单元 {uid!r} 不能连 needs(约束 7)"})
    for key in ("gates", "checks"):
        v = cfg.get(key)
        if v is not None and not isinstance(v, list):
            raise _bad_cfg(f"modeConfig.{key} 须为数组")
    for key in ("parallel", "nRuns"):
        v = cfg.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
            raise _bad_cfg(f"modeConfig.{key} 须为整数")


@router.put("/{suite_id}/composition", response_model=SuiteDetailOut)
async def put_composition(
    user: CurrentUser, db: DbSession, suite_id: int,
    body: SuiteCompositionIn,
) -> SuiteDetailOut:
    """整体保存:模式、成员及顺序、编排配置一次落库(重构方案,
    替代 members/order)。rev 乐观锁 —— 冲突 409 附最新内容;任何改
    成员或编排的路径(本端点、加/移成员、场景删除清理)都推进 rev。"""
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    if body.rev != suite.rev:
        # 先物化再 rollback:rollback 会过期 suite 实例,事后访问属性
        # 触发异步懒加载(MissingGreenlet,本仓已文档化的陷阱)
        current_rev = suite.rev
        latest = (await _detail_out(db, user, suite)).model_dump(mode="json")
        await db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "suite_rev_conflict",
            "message": "Suite 已被修改(他人或其他页面),拉取最新后再保存",
            "currentRev": current_rev,
            "latest": latest})
    _validate_composition(body)
    if len(body.members) > settings.SUITE_MEMBER_CAP:
        raise HTTPException(status_code=409, detail={
            "code": "suite_member_cap_exceeded",
            "message": f"suite member cap is {settings.SUITE_MEMBER_CAP}"})

    # 成员属主校验(§6.3 一刀切)+ 公共不变量(§7.9 第二入口,与
    # add_members 同一套:无标志 → 409 列出待发布,有标志 → 同事务公开)
    scen_rows: dict[str, object] = {}
    pending_publish: list[str] = []
    for m in body.members:
        scen = await scenario_store.get_row(db, m.scenarioId)
        if scen is None or scen.owner_id != suite.owner_id:
            await db.rollback()
            raise not_found_404("scenario", m.scenarioId)
        scen_rows[m.scenarioId] = scen
        if (suite.visibility == "public"
                and (scen.visibility or "private") != "public"):
            pending_publish.append(m.scenarioId)
    if pending_publish and not body.publishUnpublished:
        await db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "suite_member_publish_required",
            "message": ("suite is public: unpublished members must be "
                        "published to join (confirm to publish them and "
                        "their datasets)"),
            "pendingPublish": pending_publish})

    # 差量重写成员表(保留 added_at;删行交给组合外键语义外的显式删除)
    incoming_ids = {m.scenarioId for m in body.members}
    current = {m.scenario_id: m
               for m in await _ordered_members(db, suite.id)}
    for sid, row in current.items():
        if sid not in incoming_ids:
            await db.delete(row)
    for idx, m in enumerate(body.members):
        row = current.get(m.scenarioId)
        if row is None:
            db.add(SuiteMember(
                suite_id=suite.id, scenario_id=m.scenarioId,
                owner_id=suite.owner_id, role=m.role, sort=idx))
        else:
            row.role = m.role
            row.sort = idx
    for sid in pending_publish:  # 确认发布:成员随组公开(数据集随场景)
        scen_rows[sid].visibility = "public"

    suite.mode = body.mode
    cfg = dict(body.modeConfig or {})
    if _is_draft(suite):
        cfg["draft"] = True   # 草稿标记穿越整体保存;完成编排走 clearDraft
    suite.mode_config = cfg
    suite.rev += 1
    await db.commit()
    await db.refresh(suite)
    return await _detail_out(db, user, suite)


# ── 运行:模式分流(重构方案)─────────────────────────────────────
def _build_graph_spec(suite: Suite, members: list[SuiteMember]) -> dict:
    """Suite(mode + mode_config + 成员)→ GraphRunRequest dict(纯值,
    入队物化的全部内容 —— worker 不回读 Suite,不变量 5)。needs 存储按
    scenarioId、下发换 ref;repeat/nRuns/row/schemeId/map/injectionEntryIds
    从 mode_config.units 取,缺省由拼装层补默认行为。"""
    cfg = suite.mode_config or {}
    units_cfg = cfg.get("units") or {}

    def _ref_of(sid: str) -> str:
        u = units_cfg.get(sid) or {}
        return u.get("ref") or sid

    def _unit(m: SuiteMember) -> dict:
        u = dict(units_cfg.get(m.scenario_id) or {})
        d = {"ref": u.get("ref") or m.scenario_id,
             "scenarioId": m.scenario_id}
        for k in ("schemeId", "row", "map", "injectionEntryIds"):
            if u.get(k) is not None:
                d[k] = u[k]
        if u.get("repeat"):
            d["repeat"] = int(u["repeat"])
        if u.get("nRuns"):
            d["nRuns"] = int(u["nRuns"])
        if u.get("needs"):
            d["needs"] = [_ref_of(n) for n in u["needs"] if n in units_cfg
                          or n in {m2.scenario_id for m2 in members}]
        return d

    by_role: dict[str, list[dict]] = {"before": [], "main": [], "after": []}
    for m in members:
        by_role.setdefault(m.role or "main", []).append(_unit(m))
    gs: dict = {"mode": suite.mode, "units": by_role["main"]}
    if by_role["before"]:
        gs["before"] = by_role["before"]
    if by_role["after"]:
        gs["after"] = by_role["after"]
    for key in ("parallel", "nRuns", "gates", "checks"):
        if cfg.get(key) is not None:
            gs[key] = cfg[key]
    return gs


async def _in_flight_batch(
    db: AsyncSession, runner_id: int, suite_id: int,
) -> str | None:
    """防重(§6.6):按 (suite, 发起人),时效窗口内的未终态批次。"""
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=settings.SUITE_RUN_STALE_HOURS)
    rows = (await db.execute(
        select(Execution.id, Execution.batch_id).where(
            Execution.owner_id == runner_id,
            Execution.status.in_(("queued", "running")),
            Execution.created_at > cutoff,
        )
    )).all()
    prefix = f"suite-{suite_id}-"
    hit = next((r for r in rows if r.batch_id
                and r.batch_id.startswith(prefix)), None)
    return hit.batch_id if hit else None


def _in_flight_409(batch_id: str) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": "suite_run_in_progress",
        "message": "该 suite 已有你未完成的批次(先查看或取消后再发起)",
        "batchId": batch_id,
        "link": f"/executions?batch_id={batch_id}"})


async def _run_orchestration(
    db: AsyncSession, user: CurrentUser, suite: Suite,
    members: list[SuiteMember], *, control: dict | None = None,
) -> dict:
    """编排模式运行(重构方案):逐单元 can_run_scenario(任一不过整体
    403 —— 图不能像聚合那样跳过单元),入队时把成员 / 编排配置 / 各
    单元方案与数据行参数全部物化进任务(worker 不回读 Suite,不变量
    5);快照 = 入队时解析完成的 graph_spec + 当时 rev。"""
    from ._ownership import can_run_scenario as _can_run
    not_runnable: list[str] = []
    for m in members:
        scen = await scenario_store.get_row(db, m.scenario_id)
        if scen is None or not await _can_run(
                db, user, scenario_id=m.scenario_id,
                owner_id=scen.owner_id if scen else None):
            not_runnable.append(m.scenario_id)
    if not_runnable:
        raise HTTPException(status_code=403, detail={
            "code": "units_not_runnable",
            "message": "编排模式下所有单元都必须可运行(图不能跳过单元)",
            "units": not_runnable})

    graph_spec = _build_graph_spec(suite, members)
    if control:
        graph_spec["control"] = control
    est = sum(int(u.get("repeat") or 1) * int(u.get("nRuns") or 1)
              for u in [*graph_spec.get("before", []),
                        *graph_spec["units"],
                        *graph_spec.get("after", [])])
    if est > settings.SUITE_RUN_TOTAL_CAP:
        raise HTTPException(status_code=409, detail={
            "code": "too_many_runs",
            "message": (f"suite total runs {est} exceed cap "
                        f"{settings.SUITE_RUN_TOTAL_CAP} (units x repeat "
                        f"x nRuns)")})

    from ..services import execution_queue as _eq
    from ..services.run_dispatcher import _create_execution, _new_run_id
    chain = str(getattr(settings, "EXEC_CHAIN", "legacy") or "legacy")
    run_id = _new_run_id()
    batch_id = f"suite-{suite.id}-{user.id}-{uuid4().hex[:12]}"
    execution = await _create_execution(
        db,
        # 占位(非 sc- 前缀,绝不命中真实场景的场景维度查询)
        scenario_id=f"suite-{suite.id}",
        owner_id=user.id,
        total_runs=est,
        scenario_name=suite.name,
        batch_id=batch_id,
        # 入队物化快照(不变量 5 的证据):拼装产物 + 当时 rev
        scenario_snapshot={"graphSpec": graph_spec, "rev": suite.rev,
                           "suiteId": suite.id},
        config_json={"kind": "graph", "suiteId": suite.id,
                     "rev": suite.rev, "mode": suite.mode,
                     "runId": run_id, "batchId": batch_id,
                     "graphSpec": graph_spec, "chain": chain},
        kind="suite_graph", suite_id=suite.id,
    )
    await _eq.enqueue(db, execution.id, kind="graph", payload={
        "kind": "graph", "chain": chain,
        "args": {"execution_id": execution.id, "run_id": run_id,
                 "owner_id": user.id, "graph_spec": graph_spec,
                 "n_runs": 1, "halt_at": None, "scenario_payload": {}},
    })
    _eq.ensure_workers()
    n_units = (len(graph_spec["units"]) + len(graph_spec.get("before", []))
               + len(graph_spec.get("after", [])))
    return {"executionId": execution.id, "batchId": batch_id,
            "mode": suite.mode, "units": n_units, "estimatedRuns": est}


def _req_from_scheme(
    scenario_id: str, scheme: dict, batch_id: str,
) -> RunRequest:
    """默认方案参数 → RunRequest(与前端「直接执行」同口径:读默认
    方案后内联发送,§13.3-2);batchId 必带 —— 执行行据此挂批次键
    (批次视图/通知聚合的归并面)。"""
    return RunRequest(
        scenarioId=scenario_id,
        batchId=batch_id,
        dataSetIds=scheme.get("dataSetIds") or [],
        dataSetSelection=scheme.get("dataSetSelection") or [],
        injectionEntryIds=scheme.get("injectionEntryIds") or [],
        serviceBindings=scheme.get("serviceBindings") or {},
        stepTo=scheme.get("stepTo"),
        nRuns=scheme.get("nRuns") or 1,
        parallel=scheme.get("parallel") or 1,
        schemeId=scheme.get("schemeId"),
        schemeName=scheme.get("name"),
    )


@router.post("/{suite_id}/run", status_code=201)
async def run_suite(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> dict:
    """聚合模式 = 逐个跑成员、无执行策略(§6.6):服务端循环分发 +
    batch_id 归并,是聚合模式的完整实现,不依赖执行器侧 suite 能力。

    实现纪律(定稿 §6.6,全部钉死):
    - **循环前物化**:成员快照与各成员默认方案参数先取纯值,循环内
      不触碰 ORM 实例 —— ``rollback()`` 总是使 Session 内已加载实例
      过期,async 下访问过期属性触发懒加载抛 ``MissingGreenlet``,
      一个成员出错会让后续成员连锁失败;发起人 id/角色同样先取纯值。
    - **防重按 (suite, 发起人)**:本人时效窗口内的未终态批次 → 409,
      深链只指本人批次(P1 无引用分享,锁整个 suite 会互相阻塞的说法
      留给 P2 之后的语义;现在按人即正确形态);**不加服务端锁**
      (事务级锁在逐成员自决 commit 下提前释放、会话级与连接池冲突,
      接受良性竞态 —— 双开提交的后果只是多一个批次)。
    - **总量预检**:Σ 成员 runs 复用 ``compute_run_fanout``/``fanout_total``
      与 dispatch 同一份实现,防「预检通过、单成员 409」漂移。
    - **逐成员 try/except**:校验类(NotFound/Conflict)进 skipped;
      基础设施异常先 rollback,**再按落库事实归类** —— 该成员在本
      batch_id 下已有执行行 → started 附警告(执行会照常跑,不能
      「显示跳过实际在跑」),没有才 skipped。
    """
    suite = await _load_suite(db, suite_id)
    await _require_run_async(db, user, suite)

    # ── 循环前物化(纯值):发起人、成员快照、各成员默认方案 ──
    # suite 纯值同样先行:循环内异常路径的 rollback 会过期 ORM 实例,
    # 事后访问属性触发异步懒加载(MissingGreenlet,本仓已文档化)
    suite_id_val = suite.id
    runner_id = user.id
    members = await _ordered_members(db, suite_id)
    if not members:
        raise HTTPException(status_code=409, detail={
            "code": "suite_empty", "message": "suite 没有成员,无可执行场景"})

    # ── 模式分流(重构方案):编排模式走一次编排执行,防重同口径 ──
    if (suite.mode or "aggregate") in ("chain", "fanout", "compose"):
        in_flight = await _in_flight_batch(db, runner_id, suite_id)
        if in_flight is not None:
            raise _in_flight_409(in_flight)
        return await _run_orchestration(db, user, suite, members)

    scen_rows: dict[str, object] = {}
    default_schemes: dict[str, dict | None] = {}
    stale_ids: list[str] = []
    for m in members:
        scen = await scenario_store.get_row(db, m.scenario_id)
        if scen is None:
            # 瞬态:成员快照后场景被删(FK CASCADE 随即收掉成员行)
            stale_ids.append(m.scenario_id)
            continue
        scen_rows[m.scenario_id] = scen
        await scheme_store.ensure_default_scheme(db, m.scenario_id)
        schemes = await scheme_store.list_schemes(db, m.scenario_id)
        default_schemes[m.scenario_id] = next(
            (s for s in schemes if s.get("isDefault")), None)
    await db.commit()  # ensure_default_scheme 的自愈写入先落库

    # ── 防重(§6.6):按 (suite, 发起人),时效窗口内的未终态批次 ──
    in_flight = await _in_flight_batch(db, runner_id, suite_id)
    if in_flight is not None:
        raise _in_flight_409(in_flight)

    batch_id = f"suite-{suite_id}-{runner_id}-{uuid4().hex[:12]}"
    plain: list[dict] = [
        {"scenarioId": sid, "req": None, "skip_reason": "scenario_not_found"}
        for sid in stale_ids
    ] + [
        {
            "scenarioId": sid,
            "req": (_req_from_scheme(sid, default_schemes[sid], batch_id)
                    if default_schemes[sid] is not None
                    else RunRequest(scenarioId=sid, batchId=batch_id)),
        }
        for sid in scen_rows
    ]

    # ── 总量预检(与 dispatch 同一份计算;校验类失败提前归 skipped)──
    total_runs = 0
    for entry in plain:
        if entry["req"] is None:
            continue
        try:
            fd, inj, _se, _sd = await run_dispatcher.compute_run_fanout(
                db, scen_rows[entry["scenarioId"]], entry["req"])
            total_runs += run_dispatcher.fanout_total(fd, inj)
        except (run_dispatcher.NotFound, run_dispatcher.Conflict) as e:
            entry["req"] = None
            entry["skip_reason"] = e.code
    if total_runs > settings.SUITE_RUN_TOTAL_CAP:
        raise HTTPException(status_code=409, detail={
            "code": "too_many_runs",
            "message": (f"suite total runs {total_runs} exceed cap "
                        f"{settings.SUITE_RUN_TOTAL_CAP} (rows x injections)")})

    started: list[int] = []
    skipped: list[dict] = []
    dispatch_warnings: list[dict] = []

    from ._ownership import can_run_scenario as _can_run
    for entry in plain:
        sid = entry["scenarioId"]
        if entry["req"] is None:
            skipped.append({"scenarioId": sid, "reason": entry["skip_reason"]})
            continue
        # §8.2:逐成员 can_run_scenario(属主 ∨ admin ∨ 引用;引用者
        # 经 suite 引用覆盖全部成员 —— 正常态全过,守边界)。
        _scen = scen_rows.get(sid)
        if _scen is not None and not await _can_run(
                db, user, scenario_id=sid, owner_id=_scen.owner_id):
            skipped.append({"scenarioId": sid, "reason": "not_runnable"})
            continue
        try:
            # 不传 preloaded_scenario:except 分支的 rollback 会使 ORM
            # 实例过期(懒加载在 async 下抛 MissingGreenlet),让
            # dispatch_run 每成员自查一行(PK 查询,代价可忽略)。
            resp = await run_dispatcher.dispatch_run(
                db, user_id=runner_id, req=entry["req"])
            started.append(resp.execution_id)
        except (run_dispatcher.NotFound, run_dispatcher.Conflict) as e:
            skipped.append({"scenarioId": sid, "reason": e.code})
        except Exception as e:  # noqa: BLE001 —— 基础设施异常不连坐(§6.6)
            await db.rollback()
            # 归类按落库事实:enqueue 自决 commit 后抛错的成员,其执行
            # 行已存在、之后会照常跑 —— 归 started 附警告,不进 skipped。
            ex_id = (await db.execute(
                select(Execution.id).where(
                    Execution.batch_id == batch_id,
                    Execution.scenario_id == sid,
                )
            )).scalar_one_or_none()
            if ex_id is not None:
                started.append(ex_id)
                dispatch_warnings.append({
                    "scenarioId": sid, "executionId": ex_id,
                    "message": f"dispatch error after enqueue: {e}"})
            else:
                skipped.append({"scenarioId": sid, "reason": "dispatch_error"})

    # 聚合成员执行回挂 suite_id(21 页按 Suite 归并;kind 仍是
    # scenario —— 它就是该场景按默认方案的一次真实运行)
    if started:
        from sqlalchemy import update as _su
        await db.execute(_su(Execution).where(
            Execution.id.in_((started))).values(suite_id=suite_id_val))
        await db.commit()

    return {
        "batchId": batch_id,
        "started": started,
        "skipped": skipped,
        "dispatchWarnings": dispatch_warnings,
        "totalRuns": total_runs,
    }


@router.get("/{suite_id}/runs")
async def suite_runs(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> dict:
    """该 Suite 的历次运行(重构方案):**只返回本人发起的**(不变量 2:
    执行台账归执行人,属主 / admin 亦然)。聚合按批次归并,编排执行逐条;
    供 21 页混排(标明通道)。"""
    suite = await _load_suite(db, suite_id)
    await _require_read_async(db, user, suite)
    rows = (await db.execute(
        select(Execution).where(
            Execution.suite_id == suite.id,
            Execution.owner_id == user.id,
        ).order_by(Execution.created_at.desc(), Execution.id.desc())
        .limit(200))).scalars().all()

    items: list[dict] = []
    batches: dict[str, dict] = {}
    for ex in rows:
        if (ex.kind or "scenario") == "suite_graph":
            items.append({
                "executionId": ex.id, "kind": "suite_graph",
                "batchId": ex.batch_id,
                "mode": (ex.config_json or {}).get("mode"),
                "status": ex.status,
                "totalRuns": ex.total_runs, "passed": ex.passed,
                "failed": ex.failed, "skipped": ex.skipped,
                "createdAt": _iso(ex.created_at),
                "finishedAt": _iso(ex.finished_at),
            })
            continue
        key = ex.batch_id or f"single-{ex.id}"
        agg = batches.setdefault(key, {
            "batchId": key, "kind": "batch",
            "status": "running", "executions": [],
            "totalRuns": 0, "passed": 0, "failed": 0, "skipped": 0,
            "createdAt": _iso(ex.created_at), "finishedAt": None})
        agg["executions"].append(ex.id)
        agg["totalRuns"] += ex.total_runs
        agg["passed"] += ex.passed
        agg["failed"] += ex.failed
        agg["skipped"] += ex.skipped
        if ex.finished_at and (agg["finishedAt"] is None
                               or ex.finished_at > agg["finishedAt"]):
            agg["finishedAt"] = _iso(ex.finished_at)
        if ex.status in ("queued", "running"):
            agg["status"] = "running"
        elif agg["status"] != "running":
            agg["status"] = ("failed" if agg["failed"] else
                             "canceled" if ex.status == "canceled" else "done")
    items.extend(batches.values())
    items.sort(key=lambda i: i["createdAt"] or "", reverse=True)
    return {"items": items, "total": len(items)}


@router.post("/{suite_id}/runs/{execution_id}/rerun-failed", status_code=201)
async def rerun_failed_units(
    user: CurrentUser, db: DbSession, suite_id: int, execution_id: int,
) -> dict:
    """只重跑某次编排执行里失败的单元:以失败单元为 ``control.only``
    重新运行**当前** Suite(上游随之重跑;Suite 此后的编排变更随本次
    生效)。只能对自己发起的执行操作(不变量 2,属主 / admin 同口径)。"""
    from ..models.execution import ExecutionRow
    suite = await _load_suite(db, suite_id)
    await _require_run_async(db, user, suite)
    ex = await db.get(Execution, execution_id)
    if (ex is None or ex.suite_id != suite.id
            or (ex.kind or "scenario") != "suite_graph"):
        raise not_found_404("execution", str(execution_id))
    if ex.owner_id != user.id:
        raise HTTPException(status_code=403, detail={
            "code": "not_initiator",
            "message": "只能对自己发起的执行重跑失败单元(不变量 2)"})
    failed_rows = (await db.execute(
        select(ExecutionRow.unit_id).where(
            ExecutionRow.execution_id == execution_id,
            ExecutionRow.seq > 0,
            ExecutionRow.status.in_(("failed", "error", "halted")),
        ).order_by(ExecutionRow.seq))).scalars().all()
    # ×重复变体(ref#k)归并到基座 ref
    failed_refs = list(dict.fromkeys(
        r.split("#")[0] for r in failed_rows if r and r != "graph"))
    if not failed_refs:
        raise HTTPException(status_code=409, detail={
            "code": "no_failed_units",
            "message": "该执行没有失败单元可重跑"})
    members = await _ordered_members(db, suite.id)
    if not members:
        raise HTTPException(status_code=409, detail={
            "code": "suite_empty", "message": "suite 没有成员,无可执行场景"})
    in_flight = await _in_flight_batch(db, user.id, suite_id)
    if in_flight is not None:
        raise _in_flight_409(in_flight)
    return await _run_orchestration(
        db, user, suite, members, control={"only": failed_refs})


# ── P2 §7.9/§9:suite 发布 / 下架 ────────────────────────────────
@router.post("/{suite_id}/publish", response_model=SuiteSummaryOut)
async def publish_suite(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> SuiteSummaryOut:
    """发布:级联发布未发布成员(确认框由前端承载;数据集随场景
    可见性公开,《权限一期》口径)。属主 ∨ admin(§8.1 写 = 治理)。"""
    from ..models.composer_scenario import ComposerScenario
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    if _is_draft(suite):
        raise HTTPException(status_code=409, detail={
            "code": "suite_is_draft",
            "message": "草稿不可发布(完成编排后可发布)"})
    members = await _ordered_members(db, suite.id)
    unpublished: list[str] = []
    for m in members:
        scen = await scenario_store.get_row(db, m.scenario_id)
        if scen is not None and (scen.visibility or "private") != "public":
            unpublished.append(m.scenario_id)
            scen.visibility = "public"
    suite.visibility = "public"
    await db.commit()
    await db.refresh(suite)
    out = _summary(suite, len(members))
    out.publishedMembers = unpublished  # 级联清单:确认框的事实面回执
    return out


@router.delete("/{suite_id}/publish", response_model=SuiteSummaryOut)
async def unpublish_suite(
    user: CurrentUser, db: DbSession, suite_id: int,
) -> SuiteSummaryOut:
    """下架 suite 本体(成员各自的 public 状态独立保留,§9)。admin
    下架他人 suite → 通知属主 + 入审计(§10;属主自下架不通知不入)。"""
    from ..services import audit as audit_svc
    from ..services import notifications as notify_svc
    suite = await _load_suite(db, suite_id)
    _require_write(user, suite)
    suite.visibility = "private"
    await db.commit()
    await db.refresh(suite)
    if user.role == "admin" and suite.owner_id != user.id:
        try:
            await notify_svc.create_notification(
                db, user_id=suite.owner_id,
                type_="scenario_unpublished",
                title=f"你的公共 Suite 已被下架:{suite.name}",
                body=(f"管理员 {user.display_name or user.username} 将 Suite "
                      f"「{suite.name}」从公共库下架(现为私有;成员场景的"
                      f"公共状态不受影响)。"),
                link=f"/suites/{suite.id}")
        except Exception:  # noqa: BLE001
            pass
        await audit_svc.record(
            db, actor_id=user.id,
            actor_name=user.display_name or user.username,
            action="suite.admin_unpublish",
            resource_type="suite", resource_id=str(suite.id),
            detail={"name": suite.name})
    return _summary(suite, await _member_count(db, suite.id))


# ── 反查:场景在哪些 suite ─────────────────────────────────────────
@lookup_router.get("/{scenario_id}/suites", response_model=list[SuiteLookupItem])
async def suites_of_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> list[SuiteLookupItem]:
    """场景详情「所属 suite」反查:自己的 suite(成员 ⊆ 自己的场景,
    场景属主视角天然成立);admin 另见全量(治理)。"""
    scen = await scenario_store.get_row(db, scenario_id)
    if scen is None:
        raise not_found_404("scenario", scenario_id)
    ensure_owner(
        user, scen.owner_id,
        {"code": "not_owner",
         "message": "only the scenario's owner (or admin) can view "
                    "its suites"},
    )
    clauses = [Suite.id.in_(
        select(SuiteMember.suite_id)
        .where(SuiteMember.scenario_id == scenario_id)
    )]
    if user.role != "admin":
        clauses.append(Suite.owner_id == user.id)
    rows = (await db.execute(
        select(Suite).where(*clauses).order_by(Suite.updated_at.desc())
    )).scalars().all()
    return [
        SuiteLookupItem(
            suiteId=s.id, name=s.name,
            memberCount=await _member_count(db, s.id),
            ownerName="",
        )
        for s in rows
    ]
