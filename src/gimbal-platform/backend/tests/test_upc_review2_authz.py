"""评审二轮回归(授权与处置面):P1-5 归档闸 / P1-7 成员管理 TOCTOU /
P1-3 处置台账收口 / P2-15 默认切换真实交错 / P2-14 普通 PUT 可选 CAS。"""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import text as sa_text

from app.core import db as db_module
from tests.helpers import make_draft, register_and_login, role_headers


# ── P1-5:归档项目禁止新写入与新执行 ────────────────────────────────

async def test_archived_project_blocks_write_and_execute(
        client: AsyncClient):
    """修前:归档 normal 项目成员 PUT 场景仍 200、执行闸照常放行。
    收口后:表 B 写动词与 can_run_scenario 在授权单源上查项目状态。"""
    from sqlalchemy import select, update as sa_update

    from app.models.project import Project
    from app.models.user import User
    from tests.helpers import mk_normal_project

    await register_and_login(client, "arc_own", "pw123456")
    h_mem = await register_and_login(client, "arc_mem", "pw123456")
    pid = await mk_normal_project("arc-proj", {
        "arc_own": "admin", "arc_mem": "member"})
    await client.post(f"/api/scenarios?projectId={pid}",
                      headers=h_mem, json=make_draft("sc-arc"))

    # 归档
    async with db_module.SessionLocal() as s:
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()

    # 写闸:成员 PUT 场景 → 403(读仍可见,写动词在单源被拒)
    r = await client.put("/api/scenarios/sc-arc", headers=h_mem,
                         json=make_draft("sc-arc"))
    assert r.status_code == 403, r.text

    # 执行闸:can_run_scenario False(执行授权单源)
    from app.routers._ownership import can_run_scenario

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id).where(
            User.username == "arc_mem"))).scalar_one()
        assert not await can_run_scenario(
            s, type("U", (), {"id": uid})(),
            scenario_id="sc-arc", owner_id=uid, project_id=pid)

    # 对照:恢复 active 后写闸重开
    async with db_module.SessionLocal() as s:
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="active"))
        await s.commit()
    r = await client.put("/api/scenarios/sc-arc", headers=h_mem,
                         json=make_draft("sc-arc"))
    assert r.status_code == 200, r.text


# ── P1-7:成员管理写点锁行重验(TOCTOU)────────────────────────────

async def test_member_manage_serialized_on_operator_row(
        client: AsyncClient):
    """①操作者成员行持锁期间,并发的降级 UPDATE 阻塞(检查-写入窗口
    关闭);②降级提交后,同一操作者的新管理请求被写点重验拒绝。"""
    from sqlalchemy import select

    from app.models.project import ProjectMember

    h_admin = await role_headers(client, "toc_adm", role="admin")
    h_pa = await role_headers(client, "toc_pa", role="user")
    _h_mb = await role_headers(client, "toc_mb", role="user")
    _h_out = await role_headers(client, "toc_out", role="user")
    pa_uid = await _uid_by(client, "toc_pa")
    mb_uid = await _uid_by(client, "toc_mb")
    out_uid = await _uid_by(client, "toc_out")
    from tests.test_authz_s14_projects import _create_project

    pid = (await _create_project(
        client, h_admin, "toc-proj", pa_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_pa, json={"userId": mb_uid})
    assert r.status_code == 201, r.text
    # 提拔 mb 为第二个成员管理员(降级的执行者)
    r = await client.patch(f"/api/projects/{pid}/members/{mb_uid}",
                           headers=h_pa, json={"role": "admin"})
    assert r.status_code == 200, r.text

    # ① pa 的在途管理写:写点重验持有自己的成员行锁(未提交)
    s1 = db_module.SessionLocal()
    s2 = db_module.SessionLocal()
    try:
        locked = await s1.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == pid,
                ProjectMember.user_id == pa_uid).with_for_update())
        locked.scalar_one()

        # mb 并发降级 pa —— 撞行锁,必须阻塞(窗口关闭的证据)
        task = asyncio.ensure_future(s2.execute(sa_text(
            "UPDATE project_members SET role = 'member' "
            "WHERE project_id = :pid AND user_id = :uid"),
            {"pid": pid, "uid": pa_uid}))
        await asyncio.sleep(0.4)
        assert not task.done(), "降级未与操作者行串行化:TOCTOU 窗口仍在"
        await s1.commit()          # 在途管理写提交,锁释放
        await asyncio.wait_for(task, 5)   # 降级随后落库
        await s2.commit()
    finally:
        await s1.close()
        await s2.close()

    # ② 降级已提交 → pa 的新管理请求被写点重验拒绝
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_pa, json={"userId": out_uid})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "not_project_admin"


async def _uid_by(client: AsyncClient, username: str) -> int:
    from sqlalchemy import select

    from app.models.user import User

    async with db_module.SessionLocal() as s:
        return (await s.execute(select(User.id).where(
            User.username == username))).scalar_one()


# ── P1-3:私有空间处置补台账依赖 + purge 事务内删除 ─────────────────

async def test_disposal_purge_cleans_history_ledger_rows(
        client: AsyncClient):
    """含资产导入台账行的私有空间,删号 purge 不再撞 NO ACTION FK;
    台账随容器显式收口;purge 路径的场景删除并入处置事务(commit=False)。"""
    from sqlalchemy import select, text as _t, update as sa_update

    from app.models.composer_run_scheme import ComposerRunScheme
    from app.models.composer_scenario import ComposerScenario
    from app.models.scenario_asset_import import ScenarioAssetImport
    from app.models.user import User as _User
    from tests.conftest import seed_identity_fixture
    from tests.helpers import default_space_id

    h_admin = await register_and_login(client, "lgd_adm", "pw123456")

    # 受害者 + 私有空间内容(场景/方案/台账)
    r = await client.post("/api/users", headers=h_admin,
                          json={"username": "lgd_victim",
                                "password": "Test2026!"})
    assert r.status_code == 201, r.text
    victim = r.json()
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias="lgd-qa", username="u", password="p",
            service="fin-service", owner_id=victim["id"])
        await s.commit()
    # 场景建在 admin 名下再搬入 victim 空间(与既有处置布景同款)
    await client.post("/api/scenarios", headers=h_admin,
                      json=make_draft("sc-lgd"))
    async with db_module.SessionLocal() as s:
        _home = await default_space_id(s, victim["id"])
        await s.execute(_t(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(sa_update(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-lgd"
        ).values(owner_id=victim["id"], owner_name="lgd_victim",
                 project_id=_home))
        await s.execute(sa_update(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-lgd"
        ).values(project_id=_home))
        s.add(ScenarioAssetImport(
            project_id=_home, package_id="pkg-lgd",
            source_scenario_id="sc-src", request_digest="d" * 64,
            restored_scenario_id="sc-lgd", restored_scheme_ids=[],
            default_scheme_id=None, report={}, created_by=victim["id"]))
        await s.commit()

    r = await client.request("DELETE", f"/api/users/{victim['id']}",
                             headers=h_admin, json={"disposal": "purge"})
    assert r.status_code == 204, r.text
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(ScenarioAssetImport).where(
            ScenarioAssetImport.project_id == _home))).scalars().all() == []
        assert await s.get(_User, victim["id"]) is None


# ── P2-15:默认空间并发切换 —— 真实交错(两事务重叠后再分别提交)──

async def test_concurrent_default_space_switch_true_interleave(
        client: AsyncClient):
    """修前测试「先提交 s1 再跑 s2」并非交错。本用例把两事务的写入
    重叠在双方均未提交的窗口内(s2 挂在 s1 的行锁上,任务未完成即
    重叠证据),随后各自提交 —— 恒恰一个默认,后提交者读到前者的
    已提交终态,不变量由唯一索引与串行化共同兜住。"""
    h = await register_and_login(client, "cx_sw2", "pw123456")
    pids = []
    for name in ("切换甲2", "切换乙2"):
        r = await client.post("/api/projects", headers=h, json={
            "name": name, "kind": "private"})
        assert r.status_code == 201, r.text
        pids.append(r.json()["id"])
    uid = await _uid_by(client, "cx_sw2")
    async with db_module.SessionLocal() as s:
        old_default = (await s.execute(sa_text(
            "SELECT id FROM projects WHERE kind='private' "
            "AND owner_id=:uid AND is_default"), {"uid": uid}
        )).scalar_one()

    s1 = db_module.SessionLocal()
    s2 = db_module.SessionLocal()
    try:
        # s1:取消旧默认 + 甲置默认(未提交)
        await s1.execute(sa_text(
            "UPDATE projects SET is_default=false WHERE id=:pid"),
            {"pid": old_default})
        await s1.execute(sa_text(
            "UPDATE projects SET is_default=true WHERE id=:pid"),
            {"pid": pids[0]})
        # s2:取消旧默认(挂 s1 行锁 —— 两事务真实重叠)
        task = asyncio.ensure_future(s2.execute(sa_text(
            "UPDATE projects SET is_default=false WHERE id=:pid"),
            {"pid": old_default}))
        await asyncio.sleep(0.4)
        assert not task.done(), "s2 未重叠:s1 的行锁未阻塞 s2"
        await s1.commit()          # s1 提交,锁释放
        await asyncio.wait_for(task, 5)
        # s2 续行:乙置默认 —— READ COMMITTED 语句级重读已见「甲默认」,
        # 部分唯一索引在语句点拒绝(uq_projects_private_default 并发权威)
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await s2.execute(sa_text(
                "UPDATE projects SET is_default=true WHERE id=:pid"),
                {"pid": pids[1]})
        await s2.rollback()
    finally:
        await s1.close()
        await s2.close()
    async with db_module.SessionLocal() as s:
        defaults = (await s.execute(sa_text(
            "SELECT id FROM projects WHERE kind='private' "
            "AND owner_id=:uid AND is_default"), {"uid": uid}
        )).scalars().all()
        assert defaults == [pids[0]]    # 恰一个,先提交者胜


# ── P2-14:普通 PUT 可选 expectedRevision CAS ──────────────────────

async def test_scheme_put_expected_revision_cas(client: AsyncClient):
    """显式 expectedRevision 落空 → 409 scheme_revision_conflict;
    匹配 → 200 且 revision 前进;未传 → 既有最后写入语义。"""
    h = await register_and_login(client, "cas_own", "pw123456")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-cas"))
    r = await client.post("/api/scenarios/sc-cas/run-schemes",
                          headers=h,
                          json={"name": "CAS方案", "isDefault": False,
                                "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    assert r.status_code == 201, r.text
    sid = r.json()["schemeId"]
    rev = r.json()["revision"]

    # 落空:revision 已被他人推进
    r = await client.put(f"/api/scenarios/sc-cas/run-schemes/{sid}",
                         headers=h,
                         json={"name": "CAS方案", "isDefault": False,
                               "expectedRevision": rev + 5,
                               "dataSetSelection": [],
                               "injectionEntryIds": [],
                               "serviceBindings": {}, "options": {
                                   "step_from": None, "step_to": None,
                                   "n_runs": 1, "parallel": 1,
                                   "subscribe": None}})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_revision_conflict"

    # 匹配:200 且 revision 前进
    r = await client.put(f"/api/scenarios/sc-cas/run-schemes/{sid}",
                         headers=h,
                         json={"name": "CAS方案", "isDefault": False,
                               "expectedRevision": rev,
                               "dataSetSelection": [],
                               "injectionEntryIds": [],
                               "serviceBindings": {}, "options": {
                                   "step_from": None, "step_to": None,
                                   "n_runs": 1, "parallel": 1,
                                   "subscribe": None}})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == rev + 1


# ── P2-8:公共项目组合读路径的能力闸映射 ────────────────────────────

async def test_public_project_combo_read_maps_capability_error(
        client: AsyncClient):
    """修前:列表/详情的读门未翻译能力闸域错误 → 500;收口后统一 422
    (§7:公共项目组合面不开放)。"""
    from app.services.zone import public_project_id

    h = await register_and_login(client, "c2p8", "pw123456")
    async with db_module.SessionLocal() as s:
        pid = await public_project_id(s)
    r = await client.get(f"/api/projects/{pid}/account-combos", headers=h)
    assert r.status_code == 422, r.text
    assert (r.json()["detail"]["code"]
            == "account_combo_capability_disabled")
    r = await client.get(f"/api/projects/{pid}/account-combos/999",
                         headers=h)
    assert r.status_code == 422, r.text


# ── P2-13:facets 读门与项目详情同源 ────────────────────────────────

async def test_facets_gate_matches_project_detail(client: AsyncClient):
    """修前:facets 的 projectId 门残留 Admin+ 旁路 —— 平台管理员可读
    他人私有空间 facets,与详情 404 分裂。收口后同源
    ``can_view_project``(私有空间非属主含 Admin+ 一律 404)。"""
    from sqlalchemy import select

    from app.models.project import Project
    from tests.helpers import default_space_id

    h_own = await register_and_login(client, "fc_own", "pw123456")
    _h_admin = await role_headers(client, "fc_adm", role="admin")
    uid = (await client.get("/api/auth/me", headers=h_own)
           ).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        space = await default_space_id(s, uid)
        assert (await s.execute(select(Project.id).where(
            Project.id == space))).scalar_one() == space
    r = await client.get(f"/api/scenarios/facets?projectId={space}",
                         headers=h_own)
    assert r.status_code == 200, r.text       # 属主照常
    r = await client.get(f"/api/projects/{space}", headers=_h_admin)
    assert r.status_code == 404, r.text       # 详情:Admin+ 非属主 404
    r = await client.get(f"/api/scenarios/facets?projectId={space}",
                         headers=_h_admin)
    assert r.status_code == 404, r.text       # facets:同源 404(修前 200)
