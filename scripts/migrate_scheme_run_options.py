"""RunScheme 执行参数 → RunOptions 形状迁移（M2 §8 / M10）。

旧平铺键 stepTo/nRuns/parallel/logSub/plugins → options 包裹的
step_from/step_to/n_runs/parallel/subscribe（plugins 删除，Q15）。
用法：
  python scripts/migrate_scheme_run_options.py            # 演练
  python scripts/migrate_scheme_run_options.py --apply    # 落库
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
    from app.models.composer_run_scheme import ComposerRunScheme
    from sqlalchemy import select

    await db_module.init_db()
    changes: list[dict] = []
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ComposerRunScheme))).scalars().all()
        for row in rows:
            p = dict(row.payload or {})
            if "options" in p:
                continue          # 已迁移
            opts: dict = {
                "step_from": None,
                "step_to": p.pop("stepTo", None),
                "n_runs": p.pop("nRuns", 1),
                "parallel": p.pop("parallel", 1),
                "subscribe": p.pop("logSub", None),
            }
            p.pop("plugins", None)    # Q15 删除
            p["options"] = opts
            changes.append({
                "scheme_id": row.scheme_id,
                "scenario_id": row.scenario_id,
                "options": opts,
            })
            if apply:
                row.payload = p
        if apply:
            await s.commit()
    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "schemes": len(changes), "changes": changes},
        ensure_ascii=False, indent=2))
    await db_module.engine.dispose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
