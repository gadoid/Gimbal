"""DB-backed CRUD for the V3 Scenario Composer Scenario rows.

Uses SQLAlchemy async sessions against the ``composer_scenarios`` table.

All public methods take an ``AsyncSession`` (or use the default from
``get_db`` via the routers); they never hold module-level state, so
concurrent requests see consistent reads/writes.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..core.timeutil import ensure_aware

from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_run_scheme import ComposerRunScheme
# 删除 ScenarioStep;ScenarioMeta 仍保留(读侧用)
from ..schemas.scenario_composer import (
    Orchestration,
    Scenario,
    ScenarioDraft,
    ScenarioListItem,
    ScenarioMeta,
)
from . import endpoint_ref_index
from . import scheme_store


# ─── write side ───────────────────────────────────────────────────
async def create(
    db: AsyncSession,
    draft: ScenarioDraft,
    *,
    owner: str = "",
    owner_id: int | None = None,
    visibility: str = "private",
) -> Scenario:
    """Insert a new scenario.  Raises ValueError on duplicate scenarioId.

    Server-side override: ``owner`` is always taken from the router's
    ``owner`` parameter (the authenticated user's display_name), so a
    caller cannot spoof the owner field by sending a different value in
    the request body.  ``owner_id`` 同理由路由层传入(int user.id,
    P1 起为归属判断主键);缺省 None = 归属未知(与 ETL 把历史 0 行
    映射 NULL 同语义 —— 0 在 PG 上恒违反 FK,M2 起不再落 0)。
    普通创建恒为 private;``visibility`` 参数仅供 P2 迁移复用(公共
    目录导入 → public)。
    """
    def_meta = draft.definition.get("meta") or {}
    scenario_id = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    server_owned = ScenarioMeta.model_validate({
        **def_meta,
        "scenarioId": scenario_id,
        "owner": owner or def_meta.get("owner", ""),
    })
    # Write the server-owned meta back into the stored definition so the
    # owner override (and any server-side meta normalization) survives a
    # read-back via _meta_from_row, which reads definition.meta.
    stored_definition = {
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": server_owned.model_dump(by_alias=True, mode="json"),
    }
    payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=draft.orchestration,
        # 注册表随容器重铸透传(spec v2 §3)— 不传则回落 default {}
        # 丢条目(copy 路径经 model_validate 后同样走到这里)。
        assertion_registry=draft.assertion_registry,
    ).model_dump(by_alias=True, mode="json")
    row = ComposerScenario(
        scenario_id=server_owned.scenario_id,
        owner_name=server_owned.owner,
        owner_id=owner_id,
        visibility=visibility,
        payload=payload,
    )
    db.add(row)
    try:
        # 挂钩在 try 内:sync 的 DELETE 会 autoflush 待插行,重复
        # scenario_id 的 IntegrityError 由此仍映射为 ValueError(契约不变)。
        await endpoint_ref_index.sync_scenario(db, server_owned.scenario_id, payload)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"scenario_id_exists: {scenario_id}") from e
    await db.refresh(row)
    # 场景创建即物化默认方案(工作台 spec §4.3/§5;
    # GET /run-schemes 侧的 ensure_default 是自愈兜底)。
    await scheme_store.ensure_default_scheme(db, server_owned.scenario_id)
    return await to_read_shape(db, row)


async def update(
    db: AsyncSession,
    scenario_id: str,
    draft: ScenarioDraft,
    *,
    user_id: int | None = None,
    new_owner: str = "",
) -> Scenario:
    """Replace an existing scenario.  Raises KeyError on miss.

    Refuses to change ``scenarioId`` (the row's primary key in the table
    and the unique identity the rest of the system uses).

    Server-side override: if ``new_owner`` is supplied, it's used in
    place of ``draft.definition["meta"]["owner"]`` so the caller can't
    re-assign the scenario to a different user mid-edit.
    """
    row = await _get_row(db, scenario_id)
    def_meta = draft.definition.get("meta") or {}
    req_sid = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    if req_sid != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    # Repair empty meta fields before validation: legacy / partially-edited
    # scenarios may carry an empty `module` or empty `system`, and we don't
    # want a routine save (e.g. baseline / dataset save) to fail on
    # metadata. ``create()`` mirrors this normalization, so a write
    # round-trip never widens the surface area of validation.
    repaired_meta = {
        **def_meta,
        "module": (def_meta.get("module") or "").strip() or "default",
        "system": list(def_meta.get("system") or []) or ["default"],
    }
    effective_owner = new_owner or def_meta.get("owner") or row.owner_name
    server_owned = ScenarioMeta.model_validate({
        **repaired_meta, "scenarioId": scenario_id, "owner": effective_owner,
    })
    # Write the server-owned meta back into the stored definition so the
    # owner override (and any server-side meta normalization) survives a
    # read-back via _meta_from_row, which reads definition.meta.
    stored_definition = {
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": server_owned.model_dump(by_alias=True, mode="json"),
    }
    row.owner_name = effective_owner
    # 方案不经 payload(阶段④:runSchemes sidecar 键下线)— 编排容器
    # 原样落库,方案读写唯一面是 /run-schemes CRUD(scheme_store)。
    orch_data = draft.orchestration.model_dump(by_alias=True, mode="json")
    row.payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=Orchestration.model_validate(orch_data),
        # 注册表编辑器整包替换语义(spec v2 §3):PUT 带就存、不带(旧
        # 客户端)回落空 dict — 键归编排器。
        assertion_registry=draft.assertion_registry,
    ).model_dump(by_alias=True, mode="json")
    await endpoint_ref_index.sync_scenario(db, scenario_id, row.payload)
    await db.commit()
    await db.refresh(row)
    return await to_read_shape(db, row, user_id=user_id)


async def delete(db: AsyncSession, scenario_id: str) -> None:
    """Delete a scenario and cascade its datasets.

    Raises KeyError on miss.  Uses a single transaction so a failure
    mid-cascade rolls everything back.
    """
    row = await _get_row(db, scenario_id)
    # Cascade order: data_sets → scenario (reverse FK).
    await endpoint_ref_index.drop_scenario(db, scenario_id)
    await db.execute(
        sa_delete(ComposerDataSet).where(
            ComposerDataSet.scenario_id == scenario_id
        )
    )
    await db.execute(
        sa_delete(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id
        )
    )
    # user_stars 随场景 CASCADE(M6-2)。PG 上 DB 级 CASCADE 已处理,
    # 这里是 SQLite 兜底(该方言默认不强制 FK,CASCADE 不触发)——
    # 单条机械 DELETE,非逐用户簿记。
    from ..models.permission import UserStar

    await db.execute(
        sa_delete(UserStar).where(UserStar.scenario_id == scenario_id)
    )
    await db.delete(row)
    await db.commit()


async def set_visibility(
    db: AsyncSession, scenario_id: str, visibility: str
) -> Scenario:
    """发布/下架:翻转 visibility(public ↔ private)。KeyError on miss."""
    if visibility not in ("public", "private"):
        raise ValueError(f"bad_visibility: {visibility}")
    row = await _get_row(db, scenario_id)
    row.visibility = visibility
    await db.commit()
    await db.refresh(row)
    return await to_read_shape(db, row)


async def copy_scenario(
    db: AsyncSession,
    scenario_id: str,
    *,
    new_owner: str,
    new_owner_id: int,
) -> Scenario:
    """深拷贝场景 + 数据集(替代 V1 公共库"复制到我的")。

    新 id = 原 id + ``-copy-<6hex>``;属主 = 调用者;visibility 恒为
    private(复制来的公共场景也要先归自己再自行发布)。
    """
    import copy as _copy
    from uuid import uuid4 as _uuid4

    src = await _get_row(db, scenario_id)
    suffix = _uuid4().hex[:6]
    new_sid = f"{scenario_id}-copy-{suffix}"[:128]

    payload = _copy.deepcopy(src.payload or {})
    definition = payload.get("definition")
    if isinstance(definition, dict):
        definition["scenarioId"] = new_sid
        meta = definition.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["scenarioId"] = new_sid
            meta["name"] = f"{meta.get('name') or src.scenario_id} (副本)"
            meta["owner"] = new_owner
    draft = ScenarioDraft.model_validate(payload)
    await create(db, draft, owner=new_owner, owner_id=new_owner_id)

    # data_sets 级联拷贝(Case 层已解散,数据集直接挂场景)
    dss = (
        await db.execute(
            select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == scenario_id
            )
        )
    ).scalars().all()
    for ds in dss:
        new_dsid = f"{ds.dataset_id}-copy-{suffix}"[:128]
        db.add(ComposerDataSet(
            dataset_id=new_dsid,
            scenario_id=new_sid,
            name=ds.name,
            description=ds.description,
            rows=_copy.deepcopy(ds.rows or []),
            # 变量锁本地放开清单按名存储 — 深拷贝必须带走,否则分叉
            # 场景的解锁语义静默丢失
            var_unlocks=list(ds.var_unlocks or []),
        ))
    # 方案随场景深拷贝 — 迁出 payload 后不再随 deepcopy 自动带走,
    # 显式复制(新 scheme_id,仿上方 data_sets 循环)。
    await scheme_store.copy_schemes(db, scenario_id, new_sid)
    await db.commit()
    return await to_read_shape(db, await _get_row(db, new_sid))


async def get(
    db: AsyncSession, scenario_id: str, *, user_id: int | None = None
) -> Scenario:
    row = await _get_row(db, scenario_id)
    return await to_read_shape(db, row, user_id=user_id)


# ─── read side ────────────────────────────────────────────────────
# 多值筛选参数的归一化形态:调用方(router)传逗号联合字符串或单值,store
# 归一为 list;updated_within 以「now - 窗口」的 naive-UTC cutoff 表达
# (行 updated_at 是 naive UTC,同基准比较)。
_UPDATED_WITHIN_WINDOWS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _split_csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _split_ints(v: str | int | None) -> list[int]:
    if v is None or v == "":
        return []
    if isinstance(v, int):
        return [v]
    out: list[int] = []
    for x in _split_csv(str(v)):
        try:
            out.append(int(x))
        except ValueError:
            continue
    return out


def _updated_cutoff(updated_within: str | None) -> datetime | None:
    # aware:与 row.updated_at 的比较双方言统一在 aware 空间(PG 读回 aware)
    window = _UPDATED_WITHIN_WINDOWS.get(updated_within or "")
    return (
        ensure_aware(datetime.utcnow() - window)
        if window is not None
        else None
    )


async def list_scenarios(
    db: AsyncSession,
    *,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: str | int | None = None,
    tag: str | None = None,
    author: str | None = None,
    updated_within: str | None = None,
    user_id: int | None = None,
) -> list[Scenario]:
    """List scenarios with optional filters — **tests only**.

    生产 list 端点(scenarios 路由)自行组合 ``list_rows`` → 属主过滤
    → ``dataset_counts`` → ``to_read_shape``/``to_list_item_shape``,
    不再经过本函数;这里保留供 store 单测做纯过滤断言。注意本函数
    **不做**可见性/属主过滤,不要在新路由里复用。

    ``q`` is a case-insensitive substring against scenarioId / name /
    module / description / tags.  ``system`` / ``module`` / ``tag`` /
    ``author`` / ``priority`` accept single values or comma-joined
    multi-values (semantics: 见 ``_passes_filters`` docstring)。
    ``user_id`` enables per-user ``starred`` flag.
    """
    rows = await list_rows(
        db, q=q, system=system, module=module, priority=priority,
        tag=tag, author=author, updated_within=updated_within,
    )
    ds_counts = await dataset_counts(db)
    return [
        await to_read_shape(
            db, r, user_id=user_id, data_set_count=ds_counts.get(r.scenario_id, 0)
        )
        for r in rows
    ]


async def list_rows(
    db: AsyncSession,
    *,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: str | int | None = None,
    tag: str | None = None,
    author: str | None = None,
    updated_within: str | None = None,
) -> list[ComposerScenario]:
    """Filtered rows (updated_at desc) — 调用方在已加载的行上做属主/
    可见性过滤,避免 list 端点为 readable_ids 再跑一趟全表扫描。"""
    stmt = select(ComposerScenario).order_by(ComposerScenario.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    systems = _split_csv(system)
    modules = _split_csv(module)
    priorities = _split_ints(priority)
    tags = _split_csv(tag)
    authors = _split_csv(author)
    cutoff = _updated_cutoff(updated_within)
    return [
        r for r in rows
        if _passes_filters(
            _meta_from_row(r), r, q=q, systems=systems, modules=modules,
            priorities=priorities, tags=tags, authors=authors,
            updated_cutoff=cutoff,
        )
    ]


async def dataset_counts(db: AsyncSession) -> dict[str, int]:
    """Batched per-scenario ΣrowCount (one GROUP BY instead of a per-row
    query — list endpoints were N+1 here)."""
    count_rows = (
        await db.execute(
            select(
                ComposerDataSet.scenario_id,
                func.sum(ComposerDataSet.row_count),
            ).group_by(ComposerDataSet.scenario_id)
        )
    ).all()
    return {sid: int(total or 0) for sid, total in count_rows}


async def owned_scenario_ids(db: AsyncSession, user) -> set[str]:
    """The set of scenario_ids ``user`` owns.

    Set-based SQL projection of the same ownership rule as
    ``routers/_ownership._user_matches``: ``owner_id`` (int user id) is
    the single authority.
    """
    return set(
        (
            await db.execute(
                select(ComposerScenario.scenario_id).where(
                    ComposerScenario.owner_id == user.id
                )
            )
        )
        .scalars()
        .all()
    )


# ─── helpers ──────────────────────────────────────────────────────
async def get_row(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario | None:
    """单行查询(scenario_id 是 string PK)。

    全后端唯一实现 — scenarios/_load_row、data_sets/_load_scenario、
    run_dispatcher/_find_scenario_by_id、runs.post_run 的内联查询都
    收敛到这里,避免多份拷贝各自漂移。
    """
    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    return res.scalar_one_or_none()


async def _get_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    row = await get_row(db, scenario_id)
    if row is None:
        raise KeyError(f"scenario_not_found: {scenario_id}")
    return row


async def to_read_shape(
    db: AsyncSession,
    row: ComposerScenario,
    *,
    user_id: int | None = None,
    data_set_count: int | None = None,
    scheme_count: int | None = None,
) -> Scenario:
    """Reconstruct the full Scenario response shape from DB row + joins.

    ``data_set_count`` may be precomputed by batch callers(list_scenarios
    的 GROUP BY);单行调用方缺省时这里现查。meta/tags project from the
    payload (mirror columns retired); starred is per-user.
    """
    if data_set_count is None:
        # dataSetCount (sum of rowCount across datasets under the scenario)
        ds_res = await db.execute(
            select(ComposerDataSet.row_count).where(
                ComposerDataSet.scenario_id == row.scenario_id
            )
        )
        data_set_count = sum(int(r[0] or 0) for r in ds_res.all())

    if scheme_count is None:
        sch_res = await db.execute(
            select(func.count()).select_from(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == row.scenario_id
            )
        )
        scheme_count = int(sch_res.scalar_one() or 0)

    meta = _meta_from_row(row)
    steps = steps_from_payload(row.payload)
    # stepCount is derived from the payload (the mirror column was
    # retired); len() of the persisted steps list is authoritative.
    # 方案不经 payload(阶段④:runSchemes sidecar 读侧回填下线)—
    # 方案列表唯一读面是 /run-schemes CRUD。
    config, resource, orchestration = _extras_from_payload(row.payload)
    # M6-2:收藏读时投影改 UserStar(marks_store 退役);单行详情一次
    # 预取,列表路径由调用方走 to_list_item_shape(集合注入)。
    from .user_stars import star_ids as _star_ids

    starred = (
        row.scenario_id in await _star_ids(db, user_id)
        if user_id is not None
        else False
    )
    return Scenario(
        meta=meta,
        steps=steps,
        config=config,
        resource=resource,
        orchestration=orchestration,
        dataSetCount=data_set_count,
        schemeCount=scheme_count,
        stepCount=len(steps),
        tags=list(meta.tags or []),
        starred=starred,
        visibility=row.visibility or "private",
    )


def to_list_item_shape(
    row: ComposerScenario,
    *,
    starred_ids: "set[str] | None" = None,
    data_set_count: int = 0,
    scheme_count: int = 0,
) -> ScenarioListItem:
    """列表行形态(M1 响应投影):meta + 计数 + starred,**不含**
    steps/config/resource/orchestration — 大 JSON 字段不出列表响应。

    stepCount/varCount 仍需读 payload(权威计数,只取长度不构造对象);
    查询侧的全表加载是 M1 接受的现状(M3 生成列接管)。
    """
    meta = _meta_from_row(row)
    # M6-2:收藏读时投影改 UserStar 集合(调用方一次 star_ids 预取,
    # 不再逐行查 marks_store)
    starred = (
        row.scenario_id in starred_ids if starred_ids is not None else False
    )
    definition = definition_from_payload(row.payload)
    config = definition.get("config")
    vars_ = config.get("vars") if isinstance(config, dict) else None
    return ScenarioListItem(
        meta=meta,
        dataSetCount=data_set_count,
        schemeCount=scheme_count,
        stepCount=len(steps_from_payload(row.payload)),
        varCount=len(vars_) if isinstance(vars_, dict) else 0,
        tags=list(meta.tags or []),
        starred=starred,
        visibility=row.visibility or "private",
    )


def _meta_from_row(row: ComposerScenario) -> ScenarioMeta:
    """Meta 投影:唯一权威是 payload.definition.meta。

    (M6-3:旧库 module/system 缺省的修复分支已删 —— ETL 已把修复值
    写回 payload,新写入恒经 create/update 的严格 meta。)
    双口径读时归一(G3/方案 §4):createTime/updateTime 同以 DB 行
    为权威(C3 照 C2 范式 —— payload 里客户端伪造/陈旧值不采信);
    scenarioId 缺键兜底 definition 顶层/行键(C1,存量行两处分叉时
    读侧不再各说各话)。SQLite CURRENT_TIMESTAMP 是 naive UTC,标上
    tzinfo 让 wire 输出 ISO-Z,前端 new Date() 才不会按本地时间错位。
    """
    payload = row.payload or {}
    definition = payload.get("definition") or {}
    meta_dict = dict(definition.get("meta") or {})
    meta_dict.setdefault(
        "scenarioId", definition.get("scenarioId") or row.scenario_id
    )
    meta_dict["createTime"] = ensure_aware(row.created_at)
    meta_dict["updateTime"] = ensure_aware(row.updated_at)
    return ScenarioMeta.model_validate(meta_dict)


def definition_from_payload(payload: dict | None) -> dict:
    """容器解包:``payload {definition, orchestration}`` → definition。

    全后端唯一的容器形状知识。run_dispatcher 的 steps 投影 / users
    读取 / 组装均复用本函数,容器形状再变时只改这里。
    """
    defn = (payload or {}).get("definition")
    return defn if isinstance(defn, dict) else {}


def steps_from_payload(payload: dict | None) -> list[dict]:
    """Steps live inside the container's definition now (plate-shaped dicts)."""
    raw = definition_from_payload(payload).get("steps") or []
    return [s for s in raw if isinstance(s, dict)]


def _extras_from_payload(
    payload: dict | None,
) -> tuple[dict | None, dict | None, Orchestration | None]:
    """Round-trip the persisted container's render-side sub-structure.

    The payload is the container ``{definition, orchestration}``.
    config/resource live under ``definition`` (plate-shaped); orchestration
    is a sibling of definition (platform render state). Returns ``(None,
    None, None)`` when absent so the frontend's default-rebuild fallback
    kicks in. Guards every read so a malformed row never 500s.
    """
    definition = (payload or {}).get("definition") or {}
    config = definition.get("config") if isinstance(definition, dict) else None
    if not isinstance(config, dict):
        config = None
    resource = definition.get("resource") if isinstance(definition, dict) else None
    if not isinstance(resource, dict):
        resource = None
    orch_raw = (payload or {}).get("orchestration")
    orchestration: Orchestration | None = None
    if isinstance(orch_raw, dict):
        try:
            orchestration = Orchestration.model_validate(orch_raw)
        except Exception:
            orchestration = None
    return config, resource, orchestration


def _passes_filters(
    meta: ScenarioMeta,
    row: ComposerScenario,
    *,
    q: str | None,
    systems: list[str],
    modules: list[str],
    priorities: list[int],
    tags: list[str],
    authors: list[str],
    updated_cutoff: datetime | None,
) -> bool:
    """Python 过滤的唯一口径(M1;M3 生成列上线后平移到 SQL,语义不变)。

    多值维度与前端 ``utils/filters.ts`` 的 ``applyFiltersToList`` 同语义:
    module/author/priority = 精确命中其一;system/tag = 行携带任一选中值
    (OR);``updated_cutoff`` = 行 updated_at 早于 cutoff 即滤掉(行缺
    updated_at 视为通过,与前端「不可解析时间戳放行」一致)。
    Filters read the payload's meta projection — the mirror columns
    were retired, so this is a method over the source, not over a copy.
    """
    if systems and not any(s in (meta.system or []) for s in systems):
        return False
    if modules and (meta.module or "") not in modules:
        return False
    if priorities and meta.priority not in priorities:
        return False
    if tags and not any(t in (meta.tags or []) for t in tags):
        return False
    if authors and (meta.author or "") not in authors:
        return False
    if q:
        ql = q.lower()
        haystacks = [
            row.scenario_id or "",
            meta.name or "",
            meta.module or "",
            meta.description or "",
        ]
        haystacks.extend(meta.tags or [])
        if not any(ql in (h or "").lower() for h in haystacks):
            return False
    if (
        updated_cutoff is not None
        and row.updated_at is not None
        and ensure_aware(row.updated_at) < updated_cutoff
    ):
        return False
    return True
