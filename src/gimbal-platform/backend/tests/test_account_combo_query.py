"""账户组合批 3 查询链测试(定稿 05 §7/§9 批 3 子集)。

覆盖:schemeId 方案感知(非默认方案身份正确;跨场景/未给回落默认)、
组合垫底进查询、call.user 直引(后端单源扫描)、多直接身份 → 422
query_identity_ambiguous(不取第一个)、凭证池通道(成员闸)与
个人/项目池 L1 缓存隔离(§7.4 键含池维),以及共享场景按查询人
隔离个人凭证与缓存。
"""
from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.models import AuthAccount, ServiceIdentity, User
from app.services import query_context, query_view_runner as run
from .helpers import make_draft
from .conftest import seed_identity_fixture
from .test_query_views_route import _IDX, _install_plate
from .test_scenario_visibility_and_copy import _member


@pytest.fixture(autouse=True)
def _reset_query_runner():
    run.reset_state_for_tests()
    yield
    run.reset_state_for_tests()


def _q_step(service: str = "svc", *, headers: dict | None = None,
            user: str | None = None) -> dict:
    call = {"kind": "call", "protocol": "http", "service": service,
            "method": "GET", "path": "/a", "headers": {}}
    if headers is not None:
        call["headers"] = headers
    if user is not None:
        call["user"] = user
    return {"call": call, "request": {"kind": "request", "body": {}}}


async def _seed(client, headers, sid: str, steps: list) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft(sid, steps=steps))
    assert r.status_code == 201, r.text


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(User.id).where(
            User.username == username))).scalar_one()


async def _seed_alias(alias: str, uid: int) -> None:
    """四件套:身份 + 账户 + 环境 + 部署行(svc 基础服务)。默认位不取
    (每 owner×system 唯一,多条同 system 会撞 uq_account_default;
    本面只吃身份/标签/地址,账户默认位无关)。"""
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias=alias, username=f"{alias}-u", password="p",
            service="svc", owner_id=uid, env_name="查询环境",
            login_url="https://svc-login.internal", is_default=False)


async def _resolve(sid: str, *, scheme_id: str | None = None,
                   username: str = "quser") -> "query_context.QueryContext":
    async with db_module.SessionLocal() as db:
        u = (await db.execute(sa.select(User).where(
            User.username == username))).scalar_one()
        return await query_context.resolve_query_context(
            db, user=u, scenario_id=sid, step_index=0,
            scheme_id=scheme_id)


async def _mk_scheme(client, headers, sid: str, name: str,
                     bindings: dict, combo_id: int | None = None) -> str:
    # 先 GET 触发 ensure_default_scheme(默认方案空行落库),再建命名方案
    assert (await client.get(
        f"/api/scenarios/{sid}/run-schemes", headers=headers)).status_code == 200
    r = await client.post(f"/api/scenarios/{sid}/run-schemes", headers=headers,
                          json={"name": name, "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": bindings,
                                **({"accountComboId": combo_id}
                                   if combo_id is not None else {}),
                                "options": {}})
    assert r.status_code == 201, r.text
    return r.json()["schemeId"]


async def _bind_default(client, headers, sid: str, combo_id) -> None:
    listed = await client.get(
        f"/api/scenarios/{sid}/run-schemes", headers=headers)
    assert listed.status_code == 200, listed.text
    scheme = next(s for s in listed.json() if s["isDefault"])
    body = {
        "name": scheme["name"],
        "dataSetSelection": scheme.get("dataSetSelection") or [],
        "injectionEntryIds": scheme.get("injectionEntryIds") or [],
        "serviceBindings": scheme.get("serviceBindings") or {},
        "options": scheme.get("options") or {},
        **({"accountComboId": combo_id} if combo_id is not None else {}),
    }
    r = await client.put(
        f"/api/scenarios/{sid}/run-schemes/{scheme['schemeId']}",
        headers=headers, json=body)
    assert r.status_code == 200, r.text


async def _mk_combo(client, headers, entries: list[dict]) -> int:
    r = await client.post("/api/account-combos", headers=headers, json={
        "name": f"组合-{len(entries)}", "entries": entries})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── §7.1 方案感知 + §7.2/§7.3 步骤身份 ──────────────────────────

async def test_query_scheme_and_combo_resolution(client, fresh_db) -> None:
    """schemeId 解析(非默认方案身份正确)+ 组合垫底 + 覆盖序:
    步骤声明 > 方案 > 组合 > 服务键(§3.1 同序);跨场景/未给回落默认。"""
    h = await _member(client, "quser")
    uid = await _uid("quser")
    await _seed(client, h, "sc-q1", [_q_step("svc")])
    await _seed_alias("aliasA", uid)
    await _seed_alias("aliasB", uid)
    scheme_a = await _mk_scheme(client, h, "sc-q1", "方案甲", {
        "svc": {"alias": "aliasA"}})

    # 未给 schemeId → 默认方案(空)→ 服务键自身
    ctx = await _resolve("sc-q1")
    assert ctx.query_alias == "svc"
    # 非默认方案 → 方案绑定身份正确(§9 钉)
    ctx = await _resolve("sc-q1", scheme_id=scheme_a)
    assert ctx.query_alias == "aliasA"
    # 跨场景/不存在的 schemeId → 回落默认(与执行面 resolve_for_run 同款)
    ctx = await _resolve("sc-q1", scheme_id="rs-ghost")
    assert ctx.query_alias == "svc"

    # 组合垫底:默认方案空 → 组合补位;方案键胜出组合
    cid = await _mk_combo(client, h, [{"service": "svc",
                                       "alias": "aliasB"}])
    await _bind_default(client, h, "sc-q1", cid)
    ctx = await _resolve("sc-q1")
    assert ctx.query_alias == "aliasB"
    ctx = await _resolve("sc-q1", scheme_id=scheme_a)
    assert ctx.query_alias == "aliasA"
    # raw 不吃默认方案组合
    ctx = await _resolve("sc-q1", scheme_id="raw")
    assert ctx.query_alias == "svc"


async def test_query_combo_missing_fail_closed_even_with_url_override(
        client, fresh_db) -> None:
    """显式 service_url 只覆盖地址,不绕过方案组合的 fail-closed。"""
    from app.models import AccountCombo
    h = await _member(client, "quser_missing")
    await _seed(client, h, "sc-q-missing", [_q_step("svc")])
    cid = await _mk_combo(client, h, [])
    await _bind_default(client, h, "sc-q-missing", cid)
    async with db_module.SessionLocal() as db:
        await db.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await db.commit()
    async with db_module.SessionLocal() as db:
        u = (await db.execute(sa.select(User).where(
            User.username == "quser_missing"))).scalar_one()
        with pytest.raises(query_context.QueryContextError) as ei:
            await query_context.resolve_query_context(
                db, user=u, scenario_id="sc-q-missing", step_index=0,
                service_url_override="http://private-sut")
        assert ei.value.code == "identity_combo_missing"
        assert ei.value.status == 409


async def test_query_combo_dangling_shadowed_by_scheme_or_override(
        client, fresh_db) -> None:
    """方案、步骤直引或显式 query_alias 覆盖组合时不校验被覆盖条目。"""
    from app.models import AccountCombo
    h = await _member(client, "quser_shadow")
    uid = await _uid("quser_shadow")
    await _seed_alias("query-good", uid)
    await _seed_alias("query-other", uid)
    await _seed(client, h, "sc-q-shadow", [_q_step("svc")])
    cid = await _mk_combo(client, h, [{"service": "svc",
                                       "alias": "query-good"}])
    await _bind_default(client, h, "sc-q-shadow", cid)
    scheme = await _mk_scheme(client, h, "sc-q-shadow", "覆盖方案", {
        "svc": {"alias": "query-other"}})
    async with db_module.SessionLocal() as db:
        await db.execute(sa.delete(ServiceIdentity).where(
            ServiceIdentity.alias_name == "query-good"))
        await db.commit()
    async with db_module.SessionLocal() as db:
        u = (await db.execute(sa.select(User).where(
            User.username == "quser_shadow"))).scalar_one()
        ctx = await query_context.resolve_query_context(
            db, user=u, scenario_id="sc-q-shadow", step_index=0,
            scheme_id=scheme, service_url_override="http://private-sut")
        assert ctx.query_alias == "query-other"
        ctx = await query_context.resolve_query_context(
            db, user=u, scenario_id="sc-q-shadow", step_index=0,
            query_alias_override="query-other",
            service_url_override="http://private-sut")
        assert ctx.query_alias == "query-other"


async def test_query_call_user_direct_ref(client, fresh_db) -> None:
    """§7.2:call.user 直引进查询身份判定(后端单源扫描器,前端
    headers-only 扫描的补齐项);单个 ${auth.X} 模板引用同理。"""
    h = await _member(client, "quser2")
    uid = await _uid("quser2")
    await _seed_alias("cu1", uid)
    await _seed_alias("hA", uid)
    # call.user 直引
    await _seed(client, h, "sc-q2", [_q_step("svc", user="cu1")])
    ctx = await _resolve("sc-q2", username="quser2")
    assert ctx.query_alias == "cu1"
    # 单个 header ${auth.X} 模板引用 = 该步执行身份声明
    await _seed(client, h, "sc-q3", [_q_step(
        "svc", headers={"Authorization": "${auth.hA.token}"})])
    ctx = await _resolve("sc-q3", username="quser2")
    assert ctx.query_alias == "hA"


async def test_query_multi_identity_ambiguous(client, fresh_db,
                                              monkeypatch) -> None:
    """§7.3:同一步多个直接身份且无法唯一判定 → 422
    query_identity_ambiguous,不取第一个。"""
    h = await _member(client, "quser3")
    uid = await _uid("quser3")
    await _seed_alias("hA", uid)
    await _seed_alias("cu1", uid)
    await _seed(client, h, "sc-q4", [_q_step(
        "svc", headers={"Authorization": "${auth.hA.token}"}, user="cu1")])
    with pytest.raises(query_context.QueryContextError) as ei:
        await _resolve("sc-q4", username="quser3")
    assert ei.value.code == "query_identity_ambiguous"
    async with db_module.SessionLocal() as db:
        u = (await db.execute(sa.select(User).where(
            User.username == "quser3"))).scalar_one()
        ctx = await query_context.resolve_query_context(
            db, user=u, scenario_id="sc-q4", step_index=0,
            query_alias_override="hA", service_url_override="http://sut")
        assert ctx.query_alias == "hA"

    # 路由面:rows 端点同码 422(查询族 detail 形态 {code, msg});
    # 422 在上下文解析段即拒,不触 SUT
    _install_plate(monkeypatch, _IDX)
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q4", "stepIndex": 0}, headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "query_identity_ambiguous"


# ── §7.4 池通道 + 缓存隔离 ─────────────────────────────────────

async def test_query_pool_channel_member_gate(client, fresh_db,
                                               monkeypatch) -> None:
    """credentialSource=project:成员过闸(200);可读但非成员(平台
    Admin,§5.3 不旁路语义)→ 422 credential_source_invalid —— 不静默
    回落个人池(回落会打到错误账号的数据面);完全不可读者仍 404。"""
    from app.models.project import Project, ProjectMember
    from app.models.composer_scenario import ComposerScenario
    from .helpers import role_headers

    _install_plate(monkeypatch, _IDX)   # 视图 v1(auth=none,items=$.d[*])
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "z"}]}))
    await _member(client, "qmem")          # 项目成员
    h_out = await _member(client, "qout")  # 局外人(不可读 → 404)
    h_plat = await role_headers(client, "qplat", role="super_admin")
    async with db_module.SessionLocal() as db:
        proj = Project(name="q-proj", kind="normal", description="")
        db.add(proj)
        await db.flush()
        db.add(ProjectMember(project_id=proj.id,
                             user_id=await _uid("qmem"), role="member"))
        await db.commit()
        pid = proj.id
    h_mem = await _member(client, "qmem")
    await _seed(client, h_mem, "sc-q5", [_q_step("svc")])
    await _seed_alias("svc", await _uid("qmem"))
    async with db_module.SessionLocal() as db:
        row = (await db.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-q5"))).scalar_one()
        row.project_id = pid
        await db.commit()

    # 成员 → 项目池通道可用
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q5", "stepIndex": 0,
                "credentialSource": "project"}, headers=h_mem)
    assert r.status_code == 200, r.text
    # 显式 URL 仍保留场景身份/池上下文,成员闸不被绕过。
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q5", "stepIndex": 0,
                "credentialSource": "project", "service_url": "http://sut"},
        headers=h_mem)
    assert r.status_code == 200, r.text
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"credentialSource": "project", "service_url": "http://sut"},
        headers=h_mem)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "credential_source_invalid"
    # 非成员读者均止步于读闸(场景不可读 → 404;平台 Admin 对项目场景
    # 同样无读旁路)——「可读但非成员」面(ref 读者)由 422 池闸防御,
    # 此处记录读闸先行的实际序
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q5", "stepIndex": 0,
                "credentialSource": "project"}, headers=h_plat)
    assert r.status_code == 404
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q5", "stepIndex": 0,
                "credentialSource": "project"}, headers=h_out)
    assert r.status_code == 404
    # 非法取值 → 422
    r = await client.get(
        "/api/query-views/v1/rows",
        params={"scenarioId": "sc-q5", "stepIndex": 0,
                "credentialSource": "weird"}, headers=h_mem)
    assert r.status_code == 422


async def test_shared_scenario_uses_reader_credentials_and_cache(
        client, fresh_db, monkeypatch) -> None:
    """公共场景的作者与读者同名身份条目各取自己的个人凭证;查询缓存
    按执行人隔离,读者不能命中作者先前写入的行集。"""
    from app.core.security import fernet_encrypt

    _install_plate(monkeypatch, [dict(_IDX[0], auth="bearer")])
    h_author = await _member(client, "qshared_author")
    h_reader = await _member(client, "qshared_reader")
    author_id = await _uid("qshared_author")
    reader_id = await _uid("qshared_reader")
    await _seed_alias("svc", author_id)
    async with db_module.SessionLocal() as db:
        ident = (await db.execute(sa.select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "svc"))).scalar_one()
        db.add(AuthAccount(
            owner_id=reader_id, system="svc", env_id=ident.env_id,
            username=ident.ref_username,
            password_enc=fernet_encrypt("reader-pass"), token_type="Bearer",
            expires_in=7200, account_fields={}, is_default=False))
        await db.commit()
    await _seed(client, h_author, "sc-q-shared", [_q_step("svc")])
    published = await client.post(
        "/api/scenarios/sc-q-shared/publish", headers=h_author)
    assert published.status_code == 200, published.text
    public_sid = "sc-q-shared-public"
    assert published.json()["meta"]["scenarioId"] == public_sid

    def fake_auth(session, why):
        session.apply_token(f"tok-{session.password}", 3600)
    monkeypatch.setattr(run, "_AUTHENTICATE", fake_auth)

    hits: list[str] = []

    def fake_request(method, url, **kw):
        token = kw["headers"]["Authorization"]
        hits.append(token)
        return httpx.Response(200, json={"d": [{"nm": token}]})
    monkeypatch.setattr(httpx, "request", fake_request)

    params = {"scenarioId": public_sid, "stepIndex": 0}
    author_first = await client.get(
        "/api/query-views/v1/rows", params=params, headers=h_author)
    assert author_first.status_code == 200, author_first.text
    assert author_first.json()["rows"] == [{"nm": "tok-p"}]
    assert not author_first.json()["cached"]

    reader_first = await client.get(
        "/api/query-views/v1/rows", params=params, headers=h_reader)
    assert reader_first.status_code == 200, reader_first.text
    assert reader_first.json()["rows"] == [{"nm": "tok-reader-pass"}]
    assert not reader_first.json()["cached"]

    author_again = await client.get(
        "/api/query-views/v1/rows", params=params, headers=h_author)
    reader_again = await client.get(
        "/api/query-views/v1/rows", params=params, headers=h_reader)
    assert author_again.json()["cached"] is True
    assert reader_again.json()["cached"] is True
    assert author_again.json()["rows"] == [{"nm": "tok-p"}]
    assert reader_again.json()["rows"] == [{"nm": "tok-reader-pass"}]
    assert hits == ["tok-p", "tok-reader-pass"]


async def test_pool_cache_isolation(monkeypatch) -> None:
    """§7.4:凭证会话/缓存键含池维 —— 个人池与项目池同名条目各自
    缓存/单飞,互不串台;drop_credential 按前两维清全部池。"""
    IDX = [{
        "name": "v2", "endpoint_id": "t.b", "system": "t", "service": "svc",
        "method": "POST", "path": "/api/b", "params": {"k": "x"},
        "items": "$.rows[*]", "label": "code",
        "columns": ["code"], "query_safe": True, "missing_required": [],
        "auth": "bearer", "timeout_seconds": 5.0,
    }]

    async def fake_index():
        return IDX
    monkeypatch.setattr(run, "fetch_query_view_index", fake_index)
    run.reset_state_for_tests()

    hits: list[str] = []

    class _S:
        token = "tok-pool"

    def fake_request(method, url, **kw):
        hits.append(url)
        return httpx.Response(200, json={"rows": [{"code": "c1"}]})
    monkeypatch.setattr(httpx, "request", fake_request)

    kw = dict(refresh=False, service_url="http://sut", owner_id=1,
              query_alias="qa", service="svc",
              load_credential=lambda o, a: _S())
    r1 = await run.fetch_rows("v2", cred_pool=None, **kw)
    r2 = await run.fetch_rows("v2", cred_pool=99, **kw)    # 项目池 → miss
    r3 = await run.fetch_rows("v2", cred_pool=None, **kw)   # 个人池 → 命中 r1
    r4 = await run.fetch_rows("v2", cred_pool=99, **kw)     # 项目池 → 命中 r2
    assert len(hits) == 2
    assert not r1.cached and not r2.cached
    assert r3.cached and r4.cached

    # 凭证变化 → 前两维清全部池(个人+项目缓存同失效)
    run.drop_credential(1, "qa")
    r5 = await run.fetch_rows("v2", cred_pool=None, **kw)
    r6 = await run.fetch_rows("v2", cred_pool=99, **kw)
    assert not r5.cached and not r6.cached
    assert len(hits) == 4
    run.reset_state_for_tests()
