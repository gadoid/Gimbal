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
    """默认注册表包含 9 个内置生成器。

    原始 7 个(uuid/random_str/random_int/random_decimal/timestamp/now/seq)
    + random_decorated / time_offset(装饰随机串与时间偏移,随生成器目录
    扩充入册)= 9;函数名保留历史称呼。
    """
    g = Generator(build_default_registry())
    assert len(g._registry.kinds()) == 9
    assert set(g._registry.kinds()) == {"uuid", "random_str", "random_int",
                                          "random_decimal", "timestamp", "now", "seq",
                                          "random_decorated", "time_offset"}
