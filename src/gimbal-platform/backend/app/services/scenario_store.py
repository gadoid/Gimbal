"""DB-backed CRUD for the V3 Scenario Composer Scenario rows.

Uses SQLAlchemy async sessions against the ``composer_scenarios`` table.

All public methods take an ``AsyncSession`` (or use the default from
``get_db`` via the routers); they never hold module-level state, so
concurrent requests see consistent reads/writes.
"""
from __future__ import annotations
from .run_semantics import INTEGRATION, PIN, UNDECLARED, WORKING, invalid_reason, record_category, ref_category

from datetime import datetime, timedelta

from loguru import logger

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
    ParamSlot,
    Scenario,
    ScenarioDraft,
    ScenarioListItem,
    ScenarioMeta,
)
from . import endpoint_ref_index
from . import run_injection
from . import run_params
from . import scheme_store


# ─── write side ───────────────────────────────────────────────────
# plate ConfigView 的 users 附带视图专有键
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


async def gates_for_mutation(
    definition: dict, *, prev_payload: "dict | None" = None,
) -> None:
    """定义写面共用闸单源:

    * 版本声明闸 ``enforce_meta_plate``(prev = 存量行 plate —— 声明
      未变跳过引用校验的防抖语义,适配直存同样走本闸);
    * 明文凭证拒收(§3.5:旧行 users 空 + 本次带明文
      → 422)—— 适配直存同样受闸(op 改写理论上不产明文,但该闸
      是写面不变量,不该靠「理论」)。

    消费面 = store.update / 适配直存(adaptation_service.submit)。
    Raises ValueError(两闸原码)。"""
    _old_cfg = (((prev_payload or {}).get("definition") or {})
                .get("config") or {})
    _new_users = ((definition or {}).get("config") or {}).get("users")
    _old_users = _old_cfg.get("users")
    if (not (isinstance(_old_users, dict) and _old_users)
            and isinstance(_new_users, dict) and _new_users):
        raise ValueError(
            "plaintext_users_rejected: 场景不再接受明文凭证快照"
            "(definition.config.users)——引用请改为身份条目名"
            "(${auth.*} 模板 / call.user),手配凭证请走认证管理或"
            "配置页落池后引用")
    await enforce_meta_plate(
        definition,
        prev_meta_plate=(((prev_payload or {}).get("definition") or {})
                         .get("meta") or {}).get("plate"))


async def post_save_chain(db: AsyncSession, row: "ComposerScenario") -> None:
    """保存后链单源:已验证修订 → 生效修订 best-effort(M1 版本模型
    4.1;plate 不可达保持原值,绝不阻塞保存主链)。store.update 与
    适配直存同走(升档覆盖适配保存路径)。"""
    try:
        await _bump_verified_to_effective(db, row)
    except Exception as e:  # noqa: BLE001 — best-effort 升档,不阻塞保存主链
        logger.warning(
            "scenario_store: verified→effective 升档失败,保持原值(id={}):{}",
            row.id, e)


async def enforce_meta_plate(definition: dict,
                             prev_meta_plate: dict | None = None) -> None:
    """版本声明闸(create/update/导入/适配提交共用)。

    * 锚定系统(endpoint 首段)必须声明 —— 未声明
      = 绕开 plate 按陈旧存储 binding 执行的过渡形态(C-2),唯一
      写入口由本闸拦下;
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
       }
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


def _integrity_conflict_code(e: IntegrityError) -> str:
    """IntegrityError → 冲突码(冲突码精确化)。

    调用身份草稿与场景行同事务后,create/update 提交点的完整性冲突
    不止场景 PK 一个来源 —— 条目名唯一(service_identities)按
    约束名分派回 auth_draft 家族码(路由侧既有 409 映射,「同名直接
    引用」语义一致),其余保守回落 scenario_id_exists(旧行为;FK
    竞态等罕见面宁 409 不 500)。
    """
    orig = getattr(e, "orig", None)
    name = str(getattr(orig, "constraint_name", "")
               or getattr(getattr(orig, "diag", None),
                          "constraint_name", "") or "")
    if "service_identities" in name or "alias_name" in name:
        return "auth_draft_alias_taken"
    return "scenario_id_exists"


def _integrity_message(code: str, scenario_id: str) -> str:
    if code == "scenario_id_exists":
        return f"scenario_id_exists: {scenario_id}"
    return (f"{code}: 并发冲突(他处刚登记同名条目)—— "
            "同名即直接引用,或改条目名后重试")


async def _resolve_default_zone(
    db: AsyncSession, owner_id: int | None,
) -> int | None:
    """UPC M2 归属写入点收敛:缺省目标 = **owner 的默认私有空间**(§4
    每用户恰一个 —— 契约规则,非猜测)。显式 project_id 调用方不经此。
    无默认空间(系统管道无属主/处置中)→ None,由调用方决定语义。"""
    from .project_space import get_default_private_project

    proj = await get_default_private_project(db, owner_id)
    return proj.id if proj else None


async def create_in_transaction(
    db: AsyncSession,
    draft: ScenarioDraft,
    *,
    owner: str = "",
    owner_id: int | None = None,
    project_id: int | None = None,
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

    UPC M2:``project_id`` 缺省 = owner 的默认私有空间(project_id
    NOT NULL 后「空 = 私有区」退役);显式归属由路由层先行经
    ``project_access.resolve_content_target`` 校验。
    """
    if project_id is None:
        if owner_id is None:
            # §8/AC-04:无 owner 也无显式目标 —— 契约违例,不隐式猜测归属
            raise ValueError(
                "scenario_target_required: 场景创建须明确归属"
                "(owner 的默认私有空间或显式 project_id)")
        resolved = await _resolve_default_zone(db, owner_id)
        if resolved is None:
            raise ValueError(
                "default_space_missing: 用户没有默认私有空间"
                "(用户初始化未完成或处置中)")
        project_id = resolved
    def_meta = draft.definition.get("meta") or {}
    scenario_id = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    await enforce_meta_plate(draft.definition)      # 唯一写入口
    # 凭证治理 §3.5:新场景不接受明文凭证快照 ——
    # config.users 非空 → ValueError("plaintext_users_rejected",调用方
    # 映 422)。唯一写入口 = 全部新建路径统一生效;副本/导入链在
    # 上游已清空(§4.4-2 拍板:副本 = 新建),恒过此闸,直写 API 是唯一
    # 暴露面。选 422 而非 strip:静默丢弃用户输入是假空态反模式。
    _plain_users = ((draft.definition.get("config") or {}).get("users"))
    if isinstance(_plain_users, dict) and _plain_users:
        raise ValueError(
            "plaintext_users_rejected: 场景不再接受明文凭证快照"
            "(definition.config.users)——引用请改为身份条目名"
            "(${auth.*} 模板 / call.user),手配凭证请走认证管理或"
            "配置页落池后引用")
    # 调用身份草稿:随保存**同事务**建 username-ref 条目(不建账户、
    # 不碰密码 —— 凭证走 POST /auths)。校验失败在场景行 add 之前整单
    # ValueError,调用方映射后回滚。owner_id 缺省(系统管道)不收草稿;
    # 属主闸在 update 路径(user_id vs row.owner)。
    if draft.auth_drafts:
        if owner_id is None:
            raise ValueError(
                "auth_draft_owner_required: 调用身份草稿须保存者即场景属主")
        from .auth_drafts import materialize
        await materialize(db, draft.auth_drafts, owner_id=owner_id,
                          project_id=project_id)
    # 入站参数契约写时校验(设计 §2.1):槽位 ⊆ vars 标量键
    run_params.validate_param_slots(
        draft.definition,
        [s.model_dump(by_alias=True) for s in draft.param_slots])
    # 断言注册表写侧形状闸(裁定「隔离区+后端闸」):
    # entries 逐元素 dict;前端隔离区 unrecognized 原样放行。与
    # param_slots 同层同形(同层平台侧字段,create/PUT 双跑)。
    run_injection.validate_registry_shape(draft.assertion_registry)
    server_owned = ScenarioMeta.model_validate({
        **def_meta,
        "scenarioId": scenario_id,
        "owner": owner or def_meta.get("owner", ""),
    })
    #（M2 §3）存储的定义即纯 M2 实例 —— meta.scenarioId /
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
        # 入站参数契约随容器透传(设计 §4:契约随场景
        # payload 走,复制/转让/fork 自动携带)
        param_slots=draft.param_slots,
        params_strict=draft.params_strict,
        # M4:编辑器状态(ui.fieldStates)随容器透传
        ui=draft.ui,
    ).model_dump(by_alias=True, mode="json")
    row = ComposerScenario(
        scenario_id=server_owned.scenario_id,
        owner_name=server_owned.owner,
        owner_id=owner_id,
        project_id=project_id,
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
    project_id: int | None = None,
    forked_from_id: str | None = None,
    forked_from_owner_name: str | None = None,
    forked_from_at: "datetime | None" = None,
) -> Scenario:
    """Insert a new scenario.  Raises ValueError on duplicate scenarioId.

    Server-side override: ``owner`` is always taken from the router's
    ``owner`` parameter (the authenticated user's display_name), so a
    caller cannot spoof the owner field by sending a different value in
    the request body.  ``owner_id`` 同理由路由层传入(int user.id,
    审计/维护者快照);归属权威是 ``project_id``(UPC M2:真实容器)。
    区归属:缺省 = owner 的默认私有空间;显式归属由路由层经
    ``project_access.resolve_content_target`` 三 kind 统一校验。

    提交包装器:常规创建/copy/fork/迁移脚本等既有调用方行为
    零变化;导入流水线走 :func:`create_in_transaction` 自管事务
    (别名/carry/场景单事务,场景导入 v2.3 方案 §6)。
    """
    scenario_id = (draft.definition.get("scenarioId")
                   or (draft.definition.get("meta") or {}).get("scenarioId")
                   or "")
    try:
        row = await create_in_transaction(
            db, draft, owner=owner, owner_id=owner_id,
            project_id=project_id,
            forked_from_id=forked_from_id,
            forked_from_owner_name=forked_from_owner_name,
            forked_from_at=forked_from_at)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        code = _integrity_conflict_code(e)
        raise ValueError(_integrity_message(code, scenario_id)) from e
    await db.refresh(row)
    # 场景创建即物化默认方案(工作台 spec §4.3/§5;
    # GET /run-schemes 侧的 ensure_default 是自愈兜底)。
    await scheme_store.ensure_default_scheme(db, row.scenario_id)
    out = await to_read_shape(db, row)
    # 凭证治理行为规则④:保存结果列出本次新建凭证(revive 由路由层
    # best-effort 触发,与 /auths create 同款)。
    if draft.auth_drafts:
        out.new_auths = [d.name for d in draft.auth_drafts]
    return out


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
    # 旧名快照(提交后判 rename/edit;在 payload 覆盖前取)
    old_name = (((row.payload or {}).get("definition") or {})
                .get("meta") or {}).get("name")
    # 写面闸单源:版本声明(prev 防抖)+ 明文凭证
    # 拒收 —— 与适配直存(adaptation_service.submit)同走本函数。
    await gates_for_mutation(
        draft.definition, prev_payload=row.payload)
    # 调用身份草稿:§3.8 拍板 —— 维护者/admin 改他人场景只能手填名字,
    # 不带草稿(属主单判与 _require_owner 表 B 同源,私有区写权本就归
    # 属主;公共/项目区维护者可写但不代属主登记全局条目)。
    if draft.auth_drafts:
        if user_id is None or user_id != row.owner_id:
            raise ValueError(
                "auth_draft_owner_required: 调用身份草稿仅场景属主可随保存"
                "创建(维护者改他人场景请手填引用名)")
        from .auth_drafts import materialize
        await materialize(db, draft.auth_drafts, owner_id=user_id,
                          project_id=row.project_id)
    # 入站参数契约缺键保留(设计挂账:前端契约编辑面
    # 不接线):**逐键**判定 —— 请求未携带该键而存量行有值则保留存量
    # (防前端整包保存/适配操作把 API 侧维护的契约抹掉);显式携带
    # (含空槽清空)走整包替换。model_fields_set 精确区分「缺键」与
    # 「显式 []/false」。逐键而非「任一键在即整包」:只带 paramsStrict
    # 不带 paramSlots 的部分携带 PUT 不得清空槽位。
    # **必须在下方写时校验之前**:保留后的契约要对着新定义重验
    # (防「缺键 PUT + 删变量/适配 renameVar」留下悬空槽位)。
    _old = row.payload or {}
    _keep: dict = {}
    if ("param_slots" not in draft.model_fields_set
            and _old.get("paramSlots")):
        _keep["param_slots"] = [ParamSlot.model_validate(s)
                                for s in _old["paramSlots"]]
    if ("params_strict" not in draft.model_fields_set
            and _old.get("paramsStrict")):
        _keep["params_strict"] = bool(_old["paramsStrict"])
    if _keep:
        draft = draft.model_copy(update=_keep)
    # 入站参数契约写时校验(设计 §2.1):PUT 重验 —— 防删变量后槽位悬空
    run_params.validate_param_slots(
        draft.definition,
        [s.model_dump(by_alias=True) for s in draft.param_slots])
    # 断言注册表写侧形状闸(I-01):PUT 同闸重验(整包替换语义,键归编排器)
    run_injection.validate_registry_shape(draft.assertion_registry)
    def_meta = draft.definition.get("meta") or {}
    req_sid = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    if req_sid != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    # module 空值不写 default / system 空值不写 ["default"]:
    # "default" 伪系统与 meta.system 每系统须有 plate 声明冲突,
    # ScenarioMeta 按 M2 空值语义('' / [])接受,存量空值
    # 原样入校验、原样存储。
    effective_owner = new_owner or def_meta.get("owner") or row.owner_name
    server_owned = ScenarioMeta.model_validate({
        **def_meta, "scenarioId": scenario_id, "owner": effective_owner,
    })
    # 同 create —— 平台元数据出定义，定义即纯 M2 实例。
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
        # 入站参数契约随容器透传:PUT 整包替换语义
        # 与 assertion_registry 同款;旧客户端缺键回落缺省([]/false)
        param_slots=draft.param_slots,
        params_strict=draft.params_strict,
        # M4:编辑器状态(ui.fieldStates)随容器透传
        ui=draft.ui,
    ).model_dump(by_alias=True, mode="json")
    await endpoint_ref_index.sync_scenario(db, scenario_id, row.payload)
    try:
        await db.commit()
    except IntegrityError as e:
        # 手配落池并发唯一冲突(update 同族:冲突码精确化)—— 场景行
        # PK 不变无撞号面,冲突源只有 drafts 家族;
        # 裸 IntegrityError 对外 = 500。
        await db.rollback()
        raise ValueError(_integrity_message(
            _integrity_conflict_code(e), scenario_id)) from e
    await db.refresh(row)
    # 版本模型 4.1(M1):普通保存后已验证修订 best-effort 升级(后链单源)
    await post_save_chain(db, row)
    # 事件落账(业务提交后):name 变化 → rename,否则 edit;
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
    out = await to_read_shape(db, row, user_id=user_id)
    if draft.auth_drafts:
        out.new_auths = [d.name for d in draft.auth_drafts]
    return out


async def delete(db: AsyncSession, scenario_id: str,
                 *, commit: bool = True) -> None:
    """Delete a scenario and cascade its datasets.

    Raises KeyError on miss.  Uses a single transaction so a failure
    mid-cascade rolls everything back.

    ``commit=False``(评审二轮 P1-3):调用方自持事务(用户处置 purge
    等)时只写不提交 —— 删除与业务写入统一到调用方的最终事务,中途
    失败整体回滚,不再留下「资源已删、用户仍在」的半程状态。
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
    # user_stars 随场景 CASCADE。PG 上 DB 级 CASCADE 已处理,
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
    if commit:
        await db.commit()



# ── authz:明文凭证不随公开/拷贝扩散(方案 §9.1/§10.6)────
# 原件不动(作者自己照常用内置凭证与敏感列,下架无损);凡交到**非属主**
# 手里的形态一律脱敏:读(详情/draft/数据集)、跨属主拷贝、执行(属主
# 规则 run_prepare.built_in_users + 非属主数据集剥敏感列)。
# 列名敏感启发与 scenario_import._SENSITIVE_RE 同源(密改一处两处同步:
# 导入模块 import 本常量,避免两张正则漂移)
import re as _re

SENSITIVE_COLUMN_RE = _re.compile(
    r"(password|secret|token|key)", _re.IGNORECASE)


def strip_builtin_credentials(payload: dict) -> dict:
    """删除 ``definition.config.users``(内置凭证基座),原地返回。

    调用面:跨属主拷贝(copy_scenario 单点)、导入、非属主读形态
    (:func:`payload_for_viewer`)、非属主执行的快照/任务参数。原件
    永不经过这里(发布不剥离 —— 订阅执行由属主规则兜底)。
    """
    definition = payload.get("definition")
    if isinstance(definition, dict):
        cfg = definition.get("config")
        if isinstance(cfg, dict) and cfg.get("users"):
            cfg["users"] = {}
    return payload


def strip_sensitive_columns(rows: list) -> list:
    """数据集行敏感列剥离(10.6):键名命中 SENSITIVE_COLUMN_RE 的列
    删除,非敏感列保留;返回新列表(不改入参)。"""
    return [
        {k: v for k, v in (row or {}).items()
         if not SENSITIVE_COLUMN_RE.search(str(k))}
        for row in (rows or [])
    ]


# r6 二.1:行的敏感部分 HMAC 短键 —— 读面随脱敏行下发(``__rowKey``),
# 写面按它把存量敏感值并回**正确的行**。按行号并会在成员删/插/重排
# 后串号(删掉 alice 行 → bob 拿到 alice 的密码),比丢列更隐蔽。
ROW_KEY_FIELD = "__rowKey"


def sensitive_row_key(row: dict) -> str | None:
    """行敏感部分的 HMAC-SHA256 短键(r6 二.1)。HMAC + 应用密钥
    (FERNET_KEY,与凭证加密同保护类):成员拿到的键不能离线爆破
    敏感值。无敏感列的行无键(无可并回的内容)。"""
    import hashlib
    import hmac as _hmac
    import json as _json

    part = {str(k): v for k, v in (row or {}).items()
            if SENSITIVE_COLUMN_RE.search(str(k))}
    if not part:
        return None
    from ..core.config import settings

    return _hmac.new(
        (settings.FERNET_KEY or "gimbal-rowkey").encode("utf-8"),
        _json.dumps(part, sort_keys=True, ensure_ascii=False,
                    default=str).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


def attach_row_keys(stored: list, redacted: list) -> list:
    """读面:脱敏行按下标附 ``__rowKey``(stored/redacted 同源数组,
    位置安全);无敏感列的行原样。"""
    out = []
    for i, r in enumerate(redacted):
        key = sensitive_row_key(stored[i]) if i < len(stored) else None
        if key:
            r = dict(r or {})
            r[ROW_KEY_FIELD] = key
        out.append(r)
    return out


def strip_row_keys(rows: list) -> list:
    """剥离 ``__rowKey``(落库/校验前 —— 它不是调色板列,也不持久化)。"""
    return [{k: v for k, v in (r or {}).items() if k != ROW_KEY_FIELD}
            for r in rows or []]


def merge_sensitive_columns(stored: list, submitted: list) -> list:
    """非属主保存数据集(r6 二.1 修订):按 ``__rowKey`` 并回存量敏感
    值 —— 删行(键缺席)→ 值随行删;插行(无键/未知键)→ 新行不并回
    任何值;重排 → 键随行走,不串号。同键多行按序消费(同键即同敏感
    值);成员提交里的敏感键值(看不到真值)不生效,存量权威。
    ``__rowKey`` 已剥,不落库。"""
    from collections import defaultdict, deque

    pool: "dict[str, deque]" = defaultdict(deque)
    for s in stored or []:
        key = sensitive_row_key(s)
        if key:
            pool[key].append(
                {k: v for k, v in (s or {}).items()
                 if SENSITIVE_COLUMN_RE.search(str(k))})
    out = []
    for sub in submitted or []:
        row = dict(sub or {})
        key = row.pop(ROW_KEY_FIELD, None)
        src = pool.get(key) if key else None
        if src:
            row.update(src.popleft())
        out.append(row)
    return out


def is_foreign_viewer(viewer_id: int | None, owner_id: int | None) -> bool:
    """读/执行主体不是场景属主 → 需要脱敏。``viewer_id`` 为 None =
    内部/属主上下文(不判)。"""
    return viewer_id is not None and viewer_id != owner_id


def payload_for_viewer(payload: dict | None, *, viewer_id: int | None,
                       owner_id: int | None) -> dict:
    """场景 payload 的读者形态:非属主拿到剥掉 config.users 的深拷贝,
    属主原样(浅拷贝)。"""
    import copy as _copy

    if not is_foreign_viewer(viewer_id, owner_id):
        return dict(payload or {})
    return strip_builtin_credentials(_copy.deepcopy(payload or {}))


async def resolve_name_conflict(
    db: AsyncSession, owner_id: int, desired_name: str
) -> tuple[str, bool]:
    """该 owner 名下已有同名场景 → 返回 (计数后缀名, True);否则原样。

    分发(静默后缀)与另存为(前端确认后缀)共用 —— 重名判定
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
    # S1.3 发布新语义:确定性副本 id(公共副本 = <原 id>-public)、
    # 落库项目、剥离口径三值 —— ``users``(缺省,拍板 #5 2026-11-20:
    # 副本 = 新建,users 恒剥、同属主也剥;数据集敏感列同属主保留,
    # 属主自己的数据)/ ``always``(发布复制与项目晋升:公共副本连
    # 数据集敏感列一起剥,S1.3 原语义)/ ``cross_owner``(历史值,兼容
    # 显式传参;跨属主恒双剥不依赖该值)。勿把缺省回退成 cross_owner。
    new_sid: str | None = None,
    project_id: int | None = None,
    strip: str = "users",
) -> Scenario:
    """深拷贝场景 + 数据集(替代 V1 公共库"复制到我的")。

    新 id = 原 id + ``-copy-<6hex>``;属主 = 调用者;缺省落私有区
    (复制来的公共场景也要先归自己再自行发布;发布复制传 project_id)。
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
    new_sid = (new_sid if new_sid is not None
               else f"{scenario_id}-copy-{suffix}")[:128]

    payload = _copy.deepcopy(src.payload or {})
    # authz W6:跨属主拷贝剥离内置凭证与数据集敏感列(单点:复制到我的 /
    # 分享拷贝 / 引用转副本 / suite fork / 变更适配副本全走这里;E1 ——
    # 订阅不复制,无此路径)。拍板 #5(2026-11-20,凭证治理 §4.4-2):
    # **同属主副本同样清空** —— 副本 = 新建,验收口径「新场景 users
    # 恒空」全局一致;原件(含存量明文基座)仍在属主手里,丢的只是
    # 副本上的陈旧明文兜底。上游还有 §3.5 的 create_in_transaction
    # 422 闸(明文直写),这里是副本路径的清空位。
    cross_owner = src.owner_id != new_owner_id
    if cross_owner or strip in ("users", "always"):
        strip_builtin_credentials(payload)
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
        project_id=project_id,
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
            rows=(strip_sensitive_columns(ds.rows or [])
                  # 数据集敏感列:跨属主(属主自己的数据不外带)或
                  # 发布/晋升(公共副本不落敏感列,S1.3)剥;同属主
                  # 普通副本(拍板 #5 缺省口径)保留。
                  if (cross_owner or strip == "always")
                  else _copy.deepcopy(ds.rows or [])),
            # 变量锁本地放开清单按名存储 — 深拷贝必须带走,否则分叉
            # 场景的解锁语义静默丢失
            var_unlocks=list(ds.var_unlocks or []),
        ))
    # 方案随场景深拷贝 — 迁出 payload 后不再随 deepcopy 自动带走,
    # 显式复制(新 scheme_id,仿上方 data_sets 循环)。
    await scheme_store.copy_schemes(db, scenario_id, new_sid)
    await db.commit()
    # 事件落账(业务提交后):副本的创建事件归新属主的时间线。
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


async def project_member_scenario_ids(db: AsyncSession, user) -> set[str]:
    """我所在项目的项目区场景 id 集(r3二.1:项目区场景的数据集 =
    项目共享业务数据,成员可列同事的数据集;预览剥敏感列由列表层
    处理)。公共项目无成员行,天然不在其中。"""
    from ..models.project import ProjectMember

    pids = (await db.execute(select(ProjectMember.project_id).where(
        ProjectMember.user_id == user.id))).scalars().all()
    if not pids:
        return set()
    return set(
        (await db.execute(select(ComposerScenario.scenario_id).where(
            ComposerScenario.project_id.in_(pids)))).scalars().all())


# ─── helpers ──────────────────────────────────────────────────────
# ── 发布新语义(S1.3):发布 = 复制到公共项目 ────────────────────────

def public_copy_id(scenario_id: str) -> str:
    """公共副本的确定性 id:<原 id>-public(≤128 截断;scenarioId 模式
    只允许小写字母数字连字符,不能用 @)。重发布/下架按它定位,
    不需要查 forked_from 索引。"""
    return f"{scenario_id}-public"[:128]


async def find_public_copy(
    db: AsyncSession, scenario_id: str
) -> "ComposerScenario | None":
    """原件的公共副本(forked_from_id = 原 id ∧ 公共项目);无 → None。"""
    from .zone import public_project_id

    pid = await public_project_id(db)
    if pid is None:
        return None
    return (await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.forked_from_id == scenario_id,
            ComposerScenario.project_id == pid))).scalar_one_or_none()


async def publish_copy(
    db: AsyncSession, scenario_id: str,
) -> "tuple[Scenario, bool]":
    """发布 = 复制到公共项目(S1.3,s1-detail §五):

    * 副本 id = :func:`public_copy_id`(确定性);**恒剥离**内置凭证与
      数据集敏感列(strip="always",同属主也剥 —— 公共副本不落明文,
      原件仍在属主手里);``forked_from_id`` = 原件 id;owner_id 不动
      (= 维护者);原件不动(private、可继续执行/维护)。
    * 重发布 = 删旧副本再复制(全级联:数据集/方案/suite 引用清洗),
      同 id 覆盖内容 —— 订阅者经指纹闸在下次执行暂停待确认。
    Returns ``(公共副本读形态, 是否新建)``。
    """
    from .zone import public_project_id

    src = await _get_row(db, scenario_id)
    pid = await public_project_id(db)
    if pid is None:
        raise ValueError("public_project_missing: 公共项目未种子")
    copy_sid = public_copy_id(scenario_id)
    existing = await get_row(db, copy_sid)
    created = existing is None
    if existing is not None:
        await delete(db, copy_sid)
    meta = ((src.payload or {}).get("definition") or {}).get("meta") or {}
    out = await copy_scenario(
        db, scenario_id,
        new_owner=src.owner_name or "", new_owner_id=src.owner_id,
        new_name=str(meta.get("name") or scenario_id),  # 公共列表显示原名
        new_sid=copy_sid, project_id=pid,
        strip="always", activity_kind="scenario.published",
        activity_detail={"via": "publish_copy",
                         "sourceScenarioId": scenario_id})
    return out, created


async def unpublish_public_copy(db: AsyncSession, copy_sid: str) -> None:
    """下架 = 删除公共副本(:func:`delete` 全级联)。KeyError on miss."""
    await delete(db, copy_sid)


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
    if config and config.get("users") and is_foreign_viewer(
            user_id, row.owner_id):
        config = {**config, "users": {}}   # authz W6:非属主读不带内置凭证
    # M6-2:收藏读时投影改 UserStar(marks_store 退役);单行详情一次
    # 预取,列表路径由调用方走 to_list_item_shape(集合注入)。
    from .user_stars import star_ids as _star_ids

    starred = (
        row.scenario_id in await _star_ids(db, user_id)
        if user_id is not None
        else False
    )
    # C3 收口(2026-11-22):visibility 单源 derive_visibility(普通项目
    # = 'private',与公共页过滤/S1.9 对齐;旧宽口径见 to_list_item_shape)
    from .zone import derive_visibility

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
        visibility=await derive_visibility(db, row.project_id),
        projectId=row.project_id,
    )


def to_list_item_shape(
    row: ComposerScenario,
    *,
    starred_ids: "set[str] | None" = None,
    data_set_count: int = 0,
    scheme_count: int = 0,
    visibility: str,
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
        # C3 收口(2026-11-22)+ 复核收口:visibility 必传(调用方按
        # derive_visibility 单源计算)—— None 兜底回落旧宽口径
        # (「project_id 非空 = public」)是 shim perpetuates drift,
        # 现存两处调用方均已显式传参,兜底删除。
        visibility=visibility,
        projectId=row.project_id,
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
        except Exception as e:  # noqa: BLE001 — 畸形行不 500,渲染面重建
            logger.warning(
                "scenario_store: orchestration 模型校验失败,按缺失处理"
                "(payload 形状漂移?):{}", e)
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
