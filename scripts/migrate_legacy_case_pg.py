"""批次 F 存量 case 的 PG 侧迁移驱动(评审 M5 入库)。

2026-10-08 对远端 PG(192.168.22.106)执行过一次:6 个场景共 176 处
旧 scratch 伪路径($.response_status/$.response_body.* → $.call.*),
执行器 09c1779 的提交信息提到的迁移即由本脚本完成。核心转换复用
scripts/migrate_legacy_case.py 的 migrate_payload(幂等、边界安全);
本脚本只负责 PG 读写、kind 补齐与备份。

迁移前 payload 备份(含 order_dispatch 改绑前的另一份)落在**执行机
仓库根**(不入库,含场景业务数据):
    legacy-path-migration-backup.json      ← 本脚本的备份
    order_dispatch-rebind-backup.json      ← 同日接口改绑的备份

用法:
    python scripts/migrate_legacy_case_pg.py --db "$GIMBAL_DB_URL" [--dry-run]

--dry-run 只打印将迁移的场景与变更数,不写库。
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "migrate_legacy_case", _REPO / "scripts" / "migrate_legacy_case.py")
mig = importlib.util.module_from_spec(_spec)
sys.modules["migrate_legacy_case"] = mig
_spec.loader.exec_module(mig)

import asyncpg  # noqa: E402


async def main(db_url: str, *, dry_run: bool) -> int:
    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch("SELECT scenario_id, payload FROM composer_scenarios")
    backup, migrated = {}, 0
    for sid, payload in rows:
        d = json.loads(payload) if isinstance(payload, str) else payload
        definition = d.get("definition") or {}
        had_kind = "kind" in definition          # plate 校验必填,UI 不采集
        definition.setdefault("kind", "scenario")
        out, res = mig.migrate_payload(definition)
        if not had_kind:
            out.pop("kind", None)
        backup[sid] = d
        if res.changes:
            migrated += 1
            print(f"{'would migrate' if dry_run else 'migrated'} "
                  f"{sid}: {len(res.changes)} 处 warnings={res.warnings or '无'}")
            if not dry_run:
                d["definition"] = out
                await conn.execute(
                    "UPDATE composer_scenarios SET payload=$1::jsonb "
                    "WHERE scenario_id=$2",
                    json.dumps(d, ensure_ascii=False), sid)
    if not dry_run and migrated:
        (_REPO / "legacy-path-migration-backup.json").write_text(
            json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"备份 → {_REPO / 'legacy-path-migration-backup.json'}")
    print(f"共 {'would migrate' if dry_run else 'migrated'} {migrated} 个场景")
    await conn.close()
    return 0


if __name__ == "__main__":
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("GIMBAL_DB_URL") or "")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.db:
        print("error: 缺少连接串 — --db 或环境变量 GIMBAL_DB_URL", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(args.db, dry_run=args.dry_run)))
