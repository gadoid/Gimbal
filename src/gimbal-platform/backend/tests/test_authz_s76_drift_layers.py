"""M2a S7.6:漂移与适配批次按层 + 公共层改动 → 项目层遮蔽通知。

三个钉子:
* drift 按层:``?scope=global|project|user``(分权 = carry 写面同口径:
  公共层 Admin+、项目层项目管理员、个人层本人);响应带层标签。
* carry 批带作用域:开批/快照/apply/rollback 全链落对应层;批次访问门
  随层(项目层批 = 项目管理员;个人层批 = 本人;Admin+ 不旁路);
  ``?scope=mine`` 含本人的分层 carry 批。
* 公共层值变更(路由 PUT / 适配批 op / 回滚)命中项目层同键 →
  ``carry.shadowed`` 通知项目管理员;项目/个人层写不通知。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import register_and_login, role_headers

# plate mock:fin-service 面只有 $.remark(其余绑定全 orphaned)
_EP = {"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
       "service": "fin-service"}
_FACE = {"request": {"declarations": [
    {"path": "$.remark", "state": "carry", "type": "string"}]}}


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa_select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid, role=role))
        await db.commit()
        return proj.id


async def _uid(username: str) -> int:
    from sqlalchemy import text

    from app.core import db as db_module

    async with db_module.SessionLocal() as s:
        return (await s.execute(text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _put_carry(
    client: AsyncClient, headers: dict, entries: dict, *,
    scope: str, service: str = "fin-service",
    project_id: int | None = None,
):
    params: dict = {"scope": scope}
    if project_id is not None:
        params["projectId"] = project_id
    return await client.put(
        f"/api/carry/bindings/{service}", headers=headers,
        params=params, json={"bindings": entries})


async def _notes(client: AsyncClient, type_: str) -> list:
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.permission import Notification

    async with db_module.SessionLocal() as db:
        return (await db.execute(sa_select(Notification).where(
            Notification.type == type_))).scalars().all()


# ── ① drift 按层 ─────────────────────────────────────────────────

class TestDriftLayers:

    async def test_global_layer_admin_only_and_label(self, client, plate):
        plate.items = [_EP]
        plate.fulls = {"fin.ep1": _FACE}
        h_member = await role_headers(client, "s76_dm", role="user")
        h_admin = await role_headers(client, "s76_dad", role="admin")
        # member 无参(默认 global)→ 403;admin → 200 带层标签
        r = await client.get("/api/carry/drift", headers=h_member)
        assert r.status_code == 403, r.text
        r = await client.get("/api/carry/drift", headers=h_admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scope"] == "project"   # global 请求 → 公共项目层
        assert isinstance(body["scopeId"], int)

    async def test_user_layer_own_drift(self, client, plate):
        """分层⑥(决策 8):个人层已收编为默认执行配置 —— drift 的
        scope=user 读写面一律 422 指路(/exec-configs)。"""
        h = await role_headers(client, "s76_um", role="user")
        r = await client.get("/api/carry/drift", headers=h,
                             params={"scope": "user"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "carry_user_scope_retired"

    async def test_project_layer_gate_matrix(self, client, plate):
        plate.items = [_EP]
        plate.fulls = {"fin.ep1": _FACE}
        h_member = await role_headers(client, "s76_pm", role="user")
        h_admin = await register_and_login(client, "s76_pad", "pw123456")
        h_out = await role_headers(client, "s76_po", role="user")
        pid = await _mk_project(
            "s76-dgate", members={"s76_pm": "member", "s76_pad": "admin"})
        await _put_carry(client, h_admin, {"$.proj": "v"}, scope="project",
                         project_id=pid)
        # 普通成员 403;外人 404;项目管理员 200(层标签 = 本项目)
        r = await client.get("/api/carry/drift", headers=h_member,
                             params={"scope": "project", "projectId": pid})
        assert r.status_code == 403, r.text
        r = await client.get("/api/carry/drift", headers=h_out,
                             params={"scope": "project", "projectId": pid})
        assert r.status_code == 404, r.text
        r = await client.get("/api/carry/drift", headers=h_admin,
                             params={"scope": "project", "projectId": pid})
        assert r.status_code == 200, r.text
        assert (r.json()["scope"], r.json()["scopeId"]) == ("project", pid)
        fin = next(s for s in r.json()["services"]
                   if s["service"] == "fin-service")
        assert fin["orphaned"] == ["$.proj"]


# ── ② carry 批带作用域 ───────────────────────────────────────────

async def _open_batch(client, headers, service=None, *, scope=None,
                      project_id=None) -> dict:
    json_: dict = {"service": service}
    params: dict = {}
    if scope is not None:
        json_["scope"] = scope
        if project_id is not None:
            json_["projectId"] = project_id
    r = await client.post("/api/adaptations/carry-batches", headers=headers,
                          json=json_, params=params or None)
    assert r.status_code == 201, r.text
    return r.json()


async def _add_op(client, headers, batch_id, op_type, payload) -> int:
    r = await client.post(f"/api/adaptations/batches/{batch_id}/ops",
                          headers=headers,
                          json={"opType": op_type, "payload": payload})
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestScopedCarryBatch:

    async def test_project_batch_end_to_end(self, client):
        """项目层批:apply 落项目层(公共层不动),rollback 还原项目层。"""
        from app.services import carry_store as cs
        from app.core import db as db_module

        h_adm = await role_headers(client, "s76_bad", role="admin")
        pid = await _mk_project("s76-batch", members={"s76_bad": "admin"})
        async with db_module.SessionLocal() as db:
            await cs.put_bindings(
                db, "fin-service", {"$.old": "proj"},
                updated_by_id=None, updated_by_name="t",
                scope=("project", pid))
            await db.commit()

        detail = await _open_batch(client, h_adm, "fin-service",
                                   scope="project", project_id=pid)
        assert detail["carryScope"] == "project"
        assert detail["carryScopeId"] == pid
        op = await _add_op(client, h_adm, detail["batchId"],
                           "renameCarryPath",
                           {"service": "fin-service", "from": "$.old",
                            "to": "$.new"})
        r = await client.post(f"/api/adaptations/ops/{op}/apply",
                              headers=h_adm)
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as db:
            pub = await cs.public_scope(db)
            assert await cs.get_bindings(
                db, "fin-service", ("project", pid)) == {"$.new": "proj"}
            # 公共层未被触碰
            assert await cs.get_bindings(db, "fin-service", pub) == {}

        r = await client.post(
            f"/api/adaptations/batches/{detail['batchId']}/rollback",
            headers=h_adm)
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as db:
            assert await cs.get_bindings(
                db, "fin-service", ("project", pid)) == {"$.old": "proj"}

    async def test_user_batch_and_mine_listing(self, client):
        """分层⑥(决策 8):个人层批随个人层退役 —— 开批 422 指路;
        ?scope=mine 镜头仍在(公共/项目层批的属主视图)。"""
        h = await role_headers(client, "s76_bum", role="user")
        r = await client.post("/api/adaptations/carry-batches", headers=h,
                              json={"service": "fin-service",
                                    "scope": "user"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "carry_user_scope_retired"

        r = await client.get("/api/adaptations/batches", headers=h,
                             params={"scope": "mine"})
        assert r.status_code == 200, r.text

    async def test_access_gates(self, client):
        h_member = await role_headers(client, "s76_gm", role="user")
        h_admin = await role_headers(client, "s76_gad", role="admin")
        pid = await _mk_project("s76-gate", members={"s76_gm": "member",
                                                     "s76_gad": "admin"})
        # member 开公共层批 → 403;开别人项目层批 → 404(非成员);
        # 开本项目层批 → 403(成员非管理员)
        r = await client.post("/api/adaptations/carry-batches",
                              headers=h_member, json={"service": None})
        assert r.status_code == 403, r.text
        r = await client.post("/api/adaptations/carry-batches",
                              headers=h_member,
                              json={"service": None, "scope": "project",
                                    "projectId": pid})
        assert r.status_code == 403, r.text
        r = await client.post("/api/adaptations/carry-batches",
                              headers=h_member,
                              json={"service": None, "scope": "project",
                                    "projectId": 999999})
        assert r.status_code == 404, r.text
        # member 触碰他人批的 op → 403(分层⑥起个人层批退役,用
        # h_other 的管理员身份开项目层批当「他人批」载体)
        h_other = await role_headers(client, "s76_go", role="admin")
        _pid2 = await _mk_project("s76-gate2", members={"s76_go": "admin"})
        detail = await _open_batch(client, h_other, None, scope="project",
                                   project_id=_pid2)
        r = await client.post(
            f"/api/adaptations/batches/{detail['batchId']}/ops",
            headers=h_member,
            json={"opType": "addCarryBinding",
                  "payload": {"path": "$.x", "value": "1"}})
        assert r.status_code == 403, r.text
        # 批的属主可加 op;Admin+ 旁路一切(公共层批照开)
        r = await client.post(
            f"/api/adaptations/batches/{detail['batchId']}/ops",
            headers=h_other,
            json={"opType": "addCarryBinding",
                  "payload": {"path": "$.x", "value": "1"}})
        assert r.status_code == 201, r.text
        r = await client.post("/api/adaptations/carry-batches",
                              headers=h_admin, json={"service": None})
        assert r.status_code == 201, r.text


# ── ③ 公共层改动 → 项目层遮蔽通知 ───────────────────────────────

class TestShadowNotify:

    async def test_public_put_shadows_project_layer(self, client):
        h_admin = await role_headers(client, "s76_sad", role="admin")
        h_padmin = await role_headers(client, "s76_spad", role="user")
        pid = await _mk_project("s76-shadow", members={"s76_spad": "admin"})
        await _put_carry(client, h_padmin, {"$.host": "proj"},
                         scope="project", project_id=pid)
        # 公共层写 $.host(被项目层覆盖遮住)+ $.other(项目层没有)
        r = await _put_carry(client, h_admin,
                             {"$.host": "v2", "$.other": "o"}, scope="global")
        assert r.status_code == 200, r.text
        notes = await _notes(client, "carry.shadowed")
        assert len(notes) == 1
        n = notes[0]
        assert n.user_id == await _uid("s76_spad")
        assert n.payload["projectId"] == pid
        assert n.payload["service"] == "fin-service"
        assert n.payload["keys"] == ["$.host"]   # $.other 不在项目层,不报

    async def test_project_layer_write_does_not_notify(self, client):
        h_padmin = await role_headers(client, "s76_qpad", role="user")
        pid = await _mk_project("s76-quiet", members={"s76_qpad": "admin"})
        r = await _put_carry(client, h_padmin, {"$.a": "1"},
                             scope="project", project_id=pid)
        assert r.status_code == 200, r.text
        assert await _notes(client, "carry.shadowed") == []

    async def test_public_batch_op_and_rollback_notify(self, client):
        from app.services import carry_store as cs
        from app.core import db as db_module

        h_admin = await role_headers(client, "s76_nad", role="admin")
        h_padmin = await role_headers(client, "s76_npad", role="user")
        pid = await _mk_project("s76-note", members={"s76_npad": "admin"})
        async with db_module.SessionLocal() as db:
            await cs.put_bindings(
                db, "fin-service", {"$.old": "proj"},
                updated_by_id=None, updated_by_name="t",
                scope=("project", pid))
            await cs.put_bindings(
                db, "fin-service", {"$.old": "pub"},
                updated_by_id=None, updated_by_name="t",
                scope=await cs.public_scope(db))
            await db.commit()

        # 公共层批 rename $.old → $.new:项目层 $.old 悬空 → 通知
        detail = await _open_batch(client, h_admin, "fin-service")
        op = await _add_op(client, h_admin, detail["batchId"],
                           "renameCarryPath",
                           {"service": "fin-service", "from": "$.old",
                            "to": "$.new"})
        # 留一条 pending:单 op 应用完即 completed,rollback 只接受
        # open/applying(既有不变量)
        await _add_op(client, h_admin, detail["batchId"],
                      "addCarryBinding",
                      {"service": "fin-service", "path": "$.keep",
                       "value": "pending"})
        r = await client.post(f"/api/adaptations/ops/{op}/apply",
                              headers=h_admin)
        assert r.status_code == 200, r.text
        notes = await _notes(client, "carry.shadowed")
        assert len(notes) == 1
        # 只报项目层实际覆盖的键($.old 悬空;$.new 项目层没有,不报)
        assert notes[0].payload["keys"] == ["$.old"]

        # 回滚恢复公共层 → 又一轮通知(值变更与通知同判)
        r = await client.post(
            f"/api/adaptations/batches/{detail['batchId']}/rollback",
            headers=h_admin)
        assert r.status_code == 200, r.text
        notes = await _notes(client, "carry.shadowed")
        assert len(notes) == 2
