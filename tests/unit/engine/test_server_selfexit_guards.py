"""server 进程自守卫的判定面(2026-11-03 执行器泄漏复盘)。

真子进程 e2e(stdin EOF 自退/空闲 TTL 自退)在 tests/integration/
test_server_selfexit.py;本文件只钉纯判定,毫秒级:

- ``proc_guard.stdin_is_pipe``(server/launch 两链共用):只有管道才
  布防 EOF 守卫 —— devnull(立即 EOF)/普通文件(读完 EOF)/非 fd 都
  不得布防,否则手动运行与 pytest 捕获 stdin 的场景一启动就自退;
- ``server._idle_should_exit``:在飞 run 挡住 TTL;最近活动未到 TTL
  挡住;timeout≤0 恒不退(开关关闭)。状态面来自 server_debug 挂的
  app.state(runs_registry/runs_lock/runs_last_activity);
- ``server._cancel_inflight_runs``(评审 3.2,退出收口):有在飞 run 时
  置位 drain+cancel(与 POST cancel scope=step 同款)并等收口;等不到
  超宽限放行;无在飞 run 直接返回(空闲自退路径零开销)。
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from types import SimpleNamespace

from gimbal.core.proc_guard import stdin_is_pipe
from gimbal.core.server import _cancel_inflight_runs, _idle_should_exit


def test_stdin_is_pipe_true_for_fifo() -> None:
    r, w = os.pipe()
    try:
        assert stdin_is_pipe(r) is True
        assert stdin_is_pipe(w) is True
    finally:
        os.close(r)
        os.close(w)


def test_stdin_is_pipe_false_for_file_and_devnull() -> None:
    # 普通文件:读完即 EOF,不是「父进程死亡」信号
    with tempfile.NamedTemporaryFile() as f:
        assert stdin_is_pipe(f.fileno()) is False
    # /dev/null:字符设备,打开即 EOF;手动后台运行常见形态
    fd = os.open(os.devnull, os.O_RDONLY)
    try:
        assert stdin_is_pipe(fd) is False
    finally:
        os.close(fd)


def test_stdin_is_pipe_false_for_bad_fd() -> None:
    assert stdin_is_pipe(9999) is False


def _state_app(*, running: bool, idle_for: float) -> SimpleNamespace:
    """按 server_debug.register_debug_endpoints 的挂载面造假 app。"""
    return SimpleNamespace(state=SimpleNamespace(
        runs_registry={"r1": {"status": "running" if running else "finished"}},
        runs_lock=threading.Lock(),
        runs_last_activity=time.monotonic() - idle_for,
    ))


def test_idle_should_exit_requires_idle_and_beyond_ttl() -> None:
    app = _state_app(running=False, idle_for=1801.0)
    assert _idle_should_exit(app, 1800.0) is True


def test_idle_should_exit_blocked_by_recent_activity() -> None:
    app = _state_app(running=False, idle_for=10.0)
    assert _idle_should_exit(app, 1800.0) is False


def test_idle_should_exit_blocked_by_running_run() -> None:
    # 调试会话挂起也是 running —— 空闲再久也不退(在飞保护)
    app = _state_app(running=True, idle_for=99999.0)
    assert _idle_should_exit(app, 1800.0) is False


def test_idle_should_exit_disabled_when_timeout_zero() -> None:
    app = _state_app(running=False, idle_for=99999.0)
    assert _idle_should_exit(app, 0) is False


# ─── 退出收口(评审 3.2):在飞 run 协作取消后放行退出 ────────────────

def _run_app(*, with_events: bool = True) -> tuple[SimpleNamespace, dict]:
    """带一个 running 条目的假 app(事件面同 server_debug 注册形态)。"""
    entry: dict = {"status": "running"}
    if with_events:
        entry["cancel"] = threading.Event()
        entry["drain"] = threading.Event()
    app = SimpleNamespace(state=SimpleNamespace(
        runs_registry={"r1": entry},
        runs_lock=threading.Lock(),
        runs_last_activity=time.monotonic(),
    ))
    return app, entry


def test_cancel_inflight_runs_noop_when_idle() -> None:
    """无在飞 run(空闲自退路径)直接返回,不置任何事件。"""
    app = _state_app(running=False, idle_for=99999.0)
    t0 = time.monotonic()
    _cancel_inflight_runs(app, grace_sec=30.0)
    assert time.monotonic() - t0 < 0.5


def test_cancel_inflight_runs_sets_events_and_waits_for_wrapup() -> None:
    """在飞 run:置 drain+cancel(POST cancel scope=step 同款),等它收口。"""
    app, entry = _run_app()

    def _fake_run() -> None:
        assert entry["drain"].wait(timeout=5.0)      # 协作取消先到
        assert entry["cancel"].is_set()
        time.sleep(0.05)                             # 步骤边界收尾
        entry["status"] = "finished"

    worker = threading.Thread(target=_fake_run)
    worker.start()
    t0 = time.monotonic()
    _cancel_inflight_runs(app, grace_sec=10.0)       # 应在收口后即返回
    elapsed = time.monotonic() - t0
    worker.join(timeout=5.0)
    assert elapsed < 5.0, "run 已收口仍等满宽限 —— 收口探测失效"


def test_cancel_inflight_runs_gives_up_after_grace() -> None:
    """run 卡死不收口:到宽限即放行(有界等待,进程退出不陪葬)。"""
    app, _entry = _run_app()                         # status 恒 running
    t0 = time.monotonic()
    _cancel_inflight_runs(app, grace_sec=0.3)
    assert time.monotonic() - t0 >= 0.3


def test_cancel_inflight_runs_tolerates_legacy_entries() -> None:
    """旧形态条目(无 cancel/drain 键)不炸,仍进入等待面。"""
    app, entry = _run_app(with_events=False)
    t0 = time.monotonic()
    _cancel_inflight_runs(app, grace_sec=0.2)
    assert time.monotonic() - t0 >= 0.2              # 无事件可置 → 等满宽限
    assert entry["status"] == "running"
