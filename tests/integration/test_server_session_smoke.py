"""④(2026-10-13):server 链真实子进程冒烟 + ServerSession API 面守卫。

背景:f062a88a 曾把 ServerSession 后半方法吞进一个模块级函数(嵌套
函数化),生产默认的 server 链**整条不可用** —— run_case 一调即
AttributeError;而当时的检查全部是绿的单测(fake session 顶替了真类)。
两道防线:

1. **真实子进程冒烟**:ServerSession.start 真拉起 `gimbal run server`
   (健康检查过)→ run_case 跑一个最小 case → LaunchResult ok。任何
   "类体被吞/启动链断裂"的回归在此当场红;
2. **API 面守卫**(纯反射,毫秒级):公开方法集必须在**类**上 ——
   嵌套函数化后它们会从类 dict 消失。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_server_session_api_surface_on_class():
    """公开 API 必须挂在类上(防'方法被吞进嵌套函数'的静默回归)。"""
    from app.services.gimbal_server_session import ServerSession

    required = {"start", "close", "run_case", "cancel",
                "debug_command", "debug_output"}
    own = ServerSession.__dict__
    missing = {n for n in required
               if n not in own or not callable(own[n])}
    assert not missing, (
        f"ServerSession 丢失类方法 {missing} —— 检查近期编辑是否把方法"
        "吞进了嵌套函数(f062a88a 同款事故)")


@pytest.mark.asyncio
async def test_server_chain_smoke(tmp_path: Path) -> None:
    """真拉起 server 子进程跑一单:启动健康检查 + run_case + 退出码。"""
    import asyncio

    from app.services.gimbal_server_session import ServerSession

    case = {
        "kind": "scenario", "scenarioId": "sc-smoke",
        "meta": {"name": "smoke"},
        "config": {"services": {}, "users": {},
                   "timePolicy": {"kind": "record"}},
        "resource": {},
        "steps": [],
    }
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(case, ensure_ascii=False),
                         encoding="utf-8")

    ss = ServerSession()
    await ss.start(engine_log_path=tmp_path / "engine.log", cwd=tmp_path)
    try:
        result = await ss.run_case(case_path, n_runs=1)
        assert result.launch_status == "ok", (
            f"launch={result.launch_status} error={result.error}")
        assert result.exit_code == 0, result.run_result
    finally:
        await asyncio.wait_for(ss.close(), timeout=15.0)
    # D1 回归面:close 后泵任务已收编(None)且进程引用清空
    assert ss._stderr_task is None
    assert ss._proc is None


@pytest.mark.asyncio
async def test_server_chain_smoke_failure_path(tmp_path: Path) -> None:
    """冒烟失败路径:必败断言(状态 404≠200)→ exit_code=1(此前只覆盖
    通过路径,复核 2-5 指出)。"""
    from app.services.gimbal_server_session import ServerSession

    case = {
        "kind": "scenario", "scenarioId": "sc-smoke-f",
        "meta": {"name": "smoke-fail"},
        "config": {"services": {"dead": "http://127.0.0.1:9"},
                   "users": {}, "timePolicy": {"kind": "record"}},
        "resource": {},
        "steps": [{
            "kind": "step",
            "call": {"protocol": "http", "service": "dead",
                     "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [{"kind": "assertion",
                          "target": "$.call.response.status",
                          "operator": "eq", "expected": 200}],
        }],
    }
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(case, ensure_ascii=False),
                         encoding="utf-8")
    import asyncio
    ss = ServerSession()
    await ss.start(engine_log_path=tmp_path / "engine.log", cwd=tmp_path)
    try:
        result = await ss.run_case(case_path, n_runs=1)
        assert result.launch_status == "ok"
        assert result.exit_code == 1, result.run_result
    finally:
        await asyncio.wait_for(ss.close(), timeout=15.0)
