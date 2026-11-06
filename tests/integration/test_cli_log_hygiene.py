"""日志整理 B2(2026-11-06):CLI 进程级日志与校验错误口径。

真实子进程(stderr 非 tty,与平台 spawn 同口径):

* stderr 每一行都是 JSON——早期(bootstrap 之前)日志不再以彩色文本混入;
* 启动阶段只留一行 INFO 汇总;
* 日志里不出现枚举 repr(StrategyPhase.X / StepStatus.X …);
* --dry-run 也做结构校验;校验错误按「字段路径: 问题 —— 提示」输出,
  不带 pydantic.dev 链接。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

_SCENARIO = {
    "kind": "scenario",
    "scenarioId": "sc-log-hygiene",
    "meta": {"name": "log-hygiene"},
    "config": {"services": {"dead": "http://127.0.0.1:9"},
               "users": {}, "timePolicy": {"kind": "record"}},
    "resource": {},
    "steps": [{
        "kind": "step",
        "call": {"protocol": "http", "service": "dead",
                 "method": "GET", "path": "/ping"},
        "request": {"kind": "request", "body": {}},
        "strategy": [{"kind": "assertion",
                      "target": "$.call.response.status",
                      "operator": "eq", "expected": 200}],
    }],
}

_ENUM_REPR = re.compile(
    r"\b(StrategyPhase|StrategyStatus|StepStatus|Scope|AssertOperator|Auth)\.[A-Z_]+\b")


def _run(payload: dict, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gimbal", "run", "launch", "--inline",
         json.dumps(payload), "--reporter", "json", *extra],
        capture_output=True, text=True, timeout=120,
        env={**__import__("os").environ, "NO_COLOR": "1"},
    )


def test_stderr_is_all_json_and_quiet_startup():
    proc = _run(_SCENARIO)
    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    assert lines, proc.stderr
    records = []
    for ln in lines:
        records.append(json.loads(ln))   # 任一非 JSON 行即失败
    startup = [r for r in records
               if r.get("logger", "").startswith(("gimbal.core.bootstrap",
                                                    "gimbal.plugins",
                                                    "gimbal.reporter.runtime"))
               and r.get("level") == "INFO"]
    assert len(startup) == 1 and "就绪" in startup[0]["message"]
    assert not _ENUM_REPR.search(proc.stderr)


def test_dry_run_validates_and_summarizes_errors():
    bad = json.loads(json.dumps(_SCENARIO))
    bad["config"]["setup"] = [{"name": "wait", "kind": "sleep",
                               "payload": {"seconds": 0.1}}]
    proc = _run(bad, "--dry-run")
    assert proc.returncode == 2
    assert "config.setup[0].name" in proc.stderr
    assert "config.setup[0].payload" in proc.stderr
    assert "errors.pydantic.dev" not in proc.stderr
