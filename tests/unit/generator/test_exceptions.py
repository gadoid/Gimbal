"""Unit tests for gimbal.generator.exceptions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError


class TestUnknownGeneratorError:
    def test_is_generator_error_subclass(self):
        """UnknownGeneratorError 是 GeneratorError 的子类。"""
        err = UnknownGeneratorError("foo")
        assert isinstance(err, GeneratorError)

    def test_message_includes_kind(self):
        """错误消息包含 kind 名称。"""
        err = UnknownGeneratorError("my_kind")
        assert "my_kind" in str(err)

    def test_kind_attribute_stored(self):
        """构造时传入的 kind 被保存到 .kind 属性。"""
        err = UnknownGeneratorError("uuid_xxx")
        assert err.kind == "uuid_xxx"


class TestGeneratorError:
    def test_can_be_raised_and_caught(self):
        """GeneratorError 可正常 raise / catch。"""
        with pytest.raises(GeneratorError):
            raise GeneratorError("boom")

    def test_message_preserved(self):
        """消息原样保留。"""
        err = GeneratorError("specific message")
        assert str(err) == "specific message"
