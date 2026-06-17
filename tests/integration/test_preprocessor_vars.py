"""Integration tests: ScenarioPreprocessor + vars + generator."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
from gimbal.schema.scenario import Scenario, Config
from gimbal.schema.step import Step
from gimbal.schema.request import Request
from gimbal.schema.api import Api
from gimbal.generator import Generator, build_default_registry
from gimbal.config.models import BootstrapConfig


def _make_scenario(body, *, vars=None):
    """构造一个最小 scenario 用于测试。"""
    cfg = Config(vars=vars or {})
    from gimbal.schema.scenario import Meta
    meta = Meta(
        name="test", description="test", module="t", priority=1,
        author="x", owner="x", tags=[], version="1.0.0",
        createTime="2026-01-01T00:00:00", expire=False, requirementRef=[],
    )
    api = Api(kind="api", service="s", method="POST", path="/x", headers={}, timeout=30)
    request = Request(kind="request", body=body)
    step = Step(kind="step", api=api, request=request, strategy=[])
    return Scenario(kind="scenario", scenarioId="t1", meta=meta, config=cfg,
                    resource={}, steps=[step])


def _make_cfg(generator=None, vars=None):
    g = generator or Generator(build_default_registry())
    return BootstrapConfig(env="dev", mode="local", generator=g, vars=vars or {})


class TestGeneratorVar:
    def test_random_str_var_resolved(self):
        """生成式 var 能在 step body 中展开。"""
        sc = _make_scenario(
            vars={"bl_no": {"kind": "random_str", "length": 12, "charset": "alnum"}},
            body={"bl_no": "${var.bl_no}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        body = steps[0].request.body
        assert isinstance(body["bl_no"], str)
        assert len(body["bl_no"]) == 12

    def test_timestamp_var_preserves_int_type(self):
        """生成式 timestamp (format=epoch) 解析为 int。"""
        sc = _make_scenario(
            vars={"etd": {"kind": "timestamp", "format": "epoch"}},
            body={"etd": "${var.etd}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        assert isinstance(steps[0].request.body["etd"], int)

    def test_random_decimal_var_preserves_float_type(self):
        """生成式 random_decimal 解析为 float。"""
        sc = _make_scenario(
            vars={"w": {"kind": "random_decimal", "min": 10, "max": 20, "places": 2}},
            body={"w": "${var.w}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        assert isinstance(steps[0].request.body["w"], float)

    def test_uuid_var_resolved(self):
        sc = _make_scenario(
            vars={"u": {"kind": "uuid"}},
            body={"u": "${var.u}"},
        )
        cfg = _make_cfg()
        pre = ScenarioPreprocessor(sc, cfg)
        steps, _ = pre.run()
        u = steps[0].request.body["u"]
        assert isinstance(u, str) and len(u) == 32


class TestLiteralVar:
    def test_int_literal(self):
        sc = _make_scenario(vars={"n": 16}, body={"n": "${var.n}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["n"] == 16

    def test_str_literal(self):
        sc = _make_scenario(vars={"s": "hello"}, body={"s": "${var.s}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["s"] == "hello"

    def test_bool_literal(self):
        sc = _make_scenario(vars={"b": False}, body={"b": "${var.b}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["b"] is False

    def test_none_literal(self):
        """None 字面量展开为 None（合法值）。"""
        sc = _make_scenario(vars={"x": None}, body={"x": "${var.x}"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] is None


class TestPrecedence:
    def test_cli_var_wins_over_scenario_var(self):
        """CLI vars 与 scenario vars 同名时 CLI 赢。"""
        sc = _make_scenario(
            vars={"x": {"kind": "random_str", "length": 5}},
            body={"x": "${var.x}"},
        )
        cfg = _make_cfg(vars={"x": "fixed_from_cli"})
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] == "fixed_from_cli"

    def test_cli_var_merges_with_scenario_vars(self):
        """scenario 没声明、CLI 有声明时 CLI 提供值。"""
        sc = _make_scenario(
            vars={"a": "literal_a"},
            body={"a": "${var.a}", "b": "${var.b}"},
        )
        cfg = _make_cfg(vars={"b": "from_cli"})
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        body = steps[0].request.body
        assert body["a"] == "literal_a"
        assert body["b"] == "from_cli"


class TestErrors:
    def test_invalid_spec_raises(self):
        """不合法的 spec 抛 GeneratorError 或 ValidationError。"""
        from pydantic import ValidationError
        sc = _make_scenario(
            vars={"x": {"kind": "nonexistent"}},
            body={"x": "${var.x}"},
        )
        cfg = _make_cfg()
        with pytest.raises(ValidationError):
            ScenarioPreprocessor(sc, cfg).run()

    def test_undefined_var_in_template_raises(self):
        """模板引用未声明 var 抛 ValueError。"""
        sc = _make_scenario(vars={}, body={"x": "${var.undef}"})
        cfg = _make_cfg()
        with pytest.raises(ValueError, match="undef"):
            ScenarioPreprocessor(sc, cfg).run()


class TestNoVars:
    def test_empty_vars_runs_fine(self):
        """vars 为空时不影响其他阶段。"""
        sc = _make_scenario(vars={}, body={"x": "static_value"})
        cfg = _make_cfg()
        steps, _ = ScenarioPreprocessor(sc, cfg).run()
        assert steps[0].request.body["x"] == "static_value"
