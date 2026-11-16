"""账户引用反查(重构 2026-11-16 账户实体化)— 读时计算,不建反向索引。

引用语义:身份条目按 ref(username/default)引用账户,场景按**条目名**
引用身份(``${auth.<条目名>.*}`` 模板 / ``config.users`` 快照键)。
账户 → 条目 → 场景两层聚合:

* ``template`` — steps 里的 ``${auth.<条目名>.*}`` 模板(扫描单一实现
  复用 ``auth_ref_scan``,与注入清单同源);
* ``snapshot`` — ``definition.config.users`` 的同名键(快照自足,非
  运行依赖 — 卫生信号:哪些场景揣着旧密码副本)。

删除拦截口径(沿用 §1.4.3/§1.5 拍板):**硬 409 只对本人场景的
template 引用**(它们会在下次运行时真正失效);快照与他人场景只在
面板提示。可见性:计数照给,场景名按 ``can_read_scenario`` 过滤,
剩余计为 hidden。实时扫 O(场景数 × payload):内部平台量级可接受,
面板点开才算;扛不住的那天扩写路径,不另起表。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.auth_account import AuthAccount
from ..models.composer_scenario import ComposerScenario
from ..models.service import Service
from ..models.service_identity import ServiceIdentity
from .auth_ref_scan import scan_auth_aliases
from .scenario_store import definition_from_payload

KIND_TEMPLATE = "template"
KIND_SNAPSHOT = "snapshot"

# 面板列表行的「N 场景」计数口径:模板引用(真依赖),快照不进计数、
# 只在面板里按 kind 展示。
COUNTED_KINDS = frozenset({KIND_TEMPLATE})


@dataclass
class ScenarioRef:
    scenario_id: str
    owner_id: int
    visibility: str
    name: str
    # S1.1:区维度(读面谓词 can_pure 按 project_id 判)
    project_id: int | None = None
    kinds: set[str] = field(default_factory=set)


async def _scan_scenario_refs(db: AsyncSession) -> dict[str, list[ScenarioRef]]:
    """全场景一遍扫 → 条目名 → 引用记录。所有调用方共享同一次扫描。

    config.users 的键集合就是快照引用面(键名 = 身份条目名)。
    """
    scenarios = (await db.execute(select(ComposerScenario))).scalars().all()

    by_alias: dict[str, list[ScenarioRef]] = {}
    per_scenario: dict[tuple[str, str], ScenarioRef] = {}
    for row in scenarios:
        defn = definition_from_payload(row.payload)
        meta = defn.get("meta") if isinstance(defn.get("meta"), dict) else {}
        name = str(meta.get("name") or row.scenario_id)

        template_aliases: list[str] = []
        steps = defn.get("steps")
        if isinstance(steps, list):
            template_aliases = scan_auth_aliases(steps)
        # webhook v4 §3.2:setup/teardown 条目的 ${auth.*} 同为模板引用
        # (与 exec_auth_aliases_of_definition 同一扫描源,不漂移)
        from .service_aliases import setup_teardown_nodes
        template_aliases.extend(
            scan_auth_aliases(setup_teardown_nodes(defn)))

        snapshot_aliases: list[str] = []
        users = defn.get("config")
        users = users.get("users") if isinstance(users, dict) else None
        if isinstance(users, dict):
            snapshot_aliases = [str(k) for k in users]

        for kind, aliases in ((KIND_TEMPLATE, template_aliases),
                              (KIND_SNAPSHOT, snapshot_aliases)):
            for a in aliases:
                ref = per_scenario.get((a, row.scenario_id))
                if ref is None:
                    ref = ScenarioRef(
                        scenario_id=row.scenario_id,
                        owner_id=row.owner_id,
                        visibility=("public" if row.project_id is not None else "private"),
                        project_id=row.project_id,
                        name=name,
                    )
                    per_scenario[(a, row.scenario_id)] = ref
                    by_alias.setdefault(a, []).append(ref)
                ref.kinds.add(kind)
    return by_alias


async def identities_for_account(
    db: AsyncSession, account: AuthAccount,
) -> list[ServiceIdentity]:
    """ref 指向该账户的身份条目(条目不分池,匹配只看 system/env/ref
    三元;与 run_prepare._resolve_identities 的 ref 解析同构)。"""
    idents = (await db.execute(
        select(ServiceIdentity, Service.system).join(
            Service, Service.name == ServiceIdentity.base_service
        ).where(
            Service.system == account.system,
            ServiceIdentity.env_id == account.env_id,
        ))).all()
    out: list[ServiceIdentity] = []
    for ident, _svc in idents:
        if ident.ref_mode == "username":
            if ident.ref_username == account.username:
                out.append(ident)
        elif account.is_default:  # ref_mode=default:吃池内默认账户
            out.append(ident)
    return sorted(out, key=lambda i: i.alias_name)


async def _identity_name_map(
    db: AsyncSession, accounts: list[AuthAccount],
) -> dict[int, list[ServiceIdentity]]:
    """账户 id → ref 条目清单(列表页批量;一次查询全体条目+主档)。"""
    if not accounts:
        return {}
    pairs = {(a.system, a.env_id) for a in accounts}
    rows = (await db.execute(
        select(ServiceIdentity, Service.system).join(
            Service, Service.name == ServiceIdentity.base_service)
    )).all()
    by_key: dict[tuple[str, int], list] = {}
    for ident, sysname in rows:
        by_key.setdefault((sysname, ident.env_id), []).append(ident)
    out: dict[int, list[ServiceIdentity]] = {}
    for a in accounts:
        matched = []
        for ident in by_key.get((a.system, a.env_id), []):
            if (ident.ref_mode == "username"
                    and ident.ref_username == a.username):
                matched.append(ident)
            elif ident.ref_mode != "username" and a.is_default:
                matched.append(ident)
        out[a.id] = sorted(matched, key=lambda i: i.alias_name)
    return out


async def references(
    db: AsyncSession, *, user, account: AuthAccount,
) -> dict:
    """反查面板数据:ref 条目清单 + 场景引用(条目名聚合,可见名 +
    不可见计数)。"""
    by_alias = await _scan_scenario_refs(db)
    idents = await identities_for_account(db, account)
    hits: list[ScenarioRef] = []
    for ident in idents:
        hits.extend(by_alias.get(ident.alias_name, []))
    from types import SimpleNamespace

    from ..routers._ownership import can_pure
    from .zone import my_project_roles, public_project_id
    _ctx = dict(public_project_id=await public_project_id(db),
                project_roles=await my_project_roles(db, user.id))
    visible = [r for r in hits
               if can_pure(user, "scenario", "read",
                           SimpleNamespace(owner_id=r.owner_id,
                                           project_id=r.project_id),
                           **_ctx)]
    return {
        "identity_refs": [
            {"alias_name": i.alias_name, "base_service": i.base_service,
             "env_id": i.env_id, "ref_mode": i.ref_mode,
             "ref_username": i.ref_username or None}
            for i in idents
        ],
        "scenario_refs": {
            "visible": [
                {"scenario_id": r.scenario_id, "name": r.name,
                 "kinds": sorted(r.kinds), "owner_id": r.owner_id}
                for r in sorted(visible, key=lambda r: r.scenario_id)
            ],
            "hidden_count": len(hits) - len(visible),
        },
    }


async def blocking_refs(
    db: AsyncSession, *, user, account: AuthAccount,
) -> list[str]:
    """删除拦截(窄口径):ref 该账户的条目被本人场景 template 引用 —
    删除会让这些场景下次运行真正失效。快照/他人场景不阻断。"""
    by_alias = await _scan_scenario_refs(db)
    idents = await identities_for_account(db, account)
    blocking: set[str] = set()
    for ident in idents:
        blocking.update(
            r.scenario_id for r in by_alias.get(ident.alias_name, [])
            if r.owner_id == user.id and (r.kinds & COUNTED_KINDS))
    return sorted(blocking)


async def account_ref_counts(
    db: AsyncSession, accounts: list[AuthAccount],
) -> dict[int, dict[str, int]]:
    """列表页计数(一次扫描服务所有行):``{账户id: {条目数, 场景数}}``。
    场景计数 = ref 条目的模板引用去重场景数(快照不进计数)。"""
    by_alias = await _scan_scenario_refs(db)
    ident_map = await _identity_name_map(db, accounts)
    out: dict[int, dict[str, int]] = {}
    for aid, idents in ident_map.items():
        scen_ids = {
            r.scenario_id
            for i in idents
            for r in by_alias.get(i.alias_name, [])
            if r.kinds & COUNTED_KINDS}
        out[aid] = {"identity_count": len(idents),
                    "scenario_count": len(scen_ids)}
    return out


# ── M5-5 计数增量化(指纹缓存;反查面板 references() 保持实时扫)─────
_counts_cache: dict = {"fingerprint": None, "value": None}


async def _counts_fingerprint(db: AsyncSession) -> tuple:
    scen = (await db.execute(select(
        func.count(), func.max(ComposerScenario.updated_at)
    ).select_from(ComposerScenario))).one()
    idents = (await db.execute(select(
        func.count(), func.max(ServiceIdentity.updated_at)
    ).select_from(ServiceIdentity))).one()
    return (scen, idents)


def reset_counts_cache_for_tests() -> None:
    _counts_cache["fingerprint"] = None
    _counts_cache["value"] = None


async def cached_scenario_refs(db: AsyncSession) -> dict[str, int]:
    """条目名 → 场景引用数(指纹缓存;账户计数经 account_ref_counts
    组合,供轻量消费方)。"""
    fp = await _counts_fingerprint(db)
    if _counts_cache["value"] is not None and _counts_cache["fingerprint"] == fp:
        return _counts_cache["value"]
    by_alias = await _scan_scenario_refs(db)
    value = {
        name: len({r.scenario_id for r in refs if r.kinds & COUNTED_KINDS})
        for name, refs in by_alias.items()}
    _counts_cache["fingerprint"] = fp
    _counts_cache["value"] = value
    return value
