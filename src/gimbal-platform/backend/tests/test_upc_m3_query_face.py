"""组合 v4 §7.1 查询链(随 UPC M3 执行装配接入)回归:

* 方案感知:绑定基础 = schemeId 解析 + 组合垫底(查询视角 = 执行视角),
  缺省/跨场景回落默认方案;未保存编辑态不参与(只认库中方案行);
* §20.3 装配闸:blocked 方案先于身份/标签/地址解析 409;
* 多身份不猜测:步骤多直接身份 → 422 query_identity_ambiguous
  (step_auth_refs 复用,含 call.user 直引);
* 池通道与缓存隔离:credentialSource=project 走项目池(成员资格判定),
  L1/单飞/会话键带池维度,个人池/项目池不串缓存。"""
import pytest

from app.core import db as db_module
from app.services import query_view_runner as run
from tests.conftest import seed_identity_fixture
from tests.helpers import default_space_id, register_and_login

from tests.test_query_views_route import (  # noqa: F401  布景单源
    _IDX, _call_step, _install_plate, _save_scenario,
)


@pytest.fixture(autouse=True)
def _reset_runner():
    run.reset_state_for_tests()
    yield
    run.reset_state_for_tests()


ALIAS = "q71-qa"


async def _seed_scenario_with_scheme(client, h, uid, tag: str):
    """布景:身份四件套 + 组合 + 场景(svc 步骤)+ 绑组合的方案
    (payload serviceBindings 空 —— 组合是身份唯一来源)。"""
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias=ALIAS, username="u", password="p",
            service="svc", owner_id=uid,
            env_name="查询环境", login_url=None,
            base_url="https://svc-deploy.internal")
        space = await default_space_id(s, uid)
        await s.commit()
    combo_id = (await client.post(
        f"/api/projects/{space}/account-combos", headers=h,
        json={"name": f"查询组合-{tag}", "entries": [
            {"service": "svc", "alias": ALIAS}]}
    )).json()["id"]
    sid = f"sc-q71{tag}"
    await _save_scenario(client, h, sid, [_call_step("svc")])
    qa_id = (await client.post(f"/api/scenarios/{sid}/run-schemes",
                               headers=h,
                               json={"name": "查询方案", "isDefault": False,
                                     "accountComboId": combo_id,
                                     "dataSetSelection": [],
                                     "injectionEntryIds": [],
                                     "serviceBindings": {}, "options": {
                                         "step_from": None, "step_to": None,
                                         "n_runs": 1, "parallel": 1,
                                         "subscribe": None}})
             ).json()["schemeId"]
    return combo_id, sid, qa_id


async def _uid(client, h) -> int:
    return (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]


# ── 方案感知 + 组合垫底(查询视角 = 执行视角)────────────────────────

async def test_query_context_scheme_aware_combo_pad(client, monkeypatch):
    """缺省回落默认方案 → 默认方案无组合无绑定 → effective_alias(svc)
    兜底别名 = svc(服务键自身);显式 schemeId 指向绑组合方案 →
    query_alias = 组合条目别名(组合垫底)。"""
    from app.services import query_context as qc

    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client, "q71a_own")
    uid = await _uid(client, h)
    _combo, sid, qa_id = await _seed_scenario_with_scheme(
        client, h, uid, "a")

    async with db_module.SessionLocal() as s:
        user = type("U", (), {"id": uid})()
        # 缺省(回落默认方案;默认方案无组合)→ 别名兜底 svc
        ctx = await qc.resolve_query_context(
            s, user=user, scenario_id=sid, step_index=0)
        assert ctx.query_alias == "svc"
        # 显式 schemeId(绑组合方案,payload 绑定空)→ 组合垫底别名
        ctx2 = await qc.resolve_query_context(
            s, user=user, scenario_id=sid, step_index=0, scheme_id=qa_id)
        assert ctx2.query_alias == ALIAS
        assert ctx2.project_id is not None
        await s.rollback()


async def test_query_context_blocked_scheme_rejected(client, monkeypatch):
    """§20.3:默认方案 blocked → 409 scheme_repair_required(先于身份/
    标签/地址解析);显式 ready 方案照常放行。"""
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import query_context as qc
    from app.services import scheme_repair
    from sqlalchemy import select

    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client, "q71b_own")
    uid = await _uid(client, h)
    _combo, sid, qa_id = await _seed_scenario_with_scheme(
        client, h, uid, "b")
    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid,
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid, actor_name="seed")
        await s.commit()

    # 缺省回落默认方案 = blocked → 409(路由面同码)
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": sid, "stepIndex": 0},
                         headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    # 显式 ready 方案(绑组合)→ 组合垫底别名照常解析
    async with db_module.SessionLocal() as s:
        user = type("U", (), {"id": uid})()
        ctx = await qc.resolve_query_context(
            s, user=user, scenario_id=sid, step_index=0, scheme_id=qa_id)
        assert ctx.query_alias == ALIAS
        await s.rollback()


# ── 多身份不猜测(§7.1 点 3)+ call.user 直引(点 2)───────────────

async def test_query_context_multi_direct_identities_ambiguous(
        client, monkeypatch):
    """步骤两个直接身份(${auth.X} headers + call.user 异名)→ 422
    query_identity_ambiguous,不取第一个(前端 headers 首命中同款猜测
    在后端被挡)。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client, "q71c_own")
    await _save_scenario(client, h, "sc-q71c", [{
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/a", "user": ALIAS,
                 "headers": {"X-Tok": "${auth.other-alias.token}"}},
        "request": {"kind": "request", "body": {}},
    }])
    r = await client.get("/api/query-views/v1/rows",
                         params={"scenarioId": "sc-q71c", "stepIndex": 0},
                         headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "query_identity_ambiguous"


async def test_query_context_call_user_direct_ref(client, monkeypatch):
    """§7.1 点 2:call.user 直引是步骤执行身份声明 —— 单一直接身份
    优先于绑定兜底(query_alias = call.user,不落 effective_alias)。"""
    from app.services import query_context as qc

    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client, "q71d_own")
    uid = await _uid(client, h)
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias=ALIAS, username="u", password="p",
            service="svc", owner_id=uid,
            env_name="查询环境", login_url=None,
            base_url="https://svc-deploy.internal")
        await s.commit()
    await _save_scenario(client, h, "sc-q71d", [{
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/a", "user": ALIAS,
                 "headers": {}},
        "request": {"kind": "request", "body": {}},
    }])
    async with db_module.SessionLocal() as s:
        user = type("U", (), {"id": uid})()
        ctx = await qc.resolve_query_context(
            s, user=user, scenario_id="sc-q71d", step_index=0)
        assert ctx.query_alias == ALIAS      # call.user 直引(非 svc 兜底)
        await s.rollback()


# ── 池通道与缓存隔离(§7.1 点 4)────────────────────────────────────

async def test_rows_credential_source_project_channel(client, monkeypatch):
    """credentialSource=project:私有空间场景(无项目语境)→ 409
    credential_source_invalid;显式 service_url 直连通道同样 409。"""
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client, "q71e_own")
    uid = await _uid(client, h)
    _combo, sid, _qa = await _seed_scenario_with_scheme(
        client, h, uid, "e")
    # 场景在私有空间 —— 无项目语境:project 须 409(不可用项目池)
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": sid, "stepIndex": 0,
                "credentialSource": "project"},
        headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "credential_source_invalid"
    # 显式覆盖通道 + project → 409(无场景语境)
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"service_url": "http://sut", "credentialSource": "project"},
        headers=h)
    assert r.status_code == 409, r.text


async def test_pool_dimension_isolates_sessions_and_cache():
    """键维度单元钉:cred_key/L1 cred_id 带 (owner, alias, pool) 三分量
    —— 个人池与项目池同 (owner, alias) 会话不串;drop_credential 按
    前两分量清全池变体。"""
    # 直接操纵 runner 内存态(_cred_sessions/_cred_dead/L1)
    personal_key = (7, ALIAS, None)
    project_key = (7, ALIAS, 3)
    run._cred_sessions[personal_key] = object()
    run._cred_sessions[project_key] = object()
    run._cred_dead.add(project_key)
    run._cache.put(("v1", None, project_key), (["r"], False), "2026-01-01")
    run._cache.put(("v1", None, personal_key), (["r2"], False), "2026-01-01")

    run.drop_credential(7, ALIAS)
    assert personal_key not in run._cred_sessions
    assert project_key not in run._cred_sessions
    assert project_key not in run._cred_dead
    # L1 行集同步清空(两池变体都不留)
    for ck in ("v1", None, project_key), ("v1", None, personal_key):
        _e, fresh = run._cache.lookup(ck)
        assert not fresh, f"池变体缓存未清: {ck}"
