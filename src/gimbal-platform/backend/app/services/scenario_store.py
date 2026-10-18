"""DB-backed CRUD for the V3 Scenario Composer Scenario rows.

Uses SQLAlchemy async sessions against the ``composer_scenarios`` table.

All public methods take an ``AsyncSession`` (or use the default from
``get_db`` via the routers); they never hold module-level state, so
concurrent requests see consistent reads/writes.
"""
from __future__ import annotations
from .run_semantics import INTEGRATION, PIN, UNDECLARED, WORKING, invalid_reason, record_category, ref_category

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
from . import activity
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
# A-1 根因收口(2026-10-14):plate ConfigView 的 users 附带视图专有键
# (is_authenticated/remaining_seconds — 认证状态投影,非 M2
# UserCredential 字段)。UI 预填(useSystemPrefill)已剥,此处是保存闸
# 的第二道:手写载荷/API 直写路径同样不得把视图键落库 —— 落库即
# /convert extra_forbidden 拒收(执行 plate_rejected)。
_USER_VIEW_KEYS = ("is_authenticated", "remaining_seconds")


def _strip_user_view_keys(definition: dict) -> dict:
    users = ((definition.get("config") or {}).get("users")) \
        if isinstance(definition.get("config"), dict) else None
    if not isinstance(users, dict) or not users:
        return definition
    cleaned: dict = {}
    dirty = False
    for tag, u in users.items():
        if isinstance(u, dict) and any(k in u for k in _USER_VIEW_KEYS):
            cleaned[tag] = {k: v for k, v in u.items()
                            if k not in _USER_VIEW_KEYS}
            dirty = True
        else:
            cleaned[tag] = u
    if not dirty:
        return definition
    return {**definition,
            "config": {**definition["config"], "users": cleaned}}


async def enforce_meta_plate(definition: dict,
                             prev_meta_plate: dict | None = None) -> None:
    """版本声明闸(⑥下沉,2026-10-13;create/update/导入/适配提交共用)。

    * 锚定系统(endpoint 首段,``ext:`` 外部锚点豁免)必须声明 —— 未声明
      = 绕开 plate 按陈旧存储 binding 执行的过渡形态(C-2),唯一写入口
      收口后由本闸关闭;
    * 声明引用须有效(线/修订存在;working 豁免);
    * ``prev_meta_plate`` 提供且声明未变 → 跳过引用校验(防抖自动保存
      不放大 plate 调用);
    * plate 不可达 → 引用校验跳过(保存不因目录故障阻断;执行期门仍在),
      「必须声明」是本地判定,恒生效。

    Raises:
        ValueError: ``meta_plate_missing_system`` / ``meta_plate_invalid_ref``。
    """
    from . import plate_client, run_semantics

    meta = (definition or {}).get("meta") or {}
    meta_plate = meta.get("plate")
    meta_plate = meta_plate if isinstance(meta_plate, dict) else {}
    anchored = {
        s for s in run_semantics.anchored_systems({"definition": definition})
        if not s.startswith("ext:")}
    undeclared = sorted(s for s in anchored if not meta_plate.get(s))
    if undeclared:
        raise ValueError(
            f"meta_plate_missing_system: 锚定系统 {undeclared} 未声明版本"
            "(meta.plate 须给 <line>#<n> 或 working)")
    if prev_meta_plate is not None and prev_meta_plate == meta_plate:
        return          # 声明未变:跳过引用校验
    try:
        await plate_client.validate_meta_plate_refs(meta_plate)
    except plate_client.PlateUnavailableError:
        pass            # 目录故障不阻断保存(执行期门仍在)
    except plate_client.PlateRejectedError as e:
        raise ValueError(
            f"meta_plate_invalid_ref: 版本声明校验被 plate 拒绝: {e}") from e
    # validate_meta_plate_refs 自身的 ValueError 已带 meta_plate_invalid_ref 前缀


async def create_in_transaction(
    db: AsyncSession,
    draft: ScenarioDraft,
    *,
    owner: str = "",
    owner_id: int | None = None,
    visibility: str = "private",
    forked_from_id: str | None = None,
    forked_from_owner_name: str | None = None,
    forked_from_at: "datetime | None" = None,
) -> ComposerScenario:
    """Insert a new scenario **without committing**(导入 W2/T1:建别名 +
    写 carry + 建场景单事务落库,场景导入 v2.3 方案 §6)。

    写入行为与 :func:`create` 的写入部分一致(enforce_meta_plate /
    服务端 owner 覆盖 / 存储归一化 / endpoint 索引同步);**提交与错误
    映射是调用方的责任**——``sync_scenario`` 的 DELETE 会 autoflush
    待插行,重复 scenario_id 的 IntegrityError 在此浮出,调用方在事务
    边界统一 except 并映射(如 ``ValueError("scenario_id_exists: ...")``)
    后回滚整单。返回**未 refresh** 的 row(server_default 列需调用方
    在 commit 后 refresh)。
    """
    def_meta = draft.definition.get("meta") or {}
    scenario_id = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    await enforce_meta_plate(draft.definition)      # ⑥:唯一写入口收口
    server_owned = ScenarioMeta.model_validate({
        **def_meta,
        "scenarioId": scenario_id,
        "owner": owner or def_meta.get("owner", ""),
    })
    # M4/Q18（M2 §3）：存储的定义即纯 M2 实例 —— meta.scenarioId /
    # updateTime / owner 等平台元数据只在行的列上，不写进定义；
    # 顶层 scenarioId（M2 必填身份字段）由行写入。读侧 _meta_from_row
    # 从行的列组装展示 meta（createTime/updateTime/scenarioId/owner）。
    # Release 6.2：锚点步骤 call 的 binding 派生字段出存储（6.2）。
    stored_definition = _strip_user_view_keys(strip_binding_fields({
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": _strip_platform_meta(def_meta),
    }))
    payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=draft.orchestration,
        # 注册表随容器重铸透传(spec v2 §3)— 不传则回落 default {}
        # 丢条目(copy 路径经 model_validate 后同样走到这里)。
        assertion_registry=draft.assertion_registry,
        # M4:编辑器状态(ui.fieldStates)随容器透传
        ui=draft.ui,
    ).model_dump(by_alias=True, mode="json")
    row = ComposerScenario(
        scenario_id=server_owned.scenario_id,
        owner_name=server_owned.owner,
        owner_id=owner_id,
        visibility=visibility,
        payload=payload,
        forked_from_id=forked_from_id,
        forked_from_owner_name=forked_from_owner_name,
        forked_from_at=forked_from_at,
    )
    db.add(row)
    # sync 的 DELETE 会 autoflush 待插行,重复 scenario_id 的
    # IntegrityError 在此浮出 —— 由调用方在事务边界映射(见 docstring)。
    await endpoint_ref_index.sync_scenario(db, server_owned.scenario_id, payload)
    return row


async def create(
    db: AsyncSession,
    draft: ScenarioDraft,
    *,
    owner: str = "",
    owner_id: int | None = None,
    visibility: str = "private",
    forked_from_id: str | None = None,
    forked_from_owner_name: str | None = None,
    forked_from_at: "datetime | None" = None,
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

    提交包装器(W2/T1):常规创建/copy/fork/迁移脚本等既有调用方行为
    零变化;导入流水线走 :func:`create_in_transaction` 自管事务
    (别名/carry/场景单事务,场景导入 v2.3 方案 §6)。
    """
    scenario_id = (draft.definition.get("scenarioId")
                   or (draft.definition.get("meta") or {}).get("scenarioId")
                   or "")
    try:
        row = await create_in_transaction(
            db, draft, owner=owner, owner_id=owner_id,
            visibility=visibility, forked_from_id=forked_from_id,
            forked_from_owner_name=forked_from_owner_name,
            forked_from_at=forked_from_at)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ValueError(f"scenario_id_exists: {scenario_id}") from e
    await db.refresh(row)
    # 场景创建即物化默认方案(工作台 spec §4.3/§5;
    # GET /run-schemes 侧的 ensure_default 是自愈兜底)。
    await scheme_store.ensure_default_scheme(db, row.scenario_id)
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
    # F3:旧名快照(提交后判 rename/edit;在 payload 覆盖前取)
    old_name = (((row.payload or {}).get("definition") or {})
                .get("meta") or {}).get("name")
    await enforce_meta_plate(
        draft.definition,
        prev_meta_plate=(((row.payload or {}).get("definition") or {})
                         .get("meta") or {}).get("plate"))
    def_meta = draft.definition.get("meta") or {}
    req_sid = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    if req_sid != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    # A-1(2026-10-12):删「module 空写 default / system 空写 ["default"]」
    # 修复兜底 —— "default" 伪系统与 M11(meta.system 每系统须有 plate
    # 声明)冲突,ScenarioMeta 已对齐 M2 空值语义('' / []),存量空值
    # 原样入校验、原样存储。
    effective_owner = new_owner or def_meta.get("owner") or row.owner_name
    server_owned = ScenarioMeta.model_validate({
        **def_meta, "scenarioId": scenario_id, "owner": effective_owner,
    })
    # M4/Q18：同 create —— 平台元数据出定义，定义即纯 M2 实例。
    # Release 6.2：锚点步骤 call 的 binding 派生字段出存储（6.2）。
    stored_definition = _strip_user_view_keys(strip_binding_fields({
        **draft.definition,
        "scenarioId": server_owned.scenario_id,
        "meta": _strip_platform_meta(def_meta),
    }))
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
        # M4:编辑器状态(ui.fieldStates)随容器透传
        ui=draft.ui,
    ).model_dump(by_alias=True, mode="json")
    await endpoint_ref_index.sync_scenario(db, scenario_id, row.payload)
    await db.commit()
    await db.refresh(row)
    # 版本模型 4.1(M1):普通保存后,已验证修订 best-effort 升级为
    # 当时的生效修订 —— plate 不可达时保持原值,绝不阻塞保存主链。
    try:
        await _bump_verified_to_effective(db, row)
    except Exception:  # noqa: BLE001
        pass
    # F3 事件落账(业务提交后):name 变化 → rename,否则 edit;
    # edit 走短窗合并吸收 autosave(2.5s 防抖全量 PUT)。
    if old_name and server_owned.name and old_name != server_owned.name:
        await activity.record(
            db, actor_id=user_id, kind=activity.KIND_RENAME,
            resource_type="scenario", resource_id=scenario_id,
            detail={"name": server_owned.name,
                    "oldName": old_name, "newName": server_owned.name})
    else:
        await activity.record(
            db, actor_id=user_id, kind=activity.KIND_EDIT,
            resource_type="scenario", resource_id=scenario_id,
            detail={"name": server_owned.name})
    return await to_read_shape(db, row, user_id=user_id)


async def delete(db: AsyncSession, scenario_id: str) -> None:
    """Delete a scenario and cascade its datasets.

    Raises KeyError on miss.  Uses a single transaction so a failure
    mid-cascade rolls everything back.
    """
    row = await _get_row(db, scenario_id)
    # 重构方案约束 6(单点):场景删除 → 所有含它的 suite 清理编排配置
    # 引用并推进 rev,写在此处而非各调用方。成员行随后删除/级联。
    from sqlalchemy import select as _select
    from .suite_copy import scrub_config_references
    from ..models.suite import Suite, SuiteMember as _SuiteMember
    _suite_ids = (await db.execute(
        _select(_SuiteMember.suite_id).where(
            _SuiteMember.scenario_id == scenario_id))).scalars().all()
    if _suite_ids:
        _suites = (await db.execute(
            _select(Suite).where(Suite.id.in_(_suite_ids)))).scalars().all()
        for _s in _suites:
            _s.mode_config = scrub_config_references(
                dict(_s.mode_config or {}), {scenario_id})
            _s.rev += 1
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
    # suite_members 同款兜底(权限域二期 P1:场景删除 → 自动退出全部
    # suite;组合外键 CASCADE 的 SQLite 兜底)。
    from ..models.suite import SuiteMember

    await db.execute(
        sa_delete(UserStar).where(UserStar.scenario_id == scenario_id)
    )
    await db.execute(
        sa_delete(SuiteMember).where(SuiteMember.scenario_id == scenario_id)
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


async def resolve_name_conflict(
    db: AsyncSession, owner_id: int, desired_name: str
) -> tuple[str, bool]:
    """该 owner 名下已有同名场景 → 返回 (计数后缀名, True);否则原样。

    F1 分发(静默后缀)与 F2 另存为(前端确认后缀)共用 —— 重名判定
    的唯一实现,不各写一份。name 上限 64(ScenarioMeta.name
    max_length),拼后缀前先截断基名。基名本身也在入口钳一次:源场景
    name 为空时调用方用 scenario_id 兜底(最长 128),不撞名也得截断 ——
    放过去会在 meta 校验变成一个不好理解的 422。现状无任何 name 唯一
    约束(2026-09-23 评审拍板不加 DB 约束,存量重名会让索引迁移炸),
    本 helper 是软校验。
    """
    desired_name = desired_name[:64]
    names = {
        n
        for (n,) in await db.execute(
            select(ComposerScenario.name).where(
                ComposerScenario.owner_id == owner_id))
    }
    if desired_name not in names:
        return desired_name, False
    n = 2
    while True:
        suffix = f" ({n})"
        cand = desired_name[: 64 - len(suffix)] + suffix
        if cand not in names:
            return cand, True
        n += 1


async def copy_scenario(
    db: AsyncSession,
    scenario_id: str,
    *,
    new_owner: str,
    new_owner_id: int,
    new_name: str | None = None,
    activity_kind: str | None = None,
    activity_detail: dict | None = None,
    origin_id: str | None = None,
    origin_owner_name: str | None = None,
) -> Scenario:
    """深拷贝场景 + 数据集(替代 V1 公共库"复制到我的")。

    新 id = 原 id + ``-copy-<6hex>``;属主 = 调用者;visibility 恒为
    private(复制来的公共场景也要先归自己再自行发布)。
    ``new_name``(2026-09-23 批次 F2):另存为/分发自定义副本名;缺省
    保留 ``(副本)`` 后缀行为(向后兼容)。重名判定不在本函数内 ——
    调用方先走 :func:`resolve_name_conflict`(软校验,见其注释)。

    ``activity_kind``/``activity_detail``(F1 分发复用):事件落账的
    kind/detail 覆盖 —— 缺省 ``scenario.save_as``;分发传
    ``scenario.handoff_received`` + 发送方信息,写入点保持唯一。
    """
    import copy as _copy
    from uuid import uuid4 as _uuid4

    src = await _get_row(db, scenario_id)
    suffix = _uuid4().hex[:6]
    new_sid = f"{scenario_id}-copy-{suffix}"[:128]

    payload = _copy.deepcopy(src.payload or {})
    copied_name = new_name or ""
    definition = payload.get("definition")
    if isinstance(definition, dict):
        definition["scenarioId"] = new_sid
        meta = definition.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["scenarioId"] = new_sid
            meta["name"] = new_name or f"{meta.get('name') or src.scenario_id} (副本)"
            meta["owner"] = new_owner
            copied_name = meta["name"]
    draft = ScenarioDraft.model_validate(payload)
    from datetime import datetime as _dt, timezone as _tz
    await create(
        db, draft, owner=new_owner, owner_id=new_owner_id,
        forked_from_id=origin_id or scenario_id,
        forked_from_owner_name=origin_owner_name
        or (src.owner_name or ""),
        forked_from_at=_dt.now(_tz.utc).replace(tzinfo=None),
    )

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
    # F3 事件落账(业务提交后):副本的创建事件归新属主的时间线。
    await activity.record(
        db,
        actor_id=new_owner_id,
        kind=activity_kind or activity.KIND_SAVE_AS,
        resource_type="scenario",
        resource_id=new_sid,
        detail={
            "name": copied_name,
            "sourceScenarioId": scenario_id,
            **(activity_detail or {}),
        },
    )
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


async def _bump_verified_to_effective(db, row: ComposerScenario) -> None:
    """已验证修订 → 生效修订(版本模型 4.1;调用方已兜异常)。

    只在 resolve 报告「全部用到的接口结构一致」时推进——有接口
    结构变化(changed_endpoints 非空)时保持原值,让用户经适配中心
    处理(推进会掩盖结构不匹配,执行时报 ENDPOINT_NOT_IN_RELEASE)。
    """
    from . import plate_client
    payload = row.payload or {}
    definition = definition_from_payload(payload)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    resolvable: dict[str, str] = {}
    endpoints: dict[str, list[str]] = {}
    for st in (definition.get("steps") or []):
        if isinstance(st, dict) and st.get("endpoint"):
            eid = str(st["endpoint"])
            system = eid.split(".")[0]
            ref = meta_plate.get(system)
            if ref_category(ref) == PIN and system not in resolvable:  # b2-3:钉定收集仅 PIN(integration 不改写落库)
                resolvable[system] = ref
            endpoints.setdefault(system, []).append(eid)
    resolvable = {s: r for s, r in resolvable.items() if endpoints.get(s)}
    if not resolvable:
        return
    resolved = await plate_client.resolve(
        resolvable, {s: endpoints[s] for s in resolvable})
    changed = False
    for system, info in resolved.items():
        # 有结构变化的接口 → 不推进(须先适配;推进会让新接口在
        # 执行时报 ENDPOINT_NOT_IN_RELEASE)
        if info.get("changed_endpoints"):
            continue
        eff = info.get("effective")
        if eff and eff != meta_plate.get(system):
            meta_plate[system] = eff
            changed = True
    if changed:
        row.payload = {**payload, "definition": definition}
        await db.commit()



# M4/Q18（M2 §3）：平台元数据出定义 —— 这些键只在数据库行的列上，
# 保存时从 definition.meta 剥掉，避免 M2 forbid（extra_forbidden）拒收。
_PLATFORM_META_KEYS = frozenset({"scenarioId", "updateTime", "owner"})


def _strip_platform_meta(def_meta: dict) -> dict:
    """定义存储面过滤：meta 只留 M2 字段（含 plate）。"""
    return {k: v for k, v in (def_meta or {}).items()
            if k not in _PLATFORM_META_KEYS}


# Release 6.2：接口步骤的 call 只存场景自有字段（service/user/
# path_params/追加 headers）。protocol/method/path/timeout 是 binding
# 派生字段，执行由 plate /convert 按 meta.plate 投影提供 —— 存储出现
# 即被重投影拒收（binding_field_in_storage，口径同 reproject 的
# _STORAGE_FORBIDDEN）。前端旧草稿仍可能携带，保存侧统一剥离。
# 前提：该步骤所属系统已在 meta.plate 声明（钉修订或 working ——
# 投影才有来源）；未声明的存储字段即执行面（/convert 原样透传），
# 剥了就没有可执行形态，故保留（过渡期旧形态）。无 endpoint 锚点的
# 手写原始调用不受影响（Release 4.5 原样使用）。
_BINDING_DERIVED_FIELDS = ("protocol", "method", "path", "timeout")


def strip_binding_fields(definition: dict) -> dict:
    """存储面过滤：已声明系统的锚点步骤 call 去 binding 派生字段。"""
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    if not meta_plate:
        return definition
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return definition
    out_steps: list | None = None
    for i, step in enumerate(steps):
        if (isinstance(step, dict) and step.get("endpoint")
                and str(step["endpoint"]).split(".")[0] in meta_plate
                and isinstance(step.get("call"), dict)
                and any(k in step["call"] for k in _BINDING_DERIVED_FIELDS)):
            if out_steps is None:
                out_steps = list(steps)
            out_steps[i] = {
                **step,
                "call": {k: v for k, v in step["call"].items()
                         if k not in _BINDING_DERIVED_FIELDS},
            }
    if out_steps is None:
        return definition
    return {**definition, "steps": out_steps}


def strip_binding_fields_payload(payload: dict) -> dict:
    """payload 容器层的同款过滤（adaptation 提交/回滚/副本写库共用）。"""
    definition = payload.get("definition")
    if not isinstance(definition, dict):
        return payload
    new_def = strip_binding_fields(definition)
    if new_def is definition:
        return payload
    return {**payload, "definition": new_def}


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
    # M4/Q18：owner 也出定义 —— 展示值从行(owner_name)组装。
    meta_dict.setdefault("owner", row.owner_name or "")
    return ScenarioMeta.model_validate(meta_dict)


def definition_from_payload(payload: dict | None) -> dict:
    """容器解包:``payload {definition, orchestration}`` → definition。

    全后端唯一的容器形状知识。run_dispatcher 的 steps 投影 / users
    读取 / 组装均复用本函数,容器形状再变时只改这里。
    """
    defn = (payload or {}).get("definition")
    return defn if isinstance(defn, dict) else {}


def steps_from_payload(payload: dict | None) -> list[dict]:
    """Steps live inside the container's definition now (plate-shaped dicts).

    v2.1 F-2a 终态:call 形态直接返回(前端已支持 stepCall 双读);
    (api 形态已退役;前端 stepCall() 单读 call。)
    后端不再做归一化——前端是双读的,存储什么就返回什么。
    """
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
            # 检索面与前端占位符对齐(含系统);system 是 JSONB 数组镜像列
            *(getattr(row, "system", None) or []),
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
