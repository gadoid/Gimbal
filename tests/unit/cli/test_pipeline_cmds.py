"""P0-06：compile/validate/resolve 的 `-o json` 机器可读错误契约。

五类错误的 JSON 结构与稳定错误码断言（验收标准）：
call 字段拼写 → CALL_FIELD_INVALID；未知协议 → UNKNOWN_PROTOCOL；
输入不满足 → INPUT_UNSATISFIED；shared 不一致 → SHARED_MISMATCH；
依赖成环 → CYCLE。失败退出码一律 2。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from typer.testing import CliRunner

from gimbal.cli.params import starter
from gimbal.schema.call import Call
from gimbal.schema.scenario import Scenario, Config as ScenarioConfig, SuiteGraph, UnitDecl, Meta
from gimbal.schema.step import Step

runner = CliRunner()


def _meta(name: str) -> Meta:
    return Meta(name=name, description="d", module="m", priority=1, author="a",
                owner="o", tags=[], version="1.0",
                createTime=datetime.now(timezone.utc), expire=False, requirementRef=[])


def _http_scenario(sid: str, *, call: Call | None = None,
                   template_var: str | None = None) -> Scenario:
    path = f"/p?x=${{{template_var}}}" if template_var else f"/p/{sid}"
    return Scenario(
        scenarioId=sid, meta=_meta(sid), config=ScenarioConfig(), resource={},
        steps=[Step(description="d",
                    call=call or Call(protocol="http", service="svc",
                                      method="GET", path=path),
                    strategy=[])],
    )


def _write(tmp_path: Path, target) -> str:
    p = tmp_path / "target.json"
    p.write_text(json.dumps(target.model_dump(mode="json"), ensure_ascii=False),
                 encoding="utf-8")
    return str(p)


def _invoke_json(cmd: str, source: str):
    result = runner.invoke(starter, [cmd, source, "-o"])
    assert result.exit_code == 2, (result.exit_code, result.output)
    data = json.loads(result.output)
    assert data["ok"] is False
    assert isinstance(data["errors"], list) and data["errors"]
    for e in data["errors"]:
        assert set(e.keys()) == {"code", "message", "location"}, e
        assert isinstance(e["location"], dict)
    return data


def test_call_field_typo_reports_call_field_invalid(tmp_path):
    """协议字段拼写错误（servic≠service）→ CALL_FIELD_INVALID。"""
    sc = _http_scenario("sc-typo",
                        call=Call(protocol="http", servic="svc",
                                  method="GET", path="/p"))
    data = _invoke_json("validate", _write(tmp_path, sc))
    assert data["errors"][0]["code"] == "CALL_FIELD_INVALID"


def test_unknown_protocol_reports_unknown_protocol(tmp_path):
    sc = _http_scenario("sc-proto",
                        call=Call(protocol="nope", method="GET", path="/p"))
    data = _invoke_json("validate", _write(tmp_path, sc))
    assert data["errors"][0]["code"] == "UNKNOWN_PROTOCOL"


def test_unsatisfied_input_reports_input_unsatisfied(tmp_path):
    """消费者引用 ${v} 而无上游产出 → INPUT_UNSATISFIED。"""
    graph = SuiteGraph(kind="graph", mode="compose", units=[
        UnitDecl(ref="a", scenario=_http_scenario("a", template_var="v")),
    ])
    data = _invoke_json("compile", _write(tmp_path, graph))
    codes = [e["code"] for e in data["errors"]]
    assert "INPUT_UNSATISFIED" in codes


def test_shared_mismatch_reports_shared_mismatch(tmp_path):
    graph = SuiteGraph(kind="graph", mode="compose", units=[
        UnitDecl(ref="a", scenario=_http_scenario("a"), shared="L"),
        UnitDecl(ref="b", scenario=_http_scenario("b"), shared="L"),
    ])
    data = _invoke_json("validate", _write(tmp_path, graph))
    assert data["errors"][0]["code"] == "SHARED_MISMATCH"


def test_dependency_cycle_reports_cycle(tmp_path):
    graph = SuiteGraph(kind="graph", mode="compose", units=[
        UnitDecl(ref="a", scenario=_http_scenario("a"), needs=["b"]),
        UnitDecl(ref="b", scenario=_http_scenario("b"), needs=["a"]),
    ])
    data = _invoke_json("validate", _write(tmp_path, graph))
    assert data["errors"][0]["code"] == "CYCLE"


def test_validate_success_json_shape(tmp_path):
    """成功路径：{-o json} 输出 ok 摘要，退出码 0。"""
    sc = _http_scenario("sc-ok")
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(sc.model_dump(mode="json"), ensure_ascii=False),
                 encoding="utf-8")
    result = runner.invoke(starter, ["validate", str(p), "-o"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == {"ok": True, "kind": "scenario", "mode": "aggregate",
                    "units": 1, "parallel": 1}


def test_resolve_unknown_unit_json_error(tmp_path):
    """resolve --unit 指向不存在的单元：结构化错误 + exit 2。"""
    sc = _http_scenario("sc-r")
    p = tmp_path / "r.json"
    p.write_text(json.dumps(sc.model_dump(mode="json"), ensure_ascii=False),
                 encoding="utf-8")
    result = runner.invoke(starter, ["resolve", str(p), "--unit", "ghost", "-o"])
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["errors"][0]["location"].get("unit") == "ghost"
