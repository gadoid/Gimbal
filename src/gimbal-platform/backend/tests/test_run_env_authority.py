"""P5 env 服务端权威:下发 env 取自 env_store,不采信请求体 baseUrl。"""
from __future__ import annotations

import json

from loguru import logger

from tests.helpers import make_draft, register_and_login, test_env, wait_until


# ─── 测试基座(同 test_run_cancel:mock launch/convert 走 /api/runs 全链)──
async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
    from tests.helpers import launch_ok

    return launch_ok()


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


def _jsonl_records(run_dispatcher) -> list:
    """读当日调度日志(JSONL)的全部记录。"""
    path = run_dispatcher._jsonl_path()
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def test_dispatch_uses_server_env_base_url(client, monkeypatch):
    from app.services import (
        env_store,
        gimbal_launcher as gl,
        plate_client as pc,
        run_dispatcher,
    )

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-env"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    # 服务端 test-env-A 的真值来自 env_store(bundled envs.yaml 解析结果,
    # baseUrl=http://test-a.fin.local:8000;helpers.test_env 的 http://x
    # 只是请求体形状,恰与真值不同 — 正好充当"客户端自带 env"的样本)。
    server_env = next(
        e for e in env_store.list_envs() if e.env_id == "test-env-A"
    )

    tampered = test_env()
    tampered["baseUrl"] = "http://evil.example"     # envId 不变,baseUrl 篡改

    # P5 告警捕获:loguru 不经 caplog,挂临时 sink 收 WARNING。
    warns: list[str] = []
    sink_id = logger.add(lambda m: warns.append(str(m)), level="WARNING")
    try:
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-env", "dataSetIds": [], "env": tampered,
        })
    finally:
        logger.remove(sink_id)
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]
    await wait_until(
        lambda: list(run_dispatcher._run_dir(run_id).rglob("case.json"))
    )

    # 按 runId 收窄:当日 JSONL 跨测试累积在真实 data/ 下,不能裸取 [0]。
    dispatched = [
        rec for rec in _jsonl_records(run_dispatcher)
        if rec.get("status") == "dispatched" and rec.get("runId") == run_id
    ]
    assert dispatched
    # 服务端记录整体胜出(envId/name/baseUrl 全取 env_store dump);
    # brief 原文断言 baseUrl == "http://x" 基于错误的捆绑值假设,
    # 实际真值以 env_store 为准(运行时核实)。
    assert dispatched[0]["env"] == server_env.model_dump(
        by_alias=True, mode="json"
    )
    assert "evil.example" not in str(dispatched[0]["env"])
    # 客户端值与记录不一致 → 告警留痕(服务端获胜可审计)。
    assert any(
        "env mismatch" in w and "test-env-A" in w for w in warns
    )
