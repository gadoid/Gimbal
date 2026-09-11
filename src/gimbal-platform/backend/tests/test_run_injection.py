"""run_injection — 注入条目物化纯函数(spec v2 §8)。"""
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


def test_injection_overrides_baseline_vars_without_mutation():
    entry = {"id": "inj-1", "injection": [{"varName": "amount", "value": "-1"}], "asserts": []}
    out = compose_injection_scenario(DEF, entry)
    assert out["config"]["vars"]["amount"] == "-1"  # 原样覆写不 coerce(基线 int,条目值 str)
    assert DEF["config"]["vars"]["amount"] == 100          # 源零污染
    assert out["config"]["vars"]["bl_no"] == "BL1"          # 基线保留


def test_override_patches_matching_assert_expected():
    entry = {"id": "inj-1", "injection": [], "asserts": [
        {"stepIndex": 0, "target": "$.response_body.code", "operator": "eq",
         "expected": "400", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    st = out["steps"][0]["strategy"]
    assert len(st) == 1
    assert st[0]["expected"] == "400"


def test_append_adds_new_assertion():
    entry = {"id": "inj-1", "injection": [], "asserts": [
        {"stepIndex": 1, "target": "$.response_body.msg", "operator": "contains",
         "expected": "金额非法", "mode": "append"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][1]["strategy"] == [{"kind": "assertion", "target": "$.response_body.msg",
                                            "operator": "contains", "expected": "金额非法"}]


def test_dangling_step_and_unmatched_override_skipped():
    entry = {"id": "inj-1", "injection": [{"varName": "ghost", "value": "1"}], "asserts": [
        {"stepIndex": 9, "target": "$.x", "operator": "eq", "expected": "1", "mode": "append"},
        {"stepIndex": 0, "target": "$.nope", "operator": "eq", "expected": "1", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "0"   # 无匹配 override 不动
    assert out["steps"][1]["strategy"] == []                     # 越界 append 不落
    issues = entry_issues(entry, 2, {"amount"}, lambda si: {"$.response_body.code"} if si == 0 else set())
    assert {"kind": "step-oob", "stepIndex": 9} in issues
    assert {"kind": "var-unknown", "varName": "ghost"} in issues
    assert {"kind": "override-no-match", "stepIndex": 0, "target": "$.nope"} in issues


# ── dispatcher 集成(注入族 fan-out + 行可观测,spec v2 §8)────────
# 仿 test_run_m1_capabilities 的 _run_payload/_patch_launch_capture 骨架:
# 建场景(scenarios API 注入 assertion_registry 节)→ POST /api/runs
# (injectionEntryIds)→ 断言 case 数 / case.json patch / rows 回放。

_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:回放只读本测试写入的行。

    DATA_DIR 是进程级共享目录(真实 ./data/),而 fresh 库的 execution
    id 每个测试都从 1 重新计数 —— 不隔离的话回放会串进同日其他测试
    写下的同 id JSONL 行(镜像 test_execution_rows.py 的做法)。
    """
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
    """选中 1 活条目(+ 1 死条目)且无数据集 → case 数 = 活条目数×nRuns
    (注入族即基线行,不再叠加隐式基线);死条目被 skip 且不炸;case.json
    的 vars/asserts 已 patch;rows API 回放含 injectionId。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[
            {"id": "s1", "strategy": [{"kind": "assertion",
                                       "target": "$.response_body.code",
                                       "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    draft["assertion_registry"] = {"entries": [
        # 活条目:var 覆写(amount '-1' 原样不 coerce)+ override patch('400')
        {"id": "inj-live", "name": "金额非法",
         "injection": [{"varName": "amount", "value": "-1"}],
         "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                      "operator": "eq", "expected": "400", "mode": "override"}]},
        # 死条目:stepIndex 越界 + 未知 var → entry_issues 判死,skip 不炸
        {"id": "inj-dead", "name": "越界死条目",
         "injection": [{"varName": "ghost", "value": "1"}],
         "asserts": [{"stepIndex": 9, "target": "$.x", "operator": "eq",
                      "expected": "1", "mode": "append"}]},
    ]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    # echo:converted 原样回灌 → case.json 保留 patched vars/strategy 可断言
    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-live", "inj-dead"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 2)
    assert len(cases) == 2                       # 1 活条目 × nRuns=2;死条目 skip
    for case in cases:
        assert case["config"]["vars"]["amount"] == "-1"            # 原样覆写
        assert case["steps"][0]["strategy"][0]["expected"] == "400"  # override patch

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 2
    await _await_final(client, bob, exec_id)

    # finalize 后 registry pop → rows 走 JSONL 回放,注入族行带 injectionId
    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert all(row["injectionId"] == "inj-live" for row in rows)
    assert all(row["datasetId"] is None for row in rows)
    assert all(row["caseDir"].startswith("case-00") and "-inj-" in row["caseDir"]
               for row in rows)
    assert all(row["status"] == "passed" for row in rows)
