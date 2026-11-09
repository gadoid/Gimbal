"""S7.4 share_ref 退役:存量引用一次性转被分享人的私有副本(Q2 裁定)。

逐条调 app/services/share_ref_retire.convert_ref(与 fork 同一复制口径:
跨属主剥内置凭证与敏感列);成功即删 ref 行 → 幂等可重跑;失败行保留
并进报告(空套件/上限等,人工处置后重跑)。随后跑迁移 0049 删表(表
非空即拒绝,防漏跑本命令)。

用法:
  python scripts/retire_share_refs.py            # 演练(列出将转换的引用)
  python scripts/retire_share_refs.py --apply    # 逐条转换落库
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
    from app.models.user import User
    from app.services.share_ref_retire import (
        RefConversionError, convert_ref, list_refs)

    await db_module.init_db()
    converted: list[dict] = []
    failed: list[dict] = []
    async with db_module.SessionLocal() as s:
        refs = await list_refs(s)
        if not apply:
            plan = []
            for r in refs:
                u = await s.get(User, r.grantee_user_id)
                plan.append({
                    "refId": r.id,
                    "grantee": u.username if u else f"#{r.grantee_user_id}",
                    "resource": r.scenario_id or f"suite#{r.suite_id}",
                })
            print(json.dumps({
                "mode": "dry-run", "refs": len(plan), "plan": plan},
                ensure_ascii=False, indent=2))
        else:
            for r in refs:
                try:
                    out = await convert_ref(s, r)
                    converted.append({"refId": r.id, **out})
                    print(f"[ok] ref#{r.id} -> {out['kind']} copy "
                          f"{out['copyId']} (grantee #{out['granteeId']})")
                except RefConversionError as e:
                    failed.append({"refId": r.id, "reason": e.reason})
                    print(f"[FAIL] ref#{r.id}: {e.reason}(行保留,可修后重跑)")
    await db_module.engine.dispose()
    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "converted": len(converted), "failed": len(failed),
        "failures": failed,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="逐条转换落库(默认演练)")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
