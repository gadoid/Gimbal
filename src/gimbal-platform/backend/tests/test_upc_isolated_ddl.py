"""§20.2/§20.6 隔离目标结构 DDL 语义验证(UPC M1,v2.10 §20.4)。

M1 只验证**隔离的目标表结构**(Scheme 领域迁移随 M2;此处用独立命名的
影子表复刻 §20.2 双复合 FK 与 §20.6 双父同区约束的物理形态),在真实
PostgreSQL 上断言:

* 默认即时检查:跨区绑定/跨区套件成员直接拒绝;
* 显式 ``SET CONSTRAINTS ... DEFERRED`` 后合法原子移动(父对象 + 关联
  行同事务)提交成功;
* 非法提交(只挪父对象、留下跨区边)完整失败,回滚后状态不变;
* 合法空绑定(MATCH SIMPLE)通过;引用中对象删除受 NO ACTION 保护;
* 父资产删除维持关联行 CASCADE(§20.6)。

不解析 JSON、不用服务校验替代库层(§20.2 测试要求);影子表随测随删,
不污染池 schema 元数据(fresh_db 的 TRUNCATE 只扫 Base.metadata)。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError

from tests.conftest import TEST_DATABASE_URL  # noqa: F401  环境就位断言


_ISO_DDL = (
    # §20.2:Scenario 候选键(整数主键 + 字符串业务 ID 双身份)
    """
    CREATE TABLE IF NOT EXISTS upc_iso_scenarios (
        id int PRIMARY KEY,
        project_id int NOT NULL,
        scenario_id varchar(128) NOT NULL,
        owner_id int,
        CONSTRAINT uq_iso_scenario_project_sid
          UNIQUE (project_id, scenario_id)
    )
    """,
    # §20.2:AccountCombo 非延迟候选键
    """
    CREATE TABLE IF NOT EXISTS upc_iso_combos (
        id int PRIMARY KEY,
        project_id int NOT NULL,
        name varchar(128),
        CONSTRAINT uq_iso_combo_project_id UNIQUE (project_id, id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS upc_iso_schemes (
        id int PRIMARY KEY,
        project_id int NOT NULL,
        scenario_id varchar(128) NOT NULL,
        account_combo_id int,
        CONSTRAINT fk_iso_scheme_scenario_zone
          FOREIGN KEY (project_id, scenario_id)
          REFERENCES upc_iso_scenarios (project_id, scenario_id)
          ON DELETE NO ACTION DEFERRABLE INITIALLY IMMEDIATE,
        CONSTRAINT fk_iso_scheme_combo_zone
          FOREIGN KEY (project_id, account_combo_id)
          REFERENCES upc_iso_combos (project_id, id)
          MATCH SIMPLE ON DELETE NO ACTION DEFERRABLE INITIALLY IMMEDIATE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_iso_scheme_combo_zone
      ON upc_iso_schemes (project_id, account_combo_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_iso_scheme_scenario_zone
      ON upc_iso_schemes (project_id, scenario_id)
    """,
    # §20.6:Suite 候选键 + 双父同区成员表(保留级联删除语义)
    """
    CREATE TABLE IF NOT EXISTS upc_iso_suites (
        id int PRIMARY KEY,
        project_id int NOT NULL,
        name varchar(128),
        CONSTRAINT uq_iso_suite_project_id UNIQUE (project_id, id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS upc_iso_suite_members (
        project_id int NOT NULL,
        suite_id int NOT NULL,
        scenario_id varchar(128) NOT NULL,
        role varchar(16) NOT NULL DEFAULT 'main',
        sort int NOT NULL DEFAULT 0,
        PRIMARY KEY (suite_id, scenario_id),
        CONSTRAINT fk_iso_sm_suite_zone
          FOREIGN KEY (project_id, suite_id)
          REFERENCES upc_iso_suites (project_id, id)
          ON DELETE CASCADE ON UPDATE NO ACTION
          DEFERRABLE INITIALLY IMMEDIATE,
        CONSTRAINT fk_iso_sm_scenario_zone
          FOREIGN KEY (project_id, scenario_id)
          REFERENCES upc_iso_scenarios (project_id, scenario_id)
          ON DELETE CASCADE ON UPDATE NO ACTION
          DEFERRABLE INITIALLY IMMEDIATE
    )
    """,
)

_SEED = (
    # 两个「项目」仅以整数区分(影子表不 FK 到真 projects —— 隔离验证)
    "INSERT INTO upc_iso_scenarios VALUES (1, 1, 'S1', NULL)",
    "INSERT INTO upc_iso_scenarios VALUES (2, 2, 'S2', NULL)",
    "INSERT INTO upc_iso_combos VALUES (1, 1, '组合A')",
    "INSERT INTO upc_iso_combos VALUES (2, 2, '组合B')",
    "INSERT INTO upc_iso_suites VALUES (1, 1, '套件U1')",
)


async def _session():
    """池引擎上的一个新会话(fresh_db 已把 SessionLocal 钉到测试池)。"""
    from app.core import db as db_module

    return db_module.SessionLocal()


@pytest.fixture
async def iso_tables(client):  # noqa: ARG001 — client 就位池 schema/引擎
    """建影子表 + 种子,测试后整体拆除(同会话建删,避免跨测试残留)。"""
    async with await _session() as s:
        for stmt in _ISO_DDL + _SEED:
            await s.execute(sa_text(stmt))
        await s.commit()
    yield
    async with await _session() as s:
        for tbl in ("upc_iso_suite_members", "upc_iso_schemes",
                    "upc_iso_suites", "upc_iso_combos",
                    "upc_iso_scenarios"):
            await s.execute(sa_text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        await s.commit()


async def _execute(sqls: list[str]):
    """同一事务顺序执行并提交(SET CONSTRAINTS 的事务面)。"""
    async with await _session() as s:
        for stmt in sqls:
            await s.execute(sa_text(stmt))
        await s.commit()


class TestSchemeComboZone:
    """§20.2:Scheme → AccountCombo / Scenario 双复合 FK。"""

    async def test_same_zone_binding_ok(self, iso_tables):
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (10, 1, 'S1', 1)"])
        # 合法空绑定(MATCH SIMPLE:引用列含 NULL 跳过校验)
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (11, 1, 'S1', NULL)"])

    async def test_cross_zone_combo_rejected_immediately(self, iso_tables):
        """跨区组合绑定默认即时拒绝(S1 在项目1,组合B 在项目2)。"""
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO upc_iso_schemes VALUES (12, 1, 'S1', 2)"))
            await s.rollback()

    async def test_fake_scheme_project_id_rejected(self, iso_tables):
        """伪造 Scheme.project_id(与父场景不一致)被第一组 FK 拒绝。"""
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO upc_iso_schemes VALUES (13, 2, 'S1', 1)"))
            await s.rollback()

    async def test_legal_atomic_move_with_deferred(self, iso_tables):
        """场景整体移动:显式延迟后父场景 + Scheme 同事务挪区,提交成功。"""
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (14, 1, 'S1', 1)"])
        await _execute([
            "SET CONSTRAINTS fk_iso_scheme_scenario_zone, "
            "fk_iso_scheme_combo_zone DEFERRED",
            "UPDATE upc_iso_scenarios SET project_id = 2 WHERE id = 1",
            "UPDATE upc_iso_schemes SET project_id = 2 WHERE id = 14",
            # 组合A(项目1)不再同区:一并解绑或挪组合 —— 此处挪组合
            "UPDATE upc_iso_combos SET project_id = 2 WHERE id = 1",
        ])
        async with await _session() as s:
            pid, combo = (await s.execute(sa_text(
                "SELECT project_id, account_combo_id FROM upc_iso_schemes "
                "WHERE id = 14"))).one()
            assert (pid, combo) == (2, 1)

    async def test_illegal_deferred_commit_fails_and_rolls_back(
            self, iso_tables):
        """只挪父对象、留下跨区 Scheme → 提交失败,回滚后原状态不变。"""
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (15, 1, 'S1', 1)"])
        async with await _session() as s:
            await s.execute(sa_text(
                "SET CONSTRAINTS fk_iso_scheme_scenario_zone, "
                "fk_iso_scheme_combo_zone DEFERRED"))
            await s.execute(sa_text(
                "UPDATE upc_iso_scenarios SET project_id = 2 WHERE id = 1"))
            with pytest.raises(IntegrityError):
                await s.commit()
        # 事务整体回滚:场景仍在项目1
        async with await _session() as s:
            pid = (await s.execute(sa_text(
                "SELECT project_id FROM upc_iso_scenarios WHERE id = 1")
            )).scalar_one()
            assert pid == 1

    async def test_referenced_combo_delete_blocked(self, iso_tables):
        """引用中的组合不可直接删除(NO ACTION;§5.1「引用中的组合
        不可直接删除」,禁止级联解绑)。"""
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (16, 1, 'S1', 1)"])
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text("DELETE FROM upc_iso_combos "
                                        "WHERE id = 1"))
            await s.rollback()

    async def test_scenario_delete_blocked_while_scheme_exists(
            self, iso_tables):
        """删除场景须先处置 Scheme(§20.2)。"""
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (17, 1, 'S1', NULL)"])
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text("DELETE FROM upc_iso_scenarios "
                                        "WHERE id = 1"))
            await s.rollback()


class TestSuiteMemberZone:
    """§20.6:SuiteMember 双父同区复合 FK。"""

    async def test_same_zone_member_ok(self, iso_tables):
        await _execute([
            "INSERT INTO upc_iso_suite_members VALUES "
            "(1, 1, 'S1', 'main', 0)"])

    async def test_cross_zone_member_rejected(self, iso_tables):
        """套件(项目1)挂项目2 的场景 → 双 FK 联合拒绝。"""
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO upc_iso_suite_members VALUES "
                    "(1, 1, 'S2', 'main', 0)"))  # S2 在项目2
            await s.rollback()
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO upc_iso_suite_members VALUES "
                    "(2, 1, 'S1', 'main', 0)"))  # 声称项目2 的套件边
            await s.rollback()

    async def test_single_parent_move_fails_at_commit(self, iso_tables):
        """只挪套件父端(成员行留在原区)→ 提交失败并完整回滚。"""
        await _execute([
            "INSERT INTO upc_iso_suite_members VALUES (1, 1, 'S1', 'main', 0)",
        ])
        async with await _session() as s:
            await s.execute(sa_text(
                "SET CONSTRAINTS fk_iso_sm_suite_zone, "
                "fk_iso_sm_scenario_zone DEFERRED"))
            await s.execute(sa_text(
                "UPDATE upc_iso_suites SET project_id = 2 WHERE id = 1"))
            with pytest.raises(IntegrityError):
                await s.commit()
        async with await _session() as s:
            assert (await s.execute(sa_text(
                "SELECT project_id FROM upc_iso_suites WHERE id = 1")
            )).scalar_one() == 1

    async def test_whole_graph_move_succeeds(self, iso_tables):
        """完整依赖一并挪(套件 + 成员 + 场景 + Scheme + 组合)→ 提交成功。"""
        await _execute([
            "INSERT INTO upc_iso_schemes VALUES (18, 1, 'S1', 1)",
            "INSERT INTO upc_iso_suite_members VALUES (1, 1, 'S1', 'main', 0)",
        ])
        await _execute([
            "SET CONSTRAINTS fk_iso_sm_suite_zone, "
            "fk_iso_sm_scenario_zone, fk_iso_scheme_scenario_zone, "
            "fk_iso_scheme_combo_zone DEFERRED",
            "UPDATE upc_iso_scenarios SET project_id = 2 WHERE id = 1",
            "UPDATE upc_iso_schemes SET project_id = 2 WHERE id = 18",
            "UPDATE upc_iso_combos SET project_id = 2 WHERE id = 1",
            "UPDATE upc_iso_suites SET project_id = 2 WHERE id = 1",
            "UPDATE upc_iso_suite_members SET project_id = 2 "
            "WHERE suite_id = 1",
        ])
        async with await _session() as s:
            rows = (await s.execute(sa_text(
                "SELECT project_id FROM upc_iso_suite_members "
                "WHERE suite_id = 1"))).scalars().all()
            assert rows == [2]

    async def test_parent_delete_cascades_members_but_respects_scheme(
            self, iso_tables):
        """父资产删除:成员行 CASCADE 收口;Scheme 引用按 NO ACTION
        保护(删套件级联成员;删被 Scheme 引用的场景拒绝)。"""
        await _execute([
            "INSERT INTO upc_iso_suite_members VALUES (1, 1, 'S1', 'main', 0)",
        ])
        await _execute(["DELETE FROM upc_iso_suites WHERE id = 1"])
        async with await _session() as s:
            n = (await s.execute(sa_text(
                "SELECT count(*) FROM upc_iso_suite_members"))).scalar_one()
            assert n == 0
        # 场景删除:无 Scheme → 成员行级联,成功
        await _execute(["DELETE FROM upc_iso_scenarios WHERE id = 1"])
        # 被 Scheme 引用的场景不可删
        await _execute([
            "INSERT INTO upc_iso_scenarios VALUES (3, 2, 'S3', NULL)",
            "INSERT INTO upc_iso_schemes VALUES (19, 2, 'S3', NULL)"])
        async with await _session() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text("DELETE FROM upc_iso_scenarios "
                                        "WHERE id = 3"))
            await s.rollback()
