"""场景存储形态迁移(Release 6.2):锚点步骤 call 的 binding 派生字段出存储。

protocol/method/path/timeout 由 plate /convert 按 meta.plate 投影提供,
存储出现即被重投影拒收(binding_field_in_storage)—— 钉了修订的存量
场景执行全部报 plate_rejected。本脚本把 composer_scenarios.payload 里
锚点步骤 call 的这四个字段剥掉(剥离逻辑与保存侧
scenario_store.strip_binding_fields 同一份实现);无锚点的手写原始
调用不受影响。幂等:已剥离的行不再改动。

用法:
  python scripts/migrate_strip_binding_fields.py            # 演练
  python scripts/migrate_strip_binding_fields.py --apply    # 落库
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(BACKEND))


async def main(apply: bool) -> int:
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.services.scenario_store import strip_binding_fields_payload
    from sqlalchemy import select

    await db_module.init_db()
    changes: list[dict] = []
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ComposerScenario))).scalars().all()
        for row in rows:
            payload = row.payload or {}
            stripped = strip_binding_fields_payload(dict(payload))
            if stripped == payload:
                continue          # 干净行(或无锚点步骤)
            old_steps = (payload.get("definition") or {}).get("steps") or []
            new_steps = (stripped.get("definition") or {}).get("steps") or []
            fields_by_step: dict[int, list[str]] = {}
            for i in range(min(len(old_steps), len(new_steps))):
                old_call = old_steps[i].get("call") or {}
                new_call = new_steps[i].get("call") or {}
                removed = sorted(set(old_call) - set(new_call))
                if removed:
                    fields_by_step[i] = removed
            changes.append({
                "scenario_id": row.scenario_id,
                "steps": fields_by_step,
            })
            if apply:
                row.payload = stripped
        if apply:
            await s.commit()
    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "scenarios": len(changes), "changes": changes},
        ensure_ascii=False, indent=2))
    await db_module.engine.dispose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
