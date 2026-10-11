"""Gimbal HTTP /runs 入口测试（M10 改形后：``{target, options, m2?}``）。

覆盖:
  [1] create_app 暴露 /runs + /healthz; /run 旧端点已删除（M10）
  [2] POST /runs 非 target → 422
  [3] POST /runs 合法 target → bootstrap→Engine.run→shutdown 全生命周期
  [4] options.step_to → RuntimeControl halt_at
  [5] options 缺省 → RuntimeControl halt_at=None
  [6] m2 代际门:代际不同 → 409 M2_GENERATION_MISMATCH
  [7] ServerConfig 默认端口 8766(不与 plate 8765 冲突)
"""
from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING)

# S-6 鉴权:测试设 token 绕过回环检查(TestClient 的 client.host 不是回环地址)
os.environ.setdefault("GIMBAL_SERVER_TOKEN", "test-token")

from fastapi.testclient import TestClient

from gimbal.cli.context import CLIContext
from gimbal.core.server import ServerConfig, create_app

LEGAL_TARGET = {
    "kind": "scenario",
    "scenarioId": "sc-server-001",
    "meta": {"name": "server run test"},
    "config": {
        "services": {"mock": "http://127.0.0.1:9999"},
        "users": {},
        "timePolicy": {"kind": "record"},
    },
    "resource": {},
    "steps": [
        {
            "kind": "step",
            "call": {"protocol": "http", "service": "mock",
                     "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }
    ],
}


HDRS = {"X-Gimbal-Token": "test-token"}


def make_client():
    return TestClient(create_app(CLIContext()))


def _wait_run(client, run_id, timeout=10):
    for _ in range(timeout * 10):
        r = client.get(f"/runs/{run_id}")
        if r.status_code == 200 and r.json()["status"] != "running":
            return r.json()
        time.sleep(0.1)
    return {"status": "timeout", "error": "timeout"}


# ════════════════════════════════════════════════════════════════
# [1] app 结构：/runs 在、/run 不在（M10 删除）
# ════════════════════════════════════════════════════════════════
def test_app_structure():
    client = make_client()
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True
    openapi = client.get("/openapi.json").json()
    assert "/runs" in openapi["paths"], f"/runs missing: {list(openapi['paths'])}"
    assert "/run" not in openapi["paths"], "M10: /run 旧端点应已删除"


# ════════════════════════════════════════════════════════════════
# [2] 空 target → 422
# ════════════════════════════════════════════════════════════════
def test_empty_target_422():
    client = make_client()
    r = client.post("/runs", headers=HDRS, json={"target": {"kind": "scenario"}})
    assert r.status_code == 422, f"expect 422, got {r.status_code}"


# ════════════════════════════════════════════════════════════════
# [3] 合法 target → 全生命周期
# ════════════════════════════════════════════════════════════════
def test_run_lifecycle():
    from gimbal.core.runner import RunResult

    fake_result = RunResult(
        exit_code=0, total=1, passed=1, failed=0, skipped=0, halted=0,
        details=[{"scenario_id": "sc-server-001", "status": "passed"}],
    )
    calls: list[str] = []

    def fake_bootstrap(cli_ctx):
        calls.append("bootstrap")
        m = MagicMock()
        m.cfg.reporters = ()
        m.cfg.report_dir = "./reports"
        m.cfg.plugin_configs = {}
        m.reporter_runtime = None
        return m

    class FakeEngine:
        def __init__(self, configuration):
            calls.append("engine_init")
        def run(self, target, runtime_control=None):
            calls.append("run")
            return fake_result

    def fake_shutdown(configuration):
        calls.append("shutdown")

    client = make_client()
    with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
         patch("gimbal.core.bootstrap.shutdown", fake_shutdown), \
         patch("gimbal.core.runner.Engine", FakeEngine):
        r = client.post("/runs", headers=HDRS, json={"target": LEGAL_TARGET})
    assert r.status_code == 200, f"expect 200, got {r.status_code}: {r.text[:300]}"
    run_id = r.json()["runId"]
    assert run_id
    result = _wait_run(client, run_id)
    assert result["status"] == "finished"
    assert result["summary"]["exitCode"] == 0
    assert result["summary"]["passed"] == 1


# ════════════════════════════════════════════════════════════════
# [4] options.step_to → RuntimeControl halt_at（M10：halt_at 并入 step_to）
# ════════════════════════════════════════════════════════════════
def test_options_step_to():
    from gimbal.core.runner import RunResult

    fake_result = RunResult(
        exit_code=0, total=1, passed=1, failed=0, skipped=0, halted=0,
        details=[],
    )
    captured_rc = {}

    def fake_bootstrap(cli_ctx):
        m = MagicMock()
        m.cfg.reporters = ()
        m.cfg.report_dir = "./reports"
        m.cfg.plugin_configs = {}
        m.reporter_runtime = None
        return m

    class FakeEngineRC:
        def __init__(self, configuration):
            pass
        def run(self, target, runtime_control=None):
            captured_rc["rc"] = runtime_control
            return fake_result

    client = make_client()
    with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
         patch("gimbal.core.bootstrap.shutdown", MagicMock()), \
         patch("gimbal.core.runner.Engine", FakeEngineRC):
        r = client.post("/runs", headers=HDRS, json={
            "target": LEGAL_TARGET,
            "options": {"step_to": 2},
        })
    assert r.status_code == 200
    _wait_run(client, r.json()["runId"])
    rc = captured_rc.get("rc")
    assert rc is not None and rc.halt_at == 2, f"halt_at should be 2, got {rc}"


# ════════════════════════════════════════════════════════════════
# [5] options 缺省 → halt_at=None
# ════════════════════════════════════════════════════════════════
def test_no_options():
    from gimbal.core.runner import RunResult

    fake_result = RunResult(
        exit_code=0, total=1, passed=1, failed=0, skipped=0, halted=0,
        details=[],
    )
    captured_rc = {}

    def fake_bootstrap(cli_ctx):
        m = MagicMock()
        m.cfg.reporters = ()
        m.cfg.report_dir = "./reports"
        m.cfg.plugin_configs = {}
        m.reporter_runtime = None
        return m

    class FakeEngineRC:
        def __init__(self, configuration):
            pass
        def run(self, target, runtime_control=None):
            captured_rc["rc"] = runtime_control
            return fake_result

    client = make_client()
    with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
         patch("gimbal.core.bootstrap.shutdown", MagicMock()), \
         patch("gimbal.core.runner.Engine", FakeEngineRC):
        r = client.post("/runs", headers=HDRS, json={"target": LEGAL_TARGET})
    assert r.status_code == 200
    _wait_run(client, r.json()["runId"])
    assert captured_rc["rc"].halt_at is None


# ════════════════════════════════════════════════════════════════
# [6] m2 代际门
# ════════════════════════════════════════════════════════════════
def test_m2_generation_gate():
    from gimbal.schema import M2_GENERATION, M2_HASH

    client = make_client()
    # 代际不同 → 409
    r = client.post("/runs", headers=HDRS, json={
        "target": LEGAL_TARGET,
        "m2": {"hash": "different", "generation": M2_GENERATION + 1},
    })
    assert r.status_code == 409
    assert "M2_GENERATION_MISMATCH" in r.json()["detail"]

    # hash 相同 → 放行
    r2 = client.post("/runs", headers=HDRS, json={
        "target": LEGAL_TARGET,
        "m2": {"hash": M2_HASH, "generation": M2_GENERATION},
    })
    assert r2.status_code == 200

    # 不带 m2 → 不做门检查（新 client 避开 one-run-at-a-time）
    client3 = make_client()
    r3 = client3.post("/runs", headers=HDRS, json={"target": LEGAL_TARGET})
    assert r3.status_code == 200

    # hash 不同、代际相同 → 放行(兼容;发 m2.hash_mismatch 警告事件)
    client4 = make_client()
    r4 = client4.post("/runs", headers=HDRS, json={
        "target": LEGAL_TARGET,
        "m2": {"hash": "a" * 64, "generation": M2_GENERATION},
    })
    assert r4.status_code == 200


# ════════════════════════════════════════════════════════════════
# [7] 默认端口
# ════════════════════════════════════════════════════════════════
def test_default_port():
    assert ServerConfig().port == 8766
