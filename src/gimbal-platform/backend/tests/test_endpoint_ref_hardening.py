"""外部接口登记批 X3:倒排索引两盲区硬化(设计 v1.0 §5)。

1. via_vars:值内全部 ${var.NAME} 按出现序入 JSON 列;via_var 首变量
   兼容保留;
2. 断言侧:assertion_registry 条目的 jsonpath 根段 → source=assertion
   行(锚点含 ext:;同 (step, 根段) 去重;断言悬空步骤不出行)。
"""
from __future__ import annotations

from app.services.endpoint_ref_index import (
    ASSERT_SOURCE,
    parse_refs,
    sync_scenario,
)

from .helpers import make_draft, register_and_login


def _step(ep: str, body: dict | None = None) -> dict:
    return {
        "kind": "step", "endpoint": ep,
        "call": {"protocol": "http", "service": "svc", "headers": {}},
        "request": {"kind": "request", "body": body if body is not None else {}},
        "strategy": [],
    }


def _payload(steps: list[dict], entries: list[dict] | None = None) -> dict:
    p = {"definition": {"meta": {"name": "n"}, "steps": steps}}
    if entries is not None:
        p["assertion_registry"] = {"entries": entries}
    return p


# ── via_vars(多变量全收)─────────────────────────────────────────

def test_via_vars_collects_all_in_order():
    refs, _ = parse_refs("sc-t", _payload([_step(
        "fin.a.b", {"q": "${var.a}x${var.b}", "solo": "${var.c}",
                    "plain": 1, "nested.key": "${var.d.e}"})]))
    by_field = {r.field_name: r for r in refs}
    assert by_field["q"].via_vars == ["a", "b"]
    assert by_field["q"].via_var == "a"            # 首变量兼容保留
    assert by_field["solo"].via_vars == ["c"]
    assert by_field["plain"].via_vars is None and by_field["plain"].via_var is None
    assert by_field["nested.key"].via_vars == ["d.e"]   # 变量名含点


# ── 断言侧行 ──────────────────────────────────────────────────────

def test_assertion_rows_by_step_and_root():
    entries = [
        {"id": "e1", "name": "金额",
         "path": {"stepIndex": 0, "source": "body",
                  "jsonpath": "$.data.amount"}, "value": 1, "asserts": []},
        # 同根段第二条(不同子路径)→ 去重
        {"id": "e2", "name": "币种",
         "path": {"stepIndex": 0, "source": "body",
                  "jsonpath": "$.data.currency"}, "value": "CNY",
         "asserts": []},
        # 另一根段
        {"id": "e3", "name": "状态",
         "path": {"stepIndex": 0, "source": "body",
                  "jsonpath": "$.code"}, "value": 0, "asserts": []},
        # 指向步骤 1
        {"id": "e4", "name": "二号",
         "path": {"stepIndex": 1, "source": "body",
                  "jsonpath": "$.ok"}, "value": True, "asserts": []},
    ]
    refs, _ = parse_refs("sc-t", _payload(
        [_step("fin.a.b"), _step("fin.a.c")], entries))
    assert_rows = [r for r in refs if r.source == ASSERT_SOURCE]
    # (step0, data) 一行 + (step0, code) + (step1, ok) = 3 行
    assert sorted(
        (r.step_index, r.field_name, r.endpoint_id) for r in assert_rows
    ) == [(0, "code", "fin.a.b"), (0, "data", "fin.a.b"),
          (1, "ok", "fin.a.c")]
    for r in assert_rows:
        assert r.via_var is None and r.via_vars is None


def test_assertion_rows_cover_ext_anchors_and_skip_garbage():
    entries = [
        # ext 锚点步骤的断言 → 行(external 接口影响查询可见)
        {"id": "e1", "path": {"stepIndex": 0, "source": "body",
                              "jsonpath": "$.ext_field"}, "value": 1},
        # 坏 stepIndex / 缺 path → 跳过不炸
        {"id": "e2", "path": {"stepIndex": "x", "source": "body",
                              "jsonpath": "$.y"}, "value": 1},
        {"id": "e3", "value": 1},
    ]
    refs, _ = parse_refs("sc-t", _payload(
        [_step("ext:gitlab-ext.mr-create")], entries))
    assert_rows = [r for r in refs if r.source == ASSERT_SOURCE]
    assert len(assert_rows) == 1
    assert assert_rows[0].endpoint_id == "ext:gitlab-ext.mr-create"


async def test_sync_scenario_roundtrip_with_new_columns(client):
    """sync_scenario(删旧插新)带 via_vars/断言行完整落库(真库列)。"""
    admin = await register_and_login(client, "x3_admin", "pw123456")
    draft = make_draft("sc-x3", steps=[
        _step("fin.a.b", {"q": "${var.a}x${var.b}"})])
    draft["assertion_registry"] = {"entries": [{
        "id": "e1", "name": "n",
        "path": {"stepIndex": 0, "source": "body",
                 "jsonpath": "$.data.amount"}, "value": 1, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=admin, json=draft)
    assert r.status_code in (200, 201), r.text

    from sqlalchemy import select
    from app.core import db as db_module
    from app.models.scenario_endpoint_ref import ScenarioEndpointRef
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ScenarioEndpointRef).where(
            ScenarioEndpointRef.scenario_id == "sc-x3"))).scalars().all()
    by = {(x.source, x.field_name): x for x in rows}
    assert by[("body", "q")].via_vars == ["a", "b"]
    assert by[(ASSERT_SOURCE, "data")].endpoint_id == "fin.a.b"
