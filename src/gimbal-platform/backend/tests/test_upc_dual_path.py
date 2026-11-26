"""§20.4 双初始化路径结构断言(UPC M1,v2.10 §20.4 / AC-23/36)。

同一套结构断言分别运行于:

* **路径 A(交付快照语义)**:空库经 Alembic 迁移链升到 head;
* **路径 B(正式新库初始化)**:``create_all`` + 共享触发器 DDL
  (``ensure_schema_sync`` 同款)+ stamp head。

以 PostgreSQL 系统目录逐属性比较 M1 交付面(projects / project_members
的列、类型、默认值、NULL、主键、FK、CHECK、唯一/部分索引,以及四张表
上的触发器与共享函数体)—— 任何目标结构缺失或定义差异即失败,不以
Alembic revision 相同代替结构一致。M1 只断言已交付结构(§20.4:不要求
尚未实现的 M2 迁移通过),后续阶段新增 DDL 时在同一断言上扩展。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, text

_BACKEND = Path(__file__).resolve().parents[1]

# 单源复用(test_migrations 是链测试的家):造形机制 + temp schema + 配置
from tests.test_migrations import (  # noqa: E402
    _add_legacy_visibility, _cfg, _create_retired_tables, temp_schema,
)

# M2 起交付面扩展到全部对象表 + 组合/方案/成员复合约束(§20.4:
# 每次新增 DDL 更新同一断言套件)
_COMPARE_TABLES = (
    "projects", "project_members",
    "composer_scenarios", "composer_run_schemes",
    "suites", "suite_members", "account_combos",
    "integration_tasks", "report_definitions",
    "scheme_repair_events", "scheme_repair_diagnosis",
    "scenario_asset_imports",
)
_TRIGGER_TABLES = ("projects", "project_members", "users")

# §20.6 复合 FK 取代 0042 同区触发器:suite_member_same_zone 不再
# 在任一路径存在(链路径 0042 挂上、0068 摘除)
_SHARED_FUNCTIONS = (
    "project_member_kind_guard",
    "project_kind_immutable",
    "project_member_admin_invariant",
    "project_admin_invariant",
    "user_active_admin_invariant",
    "user_default_space_invariant",
)


def _build_chain(sync_url: str) -> None:
    """路径 A(交付快照语义):baseline 建表 + 时代造形,沿链升到 head。"""
    command.upgrade(_cfg(sync_url), "0001_baseline")
    engine = create_engine(sync_url)
    try:
        # 时代造形(退役前三表 + visibility 列):历史增量引用的旧形态
        _add_legacy_visibility(engine)
        _create_retired_tables(engine)
    finally:
        engine.dispose()
    command.upgrade(_cfg(sync_url), "head")


def _build_fresh(sync_url: str) -> None:
    """路径 B:正式新库初始化 = create_all + 共享触发器 DDL + stamp。"""
    from app.core.db import Base
    from app.models.project import PROJECT_CONTAINER_DDL

    import app.models  # noqa: F401  注册所有模型

    engine = create_engine(sync_url, future=True)
    try:
        Base.metadata.create_all(engine, checkfirst=False)
        with engine.begin() as conn:
            for stmt in PROJECT_CONTAINER_DDL:
                conn.execute(text(stmt))
        command.stamp(_cfg(sync_url), "head")
    finally:
        engine.dispose()


# ── 系统目录断言面(按属性比较;名称只在两路径同源可控时参与)────────

def _regclass(conn, schema: str, table: str) -> int:
    return conn.execute(text(
        "SELECT to_regclass(:t)::oid"),
        {"t": f"{schema}.{table}"}).scalar_one()


def _columns(conn, schema: str, table: str) -> list[tuple]:
    return sorted(conn.execute(text("""
        SELECT a.attname,
               format_type(a.atttypid, a.atttypmod),
               a.attnotnull,
               coalesce(pg_get_expr(ad.adbin, a.attrelid), '')
          FROM pg_attribute a
          LEFT JOIN pg_attrdef ad
            ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
         WHERE a.attrelid = :rc AND a.attnum > 0 AND NOT a.attisdropped
    """), {"rc": _regclass(conn, schema, table)}).fetchall())


def _constraints(conn, schema: str, table: str) -> list[tuple]:
    """(类型, 定义) 按序比较;名称不参与 —— 模型侧 FK 为 PG 自动命名,
    迁移侧为显式命名,定义等价即为结构一致(§20.4 比较的是属性)。"""
    return sorted((contype, definition) for contype, definition in conn.execute(text("""
        SELECT c.contype, pg_get_constraintdef(c.oid)
          FROM pg_constraint c
         WHERE c.conrelid = :rc
    """), {"rc": _regclass(conn, schema, table)}).fetchall())


def _indexes(conn, schema: str, table: str) -> list[tuple]:
    """pg_get_indexdef 内嵌限定 schema 名(路径 A/B 的临时 schema 不同)——
    归一掉前缀,只比较结构定义。"""
    prefix = f"ON {schema}."
    rows = conn.execute(text("""
        SELECT i.relname, pg_get_indexdef(ix.indexrelid)
          FROM pg_index ix
          JOIN pg_class i ON i.oid = ix.indexrelid
         WHERE ix.indrelid = :rc AND NOT ix.indisprimary
    """), {"rc": _regclass(conn, schema, table)}).fetchall()
    return sorted((name, definition.replace(prefix, "ON "))
                  for name, definition in rows)


def _triggers(conn, schema: str, table: str) -> list[tuple]:
    return sorted(conn.execute(text("""
        SELECT t.tgname, t.tgdeferrable, t.tginitdeferred,
               t.tgenabled, p.proname
          FROM pg_trigger t
          JOIN pg_proc p ON p.oid = t.tgfoid
         WHERE t.tgrelid = :rc AND NOT t.tgisinternal
    """), {"rc": _regclass(conn, schema, table)}).fetchall())


def _functions(conn, schema: str) -> dict[str, str]:
    rows = conn.execute(text("""
        SELECT p.proname, p.prosrc
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = :s AND p.proname = ANY(:names)
    """), {"s": schema, "names": list(_SHARED_FUNCTIONS)}).fetchall()
    return dict(rows)


def _schema_shape(engine, schema: str) -> None:
    """采集该 schema 的可比结构面(供两路径对照)。"""
    with engine.connect() as conn:
        shape = {
            "columns": {t: _columns(conn, schema, t)
                        for t in _COMPARE_TABLES},
            "constraints": {t: _constraints(conn, schema, t)
                            for t in _COMPARE_TABLES},
            "indexes": {t: _indexes(conn, schema, t)
                        for t in _COMPARE_TABLES},
            "triggers": {t: _triggers(conn, schema, t)
                         for t in _TRIGGER_TABLES},
            "functions": _functions(conn, schema),
        }
    return shape


@pytest.fixture(scope="module")
def dual_paths():
    """一次构建两条路径(M1 交付面),全部用例共享。"""
    with temp_schema() as (schema_a, url_a):
        _build_chain(url_a)
        with temp_schema() as (schema_b, url_b):
            _build_fresh(url_b)
            engine_a = create_engine(url_a, future=True)
            engine_b = create_engine(url_b, future=True)
            try:
                yield (_schema_shape(engine_a, schema_a),
                       _schema_shape(engine_b, schema_b))
            finally:
                engine_a.dispose()
                engine_b.dispose()


class TestDualPathStructure:

    def test_columns(self, dual_paths):
        a, b = dual_paths
        assert a["columns"] == b["columns"]

    def test_constraints(self, dual_paths):
        """PK/FK/CHECK/UNIQUE(含删除动作与延迟属性)逐条一致。"""
        a, b = dual_paths
        assert a["constraints"] == b["constraints"]

    def test_indexes(self, dual_paths):
        """索引(含谓词部分唯一索引)逐条一致。"""
        a, b = dual_paths
        assert a["indexes"] == b["indexes"]

    def test_triggers(self, dual_paths):
        """触发器名称、启用状态、延迟属性与挂靠函数一致(§20.4)。"""
        a, b = dual_paths
        assert a["triggers"] == b["triggers"]

    def test_shared_function_bodies(self, dual_paths):
        """共享 DDL 定义的函数体一致 —— 结构断言不仅看名字。"""
        a, b = dual_paths
        assert a["functions"] == b["functions"]

    def test_container_invariants_present(self, dual_paths):
        """两路径都具备 §20 容器不变量的完整触发器面(非仅路径 B);
        §20.6 起对象表不再挂任何触发器(复合 FK 是权威)。"""
        for shape in dual_paths:
            trigger_names = {t[0]
                             for rows in shape["triggers"].values()
                             for t in rows}
            for name in ("trg_project_member_kind_guard",
                         "trg_project_kind_immutable",
                         "trg_project_member_admin_invariant",
                         "trg_project_admin_invariant",
                         "trg_user_active_admin_invariant",
                         "trg_user_default_space_invariant"):
                assert name in trigger_names, name
            assert "trg_suite_member_same_zone" not in trigger_names
            fns = set(shape["functions"])
            assert fns == set(_SHARED_FUNCTIONS)
