"""UPC M1 验收(v2.10):AC-01/AC-02/AC-51 与 §20 容器不变量的库层负向用例。

覆盖:
* AC-01 用户初始化 —— 注册恰一个默认私有空间;并发权威 = 部分唯一
  索引(直插第二行被拒);系统用户排除;缺空间用户提交被延迟约束拒绝;
* AC-02 多私有空间 —— API 建/名称域内唯一/跨所有者同名;
* AC-51 可见性一致 —— /auth/me 与 /projects、详情、context 同源,
  ops.write 非所有者枚举不了他人私有空间;
* §20 库层约束 —— kind/形状/默认/状态 CHECK、public 唯一、kind 不可
  改、private/public 无成员行、活跃 normal ≥1 有效 admin(含末位与
  停用连带)、默认空间删除保护、用户处置删私有容器。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError

from tests.helpers import register_and_login, role_headers


def _db():
    from app.core import db as db_module

    return db_module.SessionLocal


async def _uid_of(client: AsyncClient, headers: dict) -> int:
    me = (await client.get("/api/auth/me", headers=headers)).json()
    return me["user"]["id"]


async def _private_spaces(client: AsyncClient, headers: dict) -> list[dict]:
    return [p for p in (await client.get("/api/projects", headers=headers)
                       ).json() if p["kind"] == "private"]


# ── AC-01 用户初始化 ────────────────────────────────────────────────
class TestUserInitDefaultSpace:

    async def test_register_creates_exactly_one_default_space(
            self, client: AsyncClient):
        h = await register_and_login(client, "upc_ac01")
        uid = await _uid_of(client, h)
        me = (await client.get("/api/auth/me", headers=h)).json()
        priv = [p for p in me["projects"] if p["kind"] == "private"]
        assert len(priv) == 1
        assert priv[0]["isDefault"] is True
        # 幂等重入:服务层再调一次不新建
        async with _db()() as s:
            from app.services.project_space import (
                ensure_default_private_project,
            )

            await ensure_default_private_project(s, uid)
            await s.commit()
        spaces = await _private_spaces(client, h)
        assert len(spaces) == 1 and spaces[0]["isDefault"] is True

    async def test_second_default_row_blocked_by_partial_index(
            self, client: AsyncClient):
        """并发权威是部分唯一索引 uq_projects_private_default(非应用层)。"""
        h = await register_and_login(client, "upc_ac01x")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, owner_id, is_default, status) "
                    "VALUES (gen_random_uuid(), '默认空间', 'private', '', "
                    ":uid, true, 'active')"), {"uid": uid})

    async def test_system_user_excluded(self, client: AsyncClient):
        """系统用户不自动创建私有空间(§4);延迟约束按 is_system 排除。"""
        from app.core.security import hash_password
        from app.models.user import User

        async with _db()() as s:
            s.add(User(username="upc_sys_acct", display_name="",
                       password_hash=hash_password("x"), is_system=True))
            await s.commit()  # 不应触发 user_default_space_required
            n = (await s.execute(sa_text(
                "SELECT count(*) FROM projects WHERE kind='private' "
                "AND owner_id = (SELECT id FROM users "
                "WHERE username='upc_sys_acct')"))).scalar()
            assert n == 0

    async def test_user_without_space_rejected_at_commit(
            self, client: AsyncClient):
        """非系统用户缺默认空间 → 延迟约束触发器在提交时拒绝(§20)。"""
        from app.core.security import hash_password
        from app.models.user import User

        async with _db()() as s:
            s.add(User(username="upc_nospace", display_name="",
                       password_hash=hash_password("x")))
            with pytest.raises(IntegrityError):
                await s.commit()


# ── AC-02 多私有空间 ────────────────────────────────────────────────
class TestMultiplePrivateSpaces:

    async def test_create_second_space_and_name_domains(
            self, client: AsyncClient):
        h = await register_and_login(client, "upc_ac02")
        r = await client.post("/api/projects", headers=h, json={
            "name": "第二空间", "kind": "private"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["kind"] == "private" and body["isDefault"] is False
        assert body["canManage"] is True and body["canWrite"] is True
        # 默认空间仍是唯一默认(AC-02:默认唯一)
        spaces = await _private_spaces(client, h)
        assert sorted(p["isDefault"] for p in spaces) == [False, True]
        # 所有者域内重名 → 409
        r2 = await client.post("/api/projects", headers=h, json={
            "name": "第二空间", "kind": "private"})
        assert r2.status_code == 409
        # 其他所有者同名 → 不冲突(名称分域,§4)
        h2 = await register_and_login(client, "upc_ac02b")
        r3 = await client.post("/api/projects", headers=h2, json={
            "name": "第二空间", "kind": "private"})
        assert r3.status_code == 201

    async def test_private_create_rejects_first_admin(
            self, client: AsyncClient):
        h = await register_and_login(client, "upc_ac02c")
        uid = await _uid_of(client, h)
        r = await client.post("/api/projects", headers=h, json={
            "name": "x", "kind": "private", "firstAdminUserId": uid})
        assert r.status_code == 422

    async def test_ordinary_user_cannot_create_normal_project(
            self, client: AsyncClient):
        # 直插普通用户(注册面首个真人自动 super_admin,测不了 403)
        h = await role_headers(client, "upc_ac02d", role="user")
        uid = await _uid_of(client, h)
        r = await client.post("/api/projects", headers=h, json={
            "name": "普通项目", "kind": "normal", "firstAdminUserId": uid})
        assert r.status_code == 403  # §4 授权创建 = Admin+


# ── AC-51 可见性一致 ─────────────────────────────────────────────────
class TestVisibilityConsistency:

    async def _me_ids(self, client, h) -> set[int]:
        me = (await client.get("/api/auth/me", headers=h)).json()
        return {p["id"] for p in me["projects"]}

    async def test_lists_detail_context_same_source(self, client: AsyncClient):
        """AC-51:/auth/me、/projects、详情与 context 逐 id 一致。"""
        h = await register_and_login(client, "upc_v_owner")
        ids_me = await self._me_ids(client, h)
        ids_list = {p["id"] for p in (
            await client.get("/api/projects", headers=h)).json()}
        assert ids_me == ids_list and ids_me
        for pid in ids_me:
            assert (await client.get(
                f"/api/projects/{pid}", headers=h)).status_code == 200
            assert (await client.get(
                f"/api/projects/{pid}/context", headers=h)).status_code == 200

    async def test_ops_write_cannot_enumerate_private_spaces(
            self, client: AsyncClient):
        """AC-51:具有 ops.write 的非所有者无法枚举私有项目(§6:平台
        管理员对他人私有空间全否;Admin+ 旁路已删)。"""
        h_owner = await register_and_login(client, "upc_v_owner2")
        h_admin = await role_headers(client, "upc_v_admin", role="admin")
        owner_me = (await client.get("/api/auth/me", headers=h_owner)).json()
        owner_private = {p["id"] for p in owner_me["projects"]
                         if p["kind"] == "private"}
        assert owner_private
        admin_list = (await client.get(
            "/api/projects", headers=h_admin)).json()
        listed = {p["id"] for p in admin_list}
        assert owner_private.isdisjoint(listed)
        for pid in owner_private:
            assert (await client.get(
                f"/api/projects/{pid}", headers=h_admin)).status_code == 404
            assert (await client.get(
                f"/api/projects/{pid}/context",
                headers=h_admin)).status_code == 404

    async def test_normal_member_vs_nonmember_visibility(
            self, client: AsyncClient):
        h_admin = await role_headers(client, "upc_v_padmin", role="admin")
        admin_uid = await _uid_of(client, h_admin)
        r = await client.post("/api/projects", headers=h_admin, json={
            "name": "可见性普通项目", "kind": "normal",
            "firstAdminUserId": admin_uid})
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        # 非成员用户:列表、详情、context 一致不可见(404)
        h_out = await register_and_login(client, "upc_v_outsider")
        ids = {p["id"] for p in (
            await client.get("/api/projects", headers=h_out)).json()}
        assert pid not in ids
        assert (await client.get(
            f"/api/projects/{pid}", headers=h_out)).status_code == 404
        assert (await client.get(
            f"/api/projects/{pid}/context", headers=h_out)).status_code == 404


# ── §20 库层不变量(直插负向)────────────────────────────────────────
class TestContainerDbInvariants:

    async def test_kind_check(self, client: AsyncClient):
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, is_default, status) VALUES "
                    "(gen_random_uuid(), '怪', 'weird', '', false, 'active')"))

    async def test_private_requires_owner(self, client: AsyncClient):
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, is_default, status) VALUES "
                    "(gen_random_uuid(), '无主私有', 'private', '', "
                    "false, 'active')"))

    async def test_normal_forbids_owner_and_default(
            self, client: AsyncClient):
        h = await register_and_login(client, "upc_inv_n")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, owner_id, is_default, status) VALUES "
                    "(gen_random_uuid(), '带主普通', 'normal', '', :uid, "
                    "false, 'active')"), {"uid": uid})
            await s.rollback()
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, is_default, status) VALUES "
                    "(gen_random_uuid(), '默认普通', 'normal', '', "
                    "true, 'active')"))
            await s.rollback()

    async def test_second_public_project_rejected(self, client: AsyncClient):
        """公共项目恰一行(uq_projects_public_kind;0040 种子已有一行)。"""
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO projects (project_uid, name, kind, "
                    "description, is_default, status) VALUES "
                    "(gen_random_uuid(), '公共2', 'public', '', "
                    "false, 'active')"))

    async def test_kind_immutable(self, client: AsyncClient):
        h = await register_and_login(client, "upc_inv_k")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "UPDATE projects SET kind='normal' "
                    "WHERE kind='private' AND owner_id=:uid"),
                    {"uid": uid})

    async def test_member_rows_only_on_normal(self, client: AsyncClient):
        """private/public 不落成员行(触发器;AC-06 无伪成员行)。"""
        h = await register_and_login(client, "upc_inv_m")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "SELECT id FROM projects WHERE kind='private' "
                "AND owner_id=:uid"), {"uid": uid})).scalar_one()
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO project_members (project_id, user_id, "
                    "role) VALUES (:pid, :uid, 'admin')"),
                    {"pid": pid, "uid": uid})
            await s.rollback()
            pub = (await s.execute(sa_text(
                "SELECT id FROM projects WHERE kind='public'"))).scalar_one()
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "INSERT INTO project_members (project_id, user_id, "
                    "role) VALUES (:pid, :uid, 'member')"),
                    {"pid": pub, "uid": uid})
            await s.rollback()

    async def test_active_normal_needs_admin_deferred(
            self, client: AsyncClient):
        """活跃 normal 无有效 admin → 提交被延迟约束拒绝;补 admin 通过。"""
        h = await register_and_login(client, "upc_inv_a")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "INSERT INTO projects (project_uid, name, kind, "
                "description, is_default, status) VALUES "
                "(gen_random_uuid(), '无管普通', 'normal', '', false, "
                "'active') RETURNING id"))).scalar_one()
            await s.flush()
            # 提交时触发:活跃 normal ≥1 有效 admin
            with pytest.raises(IntegrityError):
                await s.commit()
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "INSERT INTO projects (project_uid, name, kind, "
                "description, is_default, status) VALUES "
                "(gen_random_uuid(), '无管普通2', 'normal', '', false, "
                "'active') RETURNING id"))).scalar_one()
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"),
                {"pid": pid, "uid": uid})
            await s.commit()  # 有 admin → 通过

    async def test_last_admin_member_row_protected_at_db(
            self, client: AsyncClient):
        h_admin = await role_headers(client, "upc_inv_la", role="admin")
        admin_uid = await _uid_of(client, h_admin)
        r = await client.post("/api/projects", headers=h_admin, json={
            "name": "末位普通", "kind": "normal",
            "firstAdminUserId": admin_uid})
        assert r.status_code == 201
        pid = r.json()["id"]
        async with _db()() as s:
            # 再拉一个成员当 admin,随后删到只剩一个 → 删最后一个被拒
            h2 = await register_and_login(client, "upc_inv_la2")
            uid2 = await _uid_of(client, h2)
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"),
                {"pid": pid, "uid": uid2})
            await s.commit()
            # 两个 admin 在场:删其一合法
            await s.execute(sa_text(
                "DELETE FROM project_members WHERE project_id=:pid "
                "AND user_id=:uid"), {"pid": pid, "uid": uid2})
            await s.commit()
            # 只剩一个:再删 → 延迟约束拒绝
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "DELETE FROM project_members WHERE project_id=:pid "
                    "AND user_id=:uid"), {"pid": pid, "uid": admin_uid})
                await s.commit()

    async def test_deactivating_sole_admin_user_blocked(
            self, client: AsyncClient):
        """停用唯一有效 admin 的用户 → 延迟约束拒绝(§20 覆盖用户停用)。"""
        h = await register_and_login(client, "upc_inv_da")
        uid = await _uid_of(client, h)
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "INSERT INTO projects (project_uid, name, kind, "
                "description, is_default, status) VALUES "
                "(gen_random_uuid(), '停用连带', 'normal', '', false, "
                "'active') RETURNING id"))).scalar_one()
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"),
                {"pid": pid, "uid": uid})
            with pytest.raises(IntegrityError):
                await s.execute(sa_text(
                    "UPDATE users SET is_active=false WHERE id=:uid"),
                    {"uid": uid})
                await s.commit()


# ── 删除保护与用户处置 ───────────────────────────────────────────────
class TestDeleteProtectionsAndDisposal:

    async def test_default_space_delete_forbidden(self, client: AsyncClient):
        h = await register_and_login(client, "upc_del_d")
        spaces = await _private_spaces(client, h)
        default_id = next(p["id"] for p in spaces if p["isDefault"])
        r = await client.delete(f"/api/projects/{default_id}", headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "default_space_protected"

    async def test_owner_deletes_extra_space(self, client: AsyncClient):
        h = await register_and_login(client, "upc_del_e")
        r = await client.post("/api/projects", headers=h, json={
            "name": "待删空间", "kind": "private"})
        pid = r.json()["id"]
        r2 = await client.delete(f"/api/projects/{pid}", headers=h)
        assert r2.status_code == 204
        assert pid not in {p["id"] for p in await _private_spaces(client, h)}

    async def test_admin_cannot_delete_others_private_space(
            self, client: AsyncClient):
        h_owner = await register_and_login(client, "upc_del_o")
        h_admin = await role_headers(client, "upc_del_admin", role="admin")
        spaces = await _private_spaces(client, h_owner)
        for p in spaces:
            r = await client.delete(f"/api/projects/{p['id']}", headers=h_admin)
            assert r.status_code == 404  # 不可见统一 404

    async def test_member_api_rejects_private_project(
            self, client: AsyncClient):
        h = await register_and_login(client, "upc_del_m")
        uid = await _uid_of(client, h)
        default_id = (await _private_spaces(client, h))[0]["id"]
        r = await client.post(
            f"/api/projects/{default_id}/members", headers=h,
            json={"userId": uid, "role": "member"})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "project_kind_no_members"

    async def test_user_deletion_disposes_private_containers(
            self, client: AsyncClient):
        """§13:用户删除仅处置其私有容器及主体资源 —— 空间随账号消失。"""
        h_victim = await role_headers(client, "upc_del_victim", role="user")
        victim_uid = await _uid_of(client, h_victim)
        h_super = await role_headers(client, "upc_del_super", role="super_admin")
        r = await client.request(
            "DELETE", f"/api/users/{victim_uid}", headers=h_super,
            json={"disposal": "purge"})
        assert r.status_code == 204, r.text
        async with _db()() as s:
            n = (await s.execute(sa_text(
                "SELECT count(*) FROM projects WHERE owner_id=:uid"),
                {"uid": victim_uid})).scalar()
            assert n == 0


# ── context:§6 授权矩阵 × §7 能力矩阵投影 ───────────────────────────
class TestProjectContextProjection:

    async def _context(self, client, h, pid) -> dict:
        r = await client.get(f"/api/projects/{pid}/context", headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    async def test_private_owner_context(self, client: AsyncClient):
        h = await register_and_login(client, "upc_ctx_p")
        pid = (await _private_spaces(client, h))[0]["id"]
        ctx = await self._context(client, h, pid)
        assert ctx["kind"] == "private" and ctx["isDefault"] is True
        assert ctx["uid"]  # 不可复用身份非空
        perms = ctx["effectivePermissions"]
        assert perms["project.read"] is True
        assert perms["project.update"] is True
        assert perms["project.delete"] is False  # 默认空间保护
        assert perms["project.execute"] is True
        assert perms["project.content.write"] is True
        assert perms["project.member.manage"] is False  # §6:Owner 无成员治理
        assert perms["project.credential.manage"] is False  # §7:私有池关
        caps = ctx["capabilities"]
        assert caps["account_combo"] is True
        assert caps["execution"] is True
        assert caps["project_credential_pool"] is False
        assert caps["project_token"] is False
        assert caps["member_management"] is False  # 不适用 → False 投影

    async def test_public_context_matrix(self, client: AsyncClient):
        # 直插普通用户(注册面首个真人自动 super_admin,测不了非治理者)
        h = await role_headers(client, "upc_ctx_pub", role="user")
        pub = next(p for p in (
            await client.get("/api/projects", headers=h)).json()
            if p["kind"] == "public")
        ctx = await self._context(client, h, pub["id"])
        assert ctx["effectivePermissions"] == {
            **ctx["effectivePermissions"], "project.read": True}
        assert ctx["effectivePermissions"]["project.govern"] is False
        assert ctx["capabilities"]["execution"] is False
        assert ctx["capabilities"]["account_combo"] is False
        assert ctx["capabilities"]["project_carry"] is True  # 公共基线
        # Admin+ = 公共治理者:治理位开,但不是所有者/成员
        h_admin = await role_headers(client, "upc_ctx_admin", role="admin")
        ctx_admin = await self._context(client, h_admin, pub["id"])
        assert ctx_admin["effectivePermissions"]["project.govern"] is True
        assert ctx_admin["effectivePermissions"]["project.update"] is False

    async def test_normal_roles_context(self, client: AsyncClient):
        h_admin = await role_headers(client, "upc_ctx_nadmin", role="admin")
        admin_uid = await _uid_of(client, h_admin)
        pid = (await client.post("/api/projects", headers=h_admin, json={
            "name": "矩阵普通", "kind": "normal",
            "firstAdminUserId": admin_uid})).json()["id"]
        # 拉两个成员:member(可写)与 user(只读+执行)
        h_m = await register_and_login(client, "upc_ctx_nmember")
        h_u = await register_and_login(client, "upc_ctx_nuser")
        for hdrs, role in ((h_m, "member"), (h_u, "user")):
            uid = await _uid_of(client, hdrs)
            r = await client.post(f"/api/projects/{pid}/members",
                                  headers=h_admin,
                                  json={"userId": uid, "role": role})
            assert r.status_code == 201, r.text
        ctx_admin = await self._context(client, h_admin, pid)
        assert ctx_admin["effectivePermissions"]["project.member.manage"] is True
        assert ctx_admin["effectivePermissions"]["project.credential.manage"] is True
        assert ctx_admin["capabilities"]["project_credential_pool"] is True
        assert ctx_admin["capabilities"]["member_management"] is True
        ctx_m = await self._context(client, h_m, pid)
        assert ctx_m["effectivePermissions"]["project.content.write"] is True
        assert ctx_m["effectivePermissions"]["project.member.manage"] is False
        ctx_u = await self._context(client, h_u, pid)
        assert ctx_u["effectivePermissions"]["project.read"] is True
        assert ctx_u["effectivePermissions"]["project.execute"] is True
        assert ctx_u["effectivePermissions"]["project.content.write"] is False

    async def test_deactivate_sole_admin_returns_409(
            self, client: AsyncClient):
        h_member = await role_headers(client, "upc_ctx_sole", role="user")
        member_uid = await _uid_of(client, h_member)
        h_super = await role_headers(client, "upc_ctx_super", role="super_admin")
        pid = (await client.post("/api/projects", headers=h_super, json={
            "name": "停用闸普通", "kind": "normal",
            "firstAdminUserId": member_uid})).json()["id"]
        r = await client.patch(f"/api/users/{member_uid}", headers=h_super,
                               json={"is_active": False})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "user_last_project_admin"


# ── AC-31 并发不变量(§20:测试不能替代库层约束,但并发竞争下
#    库层不变量必须真实证明不被击穿)──────────────────────────────────
class TestConcurrentInvariants:
    """§20 点名的并发面:同时移除最后两个 Admin、停用与降级竞争、
    默认切换竞争。「删除与派发竞争」依赖 §13.1 删除状态机(流程未
    实现,已登记 M3/M5 交付),本类不覆盖。

    并发由两个**独立会话**的事务边界拼出:延迟约束触发器与部分唯一
    索引的求值都发生在 COMMIT,测试只须把两笔事务的写与提交顺序
    钉死,即是真实的交错竞争(谁先提交谁赢,后者在提交点被拒)。"""

    async def test_concurrent_removal_of_last_two_admins(
            self, client: AsyncClient):
        """两事务各删一名(仅剩的)admin:各自单独合法,交错提交后
        第二笔触发器已见对方的已提交删除 → 拒绝并回滚,末位不击穿。"""
        h_a = await register_and_login(client, "upc_cx_a")
        h_b = await register_and_login(client, "upc_cx_b")
        uid_a, uid_b = await _uid_of(client, h_a), await _uid_of(client, h_b)
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "INSERT INTO projects (project_uid, name, kind, "
                "description, is_default, status) VALUES "
                "(gen_random_uuid(), '并发末位', 'normal', '', false, "
                "'active') RETURNING id"))).scalar_one()
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"), {"pid": pid, "uid": uid_a})
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"), {"pid": pid, "uid": uid_b})
            await s.commit()
        # 交错:s1 删 A → s2 删 B → s1 提交(触发器尚见 B,过)
        # → s2 提交(触发器此刻已见 A 的已提交删除)→ 拒绝
        s1, s2 = _db()(), _db()()
        try:
            await s1.execute(sa_text(
                "DELETE FROM project_members WHERE project_id=:pid "
                "AND user_id=:uid"), {"pid": pid, "uid": uid_a})
            await s2.execute(sa_text(
                "DELETE FROM project_members WHERE project_id=:pid "
                "AND user_id=:uid"), {"pid": pid, "uid": uid_b})
            await s1.commit()
            with pytest.raises(IntegrityError):
                await s2.commit()
        finally:
            await s1.close()
            await s2.close()
        async with _db()() as s:
            roles = dict((await s.execute(sa_text(
                "SELECT user_id, role FROM project_members "
                "WHERE project_id=:pid"), {"pid": pid})).all())
            # s2 整笔回滚:B 复原留任;A 的删除已提交
            assert roles == {uid_b: "admin"}

    async def test_concurrent_deactivate_vs_demote(
            self, client: AsyncClient):
        """停用(admin 用户)与降级(另一 admin)交错:第二笔提交时
        触发器同时看到停用已提交 + 自己的降级 → 拒绝,不变量不击穿。"""
        h_a = await register_and_login(client, "upc_cx_da")
        h_b = await register_and_login(client, "upc_cx_db")
        uid_a, uid_b = await _uid_of(client, h_a), await _uid_of(client, h_b)
        async with _db()() as s:
            pid = (await s.execute(sa_text(
                "INSERT INTO projects (project_uid, name, kind, "
                "description, is_default, status) VALUES "
                "(gen_random_uuid(), '停用降级竞争', 'normal', '', false, "
                "'active') RETURNING id"))).scalar_one()
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"), {"pid": pid, "uid": uid_a})
            await s.execute(sa_text(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (:pid, :uid, 'admin')"), {"pid": pid, "uid": uid_b})
            await s.commit()
        # s1 停用 A;s2 把 B 降为 member;s1 提交(触发器 ⑤ 尚见 B
        # 在任)→ s2 提交(触发器 ③ 见 A 已停用 + 自己已降)→ 拒绝
        s1, s2 = _db()(), _db()()
        try:
            await s1.execute(sa_text(
                "UPDATE users SET is_active=false WHERE id=:uid"),
                {"uid": uid_a})
            await s2.execute(sa_text(
                "UPDATE project_members SET role='member' "
                "WHERE project_id=:pid AND user_id=:uid"),
                {"pid": pid, "uid": uid_b})
            await s1.commit()
            with pytest.raises(IntegrityError):
                await s2.commit()
        finally:
            await s1.close()
            await s2.close()
        async with _db()() as s:
            role_b = (await s.execute(sa_text(
                "SELECT role FROM project_members "
                "WHERE project_id=:pid AND user_id=:uid"),
                {"pid": pid, "uid": uid_b})).scalar_one()
            assert role_b == "admin"      # s2 回滚,B 复原留任
            active_a = (await s.execute(sa_text(
                "SELECT is_active FROM users WHERE id=:uid"),
                {"uid": uid_a})).scalar_one()
            assert active_a is False       # s1 的停用已提交

    async def test_concurrent_default_space_switch(
            self, client: AsyncClient):
        """默认切换竞争:部分唯一索引 uq_projects_private_default 是
        并发权威 —— 两笔切换交错,第二笔提交撞索引被拒,每用户恒
        至多一个默认。「用户级锁、先取消再设置」的服务面纪律属于
        默认切换端点(§4,随生命周期交付落地)。"""
        h = await register_and_login(client, "upc_cx_sw")
        pids = []
        for name in ("切换甲", "切换乙"):
            r = await client.post("/api/projects", headers=h, json={
                "name": name, "kind": "private"})
            assert r.status_code == 201, r.text
            pids.append(r.json()["id"])
        uid = await _uid_of(client, h)
        async with _db()() as s:
            old_default = (await s.execute(sa_text(
                "SELECT id FROM projects WHERE kind='private' "
                "AND owner_id=:uid AND is_default"), {"uid": uid}
            )).scalar_one()
        # 交错:s1 全套切换(旧默认取消 + 甲置默认)→ 提交;s2 在
        # 其后把乙置默认 → 提交撞索引(甲已默认)
        s1, s2 = _db()(), _db()()
        try:
            await s1.execute(sa_text(
                "UPDATE projects SET is_default=false "
                "WHERE id=:pid"), {"pid": old_default})
            await s1.execute(sa_text(
                "UPDATE projects SET is_default=true WHERE id=:pid"),
                {"pid": pids[0]})
            await s1.commit()
            # 唯一部分索引的违例在语句点即刻浮出(非提交点)
            with pytest.raises(IntegrityError):
                await s2.execute(sa_text(
                    "UPDATE projects SET is_default=true WHERE id=:pid"),
                    {"pid": pids[1]})
            await s2.rollback()
        finally:
            await s1.close()
            await s2.close()
        async with _db()() as s:
            defaults = (await s.execute(sa_text(
                "SELECT id FROM projects WHERE kind='private' "
                "AND owner_id=:uid AND is_default"), {"uid": uid}
            )).scalars().all()
            assert defaults == [pids[0]]    # 恰一个,先提交者胜
