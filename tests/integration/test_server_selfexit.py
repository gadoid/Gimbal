"""server 进程自守卫真子进程 e2e(2026-11-03 执行器泄漏复盘)。

背景:平台 spawn 的执行器只靠协作式 ``close()`` 回收,父进程被硬杀
(SIGKILL/Bash 超时/带会话退出)时无人 terminate,实测 21 个旧执行器以
PPID=1 空转两周(~1 GB)。core/server.py 现自带两道自退守卫,本文件
逐道实证 —— 真拉起 ``gimbal run server`` 子进程,验证**不调 close、
不递信号**也能自己优雅退出(exit code 0 = uvicorn should_exit 收口):

1. stdin EOF(父进程死亡的最小模拟:平台 spawn 时 ``stdin=PIPE``,
   父持有写端;写端一关,内核视角与父进程死亡不可区分);
2. 空闲 TTL(``--idle-timeout 2``,期间零请求 → 到点自退)。

父进程**真实**硬杀(平台 ServerSession + PDEATHSIG + stdin=PIPE 联防)
在 tests/integration/test_server_session_smoke.py 的
``test_server_session_parent_hard_death``(平台侧守卫面)。
"""
from __future__ import annotations

import socket
import subprocess
import sys
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
