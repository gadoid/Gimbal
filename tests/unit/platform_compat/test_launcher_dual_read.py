"""v2.1 F-2c 平台侧：gimbal_launcher 双读（旧终态 JSON / 新 jsonl run.finished）。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "src", "gimbal-platform", "backend"))

from app.services.gimbal_launcher import parse_run_result

NL = chr(10)

OLD_JSON = json.dumps({
    "exit_code": 0, "total": 2, "passed": 2, "failed": 0,
    "skipped": 0, "details": [],
})

JSONL_EVENTS = [
    {"event_type": "run.start", "seq": 1},
    {"event_type": "scenario.start", "seq": 2},
    {"event_type": "step.start", "seq": 3},
    {"event_type": "run.finished", "seq": 15, "exit_code": 0, "total": 3,
     "passed": 3, "failed": 0, "error": 0, "skipped": 0, "halted": 0,
     "blocked": 0, "repaired": 0, "details": []},
]

JSONL_OUTPUT = NL.join(json.dumps(e) for e in JSONL_EVENTS)


class TestParseRunResultDualRead:

    def test_old_terminal_json(self):
        r = parse_run_result(OLD_JSON)
        assert r is not None
        assert r["exit_code"] == 0 and r["total"] == 2

    def test_jsonl_run_finished(self):
        r = parse_run_result(JSONL_OUTPUT)
        assert r is not None
        assert r["exit_code"] == 0 and r["total"] == 3 and r["passed"] == 3

    def test_jsonl_priority_when_both(self):
        r = parse_run_result(OLD_JSON + NL + JSONL_OUTPUT)
        assert r is not None
        assert r["total"] == 3   # jsonl 末行赢

    def test_jsonl_failure_verdict(self):
        failed = list(JSONL_EVENTS)
        failed[-1] = dict(JSONL_EVENTS[-1], exit_code=1, total=2, passed=1,
                          failed=1, details=[{"scenario_id": "bad", "status": "failed"}])
        r = parse_run_result(NL.join(json.dumps(e) for e in failed))
        assert r["exit_code"] == 1 and r["failed"] == 1
        assert r["details"][0]["scenario_id"] == "bad"

    def test_noise_only_returns_none(self):
        assert parse_run_result("") is None
        assert parse_run_result("noise" + NL + "more noise") is None

    def test_run_finished_outside_window_not_found(self):
        """run.finished 在末尾 10 行之外 → 不识别（回退旧解析路径）。"""
        noise = [{"event_type": "noise", "seq": i} for i in range(20)]
        lines = NL.join(json.dumps(e) for e in JSONL_EVENTS + noise)
        assert parse_run_result(lines) is None

    def test_minimal_run_finished(self):
        line = json.dumps({"event_type": "run.finished", "exit_code": 0})
        r = parse_run_result(line)
        assert r is not None and r["details"] == []
