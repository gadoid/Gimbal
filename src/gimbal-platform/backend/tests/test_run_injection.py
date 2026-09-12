"""run_injection — 注入条目物化纯函数 + 集成(spec v3 §3)。"""
import asyncio

import pytest

from app.services.run_injection import compose_injection_scenario, entry_issues
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)

DEF = {
    "config": {"vars": {"amount": 100, "bl_no": "BL1"}},
    "steps": [
        {"description": "下单", "request": {"body": {"amount": "${var.amount}"}},
         "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                       "operator": "eq", "expected": "0"}]},
        {"description": "查单", "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
    ],
}


def _body_of(steps):
    return lambda si: (steps[si].get("request") or {}).get("body")


def _targets_of(steps):
    def _t(si: int) -> set:
        return {st.get("target") for st in (steps[si].get("strategy") or [])
                if isinstance(st, dict) and st.get("kind") == "assertion"}
    return _t


def test_assign_appends_strategy_without_touching_vars():
    """path 直补(spec v3 §3):Assign 追加进 steps[si].strategy,config.vars
    零触碰(与数据集 vars 注入解耦);源 definition 零污染。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": []}
    out = compose_injection_scenario(DEF, entry)
    assert out["config"]["vars"]["amount"] == 100            # vars 不动
    st = out["steps"][0]["strategy"]
    assert st[-1] == {"kind": "assign", "source": -1, "target": "$.request_body.amount"}
    assert DEF["steps"][0]["strategy"] == [{"kind": "assertion", "target": "$.response_body.code",
                                            "operator": "eq", "expected": "0"}]   # 源零污染


def test_assign_value_passthrough_no_coerce():
    """value 原样覆写不 coerce(str/bool/嵌套 dict 都不转形)。"""
    for v in ["-1", True, {"a": [1, 2]}, None]:
        entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
                 "value": v, "asserts": []}
        out = compose_injection_scenario(DEF, entry)
        assert out["steps"][0]["strategy"][-1]["source"] == v


def test_override_and_append_patch_keep_v2_semantics():
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": [
                 {"stepIndex": 0, "target": "$.response_body.code", "operator": "eq",
                  "expected": "400", "mode": "override"},
                 {"stepIndex": 1, "target": "$.response_body.msg", "operator": "contains",
                  "expected": "金额非法", "mode": "append"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "400"    # override 改 expected
    assert {"kind": "assertion", "target": "$.response_body.msg",
            "operator": "contains", "expected": "金额非法"} in out["steps"][1]["strategy"]


def test_dangling_path_and_unmatched_override_skipped():
    """悬空项静默跳过(dispatcher 已过滤,双保险):越界 stepIndex 不落
    Assign;无匹配 override 不动既有断言。issues 同构断言四种。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
             "value": 1, "asserts": [
                 {"stepIndex": 0, "target": "$.nope", "operator": "eq", "expected": "1", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "0"     # 无匹配 override 不动
    assert all(st.get("kind") != "assign" for s in out["steps"] for st in s["strategy"])
    issues = entry_issues(entry, 2, _body_of(DEF["steps"]), _targets_of(DEF["steps"]))
    assert {"kind": "step-oob", "stepIndex": 9} in issues
    assert {"kind": "override-no-match", "stepIndex": 0, "target": "$.nope"} in issues


def test_entry_issues_path_unresolvable_and_legacy():
    body_of = _body_of(DEF["steps"])
    targets = _targets_of(DEF["steps"])
    ghost = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.ghost"},
             "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.ghost"} in \
        entry_issues(ghost, 2, body_of, targets)
    # 容器前缀可解析:叶子 $.amount 在树上,$. 不在
    ok = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
          "value": 1, "asserts": []}
    assert entry_issues(ok, 2, body_of, targets) == []
    # str body 步骤无可索引字段 → 一律不可解析(spec v3 §2)
    str_body = [{"request": {"body": "raw"}}]
    s = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.x"},
         "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.x"} in \
        entry_issues(s, 2, _body_of(str_body), targets)
    # v2 旧形状(无 path)→ legacy-entry 全量 issue(spec v3 §8)
    legacy = {"id": "inj-old", "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
              "injection": [{"varName": "amount", "value": "-1"}], "asserts": []}
    assert entry_issues(legacy, 2, body_of, targets) == [{"kind": "legacy-entry"}]


# ── dispatcher 集成(spec v3 §3:Assign 直补落 case.json;skip 链)────
# 骨架不变:建场景(assertion_registry 注入)→ POST /api/runs → 断言
# case 数 / case.json patch / rows 回放。

_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:回放只读本测试写入的行(镜像
    test_execution_rows.py 的做法,理由见其注释)。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


async def test_dispatcher_fans_out_injection_entries(
    client, plate_mock: PlateMock, monkeypatch
):
    """选中 1 活条目(+ 死条目 + 旧版条目)且无数据集 → case 数 = 活条目数
    ×nRuns;死/旧条目 skip 不炸;case.json 的 steps[0].strategy 已追加
    Assign 直补($.request_body.amount)且 vars 未被触碰;rows 回放含
    injectionId。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[
            {"id": "s1", "request": {"body": {"amount": "${var.amount}"}},
             "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                           "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    draft["assertion_registry"] = {"entries": [
        # 活条目:Assign 直补(value -1,原样不 coerce)+ override patch('400')
        {"id": "inj-live", "name": "金额非法",
         "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
         "value": -1,
         "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                      "operator": "eq", "expected": "400", "mode": "override"}]},
        # 死条目:path stepIndex 越界 → entry_issues 判死,skip 不炸
        {"id": "inj-dead", "name": "越界死条目",
         "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
         "value": 1,
         "asserts": [{"stepIndex": 9, "target": "$.x", "operator": "eq",
                      "expected": "1", "mode": "append"}]},
        # 旧版条目(v2 anchor+injection 形状)→ legacy-entry 全量 issue → skip
        {"id": "inj-old", "name": "旧版条目",
         "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount", "varName": "amount"},
         "injection": [{"varName": "amount", "value": "-1"}], "asserts": []},
    ]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    # echo:converted 原样回灌 → case.json 保留 patched strategy 可断言
    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-live", "inj-dead", "inj-old"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 2)
    assert len(cases) == 2                       # 1 活条目 × nRuns=2;死/旧 skip
    for case in cases:
        st = case["steps"][0]["strategy"]
        assert st[0]["expected"] == "400"                          # override patch
        assert {"kind": "assign", "source": -1,
                "target": "$.request_body.amount"} in st           # Assign 直补
        assert case["config"]["vars"]["amount"] == 100             # vars 未触碰

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 2
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert all(row["injectionId"] == "inj-live" for row in rows)
    assert all(row["datasetId"] is None for row in rows)
