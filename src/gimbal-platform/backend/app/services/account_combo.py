"""账户组合:资源 CRUD、绑定闸与引用统计(UPC M2;组合 v4 §5 适配 UPC)。

组合 = 服务 → 已登记身份条目的引用集(``payload.entries``),归属
真实项目容器(``project_id``,§5;v4 的 (scope, scope_id) 多态归属随
UPC 收敛)。本模块职责:

* **CRUD/默认/revision** —— 条目全量校验只在**保存面**(复用
  ``validate_binding_aliases``:别名存在 ∧ 与服务键同基础服务);
  ``revision`` 仅条目变化 +1(元数据修改只动 updated_at + 审计);
  默认组合每项目至多一个(部分唯一索引为并发权威,置默认原子切换)。
* **能力闸** —— §7 矩阵:公共项目不创建组合(422;能力关闭必须在
  API 层拒绝,AC-07/26);创建门 = 项目内容写权(private 属主 /
  normal 可写成员,经 ``project_access.resolve_content_target``)。
* **引用统计与删除保护** —— 引用唯一事实源是方案**显式列**
  ``account_combos`` ← ``composer_run_schemes.account_combo_id``(§20.2,
  不扫 payload):被引用的组合删除 → 409 ``account_combo_in_use`` +
  引用方案清单(含所属场景);in-use 复核与删除同事务,不级联解绑。
* **绑定闸**(:func:`require_combo_bindable`)—— 方案保存面的组合
  绑定校验:存在 ∧ 可读 ∨ 同区(§5.1 硬同区 = combo.project_id ==
  scenario.project_id,两个私有空间同属一人也互斥)。

执行装配的垫底合并(``combo_base``/``scheme_bindings_with_combo``)
随 M3 执行装配接入;此处先立读取面(方案显式列 → 条目映射)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account_combo import AccountCombo
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario
from ..policies import capability_enabled


class ComboError(Exception):
    """组合域业务违例(路由层映射 HTTP;``status`` + ``code``)。"""

    def __init__(self, status: int, code: str, message: str,
                 detail: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail or {}


def _entries_map(combo: AccountCombo) -> dict[str, str]:
    """``payload.entries`` → {service: alias}(形状无效条目跳过;
    保存面已全量校验,这里是读面的机械投影)。"""
    out: dict[str, str] = {}
    for entry in (combo.payload or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        service, alias = entry.get("service"), entry.get("alias")
        if (isinstance(service, str) and service
                and isinstance(alias, str) and alias):
            out[service] = alias
    return out


@dataclass
class ComboBase:
    """组合条目映射、溯源与缺失信号(执行/预检装配的读取面)。"""

    combo_id: int | None
    name: str
    revision: int
    entries: dict[str, str] = field(default_factory=dict)
    missing: bool = False

    @property
    def bound(self) -> bool:
        return self.combo_id is not None


async def combo_base(db: AsyncSession, combo_id: int | None) -> ComboBase:
    """按方案显式列的组合 id 纯读取条目映射(§3.2 校验职责分层:
    自身不校验条目 —— 全量校验在保存面,执行/预检按引用服务校验)。"""
    if not isinstance(combo_id, int):
        return ComboBase(None, "", 0)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None:
        return ComboBase(combo_id, "", 0, missing=True)
    return ComboBase(combo.id, combo.name, combo.revision or 1,
                     _entries_map(combo))


def pad_bindings(bindings: dict | None, combo: ComboBase) -> dict:
    """组合垫底(面内既有服务键原样胜出;组合永远垫底,v4 §3.1)。"""
    out = dict(bindings or {})
    if not combo.bound:
        return out
    for service, alias in combo.entries.items():
        if service not in out:
            out[service] = {"alias": alias}
    return out


async def scheme_bindings_with_combo(
    db: AsyncSession, scheme: ComposerRunScheme,
) -> dict:
    """方案生效身份绑定 = {**组合条目, **方案 serviceBindings}
    (逐服务 {alias} 形状,与 ServiceBinding wire 同形)。绑定唯一事实
    源是显式列,M3 各装配面经此取基础。"""
    from ..schemas.scenario_composer import scrub_retired_bindings

    combo = await combo_base(db, scheme.account_combo_id)
    payload = scheme.payload or {}
    return pad_bindings(
        scrub_retired_bindings(payload.get("serviceBindings")), combo)


# ── 校验(保存面全量;§3.2 职责分层)──────────────────────────────

async def _validate_entries(db: AsyncSession, entries: list[dict]) -> None:
    """条目逐条过 validate_binding_aliases(别名存在 ∧ 同基础服务);
    形状/重复服务 → 422 account_combo_entry_invalid(组合自身新增码
    只留形状/重复类)。"""
    seen: set[str] = set()
    bindings: dict[str, dict] = {}
    for e in entries:
        if (not isinstance(e, dict) or not isinstance(e.get("service"), str)
                or not e.get("service")
                or not isinstance(e.get("alias"), str) or not e.get("alias")):
            raise ComboError(422, "account_combo_entry_invalid",
                             "组合条目须为 {service, alias} 且两者非空")
        service = e["service"]
        if service in seen:
            raise ComboError(
                422, "account_combo_entry_invalid",
                f"服务 {service!r} 在组合中重复(一条一服务)")
        seen.add(service)
        bindings[service] = {"alias": e["alias"]}
    from .service_aliases import BindingAliasInvalid, validate_binding_aliases

    try:
        await validate_binding_aliases(db, bindings)
    except BindingAliasInvalid as e:
        raise ComboError(422, e.code, e.message) from None


def _check_capability(project_kind: str) -> None:
    """§7 能力矩阵:公共项目不创建组合(关闭必须在 API 层拒绝)。"""
    if not capability_enabled(project_kind, "account_combo"):
        raise ComboError(
            422, "account_combo_capability_disabled",
            f"{project_kind} 项目未开放账户组合能力(§7 能力矩阵)")


# ── CRUD ─────────────────────────────────────────────────────────

def _payload_of(entries: list[dict]) -> dict:
    return {"entries": [
        {"service": e["service"], "alias": e["alias"]} for e in entries]}


async def create_combo(
    db: AsyncSession, *, project: Any, name: str, description: str = "",
    entries: list[dict] | None = None, is_default: bool = False,
    updated_by_id: int | None = None,
) -> AccountCombo:
    """新建组合(创建门由路由层经 resolve_content_target 完成;能力
    闸在此)。条目形状/重复/别名校验先行;项目内重名 → 409。"""
    _check_capability(project.kind)
    entries = entries or []
    await _validate_entries(db, entries)
    dup = (await db.execute(select(AccountCombo.id).where(
        AccountCombo.project_id == project.id,
        AccountCombo.name == name))).scalar_one_or_none()
    if dup is not None:
        raise ComboError(409, "account_combo_name_exists",
                         f"账户组合名 '{name}' 已存在")
    row = AccountCombo(
        project_id=project.id, name=name, description=description or "",
        is_default=bool(is_default), payload=_payload_of(entries),
        revision=1, updated_by_id=updated_by_id)
    db.add(row)
    await db.flush()
    return row


async def update_combo(
    db: AsyncSession, combo: AccountCombo, *,
    name: str | None = None, description: str | None = None,
    entries: list[dict] | None = None,
    updated_by_id: int | None = None,
) -> AccountCombo:
    """整体替换式更新:None = 不改;entries 显式给值(含 [])整体替换,
    逐条过保存面校验;**仅条目有实质变化 revision +1**(元数据只动
    updated_at + 审计,不制造新身份映射版本)。"""
    if name is not None:
        dup = (await db.execute(select(AccountCombo.id).where(
            AccountCombo.project_id == combo.project_id,
            AccountCombo.name == name,
            AccountCombo.id != combo.id))).scalar_one_or_none()
        if dup is not None:
            raise ComboError(409, "account_combo_name_exists",
                             f"账户组合名 '{name}' 已存在")
        combo.name = name
    if description is not None:
        combo.description = description
    if entries is not None:
        await _validate_entries(db, entries)
        new_payload = _payload_of(entries)
        if new_payload != (combo.payload or {}):
            combo.payload = new_payload
            combo.revision += 1
    combo.updated_by_id = updated_by_id
    await db.flush()
    return combo


async def set_default(db: AsyncSession, combo: AccountCombo) -> AccountCombo:
    """换默认(同项目旧默认自动摘除;同事务原子切换,部分唯一索引
    为并发权威)。默认仅用于新建/另存方案的**预选提示**,不参与解析、
    不静默自动绑定(§5.1)。"""
    from sqlalchemy import update

    await db.execute(
        update(AccountCombo)
        .where(AccountCombo.project_id == combo.project_id,
               AccountCombo.is_default.is_(True),
               AccountCombo.id != combo.id)
        .values(is_default=False))
    combo.is_default = True
    await db.flush()
    return combo


async def referencing_schemes(
    db: AsyncSession, combo_id: int,
) -> list[dict]:
    """引用清单(引用统计/删除前差异确认;显式列 SQL,不扫 payload):
    ``[{schemeId, schemeName, scenarioId, scenarioName}]``。"""
    rows = (await db.execute(
        select(ComposerRunScheme.scheme_id, ComposerRunScheme.name,
               ComposerRunScheme.scenario_id, ComposerScenario.name)
        .where(ComposerRunScheme.account_combo_id == combo_id)
        .outerjoin(ComposerScenario, and_(
            ComposerScenario.project_id == ComposerRunScheme.project_id,
            ComposerScenario.scenario_id == ComposerRunScheme.scenario_id))
        .order_by(ComposerRunScheme.scenario_id, ComposerRunScheme.name)
    )).all()
    return [{"schemeId": s, "schemeName": n,
             "scenarioId": sid, "scenarioName": (sn or sid)}
            for s, n, sid, sn in rows]


async def reference_count(db: AsyncSession, combo_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(
        ComposerRunScheme).where(
            ComposerRunScheme.account_combo_id == combo_id))).scalar_one()


async def delete_combo(db: AsyncSession, combo: AccountCombo) -> None:
    """删除保护(§5.1:引用中的组合不可直接删除,禁止级联解绑):
    in-use 复核与删除同事务。被引用 → 409 ``account_combo_in_use`` +
    引用方案清单。"""
    refs = await referencing_schemes(db, combo.id)
    if refs:
        raise ComboError(
            409, "account_combo_in_use",
            f"组合被 {len(refs)} 个方案引用,须先解绑或换绑后再删除",
            detail={"schemes": refs})
    await db.delete(combo)
    await db.flush()


# ── 方案绑定闸(run-schemes 保存面;§16.1)──────────────────────────

async def require_combo_bindable(
    db: AsyncSession, user: Any, scenario_row: Any, combo_id: int | None,
    *, lock: bool = True,
) -> AccountCombo | None:
    """方案绑定闸:存在 ∧ 可读 ∧ **同区**(§5.1 硬同区 =
    combo.project_id == scenario.project_id;两个私有空间同属一人也
    互斥)。None = 解绑/未绑定,恒过。可选锁组合行串行化删除竞态。"""
    from . import project_access

    if combo_id is None:
        return None
    stmt = select(AccountCombo).where(AccountCombo.id == combo_id)
    if lock:
        stmt = stmt.with_for_update()
    combo = (await db.execute(stmt)).scalar_one_or_none()
    if combo is not None:
        from ..models.project import Project

        proj = await db.get(Project, combo.project_id)
        if proj is None or not await project_access.can_view_project(
                db, user.id, proj):
            combo = None
    if combo is None:
        raise ComboError(422, "account_combo_not_found",
                         f"组合不存在或不可读: {combo_id}")
    if combo.project_id != scenario_row.project_id:
        raise ComboError(422, "account_combo_scope_mismatch",
                         "组合与方案父场景须同项目(§5.1 硬同区)")
    return combo
