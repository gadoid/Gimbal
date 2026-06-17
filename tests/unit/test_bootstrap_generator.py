"""Smoke test: bootstrap() injects generator into cfg.

This is a focused smoke test that verifies the two things we need to know work:
  1. cfg.model_copy(update={...}) preserves other fields and injects generator
  2. The default registry has 7 kinds

NOTE: This test does NOT call bootstrap() directly (which has side effects like
plugin loading). Instead, it tests the model_copy pattern and the default
registry directly.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from gimbal.generator import Generator
from gimbal.config.models import BootstrapConfig
from gimbal.generator.registry import build_default_registry


def test_cfg_model_copy_preserves_other_fields():
    """cfg.model_copy(update={generator: g}) 不破坏其它字段。"""
    from gimbal.config.loader import ConfigLoader
    from gimbal.cli.context import CLIContext

    # Use ConfigLoader to get a real cfg, then model_copy to inject generator
    cfg = ConfigLoader().load(CLIContext(env="dev", mode="local"))

    g = Generator(build_default_registry())
    new_cfg = cfg.model_copy(update={"generator": g})

    # 验证其它字段保留
    assert new_cfg.env == cfg.env
    assert new_cfg.mode == cfg.mode
    # 验证 generator 被注入
    assert new_cfg.generator is g


def test_generator_has_7_kinds():
    """默认注册表包含 7 个内置生成器。"""
    g = Generator(build_default_registry())
    assert len(g._registry.kinds()) == 7
    assert set(g._registry.kinds()) == {"uuid", "random_str", "random_int",
                                          "random_decimal", "timestamp", "now", "seq"}
