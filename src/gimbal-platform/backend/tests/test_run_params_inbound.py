"""入站执行参数(params)+ raw 方案 + clientRef 幂等 — 设计 2026-11-13 §7-⑥。

* 契约读写:创建/回读透传、写时校验(悬空/重复/pattern 类型/上限)、
  PUT 缺键保留(前端无编辑面期防抹掉)与显式清空;
* 422 全码矩阵(§2.3 五道闸,顺序与 fail-closed)+ 互斥族(§2.4);
* raw:虚行合成(datasets=单虚行)+ skip_carry + config_json 三键
  (inboundParams/carryPolicy=off/paramsStrict)+ schemeId="raw" 溯源;
* 混合:默认方案 + params(carry 照旧 → 无 carryPolicy 键);
* clientRef 幂等:令牌/JWT 两维 409 回显原 executionId + 列表过滤;
* rerun 回放:params/schemeId("raw")按快照回放、数据集/注入剥离、
  clientRef 不回放(重跑是新的一次独立发起)。
"""
from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft as _draft
from .test_access_tokens import _register, _user_id
from .test_adhoc_run import (
    CRED, EP, SVC,
    _personal, _plate_ready, _seed_target, _seed_user_auth,
)
from ._fanout_stub import _capture_fanout
from . import test_scenario_composer_plate_integration as _plate_it

# pytest 按对象上的 fixture 标记注册(名称仍为 plate_mock);走模块属性
# 而非 from-import,避免测试参数同名触发 pyflakes 的重定义告警。
plate_mock = _plate_it.plate_mock

SID = "sc-params-it"
USER = "params_user"

# 基线 vars:orderNo/amount/memo/flag 空(等 params 给值);channel 有
# 基线值(strict 下「基线非空」分支的样板)。
VARS = {"orderNo": "", "amount": 0, "memo": "", "flag": False,
        "channel": "POS"}

SLOTS = [
    {"name": "orderNo", "required": True, "pattern": "^PO[0-9]{8}$",
     "maxLength": 64, "description": "采购订单号"},
    {"name": "amount", "type": "number", "required": True},
    {"name": "memo", "required": False, "maxLength": 8},
    {"name": "flag", "type": "boolean", "required": False},
    {"name": "channel", "required": False},
]

GOOD_PARAMS = {"orderNo": "PO12345678", "amount": 199.0,
               "memo": "加急", "flag": True, "channel": "APP"}


def _steps() -> list[dict]:
    return [{
        "endpoint": EP, "service": SVC,
        "body": {
            "orderNo": "${var.orderNo}", "amount": "${var.amount}",
            "memo": "${var.memo}", "flag": "${var.flag}",
            "channel": "${var.channel}",
        },
    }]


def _payload(*, slots: list | None = SLOTS, strict: bool = False,
             vars_map: dict | None = VARS, sid: str = SID) -> dict:
    d = _draft(sid, steps=_steps(), vars_map=vars_map)
    return {**d, "paramSlots": slots, "paramsStrict": strict}


async def _jwt_owner(client) -> dict:
    """场景属主(mk_user 直插,密码 'x')的 JWT 头 —— 走登录。"""
    r = await client.post("/api/auth/login", json={
        "username": USER, "password": "x"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _mk_scenario(payload: dict, username: str = USER) -> None:
    async with db_module.SessionLocal() as db:
        await scenario_store.create(
            db, ScenarioDraft.model_validate(payload),
            owner=username, owner_id=await _user_id(username))


async def _draft_payload(sid: str) -> dict:
    async with db_module.SessionLocal() as db:
        row = await scenario_store.get_row(db, sid)
        return row.payload


async def _executions() -> list:
    from app.models.execution import Execution
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            sa.select(Execution).order_by(Execution.id))).scalars().all())


async def _execution(ex_id: int):
    from app.models.execution import Execution
    async with db_module.SessionLocal() as s:
        return await s.get(Execution, ex_id)


async def _wait_terminal(ex_id: int, timeout_s: float = 15.0):
    import asyncio
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        ex = await _execution(ex_id)
        if ex is not None and ex.status in ("done", "failed", "canceled"):
            return ex
        await asyncio.sleep(0.1)
    raise TimeoutError(f"execution {ex_id} not terminal")


@pytest.fixture
async def ready(client, plate_mock) -> dict:
    """场景(契约 + vars + ${var.*} 步骤)+ 个人令牌(范围 ⊇ SVC/qa-cred)。

    返回请求头;场景契约默认 SLOTS/非 strict(各用例自行建变体场景)。
    """
    await _seed_target()
    from .inbound_fixtures import mk_user
    await mk_user(USER, role="admin")
    account_user = await _seed_user_auth(USER)
    await _mk_scenario(_payload())
    h = await _personal(client, USER, scope_aliases=(SVC,),
                        cred_usernames=(account_user,))
    _plate_ready(plate_mock)
    return h


# ── 契约读写(§2.1 写时校验 + 缺键保留)──────────────────────────


class TestContractStore:
    async def test_roundtrip(self, ready):
        payload = await _draft_payload(SID)
        got = {s["name"]: s for s in payload["paramSlots"]}
        assert set(got) == {"orderNo", "amount", "memo", "flag", "channel"}
        assert got["orderNo"] == {
            "name": "orderNo", "type": "string", "required": True,
            "pattern": "^PO[0-9]{8}$", "maxLength": 64,
            "description": "采购订单号"}
        assert got["amount"]["type"] == "number"
        assert payload["paramsStrict"] is False

    async def test_slot_var_not_declared(self, ready):
        with pytest.raises(ValueError, match="param_slot_var_not_declared"):
            await _mk_scenario(_payload(
                sid="sc-params-dangling",
                slots=[{"name": "nope", "required": True}]), USER)

    async def test_slot_generative_var_rejected(self, ready):
        with pytest.raises(ValueError, match="param_slot_var_not_declared"):
            await _mk_scenario(_payload(
                sid="sc-params-gen",
                vars_map={**VARS, "gen": {"kind": "seq"}},
                slots=SLOTS + [{"name": "gen"}]), USER)

    async def test_slot_duplicate_rejected(self, ready):
        with pytest.raises(ValueError, match="param_slot_name_duplicated"):
            await _mk_scenario(_payload(
                sid="sc-params-dup",
                slots=[{"name": "orderNo"}, {"name": "orderNo"}]), USER)

    async def test_slot_pattern_on_number_rejected(self, ready):
        with pytest.raises(ValueError, match="param_slot_pattern_type"):
            await _mk_scenario(_payload(
                sid="sc-params-pat",
                slots=[{"name": "amount", "type": "number",
                        "pattern": "x"}]), USER)

    async def test_slot_over_64_rejected(self, ready):
        """上限 64 在 pydantic 层拦(ScenarioDraft.max_length)—— fail-closed。"""
        from pydantic import ValidationError
        vars64 = {**VARS, **{f"v{i}": "" for i in range(60)}}
        with pytest.raises(ValidationError, match="at most 64"):
            await _mk_scenario(_payload(
                sid="sc-params-64", vars_map=vars64,
                slots=[{"name": n} for n in vars64]), USER)

    async def test_put_absent_keys_preserve_contract(self, ready):
        """前端整包保存(不含新键)不得抹掉 API 侧维护的契约。"""
        payload = await _draft_payload(SID)
        stripped = _draft(SID, steps=_steps(), vars_map=VARS)
        assert "paramSlots" not in stripped  # 前端形态:无新键
        async with db_module.SessionLocal() as db:
            await scenario_store.update(
                db, SID, ScenarioDraft.model_validate(stripped))
        after = await _draft_payload(SID)
        assert after["paramSlots"] == payload["paramSlots"]
        assert after["paramsStrict"] is False

    async def test_put_absent_keys_and_var_deleted_rejected(self, ready):
        """缺键 PUT + 删变量:保留的契约要对新定义重验(防悬空)。

        review 修复回归:保留逻辑必须先于写时校验,否则空入参槽位
        平凡通过、悬空契约落库。
        """
        # 前端形态整包保存,且从 vars 里删掉了 orderNo
        stripped = _draft(SID, steps=_steps(),
                          vars_map={k: v for k, v in VARS.items()
                                    if k != "orderNo"})
        with pytest.raises(ValueError,
                           match="param_slot_var_not_declared"):
            async with db_module.SessionLocal() as db:
                await scenario_store.update(
                    db, SID, ScenarioDraft.model_validate(stripped))

    async def test_put_partial_keys_preserve_slots(self, ready):
        """只带 paramsStrict 不带 paramSlots 的部分携带 PUT 不清空槽位。"""
        body = {**_draft(SID, steps=_steps(), vars_map=VARS),
                "paramsStrict": True}
        async with db_module.SessionLocal() as db:
            await scenario_store.update(
                db, SID, ScenarioDraft.model_validate(body))
        after = await _draft_payload(SID)
        assert {s["name"] for s in after["paramSlots"]} == set(VARS)
        assert after["paramsStrict"] is True

    async def test_put_explicit_clear(self, ready):
        stripped = _draft(SID, steps=_steps(), vars_map=VARS)
        body = {**stripped, "paramSlots": [], "paramsStrict": False}
        async with db_module.SessionLocal() as db:
            await scenario_store.update(
                db, SID, ScenarioDraft.model_validate(body))
        after = await _draft_payload(SID)
        assert after["paramSlots"] == []
        assert after["paramsStrict"] is False


# ── 422 全码矩阵 + 互斥族(§2.3/§2.4)────────────────────────────


class TestValidationMatrix:
    async def _post(self, client, h, body):
        return await client.post("/api/runs", headers=h, json=body)

    @staticmethod
    def _code(r):
        return r.json()["detail"]["code"]

    async def test_no_contract_422(self, ready, client):
        """存量场景(未声明契约)带 params → 指引先声明;行为零变化。"""
        import pytest
        await _mk_scenario(_draft("sc-params-legacy", steps=_steps(),
                                  vars_map=VARS), USER)
        r = await self._post(client, ready, {
            "scenarioId": "sc-params-legacy",
            "params": {"orderNo": "PO12345678"}})
        assert r.status_code == 422, r.text
        assert self._code(r) == "param_slot_not_declared"
        assert await _executions() == []

    async def test_required_missing_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {"memo": "x"}})
        assert r.status_code == 422 and self._code(r) == "param_required_missing"
        assert r.json()["detail"]["fields"] == ["amount", "orderNo"]
        assert await _executions() == []

    async def test_unknown_key_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {**GOOD_PARAMS, "evil": "1"}})
        assert r.status_code == 422 and self._code(r) == "param_not_declared"
        assert r.json()["detail"]["fields"] == ["evil"]
        assert await _executions() == []

    async def test_null_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {**GOOD_PARAMS, "memo": None}})
        assert r.status_code == 422 and self._code(r) == "param_value_null"
        assert await _executions() == []

    async def test_template_forbidden_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID,
            "params": {**GOOD_PARAMS, "memo": "${auth.x.token}"}})
        assert r.status_code == 422
        assert self._code(r) == "param_template_forbidden"
        assert await _executions() == []

    async def test_type_mismatch_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {**GOOD_PARAMS, "amount": "abc"}})
        assert r.status_code == 422 and self._code(r) == "param_type_mismatch"
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {**GOOD_PARAMS, "flag": "yes"}})
        assert r.status_code == 422 and self._code(r) == "param_type_mismatch"
        assert await _executions() == []

    async def test_coerced_string_values_pass(self, ready, client,
                                              monkeypatch):
        """数字串/布尔串按 coerce_row_value 口径放行(虚行同源)。"""
        cap = await _capture_fanout(monkeypatch)
        r = await self._post(client, ready, {
            "scenarioId": SID,
            "params": {**GOOD_PARAMS, "amount": "199.0", "flag": "true"}})
        assert r.status_code == 201, r.text
        await _wait_terminal(r.json()["executionId"])
        assert cap and cap[0]["datasets"][0]["rows"][0][1]["amount"] == "199.0"

    async def test_pattern_mismatch_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {**GOOD_PARAMS,
                                          "orderNo": "XX12345678"}})
        assert r.status_code == 422
        assert self._code(r) == "param_pattern_mismatch"
        assert await _executions() == []

    async def test_too_long_422(self, ready, client):
        r = await self._post(client, ready, {
            "scenarioId": SID,
            "params": {**GOOD_PARAMS, "memo": "123456789"}})
        assert r.status_code == 422 and self._code(r) == "param_too_long"
        assert await _executions() == []

    async def test_strict_placeholder_missing_422(self, ready, client):
        """strict:占位须 params 给值或基线非空。

        全可选槽位(隔离闸 4):channel 基线 "POS" / amount 基线 0 /
        flag 基线 False 均算非空 → 只报 orderNo/memo(基线空串)。"""
        opt_slots = [{**s, "required": False} for s in SLOTS]
        await _mk_scenario(_payload(sid="sc-params-strict", strict=True,
                                    slots=opt_slots), USER)
        r = await self._post(client, ready, {
            "scenarioId": "sc-params-strict",
            "params": {"channel": "APP"}})
        assert r.status_code == 422, r.text
        assert self._code(r) == "param_placeholder_missing"
        assert sorted(r.json()["detail"]["fields"]) == ["memo", "orderNo"]
        assert await _executions() == []

    async def test_strict_pass_with_full_params(self, ready, client,
                                                monkeypatch):
        opt_slots = [{**s, "required": False} for s in SLOTS]
        await _mk_scenario(_payload(sid="sc-params-strict", strict=True,
                                    slots=opt_slots), USER)
        cap = await _capture_fanout(monkeypatch)
        r = await self._post(client, ready, {
            "scenarioId": "sc-params-strict", "params": GOOD_PARAMS})
        assert r.status_code == 201, r.text
        await _wait_terminal(r.json()["executionId"])
        assert cap

    async def test_mutex_steps_params(self, ready, client):
        r = await self._post(client, ready, {
            "steps": [{"endpoint": EP, "service": SVC, "body": {}}],
            "params": GOOD_PARAMS})
        assert r.status_code == 422 and self._code(r) == "run_target_ambiguous"
        assert await _executions() == []

    async def test_mutex_graph_params(self, ready, client):
        """graph + params 是 JWT 专属组合(令牌带 graph 被 M1 先拒)。"""
        h = await _register(client, "params_graph_jwt")
        r = await self._post(client, h, {
            "scenarioId": SID, "params": GOOD_PARAMS,
            "graph": {"units": [{"scenarioId": SID, "ref": "u1"}]}})
        assert r.status_code == 422, r.text
        assert self._code(r) == "param_graph_conflict"
        assert await _executions() == []

    async def test_mutex_params_datasets(self, ready, client):
        """params+dataSets/injection 组合是 JWT 面(令牌携带被 M1 先拒)。"""
        h = await _register(client, "params_jwt")
        r = await self._post(client, h, {
            "scenarioId": SID, "params": GOOD_PARAMS, "dataSetIds": ["ds-x"]})
        assert r.status_code == 409, r.text
        assert self._code(r) == "run_source_conflict"
        r = await self._post(client, h, {
            "scenarioId": SID, "params": GOOD_PARAMS,
            "injectionEntryIds": ["en-x"]})
        assert r.status_code == 409 and self._code(r) == "run_source_conflict"
        assert await _executions() == []

    async def test_mutex_raw_datasets(self, ready, client):
        """raw+dataSets 是 JWT 面(令牌携带被 M1 先拒)。"""
        h = await _register(client, "params_jwt2")
        r = await self._post(client, h, {
            "scenarioId": SID, "schemeId": "raw",
            "dataSetIds": ["ds-x"]})
        assert r.status_code == 409, r.text
        assert self._code(r) == "run_source_conflict"
        assert await _executions() == []

    async def test_empty_params_ignored(self, ready, client, monkeypatch):
        """"params": {} 等价缺省 —— 不入校验、不触互斥。"""
        cap = await _capture_fanout(monkeypatch)
        r = await self._post(client, ready, {
            "scenarioId": SID, "params": {}, "dataSetIds": []})
        assert r.status_code == 201, r.text
        await _wait_terminal(r.json()["executionId"])
        # 基线空覆盖行(非虚行):datasetId None + 空行
        assert cap[0]["datasets"][0]["rows"][0][1] == {}


# ── raw 虚行 + skip_carry;混合照补(§2.2 三态)───────────────────


class TestRawAndMixed:
    async def test_raw_virtual_row_skip_carry(self, ready, client,
                                              monkeypatch):
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "schemeId": "raw", "params": GOOD_PARAMS,
            "clientRef": "ord-raw-1"})
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        await _wait_terminal(ex_id)
        # 虚行合成:datasets = 单虚行(datasetId None,行值 = params;
        # 行对经队列 JSON 往返为 list)
        virt = cap[0]["datasets"]
        assert len(virt) == 1 and virt[0]["datasetId"] is None
        assert virt[0]["rows"][0][0] == 0
        assert virt[0]["rows"][0][1] == GOOD_PARAMS
        # 任务配方下发 selected_entries(空 = 无注入族);行 × [无注入] = 1 case
        assert cap[0]["injections"] == []
        assert cap[0]["skip_carry"] is True
        ex = await _execution(ex_id)
        cfg = ex.config_json
        assert cfg["inboundParams"] == GOOD_PARAMS
        assert cfg["carryPolicy"] == "off"
        assert cfg["paramsStrict"] is False
        assert cfg["schemeId"] == "raw"          # 保留字原样溯源
        assert ex.client_ref == "ord-raw-1"

    async def test_mixed_default_scheme_carry_on(self, ready, client,
                                                 monkeypatch):
        """混合模式:默认方案配方 + params;carry 照旧(无 carryPolicy 键)。"""
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO87654321",
                                          "amount": 1}})
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        await _wait_terminal(ex_id)
        assert cap[0]["skip_carry"] is False
        assert cap[0]["datasets"][0]["rows"][0][1] == {
            "orderNo": "PO87654321", "amount": 1}
        cfg = (await _execution(ex_id)).config_json
        assert cfg["inboundParams"] == {"orderNo": "PO87654321", "amount": 1}
        assert "carryPolicy" not in cfg
        assert cfg["schemeId"].startswith("rs-")   # 默认方案物化真值

    async def test_virtual_row_reaches_case_vars(self, ready, client,
                                                 monkeypatch):
        """决策 5:虚行走数据集行通路 — compose 后 vars 含参数值。"""
        sink: list[dict] = []

        async def _capture_case(case_path, **_kw):
            sink.append(_json.loads(
                Path(case_path).read_text(encoding="utf-8")))
            from app.services.gimbal_launcher import LaunchResult
            return LaunchResult(launch_status="ok", exit_code=0,
                                total=1, passed=1)

        from app.services import gimbal_launcher as gl
        monkeypatch.setattr(gl, "launch", _capture_case)
        r = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "schemeId": "raw", "params": GOOD_PARAMS})
        assert r.status_code == 201, r.text
        await _wait_terminal(r.json()["executionId"])
        assert sink, "legacy 链应落盘 case 并调 launch"
        blob = _json.dumps(sink[0], ensure_ascii=False)
        assert "PO12345678" in blob and "加急" in blob


# ── clientRef 幂等(决策 8)───────────────────────────────────────


class TestClientRefIdempotency:
    async def test_token_dim_409(self, ready, client, monkeypatch):
        await _capture_fanout(monkeypatch)
        r1 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO11111111",
                                          "amount": 1},
            "clientRef": "ord-idem-1"})
        assert r1.status_code == 201, r1.text
        first = r1.json()["executionId"]
        await _wait_terminal(first)
        r2 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO22222222",
                                          "amount": 2},
            "clientRef": "ord-idem-1"})
        assert r2.status_code == 409, r2.text
        assert r2.json()["detail"]["code"] == "duplicate_client_ref"
        assert r2.json()["detail"]["executionId"] == first
        # 不同 clientRef 照常受理
        r3 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO33333333",
                                          "amount": 3},
            "clientRef": "ord-idem-2"})
        assert r3.status_code == 201, r3.text

    async def test_jwt_dim_409(self, ready, client, monkeypatch):
        """JWT 维度:(owner_id, client_ref) ∧ token_id IS NULL。"""
        await _capture_fanout(monkeypatch)
        h = await _jwt_owner(client)
        r1 = await client.post("/api/runs", headers=h, json={
            "scenarioId": SID, "params": {"orderNo": "PO11111111",
                                          "amount": 1},
            "clientRef": "jwt-idem-1"})
        assert r1.status_code == 201, r1.text
        await _wait_terminal(r1.json()["executionId"])
        r2 = await client.post("/api/runs", headers=h, json={
            "scenarioId": SID, "params": {"orderNo": "PO22222222",
                                          "amount": 2},
            "clientRef": "jwt-idem-1"})
        assert r2.status_code == 409, r2.text
        assert r2.json()["detail"]["code"] == "duplicate_client_ref"

    async def test_list_filter_client_ref(self, ready, client, monkeypatch):
        await _capture_fanout(monkeypatch)
        r1 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO44444444",
                                          "amount": 4},
            "clientRef": "ord-query-1"})
        assert r1.status_code == 201, r1.text
        await _wait_terminal(r1.json()["executionId"])
        r = await client.get("/api/executions", headers=ready,
                             params={"clientRef": "ord-query-1"})
        assert r.status_code == 200, r.text
        rows = r.json()["items"] if "items" in r.json() else r.json()
        ids = [row["id"] for row in rows]
        assert r1.json()["executionId"] in ids
        r = await client.get("/api/executions", headers=ready,
                             params={"clientRef": "ord-none"})
        rows = r.json()["items"] if "items" in r.json() else r.json()
        assert rows == []


# ── rerun 回放(§5)──────────────────────────────────────────────


class TestRerunReplay:
    async def test_rerun_raw_params(self, ready, client, monkeypatch):
        await _capture_fanout(monkeypatch)
        r1 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "schemeId": "raw", "params": GOOD_PARAMS,
            "clientRef": "ord-rerun-1"})
        assert r1.status_code == 201, r1.text
        ex1 = r1.json()["executionId"]
        await _wait_terminal(ex1)
        # rerun 走 JWT(令牌面 rerun 语义与 JWT 一致,用属主 JWT 简化)
        h = await _jwt_owner(client)
        r2 = await client.post(f"/api/executions/{ex1}/rerun", headers=h)
        assert r2.status_code in (200, 201), r2.text
        ex2 = r2.json()["executionId"]
        await _wait_terminal(ex2)
        cfg = (await _execution(ex2)).config_json
        assert cfg["inboundParams"] == GOOD_PARAMS   # params 回放
        assert cfg["schemeId"] == "raw"              # 保留字原样
        assert cfg["carryPolicy"] == "off"
        # clientRef 不回放 → 不触幂等 409(重跑是独立发起)
        assert (await _execution(ex2)).client_ref is None

    async def test_rerun_strips_datasets_for_params_mode(
            self, ready, client, monkeypatch):
        """首发混合模式(方案带 dataSetIds)rerun:虚行路径不消费 → 剥离。"""
        # 给默认方案塞 dataSetIds(模拟方案配方带数据集)
        from app.services import scheme_store as _ss
        from app.models.composer_data_set import ComposerDataSet
        async with db_module.SessionLocal() as s:
            await s.merge(ComposerDataSet(
                dataset_id="ds-params", scenario_id=SID, name="d1",
                rows=[{"orderNo": "PO99999999", "amount": 9}]))
            sch = await _ss.resolve_for_run(s, SID, None)
            payload = dict(sch.payload or {})
            payload["dataSetIds"] = ["ds-params"]
            sch.payload = payload
            await s.commit()
        cap = await _capture_fanout(monkeypatch)
        r1 = await client.post("/api/runs", headers=ready, json={
            "scenarioId": SID, "params": {"orderNo": "PO12345678",
                                          "amount": 1}})
        assert r1.status_code == 201, r1.text
        ex1 = r1.json()["executionId"]
        await _wait_terminal(ex1)
        # 方案带入的数据集行不消费(评审 ①:砍掉比缝合便宜)
        assert cap[0]["datasets"][0]["rows"][0][1] == {
            "orderNo": "PO12345678", "amount": 1}
        h = await _jwt_owner(client)
        r2 = await client.post(f"/api/executions/{ex1}/rerun", headers=h)
        assert r2.status_code in (200, 201), r2.text
        await _wait_terminal(r2.json()["executionId"])
        # rerun 不因 params+dataSetIds 组合 409(回放已剥离)
        cfg = (await _execution(r2.json()["executionId"])).config_json
        assert cfg["dataSetIds"] == []

