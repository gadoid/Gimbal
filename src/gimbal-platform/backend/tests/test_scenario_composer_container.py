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
    # caseMeta optional
    assert draft.case_meta is None


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

