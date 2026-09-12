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


# ── 索引基数(Z2)/ 守齐(B)/ 降级可见(Y)────────────────────────────
async def test_dispatcher_uses_raw_step_index_base(client, plate_mock, monkeypatch):
    """Z2:definition.steps 混入非 dict 元素时,声明面/body/asserts 仍按**原始**下标寻址
    (与前端 compose_injection_scenario 同一基准)。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1",
                "api": {"kind": "api", "service": "svc", "method": "POST", "path": "/a", "headers": {},
                        "view_hints": {"endpoint_id": "ep-raw"}},
                "request": {"body": {"amount": "${var.amount}"}}, "strategy": []}],
        vars_map={"amount": 1},
    )
    draft["definition"]["steps"].insert(0, "GARBAGE")     # 过滤版下标会整体前移一位
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-raw", "name": "原始下标",
        "path": {"stepIndex": 1, "source": "body", "jsonpath": "$.amount"},
        "value": 9, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    plate_mock.fulls["ep-raw"] = {"request": {"declarations": [
        {"name": "amount", "path": "$.amount", "state": "form", "required": True}]}}
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-raw"]})
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 原始下标 1 = 唯一真实步骤 ⇒ 判活并执行
    # case.json 原样保留**原始** steps(含 0 位的非 dict 元素)—— 这正是判定与
    # 物化必须同一基数的原因:Assign 落在原始下标 1 上(过滤版会落到 0 位)。
    assert cases[0]["steps"][0] == "GARBAGE"
    assert {"kind": "assign", "source": 9, "target": "$.request_body.amount"} in \
        cases[0]["steps"][1]["strategy"]


async def test_dispatcher_tolerates_non_dict_api(client, plate_mock, monkeypatch):
    """B:step.api 为字符串时不再 500(守齐),按无 endpoint_id 降级为 body 面。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1", "api": "svc",                    # ← 非 dict
                "request": {"body": {"amount": "${var.amount}"}}, "strategy": []}],
        vars_map={"amount": 1},
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-b", "name": "body 面可判",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
        "value": 5, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-b"]})
    assert r.status_code == 201, r.text                      # 不是 500
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1


async def test_degraded_face_is_visible_in_run_record(client, plate_mock, monkeypatch):
    """Y:声明面**取数失败**导致的跳过与"端点本无声明"可区分 —— 前者在 run 记录里留标记。"""
    from .helpers import make_draft as _draft
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1",
                "api": {"kind": "api", "service": "svc", "method": "POST", "path": "/a", "headers": {},
                        "view_hints": {"endpoint_id": "ep-absent"}},   # fulls 里不注册 ⇒ 404
                "request": {"body": {}}, "strategy": []}])
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-d", "name": "锚在契约声明上",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 1, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text
    plate_mock.behaviour = "echo"

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-d"]})
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    ex = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    cfg = ex.get("config") or {}
    assert cfg.get("judgeDegraded") is True
    assert cfg.get("entriesSkippedByDegradation") == ["inj-d"]
    # 正对照:端点**存在**但没有该声明 ⇒ 不是降级,不留标记
    plate_mock.fulls["ep-absent"] = {"request": {"declarations": []}}
    from app.services.endpoint_declarations import _reset_declared_paths_cache
    _reset_declared_paths_cache()
    r2 = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-d"]})
    ex2 = (await client.get(f"/api/executions/{r2.json()['executionId']}", headers=bob)).json()
    assert (ex2.get("config") or {}).get("judgeDegraded") is None


async def test_compose_tolerates_non_dict_step_like_out_of_range(client, plate_mock, monkeypatch):
    """C24 ②:非 dict 步骤元素 + `jsonpath: "$"`(**判定判活**,直达物化)不得让
    compose_injection_scenario 硬抛 —— `steps[si]` 使用前守卫,与「越界」同待遇:
    跳过(该函数 docstring 声称的「悬空项静默跳过」修后才成立)。

    注:此形状的真实症状**不是** POST 500 —— compose 在后台 _fanout 里(同步
    路径之外),抛出去会掀掉整单 fan-out ⇒ 零 case + 执行永不落终态。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(steps=[{"id": "s1", "request": {"body": {}}, "strategy": []}])
    draft["definition"]["steps"].insert(0, "GARBAGE")
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-nondict", "name": "根锚在非 dict 步上",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$"},
        "value": 7,
        # asserts 侧同样指向非 dict 步 —— 两个 `steps[si]` 写入点都要跳过
        "asserts": [{"stepIndex": 0, "mode": "append", "target": "$.response_body.code",
                     "operator": "eq", "expected": "0"}]}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-nondict"]})
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                       # 后台 fan-out 没被掀掉
    assert cases[0]["steps"][0] == "GARBAGE"     # 原始 steps 原样入 case
    assert cases[0]["steps"][1]["strategy"] == []   # 非 dict 步 = 跳过,不落策略
    await _await_final(client, bob, exec_id)     # 整单仍收敛(非卡死)
