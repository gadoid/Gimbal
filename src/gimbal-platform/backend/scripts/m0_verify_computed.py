"""M0-4 一次性验证：生成列 × alembic batch 三案 + PG ETL 直插写法。

对应开发计划 Task M0-4 / 迁移方案 §2.2「交叉验证欠账」+ §3.3「ETL 写法试掉」。
跑完把结论回写开发计划附录 A3。

三案（进两案、出一案）：
  案① 进 — composer 七列：SQLite 上对带数据的表 batch 加 Computed(persisted=True)。
  案② 进 — users.role 单列：同一个「带数据表上加 STORED 生成列」的坑，单列同验
           （它在 M2 关键路径上：回滚安全整个压在 role 零读零写上）。
  案③ 出 — 生成列→普通列翻转（M2.5 权威翻转的后半程）：
           PG 原生 DROP EXPRESSION；SQLite 无等价 DDL，走手写重建
           （CREATE/INSERT SELECT/DROP/RENAME），逐行值相等断言。
PG ETL 写法（同一坑的两侧，只验一侧不算验证完）：
  列清单排除生成列直插 → PG 自算；故意带上生成列 → 记录报错形态。

跑法（backend 目录）：
    python scripts/m0_verify_computed.py
    # 可选 env：PG_DSN（默认本地 compose 库 gimbal/gimbal@127.0.0.1:5432/gimbal）

SQLite 部分全部在 tempfile 临时库上跑，PG 部分用 m0_verify_* 临时表、结束即 DROP。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, Integer, String, Table, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import Computed

PG_DSN = os.environ.get(
    "PG_DSN", "postgresql+psycopg://gimbal:gimbal@127.0.0.1:5432/gimbal"
)

RESULTS: list[tuple[str, bool, str]] = []


def record(case: str, ok: bool, note: str) -> None:
    RESULTS.append((case, ok, note))
    print(f"  [{'PASS' if ok else 'FAIL'}] {case}: {note}")


def _meta(name: str, module: str, author: str, priority: int,
          system: list[str], tags: list[str], description: str = "") -> dict:
    return {
        "definition": {
            "meta": {
                "name": name,
                "module": module,
                "author": author,
                "priority": priority,
                "system": system,
                "tags": tags,
                "description": description,
            },
            "steps": [],
        }
    }


# ───────────────────────── SQLite 生成列表达式（§2.2 方言段）─────────────────────
SQLITE_EXPRS = {
    "name": "json_extract(payload, '$.definition.meta.name')",
    "description": "json_extract(payload, '$.definition.meta.description')",
    "module": "json_extract(payload, '$.definition.meta.module')",
    "author": "json_extract(payload, '$.definition.meta.author')",
    "priority": "CAST(json_extract(payload, '$.definition.meta.priority') AS INTEGER)",
    "system": "json_extract(payload, '$.definition.meta.system')",
    "tags": "json_extract(payload, '$.definition.meta.tags')",
}

SEED = [
    _meta("订单查询", "trade", "alice", 2, ["order-svc"], ["smoke", "p2"], "d1"),
    _meta("委托创建", "trade", "bob", 1, ["order-svc", "acct-svc"], ["regression"]),
    _meta("资金划转", "asset", "carol", 0, ["acct-svc"], []),
]

EXPECTED = [
    ("订单查询", "trade", "alice", 2, ["order-svc"], ["smoke", "p2"]),
    ("委托创建", "trade", "bob", 1, ["order-svc", "acct-svc"], ["regression"]),
    ("资金划转", "asset", "carol", 0, ["acct-svc"], []),
]


def _sqlite_engine(tmpdir: str, name: str):
    return create_engine(f"sqlite:///{os.path.join(tmpdir, name)}", future=True)


def _hidden_flag(engine, table: str, col: str) -> int:
    """PRAGMA table_xinfo: 0=普通 2=VIRTUAL 3=STORED。"""
    with engine.connect() as c:
        rows = c.execute(text(f"PRAGMA table_xinfo({table})")).fetchall()
    for r in rows:
        if r[1] == col:
            return int(r[6])
    return -1


def _batch_add(engine, table: str, columns: list[Column]) -> None:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        with op.batch_alter_table(table) as batch:
            for col in columns:
                batch.add_column(col)
        conn.commit()


# ── 案①：SQLite batch 给带数据的表加 composer 七个 STORED 生成列 ───────────────
def case1(tmpdir: str) -> None:
    print("案① 进/composer 七列（SQLite batch + Computed(persisted=True)）")
    eng = _sqlite_engine(tmpdir, "case1.db")
    try:
        _case1_body(eng)
    finally:
        eng.dispose()  # Windows:不 dispose 会锁住 db 文件,临时目录清不掉


def _case1_body(eng) -> None:
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE composer_scenarios ("
            " id INTEGER PRIMARY KEY,"
            " scenario_id VARCHAR(128) UNIQUE NOT NULL,"
            " payload JSON NOT NULL)"))
        for i, p in enumerate(SEED, 1):
            c.execute(text(
                "INSERT INTO composer_scenarios (id, scenario_id, payload) "
                "VALUES (:i, :sid, :p)"),
                {"i": i, "sid": f"sc-{i}", "p": json.dumps(p, ensure_ascii=False)})

    cols = [
        Column("name", String(64), Computed(SQLITE_EXPRS["name"], persisted=True)),
        Column("description", String, Computed(SQLITE_EXPRS["description"], persisted=True)),
        Column("module", String(64), Computed(SQLITE_EXPRS["module"], persisted=True)),
        Column("author", String(128), Computed(SQLITE_EXPRS["author"], persisted=True)),
        Column("priority", Integer, Computed(SQLITE_EXPRS["priority"], persisted=True)),
        Column("system", JSON, Computed(SQLITE_EXPRS["system"], persisted=True)),
        Column("tags", JSON, Computed(SQLITE_EXPRS["tags"], persisted=True)),
    ]
    try:
        _batch_add(eng, "composer_scenarios", cols)
    except SQLAlchemyError as e:
        record("①batch加七列", False, f"batch 报错: {str(e)[:160]}")
        return

    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT name, module, author, priority, system, tags "
            "FROM composer_scenarios ORDER BY id")).fetchall()
    ok_vals = all(
        (r[0], r[1], r[2], r[3],
         json.loads(r[4]) if isinstance(r[4], str) else r[4],
         json.loads(r[5]) if isinstance(r[5], str) else r[5]) == exp
        for r, exp in zip(rows, EXPECTED)
    )
    record("①生成值=提取函数", ok_vals,
           f"{len(rows)} 行，逐行比对 {'全等' if ok_vals else '不一致'}")
    hidden = {col.name: _hidden_flag(eng, "composer_scenarios", col.name) for col in cols}
    ok_stored = all(v == 3 for v in hidden.values())
    record("①落的是STORED", ok_stored,
           f"table_xinfo hidden: {hidden} (3=STORED, 2=VIRTUAL)")


# ── 案②：users.role 单列同验（布尔 CASE，M2 关键路径）─────────────────────────
def case2(tmpdir: str) -> None:
    print("案② 进/users.role 单列（SQLite batch + CASE WHEN 布尔生成列）")
    eng = _sqlite_engine(tmpdir, "case2.db")
    try:
        _case2_body(eng)
    finally:
        eng.dispose()


def _case2_body(eng) -> None:
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE users ("
            " id INTEGER PRIMARY KEY,"
            " username VARCHAR(64) UNIQUE NOT NULL,"
            " is_admin INTEGER NOT NULL DEFAULT 0)"))
        c.execute(text("INSERT INTO users (id, username, is_admin) VALUES (1, 'root', 1)"))
        c.execute(text("INSERT INTO users (id, username, is_admin) VALUES (2, 'alice', 0)"))

    try:
        _batch_add(eng, "users", [
            Column("role", String(16),
                   Computed("CASE WHEN is_admin = 1 THEN 'admin' ELSE 'member' END",
                            persisted=True)),
        ])
    except SQLAlchemyError as e:
        record("②batch加role", False, f"batch 报错: {str(e)[:160]}")
        return

    with eng.connect() as c:
        rows = c.execute(text("SELECT id, is_admin, role FROM users ORDER BY id")).fetchall()
    ok = [(r[0], r[2]) for r in rows] == [(1, "admin"), (2, "member")]
    record("②is_admin→role映射", ok, f"rows={rows}")
    record("②落的是STORED", _hidden_flag(eng, "users", "role") == 3,
           f"hidden={_hidden_flag(eng, 'users', 'role')}")


# ── 案③：生成列→普通列翻转（出程）──────────────────────────────────────────────
def case3_sqlite(tmpdir: str) -> None:
    print("案③ 出/翻转 — SQLite（手写重建：CREATE/INSERT SELECT/DROP/RENAME）")
    eng = _sqlite_engine(tmpdir, "case3.db")
    try:
        _case3_sqlite_body(eng)
    finally:
        eng.dispose()


def _case3_sqlite_body(eng) -> None:
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE m0_users ("
            " id INTEGER PRIMARY KEY,"
            " username VARCHAR(64) NOT NULL,"
            " is_admin INTEGER NOT NULL DEFAULT 0,"
            " role VARCHAR(16) GENERATED ALWAYS AS "
            "  (CASE WHEN is_admin = 1 THEN 'admin' ELSE 'member' END) STORED)"))
        c.execute(text("INSERT INTO m0_users (id, username, is_admin) VALUES (1, 'root', 1)"))
        c.execute(text("INSERT INTO m0_users (id, username, is_admin) VALUES (2, 'alice', 0)"))

    before = None
    with eng.connect() as c:
        before = c.execute(text("SELECT id, role FROM m0_users ORDER BY id")).fetchall()

    with eng.begin() as c:  # 手写重建（设计文档钦定的 fallback 路径）
        c.execute(text(
            "CREATE TABLE m0_users_new ("
            " id INTEGER PRIMARY KEY,"
            " username VARCHAR(64) NOT NULL,"
            " is_admin INTEGER NOT NULL DEFAULT 0,"
            " role VARCHAR(16) NOT NULL DEFAULT 'member')"))
        c.execute(text(
            "INSERT INTO m0_users_new (id, username, is_admin, role) "
            "SELECT id, username, is_admin, role FROM m0_users"))  # 读 STORED 生成列
        c.execute(text("DROP TABLE m0_users"))
        c.execute(text("ALTER TABLE m0_users_new RENAME TO m0_users"))

    with eng.connect() as c:
        after = c.execute(text("SELECT id, role FROM m0_users ORDER BY id")).fetchall()
    record("③SQLite逐行值相等", [tuple(r) for r in before] == [tuple(r) for r in after],
           f"before={before} after={after}")
    with eng.begin() as c:  # 翻转后必须可写
        c.execute(text("UPDATE m0_users SET role = 'operator' WHERE id = 2"))
    with eng.connect() as c:
        r2 = c.execute(text("SELECT role FROM m0_users WHERE id = 2")).scalar()
    record("③SQLite翻转后可写", r2 == "operator", f"id=2 role={r2}")


def case3_pg() -> None:
    print("案③ 出/翻转 — PG（原生 ALTER COLUMN … DROP EXPRESSION）")
    eng = create_engine(PG_DSN, future=True)
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS m0_users_flip"))
        c.execute(text(
            "CREATE TABLE m0_users_flip ("
            " id INTEGER PRIMARY KEY,"
            " username VARCHAR(64) NOT NULL,"
            " is_admin BOOLEAN NOT NULL DEFAULT false,"
            " role VARCHAR(16) GENERATED ALWAYS AS "
            "  (CASE WHEN is_admin THEN 'admin' ELSE 'member' END) STORED)"))
        c.execute(text("INSERT INTO m0_users_flip (id, username, is_admin) "
                       "VALUES (1, 'root', true), (2, 'alice', false)"))
    with eng.connect() as c:
        before = c.execute(text("SELECT id, role FROM m0_users_flip ORDER BY id")).fetchall()

    with eng.begin() as c:
        c.execute(text("ALTER TABLE m0_users_flip ALTER COLUMN role DROP EXPRESSION"))
    try:
        with eng.begin() as c:
            c.execute(text("UPDATE m0_users_flip SET role = 'operator' WHERE id = 2"))
        writable = True
    except SQLAlchemyError:
        writable = False
    with eng.connect() as c:
        after = c.execute(text("SELECT id, role FROM m0_users_flip ORDER BY id")).fetchall()
    record("③PG DROP EXPRESSION 后可写", writable, f"rows={after}")
    record("③PG 未动行值保持",
           [tuple(r) for r in before][:1] == [tuple(r) for r in after][:1],
           f"id=1 before={before[0]} after={after[0]}")


# ── PG ETL 直插写法（§3.3：排除生成列自算 / 带上生成列的报错形态）────────────────
def pg_etl_write() -> None:
    print("PG ETL 直插写法（排除生成列 / 故意带上的报错形态）")
    eng = create_engine(PG_DSN, future=True)
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS m0_composer"))
        c.execute(text(
            "CREATE TABLE m0_composer ("
            " id INTEGER PRIMARY KEY,"
            " scenario_id VARCHAR(128) UNIQUE NOT NULL,"
            " payload JSONB NOT NULL,"
            " name VARCHAR(64) GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->>'name') STORED,"
            " description TEXT GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->>'description') STORED,"
            " module VARCHAR(64) GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->>'module') STORED,"
            " author VARCHAR(128) GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->>'author') STORED,"
            " priority SMALLINT GENERATED ALWAYS AS "
            "  ((payload->'definition'->'meta'->>'priority')::int) STORED,"
            " system JSONB GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->'system') STORED,"
            " tags JSONB GENERATED ALWAYS AS "
            "  (payload->'definition'->'meta'->'tags') STORED)"))
        for i, p in enumerate(SEED, 1):
            c.execute(text(
                "INSERT INTO m0_composer (id, scenario_id, payload) "
                "VALUES (:i, :sid, CAST(:p AS jsonb))"),
                {"i": i, "sid": f"sc-{i}", "p": json.dumps(p, ensure_ascii=False)})

    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT name, module, author, priority, system, tags "
            "FROM m0_composer ORDER BY id")).fetchall()
    ok = all(
        (r[0], r[1], r[2], r[3],
         json.loads(r[4]) if isinstance(r[4], str) else r[4],
         json.loads(r[5]) if isinstance(r[5], str) else r[5]) == exp
        for r, exp in zip(rows, EXPECTED)
    )
    record("PG排除生成列直插自算", ok, f"{len(rows)} 行逐行比对 {'全等' if ok else '不一致'}")

    err_snippet = ""
    try:
        with eng.begin() as c:
            c.execute(text(
                "INSERT INTO m0_composer (id, scenario_id, payload, name) "
                "VALUES (99, 'sc-bad', CAST(:p AS jsonb), '伪造值')"),
                {"p": json.dumps(SEED[0], ensure_ascii=False)})
    except SQLAlchemyError as e:
        err_snippet = str(getattr(e, "orig", e))[:200]
    record("PG带上生成列按预期拒绝",
           "generated column" in err_snippet or "GENERATED" in err_snippet,
           f"报错形态: {err_snippet[:120]}")


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        case1(tmpdir)
        case2(tmpdir)
        case3_sqlite(tmpdir)
    try:
        case3_pg()
        pg_etl_write()
    finally:
        eng = create_engine(PG_DSN, future=True)
        with eng.begin() as c:
            c.execute(text("DROP TABLE IF EXISTS m0_composer"))
            c.execute(text("DROP TABLE IF EXISTS m0_users_flip"))

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("\n== M0-4 结论 ==")
    for case, ok, note in RESULTS:
        print(f"  {'✓' if ok else '✗'} {case} — {note}")
    print(f"共 {len(RESULTS)} 项，失败 {n_fail} 项")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
