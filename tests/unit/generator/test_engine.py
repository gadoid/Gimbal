"""Unit tests for gimbal.generator.engine."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest
from gimbal.generator.engine import Generator
from gimbal.generator.registry import build_default_registry, GeneratorRegistry
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError
from gimbal.generator.specs import (
    UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec,
)


@pytest.fixture
def generator():
    return Generator(build_default_registry())


class TestGenerator:
    def test_uuid_kind(self, generator):
        s = UuidSpec()
        v = generator.generate(s)
        assert isinstance(v, str)
        assert len(v) == 32

    def test_random_str_kind(self, generator):
        s = RandomStrSpec(length=10, charset="digit")
        v = generator.generate(s)
        assert isinstance(v, str)
        assert len(v) == 10
        assert v.isdigit()

    def test_random_int_kind(self, generator):
        s = RandomIntSpec(min=5, max=5)  # 退化区间
        assert generator.generate(s) == 5

    def test_random_decimal_kind(self, generator):
        s = RandomDecimalSpec(min=10.0, max=10.0, places=2)
        v = generator.generate(s)
        assert v == 10.0

    def test_timestamp_epoch_kind(self, generator):
        s = TimestampSpec(format="epoch")
        v = generator.generate(s)
        assert isinstance(v, int)

    def test_now_kind(self, generator):
        s = NowSpec(format="epoch")
        v = generator.generate(s)
        assert isinstance(v, int)

    def test_seq_kind(self, generator):
        from gimbal.generator.functions import reset_seq_counter
        reset_seq_counter()
        s = SeqSpec(prefix="X", width=4)
        assert generator.generate(s) == "X0001"
        assert generator.generate(s) == "X0002"

    def test_unknown_kind_raises(self):
        """未注册 kind 抛 UnknownGeneratorError。"""
        gen = Generator(GeneratorRegistry())  # 空注册表
        s = UuidSpec()
        with pytest.raises(UnknownGeneratorError) as exc:
            gen.generate(s)
        assert exc.value.kind == "uuid"

    def test_function_exception_wrapped(self, generator):
        """生成函数自身抛异常时被包装为 GeneratorError。"""
        s = RandomIntSpec(min=10, max=5)  # min > max，会被函数拒绝
        with pytest.raises(GeneratorError) as exc:
            generator.generate(s)
        assert "random_int" in str(exc.value)
        assert "min" in str(exc.value).lower()

    def test_original_exception_chained(self, generator):
        """GeneratorError 包装时 __cause__ 指向原异常。"""
        s = RandomIntSpec(min=10, max=5)
        with pytest.raises(GeneratorError) as exc:
            generator.generate(s)
        assert exc.value.__cause__ is not None


class TestGenerateAll:
    def test_empty_dict(self, generator):
        assert generator.generate_all({}) == {}

    def test_single_spec(self, generator):
        result = generator.generate_all({"x": {"kind": "uuid"}})
        assert "x" in result
        assert len(result["x"]) == 32

    def test_multiple_specs(self, generator):
        from gimbal.generator.functions import reset_seq_counter
        reset_seq_counter()
        result = generator.generate_all({
            "u":      {"kind": "uuid"},
            "code":   {"kind": "random_str", "length": 6, "charset": "digit"},
            "n":      {"kind": "random_int", "min": 7, "max": 7},
            "order":  {"kind": "seq", "prefix": "X"},
        })
        assert len(result["u"]) == 32
        assert result["code"].isdigit() and len(result["code"]) == 6
        assert result["n"] == 7
        assert result["order"] == "X000001"

    def test_invalid_spec_raises(self, generator):
        """非法 spec 在 generate_all 里就抛 ValidationError。"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            generator.generate_all({"bad": {"kind": "nonexistent"}})

    def test_extra_field_raises(self, generator):
        """含未知字段的 spec 抛 ValidationError。"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            generator.generate_all({"bad": {"kind": "random_str", "length": 8, "foo": "x"}})
