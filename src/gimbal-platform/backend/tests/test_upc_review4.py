"""评审四轮回归:P1-1 归档删除成员 / P1-2 归档凭证写 / P2-3 资产包
schemeId 唯一与 selection 形状 / P2-4 编排闸全图前置 / P2-5 裸基线不误报 /
P2-7 保存×修复并发无 500 / P2-8 成员管理在途并发无死锁。"""
from __future__ import annotations

import asyncio

from httpx import AsyncClient
from sqlalchemy import select, text as sa_text

from app.core import db as db_module
from tests.helpers import make_draft, mk_normal_project, register_and_login, \
    role_headers, seed_legacy_users


# ── P1-1:归档项目 remove_member 与投影 ─────────────────────────────

async def test_archived_project_blocks_remove_member(client: AsyncClient):
    """修前 remove 缺 active 闸:归档后仍可撤销成员访问并联动暂停实例。
    收口后与 add/patch 同口径 409;列表 canManage 投影同步 False。"""
    from app.models.project import Project
    from sqlalchemy import update as sa_update

    h_own = await register_and_login(client, "r4rm_own", "pw123456")
    h_mem = await register_and_login(client, "r4rm_mem", "pw123456")
    pid = await mk_normal_project("r4rm-proj", {
        "r4rm_own": "admin", "r4rm_mem": "member"})
    uid_mem = (await client.get("/api/auth/me", headers=h_mem)
               ).json()["user"]["id"]

    async with db_module.SessionLocal() as s:
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()

    r = await client.delete(f"/api/projects/{pid}/members/{uid_mem}",
                            headers=h_own)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    # 读面投影:canManage 收敛 False
    r = await client.get(f"/api/projects/{pid}", headers=h_own)
    assert r.status_code == 200, r.text
    assert r.json()["canManage"] is False


# ── P1-2:归档项目凭证管理写 ────────────────────────────────────────

async def test_archived_project_blocks_credential_writes(
        client: AsyncClient):
    """运行时探针已证修前归档项目新建凭证 201。收口后四类写(经统一
    _manage_gate)409 project_not_active;列表 canManage False。"""
    from app.models.project import Project
    from sqlalchemy import update as sa_update

    h_own = await register_and_login(client, "r4cr_own", "pw123456")
    pid = await mk_normal_project("r4cr-proj", {"r4cr_own": "admin"})

    # 环境行(body 必填 envId;闸在业务校验前,体须合法才能探到闸)
    from app.models.environment import Environment

    async with db_module.SessionLocal() as s:
        env = Environment(name="r4cr-env", description="")
        s.add(env)
        await s.flush()
        env_id = env.id
        await s.execute(sa_update(Project).where(
            Project.id == pid).values(status="archived"))
        await s.commit()

    r = await client.post(f"/api/projects/{pid}/credentials", headers=h_own,
                          json={"system": "fin", "envId": env_id,
                                "username": "u", "password": "p"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    r = await client.get(f"/api/projects/{pid}/credentials", headers=h_own)
    assert r.status_code == 200, r.text
    assert r.json()["canManage"] is False


# ── P2-3:资产包 schemeId 唯一 + selection 形状 ─────────────────────

class TestBundleShapeRound4:
    async def _seed_bundle(self, client, tag: str):
        from tests.test_upc_m2_domain import TestAssetBundleRoundtrip

        return await TestAssetBundleRoundtrip._seed_source(
            None, client, tag)

    async def _restore(self, client, h_b, uid_b, bundle):
        from tests.helpers import default_space_id

        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        return await client.post(
            f"/api/projects/{space_b}/asset-bundles",
            headers=h_b, json=bundle)

    async def test_duplicate_scheme_ids_rejected(self, client):
        """重复 schemeId + defaultSchemeId 指向重复项 → 统一 422 形状错
        (修前两行 is_default=True 撞部分唯一索引 → 未捕获 500)。"""
        from tests.helpers import default_space_id

        h, _space, _combo, _ds, qa_id = await self._seed_bundle(client, "d4")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        # 复制回归方案行(schemeId 相同、默认标记指向它)
        dup = dict(next(s for s in bundle["schemes"]
                        if s["schemeId"] == qa_id))
        bundle["schemes"] = [*bundle["schemes"], dup]
        bundle["defaultSchemeId"] = qa_id
        bundle["schemes"] = [
            dict(s, isDefault=(s["schemeId"] == qa_id))
            for s in bundle["schemes"]]
        h_b = await register_and_login(client, "r4_d4_b", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_shape_invalid")

    async def test_selection_not_array_rejected(self, client):
        """dataSetSelection 非数组 → 422(修前行级重指迭代 TypeError →
        500;含选择的默认候选校验也读不到该键)。"""
        from tests.helpers import default_space_id

        h, _space, _combo, _ds, _qa = await self._seed_bundle(client, "s4")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        bundle["schemes"] = [
            dict(s, payload=dict(s["payload"], dataSetSelection=7))
            if s["schemeId"] != bundle["defaultSchemeId"] else s
            for s in bundle["schemes"]]
        h_b = await register_and_login(client, "r4_s4_b", "pw123456")
        uid_b = (await client.get("/api/auth/me", headers=h_b)
                 ).json()["user"]["id"]
        async with db_module.SessionLocal() as s:
            space_b = await default_space_id(s, uid_b)
            await s.commit()
        r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                              headers=h_b, json=bundle)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_shape_invalid")


# ── P2-4/P2-5:编排闸全图前置与裸基线口径 ───────────────────────────

async def _seed_exec_suite(client, tag: str):
    """评审五轮 P2-7 布景升级:**外部执行人** + ready 单元携带存量内置
    凭证基座。修前布景是属主自检场景 —— builtin_auth_shadowed 在属主
    分支直接返回空清单,旧交替循环同样保持零凭证解析,测试无法证伪
    两遍法(假绿)。新布景下发起人 ≠ 场景属主且 ready 单元 config.users
    非空:交替循环会对 ready 单元真实解析凭证(≥1 次),两遍法则整图
    装配闸先拒(0 次)。"""
    from tests.test_suites_validate import STEPS

    h_own = await register_and_login(client, f"r5x_{tag}_own", "pw123456")
    h_exec = await register_and_login(client, f"r5x_{tag}_exec", "pw123456")
    uid_own = await _uid_of(client, f"r5x_{tag}_own")
    pid = await mk_normal_project(f"r5x-{tag}-proj", {
        f"r5x_{tag}_own": "admin", f"r5x_{tag}_exec": "member"})
    for suffix in ("a", "b"):
        r = await client.post(f"/api/scenarios?projectId={pid}",
                              headers=h_own,
                              json=make_draft(f"sc-r5x{tag}{suffix}",
                                              steps=STEPS))
        assert r.status_code in (200, 201), r.text
    await seed_legacy_users(f"sc-r5x{tag}a", {
        "qa-legacy": {"username": "u", "password": "p"}})

    async def _mk_scheme(scen: str) -> str:
        r = await client.post(f"/api/scenarios/{scen}/run-schemes",
                              headers=h_own,
                              json={"name": "单元方案", "isDefault": False,
                                    "dataSetSelection": [],
                                    "injectionEntryIds": [],
                                    "serviceBindings": {}, "options": {
                                        "step_from": None, "step_to": None,
                                        "n_runs": 1, "parallel": 1,
                                        "subscribe": None}})
        assert r.status_code == 201, r.text
        return r.json()["schemeId"]

    a_sid = await _mk_scheme(f"sc-r5x{tag}a")
    b_sid = await _mk_scheme(f"sc-r5x{tag}b")
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import scheme_repair

    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == b_sid))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid_own, actor_name="seed")
        await s.commit()

    sid = (await client.post(
        "/api/suites", headers=h_exec,
        json={"name": "外部执行人编排", "projectId": pid})
    ).json()["suiteId"]
    body = {"rev": 0, "mode": "compose",
            "members": [{"scenarioId": f"sc-r5x{tag}a"},
                        {"scenarioId": f"sc-r5x{tag}b"}],
            "modeConfig": {"units": {
                f"sc-r5x{tag}a": {"ref": "a", "schemeId": a_sid},
                f"sc-r5x{tag}b": {"ref": "b", "needs": [f"sc-r5x{tag}a"],
                                  "schemeId": b_sid}}}}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h_exec,
                         json=body)
    assert r.status_code == 200, r.text
    return h_exec, sid, a_sid, b_sid


def _counting_resolve(monkeypatch):
    """``run_prepare.resolve_exec_auths``(解密/身份解析)调用计数探针。"""
    from app.services import run_prepare

    calls = {"resolve": 0}
    orig = run_prepare.resolve_exec_auths

    async def counting(factory, *a, **k):
        calls["resolve"] += 1
        return await orig(factory, *a, **k)

    monkeypatch.setattr(run_prepare, "resolve_exec_auths", counting)
    return calls


async def test_graph_validate_ready_first_then_blocked_zero_resolve(
        client: AsyncClient, monkeypatch):
    """P2-4 + P2-7:ready 单元在前、blocked 单元在后 —— 修前交替循环会
    先解密前序 ready 单元凭证再发现整图禁跑;两遍法下凭证解析零调用。
    布景为**外部执行人**(发起人 ≠ 场景属主,ready 单元携带存量内置
    凭证基座):属主自检分支不再吞探针,计数真实可判(修前布景假绿)。"""
    from tests.test_suites_validate import _patch_convert

    _patch_convert(monkeypatch)
    h_exec, sid, _a, _b = await _seed_exec_suite(client, "va")
    calls = _counting_resolve(monkeypatch)
    r = await client.post(f"/api/suites/{sid}/validate", headers=h_exec)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert any(i["code"] == "units_not_runnable" for i in body["items"]), \
        body["items"]
    assert calls["resolve"] == 0, "blocked 在后也必须零凭证解析(两遍法)"


async def test_graph_validate_bare_baseline_unit_not_blocked_report(
        client: AsyncClient, monkeypatch):
    """P2-5:单元未配 schemeId 且未选行 = 裸基线 —— 默认方案 blocked
    不得误报禁跑(执行器本就不选方案);预检给 no_scheme 提示。"""
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import scheme_repair
    from tests.test_suites_validate import _mk, _patch_convert

    await register_and_login(client, "r4b_boot", "r4_bootpass123")
    h = await register_and_login(client, "r4b_own", "r4_ownpass123")
    _patch_convert(monkeypatch)
    await _mk(client, h, "sc-va")
    await _mk(client, h, "sc-vb")
    uid = (await client.get("/api/auth/me", headers=h)
           ).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-va"))).scalars().all()
        for row in rows:      # 默认方案(含钩子物化)全置 blocked
            await scheme_repair.mark_blocked(
                s, row, reason="combo_missing", action="import.blocked",
                actor_id=uid, actor_name="seed")
        await s.commit()

    r = await client.post("/api/suites", headers=h,
                          json={"name": "裸基线编排", "description": ""})
    sid = r.json()["suiteId"]
    body = {"rev": 0, "mode": "compose",
            "members": [{"scenarioId": "sc-va"}, {"scenarioId": "sc-vb"}],
            "modeConfig": {"units": {
                "sc-va": {"ref": "a"},
                "sc-vb": {"ref": "b", "needs": ["sc-va"]}}}}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                         json=body)
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, body["items"]      # 裸基线可跑,不禁
    warn = [it for it in body["items"] if it.get("code") == "no_scheme"
            or "裸基线" in it.get("message", "")]
    assert warn, body["items"]


# ── P2-7:保存 × 修复并发(锁序统一后无 500)────────────────────────

async def test_save_and_repair_concurrent_no_500(client: AsyncClient):
    """普通 PUT(combo→scheme)与 rebind(同序后)并发同一方案+组合:
    无死锁 500;结果集落在 {200, 409} 内(CAS/闸语义各归各)。"""
    from app.core import db as db_module
    from tests.conftest import seed_identity_fixture
    from tests.helpers import default_space_id

    h = await register_and_login(client, "r4lk_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)
           ).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias="r4lk-qa", username="u", password="p",
            service="fin-service", owner_id=uid)
        space = await default_space_id(s, uid)
        await s.commit()
    combo_id = (await client.post(
        f"/api/projects/{space}/account-combos", headers=h,
        json={"name": "并发组合", "entries": [
            {"service": "fin-service", "alias": "r4lk-qa"}]})
    ).json()["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-r4lk"))
    r = await client.post("/api/scenarios/sc-r4lk/run-schemes", headers=h,
                          json={"name": "待修", "isDefault": False,
                                "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    scheme_id = r.json()["schemeId"]
    async with db_module.SessionLocal() as s:
        from app.models.composer_run_scheme import ComposerRunScheme
        from app.services import scheme_repair
        from sqlalchemy import select

        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid, actor_name="seed")
        await s.commit()

    put_body = {"name": "待修", "isDefault": False,
                "accountComboId": combo_id,
                "dataSetSelection": [], "injectionEntryIds": [],
                "serviceBindings": {}, "options": {
                    "step_from": None, "step_to": None, "n_runs": 1,
                    "parallel": 1, "subscribe": None}}
    r1, r2 = await asyncio.gather(
        client.put(f"/api/scenarios/sc-r4lk/run-schemes/{scheme_id}",
                   headers=h, json=put_body),
        client.post(f"/api/scenarios/sc-r4lk/run-schemes/{scheme_id}"
                    f"/rebind-combo", headers=h,
                    json={"comboId": combo_id, "expectedRevision": 2}))
    for r in (r1, r2):
        assert r.status_code != 500, f"并发出现 500(锁环): {r.text}"
    assert {r1.status_code, r2.status_code} <= {200, 409}


# ── P2-8:成员管理在途并发(真交错,无死锁 500)─────────────────────

def _barrier_lock(monkeypatch):
    """评审五轮 P2-6:锁交错 barrier —— 包装 ``_require_manage_locked``:
    第 1 个调用者锁到手后挂起(事务不提交 → 行/项目锁不释放);第 2+
    个调用者**入场即上报**(随即真阻塞在锁上)。主测据此编排确定性
    交错:「一方持锁、另一方等待」,不再依赖裸 gather 的巧合时序。"""
    from app.routers import projects as projects_mod

    calls = {"n": 0}
    a_locked = asyncio.Event()
    b_entered = asyncio.Event()
    release = asyncio.Event()
    real_lock = projects_mod._require_manage_locked

    async def barrier(db, user, project, *, target_user_id=None):
        calls["n"] += 1
        n = calls["n"]
        if n > 1:
            b_entered.set()          # 后到者已入场,即将阻塞在锁上
        await real_lock(db, user, project, target_user_id=target_user_id)
        if n == 1:
            a_locked.set()           # 先到者持锁、事务未提交
            await asyncio.wait_for(release.wait(), 10)

    monkeypatch.setattr(projects_mod, "_require_manage_locked", barrier)
    return a_locked, b_entered, release


async def _interleaved(coro1, coro2, monkeypatch):
    """并发驱动:先到者持锁 → 后到者入场并阻塞 → 放行 → 双双收场。
    保证命中「一方持锁、另一方等待」的真实锁交错窗口。"""
    a_locked, b_entered, release = _barrier_lock(monkeypatch)
    t1 = asyncio.ensure_future(_status(coro1))
    await asyncio.wait_for(a_locked.wait(), 10)
    t2 = asyncio.ensure_future(_status(coro2))
    await asyncio.wait_for(b_entered.wait(), 10)
    await asyncio.sleep(0.2)          # 让后到者真正阻塞进锁队列
    release.set()
    return await asyncio.gather(t1, t2)


async def test_member_management_inflight_concurrent_no_500(
        client: AsyncClient, monkeypatch):
    """两名成员管理员互改 —— barrier 强制「A 持锁未提交 × B 阻塞抢锁」
    真交错(修前裸 gather 命不中锁窗口,测试证伪力不足)。固定全序锁 +
    项目行锁(评审五轮 P2-5)下结果确定:B 在锁内重验被拒(403/404),
    无 500 无死锁。"""
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r4dl_adm", role="admin")
    h_a = await role_headers(client, "r4dl_a", role="user")
    h_b = await role_headers(client, "r4dl_b", role="user")
    a_uid = await _uid_of(client, "r4dl_a")
    b_uid = await _uid_of(client, "r4dl_b")
    pid = (await _create_project(
        client, h_admin, "r4dl-proj", a_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_a, json={"userId": b_uid,
                                             "role": "admin"})
    assert r.status_code == 201, r.text

    # A→B 降级 先持锁;B→A 降级 阻塞抢锁,锁内重验自身已被降级 → 403
    s1, s2 = await _interleaved(
        client.patch(f"/api/projects/{pid}/members/{b_uid}",
                     headers=h_a, json={"role": "member"}),
        client.patch(f"/api/projects/{pid}/members/{a_uid}",
                     headers=h_b, json={"role": "member"}),
        monkeypatch)
    assert (s1, s2) == (200, 403), f"并发降级出现意外结果: {s1} / {s2}"

    # 交叉 remove × patch:A 先删 B(204);B 锁内重验成员行已消失 → 404
    async with db_module.SessionLocal() as s:
        await s.execute(sa_text(
            "UPDATE project_members SET role='admin' "
            "WHERE project_id=:pid AND user_id IN (:a, :b)"),
            {"pid": pid, "a": a_uid, "b": b_uid})
        await s.commit()
    s1, s2 = await _interleaved(
        client.delete(f"/api/projects/{pid}/members/{b_uid}",
                      headers=h_a),
        client.patch(f"/api/projects/{pid}/members/{a_uid}",
                     headers=h_b, json={"role": "member"}),
        monkeypatch)
    assert (s1, s2) == (204, 404), f"交叉并发出现意外结果: {s1} / {s2}"





async def _status(coro):
    """并发探针:未处理异常(ASGI 直抛的 IntegrityError 等)归一为
    异常类名,便于死锁断言。"""
    try:
        return (await coro).status_code
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


async def _uid_of(client: AsyncClient, username: str) -> int:
    from sqlalchemy import select

    from app.models.user import User

    async with db_module.SessionLocal() as s:
        return (await s.execute(select(User.id).where(
            User.username == username))).scalar_one()
