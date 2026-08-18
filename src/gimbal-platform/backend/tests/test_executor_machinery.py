"""Unit tests for the executor's live-subprocess registry + log-file
handle lifecycle (2026-08 hardening pass).

These test the pure-process machinery directly (no DB, no HTTP) so the
shutdown-kill contract is pinned independently of the router layer.
"""
from __future__ import annotations

import threading
import time

from app.services import executor


class _FakeProc:
    """Duck-typed stand-in for subprocess.Popen — enough surface for the
    registry (poll/kill) without spawning real children."""

    def __init__(self) -> None:
        self.killed = False
        self.poll_result: int | None = None  # None = "still running"

    def poll(self) -> int | None:
        return self.poll_result

    def kill(self) -> None:
        if self.poll_result is None:
            self.killed = True
            self.poll_result = -9


def test_kill_all_kills_live_procs() -> None:
    p1, p2 = _FakeProc(), _FakeProc()
    with executor._live_procs_lock:
        executor._live_procs.add(p1)  # type: ignore[arg-type]
        executor._live_procs.add(p2)  # type: ignore[arg-type]

    killed = executor.kill_all_live_subprocesses()

    assert killed == 2
    assert p1.killed and p2.killed
    # Registry drained — a second pass is a no-op.
    assert executor.kill_all_live_subprocesses() == 0


def test_kill_all_skips_already_exited() -> None:
    dead = _FakeProc()
    dead.poll_result = 0  # exited cleanly before shutdown
    with executor._live_procs_lock:
        executor._live_procs.add(dead)  # type: ignore[arg-type]

    killed = executor.kill_all_live_subprocesses()

    assert killed == 0
    assert not dead.killed


def test_subprocess_run_streaming_closes_log_file(tmp_path) -> None:
    """The log-file handle must be closed when the streaming run returns
    (used to leak one fd per run).  Uses a real short-lived subprocess so
    the full pump/wait path is exercised."""
    log_path = tmp_path / "run_1.log"

    class _NullChannel:
        def publish_from_thread(self, *a, **k) -> None:  # noqa: ANN002
            pass

        def mark_done_from_thread(self, *a, **k) -> None:  # noqa: ANN002
            pass

    import asyncio

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            asyncio.to_thread(
                executor._subprocess_run_streaming,
                # Portable no-op command
                (["cmd", "/c", "echo hi"] if _is_windows() else ["echo", "hi"]),
                timeout=15,
                log_path=log_path,
                channel=_NullChannel(),
                loop=loop,
            )
        )
    finally:
        loop.close()

    assert result.exit_code == 0
    assert result.file_not_found is False
    # Log captured the line and the handle was closed (Windows: a closed
    # file can be re-opened/truncated; an open one would raise on the
    # footer write path — exercising _write_run_log_footer proves it).
    assert "hi" in log_path.read_text(encoding="utf-8")
    executor._write_run_log_footer(log_path, result.exit_code)
    assert "exit_code: 0" in log_path.read_text(encoding="utf-8")


def _is_windows() -> bool:
    import sys

    return sys.platform == "win32"
