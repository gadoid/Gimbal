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
    from sqlalchemy import create_engine, inspect, text

    with temp_schema() as (_schema, sync_url):
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
            assert _revision(sync_url) == "0041_public_shadow_backfill"
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
                    name="plat-tpl", owner_id=root.id, visibility="private",
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
                    name="own-tpl", owner_id=root.id, visibility="public",
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
                                     owner_id=author.id,
                                     visibility="public", payload={}),
                    ComposerScenario(scenario_id="sc-priv",
                                     owner_id=author.id, payload={}),
                    Suite(name="套件-公开", owner_id=author.id,
                          visibility="public"),
                    Suite(name="套件-私有", owner_id=author.id),
                    # 0037 遗留:无主公共报告定义(编辑面冻结)
                    ReportDefinitionRow(name="rd-orphan", owner_id=None,
                                        visibility="public"),
                    ReportDefinitionRow(name="rd-pub", owner_id=author.id,
                                        visibility="public"),
                    ReportDefinitionRow(name="rd-priv", owner_id=author.id),
                ])
                tpl_pub = IntegrationTask(  # 个人公共模板(维护者=创建人)
                    name="个人公共", owner_id=author.id, visibility="public",
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
                    name="平台模板", owner_id=plat.id, visibility="public",
                    target_type="scenario", scenario_id="sc-pub",
                    target_system="fin", trigger_cron="*/5 * * * *",
                    result_policy="latest", card_template="status",
                    state="idle")
                tpl_refugee = IntegrationTask(  # 删用户软删后挂靠的模板
                    name="挂靠", owner_id=plat.id, visibility="public",
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
                    ComposerScenario(scenario_id="sc-win", owner_id=author.id,
                                     visibility="public", payload={}),
                    ComposerScenario(scenario_id="sc-keep", owner_id=author.id,
                                     payload={}),
                    IntegrationTask(name="tpl-win", owner_id=author.id,
                                    visibility="public",
                                    target_type="scenario",
                                    scenario_id="sc-win",
                                    target_system="fin",
                                    trigger_cron="*/5 * * * *",
                                    result_policy="latest",
                                    card_template="status", state="idle"),
                ])
                s.commit()
            with eng.connect() as c:
                # 回填前:漏网行 project_id 为空
                assert c.execute(text(
                    "SELECT count(*) FROM composer_scenarios "
                    "WHERE visibility='public' "
                    "AND project_id IS NULL")).scalar() == 1
            command.upgrade(_cfg(sync_url), "head")
            assert _revision(sync_url) == "0041_public_shadow_backfill"

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
            # 幂等:重复跑 0041 不重复改(种子仍恰一行)
            command.stamp(_cfg(sync_url), "0040_project_zone")
            command.upgrade(_cfg(sync_url), "head")
            with eng.connect() as c:
                assert c.execute(text(
                    "SELECT count(*) FROM projects "
                    "WHERE kind='public'")).scalar() == 1
        finally:
            eng.dispose()
