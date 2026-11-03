"""server 进程自守卫的判定面(2026-11-03 执行器泄漏复盘)。

真子进程 e2e(stdin EOF 自退/空闲 TTL 自退)在 tests/integration/
test_server_selfexit.py;本文件只钉纯判定,毫秒级:

- ``proc_guard.stdin_is_pipe``(server/launch 两链共用):只有管道才
  布防 EOF 守卫 —— devnull(立即 EOF)/普通文件(读完 EOF)/非 fd 都
  不得布防,否则手动运行与 pytest 捕获 stdin 的场景一启动就自退;
- ``server._idle_should_exit``:在飞 run 挡住 TTL;最近活动未到 TTL
  挡住;timeout≤0 恒不退(开关关闭)。状态面来自 server_debug 挂的
  app.state(runs_registry/runs_lock/runs_last_activity)。
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from types import SimpleNamespace

from gimbal.core.proc_guard import stdin_is_pipe
from gimbal.core.server import _idle_should_exit


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
