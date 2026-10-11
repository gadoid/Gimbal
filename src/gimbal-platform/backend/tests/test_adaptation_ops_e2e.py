"""RS4a/RS4b 验收门:带 op 的端到端提交测试(评审建议轮)。

五种 op 各一例——字段改名/字段删除/换服务(rebindField)/一拆二
(splitStep)/删除步骤(removeStep)。每例验证:
  * 提交后能执行(目标修订试算在**方案态**上通过,H1);
  * 注入条目指向正确(jsonpath/stepIndex 随 op 改写,H2);
  * 结构级 op 后 RunScheme stepTo 已清空(R30);
  * 回滚后与原场景逐字段一致(§5.7)。
"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from app.core import db as db_module
from app.models.composer_run_scheme import ComposerRunScheme
from app.schemas.scenario_composer import ScenarioDraft
from app.services import adaptation_service, plate_client, scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.settlement.create"

# 目标修订声明:amount(必填,string)、settle(可空)、extra(可空)
TARGET_FULL = {"id": EP, "request": {"declarations": [
    {"name": "amount", "path": "$.amount", "type": "number",
     "state": "form", "required": True},
    {"name": "settle", "path": "$.settle", "type": "string",
     "state": "form", "required": False},
]}, "responses": {"200": {"declarations": [
    {"name": "code", "path": "$.code", "type": "string",
     "state": "form"}]}}}


async def _seed(client, name: str, *, body=None, entries=None,
                step_to=5):
    """建场景:1 步(带 endpoint 锚点)+ 可选注入条目 + RunScheme(stepTo)。"""
    user = await register_and_login(client, name, "pw123456")
    steps = [{
        "kind": "step", "endpoint": EP,
        "call": {"protocol": "http", "service": "fin-service",
                 "headers": {}},
        "request": {"kind": "request",
                    "body": body if body is not None
                    else {"legacy_amt": 100}},
        "strategy": [],
    }]
    draft = make_draft(f"sc-{name}", steps=steps, system=["fin"])
    draft["definition"]["meta"]["plate"] = {"fin": "1.0#1"}
    if entries is not None:
        draft["assertion_registry"] = {"entries": entries}
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(draft),
            owner=name, owner_id=1)
        s.add(ComposerRunScheme(
            scheme_id=f"rsch-{name}", scenario_id=f"sc-{name}",
            name="调试", is_default=False,
            payload={"options": {"step_from": None, "step_to": step_to, "n_runs": 1, "parallel": 1, "subscribe": None}}))
        await s.commit()
    return user


def _patch_plate(monkeypatch):
    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}
    async def fake_full_at(eid, ref):
        return deepcopy(TARGET_FULL)
    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)


async def _submit(client, user, sid, ops, **extra):
    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": sid, "ops": ops, "targetRevision": "1.0#2",
        "saveMode": "direct", **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _payload(sid):
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, sid)
        return deepcopy(row.payload), row


async def _rollback(client, user, batch_id, force=False):
    r = await client.post(
        f"/api/adaptations/batches/{batch_id}/rollback",
        headers=user, params={"force": "true"} if force else None)
    assert r.status_code == 200, r.text
    return r.json()


async def _step_to(sid):
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid))).scalars().all()
        return [((r.payload or {}).get("options") or {}).get("step_to") for r in rows]


# ─── 字段改名(renameField)─────────────────────────────────────────

async def test_e2e_rename_field(client, monkeypatch):
    user = await _seed(client, "e2erename", entries=[{
        "id": "ent-amt", "name": "金额",
        "path": {"stepIndex": 0, "source": "body",
                 "jsonpath": "$.legacy_amt.deep"},
        "value": 1, "asserts": []}])
    _patch_plate(monkeypatch)

    before, _ = await _payload("sc-e2erename")
    # H1 的核心断言面:legacy_amt 在目标修订不存在 → 现状检查报多余;
    # renameField 把它改成 amount 后,方案态检查必须通过
    cur = await client.post("/api/adaptations/save-check", headers=user,
                            json={"scenarioId": "sc-e2erename",
                                  "targetRevision": "1.0#2"})
    assert any(i["code"] == "extra_field"
               for i in cur.json()["blocking_issues"])

    out = await _submit(client, user, "sc-e2erename", [
        {"op": "renameField", "step": 0, "from": "legacy_amt",
         "to": "amount"}])
    planned, _ = await _payload("sc-e2erename")
    body = planned["definition"]["steps"][0]["request"]["body"]
    assert "amount" in body and "legacy_amt" not in body
    # H2:注入条目 jsonpath 随改名改写
    ent = planned["assertion_registry"]["entries"][0]
    assert ent["path"]["jsonpath"] == "$.amount.deep"
    assert not ent.get("_dangling")

    await _rollback(client, user, out["batch_id"])
    restored, _ = await _payload("sc-e2erename")
    assert restored == before            # §5.7 逐字段一致


# ─── 字段删除(removeField)─────────────────────────────────────────

async def test_e2e_remove_field(client, monkeypatch):
    user = await _seed(client, "e2eremove",
                       body={"amount": 100, "legacy_amt": "x"},
                       entries=[{
        "id": "ent-x", "name": "x",
        "path": {"stepIndex": 0, "source": "body",
                 "jsonpath": "$.legacy_amt"},
        "value": 9, "asserts": []}])
    _patch_plate(monkeypatch)
    before, _ = await _payload("sc-e2eremove")

    # 悬空条目 = R14 评审项:未确认先拒,确认后放行(设计语义)
    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": "sc-e2eremove",
        "ops": [{"op": "removeField", "step": 0,
                  "field": "legacy_amt"}],
        "targetRevision": "1.0#2", "saveMode": "direct"})
    assert r.status_code == 409
    assert "review_items_unconfirmed" in r.text
    out = await _submit(client, user, "sc-e2eremove", [
        {"op": "removeField", "step": 0, "field": "legacy_amt"}],
        reviewConfirmed=True)
    planned, _ = await _payload("sc-e2eremove")
    assert "legacy_amt" not in  planned["definition"]["steps"][0]["request"]["body"]
    # H2:删除的根段 → 条目标悬空(预检/正式执行 409 可见)
    ent = planned["assertion_registry"]["entries"][0]
    assert ent.get("_dangling") is True
    assert ent["path"]["jsonpath"] == "$.legacy_amt"

    await _rollback(client, user, out["batch_id"])
    restored, _ = await _payload("sc-e2eremove")
    assert restored == before


# ─── 换服务(rebindField)────────────────────────────────────────────

async def test_e2e_rebind_field(client, monkeypatch):
    user = await _seed(client, "e2erebind",
                       body={"amount": 100, "settle": "1"})
    _patch_plate(monkeypatch)
    before, _ = await _payload("sc-e2erebind")

    out = await _submit(client, user, "sc-e2erebind", [
        {"op": "rebindField", "step": 0, "field": "settle",
         "var": "settle_default"}])
    planned, _ = await _payload("sc-e2erebind")
    body = planned["definition"]["steps"][0]["request"]["body"]
    assert body["settle"] == "${var.settle_default}"
    # 原值落 vars(D8)
    assert planned["definition"]["config"]["vars"]  .get("settle_default") == "1"

    await _rollback(client, user, out["batch_id"])
    restored, _ = await _payload("sc-e2erebind")
    assert restored == before


# ─── 一拆二(splitStep)─────────────────────────────────────────────

async def test_e2e_split_step(client, monkeypatch):
    user = await _seed(client, "e2esplit",
                       body={"amount": 100},
                       entries=[
                           {"id": "ent-0", "name": "a",
                            "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.amount"},
                            "value": 1, "asserts": []},
                           {"id": "ent-2", "name": "b",
                            "path": {"stepIndex": 2, "source": "body",
                                     "jsonpath": "$.amount"},
                            "value": 2, "asserts": []}],
                       step_to=2)
    # 补成三步场景(拆中位步 1 → 步 2 的条目位移到 3)
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-e2esplit")
        p = deepcopy(row.payload)
        for _ in range(2):
            p["definition"]["steps"].append({
                "kind": "step", "endpoint": EP,
                "call": {"protocol": "http", "service": "fin-service",
                         "headers": {}},
                "request": {"kind": "request", "body": {"amount": 1}},
                "strategy": []})
        row.payload = p
        await s.commit()

    _patch_plate(monkeypatch)
    before, _ = await _payload("sc-e2esplit")

    out = await _submit(client, user, "sc-e2esplit", [{
        "op": "splitStep", "step": 1, "newSteps": [
            {"call": {"protocol": "http", "service": "fin-service",
                      "headers": {}},
             "request": {"kind": "request", "body": {"amount": 100}},
             "strategy": []},
            {"call": {"protocol": "http", "service": "fin-service",
                      "headers": {}},
             "request": {"kind": "request", "body": {"amount": 1}},
             "strategy": [
                 {"kind": "extract", "target": "$.code",
                  "varName": "c"}]},
        ]}])
    planned, _ = await _payload("sc-e2esplit")
    assert len(planned["definition"]["steps"]) == 4   # 3 步拆中位 → 4
    # H2:位置改写 —— 原步 2 的条目 → 步 3(+1 位移);步 0 不动
    ents = {e["id"]: e for e in planned["assertion_registry"]["entries"]}
    assert ents["ent-2"]["path"]["stepIndex"] == 3
    assert ents["ent-0"]["path"]["stepIndex"] == 0
    # R30:stepTo 已清空
    assert all(v is None for v in await _step_to("sc-e2esplit"))

    await _rollback(client, user, out["batch_id"])
    restored, _ = await _payload("sc-e2esplit")
    assert restored == before
    # 回滚不恢复调试区间(清空是随批次的既成事实;重设归编辑者)
    assert all(v is None for v in await _step_to("sc-e2esplit"))


# ─── 删除步骤(removeStep)───────────────────────────────────────────

async def test_e2e_remove_step(client, monkeypatch):
    user = await _seed(client, "e2eremovestep",
                       body={"amount": 100},
                       entries=[
                           {"id": "ent-0", "name": "a",
                            "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.amount"},
                            "value": 1, "asserts": []},
                           {"id": "ent-1", "name": "b",
                            "path": {"stepIndex": 1, "source": "body",
                                     "jsonpath": "$.amount"},
                            "value": 2, "asserts": []}],
                       step_to=1)
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-e2eremovestep")
        p = deepcopy(row.payload)
        p["definition"]["steps"].append({
            "kind": "step", "endpoint": EP,
            "call": {"protocol": "http", "service": "fin-service",
                     "headers": {}},
            "request": {"kind": "request", "body": {"amount": 1}},
            "strategy": []})
        row.payload = p
        await s.commit()

    _patch_plate(monkeypatch)
    before, _ = await _payload("sc-e2eremovestep")

    out = await _submit(client, user, "sc-e2eremovestep", [
        {"op": "removeStep", "step": 0}])
    planned, _ = await _payload("sc-e2eremovestep")
    assert len(planned["definition"]["steps"]) == 1
    ents = {e["id"]: e for e in planned["assertion_registry"]["entries"]}
    # H2:被删步骤的条目标悬空;后续步骤条目位移 -1
    assert ents["ent-0"].get("_dangling") is True
    assert ents["ent-0"]["path"]["stepIndex"] == 0
    assert ents["ent-1"]["path"]["stepIndex"] == 0
    assert not ents["ent-1"].get("_dangling")
    # R30:stepTo 清空
    assert all(v is None for v in await _step_to("sc-e2eremovestep"))

    await _rollback(client, user, out["batch_id"])
    restored, _ = await _payload("sc-e2eremovestep")
    assert restored == before


# ─── M4:force 回滚(确认放弃提交后的修改)─────────────────────────

async def test_rollback_force_after_edit(client, monkeypatch):
    user = await _seed(client, "e2eforce", body={"amount": 100})
    _patch_plate(monkeypatch)
    out = await _submit(client, user, "sc-e2eforce", [])
    # 提交后编辑(直接改 payload)
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, "sc-e2eforce")
        p = deepcopy(row.payload)
        p["definition"]["steps"][0]["request"]["body"]["edited"] = True
        row.payload = p
        await s.commit()

    r = await client.post(
        f"/api/adaptations/batches/{out['batch_id']}/rollback",
        headers=user)
    assert r.status_code == 200
    assert any(c.get("note", "").startswith("edited_beyond_batch")
               for c in r.json()["conflicts"])

    report = await _rollback(client, user, out["batch_id"], force=True)
    assert report["restored"]              # force 后按快照还原
