#!/usr/bin/env python
"""增量升级门:上一交付点 schema → head → 模型比对。

初版教训(2026-10-15 用户实测推翻):「干净库跑完整迁移链」测不到增量
路径 —— 0001 baseline 在空库上执行的就是**当前模型**的 create_all,
后续所有迁移的 _has_table/_has_column 守卫全部跳过,与空库门同路径;
把 0024 改回 sa.DateTime() 门照样绿。初版的「负向验证」(链跑完后手工
ALTER 列)只证明了比对器看得见漂移,没证明缺陷迁移真的会执行。

本版:库从**上一交付点的 schema 快照**建起,再用当前检出的迁移链
upgrade 到 head,最后与当前模型比对。快照两种来源:

* 默认:入库的 schema-only 转储 ``scripts/fixtures/schema-snapshot-*.sql``
  (psql 恢复;不执行任何历史代码 —— 2026-10-15 依赖治理下架 passlib/
  python-jose 后,worktree 复跑历史迁移会 ImportError);可直接换成
  生产/dev 库的真实转储,保真度最高;
* ``--from-ref``:git worktree 检出交付点,用其自身代码建库(要求当前
  环境装得起该提交的依赖;排障用)。

两者都免疫「当前模型 create_all」同义反复。**窗口 =
SNAPSHOT_REF 之后的全部迁移,包括对它们的任何返工**。注意合同的口径
是「最终 schema 必须与模型一致」:若后续迁移能把某列治愈到正确形态
(如 0027 之于被改坏的 0024),门绿是**正确**结论(链收敛 = 无漂移);
门要拦的是「窗口内迁移在真实存量库上执行后仍留下与模型不同的形态」。

快照随发版推进(交付后重新转储替换 fixture);长期方案 = 迁移链压平为
冻结静态 DDL baseline(此时本门退化为快照直接比对)。

另:执行面序列类型单列断言(compare_metadata 不比对序列;0028)。

用法(CI,postgres 容器内 gimbal 是超级用户):
  python scripts/check_migration_drift.py \
      --url postgresql://gimbal:gimbal@localhost:5432/gimbal

本地受限环境(gimbal 无建库权限的 dev PG)加 --schema 走独立 schema +
search_path(仅 --from-ref 模式);--keep 保留临时对象排障。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 执行面序列(0028;与 backend/tests/test_empty_db_bootstrap 同表)
EXEC_FACE_SEQUENCES = {
    "executions_id_seq", "execution_events_id_seq", "execution_rows_id_seq",
    "execution_jobs_id_seq", "adaptation_ops_id_seq",
    "adaptation_snapshots_id_seq",
}
BACKEND = ROOT / "src" / "gimbal-platform" / "backend"

# 交付点快照(2026-10-14 结构化日志批 5 收口 = alembic 0023_ext_schema_json;
# 0024+ 全部在窗口内)。发版时推进到此交付提交。
SNAPSHOT_REF = "41a8b5af"
# 默认快照源 = 入库的 schema-only 转储(整体评审 2026-10-15):worktree 复跑
# 历史代码会被已下架的历史依赖卡住(passlib/python-jose,ImportError),
# 转储恢复不执行任何历史代码,且可直接换成生产/dev 库的真实转储(更保真)。
SNAPSHOT_SQL = ROOT / "scripts" / "fixtures" / "schema-snapshot-0023.sql"


def _fail(msg: str) -> None:
    print(f"[chain-gate] FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _to_asyncpg(sync_url: str) -> str:
    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _alembic(cwd: Path, target_async_url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": target_async_url}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=cwd, env=env)
    if r.returncode != 0:
        _fail(f"alembic {' '.join(args)} 失败 @ {cwd}(见上方输出)")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="增量升级门(快照交付点 → head → 模型比对)")
    ap.add_argument("--url", required=True,
                    help="管理连接(psycopg 形式;建库模式须有权建库)")
    ap.add_argument("--scratch", default="gimbal_chain",
                    help="临时库名(默认)或临时 schema 名(--schema)")
    ap.add_argument("--schema", action="store_true",
                    help="schema 模式:无建库权限环境用独立 schema + search_path")
    ap.add_argument("--snapshot-sql", default=str(SNAPSHOT_SQL),
                    help="快照 schema 转储(默认入库 fixture;psql 恢复)")
    ap.add_argument("--from-ref", default=None,
                    help=("改用 worktree 模式:检出该交付点并用其自身代码建库"
                          "(要求当前环境装得起该提交的依赖;排障用)"))
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

    workdir = Path(tempfile.mkdtemp(prefix="chain-snap-"))
    prev = workdir / "prev"
    try:
        if args.from_ref:
            # ① 快照(worktree 模式):检出交付点,cwd 优先让 `import app`
            #    解析到交付点自己的模型(baseline create_all 用旧模型)
            r = subprocess.run(
                ["git", "worktree", "add", "--detach", str(prev),
                 args.from_ref], cwd=ROOT)
            if r.returncode != 0:
                _fail(f"git worktree add {args.from_ref} 失败(提交在本地吗?)")
            _alembic(prev / "src" / "gimbal-platform" / "backend",
                     target_async, "upgrade", "head")
            label = args.from_ref
        else:
            # ① 快照(默认):psql 恢复 schema-only 转储(含 alembic_version)
            if args.schema:
                _fail("--schema 模式不支持转储恢复(转储按 public 限定);"
                      "受限环境请用 --from-ref 或有建库权限的连接")
            psql = shutil.which("psql")
            if not psql:
                _fail("需要 psql 恢复快照转储(apt install postgresql-client)")
            r = subprocess.run(
                [psql, target_sync, "-q", "-v", "ON_ERROR_STOP=1",
                 "-f", args.snapshot_sql],
                stdout=subprocess.DEVNULL)
            if r.returncode != 0:
                _fail(f"快照转储恢复失败: {args.snapshot_sql}")
            label = Path(args.snapshot_sql).name

        # ② 窗口:当前检出的迁移链在快照之上升级到 head —— 快照期之后
        #    的迁移在这里**真实执行**(守卫不再跳过)
        _alembic(BACKEND, target_async, "upgrade", "head")

        # ③ 比对:最终 schema vs 当前模型(白名单外任何差异即红)
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
            # 序列类型(整体评审 2026-10-15 #10):compare_metadata 不比对
            # 序列,ALTER COLUMN 改 bigint 也不会带动 serial 序列 —— 单列
            # 一项断言:执行面序列在增量路径终态必须是 bigint
            seq_rows = c.exec_driver_sql(
                "select sequencename, data_type from pg_sequences "
                "where schemaname = current_schema()").fetchall()
        eng.dispose()
        seq_bad = sorted(
            f"{name}={dtype}" for name, dtype in seq_rows
            if name in EXEC_FACE_SEQUENCES and dtype != "bigint")

        def _whitelisted(d) -> bool:
            # trgm GIN 索引:迁移建、模型不声明 —— 有意差异,非漂移
            return (isinstance(d, tuple) and d
                    and d[0] in ("add_index", "remove_index")
                    and "trgm" in (getattr(d[1], "name", "") or ""))

        kept = [d for d in diffs if _whitelisted(d)]
        bad = [d for d in diffs if not _whitelisted(d)]
        print(f"[chain-gate] 快照 {label} → head:"
              f"差异 {len(diffs)} 项,"
              f"白名单(trgm 索引){len(kept)} 项,拦截 {len(bad)} 项")
        for d in bad:
            print(f"  DRIFT: {d}")
        for item in seq_bad:
            print(f"  SEQUENCE: {item}(应为 bigint)")
        if seq_bad:
            _fail(f"执行面序列非 bigint {len(seq_bad)} 项 —— 迁移须同时 "
                  "ALTER SEQUENCE ... AS bigint")
        if bad:
            _fail(f"增量路径终态与模型漂移 {len(bad)} 项 —— "
                  f"窗口迁移(快照 {label} 之后)与模型必须同改")
        return 0
    finally:
        if args.from_ref:
            subprocess.run(["git", "worktree", "remove", "--force", str(prev)],
                           cwd=ROOT, capture_output=True)
        shutil.rmtree(workdir, ignore_errors=True)
        if not args.keep:
            conn = psycopg.connect(args.url, autocommit=True)
            try:
                with conn.cursor() as cur:
                    cur.execute(drop_sql)
            finally:
                conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
