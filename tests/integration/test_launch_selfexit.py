"""launch 链「盲跑僵尸」泄漏守卫的真子进程 e2e(2026-11-03 泄漏复盘)。

实证过的事故形态:平台父进程硬死后,``run launch`` 子进程不会死 ——
stdout 写断管道的 BrokenPipeError 被引擎事件总线 ``_safe_call`` 与
loguru 层层吞掉,用例继续打满剩余请求才自然退出,且 GIMBAL_TIMEOUT_SEC
上限随父进程失效(25 步×1s 用例,父死于第 1 事件后孤儿仍打满 25 个
请求、~27s 才退)。

修复后(run_launch 0.5 布防 stdin 守卫 → 置 RuntimeControl.cancel_event
协作取消),EOF 应让孤儿在步骤边界收口:在飞请求跑完即停,远早于
自然跑完。本文件用 12 步×1s 慢服务用例(自然 ≈13s)验证:

1. stdin 写端关闭(=父进程死亡,内核视角不可区分)→ 数秒内退出;
2. stdin=DEVNULL(不布防)同用例正常跑完 —— 守卫不误伤手动/常规
   形态。

平台 launcher 侧联防(PDEATHSIG + stdin=PIPE spawn)在
test_launch_leak_guard.py。
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_slow_server(port: int, delay: float = 1.0) -> None:
    """每请求 sleep {delay} 的本地 HTTP 服务(daemon 线程,随测试进程走)。"""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(delay)
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"pong")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def _write_case(path: Path, port: int, steps: int) -> None:
    step = {"kind": "step",
            "call": {"protocol": "http", "service": "slow",
                     "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [{"kind": "assertion",
                          "target": "$.call.response.status",
                          "operator": "eq", "expected": 200}]}
    case = {"kind": "scenario", "scenarioId": "sc-launch-selfexit",
            "meta": {"name": "launch-selfexit"},
            "config": {"services": {"slow": f"http://127.0.0.1:{port}"},
                       "users": {}, "timePolicy": {"kind": "record"}},
            "resource": {}, "steps": [dict(step) for _ in range(steps)]}
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")


def _spawn(case: Path, *, stdin_pipe: bool) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "gimbal", "run", "launch", str(case),
         "-o", "jsonl"],
        stdin=subprocess.PIPE if stdin_pipe else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )


def test_launch_stdin_eof_cancels_at_step_boundary(tmp_path: Path) -> None:
    """stdin EOF(=父进程死亡)→ 协作取消,远早于自然跑完。"""
    port = _free_port()
    _start_slow_server(port)
    case = tmp_path / "case12.json"
    _write_case(case, port, steps=12)          # 自然 ≈13s

    proc = _spawn(case, stdin_pipe=True)
    assert proc.stdin is not None and proc.stdout is not None
    first = proc.stdout.readline()             # run.start 已流出 → 在跑
    assert b"run.start" in first, first

    t_eof = time.monotonic()
    proc.stdin.close()                         # 父进程死亡的最小模拟
    # 在飞请求(≤1s)跑完 + 步骤边界取消 + 收尾 —— 预期 ~2-4s;
    # 守卫失效则是「盲跑僵尸」:剩余 ~11 步 ≥11s(上限放 8s 判定)
    try:
        proc.wait(timeout=8.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)
        raise AssertionError(
            "stdin EOF 后 launch 孤儿 8s 内未退出 —— 协作取消守卫失效"
            "(盲跑僵尸回归)")
    assert time.monotonic() - t_eof < 8.0


def test_launch_devnull_stdin_runs_to_completion(tmp_path: Path) -> None:
    """stdin 非 FIFO 不布防:同链路正常跑完,守卫不误伤。"""
    port = _free_port()
    _start_slow_server(port)
    case = tmp_path / "case3.json"
    _write_case(case, port, steps=3)           # ~3-4s

    proc = _spawn(case, stdin_pipe=False)
    try:
        rc = proc.wait(timeout=60.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)
        raise AssertionError("launch 正常路径 60s 未跑完 —— 与守卫无关的故障")
    assert rc == 0, f"3 步全过用例应 rc=0,得到 {rc}"
