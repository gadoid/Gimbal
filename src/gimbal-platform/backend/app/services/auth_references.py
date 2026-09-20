"""凭证引用反查(配套方案 §1)— 四类引用,读时计算,不建反向索引。

引用语义(名字引用,运行时按**执行者本人**池解析 — 删我的凭证真正
弄坏的只有「以我身份运行」的那些引用,快照类则根本不依赖池):

* ``template`` — steps 里的 ``${auth.<alias>.*}`` 模板。扫描单一实现
  复用 ``auth_ref_scan.scan_auth_aliases``(注入清单同源,spec §5
  「场景内容是单一事实源」);
* ``scheme`` — ``composer_run_schemes.payload.serviceBindings[*].authAlias``
  (方案启动的 run 显式并入注入清单,run_dispatcher §5);
* ``alias`` — ``service_aliases.credential_alias``(共享绑定,查表);
* ``snapshot`` — ``definition.config.users`` 的同名键(快照自足,
  非运行依赖 — 卫生信号:哪些场景揣着旧密码副本)。

删除拦截口径(方案 §1.4.3/§1.5 拍板):**硬 409 只对本人场景的
template/scheme 引用**(它们会在下次运行时真正失效);别名绑定与
同名他场景只在面板提示 — 名字命中 ≠ 对象引用,别人解析的是各自的
同名凭证,阻断过度。

可见性(§1.4):计数照给,场景名按 ``can_read_scenario`` 过滤
(admin 全量 / public / owner),剩余计为 hidden — 只给数不泄露标题。
实时扫是 O(场景数 × payload) 的全表扫描:内部平台量级可接受,
面板点开才算;扛不住的那天扩 scenario_endpoint_refs 写路径,不另起表。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_run_scheme import ComposerRunScheme
from ..models.composer_scenario import ComposerScenario
from ..models.service_alias import ServiceAlias
from ..routers._ownership import can_read_scenario
from .auth_ref_scan import scan_auth_aliases
from .scenario_store import definition_from_payload

KIND_TEMPLATE = "template"
KIND_SCHEME = "scheme"
KIND_SNAPSHOT = "snapshot"

# 面板列表行的「N 场景」计数口径:模板 ∪ 方案绑定(真依赖),
# 快照不进计数、只在面板里按 kind 展示。
COUNTED_KINDS = frozenset({KIND_TEMPLATE, KIND_SCHEME})


@dataclass
class ScenarioRef:
    scenario_id: str
    owner_id: int
    visibility: str
    name: str
    kinds: set[str] = field(default_factory=set)


async def _scan_scenario_refs(db: AsyncSession) -> dict[str, list[ScenarioRef]]:
    """全场景一遍扫 → alias → 引用记录。所有调用方共享同一次扫描。

    config.users 的键集合就是快照引用面(键名 = 凭证别名);
    serviceBindings 是 dict[service → {authAlias, url}],取 values。
    """
    scenarios = (await db.execute(select(ComposerScenario))).scalars().all()
    scheme_rows = (await db.execute(select(ComposerRunScheme))).scalars().all()
    schemes_by_sid: dict[str, list[ComposerRunScheme]] = {}
    for sr in scheme_rows:
        schemes_by_sid.setdefault(sr.scenario_id, []).append(sr)

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

        scheme_aliases: list[str] = []
        for sr in schemes_by_sid.get(row.scenario_id, []):
            bindings = (sr.payload or {}).get("serviceBindings")
            if not isinstance(bindings, dict):
                continue
            for b in bindings.values():
                if isinstance(b, dict) and b.get("authAlias"):
                    scheme_aliases.append(str(b["authAlias"]))

        snapshot_aliases: list[str] = []
        users = defn.get("config")
        users = users.get("users") if isinstance(users, dict) else None
        if isinstance(users, dict):
            snapshot_aliases = [str(k) for k in users]

        for kind, aliases in ((KIND_TEMPLATE, template_aliases),
                              (KIND_SCHEME, scheme_aliases),
                              (KIND_SNAPSHOT, snapshot_aliases)):
            for a in aliases:
                ref = per_scenario.get((a, row.scenario_id))
                if ref is None:
                    ref = ScenarioRef(
                        scenario_id=row.scenario_id,
                        owner_id=row.owner_id,
                        visibility=row.visibility or "private",
                        name=name,
                    )
                    per_scenario[(a, row.scenario_id)] = ref
                    by_alias.setdefault(a, []).append(ref)
                ref.kinds.add(kind)
    return by_alias


async def alias_rows_for(db: AsyncSession, alias: str) -> list[ServiceAlias]:
    return (await db.execute(
        select(ServiceAlias).where(ServiceAlias.credential_alias == alias)
        .order_by(ServiceAlias.alias_name)
    )).scalars().all()


async def references(
    db: AsyncSession, *, user, alias: str
) -> dict:
    """反查面板数据:别名绑定行 + 场景引用(可见名 + 不可见计数)。"""
    by_alias = await _scan_scenario_refs(db)
    hits = by_alias.get(alias, [])
    visible = [r for r in hits
               if can_read_scenario(user, owner_id=r.owner_id,
                                    visibility=r.visibility)]
    alias_rows = await alias_rows_for(db, alias)
    return {
        "alias_refs": [
            {"alias_name": a.alias_name, "base_service": a.base_service,
             "group_tag": a.group_tag}
            for a in alias_rows
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


async def blocking_refs(db: AsyncSession, *, user, alias: str) -> list[str]:
    """删除拦截(窄口径):本人场景的 template/scheme 引用 — 删除会让
    这些场景下次运行真正失效。快照/别名绑定/他人场景不阻断。"""
    by_alias = await _scan_scenario_refs(db)
    return sorted(
        r.scenario_id for r in by_alias.get(alias, [])
        if r.owner_id == user.id and (r.kinds & COUNTED_KINDS)
    )


async def counts(db: AsyncSession) -> dict[str, dict[str, int]]:
    """列表页双计数(一次扫描服务所有行):``N 别名 / N 场景``。
    场景计数 = 模板 ∪ 方案绑定去重场景数(快照不进计数)。"""
    by_alias = await _scan_scenario_refs(db)
    out: dict[str, dict[str, int]] = {}
    alias_rows = (await db.execute(select(ServiceAlias))).scalars().all()
    for a in alias_rows:
        if a.credential_alias:
            out.setdefault(a.credential_alias, {})["alias_count"] = \
                out.get(a.credential_alias, {}).get("alias_count", 0) + 1
    for alias, refs in by_alias.items():
        n = len({r.scenario_id for r in refs if r.kinds & COUNTED_KINDS})
        out.setdefault(alias, {})["scenario_count"] = n
    return out
