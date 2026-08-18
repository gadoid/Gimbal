"""Gimbal HTTP run 入口测试(#4 运行最小链路)。

覆盖:
  [1] create_app 暴露 /run + /healthz,TestClient 可调
  [2] POST /run 非法 scenario → 422(校验在锁外快失败)
  [3] POST /run 合法 scenario → bootstrap→Engine.run→shutdown 全生命周期
      被走一遍(用 mock Engine 捕获),RunResult 字段映射进响应
  [4] halt_at/halt_reason → RuntimeControl 构造正确
  [5] 缺 scenario 字段 → 422(pydantic 必填)
  [6] ServerConfig 默认端口 8766(不与 plate 8765 冲突)
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING)

print("=" * 60)
print("SERVER RUN TEST (#4 minimal run chain)")
print("=" * 60)

from fastapi.testclient import TestClient

from gimbal.cli.context import CLIContext
from gimbal.core.server import ServerConfig, create_app

LEGAL_SCENARIO = {
    "kind": "scenario",
    "scenarioId": "sc-server-001",
    "meta": {
        "name": "server run test",
        "description": "minimal valid scenario",
        "module": "test",
        "priority": 1,
        "author": "test",
        "owner": "test",
        "tags": ["server"],
        "version": "v1",
        "createTime": "2025-01-01T00:00:00",
        "expire": False,
        "requirementRef": [],
    },
    "config": {
        "services": {"mock": "http://127.0.0.1:9999"},
        "users": {},
        "timePolicy": {"kind": "record"},
    },
    "resource": {},
    "steps": [
        {
            "kind": "step",
            "api": {"kind": "api", "service": "mock", "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }
    ],
}


def make_client():
    return TestClient(create_app(CLIContext()))


# ════════════════════════════════════════════════════════════════
# [1] app 结构
# ════════════════════════════════════════════════════════════════
print("\n[1] /run + /healthz 挂载")
client = make_client()
r = client.get("/healthz")
assert r.status_code == 200 and r.json()["ok"] is True
openapi = client.get("/openapi.json").json()
assert "/run" in openapi["paths"], f"/run missing: {list(openapi['paths'])}"
print("  PASS")

# ════════════════════════════════════════════════════════════════
# [2] 非法 scenario → 422
# ════════════════════════════════════════════════════════════════
print("\n[2] 非法 scenario → 422")
r = client.post("/run", json={"scenario": {"kind": "scenario"}})
assert r.status_code == 422, f"expect 422, got {r.status_code}: {r.text[:200]}"
assert "validation failed" in r.json()["detail"]
print("  PASS")

# ════════════════════════════════════════════════════════════════
# [3] 合法 scenario → 全生命周期 + 响应映射
# ════════════════════════════════════════════════════════════════
print("\n[3] bootstrap → Engine.run → shutdown 生命周期")
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
    m.reporter_runtime = None  # Engine.run 里 reporter_runtime=None 分支直接跳过
    return m

class FakeEngine:
    def __init__(self, configuration, *, asset_store=None):
        calls.append("engine_init")
    def run(self, target, runtime_control=None):
        calls.append("run")
        assert getattr(target, "scenarioId", None) == "sc-server-001"
        return fake_result

def fake_shutdown(configuration):
    calls.append("shutdown")

# patch 引擎侧符号(它们在函数体内延迟 import,patch 源模块即可)
with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
     patch("gimbal.core.bootstrap.shutdown", fake_shutdown), \
     patch("gimbal.core.runner.Engine", FakeEngine):
    r = client.post("/run", json={"scenario": LEGAL_SCENARIO})

assert r.status_code == 200, f"expect 200, got {r.status_code}: {r.text[:300]}"
body = r.json()
assert body["exitCode"] == 0
assert body["passed"] == 1 and body["total"] == 1
assert body["details"][0]["scenario_id"] == "sc-server-001"
# 生命周期顺序:bootstrap 在前,shutdown 在后
assert calls == ["bootstrap", "engine_init", "run", "shutdown"], f"lifecycle order wrong: {calls}"
print("  PASS")

# ════════════════════════════════════════════════════════════════
# [4] halt_at → RuntimeControl
# ════════════════════════════════════════════════════════════════
print("\n[4] halt_at/halt_reason → RuntimeControl")
captured_rc = {}

class FakeEngineCaptureRC(FakeEngine):
    def run(self, target, runtime_control=None):
        captured_rc["rc"] = runtime_control
        return fake_result

with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
     patch("gimbal.core.bootstrap.shutdown", fake_shutdown), \
     patch("gimbal.core.runner.Engine", FakeEngineCaptureRC):
    r = client.post("/run", json={
        "scenario": LEGAL_SCENARIO, "halt_at": 2, "halt_reason": "debug-break",
    })
assert r.status_code == 200
rc = captured_rc["rc"]
assert rc is not None and rc.halt_at == 2 and rc.halt_reason == "debug-break"
print("  PASS")

# 不传 halt_at → runtime_control=None
captured_rc.clear()
with patch("gimbal.core.bootstrap.bootstrap", fake_bootstrap), \
     patch("gimbal.core.bootstrap.shutdown", fake_shutdown), \
     patch("gimbal.core.runner.Engine", FakeEngineCaptureRC):
    r = client.post("/run", json={"scenario": LEGAL_SCENARIO})
assert r.status_code == 200
assert captured_rc["rc"] is None
print("  PASS (no halt_at → None)")

# ════════════════════════════════════════════════════════════════
# [5] 缺 scenario → 422
# ════════════════════════════════════════════════════════════════
print("\n[5] 缺 scenario 字段 → 422")
r = client.post("/run", json={})
assert r.status_code == 422
print("  PASS")

# ════════════════════════════════════════════════════════════════
# [6] 默认端口 8766
# ════════════════════════════════════════════════════════════════
print("\n[6] ServerConfig 默认端口")
assert ServerConfig().port == 8766, f"expect 8766, got {ServerConfig().port}"
print("  PASS")

print("\nALL SERVER RUN TESTS PASS")
