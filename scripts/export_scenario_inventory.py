"""场景清单导出保护 CLI(UPC M5 前置件;台账 §5:
「先场景清单导出保护,再重建 dev 库」—— 开发库重建准入后的第一步)。

用法::

    python scripts/export_scenario_inventory.py --out-dir <目录> \
        [--db-url <postgresql+asyncpg://...>] [--verify]

* ``--db-url`` 缺省用后端配置 DATABASE_URL(指向开发库时由操作者
  显式传入 —— 本脚本只读,不写目标库);
* ``--verify`` 对已导出目录跑对照校验(恢复后对账:缺包/摘要漂移)。

对目标库零写入(服务层只读纪律,见 app/services/scenario_inventory.py
模块 docstring)。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))


async def _main(args: argparse.Namespace) -> int:
    if args.db_url:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        engine = create_async_engine(args.db_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        session_cm = maker()
    else:
        from app.core.db import SessionLocal  # noqa: E402

        session_cm = SessionLocal()
    out = Path(args.out_dir)
    try:
        if args.verify:
            from app.services.scenario_inventory import verify_inventory
            report = await verify_inventory(out)
            print(json.dumps(report, ensure_ascii=False, indent=1))
            return 0 if report["ok"] else 1
        from app.services.scenario_inventory import export_inventory
        async with session_cm as db:
            manifest = await export_inventory(db, out)
        print(json.dumps({
            "outDir": str(out),
            "scenarioCount": manifest["scenarioCount"],
            "exportedCount": manifest["exportedCount"],
            "datasetCount": manifest["datasetCount"],
            "schemeCount": manifest["schemeCount"],
        }, ensure_ascii=False, indent=1))
        return 0
    finally:
        if args.db_url:
            await session_cm.close()
            await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True,
                    help="导出目录(manifest.json + bundles/)")
    ap.add_argument("--db-url", default=None,
                    help="目标库连接串(缺省用后端配置;只读)")
    ap.add_argument("--verify", action="store_true",
                    help="对已导出目录跑对照校验(不导出)")
    args = ap.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
