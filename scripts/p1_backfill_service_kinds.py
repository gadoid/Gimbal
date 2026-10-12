"""P1.0/W3:service_aliases.kind 三态回填与审计。

规则(缺口收口计划 P1.0):
- ``kind='external'`` 行不动(人工登记的第三方,目录说了不算);
- 其余行按 plate 服务目录裁决:``base_service`` 在目录内 → ``plate``;
  不在 → ``external``(存量行按登记强约束应在目录内;不在 = 目录
  漂移或旁路写入,--apply 按规则落 external 并打印明细供复核)。

迁移纪律(09c1779 约定):默认演练、先备份、单事务、可重复执行。
用法:
  python scripts/p1_backfill_service_kinds.py            # 演练(打印,不写库)
  python scripts/p1_backfill_service_kinds.py --apply    # 落库
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(BACKEND))


async def main(apply: bool) -> int:
    env = dict(re.findall(
        r"([A-Z_]+)=(.*)", (BACKEND / ".env").read_text(encoding="utf-8")))
    import httpx
    from app.core import db as db_module
    from app.models.service_alias import ServiceAlias
    from sqlalchemy import select

    plate_base = env.get("PLATE_BASE_URL", "http://127.0.0.1:8765")
    try:
        resp = await httpx.AsyncClient().get(
            f"{plate_base.rstrip('/')}/api/service", timeout=15)
        envelope = resp.json()
        catalog = {it["name"] for it in envelope.get("data", {}).get("items", [])
                   if isinstance(it, dict) and it.get("name")}
    except Exception as e:  # noqa: BLE001 — 目录不可得即停,不做盲回填
        print(f"BLOCKED: plate 服务目录不可得({e});恢复后重试", file=sys.stderr)
        return 2

    await db_module.init_db()
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ServiceAlias))).scalars().all()
        plan: list[tuple[str, str, str]] = []   # (alias, 现 kind, 目标 kind)
        for r in rows:
            if (r.kind or "plate") == "external":
                continue
            target = "plate" if r.base_service in catalog else "external"
            if target != (r.kind or "plate"):
                plan.append((r.alias_name, r.kind or "plate", target))

        print(f"共 {len(rows)} 行;目录内服务 {len(catalog)} 个;"
              f"{'拟改 ' + str(len(plan)) + ' 行' if plan else '无需变更'}")
        for alias, cur, tgt in plan:
            print(f"  {alias}: {cur} → {tgt}")
        if not plan:
            return 0
        if not apply:
            print("演练模式:加 --apply 落库")
            return 0

        backup = {
            "ts": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "rows": [{"aliasName": r.alias_name, "kind": r.kind or "plate"}
                     for r in rows],
        }
        out = Path(__file__).resolve().parents[1] / "gimbal-tmp" / "p1-kind-backup.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(backup, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"备份 → {out}")

        from sqlalchemy import update as sa_update
        async with s.begin():
            for alias, _, tgt in plan:
                await s.execute(sa_update(ServiceAlias).where(
                    ServiceAlias.alias_name == alias).values(kind=tgt))
        print(f"已应用 {len(plan)} 行(幂等:重跑应报 0 行)")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    raise SystemExit(asyncio.run(main(p.parse_args().apply)))
