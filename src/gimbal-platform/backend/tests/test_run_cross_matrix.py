"""dispatcher 交叉矩阵 + dataSetSelection 行级选择(spec v3 §4)。"""
import asyncio

import pytest

from app.schemas.scenario_composer import RunRequest, RunScheme
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)
from .test_scenario_composer_container import _register_and_login  # noqa: F401


# ── 纯函数:schema 键解析 ────────────────────────────────────────────
def test_run_request_parses_data_set_selection():
    req = RunRequest.model_validate({
        "scenarioId": "sc-test",
        "dataSetSelection": [
            {"datasetId": "ds-a", "rowIndexes": [0, 2]},
            {"datasetId": "ds-b"},                       # 缺省 = 整库
        ],
        "dataSetIds": ["ds-c"],                          # 兼容键照收
    })
    assert req.data_set_selection[0].dataset_id == "ds-a"
    assert req.data_set_selection[0].row_indexes == [0, 2]
    assert req.data_set_selection[1].row_indexes == []   # 整库 = 空
    assert req.data_set_ids == ["ds-c"]
    assert RunScheme.model_validate({
        "name": "s", "dataSetSelection": [{"datasetId": "ds-a", "rowIndexes": [1]}],
    }).data_set_selection[0].row_indexes == [1]


async def test_both_keys_selection_wins_ignores_data_set_ids(
    client, plate_mock: PlateMock, monkeypatch
):
    """两键同发:dataSetSelection 非空 → dataSetIds 整键忽略(spec v3 §4
    「dataSetSelection 优先」)— 兼容键只在权威键缺省时映射整库。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    ds_a = await _seed(client, bob, rows=[{"amount": 10}, {"amount": 20}])
    r = await client.post("/api/scenarios/sc-test/data-sets", headers=bob,
                          json={"name": "兼容库", "rows": [{"amount": 30}]})
    assert r.status_code == 201, r.text
    ds_b = r.json()["datasetId"]

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_a, "rowIndexes": [0]}],
        "dataSetIds": [ds_b],
    })
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                          # 只有 ds_a 行 0;ds_b 被忽略
    assert cases[0]["config"]["vars"]["amount"] == 10   # 30 = ds_b 未跑


# ── 集成:交叉矩阵 ──────────────────────────────────────────────────
_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


_LIVE_ENTRY = {
    "id": "inj-live", "name": "金额非法",
    "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
    "value": -1,
    "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                 "operator": "eq", "expected": "400", "mode": "override"}],
}


async def _seed(client, headers, *, entries=None, rows=None):
    """建场景(1 步,body.amount 模板 + code 断言)+ 数据集。"""
    from .helpers import make_draft as _draft

    draft = _draft(
        steps=[
            {"id": "s1", "request": {"body": {"amount": "${var.amount}"}},
             "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                           "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    if entries is not None:
        draft["assertion_registry"] = {"entries": entries}
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code in (200, 201), r.text
    if rows is None:
        return None
    r = await client.post("/api/scenarios/sc-test/data-sets", headers=headers,
                          json={"name": "正负流", "rows": rows})
    assert r.status_code == 201, r.text
    return r.json()["datasetId"]


async def test_duplicate_segments_merge_order_independent(
    client, plate_mock: PlateMock, monkeypatch
):
    """同库重复段合并取超集、段序无关:稀疏段 + 整库段(两种顺序)
    → 都整库(2 cases,rowIndex {0,1}),不因段序退化为单行;
    段内重复行号去重([0,0] 只跑一次行 0)。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    ds_id = await _seed(client, bob, rows=[{"amount": 10}, {"amount": 20}])

    plate_mock.behaviour = "echo"

    async def _run(selection):
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post("/api/runs", headers=bob, json={
            "scenarioId": "sc-test", "dataSetSelection": selection,
        })
        assert r.status_code == 201, r.text
        exec_id = r.json()["executionId"]
        await _await_final(client, bob, exec_id)
        rows = (await client.get(f"/api/executions/{exec_id}/rows",
                                 headers=bob)).json()["items"]
        return cases, rows

    # [稀疏, 整库] 与 [整库, 稀疏] 都 = 整库(合并取超集,与段序无关)
    cases_a, rows_a = await _run([
        {"datasetId": ds_id, "rowIndexes": [0]},
        {"datasetId": ds_id},
    ])
    cases_b, rows_b = await _run([
        {"datasetId": ds_id},
        {"datasetId": ds_id, "rowIndexes": [0]},
    ])
    for cases, rows in ((cases_a, rows_a), (cases_b, rows_b)):
        assert len(cases) == 2                       # 整库 2 行,不退化为行 0
        assert {c["config"]["vars"]["amount"] for c in cases} == {10, 20}
        assert {row["rowIndex"] for row in rows} == {0, 1}
    assert [r["rowIndex"] for r in rows_a] == [r["rowIndex"] for r in rows_b]

    # 段内重复行号去重:[0,0] 只跑一次行 0
    cases_d, rows_d = await _run([{"datasetId": ds_id, "rowIndexes": [0, 0]}])
    assert len(cases_d) == 1
    assert rows_d[0]["rowIndex"] == 0


async def test_cross_matrix_rows_times_entries(
    client, plate_mock: PlateMock, monkeypatch
):
    """双选 = N×M 交叉(spec v3 §4):2 行 × 1 条目 × nRuns=2 = 4 cases;
    每 case 行值合入 vars AND Assign 直补同场(正交叠加);rows 回放
    三定位同记(datasetId + rowIndex + injectionId);stem 带三定位。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    ds_id = await _seed(client, bob, entries=[_LIVE_ENTRY],
                        rows=[{"amount": 10}, {"amount": 20}])

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id}],
        "injectionEntryIds": ["inj-live"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 4)
    assert len(cases) == 4                          # 2 行 × 1 条目 × 2 rep
    for case in cases:
        assert case["config"]["vars"]["amount"] in (10, 20)     # 行值合入
        st = case["steps"][0]["strategy"]
        assert st[0]["expected"] == "400"                        # asserts patch
        assert {"kind": "assign", "source": -1,
                "target": "$.request_body.amount"} in st         # Assign 直补
    # 交叉完备:两行 × 两 rep 都出现过
    assert {c["config"]["vars"]["amount"] for c in cases} == {10, 20}

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 4
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 4
    assert all(row["datasetId"] == ds_id for row in rows)
    assert all(row["injectionId"] == "inj-live" for row in rows)   # 三定位同记
    assert {row["rowIndex"] for row in rows} == {0, 1}


async def test_row_selection_single_row(
    client, plate_mock: PlateMock, monkeypatch
):
    """dataSetSelection rowIndexes=[1] → 只跑该行(1 case,vars=行值);
    审计三定位记原始编辑器行号(rows 回放 rowIndex=1,stem 含 -r1-)。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    ds_id = await _seed(client, bob, rows=[{"amount": 10}, {"amount": 20}])

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id, "rowIndexes": [1]}],
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1
    assert cases[0]["config"]["vars"]["amount"] == 20
    assert all("source" not in st or st.get("kind") != "assign"
               for st in cases[0]["steps"][0]["strategy"])   # 未选条目 = 无注入

    await _await_final(client, bob, exec_id)
    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 1
    assert rows[0]["rowIndex"] == 1                 # 原始编辑器行号,非选集位置
    assert "-r1-" in rows[0]["caseDir"]             # stem 同口径三定位


async def test_row_index_out_of_range_409(client, plate_mock):
    """rowIndexes 越界 → 409 row_index_out_of_range,不派发任何 case。"""
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    ds_id = await _seed(client, bob, rows=[{"amount": 10}])
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id, "rowIndexes": [3]}],
    })
    assert r.status_code == 409, r.text
    # 平台既有错误信封为 FastAPI HTTPException detail({"detail": {...}}),
    # 与 data_set_not_found / too_many_runs 同款(计划稿 "error" 键按此适配)。
    assert r.json()["detail"]["code"] == "row_index_out_of_range"


async def test_both_empty_single_baseline(
    client, plate_mock: PlateMock, monkeypatch
):
    """都不选 = 1 基线 case(R={[基线]} × E={[无注入]})。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    await _seed(client, bob)

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": [],
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1
    assert cases[0]["config"]["vars"]["amount"] == 100        # 基线 vars
    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 1
