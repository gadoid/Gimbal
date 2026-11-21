"""服务引用注册化(架构终态)—— authored URL / 未注册服务键存量审计。

只读连接平台 PG,不写任何表。场景定义的 ``config.services``
(``{服务键: baseUrl}`` authored 声明,地址链第 ② 层)在终态架构中
退役:场景 = 纯引用容器,地址事实全部外置到部署表(③ 层,按执行
标签解析)。本脚本出迁移决策数字:

* 多少场景带 authored URL(② 层活跃面)、多少键、distinct 键名;
* 未注册键分布(键 ∉ 主档 ``services.name`` ∪ 条目表
  ``service_identities.alias_name`` —— 终态闸的判定域);
* 同键多值冲突面(清账时该键的 URL 落部署表会撞;不同场景声明了
  不同地址 → 需人工裁决,脚本只报名不报值差异细节);
* 各场景的标签链环境(resolve_execution_tag 同口径)—— 清账时
  authored URL 落 ``deployments[(base, env)]`` 的目标环境。

用法::

    python scripts/audit_authored_services.py [--json OUT]
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
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.service_identity import ServiceIdentity  # noqa: E402
from app.services.env_chain import resolve_execution_tag  # noqa: E402
from app.services.scenario_store import definition_from_payload  # noqa: E402


def _authored(definition: dict) -> dict[str, str]:
    """非空字符串值的声明(空/全空白视同缺 —— 与 _usable_declared_url
    同口径,审计面只数 ② 层真正活跃的行)。"""
    svc = (definition or {}).get("config") or {}
    svc = svc.get("services") if isinstance(svc.get("services"), dict) else {}
    return {str(k): str(v) for k, v in (svc or {}).items()
            if isinstance(v, str) and v.strip()}


async def main(json_out: Path | None) -> int:
    async with SessionLocal() as session:
        master = set((await session.execute(
            select(Service.name))).scalars())
        entries = set((await session.execute(
            select(ServiceIdentity.alias_name))).scalars())
        known = master | entries

        rows = (await session.execute(
            select(ComposerScenario.scenario_id,
                   ComposerScenario.name,
                   ComposerScenario.owner_name,
                   ComposerScenario.project_id,
                   ComposerScenario.payload))).all()

        by_key_urls: dict[str, set[str]] = {}
        by_key_scenarios: dict[str, set[str]] = {}
        unreg_counter: Counter = Counter()
        per_scenario: dict[str, dict] = {}
        with_url = 0
        for sid, name, owner, project_id, payload in rows:
            authored = _authored(definition_from_payload(payload))
            if not authored:
                continue
            with_url += 1
            unreg = sorted(set(authored) - known)
            for n in unreg:
                unreg_counter[n] += 1
            for k, url in authored.items():
                by_key_urls.setdefault(k, set()).add(url.strip())
                by_key_scenarios.setdefault(k, set()).add(sid)
            per_scenario[sid] = {
                "name": name or "", "owner": owner or "",
                "projectId": project_id,
                "keys": sorted(authored),
                "unregistered": unreg,
                "urls": {k: v.strip() for k, v in authored.items()},
            }

        # 标签链环境(清账落表目标;只对带 URL 场景算)
        # (按场景条目解析标签 —— 与执行链同源)
        env_of: dict[str, str] = {}
        from app.services.service_aliases import exec_auth_aliases_of_definition
        scen_by_id = {r[0]: r[4] for r in rows}
        for sid in per_scenario:
            names = await exec_auth_aliases_of_definition(
                session, definition_from_payload(scen_by_id[sid]))
            tag = await resolve_execution_tag(session, identity_names=names)
            env_of[sid] = (f"#{tag.env_id}({tag.source})" if tag.env_id
                           else "(无环境)")

        conflicts = sorted(k for k, urls in by_key_urls.items()
                           if len(urls) > 1)

    print("=" * 64)
    print("服务引用注册化 —— authored URL / 未注册键存量(架构终态审计)")
    print("=" * 64)
    print(f"场景总数(遍历)            : {len(rows)}")
    print(f"带 authored URL 的场景数    : {with_url}")
    print(f"authored 键(distinct)      : {len(by_key_urls)}")
    print(f"未注册键(distinct)         : {len(unreg_counter)}"
          + (f" → {dict(unreg_counter)}" if unreg_counter else ""))
    print(f"同键多值冲突键数            : {len(conflicts)}"
          + (f" → {conflicts}" if conflicts else ""))
    print("── 键分布(按键值种类数降序,前 20)──")
    for k in sorted(by_key_urls, key=lambda k: -len(by_key_urls[k]))[:20]:
        print(f"  {k:<40} {len(by_key_scenarios[k])} 场景"
              f" / {len(by_key_urls[k])} 种值")
    print("── 场景清单(前 20;含清账目标环境)──")
    for sid, info in list(per_scenario.items())[:20]:
        print(f"  {sid}  owner={info['owner']}  env={env_of.get(sid)}"
              f"  keys={info['keys']}  unreg={info['unregistered']}")

    if json_out:
        payload = {
            "scenariosTotal": len(rows), "withAuthoredUrl": with_url,
            "distinctKeys": sorted(by_key_urls),
            "unregistered": dict(unreg_counter),
            "conflictKeys": conflicts,
            "perScenario": per_scenario, "envOf": env_of,
        }
        json_out.write_text(json.dumps(payload, ensure_ascii=False,
                                       indent=2), encoding="utf-8")
        print(f"(全量 JSON → {json_out})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.json)))
