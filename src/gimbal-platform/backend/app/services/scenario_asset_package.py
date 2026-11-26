"""§14.2 场景资产包:导出 / 原子恢复(v2.10 M2 最小闭环,AC-45/46)。

开发库重建的资产恢复通道(**资产恢复,不是旧数据库状态恢复**;
§14.1:不建设全量业务数据转换程序):

* **导出**(:func:`export_bundle`):场景定义(剥离明文秘密 ——
  ``config.users`` 不外带,§14.2「不导出明文秘密」)+ 数据集 + 方案
  (含默认项与选择内容)+ 组合依赖(名称/条目/源标识;不保存秘密)。
* **恢复**(:func:`restore_bundle`):**每场景一个数据库事务**(只
  flush 的写入函数;入口提交,普通新建的默认方案自愈不在此另行补建,
  §14.2):
  - 幂等键 = (目标项目, 导出包标识, 源场景标识),数据库唯一约束是
    并发权威;同键同摘要 = 重放,返回已提交映射;同键不同摘要 → 409。
  - 默认候选**先验证再写入**:携带数据集/注入选择的默认候选导致**零
    提交**(422;含选择的候选不可通过清空字段升为默认,§14.2)。
  - 组合依赖按确定性映射恢复:合法条目 → 目标项目建组合并绑定
    (ready;同一源组合被多方案引用按 ref 去重复用一份);显式
    ``comboId`` 映射指向存在但**跨区**的组合 →
    blocked ``combo_cross_zone``(诊断记录留目标标识);映射目标不
    存在或 ``skipCombos`` → blocked ``combo_missing``;条目无法合法
    恢复(未登记别名/异基础服务)→ blocked ``combo_dependency_
    invalid``。悬空引用一律不落库;不猜测替代组合、不隐式用默认组合。
  - 源侧 blocked 方案(随包 ``repairStatus``)无显式映射时**原样重建
    blocked** —— 修复状态是资产事实:禁止执行的方案往返后不得静默
    变为可执行(§20.3/§14.2「不把待修复计为可执行」);携带显式
    映射则按映射显式修复。
  - 恢复产出的方案与修复状态、行级审计(:mod:`scheme_repair`
    ``scheme_repair_events``)同事务写入(AC-46:无半成品)。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account_combo import AccountCombo
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario
from ..models.scenario_asset_import import ScenarioAssetImport
from ..models.scheme_repair import (
    REASON_COMBO_CROSS_ZONE, REASON_COMBO_DEPENDENCY_INVALID,
    REASON_COMBO_MISSING,
)
from . import scheme_repair, scheme_store
from .scenario_store import (
    create_in_transaction, is_foreign_viewer, strip_builtin_credentials,
    strip_sensitive_columns,
)
from .service_aliases import BindingAliasInvalid, validate_binding_aliases
from .zone import ProjectCreateDenied

BUNDLE_FORMAT = "gimbal-upc-asset"
BUNDLE_VERSION = 1


class AssetBundleError(Exception):
    """资产包域错误(路由层映射 HTTP)。"""

    def __init__(self, status: int, code: str, message: str,
                 detail: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail or {}


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def request_digest(bundle: dict) -> str:
    """§14.2 恢复请求摘要:按规范化输入计算(同键同摘要 = 重放)。"""
    payload = {
        "format": bundle.get("format"),
        "version": bundle.get("version"),
        "packageId": bundle.get("packageId"),
        "source": bundle.get("source"),
        "scenario": bundle.get("scenario"),
        "datasets": bundle.get("datasets"),
        "schemes": bundle.get("schemes"),
        "comboDependencies": bundle.get("comboDependencies"),
        "defaultSchemeId": bundle.get("defaultSchemeId"),
        "skipCombos": bool(bundle.get("skipCombos")),
        "comboIdMappings": bundle.get("comboIdMappings"),
    }
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _shape_error(why: str) -> AssetBundleError:
    return AssetBundleError(422, "asset_bundle_shape_invalid",
                            f"资产包形状不合规:{why}")


def _validate_shape(bundle: dict) -> None:
    """顶层与嵌套形状的边界校验(评审 P2-12):形状错误统一 422,不再
    让 ``.get`` 打在非对象上产生 500。"""
    if not isinstance(bundle, dict):
        raise _shape_error("顶层须为对象")
    if (bundle.get("format") != BUNDLE_FORMAT
            or bundle.get("version") != BUNDLE_VERSION):
        raise AssetBundleError(
            422, "asset_bundle_format_invalid",
            f"资产包须为 {BUNDLE_FORMAT} v{BUNDLE_VERSION}")
    source = bundle.get("source")
    if not isinstance(source, dict) or not isinstance(
            source.get("scenarioId"), str) or not source.get("scenarioId"):
        raise AssetBundleError(
            422, "asset_bundle_source_missing",
            "资产包缺源场景标识(source.scenarioId)")
    schemes = bundle.get("schemes")
    if not isinstance(schemes, list) or not schemes:
        raise AssetBundleError(
            422, "asset_bundle_schemes_missing", "资产包缺方案清单")
    seen_sids: set[str] = set()
    for s in schemes:
        if not isinstance(s, dict):
            raise _shape_error("schemes[*] 须为对象")
        sid = s.get("schemeId")
        if not isinstance(sid, str) or not sid:
            raise _shape_error("schemes[*].schemeId 须为非空字符串")
        if sid in seen_sids:
            # 评审四轮 P2-3:重复 schemeId 会让默认候选插出两行
            # is_default=True,撞部分唯一索引变未捕获 IntegrityError
            raise _shape_error(f"schemes[*].schemeId 重复: {sid!r}")
        seen_sids.add(sid)
        # 评审五轮 P2-3:payload 判型**不许 or {} 吞 falsy** —— [] / 0
        # 会在规范化/落库面炸出 TypeError(非 None 即须为 dict)
        _payload_raw = s.get("payload")
        if _payload_raw is not None and not isinstance(_payload_raw, dict):
            raise _shape_error(
                f"schemes[{sid!r}].payload 须为对象(收到 "
                f"{_payload_raw!r})")
        _payload = _payload_raw if isinstance(_payload_raw, dict) else {}
        selection = _payload.get("dataSetSelection")
        if selection is not None:
            if not isinstance(selection, list) or not all(
                    isinstance(sel, dict) for sel in selection):
                raise _shape_error(
                    f"schemes[{sid!r}].payload.dataSetSelection 须为"
                    "对象数组(评审 P2-8/四轮 P2-3:非数组会在行级重指"
                    "迭代时 TypeError → 500)")
            else:
                # 评审五轮 P2-3:条目内 datasetId 须为非空字符串 ——
                # 列表键在重指映射(`in ds_map`)时不可哈希 → TypeError;
                # rowIndexes 须为整数数组(bool 不计)
                for sel in selection:
                    dsid = sel.get("datasetId")
                    if not isinstance(dsid, str) or not dsid:
                        raise _shape_error(
                            f"schemes[{sid!r}].payload.dataSetSelection[*]."
                            "datasetId 须为非空字符串(收到 "
                            f"{dsid!r})")
                    ris = sel.get("rowIndexes")
                    if ris is not None and (not isinstance(ris, list)
                                            or not all(
                        isinstance(x, int) and not isinstance(x, bool)
                        for x in ris)):
                        raise _shape_error(
                            f"schemes[{sid!r}].payload.dataSetSelection[*]."
                            "rowIndexes 须为整数数组")
        entries = _payload.get("injectionEntryIds")
        if entries is not None and (
                not isinstance(entries, list) or not all(
                    isinstance(x, str) and x for x in entries)):
            raise _shape_error(
                f"schemes[{sid!r}].payload.injectionEntryIds 须为非空"
                "字符串数组")
        # 评审五轮 P2-3:旧式 dataSetIds 须为非空字符串数组 —— 标量在
        # 规范化迭代(`for d in p["dataSetIds"]`)时 TypeError → 500
        legacy_ids = _payload.get("dataSetIds")
        if legacy_ids is not None and (not isinstance(legacy_ids, list)
                                       or not all(
            isinstance(x, str) and x for x in legacy_ids)):
            raise _shape_error(
                f"schemes[{sid!r}].payload.dataSetIds 须为非空字符串数组"
                f"(收到 {legacy_ids!r})")
    deps = bundle.get("comboDependencies")
    if deps is not None:
        if not isinstance(deps, dict) or not all(
                isinstance(k, str) and isinstance(v, dict)
                for k, v in deps.items()):
            raise _shape_error("comboDependencies 须为 {schemeId: 对象}")
        for k, v in deps.items():
            entries = v.get("entries")
            if entries is not None and not isinstance(entries, list):
                raise _shape_error(
                    f"comboDependencies[{k!r}].entries 须为数组"
                    "(评审 P2-8:非数组会在条目迭代时 TypeError → 500)")
            ref = v.get("ref")
            if ref is not None and not isinstance(ref, str):
                raise _shape_error(
                    f"comboDependencies[{k!r}].ref 须为字符串"
                    "(评审 P2-8:非字符串会在 ref 映射时不可哈希 → 500)")
    mappings = bundle.get("comboIdMappings")
    if mappings is not None:
        if not isinstance(mappings, dict) or not all(
                isinstance(k, str) and isinstance(v, int)
                and not isinstance(v, bool) and v >= 1
                for k, v in mappings.items()):
            raise _shape_error(
                "comboIdMappings 须为 {schemeId: 正整数组合 id}")
    datasets = bundle.get("datasets")
    if datasets is not None:
        if not isinstance(datasets, list) or not all(
                isinstance(d, dict) for d in datasets):
            raise _shape_error("datasets 须为对象数组")
    if not isinstance(bundle.get("defaultSchemeId"), str) \
            or not bundle.get("defaultSchemeId"):
        raise AssetBundleError(
            422, "asset_bundle_default_missing",
            "资产包缺默认方案标识(defaultSchemeId)"
            ";未入选原默认时须显式指定合格候选(§14.2)")


# ── 导出 ─────────────────────────────────────────────────────────

async def export_bundle(db: AsyncSession, row: ComposerScenario, *,
                        viewer) -> dict:
    """导出场景资产包:定义(剥明文)+ 数据集 + 方案 + 组合依赖。

    凭证快照(``definition.config.users``)不外带(§14.2「不导出明文
    秘密」);引用这些别名的场景恢复后由身份解析/预检显形为待修复项
    —— 历史定义内容保留,秘密不迁移。
    评审二轮 P1-1:调用者身份进导出面 —— 非属主(含普通项目成员导出
    同事场景)的数据集行经**脱敏单源** ``strip_sensitive_columns`` 剥
    敏感列,谓词与数据集单读同一(``is_foreign_viewer``);属主原样。
    评审二轮 P2-9:方案修复状态只随**授权投影**后的原因(``projected_
    reason``/``reasons_for_schemes`` 单源)—— 内部精确原因(combo_
    missing)与受限诊断引用(sourceComboRef)不随包,维持 AC-44「不
    可见目标与不存在目标响应不可区分」;恢复侧据此重建 blocked。"""
    payload = dict(row.payload or {})
    strip_builtin_credentials(payload)

    viewer_id = getattr(viewer, "id", viewer)
    redact_rows = is_foreign_viewer(viewer_id, row.owner_id)

    datasets = (await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.scenario_id == row.scenario_id)
        .order_by(ComposerDataSet.id))).scalars().all()

    scheme_rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == row.scenario_id)
        .order_by(ComposerRunScheme.id))).scalars().all()

    combo_dependencies: dict[str, dict] = {}
    combo_cache: dict[int, AccountCombo] = {}
    schemes_out: list[dict] = []
    default_scheme_id = None
    # 修复状态走授权投影单源(ready → 投影 None,不带字段)
    projected = await scheme_repair.reasons_for_schemes(
        db, viewer, list(scheme_rows))
    for s in scheme_rows:
        if s.is_default:
            default_scheme_id = s.scheme_id
        dep: dict | None = None
        if s.account_combo_id is not None:
            combo = combo_cache.get(s.account_combo_id)
            if combo is None:
                combo = await db.get(AccountCombo, s.account_combo_id)
                if combo is not None:
                    combo_cache[combo.id] = combo
            if combo is not None:
                dep = {
                    "ref": f"combo:{combo.id}",
                    "name": combo.name,
                    "entries": (combo.payload or {}).get("entries") or [],
                }
                combo_dependencies[s.scheme_id] = dep
        out = {
            "schemeId": s.scheme_id, "name": s.name,
            "isDefault": bool(s.is_default),
            "payload": scheme_store.normalized(s.payload),
        }
        reason = projected.get(s.scheme_id)
        if reason is not None:
            out["repairStatus"] = "blocked"
            out["repairReason"] = reason
        schemes_out.append(out)

    return {
        "format": BUNDLE_FORMAT, "version": BUNDLE_VERSION,
        "packageId": uuid4().hex,
        "source": {"scenarioId": row.scenario_id,
                   "projectId": row.project_id},
        "scenario": payload,
        "datasets": [
            {"datasetId": d.dataset_id, "name": d.name,
             "description": d.description,
             "rows": (strip_sensitive_columns(d.rows or [])
                      if redact_rows else list(d.rows or [])),
             "varUnlocks": d.var_unlocks or []}
            for d in datasets],
        "schemes": schemes_out,
        "comboDependencies": combo_dependencies,
        "defaultSchemeId": default_scheme_id,
    }


# ── 恢复 ─────────────────────────────────────────────────────────

def _minted(existing: set[str], wanted: str) -> str:
    """确定性 ID 铸造:源 ID 可保留则保留,否则后缀去冲突(§14.2
    「能安全保留原 ID 时可保留」)。"""
    if wanted not in existing:
        existing.add(wanted)
        return wanted
    base = wanted[:112]
    i = 2
    while True:
        cand = f"{base}-imp{i}"
        if cand not in existing:
            existing.add(cand)
            return cand
        i += 1


async def _validate_combo_entries(db: AsyncSession, entries: list) -> bool:
    """组合条目能否在目标库合法恢复(别名已登记 ∧ 同基础服务)。"""
    bindings: dict[str, dict] = {}
    seen: set[str] = set()
    for e in entries or []:
        if not isinstance(e, dict):
            return False
        service, alias = e.get("service"), e.get("alias")
        if not (isinstance(service, str) and service
                and isinstance(alias, str) and alias):
            return False
        if service in seen:
            return False
        seen.add(service)
        bindings[service] = {"alias": alias}
    if not bindings:
        return True
    try:
        await validate_binding_aliases(db, bindings)
    except BindingAliasInvalid:
        return False
    return True


def _replay_report(hit: ScenarioAssetImport) -> dict:
    """同键同摘要的重放报告(先提交者的已提交映射,§14.2)。"""
    return json.loads(json.dumps(hit.report or {})) | {
        "replayed": True,
        "scenarioId": hit.restored_scenario_id,
    }


async def _ledger_hit(db: AsyncSession, *, project_id: int,
                      package_id: str, source_sid: str
                      ) -> "ScenarioAssetImport | None":
    return (await db.execute(
        select(ScenarioAssetImport).where(
            ScenarioAssetImport.project_id == project_id,
            ScenarioAssetImport.package_id == package_id,
            ScenarioAssetImport.source_scenario_id == source_sid)
    )).scalar_one_or_none()


async def restore_bundle(
    db: AsyncSession, *, project_id: int, bundle: dict, user,
) -> dict:
    """原子恢复一个场景(只 flush,调用方提交;AC-46)。

    返回恢复报告(§14.2:区分已恢复绑定 / 显式解绑待修复 / 未导入;
    不把待修复计为可执行)。幂等冲突抛
    :class:`AssetBundleError`(409/重放由调用方返回已有映射)。

    **并发同键**(§14.2:数据库唯一约束防止并发重复创建):败者在
    唯一约束上落马 → 本事务回滚后重查台账 —— 同键同摘要重放收敛,
    同键不同摘要 409;无台账命中的意外唯一冲突原样上抛(调用方新
    事务重试,恢复契约:失败回滚、重试可继续)。"""
    _validate_shape(bundle)
    digest = request_digest(bundle)
    source_sid = str(bundle["source"]["scenarioId"])
    # 评审 P2-11:缺省 packageId 不再掷骰子 —— 由源场景 × 请求摘要派生
    # 稳定幂等键,同请求重试收敛(同键同摘要 = 重放),不再逐次造新场景
    package_id = str(bundle.get("packageId")
                     or f"auto-{source_sid}-{digest[:16]}")

    try:
        return await _restore_bundle_once(
            db, project_id=project_id, bundle=bundle, user=user,
            digest=digest, package_id=package_id, source_sid=source_sid)
    except IntegrityError:
        await db.rollback()
        hit = await _ledger_hit(
            db, project_id=project_id, package_id=package_id,
            source_sid=source_sid)
        if hit is None:
            raise      # 非同键竞争的意外冲突:不吞错,新事务重试可继续
        if hit.request_digest != digest:
            raise AssetBundleError(
                409, "asset_bundle_conflict",
                "同键不同摘要:该源场景在此包标识下已有不同的恢复记录,"
                "请处置后重试(§14.2)",
                detail={"restoredScenarioId": hit.restored_scenario_id})
        return _replay_report(hit)


async def _restore_bundle_once(
    db: AsyncSession, *, project_id: int, bundle: dict, user,
    digest: str, package_id: str, source_sid: str,
) -> dict:
    """单事务恢复主体(:func:`restore_bundle` 的写入分支)。"""
    hit = await _ledger_hit(
        db, project_id=project_id, package_id=package_id,
        source_sid=source_sid)
    if hit is not None:
        if hit.request_digest != digest:
            raise AssetBundleError(
                409, "asset_bundle_conflict",
                "同键不同摘要:该源场景在此包标识下已有不同的恢复记录,"
                "请处置后重试(§14.2)",
                detail={"restoredScenarioId": hit.restored_scenario_id})
        # 同键同摘要 = 重放,返回已提交映射
        return _replay_report(hit)

    # ── 先规范化(评审 P2-10:旧式 dataSetIds 形状在此收敛为显式选择
    #    —— 默认候选校验不再可被「校验后携带选择」的旧形状绕过),后端
    #    全程使用规范化结果 ─────────────────────────────────────────
    schemes = [
        dict(s, payload=scheme_store.normalized(s.get("payload") or {}))
        for s in bundle["schemes"]
    ]
    # ── 默认候选先验证(含选择 → 零提交,§14.2;评审 P1-6:包内默认
    #    标记与 defaultSchemeId 冲突 → 422,defaultSid 是唯一权威)────
    default_sid = str(bundle["defaultSchemeId"])
    default_scheme = next((s for s in schemes
                           if s.get("schemeId") == default_sid), None)
    if default_scheme is None:
        raise AssetBundleError(
            422, "asset_bundle_default_missing",
            f"defaultSchemeId {default_sid!r} 不在方案清单中")
    for s in schemes:
        if s.get("isDefault") and s.get("schemeId") != default_sid:
            raise AssetBundleError(
                422, "asset_bundle_default_conflict",
                f"方案 {s['schemeId']!r} 自带默认标记,与 defaultSchemeId"
                f" {default_sid!r} 冲突 —— 默认标识是唯一权威,请修正"
                "包内标记(§14.2)")
    _dp = default_scheme.get("payload") or {}
    if _dp.get("dataSetSelection") or _dp.get("injectionEntryIds"):
        raise AssetBundleError(
            422, "asset_bundle_default_invalid",
            "默认方案候选携带数据集选择/注入条目 —— 含选择的候选不可"
            "通过清空字段升为默认(§14.2);请重选合格默认候选")

    # ── 目标身份铸造 ──────────────────────────────────────────────
    taken_sids = set((await db.execute(
        select(ComposerScenario.scenario_id))).scalars().all())
    target_sid = _minted(taken_sids, source_sid)

    skip_combos = bool(bundle.get("skipCombos"))
    combo_deps = bundle.get("comboDependencies") or {}
    combo_id_mappings = bundle.get("comboIdMappings") or {}

    taken_dsids = set((await db.execute(
        select(ComposerDataSet.dataset_id))).scalars().all())

    # ── 场景(显式目标 project_id;秘密已在导出剥离,§3.5 闸照常)──
    from ..schemas.scenario_composer import ScenarioDraft

    try:
        draft = ScenarioDraft.model_validate(bundle.get("scenario") or {})
    except ValidationError as e:
        raise AssetBundleError(
            422, "asset_bundle_scenario_invalid",
            f"场景定义不符合契约: {e}") from None
    draft.definition["scenarioId"] = target_sid
    if isinstance(draft.definition.get("meta"), dict):
        draft.definition["meta"]["scenarioId"] = target_sid
    try:
        await create_in_transaction(
            db, draft,
            owner=(getattr(user, "display_name", None)
                   or getattr(user, "username", "")),
            owner_id=user.id, project_id=project_id)
    except ValueError as e:
        raise AssetBundleError(422, "asset_bundle_scenario_invalid",
                                str(e)) from None

    # ── 数据集(确定性 ID 映射 + 选择重指)─────────────────────────
    ds_map: dict[str, str] = {}
    for d in bundle.get("datasets") or []:
        src_id = str(d.get("datasetId") or "")
        if not src_id:
            continue
        new_id = _minted(taken_dsids, src_id)
        ds_map[src_id] = new_id
        db.add(ComposerDataSet(
            dataset_id=new_id, scenario_id=target_sid,
            name=str(d.get("name") or ""), description=str(
                d.get("description") or ""),
            rows=d.get("rows") or [], var_unlocks=d.get("varUnlocks") or []))
    await db.flush()

    # ── 组合依赖恢复(确定性映射;悬空引用不落库)───────────────────
    existing_combos = (await db.execute(
        select(AccountCombo).where(
            AccountCombo.project_id == project_id))).scalars().all()
    taken_combo_names = {c.name for c in existing_combos}
    combo_map: dict[str, int | None] = {}     # 旧 schemeId → 目标组合 id
    combo_blocked: dict[str, str] = {}          # 旧 schemeId → 原因码
    blocked_diag: dict[str, dict] = {}
    ref_combo_map: dict[str, int] = {}        # 源组合 ref → 目标组合 id
    ref_fingerprint: dict[str, str] = {}      # 源组合 ref → 条目内容指纹
    # 源侧 blocked 方案(§20.3):无映射时原样重建 blocked,禁止静默
    # 变 ready(源侧本就无绑定;修复状态是资产事实,不是可丢的注记)。
    # reason 只随授权投影后的值(P2-9:内部精确原因与诊断引用不出包)
    source_blocked: dict[str, dict] = {}
    for s in schemes:
        if s.get("repairStatus") == "blocked":
            source_blocked[str(s.get("schemeId"))] = {
                "reason": s.get("repairReason")}

    async def _resolve_combo_for(old_scheme_id: str, dep: dict | None,
                                 ) -> None:
        # ① 显式映射优先(§14.2「确定性映射可在导入阶段完成」;对源侧
        #    blocked 方案同样生效 —— 调用方显式指认即显式修复,不是猜测)
        mapped = combo_id_mappings.get(old_scheme_id)
        if mapped is not None:
            combo = await db.get(AccountCombo, int(mapped))
            if combo is None or combo.project_id != project_id:
                reason = (REASON_COMBO_CROSS_ZONE if combo is not None
                          else REASON_COMBO_MISSING)
                combo_blocked[old_scheme_id] = reason
                blocked_diag[old_scheme_id] = {
                    "source_combo_ref": dep and dep.get("ref"),
                    "resolved_combo_id": combo.id if combo else None,
                    "resolved_project_id": (combo.project_id
                                             if combo else None)}
                return
            combo_map[old_scheme_id] = combo.id
            return
        if dep is None:
            if old_scheme_id in source_blocked:
                # 无绑定且无映射的源 blocked 方案 → 原样 blocked
                # (包内 reason 已是授权投影值;诊断引用不随包,统一
                # 留空 —— 目标侧诊断只记本次恢复可观察的事实)
                _src = source_blocked[old_scheme_id]
                reason = (_src.get("reason")
                          if _src.get("reason") in (
                              REASON_COMBO_MISSING,
                              REASON_COMBO_CROSS_ZONE,
                              REASON_COMBO_DEPENDENCY_INVALID)
                          else REASON_COMBO_DEPENDENCY_INVALID)
                combo_blocked[old_scheme_id] = reason
                blocked_diag[old_scheme_id] = {
                    "source_combo_ref": None,
                    "resolved_combo_id": None, "resolved_project_id": None}
                return
            combo_map[old_scheme_id] = None
            return
        if skip_combos:
            combo_blocked[old_scheme_id] = REASON_COMBO_MISSING
            blocked_diag[old_scheme_id] = {
                "source_combo_ref": dep.get("ref"), "resolved_combo_id":
                    None, "resolved_project_id": None}
            return
        # ② 定义恢复:条目合法 → 目标项目建组合(名冲突 → 确定性后缀);
        #    同一源组合(ref 相同)被多个方案引用时只建一份 —— 按 ref 去重
        #    映射复用,保住复用语义与 revision 溯源(§5/§20.2)
        ref = dep.get("ref")
        if ref is not None and ref in ref_combo_map:
            # 评审三轮 P2-9:同 ref 复用前比对规范化内容指纹 —— 两方案
            # 引用同一 ref 但 entries 不同时不得静默绑到第一个组合
            if _canonical(dep.get("entries") or []) != ref_fingerprint[ref]:
                raise AssetBundleError(
                    422, "asset_bundle_combo_conflict",
                    f"同一源组合 {ref!r} 在包内携带不同条目内容 —— "
                    "请修正包内 comboDependencies 或改用显式映射(§14.2)")
            combo_map[old_scheme_id] = ref_combo_map[ref]
            return
        if not await _validate_combo_entries(db, dep.get("entries") or []):
            combo_blocked[old_scheme_id] = "combo_dependency_invalid"
            blocked_diag[old_scheme_id] = {
                "source_combo_ref": dep.get("ref"), "resolved_combo_id":
                    None, "resolved_project_id": None}
            return
        name = str(dep.get("name") or "导入组合")
        base_name = name if name not in taken_combo_names else None
        if base_name is None:
            i = 2
            while f"{name}-导入{i}" in taken_combo_names:
                i += 1
            base_name = f"{name}-导入{i}"
        taken_combo_names.add(base_name)
        combo = AccountCombo(
            project_id=project_id, name=base_name,
            description="asset import",
            payload={"entries": dep.get("entries") or []},
            revision=1, updated_by_id=user.id)
        db.add(combo)
        await db.flush()
        if ref is not None:
            ref_combo_map[ref] = combo.id
            ref_fingerprint[ref] = _canonical(dep.get("entries") or [])
        combo_map[old_scheme_id] = combo.id

    for s in schemes:
        old_scheme_id = str(s.get("schemeId"))
        if old_scheme_id in combo_id_mappings:
            await _resolve_combo_for(old_scheme_id,
                                     combo_deps.get(old_scheme_id))
        elif old_scheme_id in source_blocked:
            # 源 blocked 优先于矛盾输入(包里同时带 dep):无绑定事实
            # 权威,dep 不采信 —— 不给「静默变可执行」留缝
            await _resolve_combo_for(old_scheme_id, None)
        elif old_scheme_id in combo_deps:
            await _resolve_combo_for(old_scheme_id,
                                     combo_deps.get(old_scheme_id))
        else:
            combo_map[old_scheme_id] = None

    # ── 方案行(只 flush;修复状态与审计同事务)─────────────────────
    used_scheme_ids = set((await db.execute(
        select(ComposerRunScheme.scheme_id))).scalars().all())
    taken_scheme_names: set[str] = set()
    restored_scheme_ids: list[str] = []
    restored_bindings = 0
    blocked_schemes: list[str] = []
    for s in schemes:
        old_scheme_id = str(s.get("schemeId"))
        payload = s["payload"]      # 已在入口规范化(P2-10)
        # 数据集引用重指到目标侧铸造后的 ID
        for sel in payload.get("dataSetSelection") or []:
            if isinstance(sel, dict) and sel.get("datasetId") in ds_map:
                sel["datasetId"] = ds_map[sel["datasetId"]]
        # 方案名目标场景内唯一(防同包撞名)
        name = str(s.get("name") or old_scheme_id)
        if name in taken_scheme_names:
            i = 2
            while f"{name}-{i}" in taken_scheme_names:
                i += 1
            name = f"{name}-{i}"
        taken_scheme_names.add(name)

        blocked_reason = combo_blocked.get(old_scheme_id)
        row = ComposerRunScheme(
            scheme_id=_minted(used_scheme_ids,
                              f"rs-{uuid4().hex[:10]}"),
            scenario_id=target_sid, project_id=project_id,
            name=name,
            # 评审 P1-6:defaultSchemeId 是唯一权威 —— 包内 isDefault
            # 标记不落库(冲突已在入口 422),报告与库内默认恒一致
            is_default=(old_scheme_id == default_sid),
            payload=payload,
            repair_status="ready", revision=1,
            account_combo_id=(None if blocked_reason
                              else combo_map.get(old_scheme_id)))
        db.add(row)
        await db.flush()
        restored_scheme_ids.append(row.scheme_id)
        if blocked_reason:
            blocked_schemes.append(row.scheme_id)
            await scheme_repair.mark_blocked(
                db, row, reason=blocked_reason,
                action="import.blocked",
                source_combo_ref=blocked_diag.get(old_scheme_id, {}).get(
                    "source_combo_ref"),
                resolved_combo_id=blocked_diag.get(
                    old_scheme_id, {}).get("resolved_combo_id"),
                resolved_project_id=blocked_diag.get(
                    old_scheme_id, {}).get("resolved_project_id"),
                request_id=package_id,
                actor_id=user.id,
                actor_name=(getattr(user, "display_name", None)
                            or getattr(user, "username", "")),
                note=f"asset import: {source_sid} → {target_sid}")
        elif combo_map.get(old_scheme_id) is not None:
            restored_bindings += 1

    # ── 幂等台账 + 报告(同事务;AC-46 台账缺失即未发生)─────────────
    default_new = next(
        (nid for old, nid in zip(
            [str(s.get("schemeId")) for s in schemes],
            restored_scheme_ids)
         if old == default_sid), None)
    report = {
        "scenarioId": target_sid,
        "sourceScenarioId": source_sid,
        "schemeIds": restored_scheme_ids,
        "defaultSchemeId": default_new,
        "datasets": len(ds_map),
        "restoredBindings": restored_bindings,
        "blockedSchemes": blocked_schemes,
        "unimportedSchemes": [],
        "skippedCombos": skip_combos,
    }
    db.add(ScenarioAssetImport(
        project_id=project_id, package_id=package_id,
        source_scenario_id=source_sid, request_digest=digest,
        restored_scenario_id=target_sid,
        restored_scheme_ids=restored_scheme_ids,
        default_scheme_id=default_new, report=report,
        created_by=user.id))
    await db.flush()
    return report


async def resolve_import_target(db: AsyncSession, user, project_id: int):
    """导入目标门(§8:明确目标 project_id —— 项目可写成员,含私有
    空间所有者;公共项目 422/不适用)。"""
    from .project_access import resolve_content_target

    try:
        return await resolve_content_target(db, user.id, project_id)
    except ProjectCreateDenied as e:
        raise AssetBundleError(e.status, e.code, e.message) from None
