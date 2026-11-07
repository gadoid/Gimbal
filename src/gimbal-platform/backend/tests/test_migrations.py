"""逐版本迁移测试(authz T0.4,dev-plan §〇):stamp → upgrade → 断言 → downgrade。

空库门(test_empty_db_bootstrap)只覆盖「空库一把升到 head」;增量升级与
回滚此前没有测试面。本模块补这个面:临时 schema 里造出旧版本形态 →
``command.stamp(旧)`` → ``command.upgrade`` / ``command.downgrade``
逐步断言。

直接用 ``alembic.command``,不走 ``ensure_schema_sync`` —— 它对「有版本
但落后」的库拒绝启动是产品语义(DDL 必须人工窗口执行),不是迁移本身的
语义;迁移测试要测的恰恰是人工窗口里跑的那条路径。
"""
from __future__ import annotations

import asyncio
import os
import secrets as _secrets
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

_BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def temp_schema():
    """业务库内临时 schema(等价干净库;结束 DROP CASCADE)。

    与 test_empty_db_bootstrap 同口径:gimbal 用户通常无 CREATEDB 权限。
    yield (schema, sync_url) —— sync_url 是把 search_path 编进 options
    的 psycopg URL,可直接喂 alembic。
    """
    url = os.environ["TEST_DATABASE_URL"]  # conftest 已保证 PG 形状
    schema = f"t_mig_{_secrets.token_hex(4)}"

    async def _admin(stmt: str) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        eng = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with eng.connect() as c:
                await c.execute(text(stmt))
        finally:
            await eng.dispose()

    asyncio.run(_admin(f'CREATE SCHEMA "{schema}"'))
    try:
        sync_url = (
            url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
            + "?options=" + quote(f"-csearch_path={schema}")
        )
        yield schema, sync_url
    finally:
        asyncio.run(_admin(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def _cfg(sync_url: str):
    from app.core.migrations import _alembic_config

    return _alembic_config(sync_url)


def _revision(sync_url: str) -> str | None:
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    eng = create_engine(sync_url)
    try:
        with eng.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        eng.dispose()


def test_full_chain_from_empty():
    """空 schema → ``upgrade head``:全链从零可跑(空库门的产品面等价物,
    新迁移加入后自动纳入覆盖)。"""
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "head")

        head = ScriptDirectory(str(_BACKEND / "alembic")).get_current_head()
        assert _revision(sync_url) == head

        eng = create_engine(sync_url)
        try:
            with eng.connect() as conn:
                names = set(inspect(conn).get_table_names())
        finally:
            eng.dispose()
        for required in ("users", "integration_tasks", "access_tokens"):
            assert required in names, f"缺表 {required}"


# ── 0036_role_rename(authz W1)─────────────────────────────────────
# 三件事(更名/加列/恢复)分别断言(dev-plan 评审 R10);恢复 SQL 的字段
# 口径对照 revive_paused_instances(评审 N10),范围仅实例、模板行不动
# (评审 E4)。

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

_ROLE_MAP = {"admin": "super_admin", "member": "admin", "user": "user"}

_ROLE_FORMS = [
    pytest.param([("root", "admin"), ("worker", "user")], id="only_admin"),
    pytest.param(
        [("root", "admin"), ("op", "member"), ("worker", "user")], id="mixed"),
    pytest.param([("__platform__", "admin", True)], id="only_platform"),
]


def _to_0035_shape(eng) -> None:
    """create_all 是当前模型(已含新列);撤掉新列模拟 0035 存量库。"""
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE users DROP COLUMN must_change_password")


@pytest.mark.parametrize("seed", _ROLE_FORMS)
def test_0036_role_rename(seed):
    """① 角色更名(三数据形态)+ ② must_change_password 列;downgrade 回填。"""
    from alembic import command
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.user import User

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            with Session(eng) as s:
                for row in seed:
                    s.add(User(
                        username=row[0], display_name="", password_hash="x",
                        role=row[1],
                        is_system=(len(row) > 2 and row[2]),
                        updated_at=(datetime.now(timezone.utc)
                                    - timedelta(hours=1)),
                    ))
                s.commit()
            _to_0035_shape(eng)
            command.stamp(_cfg(sync_url), "0035_execution_steps")

            # ── ① 角色更名 ──
            command.upgrade(_cfg(sync_url), "head")
            assert _revision(sync_url) == "0037_report_def_maintainer"
            with eng.connect() as conn:
                rows = {
                    u: (role, ts) for u, role, ts in conn.exec_driver_sql(
                        "select username, role, updated_at from users"
                    ).fetchall()}
            expect = {
                row[0]: (row[1] if len(row) > 2 and row[2]
                         else _ROLE_MAP[row[1]])
                for row in seed}
            assert {u: r for u, (r, _) in rows.items()} == expect, rows
            # updated_at 只在角色被改写的行上刷新;user 行与 is_system
            # 行不在 UPDATE 范围,必须保持原值(钉「不动」语义)。
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            for row in seed:
                name, touched = row[0], row[1] in ("admin", "member") and not (
                    len(row) > 2 and row[2])
                ts = rows[name][1]
                if touched:
                    assert ts > cutoff, f"{name} 的 updated_at 未被迁移刷新"
                else:
                    assert ts < cutoff, f"{name} 不应被迁移触碰: {ts}"

            # ── ② must_change_password 列(与 ① 分开断言) ──
            with eng.connect() as conn:
                col = conn.exec_driver_sql(
                    "select data_type, column_default"
                    " from information_schema.columns"
                    f" where table_schema = '{_schema}'"
                    "   and table_name = 'users'"
                    "   and column_name = 'must_change_password'"
                ).first()
                assert col is not None, "列未加回"
                assert col[0] == "boolean"
                assert col[1] and "false" in col[1]
                flagged = conn.exec_driver_sql(
                    "select count(*) from users"
                    " where must_change_password").scalar_one()
                assert flagged == 0

            # ── downgrade:角色回填(反序)+ 删列 ──
            command.downgrade(_cfg(sync_url), "0035_execution_steps")
            with eng.connect() as conn:
                back = {u: r for u, r in conn.exec_driver_sql(
                    "select username, role from users").fetchall()}
                assert back == {row[0]: row[1] for row in seed}, back
                # schema 过滤不可省:库里可能有其他测试残留的 t_* schema
                # (information_schema 不过滤会数到别人的 users 表)
                has = conn.exec_driver_sql(
                    "select count(*) from information_schema.columns"
                    f" where table_schema = '{_schema}'"
                    "   and table_name = 'users'"
                    "   and column_name = 'must_change_password'"
                ).scalar_one()
                assert has == 0
        finally:
            eng.dispose()


def test_0036_revives_token_owner_ineligible():
    """③ 恢复 SQL:仅 ``template_id IS NOT NULL`` 且原因匹配的实例被恢复
    (state='idle' + paused_reason 清空 + next_run_at 刷新);其他暂停
    原因与模板行不动。SQL 恢复不发恢复通知 —— 与函数恢复的这一差异
    可接受(评审 N10),此处只钉数据口径。"""
    from alembic import command
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.integration_task import IntegrationTask
    from app.models.user import User

    def _tpl(name: str, owner: int) -> IntegrationTask:
        return IntegrationTask(
            name=name, owner_id=owner, visibility="private",
            identity_mode="platform", target_type="scenario",
            scenario_id="sc-1", target_system="fin",
            trigger_cron="*/5 * * * *", result_policy="latest",
            card_template="status", state="paused",
            paused_reason="token_owner_ineligible",
            run_status="ok", check_status="ok")

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            with Session(eng) as s:
                root = User(username="root", display_name="",
                            password_hash="x", role="admin")
                op = User(username="op", display_name="",
                          password_hash="x", role="member")
                worker = User(username="worker", display_name="",
                              password_hash="x", role="user")
                s.add_all([root, op, worker])
                s.flush()
                tpl = _tpl("tpl", root.id)  # 模板行:同款暂停,必须不动
                s.add(tpl)
                s.flush()
                past = datetime.now(timezone.utc) - timedelta(hours=2)
                target = _tpl("inst_target", root.id)
                target.template_id = tpl.id
                target.holder_id = op.id
                target.next_run_at = past
                other = _tpl("inst_other", root.id)
                other.template_id = tpl.id
                # uq_integration_instance:(template_id, holder_id) 唯一
                # —— 换一个 holder,保持两实例并存。
                other.holder_id = worker.id
                other.paused_reason = "missing_credential"
                other.next_run_at = past
                s.add_all([target, other])
                s.commit()
            _to_0035_shape(eng)
            command.stamp(_cfg(sync_url), "0035_execution_steps")
            command.upgrade(_cfg(sync_url), "head")

            with eng.connect() as conn:
                rows = {n: (st, pr, nr) for n, st, pr, nr in conn.exec_driver_sql(
                    "select name, state, paused_reason, next_run_at"
                    " from integration_tasks").fetchall()}
            # 目标实例:三字段全恢复
            st, pr, nr = rows["inst_target"]
            assert (st, pr) == ("idle", "")
            assert nr > past + timedelta(hours=1), "next_run_at 未刷新"
            # 其他暂停原因 / 模板行:不动
            assert rows["inst_other"][:2] == ("paused", "missing_credential")
            assert rows["tpl"][:2] == ("paused", "token_owner_ineligible")
        finally:
            eng.dispose()



# ── 0037_report_def_maintainer(authz W9-2)─────────────────────────
def test_0037_report_def_visibility_backfill():
    """公共态从 owner_id IS NULL 改为 visibility 列:存量无主行回填
    public(owner 保持 NULL);有主行保持 private;downgrade drop 列
    即回旧口径(无主 = 公共)。"""
    from alembic import command
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.report_definition import ReportDefinitionRow

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            # 存量库形状:create_all 已带新列 → 手动 drop 还原 0036 侧
            with eng.begin() as c:
                c.execute(text(
                    "ALTER TABLE report_definitions DROP COLUMN visibility"))
                # 造数据:无主 = 旧公共态;有主 = 私有
                c.execute(text(
                    "INSERT INTO report_definitions "
                    "(name, description, definition, owner_id) VALUES "
                    "('legacy-pub', '', '{}', NULL), "
                    "('owned', '', '{}', 7)"))
            with Session(eng) as s2:
                pass
            command.stamp(_cfg(sync_url), "0036_role_rename")
            command.upgrade(_cfg(sync_url), "0037_report_def_maintainer")

            with eng.connect() as c:
                rows = {r: (v, o) for r, v, o in c.execute(text(
                    "SELECT name, visibility, owner_id "
                    "FROM report_definitions"))}
            # 无主 → public(owner 不动);有主 → private
            assert rows["legacy-pub"] == ("public", None)
            assert rows["owned"] == ("private", 7)

            command.downgrade(_cfg(sync_url), "0036_role_rename")
            cols = {c["name"] for c in inspect(eng).get_columns(
                "report_definitions")}
            assert "visibility" not in cols
        finally:
            eng.dispose()
