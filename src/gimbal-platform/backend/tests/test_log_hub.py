"""Tests for the LogHub + Channel log fan-out.

Verifies the in-process pub/sub mechanics that back the SSE log stream.
The actual SSE endpoint lives in ``test_executions.py``.
"""
from __future__ import annotations

import asyncio
import threading

import pytest

from app.services.log_hub import (
    HISTORY_CAP,
    SUBSCRIBER_CAP,
    SUBSCRIBER_QUEUE_SIZE,
    EndEvent,
    KeepAlive,
    LogHub,
    RunLogLine,
    _Channel,
)


@pytest.fixture
def hub() -> LogHub:
    return LogHub()


@pytest.fixture
def channel(hub: LogHub):
    return hub.get_or_create(execution_id=1, run_id=100)


# ── Channel basic publish / subscribe ─────────────────────────
async def test_subscribe_returns_empty_replay_when_no_history(channel) -> None:
    q, replay, done = channel.subscribe(asyncio.get_running_loop())
    assert replay == []
    assert done is False
    channel.unsubscribe(q)


async def test_publish_then_subscribe_replays_history(channel) -> None:
    loop = asyncio.get_running_loop()
    channel.publish_from_thread("stdout", "first\n", loop)
    channel.publish_from_thread("stderr", "boom\n", loop)

    q, replay, done = channel.subscribe(loop)
    try:
        assert done is False
        assert len(replay) == 2
        assert replay[0].kind == "stdout"
        assert replay[0].text == "first\n"
        assert replay[1].kind == "stderr"
        assert replay[1].text == "boom\n"
        # Monotonic seq across both streams.
        assert replay[0].seq < replay[1].seq
    finally:
        channel.unsubscribe(q)


async def test_subscriber_receives_live_lines(channel) -> None:
    loop = asyncio.get_running_loop()
    q, _replay, done = channel.subscribe(loop)
    try:
        channel.publish_from_thread("stdout", "live-1\n", loop)
        item = await asyncio.wait_for(q.get(), timeout=2.0)
        assert isinstance(item, RunLogLine)
        assert item.text == "live-1\n"

        channel.publish_from_thread("stderr", "live-err\n", loop)
        item = await asyncio.wait_for(q.get(), timeout=2.0)
        assert item.kind == "stderr"
        assert item.text == "live-err\n"
    finally:
        channel.unsubscribe(q)


# ── mark_done flow ─────────────────────────────────────────────
async def test_mark_done_emits_end_event_to_live_subscribers(channel) -> None:
    loop = asyncio.get_running_loop()
    q, _replay, _done = channel.subscribe(loop)
    try:
        channel.mark_done_from_thread(exit_code=42, loop=loop)
        item = await asyncio.wait_for(q.get(), timeout=2.0)
        assert isinstance(item, EndEvent)
        assert item.exit_code == 42
        # Second subscribe sees done=True.
        q2, replay, done = channel.subscribe(loop)
        try:
            assert done is True
            assert len(replay) == 0  # no history before done
        finally:
            channel.unsubscribe(q2)
    finally:
        channel.unsubscribe(q)


async def test_mark_done_with_disk_replay_replays_into_history(channel, tmp_path) -> None:
    """When the subprocess emitted lines that were never live-streamed
    (no subscribers at the time), mark_done replays from disk so late
    joiners still see the full output."""
    log_file = tmp_path / "run.log"
    # Mirror the format produced by _write_run_log_header / streaming.
    log_file.write_text(
        "# gimbal run log\n"
        "# command:\ngimbal run launch foo.yaml\n"
        "\n"
        "===== STDOUT =====\n"
        "line-from-stdout-A\n"
        "line-from-stdout-B\n"
        "===== STDERR =====\n"
        "line-from-stderr\n",
        encoding="utf-8",
    )

    loop = asyncio.get_running_loop()
    channel.mark_done_from_thread(exit_code=0, loop=loop, log_file=log_file)
    q, replay, done = channel.subscribe(loop)
    try:
        assert done is True
        # 2 stdout + 1 stderr = 3 lines.
        assert len(replay) == 3
        assert [l.kind for l in replay] == ["stdout", "stdout", "stderr"]
        assert [l.text.strip() for l in replay] == [
            "line-from-stdout-A",
            "line-from-stdout-B",
            "line-from-stderr",
        ]
    finally:
        channel.unsubscribe(q)


# ── Backpressure: slow consumer gets dropped ───────────────────
async def test_slow_consumer_is_dropped_after_queue_overflow(channel) -> None:
    loop = asyncio.get_running_loop()
    q, _replay, _done = channel.subscribe(loop)
    try:
        # Publish more than SUBSCRIBER_QUEUE_SIZE lines without consumer reads.
        for i in range(SUBSCRIBER_QUEUE_SIZE + 50):
            channel.publish_from_thread("stdout", f"line-{i}\n", loop)
        # Give the loop ticks to run the scheduled enqueue callbacks,
        # which will eventually raise QueueFull and drop the subscriber.
        for _ in range(10):
            await asyncio.sleep(0)
        # After overflow, the channel should have dropped the subscriber.
        stats = channel.stats()
        assert stats["subscribers"] == 0, (
            f"slow consumer should be dropped after overflow, "
            f"got subscribers={stats['subscribers']}"
        )
    finally:
        channel.unsubscribe(q)


# ── Subscriber cap ────────────────────────────────────────────
def test_subscriber_cap_rejects_excess(hub: LogHub) -> None:
    ch = hub.get_or_create(2, 200)
    # Manually fill _subs to cap (the lock is held during subscribe).
    # Use a single-loop run so the subscribe() coroutines can complete.
    asyncio.run(_fill_subscriber_cap(ch))


async def _fill_subscriber_cap(ch) -> None:
    loop = asyncio.get_running_loop()
    qs = []
    for _ in range(SUBSCRIBER_CAP):
        q, _replay, _done = ch.subscribe(loop)
        qs.append(q)
    with pytest.raises(RuntimeError, match="subscriber cap reached"):
        ch.subscribe(loop)
    for q in qs:
        ch.unsubscribe(q)


# ── History cap trimming ──────────────────────────────────────
async def test_history_trims_to_cap(channel) -> None:
    loop = asyncio.get_running_loop()
    for i in range(HISTORY_CAP + 100):
        channel.publish_from_thread("stdout", f"line-{i}\n", loop)
    q, replay, _done = channel.subscribe(loop)
    try:
        assert len(replay) == HISTORY_CAP
        # First surviving line is the (HISTORY_CAP)th line we published (0-indexed).
        assert replay[0].text == f"line-100\n"
        assert replay[-1].text == f"line-{HISTORY_CAP + 99}\n"
    finally:
        channel.unsubscribe(q)


# ── Thread-safety: hammer from many threads ────────────────────
async def test_publish_from_many_threads_does_not_lose_lines(channel) -> None:
    loop = asyncio.get_running_loop()
    # NOTE: subscribe() before publishing captures an initial-empty replay.
    # We instead inspect history directly after the threads join, since
    # history is the source of truth for "did every publish land somewhere".
    N_THREADS = 8
    N_PER_THREAD = 200

    def worker(tid: int) -> None:
        for i in range(N_PER_THREAD):
            channel.publish_from_thread("stdout", f"t{tid}-{i}\n", loop)

    threads = [
        threading.Thread(target=worker, args=(t,))
        for t in range(N_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Drain whatever is in the queue (call_soon_threadsafe callbacks).
    for _ in range(5):
        await asyncio.sleep(0)
    while not channel._history:  # noqa: SLF001 — read internal state for assertion
        await asyncio.sleep(0)
        break

    # History has every published line (total < HISTORY_CAP, no trim).
    history_seq = [line.seq for line in channel._history]  # noqa: SLF001
    assert len(history_seq) == N_THREADS * N_PER_THREAD
    assert history_seq == sorted(history_seq)
    assert history_seq[0] == 1
    assert history_seq[-1] == N_THREADS * N_PER_THREAD
    # No gaps in the seq sequence.
    assert history_seq == list(range(1, N_THREADS * N_PER_THREAD + 1))


# ── Hub lookup ─────────────────────────────────────────────────
async def test_hub_get_or_create_returns_same_instance(hub: LogHub) -> None:
    a = hub.get_or_create(1, 1)
    b = hub.get_or_create(1, 1)
    assert a is b
    c = hub.get_or_create(1, 2)
    assert c is not a


def test_hub_drop_clears_channel(hub: LogHub) -> None:
    ch = hub.get_or_create(1, 1)
    hub.drop(1, 1)
    assert (1, 1) not in hub._channels  # noqa: SLF001 — internal access for test
    # Re-get creates a fresh channel.
    fresh = hub.get_or_create(1, 1)
    assert fresh is not ch
    _ = ch  # silence unused


# ── TTL eviction ──────────────────────────────────────
async def test_sweep_drops_done_channels_past_ttl(hub: LogHub) -> None:
    loop = asyncio.get_running_loop()
    ch = hub.get_or_create(50, 500)
    ch.publish_from_thread("stdout", "x\n", loop)
    ch.mark_done_from_thread(exit_code=0, loop=loop)
    # Backdate the done timestamp so the channel looks ancient.
    ch._done_at -= 9999  # noqa: SLF001
    evicted = hub.sweep(ttl_seconds=1.0)
    assert evicted == 1
    assert (50, 500) not in hub._channels  # noqa: SLF001


async def test_sweep_preserves_recent_done_channels(hub: LogHub) -> None:
    """A channel marked done moments ago must NOT be reaped even if
    it's been marked done for some time — the TTL only kicks in once
    the channel has been idle for the configured duration."""
    loop = asyncio.get_running_loop()
    ch = hub.get_or_create(60, 600)
    ch.publish_from_thread("stdout", "x\n", loop)
    ch.mark_done_from_thread(exit_code=0, loop=loop)
    # _done_at is "just now" (monotonic at mark_done time) → must survive.
    evicted = hub.sweep(ttl_seconds=3600.0)
    assert evicted == 0
    assert (60, 600) in hub._channels  # noqa: SLF001


async def test_sweep_preserves_in_flight_channels(hub: LogHub) -> None:
    """Channels with subscribers must NEVER be reaped, regardless of TTL,
    because dropping them mid-stream would orphan live SSE connections."""
    loop = asyncio.get_running_loop()
    ch = hub.get_or_create(70, 700)
    ch.publish_from_thread("stdout", "x\n", loop)
    ch.mark_done_from_thread(exit_code=0, loop=loop)
    ch._done_at -= 9999  # noqa: SLF001 — backdate
    # Attach a live subscriber.
    sub_q, _replay, _done = ch.subscribe(loop)
    try:
        evicted = hub.sweep(ttl_seconds=1.0)
        assert evicted == 0, "in-flight channel must survive TTL sweep"
        assert (70, 700) in hub._channels  # noqa: SLF001
    finally:
        ch.unsubscribe(sub_q)


async def test_sweep_preserves_not_done_channels(hub: LogHub) -> None:
    """A channel still receiving live output is never reaped."""
    loop = asyncio.get_running_loop()
    ch = hub.get_or_create(80, 800)
    ch.publish_from_thread("stdout", "x\n", loop)
    # Do NOT mark done — channel is still in flight.
    ch._done_at -= 9999  # noqa: SLF001
    evicted = hub.sweep(ttl_seconds=1.0)
    assert evicted == 0
    assert (80, 800) in hub._channels  # noqa: SLF001


async def test_sweep_zero_ttl_is_noop(hub: LogHub) -> None:
    """ttl_seconds <= 0 disables eviction entirely."""
    loop = asyncio.get_running_loop()
    ch = hub.get_or_create(90, 900)
    ch.publish_from_thread("stdout", "x\n", loop)
    ch.mark_done_from_thread(exit_code=0, loop=loop)
    ch._done_at -= 9999  # noqa: SLF001
    evicted = hub.sweep(ttl_seconds=0)
    assert evicted == 0
    evicted = hub.sweep(ttl_seconds=-1)
    assert evicted == 0


# ── SSE frame format ───────────────────────────────────────────
def test_run_log_line_to_sse_format() -> None:
    line = RunLogLine(kind="stdout", seq=7, text="hello\n")
    out = line.to_sse()
    assert out == 'id: 7\nevent: stdout\ndata: {"seq": 7, "text": "hello\\n"}\n\n'


def test_end_event_to_sse_format() -> None:
    out = EndEvent(exit_code=0, seq=42).to_sse()
    assert out == 'id: 42\nevent: end\ndata: {"exit_code": 0}\n\n'


def test_run_log_line_to_sse_includes_id_line() -> None:
    line = RunLogLine(kind="stdout", seq=99, text="x")
    out = line.to_sse()
    # The ``id:`` line is what makes Last-Event-ID resume work.
    assert out.startswith("id: 99\n")
    assert "event: stdout" in out
    assert '"seq": 99' in out


def test_next_seq_returns_one_past_current() -> None:
    """next_seq() lets the SSE endpoint emit a synthetic EndEvent with
    a seq strictly greater than any previously published line."""
    loop = asyncio.new_event_loop()
    try:
        ch = _Channel(execution_id=1, run_id=1)
        assert ch.next_seq() == 1
        ch.publish_from_thread("stdout", "a\n", loop)
        ch.publish_from_thread("stderr", "b\n", loop)
        assert ch.next_seq() == 3  # two publishes bumped seq to 2
    finally:
        loop.close()


async def test_mark_done_bumps_seq_past_history() -> None:
    """EndEvent's seq must be > last published line, so a client
    reconnecting with Last-Event-ID == last_seq won't miss the end."""
    loop = asyncio.get_running_loop()
    ch = _Channel(execution_id=1, run_id=1)
    ch.publish_from_thread("stdout", "a\n", loop)
    ch.publish_from_thread("stdout", "b\n", loop)
    ch.mark_done_from_thread(exit_code=0, loop=loop)

    # Replay (returned separately) carries the two lines; the queue
    # only carries the terminal EndEvent that subscribe() schedules.
    q, replay, _done = ch.subscribe(loop)
    try:
        assert len(replay) == 2
        assert replay[-1].seq == 2
        item = await asyncio.wait_for(q.get(), timeout=2.0)
        assert isinstance(item, EndEvent)
        # EndEvent seq must be strictly greater than the last replay line.
        assert item.seq > replay[-1].seq
        assert item.exit_code == 0
    finally:
        ch.unsubscribe(q)


def test_keepalive_to_sse_format() -> None:
    out = KeepAlive().to_sse()
    # SSE comments start with ":" — keep-alive is a comment, not an event.
    assert out == ": keep-alive\n\n"