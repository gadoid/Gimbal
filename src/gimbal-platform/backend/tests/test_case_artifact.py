"""case 工件白名单端点:engine.log / result.json 可读,其余一律拒(spec §9.1)。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.config import settings
from .helpers import launch_ok as _ok, make_draft as _draft
from .test_run_m1_capabilities import _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:工件只读本测试写入的文件。

    DATA_DIR 是进程级共享目录(真实 ./data/),而 fresh 库的 execution
    id 每个测试都从 1 重新计数 —— 不隔离的话 rows 回放会串进同日其他
    测试的 JSONL,拿错 stem 后工件 404(镜像 test_execution_rows.py)。
    """
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


@pytest.fixture
async def finished_run(client, plate_mock: PlateMock, monkeypatch):
    """单行执行完成;launch 假实现同时落 engine.log 工件。

    result.json 不由假实现写 —— 真实 writer 是 dispatcher 的
    ``_write_result_evidence``(P1 证据落盘,launch 返回后覆盖式写入),
    测试断言以它为准。等 rows 的 caseDir 就绪(live registry 行尾置
    stem;过早读会撞上 ``_append_log`` 的 to_thread 窗口拿到空 stem)。
    """
    from app.services import gimbal_launcher as gl

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        case_dir = Path(case_path).parent
        (case_dir / "engine.log").write_text("engine says hi\n", encoding="utf-8")
        return _ok()

    monkeypatch.setattr(gl, "launch", _capture)

    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}]))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    stem = ""
    for _ in range(200):
        rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
                ).json()["items"]
        if rows and rows[0]["caseDir"]:
            stem = rows[0]["caseDir"]
            break
        await asyncio.sleep(0.05)
    assert stem, "case stem not visible in rows within 10s"
    return bob, exec_id, stem       # stem


async def test_engine_log_and_result_readable(client, finished_run):
    bob, exec_id, stem = finished_run
    r1 = await client.get(f"/api/executions/{exec_id}/case-artifact",
                          headers=bob, params={"case": stem, "file": "engine-log"})
    assert r1.status_code == 200
    assert "text/plain" in r1.headers["content-type"]
    assert r1.text == "engine says hi\n"
    r2 = await client.get(f"/api/executions/{exec_id}/case-artifact",
                          headers=bob, params={"case": stem, "file": "result"})
    assert r2.status_code == 200
    assert "text/plain" in r2.headers["content-type"]
    # result.json 由 dispatcher 的 _write_result_evidence 写入(P1 证据)。
    payload = json.loads(r2.text)
    assert payload["launchStatus"] == "ok"
    assert payload["status"] == "passed"


async def test_case_json_never_exposed(client, finished_run):
    bob, exec_id, stem = finished_run
    for f in ("case", "case-json", "case.json"):
        resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                                headers=bob, params={"case": stem, "file": f})
        assert resp.status_code == 400


async def test_path_traversal_rejected(client, finished_run):
    bob, exec_id, _ = finished_run
    resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                            headers=bob,
                            params={"case": "..%2Fevil", "file": "engine-log"})
    assert resp.status_code in (400, 404)


async def test_missing_artifact_404(client, finished_run):
    bob, exec_id, _ = finished_run
    resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                            headers=bob,
                            params={"case": "case-999-none-r0-n0", "file": "engine-log"})
    assert resp.status_code == 404
