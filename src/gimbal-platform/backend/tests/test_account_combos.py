"""账户组合批 1 后端测试面(账户组合设计方案 §9 批 1 子集,定稿 05)。

覆盖:CRUD 门与角色矩阵(v1 硬同区写门 = WRITER_ROLES,Admin 不旁路)、
条目校验复用 binding_alias 族、revision 仅条目 +1、服务端托管键
(整稿 PUT 恒剥保留/create 不收)、copy 恒剥、绑定同区矩阵、删除
in-use 409、项目内容闸五表与资源计数、审计行落账。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import User
from app.models.project import Project, ProjectMember
from app.models.service_identity import ServiceIdentity

from .helpers import make_draft, register_and_login, role_headers


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员行(角色矩阵批模板,test_authz_s11 同款)。"""
    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa.select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid, role=role))
        await db.commit()
        return proj.id


async def _seed_identity(alias: str, base_service: str) -> None:
    """登记一条身份条目(validate_binding_aliases 的数据面;env 必填)。"""
    from app.models import Environment

    async with db_module.SessionLocal() as db:
        env = (await db.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            env_row = Environment(name="ac-test", is_default=True)
            db.add(env_row)
            await db.flush()
            env = env_row.id
        db.add(ServiceIdentity(
            alias_name=alias, base_service=base_service, env_id=env,
            ref_mode="default", ref_username=""))
        await db.commit()


async def _mk_scenario(client, headers, sid: str) -> None:
    r = await client.post(
        "/api/scenarios", json=make_draft(sid), headers=headers)
    assert r.status_code == 201, r.text


async def _bind(client, headers, sid: str, combo_id) -> dict:
    r = await client.post(
        f"/api/scenarios/{sid}/account-combo",
        json={"comboId": combo_id}, headers=headers)
    return r


def _combo(r_json: dict) -> int:
    assert r_json.get("comboId"), r_json
    return r_json["comboId"]


async def test_combo_crud_roundtrip(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_owner")
    await _seed_identity("fin-qa1", "fin")
    body = {"name": "测试组合", "entries": [{"service": "fin",
                                           "alias": "fin-qa1"}]}
    r = await client.post("/api/account-combos", json=body, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["revision"] == 1
    assert r.json()["entries"] == body["entries"]

    # 列表:scope 分组(个人区在 personal)
    r = await client.get("/api/account-combos", headers=h)
    assert r.status_code == 200
    out = r.json()
    assert [c["id"] for c in out["personal"]] == [cid]
    assert out["projects"] == []

    # 单读 / 改名(元数据,不加 revision)
    r = await client.get(f"/api/account-combos/{cid}", headers=h)
    assert r.status_code == 200
    r = await client.patch(
        f"/api/account-combos/{cid}",
        json={"name": "改名后", "description": "说明"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 1  # 仅条目变化才 +1(§4.1)

    # 局外人 404(不泄露存在性)
    h2 = await register_and_login(client, "ac_other")
    assert (await client.get(
        f"/api/account-combos/{cid}", headers=h2)).status_code == 404

    # 删除
    assert (await client.delete(
        f"/api/account-combos/{cid}", headers=h)).status_code == 204
    assert (await client.get(
        f"/api/account-combos/{cid}", headers=h)).status_code == 404


async def test_combo_entry_validation(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_val")
    await _seed_identity("fin-qa1", "fin")
    await _seed_identity("jira-ops", "jira")
    # 别名未登记 → 复用 binding_alias_unknown(§4.1 码族)
    r = await client.post("/api/account-combos", json={
        "name": "x", "entries": [{"service": "fin", "alias": "ghost"}]},
        headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "binding_alias_unknown"
    # 异基础服务 → binding_alias_mismatch(不许借道改地址)
    r = await client.post("/api/account-combos", json={
        "name": "x", "entries": [{"service": "fin", "alias": "jira-ops"}]},
        headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "binding_alias_mismatch"
    # 形状/重复服务 → account_combo_entry_invalid
    r = await client.post("/api/account-combos", json={
        "name": "x", "entries": [
            {"service": "fin", "alias": "fin-qa1"},
            {"service": "fin", "alias": "fin-qa1"}]}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "account_combo_entry_invalid"
    # 空条目组合合法(纯声明,绑了再说)
    r = await client.post("/api/account-combos", json={
        "name": "空组合", "entries": []}, headers=h)
    assert r.status_code == 201, r.text


async def test_combo_name_conflict(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_dup")
    r = await client.post(
        "/api/account-combos", json={"name": "同名"}, headers=h)
    assert r.status_code == 201
    cid = r.json()["id"]
    r = await client.post(
        "/api/account-combos", json={"name": "同名"}, headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "account_combo_name_exists"
    r = await client.post(
        "/api/account-combos", json={"name": "另一名"}, headers=h)
    assert r.status_code == 201
    r = await client.patch(
        f"/api/account-combos/{cid}", json={"name": "另一名"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "account_combo_name_exists"


async def test_revision_bumps_only_on_entries(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_rev")
    await _seed_identity("fin-qa1", "fin")
    await _seed_identity("fin2-qa1", "fin2")
    r = await client.post("/api/account-combos", json={
        "name": "r", "entries": [{"service": "fin", "alias": "fin-qa1"}]},
        headers=h)
    cid = r.json()["id"]
    # 条目实质变化 → +1
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "entries": [{"service": "fin", "alias": "fin-qa1"},
                    {"service": "fin2", "alias": "fin2-qa1"}]},
        headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 2
    # 同值条目重发 → 不加(§4.1 仅**变化** +1)
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "entries": [{"service": "fin", "alias": "fin-qa1"},
                    {"service": "fin2", "alias": "fin2-qa1"}]},
        headers=h)
    assert r.json()["revision"] == 2
    # 改描述不加
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "description": "d"}, headers=h)
    assert r.json()["revision"] == 2
    # 条目清空 = 实质变化
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "entries": []}, headers=h)
    assert r.json()["revision"] == 3


async def test_project_scope_role_matrix(client, fresh_db) -> None:
    # 项目成员三角色 + 局外人 + 平台 Admin 非成员
    await register_and_login(client, "ac_padmin")   # 项目 admin
    await register_and_login(client, "ac_pmember")  # 项目 member
    await register_and_login(client, "ac_puser")    # 项目 user(只读)
    await register_and_login(client, "ac_outsider")
    plat = await role_headers(client, "ac_platadmin", role="super_admin")
    pid = await _mk_project("ac-proj", members={
        "ac_padmin": "admin", "ac_pmember": "member", "ac_puser": "user"})
    h_admin = await register_and_login(client, "ac_padmin")

    body = {"scope": "project", "projectId": pid, "name": "项目组合"}
    r = await client.post("/api/account-combos", json=body, headers=h_admin)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # member(WRITER_ROLES)可建
    h_member = await register_and_login(client, "ac_pmember")
    r = await client.post("/api/account-combos", json={
        **body, "name": "成员建"}, headers=h_member)
    assert r.status_code == 201, r.text
    # 项目 user 只读 → 403(§5.3 与 D1 同码)
    h_user = await register_and_login(client, "ac_puser")
    r = await client.post("/api/account-combos", json={
        **body, "name": "只读建"}, headers=h_user)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "project_role_readonly"
    # 局外人 → 404 不泄露
    h_out = await register_and_login(client, "ac_outsider")
    r = await client.post("/api/account-combos", json={
        **body, "name": "外人建"}, headers=h_out)
    assert r.status_code == 404
    # 平台 Admin 非成员不旁路(§5.3)
    r = await client.post("/api/account-combos", json={
        **body, "name": "平台旁路"}, headers=plat)
    assert r.status_code == 404

    # 读 = 成员任一角色;写 = WRITER_ROLES
    assert (await client.get(
        f"/api/account-combos/{cid}", headers=h_user)).status_code == 200
    assert (await client.get(
        f"/api/account-combos/{cid}", headers=h_out)).status_code == 404
    assert (await client.get(
        f"/api/account-combos/{cid}", headers=plat)).status_code == 404
    # 只读成员 PATCH → 403
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "description": "x"}, headers=h_user)
    assert r.status_code == 403
    # member 可 PATCH
    r = await client.patch(f"/api/account-combos/{cid}", json={
        "description": "成员改"}, headers=h_member)
    assert r.status_code == 200, r.text

    # 列表分组:项目成员看到项目组;?projectId 过滤
    r = await client.get("/api/account-combos", headers=h_user)
    groups = {g["projectId"]: g for g in r.json()["projects"]}
    assert pid in groups and cid in [c["id"] for c in groups[pid]["items"]]
    r = await client.get(f"/api/account-combos?projectId={pid}", headers=h_out)
    assert r.status_code == 404

    # 公共项目不建组合(422,§5.3)
    async with db_module.SessionLocal() as db:
        pub = (await db.execute(sa.select(Project.id).where(
            Project.kind == "public"))).scalar_one()
    r = await client.post("/api/account-combos", json={
        "scope": "project", "projectId": pub, "name": "公共组合"},
        headers=h_admin)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "public_project_create_forbidden"


async def test_default_atomic_swap(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_def")
    ids = []
    for i in range(2):
        r = await client.post("/api/account-combos", json={
            "name": f"d{i}", "isDefault": i == 0}, headers=h)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    # 第二次 isDefault=True 创建即清旧(create 面原子)
    r = await client.post("/api/account-combos", json={
        "name": "d2", "isDefault": True}, headers=h)
    assert r.status_code == 201
    out = (await client.get("/api/account-combos", headers=h)).json()
    defaults = [c["isDefault"] for c in out["personal"]]
    assert sum(defaults) == 1 and defaults[0] is True
    # set-default 原子切换
    r = await client.post(f"/api/account-combos/{ids[0]}/set-default",
                          headers=h)
    assert r.status_code == 200 and r.json()["isDefault"] is True
    out = (await client.get("/api/account-combos", headers=h)).json()
    assert sum(c["isDefault"] for c in out["personal"]) == 1
    # 换默认不加 revision(元数据)
    assert [c for c in out["personal"]
            if c["isDefault"]][0]["revision"] == 1


async def test_bind_read_channel_and_managed_key(client, fresh_db) -> None:
    """读取通道 + 服务端托管键(整稿 PUT 恒剥保留,§4.2)。"""
    h = await register_and_login(client, "ac_bind")
    await _seed_identity("fin-qa1", "fin")
    await _mk_scenario(client, h, "sc-bind")
    r = await client.post("/api/account-combos", json={
        "name": "组合A", "entries": [{"service": "fin",
                                     "alias": "fin-qa1"}]}, headers=h)
    cid = r.json()["id"]

    # 未绑定时读取通道 → comboId null
    r = await client.get("/api/scenarios/sc-bind/account-combo", headers=h)
    assert r.status_code == 200 and r.json()["comboId"] is None

    r = await _bind(client, h, "sc-bind", cid)
    assert r.status_code == 200, r.text
    assert r.json() == {"comboId": cid, "name": "组合A", "scope": "user",
                        "revision": 1,
                        "entries": [{"service": "fin", "alias": "fin-qa1"}]}
    # 读取通道恢复显示(comboId + 名称/revision/条目摘要)
    r = await client.get("/api/scenarios/sc-bind/account-combo", headers=h)
    assert r.json()["comboId"] == cid and r.json()["name"] == "组合A"

    # 模拟 auto-save 整稿 PUT(不带键)→ 绑定不被抹掉
    r = await client.put("/api/scenarios/sc-bind",
                         json=make_draft("sc-bind"), headers=h)
    assert r.status_code == 200, r.text
    r = await client.get("/api/scenarios/sc-bind/account-combo", headers=h)
    assert r.json()["comboId"] == cid

    # 整稿 PUT 带**异值** accountCombo → 恒剥,存量保留(§9 托管键钉)
    draft = make_draft("sc-bind")
    draft["definition"]["config"]["accountCombo"] = 999999
    r = await client.put("/api/scenarios/sc-bind", json=draft, headers=h)
    assert r.status_code == 200, r.text
    r = await client.get("/api/scenarios/sc-bind/account-combo", headers=h)
    assert r.json()["comboId"] == cid

    # create 面同样不收(导入/新建防走私)
    draft2 = make_draft("sc-smuggle")
    draft2["definition"]["config"]["accountCombo"] = cid
    r = await client.post("/api/scenarios", json=draft2, headers=h)
    assert r.status_code == 201, r.text
    r = await client.get("/api/scenarios/sc-smuggle/account-combo", headers=h)
    assert r.json()["comboId"] is None

    # 解绑 → null(再解绑幂等)
    r = await _bind(client, h, "sc-bind", None)
    assert r.status_code == 200 and r.json()["comboId"] is None
    r = await _bind(client, h, "sc-bind", None)
    assert r.json()["comboId"] is None


async def test_bind_zone_matrix(client, fresh_db) -> None:
    """v1 硬同区范围矩阵(§5.3)。"""
    await register_and_login(client, "ac_zadmin")
    await register_and_login(client, "ac_zmember")
    pid = await _mk_project("ac-zone", members={
        "ac_zadmin": "admin", "ac_zmember": "member"})
    pid2 = await _mk_project("ac-zone2", members={
        "ac_zadmin": "admin"})  # 双成员跨项目:即使双成员也拒
    h = await register_and_login(client, "ac_zadmin")

    await _seed_identity("fin-qa1", "fin")
    r = await client.post("/api/account-combos", json={
        "name": "个人组合"}, headers=h)
    personal = r.json()["id"]
    r = await client.post("/api/account-combos", json={
        "scope": "project", "projectId": pid, "name": "项目组合"},
        headers=h)
    proj_combo = r.json()["id"]
    r = await client.post("/api/account-combos", json={
        "scope": "project", "projectId": pid2, "name": "另项目组合"},
        headers=h)
    other_proj_combo = r.json()["id"]

    # 私有场景(属主本人)
    await _mk_scenario(client, h, "sc-priv")
    # 项目场景:直插 project_id(模拟「加入项目」后状态)
    await _mk_scenario(client, h, "sc-proj")
    async with db_module.SessionLocal() as db:
        from app.models.composer_scenario import ComposerScenario
        row = (await db.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-proj"))).scalar_one()
        row.project_id = pid
        await db.commit()

    # ① 个人组合 × 本人私有场景 → 200
    assert (await _bind(client, h, "sc-priv", personal)).status_code == 200
    # ② 项目组合 × 同项目场景 → 200
    assert (await _bind(client, h, "sc-proj", proj_combo)).status_code == 200
    # ③ 个人组合 × 本人项目场景 → 跨区 422
    r = await _bind(client, h, "sc-proj", personal)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "account_combo_scope_mismatch"
    # ④ 项目组合 × 另一项目场景(双成员)→ 422(硬同区,跨项目也拒)
    r = await _bind(client, h, "sc-proj", other_proj_combo)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "account_combo_scope_mismatch"
    # ⑤ 他人的个人组合 → 422 not_found(不可读,双态的场景侧半边);
    #    载体用成员自己可写的项目场景(私有场景对非属主本就 404 不可见)
    h_other = await register_and_login(client, "ac_zmember")
    r = await _bind(client, h_other, "sc-proj", personal)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "account_combo_not_found"
    # ⑥ 不存在的组合 id → 422 not_found
    r = await _bind(client, h, "sc-priv", 424242)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "account_combo_not_found"
    # ⑦ 公共场景不绑(发布恒剥的防御面)
    async with db_module.SessionLocal() as db:
        from app.models.composer_scenario import ComposerScenario
        from app.services.zone import public_project_id
        pub = await public_project_id(db)
        row = (await db.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-priv"))).scalar_one()
        row.project_id = pub
        await db.commit()
    r = await _bind(client, h, "sc-priv", personal)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "account_combo_scope_mismatch"
    # ⑧ 他人私有场景 → 404(写闸先行,不可见不泄露)
    await _mk_scenario(client, h_other, "sc-others")
    r = await _bind(client, h, "sc-others", personal)
    assert r.status_code in (403, 404)


async def test_copy_strips_binding(client, fresh_db) -> None:
    """copy 恒剥(§4.3):副本不携带组合引用;原件不动。"""
    h = await register_and_login(client, "ac_copy")
    await _seed_identity("fin-qa1", "fin")
    await _mk_scenario(client, h, "sc-copy")
    r = await client.post("/api/account-combos", json={
        "name": "c"}, headers=h)
    cid = r.json()["id"]
    assert (await _bind(client, h, "sc-copy", cid)).status_code == 200

    r = await client.post("/api/scenarios/sc-copy/copy", headers=h)
    assert r.status_code == 201, r.text
    copy_sid = r.json()["meta"]["scenarioId"]
    r = await client.get(f"/api/scenarios/{copy_sid}/account-combo",
                         headers=h)
    assert r.status_code == 200 and r.json()["comboId"] is None
    # 原件绑定不动
    r = await client.get("/api/scenarios/sc-copy/account-combo", headers=h)
    assert r.json()["comboId"] == cid


async def test_delete_in_use_and_reference_count(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_del")
    await _seed_identity("fin-qa1", "fin")
    await _mk_scenario(client, h, "sc-del")
    r = await client.post("/api/account-combos", json={
        "name": "被引用", "entries": [{"service": "fin",
                                       "alias": "fin-qa1"}]}, headers=h)
    cid = r.json()["id"]
    # 未引用 → 引用计数 0
    out = (await client.get("/api/account-combos", headers=h)).json()
    assert out["personal"][0]["referenceCount"] == 0

    assert (await _bind(client, h, "sc-del", cid)).status_code == 200
    # 引用计数 1
    out = (await client.get("/api/account-combos", headers=h)).json()
    assert out["personal"][0]["referenceCount"] == 1
    # 被引用删除 → 409 + 场景清单(§5.1 不解绑不给删)
    r = await client.delete(f"/api/account-combos/{cid}", headers=h)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "account_combo_in_use"
    assert detail["scenarios"][0]["scenarioId"] == "sc-del"
    # 解绑后可删
    assert (await _bind(client, h, "sc-del", None)).status_code == 200
    assert (await client.delete(
        f"/api/account-combos/{cid}", headers=h)).status_code == 204


async def test_project_delete_gate_and_counts(client, fresh_db) -> None:
    """项目内容闸四表 → 五表(§5.4)+ 资源计数。"""
    await register_and_login(client, "ac_gate_admin")
    h = await register_and_login(client, "ac_gate_admin")
    pid = await _mk_project("ac-gate", members={"ac_gate_admin": "admin"})
    r = await client.post("/api/account-combos", json={
        "scope": "project", "projectId": pid, "name": "占位组合"},
        headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    # 资源计数含 comboCount
    r = await client.get(f"/api/projects/{pid}", headers=h)
    assert r.status_code == 200
    assert r.json()["comboCount"] == 1

    # 有组合 → 项目删除 409
    plat = await role_headers(client, "ac_gate_plat", role="super_admin")
    r = await client.delete(f"/api/projects/{pid}", headers=plat)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "project_not_empty"
    # 清空组合 → 可删
    assert (await client.delete(
        f"/api/account-combos/{cid}", headers=h)).status_code == 204
    r = await client.delete(f"/api/projects/{pid}", headers=plat)
    assert r.status_code == 204


async def test_audit_rows_written(client, fresh_db) -> None:
    h = await register_and_login(client, "ac_audit")
    await _seed_identity("fin-qa1", "fin")
    await _mk_scenario(client, h, "sc-audit")
    r = await client.post("/api/account-combos", json={
        "name": "审计组合", "entries": [{"service": "fin",
                                        "alias": "fin-qa1"}]}, headers=h)
    cid = r.json()["id"]
    assert (await _bind(client, h, "sc-audit", cid)).status_code == 200

    from app.models.permission import AuditLog
    async with db_module.SessionLocal() as db:
        actions = set((await db.execute(sa.select(AuditLog.action))).scalars())
    assert "account_combo.write" in actions
    assert "account_combo.bind" in actions
