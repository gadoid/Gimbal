"""N3(定稿 D8,P3-08):参数登记表 + p_patch 接线 + 值来源追踪。

验收(Goals P3-08):
  - 同一参数经 suite 补丁与调用参数两层设置时,生效值与登记表的合并
    规则一致,来源说明正确;
  - 现有 --var 行为不变(全量测试零回归)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.compiler.pipeline import apply_patch_layers, p_patch
from gimbal.schema.param_registry import (
    LAYER_ORDER, PARAM_REGISTRY, ParamMerge, ParamSource, ValueSourceTrace,
    merge_of, source_allowed,
)


class TestParamRegistry:

    def test_all_config_fields_registered(self):
        """可配置字段的登记完备性(vars/services/users/setup/teardown/
        timePolicy/retry 各有声明)。"""
        expected = {"vars", "services", "users", "setup", "teardown",
                    "timePolicy", "retry"}
        assert expected <= set(PARAM_REGISTRY)

    def test_vars_uses_override_merge(self):
        assert merge_of("vars") == ParamMerge.OVERRIDE

    def test_services_deep_merge(self):
        assert merge_of("services") == ParamMerge.DEEP

    def test_setup_keyed_merge(self):
        assert merge_of("setup") == ParamMerge.KEYED

    def test_layer_order(self):
        assert LAYER_ORDER[-1] == ParamSource.CLI_VAR   # --var 最深


class TestPPatchRegistry:

    def test_vars_override_not_deep(self):
        """vars 的 dict 值整名覆盖:后层的 dict 替换前层,不做部分合并。"""
        result = p_patch([
            {"vars": {"a": {"kind": "random_str", "length": 12}, "b": 1}},
            {"vars": {"a": "literal-override"}},
        ])
        assert result["vars"]["a"] == "literal-override"   # 整名覆盖
        assert result["vars"]["b"] == 1                     # 未触碰的保留

    def test_services_deep_merge(self):
        result = p_patch([
            {"services": {"fin": {"base_url": "http://a", "timeout": 30}}},
            {"services": {"fin": {"base_url": "http://b"}}},
        ])
        assert result["services"]["fin"]["base_url"] == "http://b"
        assert result["services"]["fin"]["timeout"] == 30    # 深合并保留

    def test_scalar_override(self):
        result = p_patch([{"timePolicy": {"kind": "record"}},
                          {"timePolicy": {"kind": "timeout", "seconds": 60}}])
        assert result["timePolicy"] == {"kind": "timeout", "seconds": 60}


class TestApplyPatchLayers:

    def test_five_layer_effective_value(self):
        """多层设置同一参数:生效值按登记表合并规则,来源正确。"""
        config = {"vars": {"x": "source", "gen": {"kind": "random_str",
                                                  "length": 8}}}
        cli_vars = {"x": "from-cli", "extra": "cli-new"}
        unit_inputs = {"gen": "unit-override"}

        effective, trace = apply_patch_layers(
            config, cli_vars=cli_vars, unit_inputs=unit_inputs)

        # vars=override:L4(cli)覆盖 L0(source)/L2(unit)
        assert effective["vars"]["x"] == "from-cli"
        assert effective["vars"]["extra"] == "cli-new"
        # L2(unit_inputs) 的 gen 是 dict 整名覆盖(不走深合并)
        assert effective["vars"]["gen"] == "unit-override"

        # 来源追踪:override 字段在字段级记来源(逐键覆盖归为该层的
        # vars 来源;最深层写入者胜 —— cli_var 覆盖了 unit_patch)
        summary = trace.summary()
        assert summary.get("vars") == "cli_var"

    def test_cli_var_only_source(self):
        """仅 --var 层:L0 源 + L4 cli,中间层空 → 行为与直接合并一致。"""
        config = {"vars": {"a": 1}}
        effective, _ = apply_patch_layers(config, cli_vars={"b": 2})
        assert effective["vars"] == {"a": 1, "b": 2}

    def test_no_layers_identity(self):
        config = {"vars": {"a": 1}, "services": {"s": {"base_url": "u"}}}
        effective, trace = apply_patch_layers(config)
        assert effective["vars"] == config["vars"]
        assert effective["services"] == config["services"]
        assert trace.entries == []   # 无改动 → 空追踪
