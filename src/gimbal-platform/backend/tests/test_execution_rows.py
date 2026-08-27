"""行级状态:registry(活跃)+ JSONL 回放(历史)(spec §9.1)。"""
from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member, _seed_ds

# 执行终态(models/execution.py:done/failed/canceled;queued/running 非终态)
_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:回放只读本测试写入的行。

    DATA_DIR 是进程级共享目录(真实 ./data/),而 fresh 库的 execution
    id 每个测试都从 1 重新计数 —— 不隔离的话回放会串进同日其他测试
    写下的同 id JSONL 行(镜像 test_run_case_retention.py 的做法)。
    """
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


async def test_rows_live_then_replay(client, plate_mock: PlateMock, monkeypatch):
    """执行完成后 registry 已 pop → rows 端点走 JSONL 回放,结果一致。"""
    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}], vars_map={"qty": 1}))
    assert r.status_code in (200, 201), r.text
    await _seed_ds(client, bob)
    # ds-001 追加为 2 行(现 fanout 模型:选中数据集 → 仅其数据行,
    # 不再叠加隐式基线行;基线只在未选数据集时作为唯一隐式行)→ 2 case。
    r = await client.put(
        "/api/data-sets/ds-001", headers=bob,
        json={"name": "ds", "rows": [{"qty": 1}, {"qty": 2}]},
    )
    assert r.status_code == 200, r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=["ds-001"], nRuns=1))
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 2)              # ds-001 的 2 行数据
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert [r["seq"] for r in rows] == [0, 1]
    assert all(r["status"] and r["status"] != "queued" for r in rows)
    assert all(r["caseDir"] for r in rows)            # case stem 非空(供工件端点)
    assert all(r["datasetId"] == "ds-001" for r in rows)


async def test_registry_popped_after_finalize(client, plate_mock: PlateMock,
                                              monkeypatch):
    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}]))
    assert r.status_code in (200, 201), r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    await _await_final(client, bob, exec_id)

    from app.services import run_dispatcher
    assert exec_id not in run_dispatcher._row_states   # 活跃表不泄漏


async def test_rows_unknown_execution_404(client):
    bob = await _member(client, "bob")
    resp = await client.get("/api/executions/99999999/rows", headers=bob)
    assert resp.status_code == 404


class _StepClock:
    """每次取时 +1s 的假钟:派发/完成两次取时严格递增,断言确定性。

    真实时钟下同秒完成(microsecond 精度仍可能同拍)会让
    finishedAt == startedAt 偶发红;假钟下 final 行 ts 必然晚于
    dispatched 行 ts(T7-Q1 修复的就是 final 行 ts 不刷新的回归)。
    """

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self):
        from datetime import datetime, timedelta
        self._calls += 1
        return datetime(2026, 1, 1, 12, 0, 0) + timedelta(seconds=self._calls)


async def test_replay_finished_at_after_started_at(
    client, plate_mock: PlateMock, monkeypatch
):
    """T7-Q1:final 行 ts = 完成时刻 → 回放 finishedAt 严格晚于 startedAt。"""
    from datetime import datetime

    from app.services import run_dispatcher as rd

    monkeypatch.setattr(rd, "_utcnow", _StepClock())

    bob = await _member(client, "bob")
    r = await client.post(
        "/api/scenarios", headers=bob, json=_draft(steps=[{"id": "s1"}])
    )
    assert r.status_code in (200, 201), r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    await _await_final(client, bob, exec_id)

    # finalize 后 registry 已 pop → 本读数走 JSONL 回放路径。
    rows = (
        await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
    ).json()["items"]
    assert len(rows) == 1
    assert rows[0]["status"] == "passed"
    started = datetime.fromisoformat(rows[0]["startedAt"].rstrip("Z"))
    finished = datetime.fromisoformat(rows[0]["finishedAt"].rstrip("Z"))
    assert finished > started, (rows[0]["startedAt"], rows[0]["finishedAt"])
