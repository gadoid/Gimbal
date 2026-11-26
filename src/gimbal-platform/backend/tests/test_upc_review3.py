"""评审三轮回归:R3-4 编排装配闸 / R3-5 最长名迁移 / R3-6 归档管理写 /
R3-7 项目 patch+delete 行锁 / P2-8 嵌套形状 / P2-9 ref 指纹 /
R3-1/2/3 处置原子性与晋升申请收口。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text as sa_text

from app.core import db as db_module
from tests.helpers import make_draft, register_and_login, role_headers


# ── R3-4:编排预检按单元实际 schemeId 过装配闸 ──────────────────────

async def test_graph_validate_blocked_scheme_forbids_run(
        client: AsyncClient, monkeypatch):
    """单元选定 blocked 方案(非默认)→ 结构化禁跑;物化与凭证解析
    零调用(修前只看默认方案且仅跳过告警,仍会收集别名并物化)。"""
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import run_prepare, scheme_repair
    from tests.test_suites_validate import _mk, _patch_convert

    await register_and_login(client, "r3_boot", "r3_bootpass123")
    h = await register_and_login(client, "r3_own", "r3_ownpass123")
    _patch_convert(monkeypatch)

    # 布景先行(_mk_suite 内部会再建场景,不能先建方案)
    await _mk(client, h, "sc-va")
    await _mk(client, h, "sc-vb")

    # 非默认方案置 blocked,单元显式选定它
    r = await client.post("/api/scenarios/sc-va/run-schemes",
                          headers=h,
                          json={"name": "单元方案", "isDefault": False,
                                "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    assert r.status_code == 201, r.text
    unit_scheme_id = r.json()["schemeId"]
    uid = (await client.get("/api/auth/me", headers=h)
           ).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == unit_scheme_id))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid, actor_name="seed")
        await s.commit()

    r = await client.post("/api/suites", headers=h,
                          json={"name": "blocked编排", "description": ""})
    assert r.status_code == 201, r.text
    sid = r.json()["suiteId"]
    body = {"rev": 0, "mode": "compose",
            "members": [{"scenarioId": "sc-va"},
                        {"scenarioId": "sc-vb"}],
            "modeConfig": {"units": {
                "sc-va": {"ref": "a", "schemeId": unit_scheme_id},
                "sc-vb": {"ref": "b", "needs": ["sc-va"]}}}}
    r = await client.put(f"/api/suites/{sid}/composition",
                         headers=h, json=body)
    assert r.status_code == 200, r.text

    # 物化/凭证解析任一被触即炸 —— validate 必须在装配闸前返回禁跑
    from app.services import graph_dispatch as gd

    def _boom(*a, **k):
        raise AssertionError("blocked 单元不得进入物化/凭证解析")

    monkeypatch.setattr(gd, "materialize_graph", _boom)
    calls = {"resolve": 0}
    orig = run_prepare.resolve_exec_auths

    async def counting(factory, *a, **k):
        calls["resolve"] += 1
        return await orig(factory, *a, **k)

    monkeypatch.setattr(run_prepare, "resolve_exec_auths", counting)

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    blocked_msg = [it for it in body["items"] if "不可运行" in it["message"]]
    assert blocked_msg, body["items"]
    assert calls["resolve"] == 0


# ── R3-6:归档项目的管理写封闭 ──────────────────────────────────────

async def test_archived_project_blocks_management_writes(
        client: AsyncClient):
    """patch 项目 / 成员增改 / 组合写 全部 409 project_not_active;
    读面与权限投影同步收敛(member.manage=False)。"""
    from sqlalchemy import update as sa_update

    from app.models.project import Project
    from tests.helpers import mk_normal_project

    h_own = await register_and_login(client, "r3mg_own", "pw123456")
    h_mem = await register_and_login(client, "r3mg_mem", "pw123456")
    pid = await mk_normal_project("r3mg-proj", {
        "r3mg_own": "admin", "r3mg_mem": "member"})
    uid_mem = (await client.get("/api/auth/me", headers=h_mem)
               ).json()["user"]["id"]

    async with db_module.SessionLocal() as s:
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()

    # patch 项目 → 409
    r = await client.patch(f"/api/projects/{pid}", headers=h_own,
                           json={"description": "改"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    # 加成员 → 409
    r = await client.post(f"/api/projects/{pid}/members", headers=h_own,
                          json={"userId": uid_mem})
    assert r.status_code == 409, r.text
    # 改成员角色 → 409
    r = await client.patch(f"/api/projects/{pid}/members/{uid_mem}",
                           headers=h_own, json={"role": "member"})
    assert r.status_code == 409, r.text
    # 组合写(建)→ 409;读 → 不受影响
    r = await client.post(f"/api/projects/{pid}/account-combos",
                          headers=h_own,
                          json={"name": "归档组合", "entries": []})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    r = await client.get(f"/api/projects/{pid}/account-combos",
                         headers=h_own)
    assert r.status_code == 200, r.text
    # 权限投影:member.manage 收敛 False(§13.1 注释口径)
    r = await client.get(f"/api/projects/{pid}/context", headers=h_own)
    assert r.status_code == 200, r.text
    perms = r.json()["effectivePermissions"]
    assert perms["project.member.manage"] is False
    assert perms["project.update"] is False


# ── R3-7:项目 patch/delete 的成员行锁写点重验 ──────────────────────

async def test_project_patch_delete_locked_reverify(client: AsyncClient):
    """降级提交后,原成员管理员的项目 patch / delete 被写点重验拒绝
    (与成员端点同一行锁面;修前无锁检查只做一次)。"""
    from app.models.project import ProjectMember
    from tests.helpers import mk_user_with_space
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r3toc_adm", role="admin")
    h_pa = await role_headers(client, "r3toc_pa", role="user")
    pa_uid = await _uid_of(client, "r3toc_pa")
    pid = (await _create_project(
        client, h_admin, "r3toc-proj", pa_uid))["id"]

    # 先补第二名有效管理员(降级目标不能是末位管理员 —— 库层不变量)
    second_uid = await mk_user_with_space("r3toc_second")
    async with db_module.SessionLocal() as s:
        s.add(ProjectMember(project_id=pid, user_id=second_uid,
                            role="admin"))
        await s.commit()

    # 直接 SQL 降级(模拟并发降级已提交)
    async with db_module.SessionLocal() as s:
        await s.execute(sa_text(
            "UPDATE project_members SET role = 'member' "
            "WHERE project_id = :pid AND user_id = :uid"),
            {"pid": pid, "uid": pa_uid})
        await s.commit()

    r = await client.patch(f"/api/projects/{pid}", headers=h_pa,
                           json={"description": "偷改"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "not_project_admin"
    r = await client.delete(f"/api/projects/{pid}", headers=h_pa)
    assert r.status_code == 403, r.text


async def _uid_of(client: AsyncClient, username: str) -> int:
    from app.models.user import User

    async with db_module.SessionLocal() as s:
        return (await s.execute(select(User.id).where(
            User.username == username))).scalar_one()


# ── P2-8 / P2-9:资产包嵌套形状与同 ref 指纹 ────────────────────────

async def _restore(client, h_b, uid_b, bundle):
    from tests.helpers import default_space_id

    async with db_module.SessionLocal() as s:
        space_b = await default_space_id(s, uid_b)
        await s.commit()
    return await client.post(
        f"/api/projects/{space_b}/asset-bundles",
        headers=h_b, json=bundle), space_b


class TestBundleReviewRound3:
    """P2-8(嵌套 entries/ref 形状)与 P2-9(同 ref 内容指纹)。"""

    async def _seed_bundle(self, client, tag: str):
        from tests.test_upc_m2_domain import TestAssetBundleRoundtrip

        return await TestAssetBundleRoundtrip._seed_source(
            None, client, tag)

    async def test_nested_dep_shape_errors_are_422(self, client):
        h, _space, _combo, _ds, _qa = await self._seed_bundle(client, "n8")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b = await register_and_login(client, "r3_n8_b", "pw123456")
        uid_b = await _uid_of(client, "r3_n8_b")

        bad_entries = dict(bundle)
        bad_entries["schemes"] = [
            dict(s, payload=dict(s["payload"],
                                 dataSetSelection=[], injectionEntryIds=[]))
            for s in bundle["schemes"]]
        dep_key = next(iter(bundle["comboDependencies"]))
        bad_entries["comboDependencies"] = {
            dep_key: dict(bundle["comboDependencies"][dep_key],
                          entries=1)}
        r, _sp = await _restore(client, h_b, uid_b, bad_entries)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_shape_invalid")

        bad_ref = dict(bundle)
        bad_ref["comboDependencies"] = {
            dep_key: dict(bundle["comboDependencies"][dep_key], ref=[])}
        r, _sp = await _restore(client, h_b, uid_b, bad_ref)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_shape_invalid")

    async def test_same_ref_conflicting_entries_rejected(self, client):
        """同 ref 不同 entries → 422 asset_bundle_combo_conflict,不再
        静默绑到第一个组合(P2-9)。"""
        from tests.test_upc_m2_domain import _mk_scheme

        h, _space, combo_id, _ds, qa1 = await self._seed_bundle(client, "n9")
        # 第二个方案绑定同一组合 → 包内两个 dep 共享同一 ref
        qa2 = await _mk_scheme(client, h, "sc-m2x", "回归方案B",
                               combo_id=combo_id)
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        assert bundle["comboDependencies"][qa1]["ref"] ==             bundle["comboDependencies"][qa2]["ref"]
        # 第二个 dep 的条目与第一个矛盾
        dep = bundle["comboDependencies"][qa1]
        bundle["comboDependencies"][qa2] = dict(
            dep, entries=[{"service": dep["entries"][0]["service"],
                           "alias": "someone-else"}])
        h_b = await register_and_login(client, "r3_n9_b", "pw123456")
        uid_b = await _uid_of(client, "r3_n9_b")
        r, _sp = await _restore(client, h_b, uid_b, bundle)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_combo_conflict")


# ── R3-1/2/3:处置原子性与晋升申请收口 ──────────────────────────────

async def test_disposal_failure_rolls_back_midflow_writes(
        client: AsyncClient, monkeypatch):
    """处置中途失败 → 整体回滚:场景未迁移、通知未落库、审计未落库、
    用户仍在(修前通知/审计自行提交留下半程状态)。"""
    from sqlalchemy import func, select, update as sa_update

    from app.models.permission import AuditLog
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.models.composer_scenario import ComposerScenario
    from app.models.permission import Notification
    from app.models.user import User
    from tests.helpers import default_space_id

    h_admin = await register_and_login(client, "r3rb_adm", "pw123456")
    r = await client.post("/api/users", headers=h_admin,
                          json={"username": "r3rb_victim",
                                "password": "Test2026!"})
    assert r.status_code == 201, r.text
    victim = r.json()
    await register_and_login(client, "r3rb_keeper", "pw123456")
    keeper_uid = await _uid_of(client, "r3rb_keeper")

    await client.post("/api/scenarios", headers=h_admin,
                      json=make_draft("sc-r3rb"))
    async with db_module.SessionLocal() as s:
        _home = await default_space_id(s, victim["id"])
        await s.execute(sa_text(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(sa_update(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-r3rb"
        ).values(owner_id=victim["id"], owner_name="r3rb_victim",
                 project_id=_home))
        await s.execute(sa_update(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-r3rb"
        ).values(project_id=_home))
        await s.commit()

    # 注入:私有容器处置阶段失败
    from app.services import project_space as ps

    async def _boom(db, user_id):
        raise RuntimeError("injected: disposal failure")

    monkeypatch.setattr(ps, "dispose_private_containers", _boom)
    # 注入异常经 ServerErrorMiddleware 生成 500 后原样重抛(httpx 侧
    # 直接收到异常)—— 处置失败路径即业务事务整体回滚
    with pytest.raises(RuntimeError):
        await client.request(
            "DELETE", f"/api/users/{victim['id']}", headers=h_admin,
            json={"disposal": "transfer", "transfer_to": keeper_uid})

    async with db_module.SessionLocal() as s:
        # 用户仍在
        assert await s.get(User, victim["id"]) is not None
        # 场景未迁移(仍在 victim 空间,属主未变)
        scen = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-r3rb"))).scalar_one()
        assert scen.owner_id == victim["id"]
        assert scen.project_id == _home
        # 通知与处置审计零落库
        n = (await s.execute(select(func.count()).select_from(
            Notification).where(
            Notification.user_id == keeper_uid))).scalar_one()
        assert n == 0
        a = (await s.execute(select(func.count()).select_from(
            AuditLog).where(
            AuditLog.action == "integration.task.dispose"))).scalar_one()
        assert a == 0


async def test_disposal_cleans_promotions_by_applicant(client):
    """R3-3:普通项目晋升申请行(applicant_id NO ACTION)按申请人收口
    —— 含 pending/approved 申请的用户删除不再撞 FK。"""
    from sqlalchemy import select

    from app.models.project_promotion import ProjectPromotion
    from tests.helpers import mk_normal_project

    h_admin = await register_and_login(client, "r3pm_adm", "pw123456")
    r = await client.post("/api/users", headers=h_admin,
                          json={"username": "r3pm_victim",
                                "password": "Test2026!"})
    assert r.status_code == 201, r.text
    victim = r.json()
    pid = await mk_normal_project("r3pm-proj", {
        "r3pm_victim": "member"})

    async with db_module.SessionLocal() as s:
        s.add(ProjectPromotion(project_id=pid, kind="scenario",
                               source_id="sc-a", applicant_id=victim["id"],
                               status="pending"))
        s.add(ProjectPromotion(project_id=pid, kind="scenario",
                               source_id="sc-b", applicant_id=victim["id"],
                               status="approved"))
        await s.commit()

    r = await client.request("DELETE", f"/api/users/{victim['id']}",
                             headers=h_admin, json={"disposal": "purge"})
    assert r.status_code == 204, r.text
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ProjectPromotion).where(
            ProjectPromotion.applicant_id == victim["id"]))).scalars().all()
        assert rows == []


# ── R3-5:0068 最长名 Suite 重命名(真实 0066 形态升级)──────────────

def test_upgrade_renames_128_char_same_name_suites():
    """旧合法 128 字符同名 Suite:重命名候选先按列宽截断再消歧,
    不再 StringDataRightTruncation 整笔回滚;重命名行长度 ≤ 128。"""
    from alembic import command
    from sqlalchemy import create_engine, text

    from tests.test_migrations import _cfg, temp_schema
    from tests.test_upc_m2_upgrade import _to_0066_shape

    long_name = "长" * 128
    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0001_baseline")
        eng = create_engine(sync_url)
        try:
            _to_0066_shape(eng)
            with eng.begin() as conn:
                for stmt in (
                    """
                    INSERT INTO users (username, display_name,
                                       password_hash, role, is_active,
                                       is_system)
                    VALUES ('r3ln_a', 'A', 'x', 'user', true, false),
                           ('r3ln_b', 'B', 'x', 'user', true, false)
                    """,
                    """
                    INSERT INTO projects (name, kind, description,
                                          created_at)
                    VALUES ('r3ln-proj', 'normal', '', now())
                    """,
                    """
                    INSERT INTO project_members (project_id, user_id,
                                                 role)
                    SELECT p.id, u.id, 'admin'
                      FROM projects p, users u
                     WHERE p.name = 'r3ln-proj'
                       AND u.username IN ('r3ln_a', 'r3ln_b')
                    """,
                    # 旧合法数据:128 字符同名(两 owner 各一)
                    f"""
                    INSERT INTO suites (name, owner_id, project_id, mode,
                                        mode_config, rev, description)
                    SELECT '{long_name}', u.id, p.id, 'standard', '{{}}',
                           1, ''
                      FROM projects p, users u
                     WHERE p.name = 'r3ln-proj'
                       AND u.username IN ('r3ln_a', 'r3ln_b')
                    """,
                ):
                    conn.exec_driver_sql(stmt)
            command.stamp(_cfg(sync_url), "0066_incremental_model_align")
            # 修前:追加后缀触发 StringDataRightTruncation 整笔回滚
            command.upgrade(_cfg(sync_url), "head")

            with eng.begin() as conn:
                rows = conn.execute(text(
                    "SELECT name FROM suites ORDER BY id")).scalars().all()
                assert rows[0] == long_name          # id 最小者保名
                assert len(rows[1]) <= 128           # 截断消歧,不越列宽
                assert rows[1] != rows[0]
        finally:
            eng.dispose()
