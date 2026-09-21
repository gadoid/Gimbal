"""Scenario endpoints (V3 composer).

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.1–4.7):

* ``POST /api/scenarios/preview-plate``  — Plate ``/convert`` preview
* ``POST /api/scenarios``                 — create
* ``GET  /api/scenarios?q&system&module&priority&…`` — list(Page 信封,M1)
* ``POST /api/scenarios/{id}/star``       — toggle star
* ``GET  /api/scenarios/{id}``            — detail
* ``PUT  /api/scenarios/{id}``            — replace
* ``DELETE /api/scenarios/{id}``          — cascade

**Order matters** (FastAPI matches top-to-bottom).  Static suffixes
(``preview-plate`` / ``/{id}/star``) must precede the catch-all
``/{scenario_id}`` routes, or the ``:path`` converter would capture
their suffix and the static handler would never fire.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import can_read_scenario, ensure_owner
from ._error_mapping import key_error_404, not_found_404, value_error_http
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import (
    PreviewPlateError,
    PreviewPlateIn,
    PreviewPlateResponse,
    Scenario,
    ScenarioDraft,
    ScenarioListOut,
    ScenarioOptionsItem,
    ScenarioOptionsOut,
    StarIn,
)
from ..services import plate_client, run_dispatcher, scheme_store, scenario_store
from ..services.auth_ref_scan import scan_auth_aliases
from ..services.carry_injection import build_carry_context
from ..services.run_materialize import materialize_run_copy


router = APIRouter(prefix="/scenarios", tags=["scenarios"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_row(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


def _require_owner(user: CurrentUser, row: ComposerScenario) -> None:
    # owner_id (int user.id) is the single ownership authority
    # (canonical rule in _ownership).
    ensure_owner(
        user,
        row.owner_id,
        "not_owner: only the scenario's owner (or admin) can modify it",
    )


def _require_reader(user: CurrentUser, row: ComposerScenario) -> None:
    """读侧收紧(404 而非 403,不向非读者泄露场景存在性)。"""
    if not can_read_scenario(
        user,
        owner_id=row.owner_id,
        visibility=row.visibility or "private",
    ):
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {row.scenario_id}"
        )


def _draft_to_full_scenario_dict(
    draft: ScenarioDraft, owner: str
) -> dict:
    """Build a plate-valid Scenario dict from the platform container.

    definition is already plate-shaped (it's the authoritative structure);
    this only fills plate-required defaults that the platform UI doesn't
    collect. orchestration is platform-only and never sent.

    Defaults: see :func:`plate_client.fill_plate_defaults` (shared with
    the run path — preview/export 与执行链共用同一份 plate 必填默认,
    防两路漂移).
    """
    payload = {k: v for k, v in draft.definition.items()}
    return plate_client.fill_plate_defaults(payload, owner=owner)


# ── 1) POST /preview-plate (static — must precede /{scenario_id}) ──
@router.post(
    "/preview-plate", response_model=PreviewPlateResponse
)
async def preview_plate(
    user: CurrentUser, db: DbSession, body: PreviewPlateIn
) -> PreviewPlateResponse:
    """Forward the draft to Plate's ``/convert`` and return the verdict.

    Does NOT persist anything — the draft is treated as ephemeral so the
    user can preview before saving.  The converted payload (Plate
    /convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为
    "GIMBAL 可执行" 的场景 JSON/YAML。
    """
    scenario_dict = _draft_to_full_scenario_dict(
        body, owner=user.display_name or user.username
    )
    try:
        data = await plate_client.convert(scenario_dict)
    except plate_client.PlateUnavailableError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_unavailable", "message": e.message},
        )
    except plate_client.PlateRejectedError as e:
        # The upstream 4xx is a verdict on the *client's draft*, not a
        # gateway failure — surface it as 422 (input rejected) instead of
        # 502 so operators don't chase a phantom Plate outage.
        raise HTTPException(
            status_code=422,
            detail={
                "code": "plate_rejected",
                "message": e.message,
                "errors": list(e.errors or []),
            },
        )
    # Plate returns ``{consumer, converted}`` on success.  Treat any
    # ``errors[]`` inside ``converted`` as field-level issues.  We pass
    # the full ``converted`` dict back so the frontend can use it as the
    # canonical "gimbal-executable" structure for export.
    converted = (data or {}).get("converted") or {}
    # Optional export overlay (spec §8): convert 之后、返回之前物化
    # (POST-convert 位点,明文绑定/凭证不过 plate)。物化语义与
    # run 执行链(run_dispatcher._fanout)同源 — 黄金等价:同场景同
    # overlay 下 preview-plate 产物 ≡ 基线单行 case.json,逐字段相等。
    # (旧执行环境覆盖键已随 D2 退役;overlay 只收 serviceBindings。)
    if body.overlay is not None:
        # 注入清单与 dispatch 同构(spec §7.3 矩阵:导出侧 = 执行侧):
        # scan_auth_aliases(definition steps)∪ 绑定 authAlias。预览侧
        # 无需保序,去重即可(dispatch 侧 dict.fromkeys 保序仅为一稳定日志序)。
        scanned = scan_auth_aliases(body.definition.get("steps") or [])
        bound = [b.auth_alias for b in body.overlay.service_bindings.values()
                 if b.auth_alias]
        aliases = sorted(set([*scanned, *bound]))
        try:
            exec_auths = await run_dispatcher._resolve_exec_auths(
                run_dispatcher.session_factory, owner_id=user.id, aliases=aliases)
        except run_dispatcher._AuthResolveError as e:
            # 凭证路径 fail-fast 的预览侧形态(dispatch 整单失败同语义;
            # preview 无执行副作用,直接拒答 422 而非 500)。
            raise HTTPException(
                status_code=422,
                detail={"code": "auth_resolve_failed", "message": str(e)},
            )
        # built_in 基座与 dispatch 同源:场景 definition.config.users
        # (plate 会剥平台视图字段,内置认证以场景定义为唯一可信源)
        def_cfg = (body.definition.get("config") or {})
        built_in = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
        service_bindings = {k: b.model_dump(by_alias=True)
                            for k, b in body.overlay.service_bindings.items()}
    else:
        # 默认导出(无 overlay):凭证/服务绑定零注入 — overlay 是它们
        # 的唯一开关;carry 见下方无条件物化。
        exec_auths = []
        built_in = {}
        service_bindings = {}
    # carry 同源注入(spec §4.3 勘误):与 dispatch 共用 build_carry_context
    # → 导出产物 = 绑定状态的当时快照。无条件执行 — 默认导出与按方案
    # 导出走同一套 carry 物化(执行/导出不再系统性漂移)。plate 故障在
    # build 内部降级(不注入,不 5xx);此处再兜一层 — carry 是增强
    # 不是前置条件,任何故障(含 DB)都降级为无 carry,绝不阻塞导出。
    try:
        carry_ctx = await build_carry_context(db, body.definition)
    except Exception:  # noqa: BLE001 — carry 绝不阻塞导出
        logger.opt(exception=True).warning(
            "preview_plate: carry context build failed; skipped")
        carry_ctx = None
    converted = materialize_run_copy(
        converted,
        service_bindings=service_bindings,
        resolved_auths=exec_auths,
        built_in_users=dict(built_in or {}),
        carry_context=carry_ctx,
    )
    inner_errors = converted.get("errors") or []
    return PreviewPlateResponse(
        ok=True,
        errors=[PreviewPlateError(**e) for e in inner_errors if isinstance(e, dict)],
        converted=converted if isinstance(converted, dict) else None,
    )


# ── 2) POST / (create) ─────────────────────────────────────────────
@router.post("", response_model=Scenario, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    user: CurrentUser, db: DbSession, body: ScenarioDraft
) -> Scenario:
    owner = user.display_name or user.username
    try:
        return await scenario_store.create(
            db, body, owner=owner, owner_id=user.id
        )
    except ValueError as e:
        # Pydantic validation errors already translated to 422 by FastAPI.
        raise value_error_http(e, {"scenario_id_exists": 409})


# ── 3a0) GET /signals(M5,债 12:关注页 N+1 消除)─────────────────────
@router.get("/signals")
async def scenario_signals(
    user: CurrentUser,
    db: DbSession,
    ids: str = Query(min_length=1, max_length=2048),
) -> dict:
    """批量健康趋势(M5,§7 M5-2):``?ids=a,b,c``(≤20,对齐关注上限)
    → 每场景 {trend(近5,旧→新), lastRun}。

    口径与前端 useScenarioRuns.trend 逐字对齐:我的来源锁**默认方案**
    的执行;公共原件锁自身全部(验证执行);执行池 = 调用者自己的
    (owner 隔离,同 GET /executions)。一次 SQL 圈全集,替换关注页
    每对象一次 listExecutions 的 N+1。
    """
    from sqlalchemy import select

    from ..models.execution import Execution
    from ..models.composer_run_scheme import ComposerRunScheme as RunScheme

    sid_list = [x.strip() for x in ids.split(",") if x.strip()][:20]
    if not sid_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids required",
        )

    # 场景可见性 + public 判定(follows 页的数据源,但口径仍守读侧纪律)
    scen_rows = (await db.execute(
        select(ComposerScenario.scenario_id, ComposerScenario.visibility,
               ComposerScenario.owner_id)
        .where(ComposerScenario.scenario_id.in_(sid_list))
    )).all()
    by_sid = {r.scenario_id: r for r in scen_rows}

    # 方案面(默认方案 id + 名称 + 计数;非属主读不到方案 —— 对齐
    # listRunSchemes 的属主隔离,public 关注对象给 0/None)
    scheme_rows = (await db.execute(
        select(RunScheme.scenario_id, RunScheme.scheme_id,
               RunScheme.name, RunScheme.is_default)
        .where(RunScheme.scenario_id.in_(sid_list))
    )).all()
    default_scheme: dict[str, str] = {}
    scheme_count: dict[str, int] = {}
    default_scheme_name: dict[str, str | None] = {}
    for r in scheme_rows:
        scheme_count[r.scenario_id] = scheme_count.get(r.scenario_id, 0) + 1
        if r.is_default:
            default_scheme[r.scenario_id] = r.scheme_id
            default_scheme_name[r.scenario_id] = r.name

    # 我的近期执行(一次圈回,按场景分组)
    exec_rows = (await db.execute(
        select(Execution)
        .where(Execution.owner_id == user.id,
               Execution.scenario_id.in_(sid_list))
        .order_by(Execution.id.desc())
    )).scalars().all()
    by_sid_execs: dict[str, list[Execution]] = {}
    for e in exec_rows:
        by_sid_execs.setdefault(e.scenario_id, []).append(e)

    def _scheme_of(e: Execution) -> str | None:
        cfg = e.config_json or {}
        v = cfg.get("schemeId")
        return v if isinstance(v, str) else None

    out: dict[str, dict] = {}
    for sid in sid_list:
        row = by_sid.get(sid)
        if row is None:
            out[sid] = {"trend": [], "lastRun": None}
            continue
        is_public = (row.visibility or "private") == "public"
        execs = by_sid_execs.get(sid, [])
        if not is_public:
            lock = default_scheme.get(sid)
            execs = [e for e in execs if lock and _scheme_of(e) == lock]
        trend = [e.status for e in execs[:5]][::-1]
        last = execs[0] if execs else None
        own = row.owner_id == user.id
        out[sid] = {
            "trend": trend,
            "lastRun": ({
                "status": last.status,
                "at": (last.finished_at or last.started_at or None),
            } if last else None),
            "schemeCount": scheme_count.get(sid, 0) if own else 0,
            "defaultSchemeName": default_scheme_name.get(sid) if own else None,
        }
    return {"signals": out}


# ── 3a) GET /facets(M3,§4.1)────────────────────────────────────────
@router.get("/facets")
async def scenario_facets(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    visibility: str | None = None,
) -> dict:
    """五维 facets:modules/systems/tags/authors/priorities 可选值+计数。

    替代前端「全量拉回 FilterPopover unique」的 M1 过渡形态。PG 走
    GROUP BY + jsonb unnest;SQLite Python 兜底(方言分派同 list)。
    """
    is_pg = db.bind.dialect.name == "postgresql"
    if is_pg:
        from ..services import scenario_query
        out = await scenario_query.facets(
            db, user=user, viewer_id=user.id, q=q, visibility=visibility)
        return {
            dim: [{"value": k, "count": n} for k, n in pairs]
            for dim, pairs in out.items()
        }

    # SQLite 兜底:可见集全量行上 Python 聚合(本地量小)
    rows = await scenario_store.list_rows(db)
    visible = [
        r for r in rows
        if can_read_scenario(
            user, owner_id=r.owner_id, visibility=r.visibility or "private")
    ]
    if visibility:
        visible = [r for r in visible
                   if (r.visibility or "private") == visibility]
    if q:
        ql = q.lower()

        def _hit(r):
            from ..services.scenario_store import _meta_from_row
            m = _meta_from_row(r)
            hay = [r.scenario_id or "", m.name or "", m.module or "",
                   m.description or "", *(m.tags or [])]
            return any(ql in (h or "").lower() for h in hay)

        visible = [r for r in visible if _hit(r)]

    from ..services.scenario_store import _meta_from_row
    from collections import Counter
    mod, sys_, tag, auth, prio = (Counter() for _ in range(5))
    for r in visible:
        m = _meta_from_row(r)
        mod[m.module or ""] += 1
        sys_.update(m.system or [])
        tag.update(m.tags or [])
        auth[m.author or ""] += 1
        prio[m.priority] += 1
    return {
        "modules": [{"value": k, "count": n} for k, n in mod.most_common()],
        "systems": [{"value": k, "count": n} for k, n in sys_.most_common()],
        "tags": [{"value": k, "count": n} for k, n in tag.most_common()],
        "authors": [{"value": k, "count": n} for k, n in auth.most_common()],
        "priorities": [{"value": k, "count": n} for k, n in prio.most_common()],
    }


# ── 3) GET / (list) ────────────────────────────────────────────────
@router.get("", response_model=ScenarioListOut | ScenarioOptionsOut)
async def list_scenarios(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    visibility: str | None = None,
    updated_within: Literal["24h", "7d", "30d"] | None = None,
    starred: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    fields: Literal["options"] | None = None,
) -> ScenarioListOut | ScenarioOptionsOut:
    """列表(Page 信封 + M1 响应投影,PG迁移方案 §4.1/§7 M1)。

    读侧收紧:admin 全量;普通用户 = public + 自己的。可选
    ``visibility=public|private`` 再过滤一层,供前端"公共 / 我的"分组
    标签使用。

    属主过滤直接在 store 已加载的行上做(此前为 readable_ids 再跑
    一趟全表投影,单请求双全表扫描)。

    多值筛选参数(system/module/priority/tag/author)收逗号联合字符串,
    语义与前端 ``utils/filters.ts`` 对齐(system/tag=OR 携带,其余精确
    命中其一);``updated_within`` 锚 DB 行 updated_at。排序服务端定死
    ``updated_at DESC``(§4.1,不接受任意 sort)。分页在 Python 侧切片
    ——M1 的服务端查询仍全表加载 payload,SQL 端过滤/排序是 M3 的事。
    ``fields=options`` 返回轻量元数据形态(选择器/名称映射专用)。
    """
    # ── M3 方言分派(PG迁移方案 §7 M3)───────────────────────────────
    # PG:过滤/排序/分页全 SQL(生成列承载 WHERE,债 3 消除);
    # SQLite:Python 兜底(本地量小,正确性优先)。
    # starred=true → 收藏集(≤20,cap 兜底)下推 SQL IN;
    # starred=false(排除收藏)走 Python 兜底分支(量小,不值得 NOT IN 分支)
    # M6-2:收藏源改 UserStar 表(marks_store/stars.json 退役)
    from ..services import user_stars as user_stars_svc

    user_star_ids = await user_stars_svc.star_ids(db, user.id)
    starred_ids = sorted(user_star_ids) if starred is True else None
    is_pg = db.bind.dialect.name == "postgresql"
    if is_pg and starred is not False:
        from ..services import scenario_query
        page_rows, total = await scenario_query.list_page(
            db, user=user, viewer_id=user.id, q=q,
            systems=scenario_query.split_csv(system),
            modules=scenario_query.split_csv(module),
            priorities=scenario_query.split_ints(priority),
            tags=scenario_query.split_csv(tag),
            authors=scenario_query.split_csv(author),
            cutoff=scenario_query.updated_cutoff(updated_within),
            visibility=visibility, starred_ids=starred_ids,
            page=page, page_size=page_size,
        )
        if fields == "options":
            items = [
                ScenarioOptionsItem(
                    scenarioId=r.scenario_id,
                    name=scenario_store._meta_from_row(r).name,
                    visibility=r.visibility or "private",
                    owner=r.owner_name or "",
                )
                for r in page_rows
            ]
            return ScenarioOptionsOut(
                items=items, total=total, page=page, pageSize=page_size
            )
        ds_counts = await scenario_store.dataset_counts(db)
        sch_counts = await scheme_store.scheme_counts(db)
        items = [
            scenario_store.to_list_item_shape(
                r, starred_ids=user_star_ids,
                data_set_count=ds_counts.get(r.scenario_id, 0),
                scheme_count=sch_counts.get(r.scenario_id, 0),
            )
            for r in page_rows
        ]
        return ScenarioListOut(
            items=items, total=total, page=page, pageSize=page_size)

    rows = await scenario_store.list_rows(
        db, q=q, system=system, module=module, priority=priority,
        tag=tag, author=author, updated_within=updated_within,
    )
    readable = [
        r for r in rows
        if can_read_scenario(
            user, owner_id=r.owner_id, visibility=r.visibility or "private"
        )
    ]
    if visibility:
        readable = [r for r in readable if (r.visibility or "private") == visibility]
    # 关注页/关注卡的服务端数据源(store 退位后前端不再持有全量可过滤,
    # PG迁移方案 §7 M5 的 ?starred=true 端点提前随 M1 到位)。
    if starred is not None:
        readable = [
            r for r in readable
            if (r.scenario_id in user_star_ids) == starred
        ]

    total = len(readable)
    start = (page - 1) * page_size
    page_rows = readable[start : start + page_size]

    if fields == "options":
        items = [
            ScenarioOptionsItem(
                scenarioId=r.scenario_id,
                name=scenario_store._meta_from_row(r).name,
                visibility=r.visibility or "private",
                owner=r.owner_name or "",
            )
            for r in page_rows
        ]
        return ScenarioOptionsOut(
            items=items, total=total, page=page, pageSize=page_size
        )

    ds_counts = await scenario_store.dataset_counts(db)
    sch_counts = await scheme_store.scheme_counts(db)
    items = [
        scenario_store.to_list_item_shape(
            r,
            starred_ids=user_star_ids,
            data_set_count=ds_counts.get(r.scenario_id, 0),
            scheme_count=sch_counts.get(r.scenario_id, 0),
        )
        for r in page_rows
    ]
    return ScenarioListOut(items=items, total=total, page=page, pageSize=page_size)


# ── 4) POST /{id}/star (static suffix — before /{id}) ──────────────
@router.post(
    "/{scenario_id}/star", status_code=status.HTTP_204_NO_CONTENT
)
async def star_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str, body: StarIn
) -> None:
    # Verify the scenario exists AND is readable (404 instead of a
    # silent no-op — and no starring other users' private scenarios).
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    from ..services.user_stars import STAR_CAP, StarCapExceeded
    from ..services import user_stars as user_stars_svc

    try:
        await user_stars_svc.set_star(db, user.id, scenario_id, body.starred)
    except StarCapExceeded:
        # 关注上限 20 服务端兜底(M6-2;客户端先拦不变)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "star_cap_exceeded",
                "message": f"关注上限 {STAR_CAP} 个:请先取消部分关注再试",
            },
        )


# ── 4.1) POST /{id}/publish | /unpublish — 发布 / 下架 ─────────────
@router.post("/{scenario_id}/publish", response_model=Scenario)
async def publish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """发布:visibility → public,所有登录用户可读(取代 V1 公共库)。"""
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.set_visibility(db, scenario_id, "public")
    except KeyError as e:
        raise key_error_404(e)


@router.post("/{scenario_id}/unpublish", response_model=Scenario)
async def unpublish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """下架:visibility → private,仅 owner/admin 可读。"""
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        result = await scenario_store.set_visibility(db, scenario_id, "private")
    except KeyError as e:
        raise key_error_404(e)
    # 通知接线(P1b,权限方案 §3.2):admin 下架**他人** public 场景是
    # 全员视角下的写操作,须告知原作者(本人下架自己的不通知)。
    if user.role == "admin" and row.owner_id is not None and row.owner_id != user.id:
        from ..services import notifications as notify_svc
        from ..core.timeutil import ensure_aware
        try:
            await notify_svc.create_notification(
                db,
                user_id=row.owner_id,
                type_="scenario_unpublished",
                title=f"你的公共场景已被下架:{scenario_id}",
                body=f"管理员 {user.display_name or user.username} 将 "
                     f"{scenario_id} 从公共库下架(现为私有,仅你与管理员可见)。",
                link=f"/scenarios/{scenario_id}/detail",
            )
        except Exception:  # noqa: BLE001 — 通知失败不阻断下架
            pass
    return result


# ── 4.2) POST /{id}/copy — 深拷贝到我的(取代 V1 公共库"复制") ─────
@router.post(
    "/{scenario_id}/copy", response_model=Scenario, status_code=status.HTTP_201_CREATED
)
async def copy_scenario_to_me(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """深拷贝场景+用例+数据集;新属主 = 调用者,visibility=private。
    需要读权限(public 或自己的场景才可复制)。"""
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    try:
        return await scenario_store.copy_scenario(
            db,
            scenario_id,
            new_owner=user.display_name or user.username,
            new_owner_id=user.id,
        )
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"scenario_id_exists": 409})


# ── 5) GET /{id} ───────────────────────────────────────────────────
@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    try:
        return await scenario_store.get(db, scenario_id, user_id=user.id)
    except KeyError as e:
        raise key_error_404(e)


# ── 5.1) GET /{id}/draft — 返回完整 ScenarioDraft (含 config/resource) ───
# 用于"从场景库行级导出已保存场景":普通 GET 不带 config/resource 因为
# 列表场景里这份数据量大;draft 是按需调用的。
@router.get("/{scenario_id}/draft", response_model=ScenarioDraft)
async def get_scenario_draft(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> ScenarioDraft:
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    # 方案读写唯一面 = /run-schemes CRUD(阶段④:V1 sidecar 读侧回填下线,
    # draft 不再携带 runSchemes 键;存量 payload 中的同键被 extra=ignore
    # 静默忽略)。
    payload = dict(row.payload or {})
    try:
        return ScenarioDraft.model_validate(payload)
    except Exception as e:  # noqa: BLE001
        # 内部错误信息只记到日志,对外只暴露最小可读描述
        logger.exception(
            "get_scenario_draft: scenario_id=%s payload corrupted", scenario_id,
        )
        raise HTTPException(
            status_code=500,
            detail="draft_corrupt: 存储的 ScenarioDraft 与 schema 不一致",
        )


# ── 6) PUT /{id} ───────────────────────────────────────────────────
@router.put("/{scenario_id}", response_model=Scenario)
async def put_scenario(
    user: CurrentUser,
    db: DbSession,
    scenario_id: str,
    body: ScenarioDraft,
) -> Scenario:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.update(
            db,
            scenario_id,
            body,
            user_id=user.id,
            new_owner=user.display_name or user.username,
        )
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"scenario_id_changed": 409})


# ── 7) DELETE /{id} ────────────────────────────────────────────────
@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> None:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        await scenario_store.delete(db, scenario_id)
    except KeyError as e:
        raise key_error_404(e)
