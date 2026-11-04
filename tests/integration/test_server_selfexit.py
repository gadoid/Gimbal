"""server 进程自守卫真子进程 e2e(2026-11-03 执行器泄漏复盘)。

背景:平台 spawn 的执行器只靠协作式 ``close()`` 回收,父进程被硬杀
(SIGKILL/Bash 超时/带会话退出)时无人 terminate,实测 21 个旧执行器以
PPID=1 空转两周(~1 GB)。core/server.py 现自带两道自退守卫,本文件
逐道实证 —— 真拉起 ``gimbal run server`` 子进程,验证**不调 close、
不递信号**也能自己优雅退出(exit code 0 = uvicorn should_exit 收口):

1. stdin EOF(父进程死亡的最小模拟:平台 spawn 时 ``stdin=PIPE``,
   父持有写端;写端一关,内核视角与父进程死亡不可区分);
2. 空闲 TTL(``--idle-timeout 2``,期间零请求 → 到点自退)。

评审 3.2(2026-11-04)补第三条:停机时在飞 run 的收口 —— uvicorn 优雅
停机只等 HTTP 连接,不等 run 线程;若无退出收口钩子,进程退出即硬杀
daemon 执行线程,teardown/after 清理全丢。第三条用例:run 进行中关
stdin → 执行器必须**协作取消在飞 run**(主体停在步骤边界)且 **after
清理括号照跑**,然后优雅退出(rc=0)。

父进程**真实**硬杀(平台 ServerSession + PDEATHSIG + stdin=PIPE 联防)
在 tests/integration/test_server_session_smoke.py 的
``test_server_session_parent_hard_death``(平台侧守卫面)。
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_healthz(port: int, timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/healthz", timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:  # noqa: BLE001 — 未就绪期间的连接拒绝/超时都算等待
            time.sleep(0.15)
    raise AssertionError(f"server :{port} 未在 {timeout}s 内就绪")


def _spawn(port: int, *, stdin_pipe: bool, extra: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "gimbal", "run", "server",
         "--host", "127.0.0.1", "--port", str(port), *extra],
        stdin=subprocess.PIPE if stdin_pipe else subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _assert_exits(proc: subprocess.Popen, grace: float = 12.0) -> int:
    """到点必须已退;还活着则杀掉并失败(守卫失效即泄漏回归)。"""
    try:
        rc = proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)
        raise AssertionError(
            "执行器在触发条件满足后仍未自退 —— stdin/空闲守卫失效(泄漏回归)")
    assert rc == 0, f"自退必须是优雅退出(uvicorn should_exit),rc={rc}"
    return rc


def test_stdin_eof_selfexit() -> None:
    """stdin 管道写端关闭(=父进程死亡)→ 执行器自退(TTL 关闭,隔离本守卫)。"""
    port = _free_port()
    proc = _spawn(port, stdin_pipe=True, extra=["--idle-timeout", "0"])
    try:
        _wait_healthz(port)
        assert proc.stdin is not None
        proc.stdin.close()      # 父进程死亡的最小模拟:写端一关,EOF 即达
    finally:
        if proc.poll() is None and proc.stdin is not None and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
    _assert_exits(proc)


def test_idle_timeout_selfexit() -> None:
    """无 run 空闲超 TTL → 自退(stdin=DEVNULL 不布防,隔离本守卫)。"""
    port = _free_port()
    proc = _spawn(port, stdin_pipe=False, extra=["--idle-timeout", "2"])
    _wait_healthz(port)
    # 期间零请求;TTL=2s、看门狗自适应周期 1s → 预期 ~2-4s 退出
    _assert_exits(proc)


# ─── 评审 3.2(2026-11-04):停机时在飞 run 协作取消 + after 清理必达 ──

def test_shutdown_cancels_inflight_run_and_runs_after() -> None:
    """run 进行中收到停机信号 → 协作取消主体 + after 清理照跑 + 优雅退出。

    graph 用例:main = 8 步×1s 慢请求,after = 1 步 GET /cleanup。POST
    /runs 后 2.5s(run 在飞)关 stdin(父死最小模拟)→ should_exit 优雅
    停机 → 退出收口钩子置 drain+cancel。无钩子的旧形态:进程退出硬杀
    run 线程,/cleanup 永不打、/ping 打满 8 次;有钩子:主体停在步骤
    边界(/ping 远小于 8)、after 必达、rc=0。
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits: "list[str]" = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/cleanup":       # after 清理:即时返回
                hits.append(self.path)
                body = b"ok"
            else:                             # main 慢步骤:1s/请求
                time.sleep(1.0)
                hits.append(self.path)
                body = b"pong"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        slow_port = sk.getsockname()[1]
    srv = HTTPServer(("127.0.0.1", slow_port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def _scen(sid: str, path: str) -> dict:
        return {"kind": "scenario", "scenarioId": sid,
                "meta": {"name": sid},
                "config": {"services": {"slow": f"http://127.0.0.1:{slow_port}"},
                           "users": {}, "timePolicy": {"kind": "record"}},
                "resource": {},
                "steps": [{"kind": "step",
                           "call": {"protocol": "http", "service": "slow",
                                    "method": "GET", "path": path},
                           "request": {"kind": "request", "body": {}},
                           "strategy": [{"kind": "assertion",
                                         "target": "$.call.response.status",
                                         "operator": "eq",
                                         "expected": 200}]}]}

    main_scen = _scen("sc-shutdown-main", "/ping")
    main_scen["steps"] = [dict(main_scen["steps"][0]) for _ in range(8)]
    target = {"kind": "graph",
              "units": [{"ref": "main", "scenario": main_scen}],
              "after": [{"ref": "cleanup",
                         "scenario": _scen("sc-shutdown-after", "/cleanup")}]}

    port = _free_port()
    proc = _spawn(port, stdin_pipe=True, extra=["--idle-timeout", "0"])
    try:
        _wait_healthz(port)
        body = json.dumps({"target": target, "options": {}}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/runs", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            created = json.loads(r.read())
        assert r.status == 200 and created.get("runId")
        time.sleep(2.5)                 # run 在飞(bootstrap ~1-2s + 慢步骤)
        assert proc.stdin is not None
        proc.stdin.close()              # 父进程死亡的最小模拟 → 停机
    finally:
        if proc.poll() is None and proc.stdin is not None and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
    rc = _assert_exits(proc, grace=30.0)          # 优雅退出,非硬杀
    assert "/cleanup" in hits, (
        "停机后 after 清理(/cleanup)未执行 —— 退出收口钩子失效"
        "(在飞 run 被硬杀,被测系统留脏数据)")
    assert hits.count("/ping") < 8, (
        f"主体未被协作取消(8 步全跑完)—— 停机收口只等不取消: {hits}")
