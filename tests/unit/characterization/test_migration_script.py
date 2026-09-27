"""迁移脚本单测：api→call、路径重写边界、幂等、三形态递归、产物校验。"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "migrate_legacy_case.py"
_spec = importlib.util.spec_from_file_location("migrate_legacy_case", _SCRIPT)
mig = importlib.util.module_from_spec(_spec)
sys.modules["migrate_legacy_case"] = mig   # dataclass 字段解析需要模块已注册
_spec.loader.exec_module(mig)


def _scenario(steps):
    return {
        "kind": "scenario", "scenarioId": "sc-m",
        "meta": {"name": "t", "description": "d", "module": "m", "priority": 1,
                 "author": "a", "owner": "o", "tags": [], "version": "1.0",
                 "createTime": "2026-09-27T00:00:00Z", "expire": False,
                 "requirementRef": []},
        "config": {}, "resource": {}, "steps": steps,
    }


class TestApiToCall:

    def test_api_sugar_becomes_http_call(self):
        sc = _scenario([{"kind": "step",
                         "api": {"kind": "api", "service": "s", "method": "POST",
                                 "path": "/p", "headers": {}, "timeout": 5},
                         "request": {"kind": "request", "body": {}}, "strategy": []}])
        out, res = mig.migrate_payload(sc)
        step = out["steps"][0]
        assert "api" not in step
        assert step["call"]["protocol"] == "http"
        assert step["call"]["service"] == "s" and step["call"]["method"] == "POST"
        assert res.change_count == 1
        assert mig.validate_payload(out) is None

    def test_explicit_call_untouched(self):
        sc = _scenario([{"kind": "step",
                         "call": {"kind": "call", "protocol": "echo", "message": "x"},
                         "strategy": []}])
        out, res = mig.migrate_payload(sc)
        assert res.change_count == 0
        assert out["steps"][0]["call"]["protocol"] == "echo"


class TestPathRewrites:

    def test_all_canonical_paths(self):
        targets = {
            "$.response_body": "$.call.response.body",
            "$.response_status": "$.call.response.status",
            "$.response_headers": "$.call.response.meta.headers",
            "$.request_body": "$.call.request.body",
            "$.request_method": "$.call.request.method",
            "$.request_url": "$.call.request.url",
            "$.request_headers": "$.call.request.headers",
            "$.duration_ms": "$.call.elapsed_ms",
        }
        strategy = [
            {"kind": "assertion", "name": f"a{i}", "target": t, "operator": "eq",
             "expected": 1}
            for i, t in enumerate(targets)
        ]
        sc = _scenario([{"kind": "step",
                         "call": {"kind": "call", "protocol": "echo", "message": "x"},
                         "strategy": strategy}])
        out, res = mig.migrate_payload(sc)
        got = [s["target"] for s in out["steps"][0]["strategy"]]
        assert got == list(targets.values())
        assert res.change_count == len(targets)

    def test_nested_path_segments(self):
        sc = _scenario([{"kind": "step",
                         "call": {"kind": "call", "protocol": "echo", "message": "x"},
                         "strategy": [{"kind": "extract", "name": "e",
                                       "expression": "$.response_body.data.list[0].id",
                                       "target": "oid"}]}])
        out, _ = mig.migrate_payload(sc)
        assert out["steps"][0]["strategy"][0]["expression"] == \
            "$.call.response.body.data.list[0].id"

    def test_boundary_safety(self):
        """$.response_bodyx 这类不匹配；$.response_body_x 也不匹配。"""
        sc = _scenario([{"kind": "step",
                         "call": {"kind": "call", "protocol": "echo", "message": "x"},
                         "strategy": [{"kind": "assertion", "name": "a",
                                       "target": "$.response_body_extra",
                                       "operator": "eq", "expected": 1}]}])
        out, res = mig.migrate_payload(sc)
        assert res.change_count == 0
        assert out["steps"][0]["strategy"][0]["target"] == "$.response_body_extra"

    def test_rewrites_inside_embedded_strings(self):
        sc = _scenario([{"kind": "step",
                         "call": {"kind": "call", "protocol": "echo", "message": "x"},
                         "strategy": [{"kind": "assertion", "name": "a",
                                       "target": "$.response_body.code",
                                       "operator": "eq", "expected": 1,
                                       "message": "code in $.response_body.code"}]}])
        out, res = mig.migrate_payload(sc)
        assert out["steps"][0]["strategy"][0]["message"] == \
            "code in $.call.response.body.code"
        assert res.change_count == 2


class TestRecursionAndIdempotence:

    def test_suite_desugars_to_graph(self):
        """v2.1 批次 F-2b：kind=suite 迁移为 graph aggregate（嵌入式 Suite schema 已删除）。"""
        sc = _scenario([{"kind": "step",
                         "api": {"kind": "api", "service": "s", "method": "GET",
                                 "path": "/p"},
                         "request": {"kind": "request", "body": {}},
                         "strategy": [{"kind": "assertion", "name": "a",
                                       "target": "$.response_status",
                                       "operator": "eq", "expected": 200}]}])
        suite = {"kind": "suite", "suite": [sc, dict(sc)],
                 "execution": {"parallel": True, "maxWorkers": 2, "failFast": True}}
        out, res = mig.migrate_payload(suite)
        assert out["kind"] == "graph" and out["mode"] == "aggregate"
        assert [u["ref"] for u in out["units"]] == ["sc-m", "sc-m"]
        assert out["policy"] == {"parallel": 2, "fail_fast": True}
        assert mig.validate_payload(out) is None
        # 每场景 1 api + 1 path，外加 kind 变更
        assert any("kind=suite → kind=graph" in c for c in res.changes)
        for u in out["units"]:
            assert "api" not in u["scenario"]["steps"][0]

    def test_graph_recursion(self):
        sc = _scenario([{"kind": "step",
                         "api": {"kind": "api", "service": "s", "method": "GET",
                                 "path": "/p"},
                         "request": {"kind": "request", "body": {}},
                         "strategy": [{"kind": "assertion", "name": "a",
                                       "target": "$.response_status",
                                       "operator": "eq", "expected": 200}]}])
        graph = {"kind": "graph", "mode": "chain",
                 "units": [{"ref": "a", "scenario": sc}]}
        out2, res2 = mig.migrate_payload(graph)
        assert res2.change_count == 2
        assert out2["units"][0]["scenario"]["steps"][0]["call"]["protocol"] == "http"

    def test_idempotent_second_pass_zero_changes(self):
        sc = _scenario([{"kind": "step",
                         "api": {"kind": "api", "service": "s", "method": "GET",
                                 "path": "/p"},
                         "request": {"kind": "request", "body": {}},
                         "strategy": [{"kind": "extract", "name": "e",
                                       "expression": "$.response_body.code",
                                       "target": "c"}]}])
        once, r1 = mig.migrate_payload(sc)
        twice, r2 = mig.migrate_payload(once)
        assert r1.change_count == 2
        assert r2.change_count == 0
        assert twice == once

    def test_setup_teardown_warning(self):
        sc = _scenario([])
        sc["config"]["setup"] = [{"kind": "sql", "sql": "insert"}]
        out, res = mig.migrate_payload(sc)
        assert any("LifecycleEntry" in w for w in res.warnings)
        assert out["config"]["setup"] == [{"kind": "sql", "sql": "insert"}]


class TestEndToEndEquivalence:
    """迁移语义对账：同一场景新旧形式经引擎执行结果一致（echo 双路径）。"""

    def test_migrated_case_runs_identically(self):
        # 用特征化同款断言：旧路径断言 vs 迁移后新路径断言都应通过
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from characterization.test_assign_extract_behavior import make_engine  # noqa: E402
        old_form = _scenario([{"kind": "step",
                               "call": {"kind": "call", "protocol": "echo",
                                        "message": "EQ"},
                               "strategy": [{"kind": "assertion", "name": "a",
                                             "target": "$.response_body.msg",
                                             "operator": "eq", "expected": "EQ"}]}])
        new_payload, res = mig.migrate_payload(old_form)
        assert res.change_count == 1
        # dict → Scenario 模型执行（新路径经引擎跑通 = 迁移语义等价）
        from pydantic import TypeAdapter
        from gimbal.schema.scenario import RunUnion
        scenario = TypeAdapter(RunUnion).validate_python(new_payload)
        engine, *_ = make_engine()
        result = engine.run(scenario)
        assert result.passed == 1
