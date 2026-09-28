import json

import pytest

from gimbal_bootstrap.contract_gen import (
    build_specs,
    check_collisions,
    declarations,
    derive_id,
    fetch_openapi,
)


def test_derive_id_is_deterministic_and_unique():
    assert derive_id("GET", "/api/health") == "platform.health.get_root"
    assert derive_id("POST", "/api/auth/register") == "platform.auth.post_register"
    assert derive_id("GET", "/api/scenarios/{scenario_id}") == (
        "platform.scenarios.get_by_scenario_id"
    )
    # 同 path 不同 method 不撞
    assert derive_id("GET", "/api/scenarios") != derive_id("POST", "/api/scenarios")


def test_derive_id_respects_plate_charset_and_length():
    import re

    long_path = "/api/" + "/".join(f"seg{i}" for i in range(12))
    eid = derive_id("GET", long_path)
    assert re.match(r"^[a-z][a-z0-9_.\-]{1,63}$", eid), eid
    assert len(eid) <= 64


def test_declarations_recurses_object_and_marks_response_assertable():
    schemas = {
        "Item": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "nested": {"type": "object", "properties": {"code": {"type": "number"}}},
            },
        }
    }
    decls = declarations({"$ref": "#/components/schemas/Item"}, schemas, assertable=True)
    by_name = {d["name"]: d for d in decls}
    assert by_name["id"]["path"] == "$.id"
    assert by_name["id"]["type"] == "integer"
    assert by_name["id"]["assertable"] is True
    assert by_name["nested"]["children"][0]["path"] == "$.nested.code"


def test_declarations_drops_illegal_names_and_warns():
    schemas = {
        "X": {
            "type": "object",
            "properties": {"ok": {"type": "string"}, "bad-name": {"type": "string"}},
        }
    }
    warns: list[str] = []
    decls = declarations({"$ref": "#/components/schemas/X"}, schemas, warnings=warns)
    assert [d["name"] for d in decls] == ["ok"]
    assert warns and "bad-name" in warns[0]


def test_declarations_falls_back_to_string_for_anyof():
    """可选字段（anyOf string|null）必须落 string，不能因无 type 而崩。"""
    schemas = {
        "Outer": {
            "type": "object",
            "properties": {
                "note": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "count": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
        }
    }
    by_name = {d["name"]: d for d in declarations(
        {"$ref": "#/components/schemas/Outer"}, schemas
    )}
    assert by_name["note"]["type"] == "string"
    assert by_name["count"]["type"] == "integer"


def test_build_specs_synthesizes_200_for_204_only_endpoint():
    """Review Focus #2：只回 204 的端点没有响应体，必须补 200 占位。"""
    openapi = {
        "paths": {
            "/api/things/{id}": {
                "delete": {"responses": {"204": {"description": "No Content"}}}
            }
        }
    }
    specs, _ = build_specs(openapi)
    assert set(specs[0]["responses"]) >= {"200"}
    assert specs[0]["responses"]["200"]["declarations"] == []
    assert specs[0]["metadata"]["business_notes"]


def test_build_specs_never_returns_empty_responses():
    openapi = {"paths": {"/api/x": {"get": {"responses": {}}}}}
    specs, _ = build_specs(openapi)
    assert "200" in specs[0]["responses"]


def test_build_specs_marks_auth_free_paths():
    openapi = {
        "paths": {
            "/api/health": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/api/scenarios": {"get": {"responses": {"200": {"description": "ok"}}}},
        }
    }
    specs, _ = build_specs(openapi)
    auth = {e["api"]["path"]: e["api"]["auth"] for e in specs}
    assert auth == {"/api/health": "none", "/api/scenarios": "bearer"}


def test_declarations_unions_top_level_anyof():
    """GET /api/scenarios 的响应是 anyOf[ScenarioListOut, ScenarioOptionsOut]
    —— 两条路都合法，顶层必须并集，否则声明树是空的。"""
    schemas = {
        "ListOut": {"type": "object", "properties": {
            "items": {"type": "array"}, "total": {"type": "integer"}}},
        "OptionsOut": {"type": "object", "properties": {
            "options": {"type": "array"}, "total": {"type": "integer"}}},
    }
    decls = declarations({"anyOf": [
        {"$ref": "#/components/schemas/ListOut"},
        {"$ref": "#/components/schemas/OptionsOut"},
    ]}, schemas)
    assert [d["name"] for d in decls] == ["items", "options", "total"]


def test_declarations_warns_when_union_branches_disagree_on_type():
    schemas = {
        "A": {"type": "object", "properties": {"v": {"type": "string"}}},
        "B": {"type": "object", "properties": {"v": {"type": "integer"}}},
    }
    warns: list[str] = []
    decls = declarations({"anyOf": [
        {"$ref": "#/components/schemas/A"}, {"$ref": "#/components/schemas/B"},
    ]}, schemas, warnings=warns)
    assert decls[0]["type"] == "string"
    assert warns and "v" in warns[0]


def test_check_collisions_rejects_duplicate_route():
    """Review Focus #3：plate by_route 后写覆盖，生成期必须挡住。"""
    specs = [
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
        {"id": "platform.a.two", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
    ]
    with pytest.raises(ValueError, match="by_route"):
        check_collisions(specs)


def test_check_collisions_rejects_duplicate_id():
    specs = [
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/y"}},
    ]
    with pytest.raises(ValueError, match="id 重复"):
        check_collisions(specs)


def test_fetch_openapi_falls_back_to_in_process_when_http_fails():
    """后端跑着旧代码时 /openapi.json 是 500 —— 别让契约生成卡在重启上。"""
    spec = fetch_openapi("http://127.0.0.1:1", allow_inprocess_fallback=True)
    assert len(spec["paths"]) > 50
    assert "RegisterIn" in spec["components"]["schemas"]
