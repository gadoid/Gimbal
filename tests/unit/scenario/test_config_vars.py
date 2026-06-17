"""Unit tests for Scenario.config.vars field."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.schema.scenario import Config


def test_config_vars_default_empty():
    """Config 不传 vars 时默认为空 dict。"""
    cfg = Config()
    assert cfg.vars == {}


def test_config_vars_accepts_literals():
    """vars 可包含字面量（primitive）。"""
    cfg = Config(vars={
        "customer_id": 16,
        "service_id": 55,
        "fixed": "hello",
        "flag": True,
        "nothing": None,
    })
    assert cfg.vars["customer_id"] == 16
    assert cfg.vars["fixed"] == "hello"
    assert cfg.vars["flag"] is True
    assert cfg.vars["nothing"] is None


def test_config_vars_accepts_generator_specs():
    """vars 可包含生成式 spec dict（含 kind）。"""
    cfg = Config(vars={
        "bl_no":  {"kind": "random_str", "length": 12, "charset": "alnum"},
        "etd":    {"kind": "timestamp", "format": "epoch"},
        "weight": {"kind": "random_decimal", "min": 50, "max": 200, "places": 2},
    })
    assert cfg.vars["bl_no"]["kind"] == "random_str"
    assert cfg.vars["etd"]["format"] == "epoch"


def test_config_vars_mixed():
    """vars 可同时包含字面量与生成式。"""
    cfg = Config(vars={
        "customer_id": 16,
        "bl_no": {"kind": "random_str", "length": 12},
    })
    assert cfg.vars["customer_id"] == 16
    assert cfg.vars["bl_no"]["kind"] == "random_str"
