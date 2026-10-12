"""W22/RS4b:「应用到同类步骤」批量应用(§5.4)。

单场景内结构级 op 定好一步后,按锚点端点展开到同类步骤;submit-suite
的同类聚合是跨场景面,本文件钉单场景面:

1. replaceEndpoint + applyToSimilar:所有锚定旧端点的步骤一并替换,
   非同类步骤不动;
2. removeStep + applyToSimilar:同类步骤全部删除,索引重定位正确
   (逐 pass 重扫,不预计算);
3. 非收敛保护:newSteps 仍锚原端点的 splitStep 不无限展开;
4. 缺省(applyToSimilar=false)行为不变 —— 只有 op 点名的那一步。
"""
from __future__ import annotations

from copy import deepcopy

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import adaptation_service, plate_client, scenario_store

from .helpers import make_draft, register_and_login

EP_OLD = "fin.settlement.create"
EP_NEW = "fin.settlement.v2create"
EP_OTHER = "fin.order.query"

TARGET_FULL = {"id": EP_NEW, "request": {"declarations": [
    {"name": "amount", "path": "$.amount", "type": "number",
     "state": "form", "required": True},
]}, "responses": {"200": {"declarations": [
    {"name": "code", "path": "$.code", "type": "string",
     "state": "form"}]}}}
OTHER_FULL = {"id": EP_OTHER, "request": {"declarations": [
    {"name": "q", "path": "$.q", "type": "number",
     "state": "form", "required": False},
]}}
OLD_FULL = {"id": EP_OLD, "request": {"declarations": [
    {"name": "amount", "path": "$.amount", "type": "number",
     "state": "form", "required": True},
]}}


def _steps(n_old: int) -> list[dict]:
    steps = []
    for i in range(n_old):
        steps.append({
            "kind": "step", "endpoint": EP_OLD,
            "call": {"protocol": "http", "service": "fin-service",
                     "headers": {}},
            "request": {"kind": "request", "body": {"amount": i}},
            "strategy": [],
        })
        steps.append({   # 穿插非同类步骤:不该被动
            "kind": "step", "endpoint": EP_OTHER,
            "call": {"protocol": "http", "service": "fin-service",
                     "headers": {}},
            "request": {"kind": "request", "body": {"q": i}},
            "strategy": [],
        })
    return steps


async def _seed(client, name: str, steps: list[dict]) -> dict:
    user = await register_and_login(client, name, "pw123456")
    draft = make_draft(f"sc-{name}", steps=deepcopy(steps), system=["fin"])
    draft["definition"]["meta"]["plate"] = {"fin": "1.0#1"}
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(draft),
            owner=name, owner_id=1)
        await s.commit()
    return user


def _patch_plate(monkeypatch):
    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}

    async def fake_full_at(eid, ref):
        if eid == EP_NEW:
            return deepcopy(TARGET_FULL)
        if eid == EP_OTHER:
            return deepcopy(OTHER_FULL)
        if eid == EP_OLD:
            return deepcopy(OLD_FULL)
        return None

    monkeypatch.setattr(plate_client, "convert", fake_convert)
    monkeypatch.setattr(plate_client, "get_endpoint_full_at", fake_full_at)


async def _submit(client, user, sid, ops, **extra):
    r = await client.post("/api/adaptations/submit", headers=user, json={
        "scenarioId": sid, "ops": ops, "targetRevision": "1.0#2",
        "saveMode": "direct", **extra})
    return r


async def _payload(sid):
    async with db_module.SessionLocal() as s:
        row = await scenario_store.get_row(s, sid)
        return deepcopy(row.payload)


async def test_replace_endpoint_applies_to_similar_steps(client, monkeypatch):
    _patch_plate(monkeypatch)
    user = await _seed(client, "sim1", _steps(3))   # 3×旧端点 + 3×其他
    r = await _submit(client, user, "sc-sim1", [{
        "op": "replaceEndpoint", "step": 0, "endpoint": EP_NEW,
        "targetRevision": "1.0#2"}], applyToSimilar=True)
    assert r.status_code == 200, r.text
    assert r.json()["similar_applied"] == 2      # 除点名步外还有 2 个同类

    payload = await _payload("sc-sim1")
    steps = payload["definition"]["steps"]
    assert [st["endpoint"] for st in steps] == (
        [EP_NEW, EP_OTHER] * 3)                  # 旧端点全替换,其他不动
    # 场景自有字段保留(替换不丢 service/headers)
    assert steps[0]["call"]["service"] == "fin-service"


async def test_without_flag_only_named_step_changes(client, monkeypatch):
    _patch_plate(monkeypatch)
    user = await _seed(client, "sim2", _steps(2))
    r = await _submit(client, user, "sc-sim2", [{
        "op": "replaceEndpoint", "step": 0, "endpoint": EP_NEW,
        "targetRevision": "1.0#2"}])
    assert r.status_code == 200, r.text
    assert r.json()["similar_applied"] == 0
    payload = await _payload("sc-sim2")
    ends = [st["endpoint"] for st in payload["definition"]["steps"]]
    assert ends == [EP_NEW, EP_OTHER, EP_OLD, EP_OTHER]


async def test_remove_step_relocates_indexes_per_pass(client, monkeypatch):
    _patch_plate(monkeypatch)
    user = await _seed(client, "sim3", _steps(3))
    r = await _submit(client, user, "sc-sim3", [{
        "op": "removeStep", "step": 0}], applyToSimilar=True)
    assert r.status_code == 200, r.text
    assert r.json()["similar_applied"] == 2
    payload = await _payload("sc-sim3")
    ends = [st["endpoint"] for st in payload["definition"]["steps"]]
    assert ends == [EP_OTHER] * 3               # 同类全删,其他保留


async def test_non_convergent_split_stops_after_one_pass():
    """splitStep 的 newSteps 仍锚原端点 → 锚点计数不降,不无限展开。"""
    payload = {"definition": {"meta": {"system": ["fin"]}, "steps": [
        {"kind": "step", "endpoint": EP_OLD,
         "call": {"protocol": "http", "service": "s", "headers": {}},
         "request": {"kind": "request", "body": {}}, "strategy": []},
        {"kind": "step", "endpoint": EP_OLD,
         "call": {"protocol": "http", "service": "s", "headers": {}},
         "request": {"kind": "request", "body": {}}, "strategy": []},
    ]}}
    ops = [{
        "op": "splitStep", "step": 0,
        "newSteps": [
            {"endpoint": EP_OLD, "call": {"protocol": "http",
                                          "service": "s"},
             "request": {"kind": "request", "body": {"a": 1}},
             "strategy": []},
            {"endpoint": EP_OLD, "call": {"protocol": "http",
                                          "service": "s"},
             "request": {"kind": "request", "body": {"b": 2}},
             "strategy": []},
        ]}]
    expanded, applied = adaptation_service._expand_ops_to_similar(
        payload, ops)
    assert applied == 1                          # 第二 pass 后计数未降即停
    assert len(expanded) == 2
