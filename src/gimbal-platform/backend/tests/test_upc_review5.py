"""评审五轮回归:P1-1 run/materialize blocked 装配闸 / P2-1 凭证写门
探测面 / P2-2 实例凭证聚合投影 / P2-3 嵌套形状补漏 / P2-4 rowIndex 输入
错误面 / P2-6 锁交错 barrier 并发(自降级/自移除)。

布景单源复用 test_upc_review4(_seed_exec_suite / _interleaved 等)。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text as sa_text

from app.core import db as db_module
from tests.helpers import mk_normal_project, register_and_login, role_headers
from tests.test_suites_validate import _mk, _patch_convert
from tests.test_upc_review4 import (  # noqa: F401  布景/探针单源
    _counting_resolve, _interleaved, _seed_exec_suite, _uid_of)


# ── P1-1:run 与 materialize 同闸(契约不再裂缝)─────────────────────

async def test_run_orchestration_blocked_rejected_before_resolve(
        client: AsyncClient, monkeypatch):
    """P1-1:validate 拒而 run 收 201 的契约裂缝 —— run 现在与 validate
    共用 _assembly_gate,blocked 整图 403 units_not_runnable,且**早于
    execution 创建与一切凭证解析**(resolve_exec_auths 零调用)。"""
    h_exec, sid, _a, _b = await _seed_exec_suite(client, "rn")
    calls = _counting_resolve(monkeypatch)
    r = await client.post(f"/api/suites/{sid}/run", headers=h_exec, json={})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "units_not_runnable"
    assert calls["resolve"] == 0, "run 装配闸必须先于凭证解析"


async def test_resolve_graph_units_blocked_raises(client):
    """P1-1 单源兜底:``resolve_graph_units`` 是 validate 预检 / 凭证
    清单(missing_auth_aliases)/ materialize_graph(worker 侧重物化)
    的共同路径,blocked 方案在此直接 GraphDispatchError —— 即使绕过
    路由预检也无法进入物化/解密;ready 对照腿照常通过(探针自证)。"""
    from app.services import graph_dispatch as gd

    _h, _sid, a_sid, b_sid = await _seed_exec_suite(client, "mg")
    async with db_module.SessionLocal() as s:
        with pytest.raises(gd.GraphDispatchError, match="blocked"):
            await gd.resolve_graph_units(
                s, [{"ref": "b", "scenarioId": "sc-r5xmgb",
                     "schemeId": b_sid}], owner_id=1)
        resolved = await gd.resolve_graph_units(
            s, [{"ref": "a", "scenarioId": "sc-r5xmga",
                 "schemeId": a_sid}], owner_id=1)
        assert len(resolved) == 1


# ── P2-1:归档态不再泄露项目存在性/生命周期 ─────────────────────────

async def test_archived_credential_write_no_lifecycle_probe(client):
    """P2-1:归档闸移到角色校验之后 —— 非成员访问归档项目凭证写端点
    404(与 active 项目同面),不再以 409 + 具体状态当探针;管理员成员
    归档闸语义不变(409 project_not_active)。"""
    from app.models.project import Project
    from sqlalchemy import update as sa_update

    h_own = await register_and_login(client, "r5p1_own", "pw123456")
    h_out = await register_and_login(client, "r5p1_out", "pw123456")
    pid = await mk_normal_project("r5p1-proj", {"r5p1_own": "admin"})
    async with db_module.SessionLocal() as s:
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()
    body = {"system": "fin", "envId": 1, "username": "u", "password": "p"}
    r = await client.post(f"/api/projects/{pid}/credentials",
                          headers=h_out, json=body)
    assert r.status_code == 404, r.text          # 修前 409 project_not_active
    r = await client.post(f"/api/projects/{pid}/credentials",
                          headers=h_own, json=body)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"


# ── P2-2:实例凭证聚合与凭证列表同一投影 ────────────────────────────

async def test_archived_instance_credential_matches_frozen(client):
    """P2-2:归档项目的实例×凭证聚合 canManage=False 且 username 脱敏
    (修前归档管理员仍见 canManage=true + 明文账号名)。"""
    from app.core.security import fernet_encrypt
    from app.models.auth_account import AuthAccount
    from app.models.environment import Environment
    from app.models.project import Project
    from app.models.system_env_instance import SystemEnvInstance
    from sqlalchemy import update as sa_update

    h_own = await register_and_login(client, "r5p2_own", "pw123456")
    pid = await mk_normal_project("r5p2-proj", {"r5p2_own": "admin"})
    async with db_module.SessionLocal() as s:
        env = Environment(name="r5p2-env", description="")
        s.add(env)
        await s.flush()
        s.add(SystemEnvInstance(system="fin", env_id=env.id))
        s.add(AuthAccount(owner_id=None, project_id=pid, system="fin",
                          env_id=env.id, username="r5-secret",
                          password_enc=fernet_encrypt("pw123456")))
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()
        env_id = env.id
    r = await client.get(
        f"/api/projects/{pid}/instance-credential-matches?envId={env_id}",
        headers=h_own)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canManage"] is False            # 修前 True
    creds = [c for i in body["instances"]
             for c in i["projectCredentials"]]
    assert creds, "布景缺项目凭证行"
    assert all(c["username"] == "" for c in creds)


# ── P2-3:嵌套形状补漏(payload falsy / datasetId / rowIndexes /
#    旧式 dataSetIds)───────────────────────────────────────────────

class TestBundleShapeRound5:
    async def _seed_bundle(self, client, tag: str):
        from tests.helpers import default_space_id
        from tests.test_upc_m2_domain import TestAssetBundleRoundtrip

        h, _space, _combo, _ds, _qa = await TestAssetBundleRoundtrip \
            ._seed_source(None, client, tag)
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b = await register_and_login(client, f"r5sh_{tag}_b", "pw123456")
        uid_b = await _uid_of(client, f"r5sh_{tag}_b")
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        return h_b, space_b, bundle

    async def test_nested_shape_holes_are_422(self, client):
        """P2-3:payload 空数组/数字(or {} 吞 falsy)、selection 条目
        datasetId 非字符串(重指映射 TypeError)、rowIndexes 非整数数组、
        旧式 dataSetIds 标量/非字符串元素(规范化迭代 TypeError)——
        修前 500,收口后统一 422 asset_bundle_shape_invalid。"""
        h_b, space_b, bundle = await self._seed_bundle(client, "f5")

        def tampered(mut):
            b = dict(bundle)
            mut(b)
            return b

        cases = [
            ("payload 空数组",
             lambda b: b["schemes"][0].__setitem__("payload", [])),
            ("payload 数字",
             lambda b: b["schemes"][0].__setitem__("payload", 0)),
            ("datasetId 列表",
             lambda b: b["schemes"][0].__setitem__("payload", {
                 "dataSetSelection": [{"datasetId": [], "rowIndexes": []}]})),
            ("rowIndexes 字符串",
             lambda b: b["schemes"][0].__setitem__("payload", {
                 "dataSetSelection": [{"datasetId": "ds-001",
                                       "rowIndexes": ["x"]}]})),
            ("dataSetIds 标量",
             lambda b: b["schemes"][0].__setitem__("payload", {
                 "dataSetIds": 7})),
            ("dataSetIds 非字符串元素",
             lambda b: b["schemes"][0].__setitem__("payload", {
                 "dataSetIds": [7]})),
        ]
        for name, mut in cases:
            r = await client.post(
                f"/api/projects/{space_b}/asset-bundles",
                headers=h_b, json=tampered(mut))
            assert r.status_code == 422, f"{name}: {r.text}"
            assert (r.json()["detail"]["code"]
                    == "asset_bundle_shape_invalid"), name


# ── P2-4:rowIndex 用户输入错误面 ───────────────────────────────────

async def test_composition_row_shape_validated_at_write_boundary(client):
    """P2-4 写边界:非法 row/schemeId 结构在 composition 落库前 422
    mode_config_invalid(修前存进 mode_config,物化期才炸)。"""
    await register_and_login(client, "r5p4_boot", "r4_bootpass123")
    h = await register_and_login(client, "r5p4_own", "pw123456")
    await _mk(client, h, "sc-r5p4")
    sid = (await client.post("/api/suites", headers=h,
                             json={"name": "行形状", "description": ""})
           ).json()["suiteId"]
    bad_units = [
        {"ref": "a", "row": {"datasetId": "ds-001", "rowIndex": "abc"}},
        {"ref": "a", "row": {"datasetId": "ds-001", "rowIndex": -1}},
        {"ref": "a", "row": {"datasetId": 7}},
        {"ref": "a", "row": "oops"},
        {"ref": "a", "schemeId": 7},
    ]
    for u in bad_units:
        r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                             json={"rev": 0, "mode": "chain",
                                   "members": [{"scenarioId": "sc-r5p4"}],
                                   "modeConfig": {"units": {"sc-r5p4": u}}})
        assert r.status_code == 422, f"{u}: {r.text}"
        assert r.json()["detail"]["code"] == "mode_config_invalid", u


async def test_validate_reports_row_input_error_not_degraded(
        client, monkeypatch):
    """P2-4 物化面:存量/绕过写入的非法 rowIndex —— validate 报
    materialize_failed error(ok=false),不再被基础设施降级分支吞成
    degraded warning(修前「预检绿 + degraded=true + run 201」)。"""
    from app.models.suite import Suite

    _patch_convert(monkeypatch)
    await register_and_login(client, "r5p4b_boot", "r4_bootpass123")
    h = await register_and_login(client, "r5p4b_own", "pw123456")
    await _mk(client, h, "sc-r5p4b")
    sid = (await client.post("/api/suites", headers=h,
                             json={"name": "旧行", "description": ""})
           ).json()["suiteId"]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                         json={"rev": 0, "mode": "chain",
                               "members": [{"scenarioId": "sc-r5p4b"}],
                               "modeConfig": {"units": {"sc-r5p4b": {
                                   "ref": "a",
                                   "row": {"datasetId": "ds-001",
                                           "rowIndex": 0}}}}})
    assert r.status_code == 200, r.text
    # 绕过写边界直改库(存量行形态):rowIndex 变字符串
    async with db_module.SessionLocal() as s:
        row = await s.get(Suite, sid)
        cfg = dict(row.mode_config or {})
        u = dict((cfg.get("units") or {}).get("sc-r5p4b") or {})
        u["row"] = {"datasetId": "ds-001", "rowIndex": "oops"}
        cfg["units"] = {"sc-r5p4b": u}
        row.mode_config = cfg
        await s.commit()
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["degraded"] is False
    assert any(i["code"] == "materialize_failed" for i in body["items"]), \
        body["items"]


# ── P2-6:自降级/自移除并发(barrier 强制交错)───────────────────────

async def test_self_demote_concurrent_barrier(client, monkeypatch):
    """P2-5/P2-6:两名管理员并发**自降级** —— barrier 强制 A 持锁未
    提交时 B 才入场。修前各只锁己行、都读到「还有两名管理员」双双
    放行,后提交者撞延迟触发器 trg_project_member_admin_invariant →
    未映射 500;收口后项目行锁全序化:B 在锁内按真实计数被末位保护
    拒绝(409),恰好一名管理员留存。"""
    from tests.test_authz_s14_projects import _create_project

    h_a = await _h_user(client, "r5sd_a")
    h_b = await _h_user(client, "r5sd_b")
    a_uid = await _uid_of(client, "r5sd_a")
    b_uid = await _uid_of(client, "r5sd_b")
    h_admin = await role_headers(client, "r5sd_adm", role="admin")
    pid = (await _create_project(
        client, h_admin, "r5sd-proj", a_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_a, json={"userId": b_uid,
                                             "role": "admin"})
    assert r.status_code == 201, r.text

    s1, s2 = await _interleaved(
        client.patch(f"/api/projects/{pid}/members/{a_uid}",
                     headers=h_a, json={"role": "member"}),
        client.patch(f"/api/projects/{pid}/members/{b_uid}",
                     headers=h_b, json={"role": "member"}),
        monkeypatch)
    # A 先持锁先提交(2→1 成功);B 锁内重验:仅剩自己一名管理员 → 409
    assert (s1, s2) == (200, 409), f"自降级并发结果: {s1} / {s2}"
    n_admins = await _admin_count(pid)
    assert n_admins == 1


async def test_self_remove_concurrent_barrier(client, monkeypatch):
    """P2-5/P2-6:两名管理员并发**自移除** —— 同上,后到者锁内末位
    保护 409;库内恰留一名管理员(不再以延迟触发器 500 收场)。"""
    from tests.test_authz_s14_projects import _create_project

    h_a = await _h_user(client, "r5sr_a")
    h_b = await _h_user(client, "r5sr_b")
    a_uid = await _uid_of(client, "r5sr_a")
    b_uid = await _uid_of(client, "r5sr_b")
    h_admin = await role_headers(client, "r5sr_adm", role="admin")
    pid = (await _create_project(
        client, h_admin, "r5sr-proj", a_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_a, json={"userId": b_uid,
                                             "role": "admin"})
    assert r.status_code == 201, r.text

    s1, s2 = await _interleaved(
        client.delete(f"/api/projects/{pid}/members/{a_uid}", headers=h_a),
        client.delete(f"/api/projects/{pid}/members/{b_uid}", headers=h_b),
        monkeypatch)
    # A 先移除自己(204);B 锁内重验:剩余有效管理员 0 → 409
    assert (s1, s2) == (204, 409), f"自移除并发结果: {s1} / {s2}"
    assert await _admin_count(pid) == 1


async def _h_user(client: AsyncClient, username: str) -> dict:
    return await register_and_login(client, username, "pw123456")


async def _admin_count(pid: int) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa_text(
            "SELECT count(*) FROM project_members "
            "WHERE project_id=:pid AND role='admin'"),
            {"pid": pid})).scalar_one()
