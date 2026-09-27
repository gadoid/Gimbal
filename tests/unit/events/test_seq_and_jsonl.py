"""批次 F-2c 测试：Event seq 单调 + stdout jsonl 事件流（E2 v2 契约）。"""
import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.events.bus import InMemoryEventBus
from gimbal.events.types import RunFinishedEvent, StepStartEvent


class TestEventSeq:
    """v2 §5 信封：seq 总线锁内分配，跨线程单调。"""

    def test_serial_monotonic(self):
        bus = InMemoryEventBus()
        got = []
        bus.subscribe(lambda e: got.append(e), "step.start")
        for i in range(10):
            bus.publish(StepStartEvent(step_id=f"s{i}", step_name=f"n{i}"))
        seqs = [e.seq for e in got]
        assert seqs == list(range(1, 11))

    def test_concurrent_unique_contiguous(self):
        bus = InMemoryEventBus()
        got = []
        got_lock = threading.Lock()

        def handler(e):
            with got_lock:
                got.append(e)

        bus.subscribe(handler, "step.start")

        def pub(n):
            for i in range(25):
                bus.publish(StepStartEvent(step_id=f"t{n}-{i}", step_name="x"))

        threads = [threading.Thread(target=pub, args=(n,)) for n in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        seqs = [e.seq for e in got]
        assert len(seqs) == 100
        assert len(set(seqs)) == 100          # 唯一
        assert sorted(seqs) == list(range(1, 101))   # 连续（1..100）

    def test_default_zero_without_bus(self):
        e = StepStartEvent(step_id="x", step_name="x")
        assert e.seq == 0

    def test_run_finished_event_shape(self):
        ev = RunFinishedEvent(
            exit_code=0, total=3, passed=2, failed=1,
            details=[{"scenario_id": "a", "status": "passed"}],
        )
        assert ev.event_type == "run.finished"
        d = ev.model_dump(mode="json")
        assert d["exit_code"] == 0 and d["total"] == 3
        assert "blocked" in d and "repaired" in d


class TestJsonlSink:
    """attach_jsonl_sink：全事件订阅 → stdout 逐行 JSON。"""

    def test_sink_prints_events_with_seq(self, capsys):
        from gimbal.cli.common import attach_jsonl_sink
        bus = InMemoryEventBus()
        sub_id = attach_jsonl_sink(bus)
        try:
            bus.publish(StepStartEvent(step_id="s1", step_name="n1"))
            bus.publish(StepStartEvent(step_id="s2", step_name="n2"))
        finally:
            bus.unsubscribe(sub_id)
        out = capsys.readouterr().out
        lines = [json.loads(l) for l in out.strip().splitlines() if l.strip()]
        assert len(lines) == 2
        assert lines[0]["event_type"] == "step.start"
        assert lines[0]["seq"] == 1 and lines[1]["seq"] == 2

    def test_sink_handles_non_pydantic_event(self, capsys):
        from gimbal.cli.common import attach_jsonl_sink
        bus = InMemoryEventBus()
        sub_id = attach_jsonl_sink(bus)
        try:

            class Bare:
                event_type = "bare"

            bus.publish(Bare())
        finally:
            bus.unsubscribe(sub_id)
        out = capsys.readouterr().out
        assert json.loads(out.strip())["event_type"] == "bare"
