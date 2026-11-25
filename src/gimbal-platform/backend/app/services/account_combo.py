"""账户组合方案级读取、垫底合并与绑定闸(设计方案 v4 §3/§5)。

组合引用唯一来源是运行方案 payload 的 ``accountComboId``。本模块只
负责纯读取、机械垫底和绑定权限/同区校验;条目全量校验仍归组合保存面,
执行面只按实际引用服务 fail-closed。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ComboBase:
    """组合条目映射、溯源与缺失信号。"""

    combo_id: int | None
    name: str
    revision: int
    entries: dict[str, str] = field(default_factory=dict)
    missing: bool = False

    @property
    def bound(self) -> bool:
        return self.combo_id is not None

    def fingerprint(self) -> dict | None:
        if not self.bound:
            return None
        return {"id": self.combo_id, "revision": self.revision}


async def combo_base(db: AsyncSession, combo_id: int | None) -> ComboBase:
    """按方案 payload 中的组合 id 纯读取条目映射。"""
    from ..models import AccountCombo

    if not isinstance(combo_id, int):
        return ComboBase(None, "", 0)
    combo = await db.get(AccountCombo, combo_id)
    if combo is None:
        return ComboBase(combo_id, "", 0, missing=True)
    entries: dict[str, str] = {}
    for entry in (combo.payload or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        service, alias = entry.get("service"), entry.get("alias")
        if (isinstance(service, str) and service
                and isinstance(alias, str) and alias):
            entries[service] = alias
    return ComboBase(combo.id, combo.name, combo.revision or 1, entries)


async def scheme_combo(
    db: AsyncSession, scheme_payload: dict | None,
) -> ComboBase:
    payload = scheme_payload or {}
    return await combo_base(db, payload.get("accountComboId"))


def pad_bindings(bindings: dict | None, combo: ComboBase) -> dict:
    """组合垫底,面内既有服务键原样胜出。"""
    out = dict(bindings or {})
    if not combo.bound:
        return out
    for service, alias in combo.entries.items():
        if service not in out:
            out[service] = {"alias": alias}
    return out


async def scheme_bindings_with_combo(
    db: AsyncSession, scheme_payload: dict | None,
) -> dict:
    from ..schemas.scenario_composer import scrub_retired_bindings

    payload = scheme_payload or {}
    combo = await scheme_combo(db, payload)
    return pad_bindings(
        scrub_retired_bindings(payload.get("serviceBindings")), combo)


class ComboIdentityMissing(ValueError):
    """引用服务的组合条目不可用,执行面统一映射 409。"""

    def __init__(self, message: str, *, combo_id: int,
                 service: str | None = None,
                 alias: str | None = None) -> None:
        super().__init__(f"identity_combo_missing: {message}")
        self.message = message
        self.combo_id = combo_id
        self.service = service
        self.alias = alias

    def detail(self) -> dict:
        out: dict = {"comboId": self.combo_id}
        if self.service is not None:
            out["service"] = self.service
        if self.alias is not None:
            out["alias"] = self.alias
        return out


async def referenced_combo_gate(
    db: AsyncSession, combo: ComboBase, services: Iterable[str],
    bindings: dict | None = None,
    slot_map: "dict[str, str] | None" = None,
) -> None:
    """只校验仍由组合供号的引用服务;面内覆盖与换用覆盖不连坐。"""
    if not combo.bound:
        return
    if combo.missing:
        raise ComboIdentityMissing(
            f"方案绑定的账户组合 {combo.combo_id} 已不存在"
            " —— 请重新绑定或解除绑定", combo_id=combo.combo_id)
    from ..services.service_aliases import effective_alias

    lookup = slot_map or {}
    effective: dict[str, str] = {}
    for service in services:
        alias = combo.entries.get(service)
        if alias is None:
            continue
        selected = (effective_alias(service, bindings)
                    if service in (bindings or {}) else alias)
        if lookup.get(selected, selected) != selected:
            continue
        if selected == alias:
            effective[service] = alias
    if not effective:
        return
    from ..models.service_identity import ServiceIdentity

    rows = set((await db.execute(
        select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name.in_(effective.values()))
    )).scalars())
    for service in sorted(effective):
        alias = effective[service]
        if alias in rows:
            continue
        raise ComboIdentityMissing(
            f"组合 {combo.combo_id}({combo.name})中服务 {service!r}"
            f"的身份条目 {alias!r} 已注销 —— 请修复组合或解除绑定",
            combo_id=combo.combo_id, service=service, alias=alias)


class ComboBindingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def detail(self) -> dict:
        return {"code": self.code, "message": self.message}


async def require_combo_bindable(
    db: AsyncSession, user, scenario_row, combo_id: int | None, *,
    lock: bool = True,
):
    """方案绑定闸:存在、可读、同区;可选锁组合行串行化删除。"""
    from ..models import AccountCombo
    from ..services.zone import (
        ensure_member_same_zone, my_project_roles, public_project_id,
    )

    if combo_id is None:
        return None
    stmt = select(AccountCombo).where(AccountCombo.id == combo_id)
    if lock:
        stmt = stmt.with_for_update()
    combo = (await db.execute(stmt)).scalar_one_or_none()
    if combo is None:
        raise ComboBindingError(
            "account_combo_not_found", f"组合不存在或不可读: {combo_id}")
    if combo.scope == "user":
        readable = combo.scope_id == user.id
    else:
        readable = combo.scope_id in await my_project_roles(db, user.id)
    if not readable:
        raise ComboBindingError(
            "account_combo_not_found", f"组合不存在或不可读: {combo_id}")

    public_id = await public_project_id(db)
    if scenario_row.project_id == public_id:
        raise ComboBindingError(
            "account_combo_scope_mismatch", "公共场景不绑定账户组合")
    if combo.scope == "user":
        if scenario_row.project_id is not None:
            raise ComboBindingError(
                "account_combo_scope_mismatch",
                "个人组合只能绑定本人私有场景(v1 硬同区)")
        try:
            ensure_member_same_zone(
                suite_project_id=None, suite_owner_id=scenario_row.owner_id,
                scen_project_id=None, scen_owner_id=combo.scope_id,
                scenario_id=scenario_row.scenario_id)
        except ValueError:
            raise ComboBindingError(
                "account_combo_scope_mismatch",
                "个人组合只能绑定本人私有场景(v1 硬同区)") from None
    elif scenario_row.project_id != combo.scope_id:
        raise ComboBindingError(
            "account_combo_scope_mismatch",
            "项目组合只能绑定同一项目的场景(v1 硬同区)")
    return combo
