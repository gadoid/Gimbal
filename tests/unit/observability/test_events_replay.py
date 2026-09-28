"""P1-05 事件导入与回放（gimbal events replay / query）。"""
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from typer.testing import CliRunner

from gimbal.cli.params import starter

runner = CliRunner()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonl(tmp_path, name="events.jsonl") -> str:
    """一份最小完整事件流：run.meta → scenario → step → run.finished（带判定）。"""
    lines = [
        {"event_type": "run.meta", "seq": 1, "timestamp": _now(),
         "meta": {"trigger": "test"}},
        {"event_type": "scenario.start", "seq": 2, "timestamp": _now(),
         "scenario_id": "sc-r", "scenario_name": "n", "step_count": 1},
        {"event_type": "step.start", "seq": 3, "timestamp": _now(),
         "step_id": "step-000", "step_name": "step-000", "scenario_id": "sc-r",
         "module": "m", "unit": "u-1", "attempt": "1.1"},
        {"event_type": "step.end", "seq": 4, "timestamp": _now(),
         "step_id": "step-000", "status": "passed", "duration_ms": 5.0,
         "scenario_id": "sc-r", "module": "m", "unit": "u-1", "attempt": "1.1"},
        {"event_type": "scenario.end", "seq": 5, "timestamp": _now(),
         "scenario_id": "sc-r", "status": "passed", "step_count": 1},
        {"event_type": "run.finished", "seq": 6, "timestamp": _now(),
         "exit_code": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0,
         "details": [{"scenario_id": "sc-r", "status": "passed",
                      "duration_ms": 5.0, "halted": False, "halt_reason": None,
                      "steps": [{"step_id": "step-000", "status": "passed",
                                 "duration_ms": 5.0, "error": None,
                                 "error_phase": None}]}]},
    ]
    # 乱序写入（seq 才是权威序；回放必须按 seq 排序喂）
    lines_shuffled = [lines[3], lines[0], lines[5], lines[2], lines[4], lines[1]]
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lines_shuffled),
                 encoding="utf-8")
    return str(p)


class TestReplay:

    def test_replay_produces_report_from_finished(self, tmp_path):
        f = _jsonl(tmp_path)
        report_dir = tmp_path / "reports"
        r = runner.invoke(starter, [
            "events", "replay", f,
            "--reporter", "json", "--report-dir", str(report_dir),
        ])
        assert r.exit_code == 0, r.output
        reports = list(report_dir.glob("run-*.json"))
        assert len(reports) == 1
        payload = json.loads(reports[0].read_text(encoding="utf-8"))
        # 判定计数原样取自末行 run.finished（不重放推导）
        assert payload["summary"] == {
            "exit_code": 0, "total": 1, "passed": 1,
            "failed": 0, "error": 0, "skipped": 0}
        assert payload["details"][0]["scenario_id"] == "sc-r"
        assert payload["details"][0]["steps"][0]["status"] == "passed"

    def test_replay_missing_file_exit_2(self, tmp_path):
        r = runner.invoke(starter, ["events", "replay", str(tmp_path / "nope.jsonl")])
        assert r.exit_code == 2

    def test_replay_empty_stream_exit_2(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        r = runner.invoke(starter, ["events", "replay", str(p)])
        assert r.exit_code == 2


class TestQuery:

    def test_query_where_and_events_filter(self, tmp_path):
        f = _jsonl(tmp_path)
        r = runner.invoke(starter, [
            "events", "query", f,
            "--where", "module=m", "--where", "status=passed",
            "--events", "step.*",
        ])
        assert r.exit_code == 0, r.output
        lines = [json.loads(l) for l in r.output.strip().splitlines() if l.startswith("{")]
        assert [l["event_type"] for l in lines] == ["step.end"]

    def test_query_json_output(self, tmp_path):
        f = _jsonl(tmp_path)
        r = runner.invoke(starter, [
            "events", "query", f, "--events", "run.finished", "-o", "json",
        ])
        assert r.exit_code == 0
        payload = json.loads(r.output)
        assert len(payload) == 1 and payload[0]["event_type"] == "run.finished"

    def test_query_unknown_where_key_exit_2(self, tmp_path):
        f = _jsonl(tmp_path)
        r = runner.invoke(starter, ["events", "query", f, "--where", "bogus=1"])
        assert r.exit_code == 2

    def test_query_wildcard_value(self, tmp_path):
        f = _jsonl(tmp_path)
        r = runner.invoke(starter, [
            "events", "query", f, "--where", "unit=u-*", "--events", "step.end",
        ])
        assert r.exit_code == 0
        lines = [json.loads(l) for l in r.output.strip().splitlines() if l.startswith("{")]
        assert len(lines) == 1 and lines[0]["unit"] == "u-1"
