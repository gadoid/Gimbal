"""存量场景重锚定回填(2026-10-15 #323):无锚点可执行形态 → 锚定存储形态。

#323:导出产物(引擎形态,endpoint 被 reproject 剥离)经导入落库后步骤无
锚点,dispatch 的 carry 降级门控把服务绑定全表灌进每个请求体(orderPage
被灌 customer_id → fin ES 400 → extract None)。导入链已修(precheck/land
重锚定);本脚本回填**修复前已落库**的同类行:反查回填 endpoint
(services/endpoint_anchoring.reanchor_import_definition 同一实现)+
strip_binding_fields 还原存储形态。幂等:已锚定/无派生字段的行不再改动。

纪律(对齐 migrate_strip_binding_fields / migrate_legacy_case_pg B2):
- 备份 = 深拷贝,**提交事务之前**落盘到仓库外 ``../migration-backups/``
  (带时间戳,拒绝覆盖;落盘失败 → 事务不提交,库不动);
- 每行先经 plate convert 复验(存储形态被拒 = 不写该行);
- 单事务,中途失败整体回滚;默认 dry-run,--apply 才动库;
- 锚定与否只看 reason(is_anchored)—— not_in_revision 报告条目也带
  候选 endpoint,按 endpoint 判会把漂移步骤误当已锚。

用法:
  python scripts/backfill_import_anchors.py            # 演练
  python scripts/backfill_import_anchors.py --apply    # 落库
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(BACKEND))


async def main(apply: bool) -> int:
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.services import plate_client
    from app.services.endpoint_anchoring import (
        is_anchored, reanchor_import_definition)
    from app.services.scenario_store import strip_binding_fields
    from sqlalchemy import select

    await db_module.init_db()
    changed: list[dict] = []
    backups: dict[str, dict] = {}
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ComposerScenario))).scalars().all()
        for row in rows:
            payload = row.payload or {}
            definition = payload.get("definition")
            if not isinstance(definition, dict):
                continue
            steps = definition.get("steps")
            if not isinstance(steps, list):
                continue
            pending = [
                i for i, st in enumerate(steps)
                if isinstance(st, dict) and not st.get("endpoint")
                and isinstance(st.get("call"), dict)
                and isinstance(st["call"].get("method"), str)
                and st["call"]["method"]
                and isinstance(st["call"].get("path"), str)
                and st["call"]["path"]]
            if not pending:
                continue
            anchored, report = await reanchor_import_definition(definition)
            if not any(is_anchored(r) for r in report):
                print(f"[skip] {row.scenario_id}: 反查零命中 "
                      f"(待锚 {len(pending)},报告 {report})", flush=True)
                continue
            stored = strip_binding_fields(anchored)
            try:
                await plate_client.convert(stored)
            except plate_client.PlateRejectedError as e:
                print(f"[skip] {row.scenario_id}: 存储形态 convert 被拒 "
                      f"—— 不写: {e}", flush=True)
                continue
            changed.append({
                "scenario_id": row.scenario_id,
                "anchored": [r for r in report if is_anchored(r)],
                "unresolved": [r for r in report if not is_anchored(r)],
            })
            backups[row.scenario_id] = copy.deepcopy(payload)
            if apply:
                row.payload = {**payload, "definition": stored}

        # 备份先行(2026-10-15 评审:先备份后提交 —— 落盘失败则事务
        # 不提交,库保持原样);仓库外,与 migration-backups 其余备份同址
        if apply and changed:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup_dir = _REPO.parent / "migration-backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"import-anchors-backfill-{stamp}.json"
            if backup_path.exists():
                raise SystemExit(f"备份文件已存在,拒绝覆盖: {backup_path}")
            backup_path.write_text(
                json.dumps(backups, ensure_ascii=False, indent=1),
                encoding="utf-8")
            print(f"备份已落盘: {backup_path}")

        if apply:
            await s.commit()

    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "scenarios": len(changed), "changes": changed},
        ensure_ascii=False, indent=2))
    await db_module.engine.dispose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
