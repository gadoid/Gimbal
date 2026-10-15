#!/usr/bin/env python
"""增量升级门:迁移链建库 vs 模型比对(合入评估 §2-2 的防再犯项)。

空库门(tests/test_empty_db_bootstrap)只覆盖 fresh 路径(baseline =
模型 create_all),**增量路径**(存量库逐版本 upgrade 到 head)没有门
—— 0024 用 sa.DateTime() 建出 timestamp without time zone、模型却是
timestamptz 的漂移因此漏网(dev 库实 drift 过,0027 补正)。本脚本在
干净库上走**完整迁移链** 0001→head(而非 create_all),再与模型
compare_metadata 比对 —— 链建出来的 schema 必须与模型一致。

白名单只放 trgm 索引:GIN 表达由迁移创建、模型不声明,是有意的表达
差异;其余任何差异(列类型/缺列/多列/非 trgm 索引)即门红。

用法(CI,postgres 容器内 gimbal 是超级用户):
  python scripts/check_migration_drift.py \
      --url postgresql://gimbal:gimbal@localhost:5432/gimbal

本地受限环境(gimbal 无建库权限的 dev PG)加 --schema 走独立 schema +
search_path:
  python scripts/check_migration_drift.py --schema \
      --url postgresql://gimbal:gimbal@192.168.22.106:5432/gimbal

前置:backend 已 editable 安装(alembic env 与模型导入都依赖);
--keep 保留临时对象供排障。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "src" / "gimbal-platform" / "backend"


def _fail(msg: str) -> None:
    print(f"[chain-gate] FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _to_asyncpg(sync_url: str) -> str:
    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="迁移链建库 vs 模型比对(CI 增量升级门)")
    ap.add_argument("--url", required=True,
                    help="管理连接(psycopg 形式;建库模式须有权建库)")
    ap.add_argument("--scratch", default="gimbal_chain",
                    help="临时库名(默认)或临时 schema 名(--schema)")
    ap.add_argument("--schema", action="store_true",
                    help="schema 模式:无建库权限环境用独立 schema + search_path")
    ap.add_argument("--keep", action="store_true",
                    help="保留临时对象(排障)")
    args = ap.parse_args()

    import psycopg

    base = args.url.split("?")[0]
    if args.schema:
        create_sql = f'CREATE SCHEMA "{args.scratch}"'
        drop_sql = f'DROP SCHEMA IF EXISTS "{args.scratch}" CASCADE'
        target_sync = f"{base}?options=-csearch_path%3D{args.scratch}"
    else:
        db = base.rsplit("/", 1)[-1]
        admin_head = base.rsplit("/", 1)[0]
        create_sql = f'CREATE DATABASE "{args.scratch}"'
        drop_sql = f'DROP DATABASE IF EXISTS "{args.scratch}" WITH (FORCE)'
        target_sync = f"{admin_head}/{args.scratch}"
    target_async = _to_asyncpg(target_sync)

    conn = psycopg.connect(args.url, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(drop_sql)
            cur.execute(create_sql)
    except Exception as e:  # noqa: BLE001 — 建不出来 = 环境问题,报因退出
        _fail(f"临时对象建不出来({'schema' if args.schema else 'database'} "
              f"{args.scratch!r}): {e}")
    finally:
        conn.close()

    try:
        # ① 全链 0001→head(不是 create_all —— 增量路径才是被测对象)
        env = {**os.environ, "DATABASE_URL": target_async}
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini",
             "upgrade", "head"],
            cwd=BACKEND, env=env)
        if r.returncode != 0:
            _fail("迁移链 upgrade head 失败(见上方 alembic 输出)")

        # ② 与模型比对(白名单外任何差异即红)
        os.environ["DATABASE_URL"] = target_async   # app 导入期校验用
        from alembic.autogenerate import compare_metadata
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine

        from app import models  # noqa: F401 — 注册全部表
        from app.core.db import Base

        eng = create_engine(target_sync)
        with eng.connect() as c:
            diffs = compare_metadata(
                MigrationContext.configure(c), Base.metadata)
        eng.dispose()

        def _whitelisted(d) -> bool:
            # trgm GIN 索引:迁移建、模型不声明 —— 有意差异,非漂移
            return (isinstance(d, tuple) and d
                    and d[0] in ("add_index", "remove_index")
                    and "trgm" in (getattr(d[1], "name", "") or ""))

        kept = [d for d in diffs if _whitelisted(d)]
        bad = [d for d in diffs if not _whitelisted(d)]
        print(f"[chain-gate] 差异 {len(diffs)} 项:"
              f"白名单(trgm 索引){len(kept)} 项,拦截 {len(bad)} 项")
        for d in bad:
            print(f"  DRIFT: {d}")
        if bad:
            _fail(f"迁移链建库与模型漂移 {len(bad)} 项 —— 迁移与模型必须同改")
        return 0
    finally:
        if not args.keep:
            conn = psycopg.connect(args.url, autocommit=True)
            try:
                with conn.cursor() as cur:
                    cur.execute(drop_sql)
            finally:
                conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
