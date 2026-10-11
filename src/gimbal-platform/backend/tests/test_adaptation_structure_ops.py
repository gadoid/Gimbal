"""RS4b 结构级 op 单元回归(评审 2026-10-12 修复轮)。

锁定四个此前出错的语义:
  * mergeSteps 支持不相邻索引 —— 旧实现按连续段替换,合并 0/2 会
    误删 1、留下 2;
  * replaceEndpoint 保留旧步骤的 request/strategy/description
    (整步替换会丢请求体/提取变量,下游引用断链),fieldMapping 经
    renameField 管道落到 body/注入条目/字段状态;
  * replaceEndpoint 跨系统不默认写 working(宁缺毋滥:缺省留给保存
    检查的 version_undeclared 拦,不猜);
  * splitStep/insertStep 的 call 由后端构造(继承旧步骤场景自有
    字段/接目录 service),不再要求前端拼 call。
"""
from __future__ import annotations

from app.services.adaptation_ops import apply_to_definition


def _defn(n_steps: int = 4) -> dict:
    return {
        "kind": "scenario",
        "meta": {"name": "t", "system": ["fin"], "plate": {"fin": "1.0#1"}},
        "steps": [
            {"kind": "step", "endpoint": "fin.a",
             "call": {"kind": "call", "service": "fin-service",
                      "headers": {"X-Keep": "1"}},
             "request": {"kind": "request", "body": {f"f{i}": i}},
             "strategy": [], "description": f"step-{i}"}
            for i in range(n_steps)
        ],
        "config": {},
        "resource": {},
    }


def _payload_of(definition: dict, entries: list | None = None,
                field_states: dict | None = None) -> dict:
    return {"definition": definition,
            "assertion_registry": {"entries": entries or []},
            "ui": {"fieldStates": field_states or {}}}


def test_merge_steps_non_contiguous():
    """合并 0/2(共 4 步):结果 3 步,误删 1/留下 2 的旧缺陷不得复现。"""
    d = _defn(4)
    p = _payload_of(d)
    apply_to_definition(d, {
        "op": "mergeSteps", "step": 0, "steps": [0, 2],
        "endpoint": "fin.merged", "mergedStep": {},
        "_payload": p,
    })
    steps = d["steps"]
    assert len(steps) == 3
    assert steps[0]["endpoint"] == "fin.merged"
    assert steps[1]["description"] == "step-1"     # 未被合并的 1 保留
    assert steps[2]["description"] == "step-3"     # 3 前移到 2
    # 合并步继承首步骤的 call 场景自有字段与请求体
    assert steps[0]["call"]["service"] == "fin-service"
    assert steps[0]["call"]["headers"] == {"X-Keep": "1"}
    assert steps[0]["request"]["body"] == {"f0": 0}


def test_merge_steps_registry_rewrite():
    """注入条目 stepIndex 随合并不连续索引改写:2 → 合并位,3 → 前移。"""
    d = _defn(4)
    entries = [
        {"id": "e0", "path": {"stepIndex": 2, "source": "body",
                              "jsonpath": "$.f2"}, "value": 1, "asserts": []},
        {"id": "e1", "path": {"stepIndex": 3, "source": "body",
                              "jsonpath": "$.f3"}, "value": 2, "asserts": []},
    ]
    p = _payload_of(d, entries=entries)
    apply_to_definition(d, {
        "op": "mergeSteps", "step": 0, "steps": [0, 2],
        "endpoint": "fin.merged", "_payload": p,
    })
    by_id = {e["id"]: e for e in p["assertion_registry"]["entries"]}
    assert by_id["e0"]["path"]["stepIndex"] == 0    # 被合并的 2 → 合并步
    assert by_id["e1"]["path"]["stepIndex"] == 2    # 3 前移


def test_replace_endpoint_preserves_step_semantics():
    """替换接口保留 request/strategy/description;call 只留场景自有字段。"""
    d = _defn(1)
    d["steps"][0]["strategy"] = [
        {"kind": "extract", "target": "$.code", "varName": "c"}]
    p = _payload_of(d)
    apply_to_definition(d, {
        "op": "replaceEndpoint", "step": 0, "endpoint": "fin.b",
        "_payload": p,
    })
    s = d["steps"][0]
    assert s["endpoint"] == "fin.b"
    assert s["request"]["body"] == {"f0": 0}            # 请求体不丢
    assert s["strategy"][0]["varName"] == "c"           # 提取变量不丢
    assert s["description"] == "step-0"
    assert s["call"]["service"] == "fin-service"        # 场景自有字段保留
    assert "protocol" not in s["call"]                  # 不新增派生字段


def test_replace_endpoint_field_mapping_applied():
    """fieldMapping 经 renameField 管道:body 键、注入条目、字段状态同改。"""
    from app.services.adaptation_service import _apply_ops_to_payload
    d = _defn(1)
    d["steps"][0]["request"]["body"] = {"order_id": "A1"}
    entries = [{"id": "e0", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.order_id.x"},
                "value": 1, "asserts": []}]
    payload = _payload_of(d, entries=entries,
                          field_states={"0": {"$.order_id": "form"}})
    _apply_ops_to_payload(payload, [{
        "op": "replaceEndpoint", "step": 0, "endpoint": "fin.b",
        "fieldMapping": {"order_id": "orderId"},
    }])
    s = payload["definition"]["steps"][0]
    assert "order_id" not in s["request"]["body"]
    assert s["request"]["body"]["orderId"] == "A1"
    e0 = payload["assertion_registry"]["entries"][0]
    assert e0["path"]["jsonpath"] == "$.orderId.x"
    fs = payload["ui"]["fieldStates"]["0"]
    assert list(fs.keys()) == ["$.orderId"]


def test_replace_endpoint_cross_system_revision():
    """跨系统替换:带 targetRevision 才写 meta.plate;不默认 working。"""
    d = _defn(1)
    p = _payload_of(d)
    apply_to_definition(d, {
        "op": "replaceEndpoint", "step": 0, "endpoint": "log.audit.push",
        "_payload": p,
    })
    assert "log" not in d["meta"]["plate"]             # 不猜 working

    apply_to_definition(d, {
        "op": "replaceEndpoint", "step": 0, "endpoint": "log.audit.push",
        "targetRevision": "2.0#3", "_payload": p,
    })
    assert d["meta"]["plate"]["log"] == "2.0#3"


def test_split_and_insert_build_call_server_side():
    """拆分/插入:call 由后端构造(继承旧步字段/接 service),前端不拼。"""
    d = _defn(2)
    p = _payload_of(d)
    apply_to_definition(d, {
        "op": "splitStep", "step": 0, "newSteps": [
            {"endpoint": "fin.a", "body": {"x": 1}},
            {"endpoint": "fin.a", "service": "other-svc", "body": {}},
        ], "_payload": p,
    })
    s0, s1 = d["steps"][0], d["steps"][1]
    assert s0["endpoint"] == "fin.a"
    assert s0["call"]["service"] == "fin-service"       # 继承旧步
    assert s0["call"]["headers"] == {"X-Keep": "1"}
    assert s0["request"]["body"] == {"x": 1}            # body → request.body
    assert s1["call"]["service"] == "other-svc"         # 显式 service 优先
    assert "protocol" not in s0["call"]

    apply_to_definition(d, {
        "op": "insertStep", "step": 0, "at": 1,
        "newStep": {"endpoint": "fin.auth", "service": "auth-svc"},
        "_payload": p,
    })
    ins = d["steps"][1]
    assert ins["endpoint"] == "fin.auth"
    assert ins["call"] == {"kind": "call", "headers": {},
                           "service": "auth-svc"}
    assert ins["request"] == {"kind": "request", "body": {}}
