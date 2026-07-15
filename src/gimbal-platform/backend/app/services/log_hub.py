"""Per-run log fan-out hub.

The hub is an in-process singleton that brokers log lines between the
subprocess producer (``_run_one`` in executor.py) and zero-or-more SSE
consumers (one per ``GET /runs/{rid}/log/stream`` connection).

Design constraints:

* **Single producer, multiple consumers** — each ``Channel`` has exactly
  one owner writing lines (the orchestrator thread that wraps
  ``Popen.readline``), and any number of subscribers receiving copies.
  Fan-out uses one ``asyncio.Queue`` per subscriber; the producer side
  is async-safe via ``loop.call_soon_threadsafe``.

* **Thread-safe history** — the readline thread runs in a plain OS
  thread (subprocess.Popen), not in the asyncio loop.  All mutations
  to ``_history`` / ``_subs`` from that thread are protected by
  ``_lock`` and routed through the event loop for subscriber queues.

* **Backpressure** — when a subscriber queue is full we drop the slow
  consumer (``self._subs.remove(q)``) rather than block the producer.
  Blocking the producer would back up the subprocess's pipe and
  eventually deadlock.  Counter is exposed via ``stats()``.

* **Late join replay** — when a SSE consumer subscribes after the run
  has finished, the channel's ``mark_done`` path replays the
  persisted disk log into ``_history`` so the new subscriber sees the
  full output before the ``end`` event.

* **TTL eviction** — DONE channels older than ``LOG_HUB_TTL_HOURS``
  are reaped by the background sweeper started in ``main.lifespan``.
  In-flight channels (subscribers > 0 OR ``_done`` is False) are
  preserved regardless of age.

* **Single-process only** — uvicorn must run with a single worker.  See
  ``docs/PLATFORM_REQUIREMENTS.md`` for the deployment contract.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Literal

StreamKind = Literal["stdout", "stderr"]

# Tunables — exposed as module constants so tests can override.
HISTORY_CAP = 10_000          # max lines kept in memory for replay
SUBSCRIBER_CAP = 50           # max concurrent SSE connections per channel
SUBSCRIBER_QUEUE_SIZE = 2_000 # backpressure window per subscriber


@dataclass(slots=True)
class RunLogLine:
    """A single line produced by the subprocess.

    ``text`` preserves the trailing ``\\n`` (and any embedded ``\\r``)
    so the frontend can render progress-bar-style updates verbatim.
    """
    kind: StreamKind
    seq: int          # monotonic, monotonic across both stdout+stderr
    text: str

    def to_sse(self) -> str:
        # SSE data must be on a single line; newlines in JSON strings are
        # valid JSON (escaped) so we just json.dumps the whole thing.
        # The ``id:`` line is what makes ``Last-Event-ID`` resume work
        # on the client (browsers send it back automatically on reconnect).
        import json
        return (
            f"id: {self.seq}\n"
            f"event: {self.kind}\n"
            f"data: {json.dumps({'seq': self.seq, 'text': self.text}, ensure_ascii=False)}\n\n"
        )


@dataclass(slots=True)
class EndEvent:
    """Sent when the run's subprocess exits (success / failure / timeout)."""
    exit_code: int
    seq: int = 0  # monotonic counter; included in the SSE id line

    def to_sse(self) -> str:
        import json
        return (
            f"id: {self.seq}\n"
            f"event: end\n"
            f"data: {json.dumps({'exit_code': self.exit_code})}\n\n"
        )


@dataclass(slots=True)
class KeepAlive:
    """SSE comment line; not a real event, just keeps proxies awake."""
    def to_sse(self) -> str:
        return ": keep-alive\n\n"


@dataclass
class _Channel:
    """One channel per ``(execution_id, run_id)`` pair."""

    execution_id: int
    run_id: int
    _history: Deque[RunLogLine] = field(default_factory=deque)
    _subs: list[asyncio.Queue] = field(default_factory=list)
    _seq: int = 0
    _done: bool = False
    _exit_code: int | None = None
    # Stored EndEvent so late subscribers can see the terminal signal.
    _terminal: EndEvent | None = None
    # Wall-clock seconds when mark_done fired.  Used by the TTL
    # sweeper to decide whether the channel is eligible for eviction.
    _done_at: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ── producer side (called from the readline thread) ────────────
    def publish_from_thread(self, kind: StreamKind, text: str, loop: asyncio.AbstractEventLoop) -> None:
        """Append a line, fan out to subscribers.  Called from any thread.

        The actual ``put_nowait`` is scheduled via ``call_soon_threadsafe``
        so subscribers' queues are mutated only on the asyncio loop.
        """
        with self._lock:
            self._seq += 1
            line = RunLogLine(kind=kind, seq=self._seq, text=text)
            self._history.append(line)
            # Trim history.  ``deque`` has O(1) popleft so this is cheap.
            while len(self._history) > HISTORY_CAP:
                self._history.popleft()
            subs_snapshot = list(self._subs)
            at_cap = len(self._subs) >= SUBSCRIBER_CAP
        for q in subs_snapshot:
            loop.call_soon_threadsafe(self._enqueue, q, line)
        if at_cap:
            # Don't accept new subscribers until something drops.
            pass  # subscribe() checks the cap itself

    def mark_done_from_thread(self, exit_code: int, loop: asyncio.AbstractEventLoop,
                              log_file: Path | None = None) -> None:
        """Mark the channel as finished.  If no history (e.g. subprocess
        emitted nothing), try to replay from the persisted disk log so
        late SSE subscribers still get the full output."""
        with self._lock:
            if log_file and log_file.exists() and not self._history:
                try:
                    raw = log_file.read_text(encoding="utf-8", errors="replace")
                    # The on-disk format is one chunk delimited by
                    # `# command:` / `===== STDOUT =====` / `===== STDERR =====`.
                    # Best-effort: treat everything after "===== STDOUT ====="
                    # as stdout, after "===== STDERR =====" as stderr.
                    self._replay_disk_log(raw)
                except Exception:  # noqa: BLE001  never let disk read crash the run
                    pass
            self._done = True
            self._exit_code = exit_code
            self._done_at = time.monotonic()
            # Bump seq so the EndEvent's id is strictly greater than the
            # last replayed/streamed line.
            self._seq += 1
            end = EndEvent(exit_code=exit_code, seq=self._seq)
            self._terminal = end  # late subscribers replay this too
            subs_snapshot = list(self._subs)
        for q in subs_snapshot:
            loop.call_soon_threadsafe(self._enqueue, q, end)

    def _replay_disk_log(self, raw: str) -> None:
        """Best-effort: split the disk log into stdout/stderr sections
        and append to history.  Falls back to treating everything as
        stdout if the section markers aren't found."""
        stdout_marker = "===== STDOUT ====="
        stderr_marker = "===== STDERR ====="
        stdout_idx = raw.find(stdout_marker)
        stderr_idx = raw.find(stderr_marker)
        if stdout_idx == -1 and stderr_idx == -1:
            # No markers — treat as one stdout blob, one line at a time.
            for ln in raw.splitlines():
                self._seq += 1
                self._history.append(RunLogLine(kind="stdout", seq=self._seq, text=ln + "\n"))
            return
        # Everything between markers goes to the matching stream.
        # Boundary is "after the marker line" — we strip the marker line
        # itself from the section content so it doesn't show up in the
        # replayed history.
        if stdout_idx != -1 and stderr_idx != -1:
            if stdout_idx < stderr_idx:
                stdout_section = raw[stdout_idx + len(stdout_marker):stderr_idx]
                stderr_section = raw[stderr_idx + len(stderr_marker):]
            else:
                stderr_section = raw[stderr_idx + len(stderr_marker):stdout_idx]
                stdout_section = raw[stdout_idx + len(stdout_marker):]
        elif stdout_idx != -1:
            stdout_section = raw[stdout_idx + len(stdout_marker):]
            stderr_section = ""
        else:
            stdout_section = ""
            stderr_section = raw[stderr_idx + len(stderr_marker):]

        # Skip the marker lines themselves (first line of each section).
        for section, kind in (
            (stdout_section, "stdout"),
            (stderr_section, "stderr"),
        ):
            lines = section.splitlines(keepends=True)
            for ln in lines:
                # Drop empty lines (they're the newline right after the
                # `===== ... =====` marker, not real subprocess output).
                if not ln.strip():
                    continue
                self._seq += 1
                normalized = ln if ln.endswith("\n") else ln + "\n"
                self._history.append(RunLogLine(kind=kind, seq=self._seq, text=normalized))

    # ── consumer side (called from the asyncio loop) ───────────────
    def _enqueue(self, q: asyncio.Queue, item) -> None:
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            # Slow consumer: drop the subscriber (not just the message)
            # so the next publish doesn't repeatedly fail.  Subscriber
            # SSE generator will notice via timeout and close.
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> tuple[asyncio.Queue, list[RunLogLine], bool]:
        """Register a new SSE consumer.

        Returns ``(queue, replay_history, is_done)``.  The replay history
        is the channel's full line buffer at subscribe time, so the
        consumer can flush it before going live.

        If the channel is already done, the terminal ``EndEvent`` is
        pushed onto the new subscriber's queue so the consumer sees it
        without polling ``stats()``.
        """
        with self._lock:
            if len(self._subs) >= SUBSCRIBER_CAP:
                raise RuntimeError("subscriber cap reached for this run's log channel")
            q: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
            self._subs.append(q)
            replay = list(self._history)
            done = self._done
            terminal = self._terminal
        if terminal is not None:
            loop.call_soon_threadsafe(self._enqueue, q, terminal)
        return q, replay, done

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def stats(self) -> dict:
        with self._lock:
            return {
                "history_lines": len(self._history),
                "subscribers": len(self._subs),
                "done": self._done,
                "exit_code": self._exit_code,
                "done_at": self._done_at,
                "seq": self._seq,
            }

    def next_seq(self) -> int:
        """Return the next seq number without consuming one.

        Used by callers (e.g. the SSE endpoint) that want to emit a
        synthetic EndEvent with a seq strictly greater than any
        previously published line.
        """
        with self._lock:
            return self._seq + 1


class LogHub:
    """Process-wide broker.  Module-level singleton is exported below."""

    def __init__(self) -> None:
        self._channels: dict[tuple[int, int], _Channel] = {}
        self._lock = threading.Lock()

    def get_or_create(self, execution_id: int, run_id: int) -> _Channel:
        with self._lock:
            key = (execution_id, run_id)
            ch = self._channels.get(key)
            if ch is None:
                ch = _Channel(execution_id=execution_id, run_id=run_id)
                self._channels[key] = ch
            return ch

    def drop(self, execution_id: int, run_id: int) -> None:
        """Free memory after the run is well past the SSE window.

        Currently unused — channels are kept indefinitely so a user
        who opens the log dialog 10 minutes later still sees history.
        Add a TTL eviction worker in V2 if memory becomes a concern.
        """
        with self._lock:
            self._channels.pop((execution_id, run_id), None)

    def sweep(self, ttl_seconds: float) -> int:
        """Drop DONE channels older than ``ttl_seconds`` wall-clock.

        Returns the count of evicted channels.  In-flight channels
        (subscribers > 0 or ``done=False``) are NEVER reaped — the
        TTL only applies to channels that have already streamed their
        terminal ``end`` event AND have no live subscribers.

        If ``ttl_seconds`` is 0 or negative the sweep is a no-op
        (channels kept until process exit).
        """
        if ttl_seconds <= 0:
            return 0
        now = time.monotonic()
        evicted = 0
        # Snapshot keys under lock; eviction itself doesn't strictly
        # need the lock (drop() takes its own) but it's safer.
        with self._lock:
            targets: list[tuple[int, int]] = []
            for key, ch in self._channels.items():
                stats = ch.stats()
                if (
                    stats["done"]
                    and stats["subscribers"] == 0
                    and stats["done_at"] > 0
                    and (now - stats["done_at"]) >= ttl_seconds
                ):
                    targets.append(key)
            for key in targets:
                self._channels.pop(key, None)
                evicted += 1
        return evicted

    def stats(self) -> dict:
        with self._lock:
            return {
                "channel_count": len(self._channels),
                "channels": [
                    {"execution_id": k[0], "run_id": k[1], **self._channels[k].stats()}
                    for k in list(self._channels.keys())[:50]  # cap sample size
                ],
            }


# Module singleton.  Imported by executor.py (producer) and
# routers/executions.py (consumer).
hub = LogHub()