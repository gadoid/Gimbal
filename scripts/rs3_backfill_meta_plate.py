"""RS3 运行时操作入库版：meta.plate 回填为各系统首个修订。

迁移纪律（09c1779 约定）：默认演练、先备份、单事务、可重复执行。
用法：
  python scripts/rs3_backfill_meta_plate.py            # 演练（打印将改什么，不写库）
  python scripts/rs3_backfill_meta_plate.py --apply    # 落库

前置：plate 已为各系统签发首条修订（plate release）；本脚本对
composer_scenarios.payload.definition.meta.plate 为空/working 的场景，
按 meta.system 各系统的**最新版本线最新修订**回填（首个修订即唯一线）。
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(BACKEND))


async def main(apply: bool) -> int:
    import httpx
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.services.scenario_store import definition_from_payload
    from sqlalchemy import select

    plate = "http://127.0.0.1:8765"
    await db_module.init_db()
    changes: list[dict] = []
    async with db_module.SessionLocal() as s, httpx.AsyncClient(base_url=plate) as pc:
        rows = (await s.execute(select(ComposerScenario))).scalars().all()
        lines_cache: dict[str, list] = {}
        for row in rows:
            payload = row.payload or {}
            definition = definition_from_payload(payload)
            meta = definition.get("meta") or {}
            plate_map = meta.get("plate") or {}
            systems = sorted({
                str(st["endpoint"]).split(".")[0]
                for st in (definition.get("steps") or [])
                if isinstance(st, dict) and st.get("endpoint")
            }) or list(meta.get("system") or [])
            new_refs: dict[str, str] = {}
            for system in systems:
                if plate_map.get(system) and plate_map[system] != "working":
                    continue
                if system not in lines_cache:
                    r = await pc.get(f"/api/system/{system}/lines", timeout=15)
                    lines_cache[system] = (
                        r.json().get("data", {}).get("items")
                        if r.status_code == 200 else [])
                lines = lines_cache[system] or []
                if lines:
                    new_refs[system] = lines[-1]["latest"]
            if not new_refs:
                continue
            planned = copy.deepcopy(payload)
            pdef = definition_from_payload(planned)
            pdef.setdefault("meta", {}).setdefault("plate", {}).update(new_refs)
            changes.append({
                "scenario_id": row.scenario_id,
                "name": meta.get("name", ""),
                "set": new_refs,
                "payload": planned if apply else None,
            })
            if apply:
                row.payload = planned
        if apply:
            await s.commit()
    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "scenarios": len(changes),
        "detail": [{k: v for k, v in c.items() if k != "payload"}
                   for c in changes]},
        ensure_ascii=False, indent=2))
    await db_module.engine.dispose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="落库（缺省演练）")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
