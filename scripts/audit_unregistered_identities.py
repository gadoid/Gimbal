"""决策 1「引用即登记」存量分布审计(阶段 0;identity-registry §6.1)。

只读连接平台 PG,不写任何表。遍历场景 definition + 运行方案绑定,用
**单源提取器**(``service_aliases.exec_auth_aliases_of_definition``,与
保存/导入闸同一实现)提取身份引用集,diff ``service_identities``
注册表,输出未登记引用分布:

* 多少场景 / 多少方案带未登记引用;
* 未登记条目名分布(按出现场景数排序,附场景示例);
* 受影响场景按 ``meta.system`` 分组;
* 方案绑定值(换用目标)未登记清单(写面闸 validate_binding_aliases
  在生产常开前的历史存量)。

**这个数字决定 enforce 时点**:未登记引用量大则长期 audit + 白名单
兜底,enforce 缓行;量小则阶段 3 清账向导直接收口(§9 开放问题 1)。

用法::

    python scripts/audit_unregistered_identities.py [--json OUT]

连接复用后端 ``app.core.db.SessionLocal``(``backend/.env`` 的
DATABASE_URL);只做 SELECT,不落任何变更。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.models.composer_run_scheme import ComposerRunScheme  # noqa: E402
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.models.service_identity import ServiceIdentity  # noqa: E402
from app.services.scenario_store import definition_from_payload  # noqa: E402
from app.services.service_aliases import (  # noqa: E402
    effective_alias, exec_auth_aliases_of_definition)


async def _registry(session) -> dict[str, str]:
    rows = (await session.execute(
        select(ServiceIdentity.alias_name,
               ServiceIdentity.base_service))).all()
    return {name: base for name, base in rows}


def _systems_of(definition: dict) -> list[str]:
    meta = (definition or {}).get("meta") or {}
    val = meta.get("system")
    if isinstance(val, list):
        return [str(s) for s in val]
    if isinstance(val, str) and val:
        return [val]
    return []


async def main(json_out: Path | None) -> int:
    async with SessionLocal() as session:
        registry = await _registry(session)

        # ── 场景:定义侧引用(单源提取器,与保存/导入闸同口径)──────
        by_name: Counter = Counter()          # 未登记名 → 出现场景数
        by_system: Counter = Counter()        # meta.system → 受影响场景数
        per_scenario: dict[str, dict] = {}
        scen_rows = (await session.execute(
            select(ComposerScenario.scenario_id,
                       ComposerScenario.owner_name,
                       ComposerScenario.project_id,
                       ComposerScenario.payload))).all()
        for sid, owner, project_id, payload in scen_rows:
            definition = definition_from_payload(payload)
            if not definition:
                continue
            names = await exec_auth_aliases_of_definition(session, definition)
            unreg = sorted(set(names) - set(registry))
            if not unreg:
                continue
            for n in unreg:
                by_name[n] += 1
            systems = _systems_of(definition) or ["(无 meta.system)"]
            for s in systems:
                by_system[s] += 1
            per_scenario[sid] = {
                "owner": owner, "projectId": project_id,
                "systems": systems, "unregistered": unreg,
            }

        # ── 方案:绑定换用目标(写面闸的历史存量面)────────────────
        scheme_hits: dict[str, dict] = {}
        scheme_rows = (await session.execute(
            select(ComposerRunScheme.scheme_id,
                       ComposerRunScheme.scenario_id,
                       ComposerRunScheme.name,
                       ComposerRunScheme.payload))).all()
        for scheme_id, scenario_id, name, payload in scheme_rows:
            bindings = (payload or {}).get("serviceBindings")
            if not isinstance(bindings, dict):
                bindings = (payload or {}).get("service_bindings")
            targets = {
                svc: effective_alias(svc, bindings)
                for svc in (bindings or {})
            }
            unreg = sorted({a for a in targets.values()
                            if a not in registry})
            if not unreg:
                continue
            scheme_hits[scheme_id] = {
                "scenarioId": scenario_id, "name": name,
                "unregisteredTargets": unreg,
            }

    # ── 汇总(数字即 enforce 时点的决策依据)──────────────────────
    print("=" * 64)
    print("决策 1 引用即登记 —— 未登记引用存量分布(阶段 0 审计)")
    print("=" * 64)
    print(f"注册表条目总数          : {len(registry)}")
    print(f"场景总数(遍历)        : {len(scen_rows)}")
    print(f"带未登记引用的场景数    : {len(per_scenario)}")
    print(f"未登记条目名(distinct) : {len(by_name)}")
    print(f"引用总出现次数          : {sum(by_name.values())}")
    print(f"运行方案总数(遍历)    : {len(scheme_rows)}")
    print(f"绑定目标未登记的方案数  : {len(scheme_hits)}")
    print()
    if by_name:
        print("── 未登记名分布(按出现场景数降序)──")
        for name, cnt in by_name.most_common():
            print(f"  {name:<40} {cnt} 场景")
        print()
        print("── 受影响场景按 meta.system 分组 ──")
        for sysname, cnt in by_system.most_common():
            print(f"  {sysname:<40} {cnt}")
        print()
        print("── 场景清单(前 40,全量见 --json)──")
        for sid, info in list(per_scenario.items())[:40]:
            print(f"  {sid}  owner={info['owner']}  "
                  f"unreg={','.join(info['unregistered'])}")
        if len(per_scenario) > 40:
            print(f"  …(共 {len(per_scenario)} 个)")
    else:
        print("✅ 无未登记引用 —— 注册表口径下 enforce 可直接切换。")
    if scheme_hits:
        print()
        print("── 方案绑定目标未登记(前 20)──")
        for scheme_id, info in list(scheme_hits.items())[:20]:
            print(f"  {scheme_id}  scenario={info['scenarioId']}  "
                  f"targets={','.join(info['unregisteredTargets'])}")

    if json_out is not None:
        payload_out = {
            "registrySize": len(registry),
            "scenarioTotal": len(scen_rows),
            "scenariosWithUnregistered": len(per_scenario),
            "distinctUnregisteredNames": len(by_name),
            "referenceOccurrences": sum(by_name.values()),
            "nameDistribution": dict(by_name.most_common()),
            "bySystem": dict(by_system.most_common()),
            "perScenario": per_scenario,
            "schemesWithUnregisteredTargets": scheme_hits,
        }
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(payload_out, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n明细已写入 {json_out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None,
                    help="全量明细输出路径(缺省只打印汇总)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.json)))
