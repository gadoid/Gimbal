"""Unit tests for gimbal.generator.specs."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest
from pydantic import ValidationError
from gimbal.generator.specs import (
    UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec, VarSpec,
)


class TestUuidSpec:
    def test_default_construction(self):
        """不传参数时使用默认值。"""
        s = UuidSpec()
        assert s.kind == "uuid"

    def test_explicit_kind(self):
        """显式 kind 也能正常构造。"""
        s = UuidSpec(kind="uuid")
        assert s.kind == "uuid"

    def test_extra_field_forbidden(self):
        """未知字段被拒绝（extra='forbid'）。"""
        with pytest.raises(ValidationError):
            UuidSpec(unknown="x")

    def test_wrong_kind_rejected(self):
        """错 kind 名称被拒绝。"""
        with pytest.raises(ValidationError):
            UuidSpec(kind="uuid_xxx")


class TestRandomStrSpec:
    def test_default_values(self):
        """默认 length=8, charset='alnum'。"""
        s = RandomStrSpec()
        assert s.kind == "random_str"
        assert s.length == 8
        assert s.charset == "alnum"

    def test_custom_values(self):
        """自定义 length 和 charset。"""
        s = RandomStrSpec(length=12, charset="digit")
        assert s.length == 12
        assert s.charset == "digit"

    def test_length_too_small(self):
        """length=0 被 ge=1 约束拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=0)

    def test_length_too_big(self):
        """length=99999 被 le=1024 约束拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=99999)

    def test_invalid_charset(self):
        """非法 charset 被 Literal 拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(charset="emoji")

    def test_extra_field_forbidden(self):
        """未知字段被拒绝。"""
        with pytest.raises(ValidationError):
            RandomStrSpec(length=8, charset="alnum", foo="bar")


class TestRandomIntSpec:
    def test_default_values(self):
        """默认 min=0, max=100。"""
        s = RandomIntSpec()
        assert s.min == 0
        assert s.max == 100

    def test_custom_values(self):
        """自定义 min/max。"""
        s = RandomIntSpec(min=5, max=10)
        assert s.min == 5
        assert s.max == 10

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            RandomIntSpec(min=0, max=10, extra_field="x")


class TestRandomDecimalSpec:
    def test_default_values(self):
        s = RandomDecimalSpec()
        assert s.min == 0.0
        assert s.max == 100.0
        assert s.places == 2

    def test_custom_values(self):
        s = RandomDecimalSpec(min=10.5, max=99.9, places=3)
        assert s.min == 10.5
        assert s.max == 99.9
        assert s.places == 3

    def test_places_too_big(self):
        """places=11 被 le=10 拒绝。"""
        with pytest.raises(ValidationError):
            RandomDecimalSpec(places=11)


class TestTimestampSpec:
    def test_default_values(self):
        s = TimestampSpec()
        assert s.format == "iso"
        assert s.offset_seconds == 0

    def test_custom_values(self):
        s = TimestampSpec(format="epoch", offset_seconds=3600)
        assert s.format == "epoch"
        assert s.offset_seconds == 3600

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            TimestampSpec(format="xx")


class TestNowSpec:
    def test_default_format(self):
        s = NowSpec()
        assert s.format == "iso"

    def test_custom_format(self):
        s = NowSpec(format="epoch")
        assert s.format == "epoch"


class TestSeqSpec:
    def test_default_values(self):
        s = SeqSpec()
        assert s.prefix == ""
        assert s.width == 6
        assert s.start == 1

    def test_custom_values(self):
        s = SeqSpec(prefix="YWDD", width=8, start=100000)
        assert s.prefix == "YWDD"
        assert s.width == 8
        assert s.start == 100000

    def test_width_too_small(self):
        with pytest.raises(ValidationError):
            SeqSpec(width=0)


class TestVarSpecUnion:
    """VarSpec 是 discriminated union，按 kind 自动分发到对应子类。"""

    @pytest.mark.parametrize("kind,expected_class", [
        ("uuid",           UuidSpec),
        ("random_str",     RandomStrSpec),
        ("random_int",     RandomIntSpec),
        ("random_decimal", RandomDecimalSpec),
        ("timestamp",      TimestampSpec),
        ("now",            NowSpec),
        ("seq",            SeqSpec),
    ])
    def test_dispatches_to_correct_subclass(self, kind, expected_class):
        spec = VarSpec.model_validate({"kind": kind})
        assert isinstance(spec, expected_class)

    def test_unknown_kind_rejected(self):
        """未注册的 kind 名称被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({"kind": "nonexistent"})

    def test_missing_kind_rejected(self):
        """缺 kind 字段被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({})

    def test_extra_field_in_specific_kind_rejected(self):
        """在 union 输入层面 extra 字段也被拒绝。"""
        with pytest.raises(ValidationError):
            VarSpec.model_validate({"kind": "random_str", "length": 8, "foo": "bar"})
