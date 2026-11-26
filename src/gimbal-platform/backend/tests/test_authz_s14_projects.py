"""M2a S1.4 项目管理面:建项目(Admin+ 指定首个 padmin)、成员 CRUD、
末位项目管理员保护、删项目内容闸与公共项目保护。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import role_headers


async def _uid(client: AsyncClient, token_headers: dict, username: str) -> int:
    roster = (await client.get(
        "/api/users/roster", headers=token_headers)).json()["items"]
    return next(u["id"] for u in roster if u["username"] == username)


async def _create_project(
    client: AsyncClient, h_admin: dict, name: str, admin_uid: int, **over,
) -> dict:
    r = await client.post("/api/projects", headers=h_admin, json={
        "name": name, "description": "", "firstAdminUserId": admin_uid,
        **over})
    assert r.status_code == 201, r.text
    return r.json()


class TestProjectCrud:
    async def test_create_gates_and_first_admin(self, client: AsyncClient):
        h_admin = await role_headers(client, "s14_adm", role="admin")
        h_pa = await role_headers(client, "s14_pa", role="user")
        pa_uid = await _uid(client, h_admin, "s14_pa")

        # 普通用户 403(能力门 MemberUser = ops.write)
        h_usr = await role_headers(client, "s14_usr", role="user")
        r = await client.post("/api/projects", headers=h_usr, json={
            "name": "x", "firstAdminUserId": pa_uid})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "capability_forbidden"

        out = await _create_project(client, h_admin, "s14-proj", pa_uid)
        assert out["kind"] == "normal" and out["memberCount"] == 1

        # 首个管理员无效(不存在)→ 422;重名 → 409
        r = await client.post("/api/projects", headers=h_admin, json={
            "name": "s14-p2", "firstAdminUserId": 99999})
        assert r.status_code == 422, r.text
        r = await client.post("/api/projects", headers=h_admin, json={
            "name": "s14-proj", "firstAdminUserId": pa_uid})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "project_name_taken"

        # padmin 建项目也 403(S1-g:只有 Admin+)
        r = await client.post("/api/projects", headers=h_pa, json={
            "name": "s14-p3", "firstAdminUserId": pa_uid})
        assert r.status_code == 403, r.text

    async def test_list_and_detail_visibility(self, client: AsyncClient):
        h_admin = await role_headers(client, "s14_ladm", role="admin")
        h_pa = await role_headers(client, "s14_lpa", role="user")
        h_out = await role_headers(client, "s14_lout", role="user")
        pa_uid = await _uid(client, h_admin, "s14_lpa")
        out = await _create_project(client, h_admin, "s14-lproj", pa_uid)

        # UPC M1 统一可见性(AC-51):Admin+ 不旁路 —— 他人项目不可见,
        # 只见公共 + 自己的默认空间;普通用户 = 公共 + 我所在的 + 自己
        # 的默认空间;路人只见公共 + 自己的默认空间
        r = await client.get("/api/projects", headers=h_admin)
        names = {p["name"] for p in r.json()}
        assert "s14-lproj" not in names and "公共" in names
        r = await client.get("/api/projects", headers=h_pa)
        # UPC M1:含本人默认私有空间(id 序:空间先于后建的项目)
        assert [p["name"] for p in r.json()] == [
            "公共", "默认空间", "s14-lproj"]
        assert r.json()[2]["myRole"] == "admin"
        r = await client.get("/api/projects", headers=h_out)
        assert [p["kind"] for p in r.json()] == ["public", "private"]

        # 详情:成员 200(myRole);路人 404
        r = await client.get(f"/api/projects/{out['id']}", headers=h_pa)
        assert r.status_code == 200 and r.json()["myRole"] == "admin"
        assert (await client.get(
            f"/api/projects/{out['id']}", headers=h_out)).status_code == 404

    async def test_patch_by_padmin_member_and_stranger(self, client):
        h_admin = await role_headers(client, "s14_padm", role="admin")
        h_pa = await role_headers(client, "s14_ppa", role="user")
        h_mb = await role_headers(client, "s14_pmb", role="user")
        h_out = await role_headers(client, "s14_pout", role="user")
        pa_uid = await _uid(client, h_admin, "s14_ppa")
        out = await _create_project(client, h_admin, "s14-pproj", pa_uid)
        pid = out["id"]
        # padmin 加个普通成员
        r = await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                              json={"userId": await _uid(
                                  client, h_admin, "s14_pmb"),
                                    "role": "member"})
        assert r.status_code == 201, r.text

        # padmin 改名/描述 → 200;成员 → 403;路人 → 404
        r = await client.patch(f"/api/projects/{pid}", headers=h_pa,
                               json={"description": "改过"})
        assert r.status_code == 200 and r.json()["description"] == "改过"
        r = await client.patch(f"/api/projects/{pid}", headers=h_mb,
                               json={"name": "偷改"})
        assert r.status_code == 403, r.text
        r = await client.patch(f"/api/projects/{pid}", headers=h_out,
                               json={"name": "偷改"})
        assert r.status_code == 404, r.text

    async def test_delete_empty_and_content_gate(self, client):
        h_admin = await role_headers(client, "s14_dadm", role="admin")
        h_pa = await role_headers(client, "s14_dpa", role="user")
        h_usr = await role_headers(client, "s14_dusr", role="user")
        pa_uid = await _uid(client, h_admin, "s14_dpa")
        pid = (await _create_project(
            client, h_admin, "s14-dproj", pa_uid))["id"]

        # 有内容 → 409 project_not_empty(场景挂靠)
        from sqlalchemy import update as _upd

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario

        h_own = await role_headers(client, "s14_down", role="user")
        from tests.helpers import make_draft

        await client.post("/api/scenarios", headers=h_own,
                          json=make_draft("sc-s14-d"))
        async with db_module.SessionLocal() as db:
            await db.execute(_upd(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-s14-d"
            ).values(project_id=pid))
            await db.commit()
        r = await client.delete(f"/api/projects/{pid}", headers=h_admin)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "project_not_empty"

        # 清空后删除 → 204;普通用户删除 → 403(能力门)
        async with db_module.SessionLocal() as db:
            await db.execute(_upd(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-s14-d"
            ).values(project_id=None))
            await db.commit()
        assert (await client.delete(
            f"/api/projects/{pid}", headers=h_usr)).status_code == 403
        r = await client.delete(f"/api/projects/{pid}", headers=h_admin)
        assert r.status_code == 204, r.text
        assert (await client.get(
            f"/api/projects/{pid}", headers=h_admin)).status_code == 404

    async def test_public_project_protected(self, client):
        h_admin = await role_headers(client, "s14_qadm", role="admin")
        from sqlalchemy import select as _sel

        from app.core import db as db_module
        from app.models.project import Project

        async with db_module.SessionLocal() as db:
            pid = (await db.execute(_sel(Project.id).where(
                Project.kind == "public"))).scalar_one()
        assert (await client.delete(
            f"/api/projects/{pid}", headers=h_admin)).status_code == 409
        assert (await client.patch(
            f"/api/projects/{pid}", headers=h_admin,
            json={"name": "改名"})).status_code == 409


class TestMemberManagement:
    async def _mk(self, client, name):
        h_admin = await role_headers(client, f"{name}_adm", role="admin")
        h_pa = await role_headers(client, f"{name}_pa", role="user")
        h_mb = await role_headers(client, f"{name}_mb", role="user")
        h_out = await role_headers(client, f"{name}_out", role="user")
        pa_uid = await _uid(client, h_admin, f"{name}_pa")
        pid = (await _create_project(
            client, h_admin, f"{name}-proj", pa_uid))["id"]
        return h_admin, h_pa, h_mb, h_out, pid

    async def test_member_crud_matrix(self, client):
        h_admin, h_pa, h_mb, h_out, pid = await self._mk(client, "s14m1")
        mb_uid = await _uid(client, h_admin, "s14m1_mb")
        out_uid = await _uid(client, h_admin, "s14m1_out")

        # 路人管理 → 404;普通成员视图外;成员管理(非 padmin)后测
        assert (await client.get(
            f"/api/projects/{pid}/members", headers=h_out)).status_code == 404

        # padmin 加成员(默认 member)、重复 409、无效 422
        r = await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                              json={"userId": mb_uid})
        assert r.status_code == 201 and r.json()["role"] == "member"
        r = await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                              json={"userId": mb_uid})
        assert r.status_code == 409 and r.json()["detail"]["code"] == (
            "member_exists")
        r = await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                              json={"userId": 99999})
        assert r.status_code == 422, r.text

        # /auth/me.projects 联动
        r = await client.get("/api/auth/me", headers=h_mb)
        # S7.0 + UPC M1:公共置顶(role=None)+ 本人默认空间 + 我所在项目
        assert [(p_["kind"], p_["isDefault"]) for p_ in
                r.json()["projects"][1:]] == [
            ("private", True), ("normal", False)]
        mine = next(p_ for p_ in r.json()["projects"]
                    if p_["name"] == "s14m1-proj")
        assert mine == {"id": pid, "name": "s14m1-proj",
                        "kind": "normal", "role": "member",
                        "isDefault": False, "status": "active"}

        # 普通成员(非 padmin)不能管理:403
        r = await client.post(f"/api/projects/{pid}/members", headers=h_mb,
                              json={"userId": out_uid})
        assert r.status_code == 403, r.text

        # 改角色 member→admin→member、移除
        r = await client.patch(
            f"/api/projects/{pid}/members/{mb_uid}", headers=h_pa,
            json={"role": "admin"})
        assert r.status_code == 200 and r.json()["role"] == "admin"
        # 现在两位 admin:降级 mb 不再触发末位保护
        r = await client.patch(
            f"/api/projects/{pid}/members/{mb_uid}", headers=h_pa,
            json={"role": "member"})
        assert r.status_code == 200
        r = await client.delete(
            f"/api/projects/{pid}/members/{mb_uid}", headers=h_pa)
        assert r.status_code == 204, r.text
        # 移除后 me.projects 只剩公共 + 本人默认空间(UPC M1 同口径)
        others = [p_ for p_ in (await client.get(
            "/api/auth/me", headers=h_mb)).json()["projects"]
            if p_["kind"] != "public"]
        assert [(p_["kind"], p_["isDefault"]) for p_ in others] == [
            ("private", True)]

    async def test_member_asset_counts(self, client):
        """成员列表带本项目资产数(A 级批次 2026-11-18):owner 归属权威,
        按 (project_id, owner_id) 聚合;项目外的不算。"""
        from app.core import db as db_module
        from app.models import ComposerScenario
        from app.models.suite import Suite

        h_admin, h_pa, h_mb, h_out, pid = await self._mk(client, "s14mc")
        pa_uid = await _uid(client, h_admin, "s14mc_pa")
        mb_uid = await _uid(client, h_admin, "s14mc_mb")
        assert (await client.post(
            f"/api/projects/{pid}/members", headers=h_pa,
            json={"userId": mb_uid})).status_code == 201

        async with db_module.SessionLocal() as s:
            for i in range(2):
                s.add(ComposerScenario(
                    scenario_id=f"sc-s14mc-{i}",
                    owner_id=pa_uid, project_id=pid))
            s.add(ComposerScenario(
                scenario_id="sc-s14mc-out",
                owner_id=pa_uid))
            s.add(Suite(name="套件A", owner_id=mb_uid, project_id=pid))
            await s.commit()

        r = await client.get(f"/api/projects/{pid}/members", headers=h_pa)
        assert r.status_code == 200, r.text
        by_uid = {m["userId"]: m for m in r.json()}
        assert by_uid[pa_uid]["scenarioCount"] == 2
        assert by_uid[pa_uid]["suiteCount"] == 0
        assert by_uid[mb_uid]["scenarioCount"] == 0
        assert by_uid[mb_uid]["suiteCount"] == 1

    async def test_last_project_admin_protection(self, client):
        h_admin, h_pa, h_mb, h_out, pid = await self._mk(client, "s14m2")
        pa_uid = await _uid(client, h_admin, "s14m2_pa")
        mb_uid = await _uid(client, h_admin, "s14m2_mb")
        await client.post(f"/api/projects/{pid}/members", headers=h_pa,
                          json={"userId": mb_uid})

        # 唯一 admin:降级 409、移除 409(与末位 Super Admin 同口径)
        r = await client.patch(
            f"/api/projects/{pid}/members/{pa_uid}", headers=h_pa,
            json={"role": "member"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == (
            "last_project_admin")
        r = await client.delete(
            f"/api/projects/{pid}/members/{pa_uid}", headers=h_pa)
        assert r.status_code == 409 and r.json()["detail"]["code"] == (
            "last_project_admin")
        # Admin+ 同样受末位保护(保护是结构性约束,不是权限边界)
        r = await client.delete(
            f"/api/projects/{pid}/members/{pa_uid}", headers=h_admin)
        assert r.status_code == 409, r.text

        # 提拔 mb 为 admin 后,移除原 admin 即可
        await client.patch(f"/api/projects/{pid}/members/{mb_uid}",
                           headers=h_pa, json={"role": "admin"})
        r = await client.delete(
            f"/api/projects/{pid}/members/{pa_uid}", headers=h_admin)
        assert r.status_code == 204, r.text
