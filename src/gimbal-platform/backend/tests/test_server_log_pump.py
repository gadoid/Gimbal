"""结构化日志批 1(骨干)_EventIngester 泵与缓冲机制单测。

覆盖设计 claude/structured-execution-logs-design.md 批 1 验收面:
- `_pump_stderr`(AD2/AD3):JSON 行回调 / 非 JSON 与低级别不入库 / 文件
  全量原始字节 / 回调异常不阻断泵 / 入库行零 ANSI;
- `_EventIngester` single-flight 锁(AD5 地基):慢 DB 下阈值 task 与直调
  flush 并发,同一时刻至多一个在途;
- `on_event`/`on_log` 只入队,慢 flush 不阻塞回调(DB 慢不传导到 stderr 管道);
- logs 缓冲上限(AD2):DB 长时间失败回填重试下丢最旧保最新,events 不设限。
"""
from __future__ import annotations

import asyncio
import json

import pytest


class _FakeStderr:
    """readline 形态的假 stderr:顺序吐行(带换行,如真管道)后 EOF。"""

    def __init__(self, lines: list[str]) -> None:
        self._lines = [ln.encode("utf-8") + b"\n" for ln in lines]

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


def _logline(level: str = "INFO", message: str = "hi", **extra) -> str:
    d = {"timestamp": "2026-10-14T01:00:00+00:00", "level": level,
         "logger": "gimbal.core.x", "category": "core",
         "message": message}
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


# ── 泵:_pump_stderr ─────────────────────────────────────────


async def test_pump_delivers_json_and_gates_level_and_file_gets_all(tmp_path):
    from app.services.gimbal_server_session import _pump_stderr

    log_path = tmp_path / "engine.log"
    got: list[dict] = []
    lines = [
        _logline("INFO", "keep-1", step="step-000"),
        _logline("DEBUG", "below-gate"),                 # 低于 INFO 门槛
        "\x1b[32mcolored non-json\x1b[0m",               # ANSI 行(非 JSON)
        "plain non-json",
        _logline("WARNING", "keep-2", step="step-002"),
        '{"no_level": true}',                            # JSON 但非日志行
    ]
    with log_path.open("w", encoding="utf-8", newline="") as fh:
        await _pump_stderr(_FakeStderr(lines), fh, got.append, "INFO")

    assert [d["message"] for d in got] == ["keep-1", "keep-2"]
    # 入库面零 ANSI(解析为 dict 即保证;回归闸仍显式断言)
    assert all("\x1b[" not in json.dumps(d, ensure_ascii=False) for d in got)
    # 文件面:全量原始字节(含 ANSI/非 JSON/低级别),审计兜底不受门槛影响
    file_text = log_path.read_text(encoding="utf-8")
    assert file_text.count("\n") == len(lines)
    assert "\x1b[32mcolored non-json\x1b[0m" in file_text
    assert '"below-gate"' in file_text


async def test_pump_callback_exception_does_not_kill_pump():
    from app.services.gimbal_server_session import _pump_stderr

    got: list[dict] = []

    def flaky(d: dict) -> None:
        if d["message"] == "boom":
            raise RuntimeError("callback exploded")
        got.append(d)

    await _pump_stderr(
        _FakeStderr([_logline(message="boom"), _logline(message="after")]),
        None, flaky, "INFO")
    assert [d["message"] for d in got] == ["after"]


async def test_pump_no_callback_only_writes_file(tmp_path):
    """on_log=None(server 链日志入库关闭的形态):文件照写,零回调。"""
    from app.services.gimbal_server_session import _pump_stderr

    log_path = tmp_path / "engine.log"
    with log_path.open("w", encoding="utf-8", newline="") as fh:
        await _pump_stderr(_FakeStderr([_logline(), "plain"]), fh, None, "INFO")
    assert log_path.read_text(encoding="utf-8").count("\n") == 2


# ── ingester:single-flight / 非阻塞 / 缓冲上限 ───────────────


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        pass


def _fake_db_factory():
    return lambda: _FakeSession()


def _mk_ingester(monkeypatch, *, insert_events=None, insert_logs=None):
    from app.services import execution_store
    from app.services.run_dispatcher import _EventIngester

    if insert_events is not None:
        monkeypatch.setattr(execution_store, "insert_events", insert_events)
    if insert_logs is not None:
        monkeypatch.setattr(execution_store, "insert_logs", insert_logs)
    return _EventIngester(_fake_db_factory(), execution_id=1)


async def test_flush_single_flight_under_slow_db(monkeypatch):
    """慢 DB 下阈值 task 与直调 flush(ticker 路径)并发 → 同时至多一个在途。

    回归闸:历史缺陷是 ticker 直调 `_flush` 绕过 `_pending` 互斥,两个事务
    并发时 PG 按 INSERT 时刻分 id、按提交时刻可见 → id cursor 下漏行。
    """
    state = {"cur": 0, "max": 0, "calls": 0}

    async def slow_insert(session, execution_id, events):
        state["cur"] += 1
        state["calls"] += 1
        state["max"] = max(state["max"], state["cur"])
        await asyncio.sleep(0.15)          # 模拟 DB 慢
        state["cur"] -= 1

    ing = _mk_ingester(monkeypatch, insert_events=slow_insert,
                       insert_logs=lambda *a, **k: asyncio.sleep(0))
    for i in range(250):                   # > 阈值 200 → 阈值 task 在途
        ing.on_event({"event_type": "step.end", "seq_offset": i})
    # 模拟 ticker 直调(不经 _maybe_flush 的在飞检查)
    await asyncio.gather(ing._flush(), ing._flush())
    await ing.finalize()

    assert state["calls"] >= 3             # 三路都真正落过
    assert state["max"] == 1, (
        f"并发 flush 在途数 {state['max']} > 1 —— single-flight 锁失效,"
        "执行内 id 单调(AD5 tail 地基)被破坏")


async def test_on_event_nonblocking_while_flush_slow(monkeypatch):
    """回调只入队:慢 flush 在途时 on_event 仍即时返回(泵不被 DB 慢卡住)。"""
    import time

    async def slow_insert(session, execution_id, events):
        await asyncio.sleep(0.3)

    ing = _mk_ingester(monkeypatch, insert_events=slow_insert,
                       insert_logs=lambda *a, **k: asyncio.sleep(0))
    for i in range(250):                   # 触发首个慢 flush
        ing.on_event({"event_type": "x"})
    t0 = time.perf_counter()
    ing.on_event({"event_type": "y"})      # flush 仍在途
    ing.on_log({"level": "INFO", "message": "z"})
    assert time.perf_counter() - t0 < 0.05
    await ing.finalize()


async def test_logs_buffer_cap_drops_oldest_on_persistent_failure(monkeypatch):
    """DB 持续失败回填重试 → 缓冲封顶 50k 丢最旧;events 不裁剪。"""
    async def failing_insert(session, *a, **k):
        raise RuntimeError("db down")

    ing = _mk_ingester(monkeypatch, insert_events=failing_insert,
                       insert_logs=failing_insert)
    ing.start()
    try:
        for i in range(ing._LOGS_BUF_CAP + 300):
            ing.on_log({"level": "INFO", "message": f"m-{i}"})
        await ing.finalize()               # 收尾 flush 同样失败并回填
    finally:
        ing._stopped = True

    assert len(ing._logs) == ing._LOGS_BUF_CAP
    # 丢最旧保最新:保住的是 m-300 .. m-(CAP+299)
    assert ing._logs[0]["message"] == "m-300"
    assert ing._logs[-1]["message"] == f"m-{ing._LOGS_BUF_CAP + 299}"
    assert ing.logs_dropped_overflow == 300
    # events 侧不设上限(台账不可丢)——本次只喂了日志,events 恒空
    assert ing._events == []


async def test_flush_success_flushes_both_axes(monkeypatch):
    """正常路径:事件与日志同事务落库(走 fake 收集,验证换出与批次)。"""
    seen: dict[str, list] = {"events": [], "logs": []}

    async def ev_insert(session, eid, events):
        seen["events"].extend(events)

    async def log_insert(session, eid, logs, *, seq_base):
        seen["logs"].extend(logs)

    ing = _mk_ingester(monkeypatch, insert_events=ev_insert,
                       insert_logs=log_insert)
    ing.on_event({"event_type": "step.end", "seq": 1})
    ing.on_log({"level": "WARNING", "message": "w"})
    await ing.finalize()
    assert len(seen["events"]) == 1 and len(seen["logs"]) == 1
    assert ing._events == [] and ing._logs == []
