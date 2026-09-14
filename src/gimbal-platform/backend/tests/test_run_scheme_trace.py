"""RunRequest 方案溯源:config_json 快照携带 schemeId/schemeName(快照语义,
改名不断链);缺省字段不阻断既有运行。"""
from pathlib import Path

from sqlalchemy import select

from app.models.execution import Execution
from .helpers import launch_ok as _ok, make_draft, wait_until
from .test_scenario_visibility_and_copy import _member


async def _setup(client, username="alice"):
    h = await _member(client, username)
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    return h, r.json()["meta"]["scenarioId"]


def _mock_fanout(monkeypatch) -> list:
    """POST /runs 既有测试同款 mock(test_run_baseline):plate convert 与
    gimbal launch 都不出网;返回 cases 收集器(fan-out 完成信号)。"""
    cases: list[dict] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        cases.append({"path": Path(case_path)})
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    return cases


async def _execution_config_json(execution_id: int) -> dict:
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        ex = (await db.execute(select(Execution)
                .where(Execution.id == execution_id))).scalar_one()
        return ex.config_json


async def test_config_json_carries_scheme_trace(client, monkeypatch):
    h, sid = await _setup(client)
    cases = _mock_fanout(monkeypatch)
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": sid, "dataSetIds": [], "dataSetSelection": [],
        "injectionEntryIds": [], "serviceBindings": {},
        "schemeId": "rs-042", "schemeName": "冒烟方案",
    })
    assert r.status_code == 201, r.text
    await wait_until(lambda: len(cases) >= 1)
    config_json = await _execution_config_json(r.json()["executionId"])
    assert config_json.get("schemeId") == "rs-042"
    assert config_json.get("schemeName") == "冒烟方案"


async def test_run_without_scheme_trace_still_works(client, monkeypatch):
    """无溯源字段(基线/旧客户端):照常 201,config_json 两键为 null。"""
    h, sid = await _setup(client, "bob")
    cases = _mock_fanout(monkeypatch)
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": sid, "dataSetIds": [], "dataSetSelection": [],
    })
    assert r.status_code == 201, r.text
    await wait_until(lambda: len(cases) >= 1)
    config_json = await _execution_config_json(r.json()["executionId"])
    assert config_json.get("schemeId") is None
    assert config_json.get("schemeName") is None
