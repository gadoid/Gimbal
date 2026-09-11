"""Tests for the V3 container schema (definition + orchestration)."""
from __future__ import annotations

from app.schemas.scenario_composer import (
    ScenarioDraft, Orchestration, StepOrchestration,
)


def test_draft_accepts_definition_dict_plus_orchestration() -> None:
    """definition is a free-form plate dict; orchestration is the platform side."""
    draft = ScenarioDraft.model_validate({
        "definition": {
            "kind": "scenario",
            "scenarioId": "sc-order-create",
            "meta": {"name": "x", "system": ["fin"]},
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    assert draft.definition["scenarioId"] == "sc-order-create"
    assert draft.orchestration.steps == []


def test_step_orchestration_defaults() -> None:
    s = StepOrchestration.model_validate({})
    assert s.enabled is True
    assert s.name == ""


def test_draft_serializes_camel_case() -> None:
    draft = ScenarioDraft.model_validate({
        "definition": {"scenarioId": "sc-x", "meta": {"name": "x"}, "config": {},
                       "resource": {}, "steps": []},
        "orchestration": {"steps": [{"name": "登录", "enabled": False}],
                          "resourceMeta": {"mock-1": "默认 mock"}},
    })
    out = draft.model_dump(by_alias=True, mode="json")
    assert out["orchestration"]["resourceMeta"] == {"mock-1": "默认 mock"}
    assert out["orchestration"]["steps"][0]["enabled"] is False


from datetime import datetime

from app.routers.scenarios import _draft_to_full_scenario_dict


def test_draft_to_full_passes_definition_through() -> None:
    """definition is plate-shaped; translator only adds plate-required defaults."""
    draft = ScenarioDraft.model_validate({
        "definition": {
            "scenarioId": "sc-x",
            "meta": {"name": "x", "system": ["fin"], "createTime": "2026-01-01T00:00:00Z"},
            "config": {"timePolicy": {"kind": "record"}, "vars": {"a": 1}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    out = _draft_to_full_scenario_dict(draft, owner="alice")
    # definition fields pass through untouched
    assert out["scenarioId"] == "sc-x"
    assert out["config"]["vars"] == {"a": 1}
    assert out["meta"]["name"] == "x"
    # plate-required defaults filled
    assert out["kind"] == "scenario"
    assert out["meta"]["createTime"] == "2026-01-01T00:00:00Z"  # not overwritten
    assert out["meta"]["requirementRef"] == []
    # orchestration never leaks into plate payload
    assert "orchestration" not in out
    assert "caseMeta" not in out


def test_draft_to_full_fills_missing_create_time() -> None:
    draft = ScenarioDraft.model_validate({
        "definition": {
            "scenarioId": "sc-y",
            "meta": {"name": "y", "system": ["fin"]},
            "config": {}, "resource": {}, "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    out = _draft_to_full_scenario_dict(draft, owner="bob")
    assert out["meta"]["createTime"]  # some ISO timestamp filled
    assert out["meta"]["owner"] == "bob"  # owner filled from router


# ── assertion_registry 第三键(spec v2 §3)───────────────────────────
# API 层 roundtrip:PUT(重铸 payload)不丢条目、GET /draft 原样回读、
# 旧客户端缺省回落空 dict。骨架仿 test_run_schemes_endpoint 的
# 「建场景 + GET /draft → PUT 回写」用例(共享 helpers.make_draft)。
from httpx import AsyncClient

from .helpers import make_draft as _minimal_draft
from .helpers import register_and_login as _register_and_login


async def _create_scenario(client: AsyncClient, headers: dict) -> str:
    """POST 最小合法 draft 建场景(仿 run_schemes 的 _saved_scenario)。"""
    r = await client.post("/api/scenarios", headers=headers,
                          json=_minimal_draft())
    assert r.status_code in (200, 201), r.text
    return "sc-test"                    # make_draft 缺省 scenario_id


async def test_draft_roundtrips_assertion_registry(client):
    """spec v2 §3:assertion_registry 与 orchestration 同级,create/update/draft 全链携带。"""
    entry = {"entries": [{
        "id": "inj-1", "name": "金额为负",
        "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount",
                   "varName": "amount"},
        "injection": [{"varName": "amount", "value": "-1"}],
        "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                     "operator": "eq", "expected": "400", "mode": "override"}],
    }]}
    # 先注册一次性 admin 吃掉 bootstrap,再拿普通成员 headers(仿 _member)
    await _register_and_login(client, "admin0", "admin0pass123")
    owner_headers = await _register_and_login(client, "bob")
    sid = await _create_scenario(client, owner_headers)
    draft = _minimal_draft(sid)
    draft["assertion_registry"] = entry
    resp = await client.put(f"/api/scenarios/{sid}", json=draft,
                            headers=owner_headers)
    assert resp.status_code == 200
    # GET draft 原样回读
    out = (await client.get(f"/api/scenarios/{sid}/draft",
                            headers=owner_headers)).json()
    assert out["assertion_registry"] == entry
    # 不带 registry 的 PUT(旧客户端)→ 字段回落空 dict,不炸不 422
    draft.pop("assertion_registry")
    resp2 = await client.put(f"/api/scenarios/{sid}", json=draft,
                             headers=owner_headers)
    assert resp2.status_code == 200
    out2 = (await client.get(f"/api/scenarios/{sid}/draft",
                             headers=owner_headers)).json()
    assert out2["assertion_registry"] == {}

