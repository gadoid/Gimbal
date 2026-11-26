"""CRUD store for composer_run_schemes(workbench spec §5;UPC M2 §16.1)。

行形状:关系的做关系(scenario 归属/name 唯一/default 标记/组合绑定
显式列在列),文档的做文档(方案体一个 JSON payload,camelCase wire
形状)。store 层错误约定:ValueError("name_conflict") /
ValueError("default_protected") / KeyError(scheme_id) —— 路由层负责
翻译成 409/405/404。

UPC M2(§16.1 组合绑定读写点收敛):

* **绑定唯一持久化事实 = ``account_combo_id`` 显式列**(§20.2);API
  同名 DTO 字段(``accountComboId``)在此双向映射 —— ``normalized()``
  把 payload 里的该键**恒剥**(含历史残留与恶意直写),持久化 payload
  不再保存绑定,无第二事实源。
* ``project_id`` 从父场景派生(冗余校验键,复合 FK 钉死一致),创建
  时随场景写入,此后不存在独立修改归属的路径。
* **复制恒剥绑定**(§5.1/v4 §4.3:副本 = 新建),但**继承阻塞**
  (§20.3:复制不得通过普通空绑定清除 blocked —— 源 blocked 则副本
  blocked,同原因)。
* ``revision`` 乐观锁:修复命令与绑定变更 expected_revision 原子校验,
  方案内容保存同事务递增(§20.3「绑定与 revision 同事务」)。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario

DEFAULT_SCHEME_NAME = "默认方案"

# M2 RunOptions 形状(执行参数收进 options 包裹;stepTo/nRuns→
# step_to/n_runs 蛇形,logSub→subscribe,plugins 删除 Q15)
_EMPTY_OPTIONS: dict = {
    "step_from": None, "step_to": None, "n_runs": 1, "parallel": 1,
    "subscribe": None,
}
_EMPTY_PAYLOAD: dict = {
    "dataSetSelection": [], "injectionEntryIds": [], "serviceBindings": {},
    "options": dict(_EMPTY_OPTIONS),
}

_UNSET: Any = object()


def normalized(payload: dict | None) -> dict:
    """合并缺省键,保证 wire 形状完整(存量/旧端点数据可能缺新键)。

    旧形状兼容:只有 dataSetIds(整库语义)而无行级选择时,合成
    dataSetSelection(spec v3 §4 权威键;rowIndexes 空 = 整库)。
    执行参数:M10 RunOptions 形状(options 包裹),迁移已完成
    (scripts/migrate_scheme_run_options.py --apply),不再收旧平铺键。

    UPC M2(§16.1):``accountComboId`` 恒剥 —— 绑定走显式列,
    payload 不保存(入参残留/历史行/直写一律剥离,无第二事实源)。
    """
    p = dict(payload or {})
    p.pop("accountComboId", None)
    out = dict(_EMPTY_PAYLOAD)
    out.update({k: v for k, v in p.items() if k in out})
    # 旧形状兼容:只有 dataSetIds(整库语义)而无行级选择时,合成
    # dataSetSelection(spec v3 §4 权威键;rowIndexes 空 = 整库)。
    # 合成必须放 update 之后 —— 路由层模型 dump 恒带显式空
    # dataSetSelection([]),先合成会被它盖回,经 /run-schemes 创建的
    # 旧形状方案将静默丢数据集(审计追修)。
    if not p.get("dataSetSelection") and p.get("dataSetIds"):
        out["dataSetSelection"] = [
            {"datasetId": d, "rowIndexes": []} for d in p["dataSetIds"]
        ]
    # authz M2a S6:绑定 = 服务键 → {alias};存量形态的 url/authAlias
    # 读面剥离(0047 已清洗落库值,此处兜底防旧行漏网)
    from ..schemas.scenario_composer import scrub_retired_bindings
    out["serviceBindings"] = scrub_retired_bindings(out["serviceBindings"])
    # authz M2a S2.1:方案环境(环境链第二位)—— 设置了才落键,未设置
    # 的方案 wire 形状不变(不补 null 键)
    if p.get("environmentId") is not None:
        out["environmentId"] = p["environmentId"]
    return out


def _sanitize_default(payload: dict) -> dict:
    p = normalized(payload)
    p["dataSetSelection"] = []
    p["injectionEntryIds"] = []
    return p


async def _next_scheme_id(db: AsyncSession) -> str:
    """分配最小未用的 rs-NNN(仿 data_set_store._next_dataset_id)。"""
    rows = (await db.execute(select(ComposerRunScheme.scheme_id))).scalars().all()
    used = {r for r in rows if r.startswith("rs-")}
    n = 1
    while f"rs-{n:03d}" in used:
        n += 1
    return f"rs-{n:03d}"


async def _scenario_project_id(db: AsyncSession, scenario_id: str) -> int:
    """方案归属从父场景派生(§20.2 冗余校验键的唯一写入来源)。"""
    pid = (await db.execute(
        select(ComposerScenario.project_id).where(
            ComposerScenario.scenario_id == scenario_id)
    )).scalar_one_or_none()
    if pid is None:
        raise KeyError(scenario_id)
    return pid


def _to_wire(row: ComposerRunScheme, *,
             repair_reason: str | None = None) -> dict:
    # 迁移完成:不再展开平铺键;前端读 options 形状(M10/RunOptions)。
    # UPC M2:accountComboId ↔ 显式列双向映射;repairStatus/revision
    # 随行;repairReason 由路由层经 §20.3 授权投影后注入(此处缺省
    # None = ready;内部精确原因不直接序列化)。
    return {
        "schemeId": row.scheme_id,
        "name": row.name,
        "isDefault": bool(row.is_default),
        "accountComboId": row.account_combo_id,
        "repairStatus": row.repair_status,
        "repairReason": (repair_reason if row.repair_status == "blocked"
                         else None),
        "revision": row.revision,
        **normalized(row.payload),
    }


async def ensure_default_scheme(db: AsyncSession, scenario_id: str) -> None:
    hit = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.is_default.is_(True),
        )
    )).scalar_one_or_none()
    if hit is None:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=scenario_id,
            project_id=await _scenario_project_id(db, scenario_id),
            name=DEFAULT_SCHEME_NAME,
            is_default=True,
            payload=dict(_EMPTY_PAYLOAD),
        ))
        await db.commit()


async def list_schemes(
    db: AsyncSession, scenario_id: str, *,
    repair_reasons: dict[str, str | None] | None = None,
) -> list[dict]:
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == scenario_id)
        .order_by(ComposerRunScheme.is_default.desc(), ComposerRunScheme.name)
    )).scalars().all()
    reasons = repair_reasons or {}
    return [_to_wire(r, repair_reason=reasons.get(r.scheme_id))
            for r in rows]


async def create_scheme(
    db: AsyncSession, scenario_id: str, *,
    name: str, payload: dict, is_default: bool = False,
    account_combo_id: int | None = None,
) -> dict:
    if not is_default and name == DEFAULT_SCHEME_NAME:
        raise ValueError("name_conflict")
    exists = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.name == name,
        )
    )).scalar_one_or_none()
    if exists is not None:
        raise ValueError("name_conflict")
    row = ComposerRunScheme(
        scheme_id=await _next_scheme_id(db),
        scenario_id=scenario_id,
        project_id=await _scenario_project_id(db, scenario_id),
        name=name, is_default=is_default,
        # 原生新建 = 已确认组合语义(绑定或空绑定都 ready;§20.3
        # 状态机 [*] → Ready),修复状态不接受调用方指定
        repair_status="ready",
        account_combo_id=account_combo_id,
        payload=_sanitize_default(payload) if is_default else normalized(payload),
    )
    db.add(row)
    await db.commit()
    return _to_wire(row)


async def get_row(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> ComposerRunScheme:
    row = (await db.execute(
        select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.scheme_id == scheme_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise KeyError(scheme_id)
    return row


async def resolve_unit_scheme(
    db: AsyncSession, scenario_id: str, *, scheme_id: str | None,
    row_spec: Any = None,
) -> tuple[dict | None, str | None]:
    """编排**单元**的方案选择(评审四轮 P2-5:预检与执行器共用单源,
    与 ``graph_dispatch.resolve_graph_units`` 同语义):

    * 显式 ``scheme_id`` → 该方案(找不到 = 引用失效,error 非空);
    * 仅选行(row_spec,无 schemeId)→ 默认方案;
    * 都没有 → **裸基线**(None, None)—— 执行器不选方案,预检不得
      误报 blocked(修前预检走 resolve_for_run 回落默认/首个)。

    返回 ``(scheme, error)``,scheme 为 list_schemes 同形态 DTO
    (含 ``repairStatus``);error 非空时执行器将 GraphDispatchError。
    """
    if scheme_id is None and row_spec is None:
        return None, None
    schemes = await list_schemes(db, scenario_id)
    if scheme_id is not None:
        scheme = next(
            (s for s in schemes if s.get("schemeId") == scheme_id), None)
        if scheme is None:
            return None, f"scheme not found: {scheme_id}"
        return scheme, None
    return next((s for s in schemes if s.get("isDefault")), None), None


async def resolve_for_run(
    db: AsyncSession, scenario_id: str, scheme_id: str | None,
) -> ComposerRunScheme | None:
    """执行时的方案选择(唯一实现,集成链与入站调用共用)。

    指定 → **必须属于本场景**(跨场景/不存在视为未指定,回落默认 ——
    与集成链既有口径一致);未指定 → 默认方案;无默认 → 首个;场景
    无方案 → None(空配方执行)。

    入站调用的「指定方案跨场景」在路由层先拦成 422(`scheme_not_owned`
    —— 调用方显式给了错的 id,静默回退默认会让它跑错配方);本函数
    的回落语义服务于「模板上存了一个已删除的方案 id」这类存量场景。
    """
    scheme = None
    if scheme_id:
        scheme = (await db.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id,
            ComposerRunScheme.scenario_id == scenario_id,
        ))).scalar()
    if scheme is None:
        row = (await db.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.is_default == True,  # noqa: E712
        ))).scalar()
        scheme = row or (await db.execute(
            select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == scenario_id)
        )).scalars().first()
    return scheme


async def update_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str, *,
    name: str | None, payload: dict | None,
    account_combo_id: Any = _UNSET,
    expected_revision: int | None = None,
) -> dict:
    """方案保存(整稿 PUT)。``account_combo_id``:_UNSET = 调用方未传
    (保留存量);None = 解绑;int = 换绑 —— 绑定与 revision 同事务
    (§16.1)。blocked 方案的绑定改动由 ck_scheme_combo_repair 在库层
    拒绝(普通 PATCH 不得清除阻塞,§20.3)—— 修复命令经
    ``services.scheme_repair`` 专用路径,不经此处。

    ``expected_revision``(评审二轮 P2-14,可选 CAS):传入时在恒取的
    行锁内校验,不匹配抛 ``ValueError("revision_conflict")``;未传
    维持「最后写入」语义(兼容存量客户端),但评审六轮 P2-3 起写入
    基于**行锁内重读**的当前值 —— 不再是过期快照上的盲覆盖
    (「200 但未生效」与 revision 重号一并消除)。"""
    row = await get_row(db, scenario_id, scheme_id)
    # 评审六轮 P2-3:保存**恒取方案行锁** —— 修前仅 CAS 腿刷新
    # FOR UPDATE,无 CAS 保存工作在过期快照上:并发 rebind 提交后,
    # 解绑 PUT 的 ORM 对象仍持旧值,「赋同值」不产生 UPDATE diff →
    # 200 但绑定未生效,且 revision 从旧值 +1 与并发写共享同号
    # (破坏后续 CAS token 的唯一性)。行锁位于调用方 combo 校验
    # (require_combo_bindable 已锁组合行)之后,combo→scheme 全序不变;
    # 锁内重读后 revision 严格递增。
    await db.refresh(row, with_for_update=True)
    if expected_revision is not None and expected_revision != row.revision:
        raise ValueError("revision_conflict")
    if row.is_default:
        if payload is not None:
            row.payload = _sanitize_default(payload)
    else:
        if name is not None:
            if name == DEFAULT_SCHEME_NAME:
                raise ValueError("name_conflict")
            dup = (await db.execute(
                select(ComposerRunScheme.id).where(
                    ComposerRunScheme.scenario_id == scenario_id,
                    ComposerRunScheme.name == name,
                    ComposerRunScheme.scheme_id != scheme_id,
                )
            )).scalar_one_or_none()
            if dup is not None:
                raise ValueError("name_conflict")
            row.name = name
        if payload is not None:
            row.payload = normalized(payload)
    if account_combo_id is not _UNSET:
        if (row.repair_status == "blocked"
                and account_combo_id is not None):
            # §20.3:普通保存不得解除/改绑 blocked —— 修复命令是仅有入口
            # (库层 ck_scheme_combo_repair 兜底;此处先行给人话错误)
            raise ValueError("scheme_repair_required")
        row.account_combo_id = account_combo_id
    row.revision += 1
    await db.commit()
    return _to_wire(row)


async def delete_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> None:
    row = await get_row(db, scenario_id, scheme_id)
    if row.is_default:
        raise ValueError("default_protected")
    await db.delete(row)
    await db.commit()


async def copy_schemes(
    db: AsyncSession, src_scenario_id: str, dst_scenario_id: str,
) -> None:
    """逐行复制(重新分配 scheme_id)。不 commit — 调用方
    (scenario_store.copy_scenario)把它并进自己的事务。

    dst 侧先整组清空再复制:copy_scenario 先走 create(),其钩子已为
    dst 物化默认方案,直接补插源侧 default 行会撞「每场景恰一默认」
    的部分唯一索引(及 (scenario, name) 唯一索引);整组替换保证
    dst ≡ src(含默认方案的 payload 定制)。

    UPC M2(§5.1/§20.3):**绑定恒剥**(副本 = 新建,不携带组合引用);
    **阻塞继承** —— 源 blocked 则副本 blocked(同原因),普通复制
    不得通过空绑定清除 blocked;源 ready(含空绑定)副本 ready。
    新 scheme_uid 由库默认生成(不可复用身份,删除重建是新身份)。
    """
    await db.execute(sa_delete(ComposerRunScheme).where(
        ComposerRunScheme.scenario_id == dst_scenario_id
    ))
    dst_pid = await _scenario_project_id(db, dst_scenario_id)
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == src_scenario_id)
    )).scalars().all()
    for r in rows:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=dst_scenario_id, name=r.name,
            project_id=dst_pid,
            is_default=r.is_default,
            # 绑定恒剥;阻塞继承(ready 保持 ready)
            repair_status=r.repair_status,
            repair_reason=r.repair_reason,
            payload=dict(r.payload or {}),
        ))


async def scheme_counts(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(
        select(ComposerRunScheme.scenario_id, func.count())
        .group_by(ComposerRunScheme.scenario_id)
    )).all()
    return {sid: n for sid, n in rows}
