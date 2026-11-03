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
import os
import signal
import subprocess
import sys
import time
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
    """真拉起 server 子进程跑一单:启动健康检查 + run_case + 退出码。

    结构化日志批 1:同时携带 on_log —— stderr 泵必须把 JsonSink 的
    JSON 行解析回调出来(server 链日志入库的传输面活体闸)。
    """
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

    logs: "list[dict]" = []
    ss = ServerSession()
    await ss.start(engine_log_path=tmp_path / "engine.log", cwd=tmp_path,
                   on_log=logs.append)
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
    # 泵活体:引擎 bootstrap 后的 stderr 是 JsonSink JSON 行,on_log 应收到
    # 结构化日志(带 level;入库行零 ANSI——泵只回调解析成功的 dict)
    assert logs, "stderr 泵未回调任何日志行 —— server 链日志入库链路断裂"
    for d in logs:
        assert isinstance(d.get("level"), str) and d["level"], d
    raw = (tmp_path / "engine.log").read_text(encoding="utf-8")
    assert raw, "engine.log 文件面必须全量保留(审计兜底)"


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


# ─── 子进程泄漏防线(2026-11-03 复盘) ───────────────────────────────

_HARD_DEATH_HELPER = r'''
import asyncio, os
from app.services.gimbal_server_session import ServerSession

async def main():
    ss = ServerSession()
    await ss.start()                 # healthz 过 → 执行器完全就绪
    print(ss._proc.pid, flush=True)
    os._exit(9)                      # 模拟 SIGKILL:不走任何 finally / close()

asyncio.run(main())
'''


def _pid_alive(pid: int) -> bool:
    """Linux:/proc 存在且非僵尸才算活(孤儿被 init 收割后 /proc 消失;
    尚未收割的僵尸 State=Z 也视为已死 —— 它已不占端口与内存)。"""
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("State:"):
                    return not line.split()[1].startswith("Z")
    except FileNotFoundError:
        return False
    return True


@pytest.mark.skipif(sys.platform != "linux",
                    reason="PDEATHSIG 与 /proc 探活为 Linux 语义")
def test_server_session_parent_hard_death(tmp_path: Path) -> None:
    """父进程硬死(os._exit,无 finally)→ 执行器必须自退,不依赖 close()。

    这正是泄漏事故的形态:旧实现唯一回收路径是协作式 close(),父进程
    被 SIGKILL/超时杀掉就永远没人 terminate,21 个执行器以 PPID=1 空转
    两周。现 spawn 带 PDEATHSIG(内核递 SIGTERM)+ stdin=PIPE(EOF 自退)
    双守卫,任一生效即通过;两道都失效才会在此红。
    """
    helper = tmp_path / "hard_death_helper.py"
    helper.write_text(_HARD_DEATH_HELPER, encoding="utf-8")
    out = subprocess.run([sys.executable, str(helper)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 9, f"helper 未按预期硬退: rc={out.returncode}\n{out.stderr[-800:]}"
    lines = [ln for ln in out.stdout.splitlines() if ln.strip().isdigit()]
    assert lines, f"helper 未输出执行器 pid:\n{out.stdout}\n{out.stderr[-800:]}"
    child_pid = int(lines[-1])

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if not _pid_alive(child_pid):
            return
        time.sleep(0.25)
    # 守卫失效:清掉泄漏体再失败,不给下一个用例留脏进程
    try:
        os.kill(child_pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    pytest.fail(f"父进程硬死 15s 后执行器 pid={child_pid} 仍存活 —— "
                "PDEATHSIG/stdin 守卫均未生效(泄漏回归)")
