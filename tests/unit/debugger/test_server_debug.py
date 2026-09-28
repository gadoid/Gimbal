"""批次 E server 测试：/runs 异步启动 + 调试命令（token 硬前置）+ SSE 事件流。

验收门（v2.1 批次 E）：经 server 单步调试一个运行中场景。
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from gimbal.cli.context import CLIContext
from gimbal.core.server import create_app


def _scenario_dict(sid="srv-sc", bad=False) -> dict:
    return {
        "kind": "scenario", "scenarioId": sid,
        "meta": {"name": "t", "description": "d", "module": "m", "priority": 1,
                 "author": "a", "owner": "o", "tags": [], "version": "1.0",
                 "createTime": "2026-09-27T00:00:00Z", "expire": False,
                 "requirementRef": []},
        "config": {}, "resource": {},
        "steps": [{"kind": "step",
                   "call": {"protocol": "echo", "message": sid},
                   "strategy": []}],
    }


@pytest.fixture()
def client(monkeypatch):
    # echo 协议注册：monkeypatch build_default_dispatcher 太重 —— server 每 run
    # 全新 bootstrap；这里直接向默认注册表补 echo（进程内共享，幂等）
    from gimbal.protocols.registry import build_default_protocol_registry
    from debugger.test_batch_e import ProgEcho
    import gimbal.protocols.registry as _preg
    _capture_orig()
    monkeypatch.setattr(
        _preg, "build_default_protocol_registry",
        lambda **kw: _registry_with_echo(**kw),
    )
    app = create_app(CLIContext())
    # S-6:POST /runs 无 token 时仅回环可用 —— TestClient 模拟回环来源
    return fastapi_testclient.TestClient(app, client=("127.0.0.1", 50000))


_ORIG_BUILD = None


def _registry_with_echo(**kw):
    from debugger.test_batch_e import ProgEcho
    reg = _ORIG_BUILD(**kw)
    if "echo" not in reg:
        reg.register(ProgEcho())
    return reg


def _capture_orig():
    global _ORIG_BUILD
    import gimbal.protocols.registry as preg
    if _ORIG_BUILD is None:
        _ORIG_BUILD = preg.build_default_protocol_registry


def _wait_finished(client, run_id, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = client.get(f"/runs/{run_id}").json()
        if st["status"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("run 未在限时内结束")


class TestServerAuth:

    def test_debug_endpoint_forbidden_without_token_env(self, client, monkeypatch):
        monkeypatch.delenv("GIMBAL_SERVER_TOKEN", raising=False)
        r = client.post("/runs/xxx/debug", json={"command": "continue"})
        assert r.status_code == 403
        assert "GIMBAL_SERVER_TOKEN" in r.json()["detail"]

    def test_debug_endpoint_rejects_wrong_token(self, client, monkeypatch):
        monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "s3cret")
        r = client.post("/runs/xxx/debug", json={"command": "continue"},
                        headers={"X-Gimbal-Token": "wrong"})
        assert r.status_code == 401
        r2 = client.post(
            "/runs/xxx/debug", json={"command": "continue"},
            headers={"Authorization": "Bearer s3cret"})
        assert r2.status_code in (404, 409)   # 鉴权过了，卡在 run 不存在

    def test_events_requires_token(self, client, monkeypatch):
        monkeypatch.delenv("GIMBAL_SERVER_TOKEN", raising=False)
        assert client.get("/runs/xxx/events").status_code == 403


class TestAsyncRun:

    def test_run_lifecycle_and_status(self, client):
        r = client.post("/runs", json={"target": _scenario_dict()})
        assert r.status_code == 200
        run_id = r.json()["runId"]
        st = _wait_finished(client, run_id)
        assert st["summary"]["exitCode"] == 0
        assert st["summary"]["passed"] == 1

    def test_second_run_rejected_while_running(self, client, monkeypatch):
        monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "t")
        # 用 debug 暂停卡住第一个 run（every_step 暂停 + 不给命令）
        r = client.post("/runs", json={
            "target": _scenario_dict(),
            "debug": {"pause": "every_step", "wait_timeout": 8},
        }, headers={"X-Gimbal-Token": "t"})
        assert r.status_code == 200
        rid = r.json()["runId"]
        try:
            r2 = client.post("/runs", json={"target": _scenario_dict()},
                             headers={"X-Gimbal-Token": "t"})
            assert r2.status_code == 409
        finally:
            # 下发 continue 让其结束
            client.post(f"/runs/{rid}/debug", json={"command": "continue"},
                        headers={"X-Gimbal-Token": "t"})
            _wait_finished(client, rid, timeout=15)

    def test_unknown_run_404(self, client):
        monkeypatch_env = None
        assert client.get("/runs/nope").status_code == 404


class TestDebugOverServer:

    def test_single_step_debug_via_server(self, client, monkeypatch):
        """验收门：经 server 单步调试一个运行中场景（every_step + continue）。"""
        monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "tok-1")
        r = client.post("/runs", json={
            "target": _scenario_dict("dbg-sc"),
            "debug": {"pause": "every_step", "wait_timeout": 10},
        }, headers={"X-Gimbal-Token": "tok-1"})
        assert r.status_code == 200
        rid = r.json()["runId"]
        assert r.json()["debugEnabled"] is True

        # 等待进入暂停（debug.session 事件出现 / 状态仍 running）
        deadline = time.time() + 10
        paused = False
        while time.time() < deadline:
            st = client.get(f"/runs/{rid}").json()
            if st["status"] == "running":
                # 有暂停输出即可下发 continue
                r2 = client.post(f"/runs/{rid}/debug",
                                 json={"command": "continue"},
                                 headers={"X-Gimbal-Token": "tok-1"})
                if r2.status_code == 200 and r2.json()["accepted"]:
                    paused = True
                    break
            else:
                break
            time.sleep(0.1)
        assert paused, "未能进入调试暂停"

        st = _wait_finished(client, rid, timeout=15)
        assert st["summary"]["exitCode"] == 0

    def test_sse_stream_emits_events(self, client, monkeypatch):
        monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "tok-2")
        r = client.post("/runs", json={"target": _scenario_dict("sse-sc")},
                        headers={"X-Gimbal-Token": "tok-2"})
        rid = r.json()["runId"]
        _wait_finished(client, rid)

        with client.stream("GET", f"/runs/{rid}/events",
                           headers={"X-Gimbal-Token": "tok-2"}) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(resp.iter_text())
        assert "run.start" in body or "run.end" in body
        assert "event: done" in body


def test_sse_id_is_seq(client, monkeypatch):
    """S-5：SSE id = 事件 seq（单调递增,从 1 起）。"""
    monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "tok-seq")
    r = client.post("/runs", json={"target": _scenario_dict("sse-seq-sc")},
                    headers={"X-Gimbal-Token": "tok-seq"})
    rid = r.json()["runId"]
    _wait_finished(client, rid)

    with client.stream("GET", f"/runs/{rid}/events",
                       headers={"X-Gimbal-Token": "tok-seq"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    ids = [int(line[3:]) for line in body.splitlines()
           if line.startswith("id: ")]
    assert ids, "SSE 流无 id 行"
    assert ids == sorted(ids) and ids[0] >= 1
    # 末事件 run.finished 也应带 seq id(S-5 终线事件化)
    assert "run.finished" in body


# ── S-6: server 保护 ─────────────────────────────────────────


class TestServerProtection:

    def test_post_runs_requires_token_when_configured(self, client, monkeypatch):
        monkeypatch.setenv("GIMBAL_SERVER_TOKEN", "s3cret")
        r = client.post("/runs", json={"target": _scenario_dict("auth-sc")})
        assert r.status_code == 401
        r2 = client.post("/runs", json={"target": _scenario_dict("auth-sc")},
                         headers={"X-Gimbal-Token": "s3cret"})
        assert r2.status_code == 200

    def test_post_runs_loopback_only_without_token(self, monkeypatch):
        """无 token 时非回环来源 403(回环 fixture 的对照见其余测试)。"""
        monkeypatch.delenv("GIMBAL_SERVER_TOKEN", raising=False)
        from gimbal.core.server import create_app
        import fastapi.testclient as ftc
        from gimbal.cli.context import CLIContext
        remote = ftc.TestClient(create_app(CLIContext()),
                                client=("10.0.0.5", 12345))
        r = remote.post("/runs", json={"target": _scenario_dict("remote-sc")})
        assert r.status_code == 403
        assert "loopback" in r.json()["detail"]

    def test_debug_rejects_multi_unit(self, client, monkeypatch):
        monkeypatch.delenv("GIMBAL_SERVER_TOKEN", raising=False)
        from gimbal.schema.scenario import SuiteGraph

        def _unit(ref):
            return {"ref": ref, "scenario": _scenario_dict(ref)}

        graph = {
            "kind": "graph", "mode": "aggregate",
            "units": [_unit("a"), _unit("b")],
        }
        r = client.post("/runs", json={
            "target": graph, "debug": {"pause": "every_step"},
        })
        assert r.status_code == 422
        assert "single-unit" in r.json()["detail"]

    def test_registry_reaped_after_ttl(self, client, monkeypatch):
        monkeypatch.delenv("GIMBAL_SERVER_TOKEN", raising=False)
        monkeypatch.setattr("gimbal.core.server_debug._REAP_TTL_SEC", 0.05)
        r = client.post("/runs", json={"target": _scenario_dict("reap-sc")})
        rid = r.json()["runId"]
        # 直接等待 404(reap 本身就是被测行为;run 完成快于轮询间隔时
        # 首询可能已过 TTL,不能再先 _wait_finished——那条路径会读到 404 体)
        import time as _t
        deadline = _t.time() + 5
        code = None
        while _t.time() < deadline:
            code = client.get(f"/runs/{rid}").status_code
            if code == 404:
                break
            _t.sleep(0.05)
        assert code == 404
