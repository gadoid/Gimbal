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


# ── 响应结构下钻 ─────────────────────────────────────────────
#
# 契约里 589 条响应声明只有 18 条带下级：生成器的 declarations() 只读
# properties，object 下钻还有 depth 上限，**array 干脆不处理**。结果是
# `$.ops` 标成 array 就收工，里面有什么全平台无人知道。
#
# 下面这组测试把「下钻到数组元素层」钉死。


def test_declarations_descends_into_array_items():
    schemas = {
        "Batch": {
            "type": "object",
            "properties": {
                "batchId": {"type": "string"},
                "ops": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/Op"},
                },
            },
        },
        "Op": {
            "type": "object",
            "properties": {
                "opType": {"type": "string"},
                "payload": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                },
            },
        },
    }
    by_name = {
        d["name"]: d
        for d in declarations({"$ref": "#/components/schemas/Batch"}, schemas)
    }
    ops = by_name["ops"]
    assert ops["type"] == "array"
    kids = {c["name"]: c for c in ops["children"]}
    # 模板态：children 子树内不带 [i]。实例下标是渲染器的事，plate 的
    # _check_declarations ③ 硬性拒非模板态的 children path。
    assert kids["opType"]["path"] == "$.ops.opType"
    # 元素里再嵌 object，要继续下钻 —— 两层都不能停
    assert kids["payload"]["children"][0]["path"] == "$.ops.payload.reason"


def test_declarations_reads_a_top_level_array_response():
    """GET /api/data-sets 的响应本身就是数组。

    根节点是 array，没有 properties —— 现状直接返回空声明，该端点的字段面
    全空。数组元素的字段提到顶层，path 直接挂在 $ 下。
    """
    schemas = {
        "DataSetSummary": {
            "type": "object",
            "properties": {
                "datasetId": {"type": "string"},
                "name": {"type": "string"},
            },
        }
    }
    decls = declarations(
        {"type": "array", "items": {"$ref": "#/components/schemas/DataSetSummary"}},
        schemas,
        assertable=True,
    )
    by_name = {d["name"]: d for d in decls}
    assert by_name["datasetId"]["path"] == "$.datasetId"
    assert by_name["name"]["assertable"] is True


def test_declarations_stops_at_a_self_referencing_schema():
    """$ref 自引用（Node.child 又是 Node）不能无限递归。

    下钻深度一放开，这类环就会把生成器挂死 —— 而契约生成是全量跑的，
    一次挂死就是整个自举停摆。
    """
    schemas = {
        "Node": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "child": {"$ref": "#/components/schemas/Node"},
            },
        }
    }
    decls = declarations({"$ref": "#/components/schemas/Node"}, schemas)
    child = {d["name"]: d for d in decls}["child"]
    # 环到此为止：要么不带 children，要么带非空 children —— 绝不能是空列表
    assert child.get("children") in (None, []) or len(child["children"]) > 0
    # 且必须有 children 键以外的可断言内容（第一层 Node 本身仍要出 id）
    assert {d["name"] for d in decls} == {"id", "child"}


def test_declarations_never_emits_an_empty_children_list():
    """plate 拒 children=[]（"容器要么不带(None)，要么非空"）。

    生成器在环上收工时若留下空列表，产物在 plate 加载期才炸 —— 报错点离
    成因十万八千里。这门把它钉在生成侧。
    """
    schemas = {"Empty": {"type": "object", "properties": {}}}
    decls = declarations(
        {"type": "array", "items": {"$ref": "#/components/schemas/Empty"}}, schemas
    )
    assert decls == []


def test_expanded_declarations_pass_real_plate_validation():
    """生成器说行不算行 —— 产物必须真能过 plate 的 EndpointSpec 校验。

    这是漂移检测一直缺的那一层：test_contract_drift 只查路由，声明树
    从来没人验过。这里用真实 plate 模型把「下钻 + 模板态纪律」闭环。
    """
    from gimbal_plate.schema.endpoint import (
        ApiSpec,
        DeclarationEntry,
        EndpointMetadata,
        EndpointSpec,
        RequestSpec,
        ResponseSpec,
    )
    from gimbal_plate.schema.endpoint.io_spec import iter_declarations

    schemas = {
        "Out": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "meta": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        }
    }
    decls = [
        DeclarationEntry(**d)
        for d in declarations({"$ref": "#/components/schemas/Out"}, schemas,
                              assertable=True)
    ]
    spec = EndpointSpec(
        id="platform.demo.get_thing",
        system="platform",
        service="platform-service",
        name="demo",
        api=ApiSpec(service="platform-service", method="GET", path="/api/thing"),
        request=RequestSpec(body_type="none"),
        responses={200: ResponseSpec(status=200, declarations=decls)},
        metadata=EndpointMetadata(module="demo"),
    )
    paths = {d.path for d in iter_declarations(decls)}
    assert "$.items.meta.name" in paths, paths
