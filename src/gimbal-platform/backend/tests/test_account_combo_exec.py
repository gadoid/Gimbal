"""账户组合批 2 执行面测试(定稿 05 §9 批 2 子集)。

覆盖:JWT 派发垫底 + 快照合并终值/溯源键、令牌面装载时合并(覆写不
冲掉垫底,评审 2 真 bug 的回归钉)、预览面合并序 + fail-closed、预检
报告 comboMissing、硬门分码(identity_combo_missing vs 既有
account_missing/identity_missing 精度)、未引用服务悬空不阻断、
集成面规范化 scheme_payload + 指纹含组合修订、Suite 图垫底、
复活钩子触发。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import ServiceIdentity
from .test_run_bindings_injection import (
    _env_id, _seed_deployment, _seed_pool_auth, _seed_scenario,
)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401 — fixture 供本文件用例解析
from .test_scenario_visibility_and_copy import _member


async def _mk_combo(client, headers, name: str, entries: list[dict],
                    *, scope: str = "user", project_id=None) -> int:
    r = await client.post("/api/account-combos", headers=headers, json={
        "name": name, "entries": entries,
        **({"scope": scope, "projectId": project_id}
           if scope == "project" else {})})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _bind(client, headers, sid: str, combo_id,
                scheme_id: str | None = None) -> dict:
    listed = await client.get(
        f"/api/scenarios/{sid}/run-schemes", headers=headers)
    assert listed.status_code == 200, listed.text
    schemes = listed.json()
    scheme = next((s for s in schemes if s["schemeId"] == scheme_id), None)
    if scheme is None:
        scheme = next((s for s in schemes if s["isDefault"]), schemes[0])
    body = {
        "name": scheme["name"],
        "dataSetIds": scheme.get("dataSetIds") or [],
        "dataSetSelection": scheme.get("dataSetSelection") or [],
        "injectionEntryIds": scheme.get("injectionEntryIds") or [],
        "serviceBindings": scheme.get("serviceBindings") or {},
        "options": scheme.get("options") or {},
        **({"accountComboId": combo_id} if combo_id is not None else {}),
    }
    r = await client.put(
        f"/api/scenarios/{sid}/run-schemes/{scheme['schemeId']}",
        json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _delete_identity(alias: str) -> None:
    """直删条目行(保存面校验不许悬空,竞态模拟走库面)。"""
    async with db_module.SessionLocal() as s:
        await s.execute(sa.delete(ServiceIdentity).where(
            ServiceIdentity.alias_name == alias))
        await s.commit()


async def _last_config_json() -> dict:
    from app.models import Execution
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        return ex.config_json


async def _last_execution_id() -> int:
    from app.models import Execution
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(Execution.id).order_by(
            Execution.id.desc()))).scalars().first()


async def _seed_combo_identity(alias: str, base: str) -> None:
    """直插条目(无账户行,ref_mode=username 防跟随系统默认账户):
    分码用例的「条目在、池无账户」半边。"""
    async with db_module.SessionLocal() as s:
        env = await _env_id()
        s.add(ServiceIdentity(alias_name=alias, base_service=base,
                              env_id=env, ref_mode="username",
                              ref_username=f"{alias}-user"))
        await s.commit()


# ── JWT 派发面:垫底 + 快照终值/溯源 + fail-closed 分码 ───────────

async def test_jwt_run_combo_pad_and_snapshot(client, plate_mock: PlateMock,
                                              monkeypatch):
    """JWT 运行:请求不带绑定 → 组合垫底进生效绑定;config_json 记
    合并终值 + accountComboId/Name/Revision 溯源键(§6.4)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    await _seed_pool_auth("bob", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "组合A", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    # 合并终值 = 组合条目(请求空)
    assert config_json["serviceBindings"] == {
        "fin-service": {"alias": "fin-service-maker"}}
    # 溯源三件套(§6.4)
    assert config_json["accountComboId"] == cid
    assert config_json["accountComboName"] == "组合A"
    assert config_json["accountComboRevision"] == 1


async def test_jwt_run_face_overrides_combo(client, plate_mock: PlateMock,
                                            monkeypatch):
    """请求级显式绑定 > 组合(五层解析序:组合永远垫底,§3.1)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob2")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob2", "qa1")
    await _seed_pool_auth("bob2", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "组合B", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"alias": "qa1"}}))
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {
        "fin-service": {"alias": "qa1"}}


async def test_run_combo_dangling_alias_409(client, plate_mock: PlateMock):
    """引用服务的组合条目悬空(条目被注销)→ 409 identity_combo_missing
    (fail-closed,§6.3;携带 comboId/service/alias)。"""
    bob = await _member(client, "bob3")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob3", "qa1")
    await _seed_pool_auth("bob3", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "组合C", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)
    await _delete_identity("fin-service-maker")

    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "identity_combo_missing"
    assert detail["comboId"] == cid
    assert detail["service"] == "fin-service"
    assert detail["alias"] == "fin-service-maker"


async def test_token_combo_dangling_uses_combo_error_code(
        client, plate_mock: PlateMock):
    """令牌面在范围闸前归位组合悬空,不误报普通绑定/范围错误。"""
    from .inbound_fixtures import mk_token

    bob = await _member(client, "bob_token_combo")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_token_combo", "qa1")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "令牌悬空组合", [
        {"service": "fin-service", "alias": "qa1"}])
    scheme = await _bind(client, bob, "sc-test", cid)
    await _delete_identity("qa1")
    _, plain = await mk_token(user_id=await _uid_of("bob_token_combo"))
    r = await client.post(
        "/api/runs", headers={"Authorization": f"Bearer {plain}"},
        json={"scenarioId": "sc-test", "schemeId": scheme["schemeId"]})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "identity_combo_missing"
    assert detail["comboId"] == cid
    assert detail["service"] == "fin-service"
    assert detail["alias"] == "qa1"


async def test_combo_dangling_shadowed_by_face_or_scheme(
        client, plate_mock: PlateMock, monkeypatch):
    """合法面内覆盖不被悬空组合条目阻断;无覆盖的预检仍 fail-closed。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob_shadow")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_shadow", "qa1")
    await _seed_pool_auth("bob_shadow", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "覆盖组合", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    default_scheme = await _bind(client, bob, "sc-test", cid)
    await _delete_identity("fin-service-maker")

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings={"fin-service": {"alias": "qa1"}}))
    assert r.status_code == 201, r.text
    r = await client.post("/api/runs/preview", headers=bob, json={
        "scenarioId": "sc-test",
        "serviceBindings": {"fin-service": {"alias": "qa1"}}})
    assert r.status_code == 200, r.text

    r = await client.post("/api/run/precheck", headers=bob, json=[{
        "scenarioId": "sc-test", "schemeId": default_scheme["schemeId"]}])
    assert r.status_code == 200, r.text
    assert r.json()[0]["schemeValid"] is False
    assert r.json()[0]["comboMissing"]["alias"] == "fin-service-maker"

    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=bob,
                          json={"name": "覆盖方案", "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {
                                    "fin-service": {"alias": "qa1"}},
                                "options": {}})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]
    await _bind(client, bob, "sc-test", cid, scheme_id)
    r = await client.post("/api/run/precheck", headers=bob, json=[{
        "scenarioId": "sc-test", "schemeId": scheme_id}])
    assert r.status_code == 200, r.text
    assert r.json()[0]["comboMissing"] is None
    assert r.json()[0]["schemeValid"] is True


async def test_run_combo_row_missing_409(client, plate_mock: PlateMock):
    """组合行被并发删除(直删绕过 in-use 闸模拟竞态)→ 409 同码。"""
    from app.models import AccountCombo
    bob = await _member(client, "bob4")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob4", "qa1")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "组合D", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid)
    async with db_module.SessionLocal() as s:
        await s.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await s.commit()

    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "identity_combo_missing"


async def test_run_combo_unreferenced_dangling_passes(
        client, plate_mock: PlateMock, monkeypatch):
    """校验分层(§6.3):**未引用服务**的悬空条目不阻断执行。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob5")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob5", "qa1")
    await _seed_pool_auth("bob5", "fin-service-maker")
    await _seed_deployment()
    await _seed_combo_identity("logi-maker", "logi-service")
    cid = await _mk_combo(client, bob, "组合E", [
        {"service": "fin-service", "alias": "fin-service-maker"},
        {"service": "logi-service", "alias": "logi-maker"}])
    await _bind(client, bob, "sc-test", cid)
    # 未引用服务(logi)条目悬空
    await _delete_identity("logi-maker")

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    # 组合两条都进终值(垫底不挑引用面);悬空的只是不被执行/校验消费
    assert config_json["serviceBindings"]["logi-service"] == {
        "alias": "logi-maker"}


async def test_run_combo_account_missing_not_combo_code(
        client, plate_mock: PlateMock):
    """分码精度(§5.2):条目在、当前池无账户 → 409 account_missing
    (既有分类不动),不是 identity_combo_missing。"""
    bob = await _member(client, "bob6")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob6", "qa1")
    await _seed_deployment()
    # 条目在(直插,无账户行)
    await _seed_combo_identity("fin-bare", "fin-service")
    cid = await _mk_combo(client, bob, "组合F", [
        {"service": "fin-service", "alias": "fin-bare"}])
    await _bind(client, bob, "sc-test", cid)

    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "account_missing"
    assert "fin-bare" in detail.get("aliases", [])


async def test_raw_skips_bound_combo(client, plate_mock: PlateMock,
                                     monkeypatch):
    """raw 不取任何方案配方:默认方案组合即使悬空也不阻断运行/预检。"""
    from app.models import AccountCombo
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob_raw")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_raw", "qa1")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "raw-组合", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid)
    async with db_module.SessionLocal() as s:
        await s.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await s.commit()

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], schemeId="raw"))
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}
    assert "accountComboId" not in config_json

    r = await client.post("/api/run/precheck", headers=bob, json=[{
        "scenarioId": "sc-test", "schemeId": "raw"}])
    assert r.status_code == 200, r.text
    assert r.json()[0]["schemeFound"] is True
    assert r.json()[0]["comboMissing"] is None


async def test_rerun_replays_combo_terminal_binding(client, plate_mock: PlateMock):
    """重跑只吃首发快照:当前组合行删除后,重跑仍按原合并终值执行。"""
    from app.models import AccountCombo
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob_rerun")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_rerun", "qa1")
    await _seed_pool_auth("bob_rerun", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "rerun-组合", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    origin = await _last_execution_id()
    async with db_module.SessionLocal() as s:
        await s.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await s.commit()

    r = await client.post(f"/api/executions/{origin}/rerun", headers=bob)
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {
        "fin-service": {"alias": "fin-service-maker"}}
    assert config_json["accountComboId"] == cid
    assert config_json["accountComboRevision"] == 1


async def test_rerun_keeps_unbound_combo_snapshot(client, plate_mock: PlateMock):
    """首发未绑组合时,重跑不得回查首发后新绑定的当前组合。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob_rerun_unbound")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_rerun_unbound", "qa1")
    await _seed_pool_auth("bob_rerun_unbound", "fin-service-maker")
    await _seed_deployment()
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    origin = await _last_execution_id()
    assert (await _last_config_json())["serviceBindings"] == {}

    cid = await _mk_combo(client, bob, "后绑组合", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)

    r = await client.post(f"/api/executions/{origin}/rerun", headers=bob)
    assert r.status_code == 201, r.text
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}
    assert "accountComboId" not in config_json
    assert "accountComboName" not in config_json
    assert "accountComboRevision" not in config_json


# ── 令牌面:装载时合并(覆写不冲掉,评审 2 真 bug 回归钉)──────────

async def test_token_face_merge_survives_overwrite(client, fresh_db):
    """_apply_scheme_recipe 覆写源 = {**组合, **方案}(§3.2):方案键
    胜出;方案没有的服务由组合补上 —— 覆写前垫底会被冲掉的写法已被
    评审 2 否决,此处钉住装载时合并形态。"""
    from app.routers.runs import _apply_scheme_recipe
    from app.schemas.scenario_composer import RunRequest
    from app.services import scheme_store

    bob = await _member(client, "bob7")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob7", "qa1")
    await _seed_pool_auth("bob7", "fin-service-maker")
    await _seed_combo_identity("logi-maker", "logi-service")
    # 方案绑 fin-service → qa1;组合另给 fin-service → fin-service-maker
    # (方案键须胜出)+ logi(方案没有,组合补)
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=bob,
                          json={"name": "方案甲", "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {
                                    "fin-service": {"alias": "qa1"}},
                                "options": {}})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]
    cid = await _mk_combo(client, bob, "组合G", [
        {"service": "fin-service", "alias": "fin-service-maker"},
        {"service": "logi-service", "alias": "logi-maker"}])
    await _bind(client, bob, "sc-test", cid, scheme_id)

    async with db_module.SessionLocal() as db:
        from app.services.scenario_store import get_row
        scen = await get_row(db, "sc-test")
        body = RunRequest(scenarioId="sc-test", schemeId=scheme_id)
        await _apply_scheme_recipe(db, scen, body)
        merged = {k: b.model_dump(by_alias=True)
                  for k, b in body.service_bindings.items()}
        assert merged == {
            "fin-service": {"alias": "qa1"},   # 方案键胜出(不被组合垫底冲掉)
            "logi-service": {"alias": "logi-maker"},  # 组合垫底存活
        }
        # schemeId/schemeName 溯源照写(回归防护)
        assert body.scheme_name == "方案甲"


# ── 预览面:合并序 + fail-closed ─────────────────────────────────

async def test_preview_combo_merge_and_gate(client, plate_mock: PlateMock):
    """预览(§3.2):组合 < 方案 < 请求;引用服务悬空 → 409 同码。"""
    bob = await _member(client, "bob8")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob8", "qa1")
    await _seed_pool_auth("bob8", "fin-service-maker")
    await _seed_deployment()
    cid = await _mk_combo(client, bob, "组合H", [
        {"service": "fin-service", "alias": "fin-service-maker"}])
    await _bind(client, bob, "sc-test", cid)

    # 请求不带绑定 → 组合条目进装载
    r = await client.post("/api/runs/preview", headers=bob, json={
        "scenarioId": "sc-test"})
    assert r.status_code == 200, r.text
    assert "fin-service-maker" in r.json()["auths"]

    # 请求带绑定 → 请求级胜出
    r = await client.post("/api/runs/preview", headers=bob, json={
        "scenarioId": "sc-test",
        "serviceBindings": {"fin-service": {"alias": "qa1"}}})
    assert r.status_code == 200, r.text
    assert "qa1" in r.json()["auths"]

    # 引用服务条目悬空 → 409 fail-closed
    await _delete_identity("fin-service-maker")
    r = await client.post("/api/runs/preview", headers=bob, json={
        "scenarioId": "sc-test"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "identity_combo_missing"


# ── 预检报告面 ──────────────────────────────────────────────────

async def test_precheck_report_combo_missing(client, plate_mock: PlateMock):
    """UI 预检:组合行缺失(竞态)→ comboMissing 信号(§6.3);未绑 =
    None。"""
    from app.models import AccountCombo
    bob = await _member(client, "bob9")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob9", "qa1")
    await _seed_deployment()
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=bob,
                          json={"name": "预检方案", "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {},
                                "options": {}})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]
    cid = await _mk_combo(client, bob, "组合I", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid, scheme_id)

    async def _precheck() -> dict:
        r = await client.post("/api/run/precheck", headers=bob,
                              json=[{"scenarioId": "sc-test",
                                     "schemeId": scheme_id}])
        assert r.status_code == 200, r.text
        return r.json()[0]

    assert (await _precheck())["comboMissing"] is None
    async with db_module.SessionLocal() as s:
        await s.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await s.commit()
    out = await _precheck()
    assert out["comboMissing"] is not None
    assert out["comboMissing"]["comboId"] == cid
    assert out["schemeValid"] is False


async def test_token_task_scope_uses_combo_bindings(client, fresh_db):
    """令牌任务缺项统计与执行前复核同源:组合别名进入范围集合。"""
    from app.models import IntegrationTask
    from app.routers.access_tokens import _task_bindings
    from app.services.scenario_store import get_row

    bob = await _member(client, "bob_task_scope")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob_task_scope", "qa1")
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=bob,
                          json={"name": "令牌方案", "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {}})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]
    cid = await _mk_combo(client, bob, "令牌组合", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid, scheme_id)

    async with db_module.SessionLocal() as db:
        scen = await get_row(db, "sc-test")
        tpl = IntegrationTask(name="token-scope", scenario_id="sc-test",
                              owner_id=scen.owner_id, scheme_id=scheme_id)
        bindings = await _task_bindings(db, tpl, scen)
        assert bindings == {"fin-service": {"alias": "qa1"}}
        tpl.scheme_id = "raw"
        assert await _task_bindings(db, tpl, scen) == {}


# ── 集成面:规范化 payload + 指纹含组合修订 ────────────────────────

async def test_integration_shape_and_fingerprint(client, fresh_db):
    """_load_exec_shape 返回规范化 scheme_payload(三面同源,§3.2);
    consent 指纹显式含组合 id+revision(§6.5)—— 条目变化(修订 +1)
    → 指纹变 → 非 owner 订阅者须重新确认。"""
    from app.models import IntegrationTask
    from app.services import integration_runner as ir
    from app.services.scenario_store import get_row

    bob = await _member(client, "bob10")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob10", "qa1")
    await _seed_combo_identity("logi-maker", "logi-service")
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=bob,
                          json={"name": "集成方案", "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {},
                                "options": {}})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]
    cid = await _mk_combo(client, bob, "组合J", [
        {"service": "logi-service", "alias": "logi-maker"}])
    await _bind(client, bob, "sc-test", cid, scheme_id)

    # 每阶段新会话:路由侧写发生在别的会话,长持会话的 identity map
    # 会读到陈旧行(组合修订/解绑不可见)。
    async with db_module.SessionLocal() as db:
        scen = await get_row(db, "sc-test")
        _, scheme_payload, bindings, _, _ = await ir._load_exec_shape(
            db, scheme_id, scen)
        # 规范化:合并终值写回 scheme_payload(_template_env/_slot_
        # bindings_of/指纹三面读同一份)
        assert scheme_payload["serviceBindings"] == {
            "logi-service": {"alias": "logi-maker"}}
        assert bindings == {"logi-service": {"alias": "logi-maker"}}
        tpl = IntegrationTask(name="t", scenario_id="sc-test",
                              owner_id=scen.owner_id, scheme_id=scheme_id,
                              trigger_cron="0 0 * * *")
        db.add(tpl)
        await db.commit()

    async def _fp() -> str:
        async with db_module.SessionLocal() as db:
            scen = await get_row(db, "sc-test")
            tpl = (await db.execute(sa.select(IntegrationTask).where(
                IntegrationTask.name == "t"))).scalar_one()
            return await ir.consent_fingerprint_now(db, tpl, scen)

    fp0 = await _fp()
    # 条目变化(修订 +1)→ 指纹变(组合来源变化触发重新确认,即使终值
    # 层面无差异)
    r2 = await client.patch(f"/api/account-combos/{cid}", headers=bob,
                            json={"entries": [
                                {"service": "logi-service",
                                 "alias": "logi-maker"},
                                {"service": "fin-service",
                                 "alias": "qa1"}]})
    assert r2.status_code == 200, r.text
    assert r2.json()["revision"] == 2
    fp1 = await _fp()
    assert fp1 != fp0
    # 解绑 → 指纹再变(来源消失本身入投影)
    await _bind(client, bob, "sc-test", None, scheme_id)
    fp2 = await _fp()
    assert fp2 != fp1


# ── Suite 图面:垫底 + 同闸 ─────────────────────────────────────

async def test_graph_units_combo_pad_and_gate(client, fresh_db):
    """resolve_graph_units:无方案时组合也生效(垫底不依赖方案,§3.2);
    组合行缺失 → combo.missing 信号(materialize_graph 校验环归
    identity_combo_missing)。"""
    from app.models import AccountCombo
    from app.services import graph_dispatch as gd
    from app.services.scenario_store import get_row

    bob = await _member(client, "bob11")
    await _seed_scenario(client, bob)
    await _seed_combo_identity("logi-maker", "logi-service")
    cid = await _mk_combo(client, bob, "组合K", [
        {"service": "logi-service", "alias": "logi-maker"}])
    await _bind(client, bob, "sc-test", cid)

    async with db_module.SessionLocal() as db:
        scen = await get_row(db, "sc-test")
        resolved = await gd.resolve_graph_units(db, [{
            "ref": "u1", "scenarioId": "sc-test",
            "serviceBindings": {}}], scen.owner_id)
        assert resolved[0]["unit"]["serviceBindings"] == {
            "logi-service": {"alias": "logi-maker"}}
        assert resolved[0]["combo"].bound
        # 单元级覆盖同名胜出(图/单元覆盖自然在上)
        resolved = await gd.resolve_graph_units(db, [{
            "ref": "u1", "scenarioId": "sc-test",
            "serviceBindings": {
                "logi-service": {"alias": "unit-x"}}}], scen.owner_id)
        assert resolved[0]["unit"]["serviceBindings"]["logi-service"] == {
            "alias": "unit-x"}
        # 组合行缺失 → missing 信号(校验环的闸输入)
        await db.execute(sa.delete(AccountCombo).where(
            AccountCombo.id == cid))
        await db.commit()
        resolved = await gd.resolve_graph_units(db, [{
            "ref": "u1", "scenarioId": "sc-test",
            "serviceBindings": {}}], scen.owner_id)
        assert resolved[0]["combo"].missing is True


# ── 复活钩子(§6.3:组合修复/重绑 → 暂停实例 best-effort 复活)────

async def test_revive_triggers(client, fresh_db, monkeypatch):
    calls: list[dict] = []

    async def _fake_revive(user_id=None, *, token_id=None, project_id=None):
        calls.append({"user_id": user_id, "project_id": project_id})

    from app.services import integration_runner
    monkeypatch.setattr(
        integration_runner, "revive_paused_instances", _fake_revive)

    # 注意:routers 侧延迟 import(integration_runner 模块属性替换即生效)
    bob = await _member(client, "bob12")
    uid = await _uid_of("bob12")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob12", "qa1")
    cid = await _mk_combo(client, bob, "组合L", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid)
    assert calls and calls[-1] == {"user_id": uid, "project_id": None}

    calls.clear()
    # 元数据修改不触发复活
    r = await client.patch(f"/api/account-combos/{cid}", headers=bob,
                           json={"description": "只改说明"})
    assert r.status_code == 200
    assert not calls
    # 条目实质变化 → 触发(个人组合 → user_id 维)
    r = await client.patch(f"/api/account-combos/{cid}", headers=bob,
                           json={"entries": []})
    assert r.status_code == 200
    assert calls and calls[-1]["user_id"] == uid

    calls.clear()
    # 解绑 → 触发
    await _bind(client, bob, "sc-test", None)
    assert calls and calls[-1]["user_id"] == uid


async def _uid_of(username: str) -> int:
    from app.models import User
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(User.id).where(
            User.username == username))).scalar_one()


# ── Suite 直跑:调用方垫底(纯函数签名不动,§3.2)────────────────

async def test_suite_pad_combo_req(client, fresh_db):
    """_pad_combo_req:方案绑定与组合垫底合并;未绑 = 原样返回。"""
    from app.routers.suites import _pad_combo_req, _req_from_scheme
    from app.services.scenario_store import get_row

    bob = await _member(client, "bob13")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob13", "qa1")
    cid = await _mk_combo(client, bob, "组合M", [
        {"service": "fin-service", "alias": "qa1"}])
    await _bind(client, bob, "sc-test", cid)

    async with db_module.SessionLocal() as db:
        scen = await get_row(db, "sc-test")
        req = _req_from_scheme(
            "sc-test", {"serviceBindings": {}, "dataSetIds": [],
                        "dataSetSelection": [], "injectionEntryIds": [],
                        "options": {}}, "batch-1")
        out = await _pad_combo_req(db, scen, req)
        assert {k: b.model_dump(by_alias=True)
                for k, b in out.service_bindings.items()} == {
            "fin-service": {"alias": "qa1"}}
        # 方案键胜出
        req2 = _req_from_scheme(
            "sc-test", {"serviceBindings": {
                "fin-service": {"alias": "scheme-x"}}, "dataSetIds": [],
                "dataSetSelection": [], "injectionEntryIds": [],
                "options": {}}, "batch-1")
        out2 = await _pad_combo_req(db, scen, req2)
        assert out2.service_bindings["fin-service"].model_dump(
            by_alias=True) == {"alias": "scheme-x"}
        # 未绑 = 原样
        await _bind(client, bob, "sc-test", None)
        await db.rollback()
        scen = await get_row(db, "sc-test")
        req3 = _req_from_scheme(
            "sc-test", {"serviceBindings": {}, "dataSetIds": [],
                        "dataSetSelection": [], "injectionEntryIds": [],
                        "options": {}}, "batch-1")
        out3 = await _pad_combo_req(db, scen, req3)
        assert not out3.service_bindings
        # raw 不吃默认方案组合
        await _bind(client, bob, "sc-test", cid)
        await db.rollback()
        scen = await get_row(db, "sc-test")
        req_raw = _req_from_scheme(
            "sc-test", {"serviceBindings": {}, "dataSetIds": [],
                        "dataSetSelection": [], "injectionEntryIds": [],
                        "options": {}}, "batch-1")
        req_raw.scheme_id = "raw"
        out_raw = await _pad_combo_req(db, scen, req_raw)
        assert not out_raw.service_bindings


# 引用服务集合单源与 combo gate 的分码半边(单元级)
async def test_referenced_gate_only_checks_effective_combo_entries(
        fresh_db) -> None:
    """未引用、面内覆盖或换用覆盖的悬空组合条目不连坐。"""
    from app.services import account_combo as ac

    async with db_module.SessionLocal() as db:
        env = await _env_id()
        db.add(ServiceIdentity(alias_name="ok", base_service="logi-service",
                               env_id=env, ref_mode="username",
                               ref_username="ok-user"))
        await db.commit()
        combo = ac.ComboBase(7, "c", 1, {"fin-service": "ghost",
                                         "logi-service": "ok"})
        await ac.referenced_combo_gate(db, combo, ["logi-service"])
        await ac.referenced_combo_gate(
            db, combo, ["fin-service"],
            {"fin-service": {"alias": "face-override"}})
        await ac.referenced_combo_gate(
            db, combo, ["fin-service"], slot_map={"ghost": "slot-override"})
        try:
            await ac.referenced_combo_gate(db, combo, ["fin-service"])
        except ac.ComboIdentityMissing as e:
            assert e.service == "fin-service"
            assert e.alias == "ghost"
            assert e.detail() == {"comboId": 7, "service": "fin-service",
                                  "alias": "ghost"}
        else:
            raise AssertionError("悬空条目应 fail-closed")
        missing = ac.ComboBase(8, "gone", 1, missing=True)
        try:
            await ac.referenced_combo_gate(
                db, missing, ["fin-service"],
                {"fin-service": {"alias": "face-override"}})
        except ac.ComboIdentityMissing as e:
            assert e.combo_id == 8
        else:
            raise AssertionError("组合行缺失应无条件 fail-closed")
