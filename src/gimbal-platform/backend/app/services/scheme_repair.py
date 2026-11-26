"""§20.3 Scheme 组合依赖修复状态:统一装配闸、诊断投影与修复命令。

规范性契约要点(v2.10 §20.3,本模块是唯一实现):

* **持久化状态**在方案行(``repair_status``/``repair_reason``),不引入
  通用资产修复系统;blocked 表达「当前资产不具备已确认的组合语义」。
* **诊断授权投影**(:func:`projected_reason` / :func:`reasons_for_schemes`)
  —— 对外统一错误码 ``scheme_repair_required``;仅当调用者当前具有
  相关目标组合的 read 权限才返回精确原因(combo_cross_zone),否则一律
  投影为 ``combo_dependency_invalid``;combo_missing 通常仅在内部审计
  可见(目标不存在即无人可读)。投影不返回目标 ID/名称/项目/存在性,
  不可见目标与不存在目标响应不可区分(AC-44)。内部精确原因与源依赖
  标识持久化在受限诊断记录(SchemeRepairDiagnosis)+ 事件表,普通
  Scheme read 不自动授予跨区诊断读取权。
* **统一装配闸**(:func:`require_ready`)—— 先解析真实项目与方案并
  授权,再读持久化状态;blocked 返回稳定 409 ``scheme_repair_required``
  (携带投影原因与 revision),禁止先解析秘密或执行外部副作用。
  M2 接通正式 precheck;M3 完成 execute/query/schedule/probe 全入口。
* **修复命令**(:func:`rebind_combo` / :func:`confirm_no_combo`)——
  blocked → ready 的仅有入口:方案修改权限 + 绑定目标授权 + 
  expected_revision 原子校验,更新绑定/状态/原因/revision 与审计
  **同事务**;并发过期 revision 409。普通 PATCH/复制/空绑定不得解除
  阻塞(库层 ck_scheme_combo_repair + copy_schemes 继承共同钉死)。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account_combo import AccountCombo
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.scheme_repair import (
    REASON_COMBO_CROSS_ZONE, REASON_COMBO_DEPENDENCY_INVALID,
    REASON_COMBO_MISSING, SchemeRepairDiagnosis, SchemeRepairEvent,
)
from . import project_access

#: 对外统一错误码(§20.3;HTTP 409,授权后的 precheck 为结构化失败结果)
ERROR_CODE = "scheme_repair_required"

#: 通用投影(不可见/不存在/无权/不可解析时的唯一对外原因)
GENERIC_PROJECTION = REASON_COMBO_DEPENDENCY_INVALID


class SchemeRepairRequired(Exception):
    """统一装配闸:方案 blocked(§20.3)。执行/调度入口映射
    409 ``{code: scheme_repair_required, reason: <投影>, revision}``;
    授权后的 precheck 不抛出,走结构化失败结果。"""

    def __init__(self, *, reason: str, revision: int,
                 message: str = "方案组合依赖待修复,禁止装配与派发") -> None:
        super().__init__(message)
        self.code = ERROR_CODE
        self.reason = reason
        self.revision = revision
        self.message = message

    def detail(self) -> dict:
        return {"code": self.code, "message": self.message,
                "reason": self.reason, "revision": self.revision}


class RepairCommandError(Exception):
    """修复命令业务违例(路由层映射 4xx;``code`` 见 §20.3/§21)。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


# ── 诊断授权投影(§20.3;统一服务生成,覆盖 DTO/列表/详情/precheck)─────

async def _caller_can_read_combo(
    db: AsyncSession, user_id: int, diag: SchemeRepairDiagnosis | None,
) -> bool:
    """调用者当前是否具有相关目标组合的 read 权限(§20.3 投影条件)。
    诊断缺目标(不可解析/不存在)即无投影资格 —— 不猜 ID。"""
    if diag is None or diag.resolved_combo_id is None:
        return False
    combo = await db.get(AccountCombo, diag.resolved_combo_id)
    if combo is None:
        return False
    from ..models.project import Project

    proj = await db.get(Project, combo.project_id)
    if proj is None:
        return False
    return await project_access.can_view_project(db, user_id, proj)


async def projected_reason(
    db: AsyncSession, user: Any, scheme: ComposerRunScheme,
) -> str | None:
    """单方案的对外投影原因(ready → None;blocked → 精确原因仅当
    调用者可读相关目标组合,否则通用投影)。方案级读取与修复诊断
    共用本入口 —— 禁止直接序列化 ``scheme.repair_reason``。"""
    if scheme.repair_status != "blocked":
        return None
    reason = scheme.repair_reason or GENERIC_PROJECTION
    if reason != REASON_COMBO_CROSS_ZONE:
        # combo_missing(目标不存在)/combo_dependency_invalid(通用码)
        # 恒投影为通用码 —— 前者尤其不得经错误码泄露存在性差异
        return GENERIC_PROJECTION
    diag = await db.get(SchemeRepairDiagnosis, scheme.scheme_id)
    if await _caller_can_read_combo(db, user.id, diag):
        return REASON_COMBO_CROSS_ZONE
    return GENERIC_PROJECTION


async def reasons_for_schemes(
    db: AsyncSession, user: Any, schemes: list[ComposerRunScheme],
) -> dict[str, str | None]:
    """方案列表/详情 DTO 的投影原因批量入口(§9:Scheme DTO 返回
    repairStatus 与经授权投影的 repairReason)。"""
    out: dict[str, str | None] = {}
    blocked = [s for s in schemes if s.repair_status == "blocked"]
    diag_rows: dict[str, SchemeRepairDiagnosis] = {}
    if blocked:
        diag_rows = {
            d.scheme_id: d for d in (await db.execute(
                select(SchemeRepairDiagnosis).where(
                    SchemeRepairDiagnosis.scheme_id.in_(
                        [s.scheme_id for s in blocked])))).scalars()}
    for s in schemes:
        if s.repair_status != "blocked":
            out[s.scheme_id] = None
            continue
        reason = s.repair_reason or GENERIC_PROJECTION
        if (reason == REASON_COMBO_CROSS_ZONE
                and await _caller_can_read_combo(db, user.id,
                                                 diag_rows.get(s.scheme_id))):
            out[s.scheme_id] = REASON_COMBO_CROSS_ZONE
        else:
            out[s.scheme_id] = GENERIC_PROJECTION
    return out


# ── 统一装配闸(§20.3;调用方须已完成主体与方案的可见性/动作授权)──────

def require_ready(scheme: ComposerRunScheme) -> None:
    """装配闸的同步判定面(状态读取单点):blocked 即抛
    :class:`SchemeRepairRequired`(携带投影所需最小事实)。入口接入
    约定(M2:precheck;M3:execute/query/schedule/probe):

    1. 解析真实项目 + 方案并完成可见性/动作授权(404/403 先行);
    2. 调用本闸读持久化状态 —— **在解析任何秘密/凭证之前**;
    3. 捕获 ``SchemeRepairRequired`` 后经 :func:`projected_reason`
       生成对外原因(不透传内部 reason)。
    """
    if scheme.repair_status == "blocked":
        raise SchemeRepairRequired(
            # 占位原因:由调用方在授权上下文中重投影(见上方第 3 步;
            # 异步 worker 实际装配前同样重新授权并检查)
            reason=GENERIC_PROJECTION, revision=scheme.revision)


# ── 状态写入(导入/处置/修复命令;均与调用方同一事务,只 flush)────────

async def record_event(
    db: AsyncSession, scheme: ComposerRunScheme, *, action: str,
    old_status: str | None, new_status: str | None,
    old_reason: str | None, new_reason: str | None,
    old_combo_id: int | None, new_combo_id: int | None,
    old_revision: int | None, new_revision: int | None,
    source_combo_ref: str | None = None,
    resolved_combo_id: int | None = None,
    resolved_project_id: int | None = None,
    reason: str | None = None, request_id: str | None = None,
    actor_id: int | None = None, actor_name: str = "",
) -> SchemeRepairEvent:
    """事件表写入(§20.3 审计清单;历史事实,无 FK,不保存秘密)。"""
    event = SchemeRepairEvent(
        scheme_id=scheme.scheme_id, scheme_uid=scheme.scheme_uid,
        project_id=scheme.project_id, action=action,
        old_status=old_status, new_status=new_status,
        old_reason=old_reason, new_reason=new_reason,
        old_combo_id=old_combo_id, new_combo_id=new_combo_id,
        old_revision=old_revision, new_revision=new_revision,
        source_combo_ref=source_combo_ref,
        resolved_combo_id=resolved_combo_id,
        resolved_project_id=resolved_project_id,
        reason=reason, request_id=request_id,
        actor_id=actor_id, actor_name=actor_name)
    db.add(event)
    await db.flush()
    return event


async def _upsert_diagnosis(
    db: AsyncSession, scheme_id: str, *,
    source_combo_ref: str | None, resolved_combo_id: int | None,
    resolved_project_id: int | None,
) -> SchemeRepairDiagnosis:
    """受限诊断记录当前态(投影数据源;§20.3)。"""
    diag = await db.get(SchemeRepairDiagnosis, scheme_id)
    if diag is None:
        diag = SchemeRepairDiagnosis(scheme_id=scheme_id)
        db.add(diag)
    diag.source_combo_ref = source_combo_ref
    diag.resolved_combo_id = resolved_combo_id
    diag.resolved_project_id = resolved_project_id
    return diag


async def mark_blocked(
    db: AsyncSession, scheme: ComposerRunScheme, *, reason: str,
    action: str = "import.blocked",
    source_combo_ref: str | None = None,
    resolved_combo_id: int | None = None,
    resolved_project_id: int | None = None,
    request_id: str | None = None,
    actor_id: int | None = None, actor_name: str = "",
    note: str | None = None,
) -> None:
    """置 blocked(导入/恢复/显式处置/重新诊断;§20.3 状态机
    [*]→Blocked、Ready→Blocked、Blocked→Blocked)。**只 flush,不
    commit** —— 与调用方(资产恢复/处置)同一事务提交(AC-46)。
    库层 ck_scheme_combo_repair 要求 blocked 时绑定列必须为空。"""
    if reason not in (REASON_COMBO_MISSING, REASON_COMBO_CROSS_ZONE,
                      REASON_COMBO_DEPENDENCY_INVALID):
        raise ValueError(f"unknown repair reason: {reason!r}")
    old_status, old_reason = scheme.repair_status, scheme.repair_reason
    old_combo, old_rev = scheme.account_combo_id, scheme.revision
    scheme.repair_status = "blocked"
    scheme.repair_reason = reason
    scheme.account_combo_id = None
    scheme.revision += 1
    await _upsert_diagnosis(
        db, scheme.scheme_id,
        source_combo_ref=source_combo_ref,
        resolved_combo_id=resolved_combo_id,
        resolved_project_id=resolved_project_id)
    await record_event(
        db, scheme, action=action,
        old_status=old_status, new_status="blocked",
        old_reason=old_reason, new_reason=reason,
        old_combo_id=old_combo, new_combo_id=None,
        old_revision=old_rev, new_revision=scheme.revision,
        source_combo_ref=source_combo_ref,
        resolved_combo_id=resolved_combo_id,
        resolved_project_id=resolved_project_id,
        reason=note, request_id=request_id,
        actor_id=actor_id, actor_name=actor_name)
    await db.flush()


def _require_blocked_for_command(scheme: ComposerRunScheme) -> None:
    if scheme.repair_status != "blocked":
        raise RepairCommandError(
            409, "scheme_not_blocked",
            "修复命令仅作用于 blocked 方案;ready 方案的绑定变更走普通保存")


def _check_expected_revision(scheme: ComposerRunScheme,
                             expected_revision: int) -> None:
    if expected_revision != scheme.revision:
        raise RepairCommandError(
            409, "scheme_revision_conflict",
            f"方案已发生变化(revision {scheme.revision} ≠ "
            f"expected {expected_revision}),请刷新后重试")


async def _require_active_combo_capability(
    db: AsyncSession, scheme: ComposerRunScheme,
) -> None:
    """修复前置:项目 active + 组合能力开(§20.3「锁定方案,验证当前
    blocked 状态、项目状态与能力」)。"""
    from ..models.project import Project

    proj = await db.get(Project, scheme.project_id)
    if proj is None:
        raise RepairCommandError(409, "scheme_repair_required",
                                 "方案所属项目已不存在")
    if proj.status != Project.STATUS_ACTIVE:
        raise RepairCommandError(
            409, "project_not_active",
            f"项目状态为 {proj.status},归档起禁止新写入(§13.1)")
    from ..policies import capability_enabled

    if not capability_enabled(proj.kind, "account_combo"):
        raise RepairCommandError(
            422, "account_combo_capability_disabled",
            f"{proj.kind} 项目未开放账户组合能力(§7 能力矩阵)")


async def rebind_combo(
    db: AsyncSession, scheme: ComposerRunScheme, *, user: Any,
    combo_id: int, expected_revision: int,
    request_id: str | None = None,
) -> ComposerRunScheme:
    """修复命令 ①:blocked → ready,指定合法同区组合(§20.3)。

    门:方案修改权限与绑定目标授权由**路由层**先行(§21 scheme.update
    + 目标组合 read);此处验证 blocked 状态、expected_revision、项目
    状态与能力、目标组合存在∧同区∧可读。绑定/状态/原因/revision 与
    审计同事务;失败整体回滚。"""
    _require_blocked_for_command(scheme)
    _check_expected_revision(scheme, expected_revision)
    await _require_active_combo_capability(db, scheme)
    combo = await db.get(AccountCombo, combo_id)
    if combo is not None:
        from ..models.project import Project

        proj = await db.get(Project, combo.project_id)
        if proj is None or not await project_access.can_view_project(
                db, user.id, proj):
            combo = None
    if combo is None:
        raise RepairCommandError(
            404, "account_combo_not_found",
            f"账户组合不存在: {combo_id}")
    if combo.project_id != scheme.project_id:
        raise RepairCommandError(
            422, "account_combo_scope_mismatch",
            "组合与方案须同项目(§5.1 硬同区;跨区绑定被拒,不猜测替代)")
    old_status, old_reason = scheme.repair_status, scheme.repair_reason
    old_combo, old_rev = scheme.account_combo_id, scheme.revision
    scheme.account_combo_id = combo.id
    scheme.repair_status = "ready"
    scheme.repair_reason = None
    scheme.revision += 1
    await _upsert_diagnosis(
        db, scheme.scheme_id, source_combo_ref=None,
        resolved_combo_id=None, resolved_project_id=None)
    await record_event(
        db, scheme, action="rebind_combo",
        old_status=old_status, new_status="ready",
        old_reason=old_reason, new_reason=None,
        old_combo_id=old_combo, new_combo_id=combo.id,
        old_revision=old_rev, new_revision=scheme.revision,
        source_combo_ref=None, resolved_combo_id=combo.id,
        resolved_project_id=combo.project_id,
        reason=None, request_id=request_id,
        actor_id=user.id,
        actor_name=getattr(user, "display_name", "") or "")
    await db.flush()
    return scheme


async def confirm_no_combo(
    db: AsyncSession, scheme: ComposerRunScheme, *, user: Any,
    expected_revision: int, reason: str,
    request_id: str | None = None,
) -> ComposerRunScheme:
    """修复命令 ②:blocked → ready,明确确认无组合语义(§20.3)。

    确认理由是审计事实(``reason``),不是 repair_reason(ready 恒无
    原因);确认不得绕过其他凭证或装配约束(装配闸与预检照常)。"""
    _require_blocked_for_command(scheme)
    _check_expected_revision(scheme, expected_revision)
    await _require_active_combo_capability(db, scheme)
    if not (reason := (reason or "").strip()):
        raise RepairCommandError(
            422, "confirm_reason_required",
            "确认无组合须提供理由(§20.3;审计留痕)")
    old_status, old_reason = scheme.repair_status, scheme.repair_reason
    old_combo, old_rev = scheme.account_combo_id, scheme.revision
    scheme.account_combo_id = None
    scheme.repair_status = "ready"
    scheme.repair_reason = None
    scheme.revision += 1
    await _upsert_diagnosis(
        db, scheme.scheme_id, source_combo_ref=None,
        resolved_combo_id=None, resolved_project_id=None)
    await record_event(
        db, scheme, action="confirm_no_combo",
        old_status=old_status, new_status="ready",
        old_reason=old_reason, new_reason=None,
        old_combo_id=old_combo, new_combo_id=None,
        old_revision=old_rev, new_revision=scheme.revision,
        reason=reason, request_id=request_id,
        actor_id=user.id,
        actor_name=getattr(user, "display_name", "") or "")
    await db.flush()
    return scheme
