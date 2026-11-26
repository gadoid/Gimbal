"""§20.5 主线 Scheme 升级 fixtures(UPC M2,v2.10 §20.5 / AC-43)。

从**真实 0066 结构**出发沿链升到 head,断言主线方案的分类结果:

* 合法旧行(无组合绑定证据):保留方案数量、默认项与选择内容;
  每行取得从父场景派生的 ``project_id`` 与新生成的 ``scheme_uid``;
  组合绑定为空且 ``repair_status = 'ready'``(主线原生无绑定 →
  §20.5 显式分类);
* 异常输入(payload 携带**非空** ``accountComboId`` 的旧 JSON 绑定
  证据):升级**整笔回滚** —— revision 停在 0066、行数据原样保留,
  不得按默认组合或数值 ID 猜测。

形态机制:baseline create_all 产出**当前**形态;先按 0066 时代语义
回退 M2 列/复合边(候选键随列 CASCADE),stamp 0066 后造数再升 head。
结构一致性由 test_upc_dual_path 的扩展断言面覆盖(AC-36/42),本模块
只钉**升级数据语义**。
"""
from __future__ import annotations

import pytest  # noqa: F401  环境对齐(conftest 断言 TEST_DATABASE_URL)

from tests.test_migrations import _cfg, temp_schema  # noqa: F401

_BACKEND = __import__("pathlib").Path(__file__).resolve().parents[1]


def _to_0066_shape(eng) -> None:
    """baseline(当前模型)→ 0066 时代形态:M2 列/复合边/候选键回退。

    suite_members 无 project_id、run_schemes 无 M2 六列(复合 FK 与
    ck 随列 CASCADE 退场)、对象表归属列放回可空(「空 = 私有区」)、
    候选键摘除、suites 名唯一回到属主域、run_schemes 补回 0066 期的
    单列 scenario FK。
    """
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE suite_members DROP COLUMN IF EXISTS project_id"
            " CASCADE")
        for col in ("account_combo_id", "repair_status", "repair_reason",
                    "revision", "scheme_uid", "project_id"):
            conn.exec_driver_sql(
                f"ALTER TABLE composer_run_schemes DROP COLUMN IF EXISTS"
                f" {col} CASCADE")
        conn.exec_driver_sql(
            "ALTER TABLE composer_run_schemes DROP CONSTRAINT IF EXISTS"
            " composer_run_schemes_scenario_id_fkey")
        conn.exec_driver_sql(
            "ALTER TABLE composer_run_schemes ADD CONSTRAINT"
            " composer_run_schemes_scenario_id_fkey FOREIGN KEY"
            " (scenario_id) REFERENCES composer_scenarios (scenario_id)"
            " ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED")
        conn.exec_driver_sql(
            "DROP INDEX IF EXISTS uq_scenario_project_scenario_id")
        conn.exec_driver_sql(
            "ALTER TABLE composer_scenarios ALTER COLUMN project_id"
            " DROP NOT NULL")
        conn.exec_driver_sql(
            "DROP INDEX IF EXISTS uq_suites_project_id")
        conn.exec_driver_sql(
            "ALTER TABLE suites DROP CONSTRAINT IF EXISTS"
            " uq_suites_project_name")
        conn.exec_driver_sql(
            "DROP INDEX IF EXISTS uq_suites_owner_name")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_suites_owner_name"
            " ON suites (owner_id, name)")
        conn.exec_driver_sql(
            "ALTER TABLE suites ALTER COLUMN project_id DROP NOT NULL")
        conn.exec_driver_sql(
            "ALTER TABLE report_definitions ALTER COLUMN project_id"
            " DROP NOT NULL")
        conn.exec_driver_sql(
            "ALTER TABLE integration_tasks ALTER COLUMN project_id"
            " DROP NOT NULL")
        conn.exec_driver_sql(
            "ALTER TABLE integration_tasks DROP CONSTRAINT IF EXISTS"
            " ck_integration_task_shape")


_SEED_LEGAL = (
    # 0066 时代造数:用户 + 两条无绑定证据的方案(默认 + 非默认带选择)
    """
    INSERT INTO users (username, display_name, password_hash, role,
                       is_active, is_system)
    VALUES ('upg_owner', 'UPG', 'x', 'user', true, false)
    """,
    """
    INSERT INTO composer_scenarios (scenario_id, owner_name, owner_id,
                                    payload)
    VALUES ('sc-upg', 'UPG', (SELECT id FROM users
                              WHERE username = 'upg_owner'),
            '{"definition": {"meta": {"scenarioId": "sc-upg",
                                      "name": "升级样例"},
                             "steps": [], "config": {}}}')
    """,
    """
    INSERT INTO composer_run_schemes
        (scheme_id, scenario_id, name, is_default, payload)
    VALUES ('rs-upg-def', 'sc-upg', '默认方案', true,
            '{"dataSetSelection": [], "injectionEntryIds": [],'
            ' "serviceBindings": {}, "options": {}}')
    """,
    """
    INSERT INTO composer_run_schemes
        (scheme_id, scenario_id, name, is_default, payload)
    VALUES ('rs-upg-qa', 'sc-upg', '回归方案', false,
            '{"dataSetSelection": [{"datasetId": "ds-upg", "rowIndexes": [0]}],'
            ' "injectionEntryIds": ["assert-1"], "serviceBindings": {},'
            ' "options": {}}')
    """,
)

_EVIDENCE_SCHEME = """
    INSERT INTO composer_run_schemes
        (scheme_id, scenario_id, name, is_default, payload)
    VALUES ('rs-upg-bad', 'sc-upg', '异常绑定', false,
            '{"accountComboId": 12, "dataSetSelection": [],'
            ' "serviceBindings": {}, "options": {}}')
    """


def _seed_era(conn, with_evidence: bool) -> None:
    for stmt in _SEED_LEGAL:
        conn.exec_driver_sql(stmt)
    if with_evidence:
        conn.exec_driver_sql(_EVIDENCE_SCHEME)


def _head() -> str:
    from alembic import command
    from alembic.script import ScriptDirectory

    _ = command  # noqa: F401
    return ScriptDirectory(str(_BACKEND / "alembic")).get_current_head()


def test_upgrade_legal_rows_get_project_uid_ready():
    """AC-43 合法腿:数量/默认项/选择保留;组合为空且 ready;取得
    项目(= 0067 就位的默认私有空间)与不可复用 UID。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0001_baseline")
        eng = create_engine(sync_url)
        try:
            _to_0066_shape(eng)
            with eng.begin() as conn:
                _seed_era(conn, with_evidence=False)
            command.stamp(_cfg(sync_url), "0066_incremental_model_align")
            command.upgrade(_cfg(sync_url), "head")

            with eng.begin() as conn:
                # 方案数量与默认项保留
                rows = conn.execute(text("""
                    SELECT scheme_id, is_default, project_id,
                           scheme_uid IS NOT NULL AS has_uid,
                           account_combo_id, repair_status, repair_reason,
                           revision, payload
                      FROM composer_run_schemes ORDER BY scheme_id
                """)).all()
                assert len(rows) == 2
                by_sid = {r[0]: r for r in rows}
                assert by_sid["rs-upg-def"][1] is True
                assert by_sid["rs-upg-qa"][1] is False
                # 归属 = 父场景(0067 默认空间)
                scen_pid = conn.execute(text(
                    "SELECT project_id FROM composer_scenarios"
                    " WHERE scenario_id = 'sc-upg'")).scalar_one()
                for r in rows:
                    assert r[2] == scen_pid
                    assert r[3] is True          # scheme_uid 回填且非空
                    assert r[4] is None          # 组合为空
                    assert r[5] == "ready"      # §20.5 分类
                    assert r[6] is None
                    assert r[7] == 1
                # UID 不可复用:两行互不相同
                uids = {conn.execute(text(
                    f"SELECT scheme_uid FROM composer_run_schemes"
                    f" WHERE scheme_id = '{sid}'")).scalar_one()
                    for sid in ("rs-upg-def", "rs-upg-qa")}
                assert len(uids) == 2
                # 选择与默认项内容原样(§20.5「保留选择与默认项」)
                qa = by_sid["rs-upg-qa"][8]
                assert qa["dataSetSelection"] == [
                    {"datasetId": "ds-upg", "rowIndexes": [0]}]
                assert qa["injectionEntryIds"] == ["assert-1"]
                defn = by_sid["rs-upg-def"][8]
                assert defn["dataSetSelection"] == []
        finally:
            eng.dispose()


def test_upgrade_binding_evidence_aborts_and_rolls_back():
    """AC-43 异常腿:非空 accountComboId 证据 → 中止并**整笔回滚**
    (revision 停在 0066;数据原样;无半成品列/状态)。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0001_baseline")
        eng = create_engine(sync_url)
        try:
            _to_0066_shape(eng)
            with eng.begin() as conn:
                _seed_era(conn, with_evidence=True)
            command.stamp(_cfg(sync_url), "0066_incremental_model_align")

            with pytest.raises(RuntimeError) as ei:
                command.upgrade(_cfg(sync_url), "head")
            assert "legacy_binding_evidence" in str(ei.value)

            # 整笔回滚:版本钉在 0066,行数据原样,M2 列未半途落上
            with eng.begin() as conn:
                ver = conn.execute(text(
                    "SELECT version_num FROM alembic_version")).scalar_one()
                assert ver == "0066_incremental_model_align"
                n = conn.execute(text(
                    "SELECT count(*) FROM composer_run_schemes"
                    " WHERE scheme_id = 'rs-upg-bad'")).scalar_one()
                assert n == 1
                cols = {c[0] for c in conn.execute(text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'composer_run_schemes'"
                    " AND table_schema = current_schema()"))}
                # M2 列未落(回滚后保持 0066 形态,无半成品)
                assert "scheme_uid" not in cols
                assert "repair_status" not in cols
        finally:
            eng.dispose()


def test_upgrade_renames_same_name_suites_in_one_project():
    """评审 P1-4 回归:0066 旧唯一轴 (owner_id, name) 允许同一 normal
    项目下不同 owner 同名 —— 升级建 UNIQUE(project_id, name) 前按确定性
    策略重命名(id 最小者保名,其余「名-迁移2…」),不再 UniqueViolation
    整笔失败;保名行原样、约束就位。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0001_baseline")
        eng = create_engine(sync_url)
        try:
            _to_0066_shape(eng)
            with eng.begin() as conn:
                for stmt in (
                    # 两个真人用户(非系统;触发器要求默认私有空间在
                    # 0067 造,0066 期无此约束,直插合法)
                    """
                    INSERT INTO users (username, display_name,
                                       password_hash, role, is_active,
                                       is_system)
                    VALUES ('upg_sw_a', 'A', 'x', 'user', true, false),
                           ('upg_sw_b', 'B', 'x', 'user', true, false)
                    """,
                    # normal 项目(0066 期无 kind 形状 CHECK 的新列约束
                    # —— baseline 按当前模型建表,kind 三值已合法)
                    """
                    INSERT INTO projects (name, kind, description,
                                          created_at)
                    VALUES ('upg-sw-proj', 'normal', '', now())
                    """,
                    """
                    INSERT INTO project_members (project_id, user_id,
                                                 role)
                    SELECT p.id, u.id, 'admin'
                      FROM projects p, users u
                     WHERE p.name = 'upg-sw-proj'
                       AND u.username IN ('upg_sw_a', 'upg_sw_b')
                    """,
                    # 同项目、不同 owner、同名两套件(旧轴合法)
                    """
                    INSERT INTO suites (name, owner_id, project_id, mode, mode_config,
                                        rev, description)
                    SELECT '同名集', u.id, p.id, 'standard', '{}', 1, ''
                      FROM projects p, users u
                     WHERE p.name = 'upg-sw-proj'
                       AND u.username = 'upg_sw_a'
                    """,
                    """
                    INSERT INTO suites (name, owner_id, project_id, mode, mode_config,
                                        rev, description)
                    SELECT '同名集', u.id, p.id, 'standard', '{}', 1, ''
                      FROM projects p, users u
                     WHERE p.name = 'upg-sw-proj'
                       AND u.username = 'upg_sw_b'
                    """,
                ):
                    conn.exec_driver_sql(stmt)
            command.stamp(_cfg(sync_url), "0066_incremental_model_align")
            # 修前:此处在 uq_suites_project_name 上 UniqueViolation
            command.upgrade(_cfg(sync_url), "head")

            with eng.begin() as conn:
                rows = conn.execute(text("""
                    SELECT s.name, u.username
                      FROM suites s JOIN users u ON u.id = s.owner_id
                     ORDER BY s.id
                """)).all()
                assert rows[0] == ("同名集", "upg_sw_a")   # id 最小者保名
                assert rows[1][0] == "同名集-迁移2"          # 确定性重命名
                assert rows[1][1] == "upg_sw_b"
                # 新唯一轴就位(结构一致性归 test_upc_dual_path,这里钉
                # 「升级后项目内唯一」语义)
                dup = conn.execute(text("""
                    SELECT count(*) FROM (
                        SELECT project_id, name FROM suites
                         GROUP BY project_id, name
                        HAVING count(*) > 1) d
                """)).scalar_one()
                assert dup == 0
        finally:
            eng.dispose()
