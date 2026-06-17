"""Unit tests for BootstrapConfig.generator field."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError
from gimbal.config.models import BootstrapConfig


def test_generator_field_defaults_to_none():
    """BootstrapConfig 默认 generator 为 None（向后兼容）。"""
    cfg = BootstrapConfig()
    assert cfg.generator is None


def test_generator_field_accepts_value():
    """可显式传 generator 实例。"""
    mock_gen = MagicMock()
    cfg = BootstrapConfig(generator=mock_gen)
    assert cfg.generator is mock_gen


def test_generator_field_is_frozen():
    """BootstrapConfig 是 frozen，generator 字段不可重新赋值。"""
    mock_gen = MagicMock()
    cfg = BootstrapConfig(generator=mock_gen)
    with pytest.raises(ValidationError):
        cfg.generator = MagicMock()
