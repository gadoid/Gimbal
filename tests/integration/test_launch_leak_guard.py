"""launch 链平台侧联防实证:父进程硬死 → launch 子进程必须自退。

2026-11-03 泄漏复盘的 launch 链形态:平台 ``gimbal_launcher.launch()``
spawn 的 ``run launch`` 子进程,此前在父进程硬杀(SIGKILL/Bash 超时/带
会话退出)后无人回收 —— 断管道写失败被引擎吞掉,「盲跑僵尸」把用例
剩余工作量全部打完才退(真实请求打到被测系统,超时上限随父进程失效)。
现 spawn 带 PDEATHSIG(内核递 SIGTERM)+ stdin=PIPE(引擎 EOF 守卫协作
取消)双守卫,任一生效即通过。

与 test_server_session_smoke.py::test_server_session_parent_hard_death
同构:helper 进程用**平台 launcher 真链路**拉起子进程后 ``os._exit(9)``
硬死(不走任何 finally);本测试断言子进程在自然跑完(30 步×1s ≈ 32s)
之前消失。引擎直拉的同款判定在 test_launch_selfexit.py。
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

# helper 里 spy 出真实子进程 pid 后按秒打点,给 os._exit 前留足
# 「子进程已进入执行中段」的时间(引擎 bootstrap ~2s + 2-3 个慢请求)
_HELPER = r'''
import asyncio, os, sys
from app.services import gimbal_launcher as L

async def main():
    real = asyncio.create_subprocess_exec
    async def spy(*a, **kw):
        proc = await real(*a, **kw)
        print(f"child_pid={proc.pid}", flush=True)
        return proc
    asyncio.create_subprocess_exec = spy
    # 后台跑真链路(慢服务用例,30 步×1s);不等它完成
    task = asyncio.ensure_future(L.launch(sys.argv[1]))
    await asyncio.sleep(5.0)          # 子进程已 mid-run(≥2 个请求在飞/已完)
    os._exit(9)                       # 模拟 SIGKILL:无 finally/无收尾
    await task                        # 不可达,占位让 reader 理解意图

asyncio.run(main())
'''


def _pid_alive(pid: int) -> bool:
    """/proc 存在且非僵尸才算活(与 smoke 测试同口径)。"""
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
def test_launch_parent_hard_death(tmp_path: Path) -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    # 慢服务:每请求 1s;30 步 → 自然 ≈32s,给「盲跑僵尸」足够暴露窗口
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(1.0)
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"pong")

        def log_message(self, *a):
            pass

    import socket as _s
    with _s.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    step = {"kind": "step",
            "call": {"protocol": "http", "service": "slow",
                     "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [{"kind": "assertion",
                          "target": "$.call.response.status",
                          "operator": "eq", "expected": 200}]}
    case = {"kind": "scenario", "scenarioId": "sc-launch-guard",
            "meta": {"name": "launch-guard"},
            "config": {"services": {"slow": f"http://127.0.0.1:{port}"},
                       "users": {}, "timePolicy": {"kind": "record"}},
            "resource": {}, "steps": [dict(step) for _ in range(30)]}
    case_path = tmp_path / "case30.json"
    case_path.write_text(json.dumps(case, ensure_ascii=False),
                         encoding="utf-8")

    helper = tmp_path / "hard_death_helper.py"
    helper.write_text(_HELPER, encoding="utf-8")
    out = subprocess.run([sys.executable, str(helper), str(case_path)],
                         capture_output=True, text=True, timeout=90)
    assert out.returncode == 9, (
        f"helper 未按预期硬退: rc={out.returncode}\n{out.stderr[-800:]}")
    pid_line = [ln for ln in out.stdout.splitlines()
                if ln.startswith("child_pid=")]
    assert pid_line, f"helper 未抓到子进程 pid:\n{out.stdout}\n{out.stderr[-800:]}"
    child_pid = int(pid_line[-1].split("=")[1])

    # 守卫生效:EOF 协作取消(秒级)或 PDEATHSIG(即时);盲跑僵尸则要
    # ~27s+。上限 20s:既容收尾抖动,又远小于自然完成时间。
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if not _pid_alive(child_pid):
            return
        time.sleep(0.25)
    try:
        import os
        os.kill(child_pid, 9)
    except ProcessLookupError:
        pass
    pytest.fail(f"父进程硬死 20s 后 launch 子进程 pid={child_pid} 仍存活"
                "(自然完成需 ~32s)—— PDEATHSIG/stdin 守卫均未生效"
                "(盲跑僵尸回归)")
