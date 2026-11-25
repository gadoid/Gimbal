"""combo_base 单点助手(账户组合设计方案 §3.2/§6.3,定稿 05)。

组合条目在各执行装配面做**垫底合并**(``merged = {**组合条目,
**该面既有合并结果}``——组合永远垫底,不重排任何面内覆盖序);
本模块只提供两件小事:

* :func:`combo_base` —— **纯读取映射层**:读场景
  ``definition.config.accountCombo`` → 组合 ``payload.entries`` →
  ``{service: alias}``。**自身不做条目校验**(校验职责分层:全量校验
  只在组合保存面与就绪页;执行/预检只按引用服务校验,由调用面归
  ``identity_combo_missing``,§6.3 fail-closed);
* :func:`pad_bindings` —— 面内一次合并的机械半边(垫底,不改内层)。

八装配面各自按其接法合并(令牌面装载时合并防覆写、集成面规范化
scheme_payload、Suite 直跑调用方合并等,§3.2 表)——**不建大一统
resolver**;面间漂移由测试面的「装配面同基础断言」钉死。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ComboBase:
    """combo_base 的返回形态:条目映射 + 溯源四件套 + 缺失信号。

    ``missing`` = 场景绑定了组合但组合行已被并发删除 —— 删除有
    in-use 闸,正常不可达;调用面须 fail-closed 归
    ``identity_combo_missing``,**绝不以裸键继续执行**(§6.3)。
    ``combo_id is None`` = 未绑定(组合不参与解析,一切照旧)。
    """

    combo_id: int | None
    name: str
    revision: int
    entries: dict[str, str] = field(default_factory=dict)
    missing: bool = False

    @property
    def bound(self) -> bool:
        return self.combo_id is not None

    def fingerprint(self) -> dict | None:
        """订阅指纹投影形态(§6.5):id+name+revision;未绑 = None。"""
        if not self.bound:
            return None
        return {"id": self.combo_id, "name": self.name,
                "revision": self.revision}


async def combo_base(db: AsyncSession, scenario_row) -> ComboBase:
    """纯读取映射(§3.2):场景行 → 组合条目 ``{service: alias}``。"""
    from ..models import AccountCombo
    from .scenario_store import ACCOUNT_COMBO_REF_KEY

    cfg = ((scenario_row.payload or {}).get("definition") or {}).get("config")
    cid = cfg.get(ACCOUNT_COMBO_REF_KEY) if isinstance(cfg, dict) else None
    if not isinstance(cid, int):
        return ComboBase(None, "", 0)
    combo = await db.get(AccountCombo, cid)
    if combo is None:
        return ComboBase(cid, "", 0, missing=True)
    entries: dict[str, str] = {}
    for e in (combo.payload or {}).get("entries") or []:
        if not isinstance(e, dict):
            continue
        svc, alias = e.get("service"), e.get("alias")
        if isinstance(svc, str) and svc and isinstance(alias, str) and alias:
            entries[svc] = alias
    return ComboBase(combo.id, combo.name, combo.revision or 1, entries)


def pad_bindings(bindings: dict | None, combo: ComboBase) -> dict:
    """垫底合并的机械半边:``{**组合条目, **面既有合并结果}`` —— 面内
    已有的服务键原样胜出(覆盖序不动),组合只补面内没有的服务。

    返回新 dict,不改入参(面既有合并结果可能是共享对象);值域同
    ``serviceBindings`` 现行形态 ``{service: {"alias": name}}``。
    """
    out = dict(bindings or {})
    if not combo.bound:
        return out
    for svc, alias in combo.entries.items():
        if svc not in out:
            out[svc] = {"alias": alias}
    return out


class ComboIdentityMissing(ValueError):
    """引用服务的组合条目不可用(§6.3 fail-closed):组合行被并发删除,
    或引用服务的条目别名已注销。``code`` 恒 ``identity_combo_missing``;
    各执行面按自己的传输形态透传(Conflict / HTTPException 409 /
    PrecheckGateError / GraphDispatchError),detail 携带定位三件套。"""

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
) -> None:
    """执行/预检面 fail-closed(§6.3):**只校验本场景实际引用的服务**
    的组合条目——未引用服务的悬空条目不阻断执行。

    * 组合行缺失(``combo.missing``,删除竞态)→ :class:`ComboIdentityMissing`
      (调用面映射 409);
    * 引用服务的条目别名已注销 → 同码(携带 comboId/service/alias,
      修复组合或重新绑定后自动恢复,同 missing_credential 族语义);
    * 条目在、当前池无账户 / 多候选 —— **不在此判**,沿用既有
      ``account_missing`` / ``account_ambiguous`` 分类(§5.2)。
    """
    if not combo.bound:
        return
    if combo.missing:
        raise ComboIdentityMissing(
            f"场景绑定的账户组合 {combo.combo_id} 已不存在"
            " —— 请重新绑定或解除绑定", combo_id=combo.combo_id)
    wanted = {s for s in services if s in combo.entries}
    if not wanted:
        return
    from sqlalchemy import select

    from ..models.service_identity import ServiceIdentity

    rows = set((await db.execute(
        select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name.in_(
                [combo.entries[s] for s in wanted])))).scalars())
    for s in sorted(wanted):
        alias = combo.entries[s]
        if alias in rows:
            continue
        raise ComboIdentityMissing(
            f"组合 {combo.combo_id}({combo.name})中服务 {s!r}"
            f"的身份条目 {alias!r} 已注销 —— 请修复组合或解除绑定",
            combo_id=combo.combo_id, service=s, alias=alias)
