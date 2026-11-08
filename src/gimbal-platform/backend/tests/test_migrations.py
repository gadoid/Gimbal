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


def _head() -> str:
    """链头 revision(计算值:新迁移加入后旧用例的「升到头」断言不过期)。"""
    from alembic.script import ScriptDirectory

    return ScriptDirectory(str(_BACKEND / "alembic")).get_current_head()


def _add_legacy_visibility(eng) -> None:
    """S1.9(0043 删列后)迁移链兼容:补加 visibility 列(默认 private)。"""
    with eng.begin() as conn:
        for t in ("composer_scenarios", "suites",
                  "report_definitions", "integration_tasks"):
            conn.exec_driver_sql(
                f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS visibility "
                "VARCHAR(16) NOT NULL DEFAULT 'private'")


def _add_legacy_alias_columns(eng) -> None:
    """S6(0047 删列后)迁移链兼容:补回 service_aliases 的四个旧列,
    供 0044–0046 的存量回填用例按旧形态造数。"""
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE service_aliases "
            "ADD COLUMN IF NOT EXISTS base_url VARCHAR(512), "
            "ADD COLUMN IF NOT EXISTS environment_id INTEGER "
            "REFERENCES environments(id), "
            "ADD COLUMN IF NOT EXISTS credential_alias VARCHAR(64), "
            "ADD COLUMN IF NOT EXISTS owner_user_id INTEGER "
            "REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED")


def test_full_chain_from_empty():
    """空 schema → ``upgrade head``:全链从零可跑(空库门的产品面等价物,
    新迁移加入后自动纳入覆盖)。"""
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text

    with temp_schema() as (_schema, sync_url):
        # S1.9:baseline 无 visibility 列,旧迁移引用 → stamp + 补列 + 升链
        # 先跑到 baseline(建表),补 visibility 列,再升到 head
        command.upgrade(_cfg(sync_url), "0001_baseline")
        from sqlalchemy import create_engine as _ce
        _eng = _ce(sync_url)
        try:
            _add_legacy_visibility(_eng)
        finally:
            _eng.dispose()
        command.upgrade(_cfg(sync_url), "head")

        head = ScriptDirectory(str(_BACKEND / "alembic")).get_current_head()
        assert _revision(sync_url) == head

        eng = create_engine(sync_url)
        try:
            with eng.connect() as conn:
                names = set(inspect(conn).get_table_names())
                # 0040:fresh 链上两表由 baseline 建出、公共项目由 0040 种
                public_n = conn.execute(text(
                    "SELECT count(*) FROM projects "
                    "WHERE kind = 'public'")).scalar()
        finally:
            eng.dispose()
        for required in ("users", "integration_tasks", "access_tokens",
                         "projects", "project_members"):
            assert required in names, f"缺表 {required}"
        assert public_n == 1  # 公共项目恰一行(种子对 fresh 链同样生效)


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


def _add_legacy_identity_mode(eng) -> None:
    """create_all 是当前模型(identity_mode 列已随 0039 删除);0039 之前
    的存量库带该列 —— 补回,供 0036–0038 的迁移语句操作。"""
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE integration_tasks ADD COLUMN identity_mode "
            "VARCHAR(16) NOT NULL DEFAULT 'personal'")


def _to_0035_shape(eng) -> None:
    """create_all 是当前模型(已含新列);撤掉新列模拟 0035 存量库。"""
    _add_legacy_visibility(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE users DROP COLUMN must_change_password")
    _add_legacy_identity_mode(eng)


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
            assert _revision(sync_url) == _head()
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
            name=name, owner_id=owner,
            target_type="scenario",
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
            # S1.9:create_all 已无 visibility 列(0043 删列后模型),
            # 天然即 0036 形态(无 visibility 列的 report_definitions)
            with eng.begin() as c:
                # 造数据:无主 = 旧公共态;有主 = 私有
                c.execute(text(
                    "INSERT INTO report_definitions "
                    "(name, description, definition, owner_id) VALUES "
                    "('legacy-pub', '', '{}', NULL), "
                    "('owned', '', '{}', 7)"))
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


# ── 0038_platform_retire(authz C1)─────────────────────────────────
def test_0038_platform_retire():
    """四步各断言:① __platform__ 自持实例删;② 模板 personal ∧ public
    ∧ 属主 __platform__(实例行同改,个人模板不动);③ 系统用户会话与
    平台令牌删;④ 约束生效(写 platform 即拒)。"""
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.integration_task import IntegrationTask
    from app.models.user import User

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            with Session(eng) as s:
                plat = User(username="__platform__", display_name="",
                            password_hash="x", role="user", is_system=True)
                root = User(username="root", display_name="",
                            password_hash="x", role="admin")
                sub = User(username="sub", display_name="",
                           password_hash="x", role="user")
                s.add_all([plat, root, sub])
                s.flush()
                # 平台模板(私有)+ 平台唯一实例 + 订阅者实例
                tpl = IntegrationTask(
                    name="plat-tpl", owner_id=root.id,
                    target_type="scenario",
                    scenario_id="sc-1", target_system="fin",
                    trigger_cron="*/5 * * * *", result_policy="latest",
                    card_template="status", state="idle")
                s.add(tpl)
                s.flush()
                inst = IntegrationTask(
                    name="plat-tpl", owner_id=root.id,
                    template_id=tpl.id, holder_id=plat.id, state="idle")
                sub_inst = IntegrationTask(
                    name="plat-tpl", owner_id=root.id,
                    template_id=tpl.id, holder_id=sub.id, state="idle")
                s.add_all([inst, sub_inst])
                # 对照:root 的个人公共模板 —— 属主不随平台模板改
                own = IntegrationTask(
                    name="own-tpl", owner_id=root.id,
                    target_type="scenario",
                    scenario_id="sc-2", target_system="fin",
                    trigger_cron="*/5 * * * *", result_policy="latest",
                    card_template="status", state="idle")
                s.add(own)
                # 平台凭证池(系统用户会话)与平台令牌
                from app.models.auth_session import AuthSession
                from app.models.access_token import AccessToken
                s.add(AuthSession(owner_id=plat.id, alias="gitlab",
                                  url="https://git", username_enc="u",
                                  password_enc="p"))
                from datetime import datetime, timedelta, timezone as _tz
                s.add(AccessToken(kind="platform", name="pt",
                                  token_hash="x" * 64, token_hint="gtk-pt",
                                  user_id=plat.id, created_by=root.id,
                                  expires_at=datetime.now(_tz.utc)
                                  + timedelta(days=1)))
                s.commit()
                plat_id, sub_id, root_id = plat.id, sub.id, root.id
            # 0039 前的存量形态:补回 identity_mode 列,平台模板行置 platform
            _add_legacy_identity_mode(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "UPDATE integration_tasks SET identity_mode='platform' "
                    "WHERE name = 'plat-tpl' AND template_id IS NULL")
            _add_legacy_visibility(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "UPDATE integration_tasks SET visibility='public' "
                    "WHERE template_id IS NULL AND name='plat-tpl'")

            command.stamp(_cfg(sync_url), "0037_report_def_maintainer")
            command.upgrade(_cfg(sync_url), "0038_platform_retire")

            with eng.connect() as c:
                # ① 平台实例删;订阅者实例保留
                holders = [r for r in c.execute(text(
                    "SELECT holder_id FROM integration_tasks "
                    "WHERE template_id IS NOT NULL"))]
                assert holders == [(sub_id,)], holders
                # ② 模板 personal ∧ public ∧ 属主 __platform__
                row = c.execute(text(
                    "SELECT identity_mode, visibility, owner_id "
                    "FROM integration_tasks "
                    "WHERE template_id IS NULL AND name = 'plat-tpl'")).one()
                assert row == ("personal", "public", plat_id)
                # 订阅实例 owner_id 镜像模板属主;个人模板属主不动
                assert c.execute(text(
                    "SELECT owner_id FROM integration_tasks "
                    "WHERE template_id IS NOT NULL")).scalar() == plat_id
                assert c.execute(text(
                    "SELECT owner_id FROM integration_tasks "
                    "WHERE name = 'own-tpl'")).scalar() == root_id
                # ③ 会话/令牌删空
                assert c.execute(text(
                    "SELECT count(*) FROM auth_sessions")).scalar() == 0
                assert c.execute(text(
                    "SELECT count(*) FROM access_tokens")).scalar() == 0
            # ④ 约束:写 platform 即拒(独立连接,失败即回滚)
            import pytest
            import sqlalchemy as sa_exc
            with pytest.raises(sa_exc.exc.IntegrityError):
                with eng.connect() as c2:
                    with c2.begin():
                        c2.execute(text(
                            "UPDATE integration_tasks "
                            "SET identity_mode='platform' "
                            "WHERE template_id IS NULL AND name = 'plat-tpl'"))
            command.downgrade(_cfg(sync_url), "0037_report_def_maintainer")
            with eng.connect() as c:
                assert c.execute(text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conname = "
                    "'ck_integration_identity_personal'")).scalar() == 0
        finally:
            eng.dispose()


# ── 0039_drop_identity_mode(authz 收尾)───────────────────────────
def test_0039_drop_identity_mode():
    """0038 终态(列 + CHECK)→ 0039 删约束与列;downgrade 还原列(回填
    personal)与约束。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401
    from app.core.db import Base

    def _cols(c) -> set[str]:
        return {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'integration_tasks' "
            "AND table_schema = current_schema()"))}

    def _ck(c) -> int:
        return c.execute(text(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conname = 'ck_integration_identity_personal'")).scalar()

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            _add_legacy_identity_mode(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE integration_tasks ADD CONSTRAINT "
                    "ck_integration_identity_personal "
                    "CHECK (identity_mode = 'personal')")
            command.stamp(_cfg(sync_url), "0038_platform_retire")
            command.upgrade(_cfg(sync_url), "0039_drop_identity_mode")
            with eng.connect() as c:
                assert "identity_mode" not in _cols(c)
                assert _ck(c) == 0
            command.downgrade(_cfg(sync_url), "0038_platform_retire")
            with eng.connect() as c:
                assert "identity_mode" in _cols(c)
                assert _ck(c) == 1
        finally:
            eng.dispose()


# ── 0040_project_zone(authz M2a S1.0)───────────────────────────────
def _to_0039_shape(eng) -> None:
    """create_all 是当前模型(已含 project_id / is_platform_template 与
    projects 两表);撤掉这些模拟 0039 存量库(PG 删列连带删索引与 FK,
    成员表先于项目表删)。"""
    _add_legacy_visibility(eng)
    with eng.begin() as conn:
        for t in ("composer_scenarios", "suites", "integration_tasks",
                  "report_definitions", "executions"):
            conn.exec_driver_sql(f"ALTER TABLE {t} DROP COLUMN project_id")
        conn.exec_driver_sql(
            "ALTER TABLE integration_tasks "
            "DROP COLUMN is_platform_template")
        conn.exec_driver_sql("DROP TABLE project_members")
        conn.exec_driver_sql("DROP TABLE projects")


def test_0040_project_zone():
    """六步分别断言(s1-detail §二):① 两表 + 公共项目种子(created_by
    = __platform__,成员行恒空);② 加列;③ visibility='public' 迁入公共
    项目 —— 私有不动、集成实例行不迁、executions 不回填、无主公共报告
    定义照迁(0037 遗留);④ 平台模板标记仅限 removed_at IS NULL;
    ⑤ 软删挂靠模板连同实例删(订阅实例/软删的平台模板保留);⑥ visibility
    列仍在。downgrade 还原 schema 且公开行 visibility 未动。"""
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.user import User
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite
    from app.models.report_definition import ReportDefinitionRow
    from app.models.integration_task import IntegrationTask
    from app.models.execution import Execution

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            with Session(eng) as s:
                plat = User(username="__platform__", display_name="",
                            password_hash="x", role="user", is_system=True)
                author = User(username="author", display_name="作者",
                              password_hash="x", role="user")
                other = User(username="other", display_name="路人",
                             password_hash="x", role="user")
                s.add_all([plat, author, other])
                s.flush()
                s.add_all([
                    ComposerScenario(scenario_id="sc-pub",
                                     owner_id=author.id, payload={}),
                    ComposerScenario(scenario_id="sc-priv",
                                     owner_id=author.id, payload={}),
                    Suite(name="套件-公开", owner_id=author.id),
                    Suite(name="套件-私有", owner_id=author.id),
                    # 0037 遗留:无主公共报告定义(编辑面冻结)
                    ReportDefinitionRow(name="rd-orphan", owner_id=None),
                    ReportDefinitionRow(name="rd-pub", owner_id=author.id),
                    ReportDefinitionRow(name="rd-priv", owner_id=author.id),
                ])
                tpl_pub = IntegrationTask(  # 个人公共模板(维护者=创建人)
                    name="个人公共", owner_id=author.id,
                    target_type="scenario", scenario_id="sc-pub",
                    target_system="fin", trigger_cron="*/5 * * * *",
                    result_policy="latest", card_template="status",
                    state="idle")
                tpl_priv = IntegrationTask(  # 个人私有模板 —— 留在私有区
                    name="个人私有", owner_id=author.id,
                    target_type="scenario", scenario_id="sc-priv",
                    target_system="fin", trigger_cron="*/5 * * * *",
                    result_policy="latest", card_template="status",
                    state="idle")
                tpl_platform = IntegrationTask(  # 平台模板(0038 归属形态)
                    name="平台模板", owner_id=plat.id,
                    target_type="scenario", scenario_id="sc-pub",
                    target_system="fin", trigger_cron="*/5 * * * *",
                    result_policy="latest", card_template="status",
                    state="idle")
                tpl_refugee = IntegrationTask(  # 删用户软删后挂靠的模板
                    name="挂靠", owner_id=plat.id,
                    target_type="scenario", scenario_id="sc-pub",
                    target_system="fin", trigger_cron="*/5 * * * *",
                    result_policy="latest", card_template="status",
                    state="idle", removed_at=datetime.now(timezone.utc))
                s.add_all([tpl_pub, tpl_priv, tpl_platform, tpl_refugee])
                s.flush()
                s.add_all([
                    # 挂靠模板的他人订阅实例(「已移除」态死卡,随模板删)
                    IntegrationTask(name="挂靠", owner_id=plat.id,
                                    template_id=tpl_refugee.id,
                                    holder_id=other.id, state="idle"),
                    # 个人公共 / 平台模板的订阅实例 —— 保留
                    IntegrationTask(name="个人公共", owner_id=author.id,
                                    template_id=tpl_pub.id,
                                    holder_id=other.id, state="idle"),
                    IntegrationTask(name="平台模板", owner_id=plat.id,
                                    template_id=tpl_platform.id,
                                    holder_id=other.id, state="idle"),
                    # 存量执行:project_id 不回填(可见性保持仅发起人)
                    Execution(scenario_id="sc-pub", owner_id=author.id),
                ])
                s.commit()
                plat_id, author_id = plat.id, author.id
            _to_0039_shape(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "UPDATE composer_scenarios SET visibility='public' "
                    "WHERE scenario_id='sc-pub'")
                conn.exec_driver_sql(
                    "UPDATE integration_tasks SET visibility='public' "
                    "WHERE template_id IS NULL AND removed_at IS NULL "
                    "AND name IN ('个人公共', '平台模板')")
                conn.exec_driver_sql(
                    "UPDATE suites SET visibility='public' "
                    "WHERE name = '套件-公开'")
                conn.exec_driver_sql(
                    "UPDATE report_definitions SET visibility='public' "
                    "WHERE name IN ('rd-pub', 'rd-orphan')")

            command.stamp(_cfg(sync_url), "0039_drop_identity_mode")
            command.upgrade(_cfg(sync_url), "0040_project_zone")

            def _cols(c, table: str) -> set[str]:
                return {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table}' "
                    "AND table_schema = current_schema()"))}

            with eng.connect() as c:
                # ① 公共项目恰一行:名称「公共」、created_by=__platform__;
                #    成员行恒空(公共项目不落成员行)
                pid = c.execute(text(
                    "SELECT id FROM projects WHERE kind = 'public'"
                )).scalar()
                assert pid is not None
                assert c.execute(text(
                    "SELECT count(*), min(name), min(created_by) "
                    "FROM projects")).one() == (1, "公共", plat_id)
                assert c.execute(text(
                    "SELECT count(*) FROM project_members")).scalar() == 0
                # ② 加列(对象表 + 执行快照)
                for t in ("composer_scenarios", "suites", "integration_tasks",
                          "report_definitions", "executions"):
                    assert "project_id" in _cols(c, t), t
                assert "is_platform_template" in _cols(c, "integration_tasks")
                # ③ 公开内容迁入公共项目;私有不动;无主公共定义照迁
                assert c.execute(text(
                    "SELECT project_id FROM composer_scenarios "
                    "WHERE scenario_id = 'sc-pub'")).scalar() == pid
                assert c.execute(text(
                    "SELECT project_id FROM composer_scenarios "
                    "WHERE scenario_id = 'sc-priv'")).scalar() is None
                assert c.execute(text(
                    "SELECT project_id FROM suites "
                    "WHERE name = '套件-公开'")).scalar() == pid
                assert c.execute(text(
                    "SELECT project_id FROM suites "
                    "WHERE name = '套件-私有'")).scalar() is None
                for rd, want in (("rd-pub", pid), ("rd-orphan", pid),
                                 ("rd-priv", None)):
                    assert c.execute(text(
                        "SELECT project_id FROM report_definitions "
                        f"WHERE name = '{rd}'")).scalar() == want, rd
                # 集成:模板行迁入、实例行不迁(实例归持有人)
                for name, want in (("个人公共", pid), ("个人私有", None),
                                   ("平台模板", pid)):
                    assert c.execute(text(
                        "SELECT project_id FROM integration_tasks "
                        f"WHERE name = '{name}' "
                        "AND template_id IS NULL")).scalar() == want, name
                assert c.execute(text(
                    "SELECT count(*) FROM integration_tasks "
                    "WHERE template_id IS NOT NULL "
                    "AND project_id IS NOT NULL")).scalar() == 0
                # executions 不回填
                assert c.execute(text(
                    "SELECT count(*) FROM executions "
                    "WHERE project_id IS NOT NULL")).scalar() == 0
                # ④ 平台模板标记:仅 live 平台属主行;个人公共模板不标
                assert c.execute(text(
                    "SELECT is_platform_template FROM integration_tasks "
                    "WHERE name = '平台模板' "
                    "AND template_id IS NULL")).scalar() is True
                assert c.execute(text(
                    "SELECT is_platform_template FROM integration_tasks "
                    "WHERE name = '个人公共' "
                    "AND template_id IS NULL")).scalar() is False
                # ⑤ 挂靠模板连同其实例删除;订阅实例保留
                assert c.execute(text(
                    "SELECT count(*) FROM integration_tasks "
                    "WHERE name = '挂靠'")).scalar() == 0
                inst = c.execute(text(
                    "SELECT name, count(*) FROM integration_tasks "
                    "WHERE template_id IS NOT NULL "
                    "GROUP BY name ORDER BY name")).all()
                assert inst == [("个人公共", 1), ("平台模板", 1)], inst
                # ⑥ visibility 影子未删
                assert "visibility" in _cols(c, "composer_scenarios")
                # 公共项目恰一行:部分唯一索引拦第二个 public
                # (独立连接,失败即回滚 —— 0038 约束检查同款)
                import sqlalchemy as sa_exc
                with pytest.raises(sa_exc.exc.IntegrityError):
                    with eng.connect() as c2:
                        with c2.begin():
                            c2.execute(text(
                                "INSERT INTO projects (name, kind, "
                                "created_at) VALUES ("
                                "'又一个公共', 'public', now())"))

            command.downgrade(_cfg(sync_url), "0039_drop_identity_mode")
            with eng.connect() as c:
                # schema 还原;公开行 visibility 未动(读法回到 0039 代码)
                for t in ("composer_scenarios", "suites", "integration_tasks",
                          "report_definitions", "executions"):
                    assert "project_id" not in _cols(c, t), t
                assert "is_platform_template" not in _cols(
                    c, "integration_tasks")
                assert "projects" not in {
                    r[0] for r in c.execute(text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = current_schema()"))}
                assert c.execute(text(
                    "SELECT visibility FROM composer_scenarios "
                    "WHERE scenario_id = 'sc-pub'")).scalar() == "public"
                assert c.execute(text(
                    "SELECT count(*) FROM report_definitions "
                    "WHERE name = 'rd-orphan'")).scalar() == 1
        finally:
            eng.dispose()


# ── 0041_public_shadow_backfill(authz M2a S1.1)────────────────────
def test_0041_public_shadow_backfill():
    """0040→S1.1 发版窗口期里「发布」只翻 visibility 的漏网行,由 0041
    回填进公共项目(幂等;对象四表 + 集成模板行;私有行不动)。"""
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.composer_scenario import ComposerScenario
    from app.models.integration_task import IntegrationTask
    from app.models.user import User

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            # 真实时序:create_all(0040+ 形态)→ 撤列回 0039 → stamp →
            # upgrade 0040(种子 + 空表迁移)→ **再造窗口期漏网行** →
            # upgrade head(0041 回填)
            Base.metadata.create_all(eng)
            _to_0039_shape(eng)
            command.stamp(_cfg(sync_url), "0039_drop_identity_mode")
            command.upgrade(_cfg(sync_url), "0040_project_zone")
            with Session(eng) as s:
                author = User(username="author", display_name="",
                              password_hash="x", role="user")
                s.add(author)
                s.flush()
                # 窗口期发布形态:visibility=public ∧ project_id NULL
                # (0040 已跑完,不会被步③迁走)
                s.add_all([
                    ComposerScenario(scenario_id="sc-win", owner_id=author.id, payload={}),
                    ComposerScenario(scenario_id="sc-keep", owner_id=author.id,
                                     payload={}),
                    IntegrationTask(name="tpl-win", owner_id=author.id,
                                    target_type="scenario",
                                    scenario_id="sc-win",
                                    target_system="fin",
                                    trigger_cron="*/5 * * * *",
                                    result_policy="latest",
                                    card_template="status", state="idle"),
                ])
                s.commit()
            # S1.9:ORM 构造不再传 visibility → SQL 设窗口期公共形态
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "UPDATE composer_scenarios SET visibility='public' "
                    "WHERE scenario_id='sc-win'")
                conn.exec_driver_sql(
                    "UPDATE integration_tasks SET visibility='public' "
                    "WHERE template_id IS NULL AND name='tpl-win'")
            with eng.connect() as c:
                # 回填前:漏网行 project_id 为空
                assert c.execute(text(
                    "SELECT count(*) FROM composer_scenarios "
                    "WHERE visibility='public' "
                    "AND project_id IS NULL")).scalar() == 1
            command.upgrade(_cfg(sync_url), "head")
            assert _revision(sync_url) == _head()

            with eng.connect() as c:
                pid = c.execute(text(
                    "SELECT id FROM projects WHERE kind='public'")).scalar()
                assert pid is not None
                assert c.execute(text(
                    "SELECT project_id FROM composer_scenarios "
                    "WHERE scenario_id='sc-win'")).scalar() == pid
                assert c.execute(text(
                    "SELECT project_id FROM composer_scenarios "
                    "WHERE scenario_id='sc-keep'")).scalar() is None
                assert c.execute(text(
                    "SELECT project_id FROM integration_tasks "
                    "WHERE name='tpl-win' "
                    "AND template_id IS NULL")).scalar() == pid
            # 幂等:重复跑 0041 不重复改(种子仍恰一行);0043 列已删
            # → 先补列再设值(重复跑 0041 的 UPDATE 需要它)
            _add_legacy_visibility(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "UPDATE composer_scenarios SET visibility='public' "
                    "WHERE scenario_id='sc-win'")
                conn.exec_driver_sql(
                    "UPDATE integration_tasks SET visibility='public' "
                    "WHERE template_id IS NULL AND name='tpl-win'")

            command.stamp(_cfg(sync_url), "0040_project_zone")
            command.upgrade(_cfg(sync_url), "head")
            with eng.connect() as c:
                assert c.execute(text(
                    "SELECT count(*) FROM projects "
                    "WHERE kind='public'")).scalar() == 1
        finally:
            eng.dispose()


# ── 0042_suite_member_zone(authz M2a S1.5)─────────────────────────
def _to_0041_shape(eng) -> None:
    """create_all 是当前模型(无 owner_id / 简化 FK / 无触发器);补回
    0041 形态:owner_id 列 + 组合外键 + 目标唯一索引,删简化 FK。"""
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE suite_members ADD COLUMN owner_id INTEGER")
        conn.exec_driver_sql(
            "UPDATE suite_members sm SET owner_id = cs.owner_id "
            "FROM composer_scenarios cs "
            "WHERE cs.scenario_id = sm.scenario_id")
        conn.exec_driver_sql(
            "ALTER TABLE suite_members "
            "ALTER COLUMN owner_id SET NOT NULL")
        conn.exec_driver_sql(
            "ALTER TABLE suite_members DROP CONSTRAINT "
            "IF EXISTS fk_suite_members_suite_id")
        conn.exec_driver_sql(
            "ALTER TABLE suite_members DROP CONSTRAINT "
            "IF EXISTS fk_suite_members_scenario_id")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_suites_id_owner "
            "ON suites (id, owner_id)")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_composer_sid_owner "
            "ON composer_scenarios (scenario_id, owner_id)")
        conn.exec_driver_sql(
            "ALTER TABLE suite_members ADD CONSTRAINT fk_suite_members_suite "
            "FOREIGN KEY (suite_id, owner_id) "
            "REFERENCES suites (id, owner_id) ON DELETE CASCADE")
        conn.exec_driver_sql(
            "ALTER TABLE suite_members ADD CONSTRAINT "
            "fk_suite_members_scenario "
            "FOREIGN KEY (scenario_id, owner_id) "
            "REFERENCES composer_scenarios (scenario_id, owner_id) "
            "ON DELETE CASCADE")


def test_0042_suite_member_zone():
    """① 拆旧(列/组合 FK/uq 索引)② 简化 FK ③ 同区触发器;存量成员
    行不变;直插违例被触发器拒;downgrade 还原组合外键形态。"""
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.composer_scenario import ComposerScenario
    from app.models.suite import Suite, SuiteMember
    from app.models.user import User

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            with Session(eng) as s:
                alice = User(username="alice", display_name="",
                             password_hash="x", role="user")
                bob = User(username="bob", display_name="",
                           password_hash="x", role="user")
                s.add_all([alice, bob])
                s.flush()
                s.add_all([
                    ComposerScenario(scenario_id="sc-a", owner_id=alice.id,
                                     payload={}),
                    ComposerScenario(scenario_id="sc-b", owner_id=bob.id,
                                     payload={}),
                    Suite(name="s", owner_id=alice.id),
                ])
                s.commit()
            _to_0041_shape(eng)
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO suite_members "
                    "(suite_id, scenario_id, owner_id, role, sort, added_at) "
                    "SELECT s.id, 'sc-a', cs.owner_id, 'main', 0, now() "
                    "FROM suites s, composer_scenarios cs "
                    "WHERE cs.scenario_id = 'sc-a'")
            command.stamp(_cfg(sync_url), "0041_public_shadow_backfill")
            command.upgrade(_cfg(sync_url), "head")
            assert _revision(sync_url) == _head()

            with eng.connect() as c:
                cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'suite_members' "
                    "AND table_schema = current_schema()"))}
                assert "owner_id" not in cols
                fks = {r[0] for r in c.execute(text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'suite_members'::regclass "
                    "AND contype = 'f'"))}
                assert "fk_suite_members_suite" not in fks
                assert "fk_suite_members_scenario" not in fks
                assert {"fk_suite_members_suite_id",
                        "fk_suite_members_scenario_id"} <= fks
                # 触发器在;存量成员行不变(同属主对 → 同区合法)
                # pg_trigger 不按 schema 过滤 —— 同库其它 schema 的同名
                # 触发器会被数进来(调试/残留 schema),join 到当前 schema
                assert c.execute(text(
                    "SELECT count(*) FROM pg_trigger t "
                    "JOIN pg_class cl ON cl.oid = t.tgrelid "
                    "JOIN pg_namespace n ON n.oid = cl.relnamespace "
                    "WHERE t.tgname = 'trg_suite_member_same_zone' "
                    "AND n.nspname = current_schema()")).scalar() == 1
                assert c.execute(text(
                    "SELECT suite_id, scenario_id, sort FROM suite_members "
                    "ORDER BY sort")).all() == [(1, "sc-a", 0)]
                # 直插违例(私有套件 + 他人场景)被触发器拒
                import pytest as _pytest
                import sqlalchemy as _sa
                with _pytest.raises(Exception):
                    with c.begin():
                        c.execute(text(
                            "INSERT INTO suite_members "
                            "(suite_id, scenario_id, role, sort, added_at) "
                            "VALUES (1, 'sc-b', 'main', 1, now())"))

            command.downgrade(_cfg(sync_url), "0041_public_shadow_backfill")
            with eng.connect() as c:
                cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'suite_members' "
                    "AND table_schema = current_schema()"))}
                assert "owner_id" in cols
                # owner_id 按场景属主回填
                assert c.execute(text(
                    "SELECT sm.owner_id FROM suite_members sm "
                    "JOIN composer_scenarios cs "
                    "ON cs.scenario_id = sm.scenario_id "
                    "WHERE sm.scenario_id = 'sc-a'")).scalar() == (
                    c.execute(text(
                        "SELECT owner_id FROM composer_scenarios "
                        "WHERE scenario_id = 'sc-a'")).scalar())
        finally:
            eng.dispose()


# ── 0044_deployments_env_chain(authz M2a S2.0)──────────────────────
def _to_0043_shape(eng) -> None:
    """create_all 是当前模型(deployments 表 / is_default / 项目默认环境 /
    无 visibility);撤回到 0043 形态。"""
    _add_legacy_alias_columns(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql("DROP TABLE deployments")
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_environments_default")
        conn.exec_driver_sql("ALTER TABLE environments DROP COLUMN is_default")
        conn.exec_driver_sql(
            "ALTER TABLE projects DROP COLUMN default_environment_id")
        conn.exec_driver_sql(
            "ALTER TABLE environments ADD COLUMN visibility "
            "VARCHAR(16) DEFAULT 'private'")


_DEPLOY_FORMS = [
    # 恰 1 个环境:置默认;挂环境的别名按 (基础服务, 环境) 落行;没挂
    # 环境的别名落默认环境,与挂环境的同键同址 → 聚合成一行;无地址的
    # 别名不落;同键地址不一致(hr)→ 不落行(冲突留 Admin 裁定)
    pytest.param(
        ["dev"],
        [("a1", "fin", "dev", "http://fin-dev"),
         ("a4", "fin", None, "http://fin-dev"),
         ("a2", "crm", None, "http://crm"),
         ("a3", "pay", "dev", None),
         ("h1", "hr", "dev", "http://hr-1"),
         ("h2", "hr", None, "http://hr-2")],
        "dev",
        {("fin", "dev"): "http://fin-dev", ("crm", "dev"): "http://crm"},
        id="single_env"),
    # 多环境无默认:同键冲突(fin@dev)不落行;没挂环境的别名跳过
    #(运行时各别名回退自带地址,S2.1)
    pytest.param(
        ["dev", "sit"],
        [("b2", "fin", "dev", "http://fin-dev-b2"),
         ("b1", "fin", "dev", "http://fin-dev-b1"),
         ("c1", "fin", "sit", "http://fin-sit"),
         ("d1", "crm", None, "http://crm")],
        None,
        {("fin", "sit"): "http://fin-sit"},
        id="multi_env_no_default"),
    # 无环境:无默认、无部署行(别名地址全靠运行时回退)
    pytest.param(
        [],
        [("e1", "fin", None, "http://fin")],
        None,
        {},
        id="no_env"),
]


@pytest.mark.parametrize("envs,aliases,want_default,want_deploy",
                         _DEPLOY_FORMS)
def test_0044_deployments_env_chain(envs, aliases, want_default,
                                    want_deploy):
    """① 建表/加列/删 visibility ② 单环境置默认 ③ 别名地址聚合回填
    部署行(一致落一行、冲突不落、无环境落默认、无默认跳过)
    ④ downgrade 往返。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401
    from app.core.db import Base

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            _to_0043_shape(eng)
            with eng.begin() as conn:
                for name in envs:
                    conn.execute(text(
                        "INSERT INTO environments (name, description, "
                        "lines, created_at, updated_at) "
                        "VALUES (:n, '', '{}', now(), now())"), {"n": name})
                for alias, base, env, url in aliases:
                    conn.execute(text(
                        "INSERT INTO service_aliases (alias_name, "
                        "base_service, base_url, environment_id, kind, "
                        "created_at, updated_at) VALUES (:a, :b, :u, "
                        "(SELECT id FROM environments WHERE name = :e), "
                        "'plate', now(), now())"),
                        {"a": alias, "b": base, "u": url, "e": env})
            command.stamp(_cfg(sync_url), "0043_drop_visibility")
            command.upgrade(_cfg(sync_url), "0044_deployments_env_chain")

            with eng.connect() as c:
                env_cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'environments' "
                    "AND table_schema = current_schema()"))}
                assert "visibility" not in env_cols
                assert "is_default" in env_cols
                defaults = [r[0] for r in c.execute(text(
                    "SELECT name FROM environments WHERE is_default"))]
                assert defaults == ([want_default] if want_default else [])
                got = {(r[0], r[1]): r[2] for r in c.execute(text(
                    "SELECT d.base_service, e.name, d.base_url "
                    "FROM deployments d "
                    "JOIN environments e ON e.id = d.env_id"))}
                assert got == want_deploy
                assert c.execute(text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'projects' "
                    "AND column_name = 'default_environment_id' "
                    "AND table_schema = current_schema()")).scalar() == 1
            # 默认环境至多一行(部分唯一索引)
            if len(envs) >= 2:
                import pytest as _pytest
                with _pytest.raises(Exception):
                    with eng.begin() as conn:
                        conn.exec_driver_sql(
                            "UPDATE environments SET is_default = true")

            command.downgrade(_cfg(sync_url), "0043_drop_visibility")
            with eng.connect() as c:
                tables = {r[0] for r in c.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema()"))}
                assert "deployments" not in tables
                env_cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'environments' "
                    "AND table_schema = current_schema()"))}
                assert "visibility" in env_cols
                assert "is_default" not in env_cols
                # 别名地址原样(回填只读别名表)
                assert c.execute(text(
                    "SELECT count(*) FROM service_aliases "
                    "WHERE base_url IS NOT NULL")).scalar() == sum(
                        1 for a in aliases if a[3])
        finally:
            eng.dispose()


# ── 0045_auth_slot_bindings(authz M2a S3.0)──────────────────────────
def _to_0044_shape(eng) -> None:
    """create_all 是当前模型(槽位列与四元组键已存在);撤回到 0044
    形态:删 auth_sessions 五列 + 换回旧唯一键;删别名 slot 列。"""
    _add_legacy_alias_columns(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_auth_slot_default")
        conn.exec_driver_sql(
            "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS "
            "uq_auth_owner_system_env_slot")
        for col in ("is_default", "account_fields", "slot", "env_id",
                    "system"):
            conn.exec_driver_sql(
                f"ALTER TABLE auth_sessions DROP COLUMN {col}")
        conn.exec_driver_sql(
            "ALTER TABLE auth_sessions ADD CONSTRAINT "
            "uq_auth_owner_alias UNIQUE (owner_id, alias)")
        conn.exec_driver_sql(
            "ALTER TABLE service_aliases DROP COLUMN slot")


_SLOT_FORMS = [
    # 可推断:唯一引用别名 → system = base_service;无引用 → 未归类
    pytest.param(
        [("cred-a", "svc-a", "cred-a"),          # 引用 cred-a → svc-a
         ("cred-x", None, None)],                # 无引用 → ''
        {"cred-a": "svc-a", "cred-x": ""},
        id="inferable"),
    # 引用冲突:两个别名不同 base_service 引用同名凭证 → 未归类
    pytest.param(
        [("c1", "svc-a", "dup"), ("c2", "svc-b", "dup"),
         ("solo", "svc-a", "solo")],
        {"dup": "", "solo": "svc-a"},
        id="conflict_unassigned"),
]


@pytest.mark.parametrize("aliases,want_systems", _SLOT_FORMS)
def test_0045_auth_slot_bindings(aliases, want_systems):
    """① 五列 + 四元组键(NULLS NOT DISTINCT)+ 默认槽部分唯一索引
    ② slot=alias、system 推断、is_default=true ③ 别名 slot=credential_
    alias ④ 令牌范围行存活(id 稳定,F7)⑤ downgrade 往返。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401
    from app.core.db import Base

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            _to_0044_shape(eng)
            with eng.begin() as conn:
                # 两个 owner(u1/u2)各有 want_systems 里的凭证
                uids = {}
                for i, u in enumerate(("u1", "u2")):
                    conn.execute(text(
                        "INSERT INTO users (username, display_name, "
                        "password_hash, role, is_active, is_system, created_at, "
                        "updated_at) VALUES (:u, :u, 'x', 'user', true, "
                        "false, now(), now())"), {"u": u})
                    uids[u] = i + 1
                for alias in want_systems:
                    conn.execute(text(
                        "INSERT INTO auth_sessions "
                        "(owner_id, alias, url, username_enc, password_enc, "
                        " token_type, expires_in, created_at, updated_at) "
                        "VALUES (:o, :a, 'http://x', 'enc', 'enc', "
                        "'Bearer', 7200, now(), now())"),
                        {"o": uids["u1"], "a": alias})
                for alias_name, base, cred in aliases:
                    conn.execute(text(
                        "INSERT INTO service_aliases "
                        "(alias_name, base_service, credential_alias, kind, "
                        " created_at, updated_at) "
                        "VALUES (:a, :b, :c, 'plate', now(), now())"),
                        {"a": alias_name, "b": base or "svc-any",
                         "c": cred})
                # 令牌 + 范围行(auth_id → 某 auth_session id)
                conn.execute(text(
                    "INSERT INTO access_tokens (user_id, kind, name, "
                    "token_hash, token_hint, expires_at, created_at) "
                    "VALUES (:u, 'personal', 'tk', 'h1', 'h…', "
                    "now() + interval '7 days', now())"),
                    {"u": uids["u1"]})
                conn.execute(text(
                    "INSERT INTO access_token_scopes "
                    "(token_id, auth_id) "
                    "SELECT t.id, a.id FROM access_tokens t, auth_sessions a "
                    "WHERE a.alias = :alias"),
                    {"alias": next(iter(want_systems))})

            command.stamp(_cfg(sync_url), "0044_deployments_env_chain")
            command.upgrade(_cfg(sync_url), "0045_auth_slot_bindings")

            with eng.connect() as c:
                rows = {r[0]: r for r in c.execute(text(
                    "SELECT alias, system, env_id, slot, is_default "
                    "FROM auth_sessions ORDER BY id"))}
                for alias, want_sys in want_systems.items():
                    _, sys_, env, slot, dflt = rows[alias]
                    assert (sys_, env, slot, dflt) == (
                        want_sys, None, alias, True)
                # 四元组键:同 owner 同键重复被拒(NULL env 参与判重)
                import pytest as _pytest
                with _pytest.raises(Exception):
                    with c.begin():
                        c.execute(text(
                            "INSERT INTO auth_sessions "
                            "(owner_id, alias, url, username_enc, "
                            "password_enc, system, env_id, slot, "
                            "is_default, created_at, updated_at) "
                            "SELECT owner_id, alias, url, username_enc, "
                            "password_enc, system, env_id, slot, false, "
                            "now(), now() FROM auth_sessions LIMIT 1"))
                # 默认槽唯一:同 owner 同 slot 二次置默认被拒
                with _pytest.raises(Exception):
                    with c.begin():
                        c.execute(text(
                            "INSERT INTO auth_sessions "
                            "(owner_id, alias, url, username_enc, "
                            "password_enc, system, slot, is_default, "
                            "created_at, updated_at) VALUES "
                            "(1, 'other', 'http://x', 'e', 'e', '', "
                            "'dup', true, now(), now())"))
                # 别名 slot 回填
                got = {r[0]: r[1] for r in c.execute(text(
                    "SELECT alias_name, slot FROM service_aliases"))}
                assert got == {a: (cred if cred else None)
                               for a, _, cred in aliases}
                # 令牌范围行存活(id 未变,F7)
                assert c.execute(text(
                    "SELECT count(*) FROM access_token_scopes "
                    "WHERE auth_id IS NOT NULL")).scalar() == 1

            command.downgrade(_cfg(sync_url), "0044_deployments_env_chain")
            with eng.connect() as c:
                cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'auth_sessions' "
                    "AND table_schema = current_schema()"))}
                assert not ({"system", "env_id", "slot", "account_fields",
                             "is_default"} & cols)
                assert c.execute(text(
                    "SELECT count(*) FROM access_token_scopes "
                    "WHERE auth_id IS NOT NULL")).scalar() == 1
                assert c.execute(text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'service_aliases' "
                    "AND column_name = 'slot' "
                    "AND table_schema = current_schema()")).scalar() == 0
        finally:
            eng.dispose()


# ── 0046_carry_scope(authz M2a S4.0)──────────────────────────────────
def _to_0045_shape(eng) -> None:
    """create_all 是当前模型(scope 列与四元组键已存在);撤回到 0045
    形态:删两表 scope/scope_id 列,还原旧二元/一元唯一键。"""
    _add_legacy_alias_columns(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE carry_service_bindings DROP CONSTRAINT IF EXISTS "
            "uq_carry_svc_path")
        conn.exec_driver_sql(
            "ALTER TABLE carry_service_bindings ADD CONSTRAINT "
            "uq_carry_svc_path UNIQUE (service_name, field_path)")
        conn.exec_driver_sql(
            "ALTER TABLE carry_global_defaults DROP CONSTRAINT IF EXISTS "
            "uq_carry_default_path")
        conn.exec_driver_sql(
            "ALTER TABLE carry_global_defaults ADD CONSTRAINT "
            "uq_carry_default_path UNIQUE (field_path)")
        for t in ("carry_service_bindings", "carry_global_defaults"):
            conn.exec_driver_sql(
                f"ALTER TABLE {t} DROP COLUMN IF EXISTS scope_id")
            conn.exec_driver_sql(
                f"ALTER TABLE {t} DROP COLUMN IF EXISTS scope")


def test_0046_carry_scope():
    """① 两表加 scope/scope_id + 换键 ② 存量 → 公共项目层;个人别名键
    下的行 → 属主个人层 ③ 新键冲突被拒 ④ downgrade 公共层优先去重。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401
    from app.core.db import Base

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            _to_0045_shape(eng)
            with eng.begin() as conn:
                # 公共项目 id=1(conftest 同款种子口径:手工插)
                conn.execute(text(
                    "INSERT INTO projects (name, kind, description, "
                    "created_at) VALUES ('__public__', 'public', '', "
                    "now())"))
                for u in ("u1", "u2"):
                    conn.execute(text(
                        "INSERT INTO users (username, display_name, "
                        "password_hash, role, is_active, is_system, "
                        "created_at, updated_at) VALUES (:u, :u, 'x', "
                        "'user', true, false, now(), now())"), {"u": u})
                # 别名:fin(共享)、qa-alias(个人 = u2)
                conn.execute(text(
                    "INSERT INTO service_aliases (alias_name, "
                    "base_service, owner_user_id, kind, created_at, "
                    "updated_at) VALUES ('fin', 'fin', NULL, 'plate', "
                    "now(), now())"))
                conn.execute(text(
                    "INSERT INTO service_aliases (alias_name, "
                    "base_service, owner_user_id, kind, created_at, "
                    "updated_at) VALUES ('qa-alias', 'fin', 2, 'plate', "
                    "now(), now())"))
                # carry 行:共享键 / 个人别名键 / 全局默认
                for svc, path in (("fin", "$.a"), ("qa-alias", "$.b"),
                                  ("fin", "$.c")):
                    conn.execute(text(
                        "INSERT INTO carry_service_bindings (service_name, "
                        "field_path, value, updated_by_name, updated_at) "
                        "VALUES (:s, :p, 'v', 'seed', now())"),
                        {"s": svc, "p": path})
                conn.execute(text(
                    "INSERT INTO carry_global_defaults (field_path, value, "
                    "updated_by_name, updated_at) "
                    "VALUES ('$.d', 'v', 'seed', now())"))

            command.stamp(_cfg(sync_url), "0045_auth_slot_bindings")
            command.upgrade(_cfg(sync_url), "0046_carry_scope")

            with eng.connect() as c:
                got = {tuple(r) for r in c.execute(text(
                    "SELECT scope, scope_id, service_name, field_path "
                    "FROM carry_service_bindings"))}
                assert got == {
                    ("project", 1, "fin", "$.a"),
                    ("project", 1, "fin", "$.c"),
                    # 个人别名键 → 属主(u2)个人层
                    ("user", 2, "qa-alias", "$.b"),
                }
                assert [tuple(r) for r in c.execute(text(
                    "SELECT scope, scope_id, field_path "
                    "FROM carry_global_defaults"))] == [("project", 1,
                                                         "$.d")]
                # 新键:同 scope 同键重复被拒;不同 scope 同键可并存
                import pytest as _pytest
                with _pytest.raises(Exception):
                    with eng.connect() as c2:
                        with c2.begin():
                            c2.execute(text(
                                "INSERT INTO carry_service_bindings "
                                "(scope, scope_id, service_name, "
                                "field_path, value, updated_by_name, "
                                "updated_at) VALUES ('project', 1, 'fin', "
                                "'$.a', 'x', 't', now())"))
                with eng.connect() as c2:
                    with c2.begin():
                        c2.execute(text(
                            "INSERT INTO carry_service_bindings "
                            "(scope, scope_id, service_name, field_path, "
                            "value, updated_by_name, updated_at) VALUES "
                            "('user', 1, 'fin', '$.a', 'mine', 't', "
                            "now())"))

            command.downgrade(_cfg(sync_url), "0045_auth_slot_bindings")
            with eng.connect() as c:
                cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'carry_service_bindings' "
                    "AND table_schema = current_schema()"))}
                assert not ({"scope", "scope_id"} & cols)
                # 公共层优先:个人层/他层同键行被丢弃
                assert [tuple(r) for r in c.execute(text(
                    "SELECT service_name, field_path FROM "
                    "carry_service_bindings ORDER BY 1, 2"))] == [
                    ("fin", "$.a"), ("fin", "$.c"), ("qa-alias", "$.b")]
        finally:
            eng.dispose()


# ── 0047_alias_slimming(authz M2a S6)──────────────────────────────────
def test_0047_alias_slimming():
    """① slot 兜底回填 ② 无默认环境 + 无环境别名地址 → 建默认环境
    ③ 地址回落部署表(无环境:别名胜;挂环境:部署表已有不覆盖;冲突不落)
    ④ 方案 payload 剥 url/authAlias ⑤ 审计报告 + 属主/Admin 通知
    ⑥ 删四列 ⑦ downgrade 回加列(credential_alias = slot,base_url 取默认
    环境部署地址)。"""
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app.core.db import Base
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.models.composer_scenario import ComposerScenario
    from app.models.user import User

    with temp_schema() as (_schema, sync_url):
        eng = create_engine(sync_url)
        try:
            Base.metadata.create_all(eng)
            _add_legacy_alias_columns(eng)
            with Session(eng) as s:
                u1 = User(username="u1", display_name="u1",
                          password_hash="x", role="user")
                adm = User(username="adm", display_name="adm",
                           password_hash="x", role="admin")
                plat = User(username="__platform__", display_name="",
                            password_hash="x", role="admin", is_system=True)
                s.add_all([u1, adm, plat])
                s.flush()
                s.add(ComposerScenario(scenario_id="sc-a", owner_id=u1.id,
                                       payload={}))
                s.flush()
                s.add_all([
                    ComposerRunScheme(
                        scheme_id="rs-dirty", scenario_id="sc-a",
                        name="脏方案", payload={"serviceBindings": {
                            "fin": {"url": "http://x", "authAlias": "qa1"},
                            "crm": {"alias": "crm", "url": "http://y"},
                            "probe": {"url": "http://probe"}}}),
                    ComposerRunScheme(
                        scheme_id="rs-clean", scenario_id="sc-a",
                        name="干净", payload={"serviceBindings": {
                            "crm": {"alias": "crm"}}}),
                ])
                s.commit()
                u1_id, adm_id = u1.id, adm.id
            with eng.begin() as conn:
                # 两个环境、无默认 → 迁移建默认环境
                for name in ("dev", "sit"):
                    conn.execute(text(
                        "INSERT INTO environments (name, description, "
                        "lines, created_at, updated_at) "
                        "VALUES (:n, '', '{}', now(), now())"), {"n": name})
                dev = conn.execute(text(
                    "SELECT id FROM environments WHERE name='dev'")).scalar()
                conn.execute(text(
                    "INSERT INTO deployments (base_service, env_id, "
                    "base_url, created_at, updated_at) VALUES "
                    "('pay', :d, 'http://pay-dep', now(), now())"),
                    {"d": dev})
                for alias, base, env, url, cred, owner in (
                        ("fin-a", "fin", None, "http://fin", None, None),
                        ("fin-b", "fin", None, "http://fin", "qa1", None),
                        ("hr-1", "hr", None, "http://hr-1", None, None),
                        ("hr-2", "hr", None, "http://hr-2", None, None),
                        ("fin-dev", "fin", dev, "http://fin-dev", None, None),
                        ("pay-dev", "pay", dev, "http://pay-alias", None,
                         None),
                        ("mine", "fin", None, None, None, u1_id)):
                    conn.execute(text(
                        "INSERT INTO service_aliases (alias_name, "
                        "base_service, base_url, environment_id, "
                        "credential_alias, owner_user_id, kind, "
                        "created_at, updated_at) VALUES (:a, :b, :u, :e, "
                        ":c, :o, 'plate', now(), now())"),
                        {"a": alias, "b": base, "u": url, "e": env,
                         "c": cred, "o": owner})

            command.stamp(_cfg(sync_url), "0046_carry_scope")
            command.upgrade(_cfg(sync_url), "0047_alias_slimming")

            with eng.connect() as c:
                cols = {r[0] for r in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'service_aliases' "
                    "AND table_schema = current_schema()"))}
                assert not ({"base_url", "environment_id", "owner_user_id",
                             "credential_alias"} & cols)
                # ① slot 兜底
                assert c.execute(text(
                    "SELECT slot FROM service_aliases "
                    "WHERE alias_name='fin-b'")).scalar() == "qa1"
                # ② 默认环境新建
                default = c.execute(text(
                    "SELECT name FROM environments WHERE is_default")).all()
                assert [r[0] for r in default] == ["默认环境"]
                # ③ 部署表
                got = {(r[0], r[1]): r[2] for r in c.execute(text(
                    "SELECT d.base_service, e.name, d.base_url "
                    "FROM deployments d JOIN environments e "
                    "ON e.id = d.env_id"))}
                assert got == {
                    ("fin", "默认环境"): "http://fin",
                    ("fin", "dev"): "http://fin-dev",
                    ("pay", "dev"): "http://pay-dep",   # 部署表已有不覆盖
                    # ④b 方案绑定 url 补缺落默认环境(fin 已有行 → 不落)
                    ("crm", "默认环境"): "http://y",
                    ("probe", "默认环境"): "http://probe",
                }                                       # hr 冲突不落
                # ④ 方案清洗
                pl = {r[0]: r[1] for r in c.execute(text(
                    "SELECT scheme_id, payload FROM composer_run_schemes"))}
                assert pl["rs-dirty"]["serviceBindings"] == {
                    "crm": {"alias": "crm"}}
                assert pl["rs-clean"]["serviceBindings"] == {
                    "crm": {"alias": "crm"}}
                # ⑤ 报告 + 通知
                detail = c.execute(text(
                    "SELECT detail FROM audit_logs "
                    "WHERE action = 'migration.alias_slimming'")).scalar()
                assert [g["baseService"] for g in detail["conflicts"]] == [
                    "hr"]
                assert {x["alias"] for x in detail["superseded"]} >= {
                    "pay-dev", "hr-1", "hr-2"}
                assert {x["alias"] for x in detail["envSelectors"]} == {
                    "fin-dev", "pay-dev"}
                assert {x["baseService"] for x in
                        detail["schemeUrlsLanded"]} == {"crm", "probe"}
                assert [x["baseService"] for x in
                        detail["schemeUrlsSkipped"]] == ["fin"]
                assert detail["personalAliasesShared"] == [
                    {"alias": "mine", "ownerId": u1_id}]
                assert [x["schemeId"] for x in detail["schemesCleansed"]] \
                    == ["rs-dirty"]
                notes = {(r[0], r[1]) for r in c.execute(text(
                    "SELECT user_id, link FROM notifications"))}
                assert (u1_id, "/auths") in notes          # 方案属主
                assert (adm_id, "/admin/deployments") in notes   # Admin+
                assert all(uid in (u1_id, adm_id) for uid, _ in notes)

            command.downgrade(_cfg(sync_url), "0046_carry_scope")
            with eng.connect() as c:
                rows = {r[0]: (r[1], r[2]) for r in c.execute(text(
                    "SELECT alias_name, credential_alias, base_url "
                    "FROM service_aliases"))}
                assert rows["fin-b"] == ("qa1", "http://fin")
                assert rows["pay-dev"][1] is None    # 非默认环境不回填
        finally:
            eng.dispose()
