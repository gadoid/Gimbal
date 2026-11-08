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

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._error_mapping import key_error_404, not_found_404, value_error_http
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import (
    ExportOverlay,
    PreviewPlateError,
    PreviewPlateIn,
    PreviewPlateResponse,
    Scenario,
    ScenarioCopyIn,
    ScenarioDraft,
    ScenarioListOut,
    ScenarioOptionsItem,
    ScenarioOptionsOut,
    StarIn,
)
from ..services import plate_client, run_dispatcher, scheme_store, scenario_store
from ..services import run_prepare
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


async def _require_owner(
    db, user: CurrentUser, row: ComposerScenario, *, verb: str = "write",
) -> None:
    """写闸(表 B scenario.{write,delete},S1.2 区感知):读判先行
    (不可见 → 404 不泄露存在性);可读但无写权 → 403。表 B =
    owner(私有区)∨ member(项目)∨ maintainer(公共项目)。"""
    # owner_id (int user.id) is the single ownership authority
    # (canonical rule in _ownership;表 B write/delete = 属主单判,W3 起
    # admin 无旁路 —— 私有区归属主)。读判含 ref:被引用者可读 ⇒ 403
    # 而非 404(不与可读性自相矛盾);完全不可见才 404(不泄露存在性)。
    from ._ownership import can_read_scenario_row

    if not await can_read_scenario_row(db, user, row):
        raise HTTPException(
            status_code=404,
            detail=f"scenario_not_found: {row.scenario_id}")
    from ._ownership import can

    if not await can(db, user, "scenario", verb, row):
        raise HTTPException(
            403,
            detail="not_owner: only the scenario's owner (or a project "
                   "member / maintainer) can modify it",
        )


async def _require_visibility_actor(
    db, user: CurrentUser, row: ComposerScenario, *, verb: str,
) -> None:
    """发布/下架闸(表 B scenario.{publish,unpublish},authz W3):
    私有区 owner / 公共项目维护者(maintainer)可发布与下架;Admin+
    仅对公共项目对象有下架权(public_admin,R6 —— admin 对他人对象
    没有发布权)。完全不可见(含 ref 不达)
    → 404(不泄露存在性);可读但无权 → 403。"""
    from ._ownership import can, can_read_scenario_row

    if not await can_read_scenario_row(db, user, row):
        raise HTTPException(
            status_code=404,
            detail=f"scenario_not_found: {row.scenario_id}")
    # S1.1:谓词含项目维度(padmin / maintainer),走 async can
    if not await can(db, user, "scenario", verb, row):
        raise HTTPException(
            status_code=403,
            detail="not_owner: only the owner (or an operator, for "
                   "already-public scenarios) can change visibility",
        )


async def _require_reader_async(
    db, user: CurrentUser, row: ComposerScenario
) -> None:
    """读闸(完整判定 §7.6,表 B scenario.read):public ∨ 属主 ∨ 引用。"""
    from ._ownership import can_read_scenario_row
    if not await can_read_scenario_row(db, user, row):
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {row.scenario_id}"
        )


def _draft_to_full_scenario_dict(
    draft: ScenarioDraft, owner: str
) -> dict:
    """Build a plate-boundary Scenario dict from the platform container.

    definition is already plate-shaped (it's the authoritative structure);
    M2 步骤 4(Q18)起定义即纯 M2 —— 不再补 plate 默认值,且与存储同规
    剥离平台元数据(meta.scenarioId/updateTime/owner 只在行的列上),
    保证导出产物与执行 case 同形(overlay 黄金等价)。
    orchestration 是平台侧投影,绝不外发。
    """
    from ..services.scenario_store import _strip_platform_meta
    definition = dict(draft.definition)
    meta = definition.get("meta")
    if isinstance(meta, dict):
        definition["meta"] = _strip_platform_meta(meta)
    return definition


async def _materialized_executable(
    db: AsyncSession,
    *,
    definition: dict,
    ui: dict | None,
    owner_id: int,
    overlay: ExportOverlay | None = None,
    scenario_owner_id: int | None = None,
) -> dict:
    """plate /convert + 执行同源物化 —— preview-plate 与 /export 共用(W1)。

    输入任意来源的 definition(草稿或落库行;平台 meta 剥离幂等),输出
    gimbal 可执行形态:overlay=None(默认导出)时凭证/服务绑定零注入,
    carry 无条件物化(spec §4.3);overlay 携带 serviceBindings 时按 spec
    §8 注入凭证。plate 拒收/不可达原样上抛,由调用方映射 422/502。

    装载准备统一走 run_prepare.prepare_exec(N1 归一 + 评审 §3.1A):
    凭证清单/解析(仅 overlay;AuthResolveError → 422)、别名地址、
    carry、内置 users 基座与执行链同一实现;resolve_mode="none" ——
    导出按定义原样 convert(不做修订解析),payload 以容器形状包裹
    definition(definition_from_payload 解包)。
    """
    from ..services.scenario_store import _strip_platform_meta as _spm

    clean = dict(definition)
    _meta = clean.get("meta")
    if isinstance(_meta, dict):
        clean["meta"] = _spm(_meta)
    data = await plate_client.convert(clean)
    converted = (data or {}).get("converted") or {}
    # Optional export overlay (spec §8): convert 之后、返回之前物化
    # (POST-convert 位点,明文绑定/凭证不过 plate)。物化语义与
    # run 执行链(run_dispatcher._fanout)同源 — 黄金等价:同场景同
    # overlay 下产物 ≡ 基线单行 case.json,逐字段相等。
    if overlay is not None:
        # 注入清单与 dispatch 同构(spec §7.3 矩阵:导出侧 = 执行侧):
        # exec_auth_aliases 唯一实现(模板扫描 ∪ 绑定 authAlias ∪
        # **别名表凭证默认**)在 prepare_exec 内消费完整绑定(dict 值
        # 读 authAlias,与 url 物化互不干扰)。
        service_bindings = {k: b.model_dump(by_alias=True)
                            for k, b in overlay.service_bindings.items()}
    else:
        # 默认导出(无 overlay):凭证/服务绑定零注入 — overlay 是它们
        # 的唯一开关(with_auth=False 跳过清单+解析);carry 见下方
        # (prepare_exec 内无条件构建)。
        service_bindings = {}
    try:
        prep = await run_prepare.prepare_exec(
            run_dispatcher.session_factory, {"definition": clean},
            owner_id=owner_id, bindings=service_bindings,
            ui_field_states=(ui or {}).get("fieldStates") or {},
            resolve_mode="none", with_auth=overlay is not None,
            # authz W6 主规则:落库行的导出走 owner_id(执行人)≠ 属主
            # ⇒ 内置 users 当空(fail-closed:None 同样当空);preview-plate
            # 的草稿由本人即席提供,调用方显式传 scenario_owner_id=本人
            scenario_owner_id=scenario_owner_id)
    except run_prepare.AuthResolveError as e:
        # 凭证路径 fail-fast(dispatch 整单失败同语义;导出无执行
        # 副作用,直接拒答 422 而非 500)。
        raise HTTPException(
            status_code=422,
            detail={"code": "auth_resolve_failed", "message": str(e)},
        )
    return materialize_run_copy(
        converted,
        service_bindings=service_bindings,
        resolved_auths=prep.resolved_auths,
        # users 唯一来源 = 属主规则裁定后的内置凭证(属主导出照旧带
        # 明文 —— 10-14 口径;非属主为空)+ overlay 解析的凭证
        built_in_users=prep.built_in_users,
        carry_context=prep.carry_ctx,
        alias_base_urls=prep.alias_base_urls,
    )


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
        converted = await _materialized_executable(
            db, definition=scenario_dict, ui=body.ui,
            owner_id=user.id, overlay=body.overlay,
            scenario_owner_id=user.id)   # 草稿:执行人即作者
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
    # ``errors[]`` inside ``converted`` = 字段级问题,原样透传;
    # ``converted`` 即 "gimbal-executable" 结构(W1 起与 /export 同源,
    # 组装收敛在 _materialized_executable)。
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
        out = await scenario_store.create(
            db, body, owner=owner, owner_id=user.id
        )
    except ValueError as e:
        # Pydantic validation errors already translated to 422 by FastAPI.
        raise value_error_http(e, {
            "scenario_id_exists": 409,
            # ⑥:store 级版本声明闸的两种裁定 → 422(输入被拒)
            "meta_plate_missing_system": 422,
            "meta_plate_invalid_ref": 422,
        })
    # 时间线:新建此前无痕(另存为/分享各有事件,唯手工新建缺失)。
    # 挂路由层而非 store.create —— copy_scenario 内部也调 create,
    # 挂 store 会与 save_as/share_copy 双记。
    from ..services import activity as activity_svc
    await activity_svc.record(
        db, actor_id=user.id, kind="scenario.created",
        resource_type="scenario", resource_id=out.meta.scenario_id,
        detail={"name": out.meta.name, "source": "manual"})
    return out


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
        select(ComposerScenario.scenario_id, ComposerScenario.project_id,
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
        is_public = row.project_id is not None
        execs = by_sid_execs.get(sid, [])
        if not is_public:
            lock = default_scheme.get(sid)
            execs = [e for e in execs if lock and _scheme_of(e) == lock]
        trend = [e.status for e in execs[:5]][::-1]
        # W21 趋势切换点:与 trend 同序的修订钉定签名(未钉 = None),
        # SignalDots 在相邻签名不同处标「修订切换」
        trend_pins = [
            ",".join(f"{k}#{v}" for k, v in sorted(
                (e.plate_pins or {}).items())) or None
            for e in execs[:5]
        ][::-1]
        last = execs[0] if execs else None
        own = row.owner_id == user.id
        out[sid] = {
            "trend": trend,
            "trendPins": trend_pins,
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
    scope: Literal["mine", "all"] = "all",
) -> dict:
    """五维 facets:modules/systems/tags/authors/priorities 可选值+计数。

    替代前端「全量拉回 FilterPopover unique」的 M1 过渡形态。PG 走
    GROUP BY + jsonb unnest;SQLite Python 兜底(方言分派同 list)。
    scope 与 list 同口径(§5.1):mine 只统计自己创建的;visibility=public
    时 scope 不叠加。
    """
    if visibility == "public":
        scope = "all"
    is_pg = db.bind.dialect.name == "postgresql"
    if is_pg:
        from ..services import scenario_query
        out = await scenario_query.facets(
            db, user=user, viewer_id=user.id, q=q, visibility=visibility,
            scope=scope)
        return {
            dim: [{"value": k, "count": n} for k, n in pairs]
            for dim, pairs in out.items()
        }

    # (SQLite 兜底聚合分支已随 SQLite 退役删除:PG 分支无条件 return)

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
    scope: Literal["mine", "all"] = "all",
    project_id: Annotated[int | None, Query(ge=1)] = None,
    updated_within: Literal["24h", "7d", "30d"] | None = None,
    starred: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    fields: Literal["options"] | None = None,
) -> ScenarioListOut | ScenarioOptionsOut:
    """列表(Page 信封 + M1 响应投影,PG迁移方案 §4.1/§7 M1)。

    读侧收紧(authz W3 后全角色同镜头):public + 自己的 + 被引用的。可选
    ``visibility=public|private`` 再过滤一层,供前端"公共 / 我的"分组
    标签使用。

    属主过滤直接在 store 已加载的行上做(此前为 readable_ids 再跑
    一趟全表投影,单请求双全表扫描)。

    浏览镜头(《Suite成员层、引用分享与浏览镜头-设计方案》§5.1):
    ``scope=mine`` = 只看自己创建的(含已发布),对 admin 同样生效——
    镜头是查询偏好不动权限边界;API 默认 ``all`` 与现行行为完全一致,
    前端负责默认传 mine。``visibility=public`` 是公共页专用口径,
    scope 不叠加(公共页行为不变)。

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

    # 镜头参数归一(§5.1):公共页口径优先,scope 不叠加。
    if visibility == "public":
        scope = "all"

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
            visibility=visibility, scope=scope,
            project_id=project_id, starred_ids=starred_ids,
            page=page, page_size=page_size,
        )
        if fields == "options":
            items = [
                ScenarioOptionsItem(
                    scenarioId=r.scenario_id,
                    name=scenario_store._meta_from_row(r).name,
                    visibility=("public" if r.project_id is not None
                                else "private"),
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
    # P2 引用分支(§7.6,与 visibility_clause 同口径):纯判先行
    #(表 B scenario.read + 项目上下文,谓词单点 can_pure),不通过者
    # 用一次引用集合复核(团队规模有界,取集合可接受)。
    # 本分支仅 starred=false(排除收藏)走 Python 侧,其余走 SQL 分支。
    from ._ownership import can_pure
    from ..services.zone import my_project_roles, public_project_id
    _ctx = dict(
        public_project_id=await public_project_id(db),
        project_roles=await my_project_roles(db, user.id))
    _pure_readable = [
        r for r in rows
        if can_pure(user, "scenario", "read", r, **_ctx)
    ]
    _maybe = [r for r in rows if r not in _pure_readable]
    if _maybe:
        from ._ownership import referenced_scenario_ids
        _ref_ids = await referenced_scenario_ids(db, user.id)
        readable = _pure_readable + [r for r in _maybe
                                     if r.scenario_id in _ref_ids]
    else:
        readable = _pure_readable
    if scope == "mine":
        readable = [r for r in readable if r.owner_id == user.id]
    if visibility:
        readable = [r for r in readable
                    if ("public" if r.project_id is not None
                        else "private") == visibility]
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
                visibility=("public" if r.project_id is not None
                            else "private"),
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
    await _require_reader_async(db, user, row)
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
def _axis_actor(user, row) -> tuple[int | None, dict]:
    """时间线归属人:admin 代操作落在**受影响人**(资源属主)轴上,
    detail.by 记操作者;本人操作 = 本人轴。activity.actor_id 语义本是
    「时间线归属人」(handoff 的 actor 即接收方),不是动作发起者。"""
    if user.id == row.owner_id:
        return user.id, {}
    return row.owner_id, {"by": user.display_name or user.username}


async def _record_admin_visibility_audit(
    db, user, row, scenario_id: str, action: str,
) -> None:
    """Admin+ 越属主的可见性变更入审计(属主自发布/自下架不记 —— 与
    suite.admin_unpublish 同口径,只记越属主那一半)。W3 后越属主
    只剩 public_admin 下架公共项目对象一条路,入口闸已保证主体是
    Admin+。"""
    if user.id == row.owner_id:
        return
    from ..services import audit as audit_svc
    await audit_svc.record(
        db, actor_id=user.id,
        actor_name=user.display_name or user.username,
        action=action,
        resource_type="scenario", resource_id=scenario_id,
        resource_name=row.name,
        detail={"ownerId": row.owner_id, "name": row.name})
async def _take_down_public_copy(
    db, user, *, copy_row, original_id: str | None,
) -> None:
    """下架公共副本(S1.3):删副本(delete 全级联)+ 连带 —— 引用它的
    公共模板软删(卡片「已移除」,通知持有人)、含它的公共套件副本
    一并下架(通知维护者;本人操作不通知)。"""
    from sqlalchemy import select as _sel

    from ..models.suite import Suite as _Suite, SuiteMember as _SM
    from ..services import integration_runner as _ir

    copy_sid = copy_row.scenario_id
    # ① 引用副本的公共模板 → 软删(随 delete 的事务一并提交)
    tpls = await _ir.retire_templates_for_public_target(
        db, scenario_id=copy_sid)
    # ② 含副本的公共套件副本 → 一并下架(成员随 FK CASCADE;引用
    #    套件的公共模板同样软删)
    hit = (await db.execute(
        _sel(_Suite).join(_SM, _SM.suite_id == _Suite.id)
        .where(_SM.scenario_id == copy_sid,
               _Suite.project_id.is_not(None)))).scalars().all()
    suite_tpls = []
    for su in hit:
        suite_tpls += await _ir.retire_templates_for_public_target(
            db, suite_id=su.id)
    # ③ 删副本(内部提交;模板软删骑同一事务)
    await scenario_store.unpublish_public_copy(db, copy_sid)
    for su in hit:
        await db.delete(su)
        await db.commit()
    # ④ 人话通知(best-effort,提交后)
    for tpl in tpls + suite_tpls:
        try:
            await _ir.notify_subscribers(
                tpl,
                title=f"集成任务「{tpl.name}」已移除",
                message="引用的公共内容已下架,订阅随之失效;"
                        "卡片会显示「已移除」,可自行删卡")
        except Exception:  # noqa: BLE001
            pass
    for su in hit:
        if su.owner_id is not None and su.owner_id != user.id:
            from ..services import notifications as _ns
            try:
                await _ns.create_notification(
                    db, user_id=su.owner_id,
                    type_="scenario_unpublished",
                    title="你的公共 Suite 已连带下架",
                    body=f"成员场景 {original_id or copy_sid} 下架,"
                         f"其所属公共 Suite 副本已一并下架。",
                    link=f"/suites/{su.id}")
            except Exception:  # noqa: BLE001
                pass


@router.post("/{scenario_id}/publish", response_model=Scenario)
async def publish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """发布 = 复制到公共项目(S1.3,s1-detail §五):

    * 公共副本 id = ``<原 id>-public``,**恒剥离**内置凭证与数据集
      敏感列(同属主也剥 —— 公共副本不落明文,原件仍在属主手里);
      ``forked_from_id`` = 原件 id;owner_id 不动(= 维护者)。
    * 原件不动:恒 private(可继续执行/维护);重发布 = 同 id 覆盖
      副本内容(订阅者经指纹闸在下次执行暂停待确认)。
    * 已在公共项目上的行(存量迁入的无原件公共内容)再发布为空操作。
    * 表 B scenario.publish = owner ∨ padmin ∨ maintainer(R6:Admin+
      对他人对象无发布权)。
    """
    from ..services.zone import public_project_id

    row = await _load_row(db, scenario_id)
    pid = await public_project_id(db)
    if pid is not None and row.project_id == pid:
        # 已在公共项目(存量迁移行 / 副本本体):无原件可复制 → 空操作
        await _require_visibility_actor(db, user, row, verb="publish")
        return await scenario_store.get(db, scenario_id, user_id=user.id)
    await _require_visibility_actor(db, user, row, verb="publish")
    republished = (await scenario_store.find_public_copy(
        db, scenario_id)) is not None
    try:
        out, _created = await scenario_store.publish_copy(db, scenario_id)
    except KeyError as e:
        raise key_error_404(e)
    # 时间线:发布/重发布记在原件轴(副本自身时间线随复制已有事件)
    from ..services import activity as activity_svc

    actor_id, extra = _axis_actor(user, row)
    await activity_svc.record(
        db, actor_id=actor_id, kind="scenario.published",
        resource_type="scenario", resource_id=scenario_id,
        detail={"name": row.name, "publicCopyId": out.meta.scenario_id,
                "republished": republished, **extra})
    return out


@router.post("/{scenario_id}/unpublish", response_model=Scenario)
async def unpublish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """下架 = 删除公共副本(S1.3)。三条路径:

    * 私有原件上调用:找到其公共副本删除(属主动作);
    * 公共副本上调用:maintainer ∨ public_admin 直接删;
    * 存量迁入的无原件公共行(forked_from_id 为空)409 —— 只有这一
      份内容,先「复制到私有区」留底再下架。

    连带:引用副本的公共模板转「已移除」(软删 + 通知持有人);含
    副本的公共套件副本一并下架。回包 = 原件的读形态(下架后回到
    私有态;无原件路径不可能走到回包)。
    """
    from ..services.zone import public_project_id

    from ._ownership import can

    row = await _load_row(db, scenario_id)
    pid = await public_project_id(db)

    if row.project_id is None:
        # 私有原件:删它的公共副本(没有 → 常规闸 403,行为同旧)
        copy_row = await scenario_store.find_public_copy(db, scenario_id)
        if copy_row is None:
            await _require_visibility_actor(
                db, user, row, verb="unpublish")
            raise HTTPException(  # pragma: no cover — 闸必拒
                403, detail="not_owner")
        if not await can(db, user, "scenario", "write", row):
            raise HTTPException(
                403,
                detail="not_owner: only the scenario's owner can "
                       "unpublish it")
        await _take_down_public_copy(
            db, user, copy_row=copy_row, original_id=scenario_id)
        from ..services import activity as activity_svc

        actor_id, extra = _axis_actor(user, row)
        await activity_svc.record(
            db, actor_id=actor_id, kind="scenario.unpublished",
            resource_type="scenario", resource_id=scenario_id,
            detail={"name": row.name,
                    "publicCopyId": copy_row.scenario_id, **extra})
        return await scenario_store.get(db, scenario_id, user_id=user.id)

    if pid is not None and row.project_id == pid:
        # 公共行:维护者撤下 / Admin+ 治理下架
        await _require_visibility_actor(db, user, row, verb="unpublish")
        if row.forked_from_id is None:
            raise HTTPException(status_code=409, detail={
                "code": "public_copy_is_original",
                "message": "这份公共内容没有私有原件(存量迁入),"
                           "先「复制到私有区」留底再下架"})
        original_id = row.forked_from_id
        await _take_down_public_copy(
            db, user, copy_row=row, original_id=original_id)
        from ..services import activity as activity_svc

        orig = await scenario_store.get_row(db, original_id)
        actor_id, extra = _axis_actor(
            user, orig if orig is not None else row)
        await activity_svc.record(
            db, actor_id=actor_id, kind="scenario.unpublished",
            resource_type="scenario", resource_id=original_id,
            detail={"name": row.name, "publicCopyId": scenario_id,
                    **extra})
        # 越属主下架(Admin+ 治理):入审计 + 通知维护者
        await _record_admin_visibility_audit(
            db, user, row, scenario_id, "scenario.admin_unpublish")
        if row.owner_id is not None and row.owner_id != user.id:
            from ..services import notifications as notify_svc

            try:
                await notify_svc.create_notification(
                    db, user_id=row.owner_id,
                    type_="scenario_unpublished",
                    title=f"你的公共场景已被下架:{original_id}",
                    body=f"管理员 {user.display_name or user.username} "
                         f"下架了 {original_id} 的公共副本"
                         f"(原件仍在你的私有区)。",
                    link=f"/scenarios/{original_id}/detail")
            except Exception:  # noqa: BLE001
                pass
        return await scenario_store.get(
            db, original_id, user_id=user.id)

    # 普通项目场景:无下架语义(不在公共项目)→ 常规闸 403
    await _require_visibility_actor(db, user, row, verb="unpublish")
    raise HTTPException(  # pragma: no cover — 闸必拒
        403, detail="not_owner")


@router.post(
    "/{scenario_id}/copy", response_model=Scenario, status_code=status.HTTP_201_CREATED
)
async def copy_scenario_to_me(
    user: CurrentUser, db: DbSession, scenario_id: str,
    payload: ScenarioCopyIn | None = None,
) -> Scenario:
    """深拷贝场景+用例+数据集;新属主 = 调用者,visibility=private。
    需要读权限(public 或自己的场景才可复制)。

    带 ``name``(另存为,2026-09-23 批次 F2):与本人已有场景重名 →
    409 ``name_taken``,detail 带 ``suggestion``(计数后缀名),前端
    确认后带 suggestion 重发;重名判定走 resolve_name_conflict 唯一实现。
    """
    row = await _load_row(db, scenario_id)
    await _require_reader_async(db, user, row)
    name = (payload.name if payload is not None else None) or ""
    name = name.strip() or None
    if name is not None:
        resolved, taken = await scenario_store.resolve_name_conflict(
            db, user.id, name)
        if taken:
            raise HTTPException(
                status_code=409,
                detail={"code": "name_taken", "suggestion": resolved},
            )
    try:
        return await scenario_store.copy_scenario(
            db,
            scenario_id,
            new_owner=user.display_name or user.username,
            new_owner_id=user.id,
            new_name=name,
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
    await _require_reader_async(db, user, row)
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
    await _require_reader_async(db, user, row)
    # 方案读写唯一面 = /run-schemes CRUD(阶段④:V1 sidecar 读侧回填下线,
    # draft 不再携带 runSchemes 键;存量 payload 中的同键被 extra=ignore
    # 静默忽略)。authz W6:非属主读不带内置凭证(原件不动)。
    payload = scenario_store.payload_for_viewer(
        row.payload, viewer_id=user.id, owner_id=row.owner_id)
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
    await _require_owner(db, user, row)
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
        raise value_error_http(e, {
            "scenario_id_changed": 409,
            "meta_plate_missing_system": 422,
            "meta_plate_invalid_ref": 422,
        })


class TransferIn(BaseModel):
    toUserId: int


@router.post("/{scenario_id}/transfer")
async def transfer_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str,
    body: TransferIn,
) -> dict:
    """S1-e 转移维护者:仅公共项目副本(表 B scenario.transfer =
    maintainer ∨ public_admin;私有原件不适用 —— 走「另存为/分发」)。
    受让人在职非系统;新旧维护者都收通知,动态流记 from/to。"""
    from ._ownership import can

    from ..models.user import User
    from ..services import maintenance_transfer as mt
    from ..services.zone import public_project_id

    row = await _load_row(db, scenario_id)
    if row.project_id != await public_project_id(db):
        raise HTTPException(404, detail=f"scenario_not_found: {scenario_id}")
    if not await can(db, user, "scenario", "transfer", row):
        raise HTTPException(403, detail={
            "code": "not_maintainer",
            "message": "只有维护者(或 Admin+)能转移公共内容的维护者"})
    to_user = await db.get(User, body.toUserId)
    if (to_user is None or not to_user.is_active or to_user.is_system
            or to_user.id == row.owner_id):
        raise HTTPException(422, detail={
            "code": "transferee_invalid",
            "message": "受让人须为在职、非系统用户(且非当前维护者)"})
    await mt.transfer_maintenance(
        db, obj=row, obj_type="scenario", to_user=to_user, actor=user,
        obj_name=row.name or scenario_id)
    return {"transferredTo": to_user.id, "scenarioId": scenario_id}


# ── 7) DELETE /{id} ────────────────────────────────────────────────
@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> None:
    row = await _load_row(db, scenario_id)
    await _require_owner(db, user, row, verb="delete")
    owner_id, name = row.owner_id, row.name
    # 引用者名单必须在删除**之前**取 —— share_refs 行随 FK CASCADE 消失
    from sqlalchemy import select as _sel

    from ..models.share_ref import ShareRef
    referrers = (await db.execute(_sel(ShareRef.grantee_user_id).where(
        ShareRef.scenario_id == scenario_id))).scalars().all()
    try:
        await scenario_store.delete(db, scenario_id)
    except KeyError as e:
        raise key_error_404(e)
    # 引用失效通知(与 suite 删除/用户处置同口径 —— 此前场景删除是三处
    # 里唯一静默的,被分享人「共享给我的」列表无痕缩水)
    from ..services import notifications as notify_svc

    for uid in referrers:
        try:
            await notify_svc.create_notification(
                db, user_id=uid, type_="share_ref_resource_deleted",
                title=f"引用失效:{name or scenario_id}",
                body=f"场景「{name or scenario_id}」已被删除,引用分享随之结束",
                resource_type="scenario", resource_id=scenario_id)
        except Exception:  # noqa: BLE001 — 通知 best-effort,不阻断删除
            await db.rollback()
    # 时间线:删除事件(既有条目从此变孤儿深链,补事件让消失可解释)
    from ..services import activity as activity_svc

    actor_id, extra = _axis_actor(user, row)
    await activity_svc.record(
        db, actor_id=actor_id, kind="scenario.deleted",
        resource_type="scenario", resource_id=scenario_id,
        detail={"name": name, **extra})
    # (W3 删除收敛为属主单判:scenario.admin_delete 审计随 admin 越属主
    # 旁路一并消亡 —— 越属主删除在入口闸就 403/404,到不了这里)


# ── R19（Release v4.4 §6.5）:导入导出以 meta.plate 为契约 ──────────

@router.get("/{scenario_id}/export")
async def export_scenario(
    scenario_id: str, user: CurrentUser, db: DbSession,
) -> dict:
    """导出**可执行形态**(W1,场景导入 v2.3 方案):plate 转换 + carry/
    别名 URL 无条件物化,与 preview-plate 默认导出同源(overlay 黄金
    等价)——Gimbal CLI 可直接执行,亦是导入流水线的唯一文件格式。
    带方案导出(凭证注入)走 preview-plate 的 overlay。"""
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise HTTPException(404, f"scenario_not_found: {scenario_id}")
    # 读闸同详情页:public ∨ 属主 ∨ 引用(404 不泄露存在性)。
    # (旧代码直接调三参 can_read_scenario —— 签名收紧后即 500,2026-10-12)
    await _require_reader_async(db, user, row)
    from ..services.scenario_store import definition_from_payload
    payload = row.payload or {}
    try:
        return await _materialized_executable(
            db,
            definition=definition_from_payload(payload),
            ui=payload.get("ui") or {},
            owner_id=user.id,
            scenario_owner_id=row.owner_id,
        )
    except plate_client.PlateUnavailableError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_unavailable", "message": e.message},
        )
    except plate_client.PlateRejectedError as e:
        # 落库行的定义被拒 = 数据与声明修订不匹配(存量漂移),422 指向
        # 数据问题而非网关故障,与 preview-plate 的裁定口径一致。
        raise HTTPException(
            status_code=422,
            detail={
                "code": "plate_rejected",
                "message": e.message,
                "errors": list(e.errors or []),
            },
        )


# ── R19 导入端点已退役(W3/W4,场景导入 v2.3 方案):可执行形态 +
# 析出映射 + 单事务落库的新端点在 routers/scenario_import.py
# (authz W7:CurrentUser + precheck 两阶段,create 建名另需 alias.write
# 能力),注册先于本模块的 /{scenario_id}。
