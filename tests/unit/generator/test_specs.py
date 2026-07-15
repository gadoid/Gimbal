"""Unit tests for gimbal.generator.specs."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest
from datetime import datetime
from pydantic import ValidationError
from gimbal.generator.specs import (
    UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec, VarSpec, TimeOffsetSpec,
)
from gimbal.generator.functions import time_offset, _shift_months


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


class TestTimeOffsetSpec:
    def test_default_values(self):
        """默认 unit=seconds / value=0 / direction=future。"""
        s = TimeOffsetSpec()
        assert s.kind == "time_offset"
        assert s.unit == "seconds"
        assert s.value == 0
        assert s.direction == "future"

    def test_months_unit_accepted(self):
        s = TimeOffsetSpec(unit="months", value=6, direction="future")
        assert s.unit == "months"
        assert s.value == 6

    def test_years_unit_accepted(self):
        s = TimeOffsetSpec(unit="years", value=1)
        assert s.unit == "years"

    def test_invalid_unit_rejected(self):
        """不支持的单位（如 quarters）被 Literal 拒绝。"""
        with pytest.raises(ValidationError):
            TimeOffsetSpec(unit="quarters")

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            TimeOffsetSpec(unit="months", value=1, extra="x")

    def test_dispatched_via_varspec_union(self):
        """通过 VarSpec.model_validate 也能正确分发到 TimeOffsetSpec。"""
        spec = VarSpec.model_validate({
            "kind": "time_offset", "unit": "years", "value": 1, "direction": "future"
        })
        assert isinstance(spec, TimeOffsetSpec)
        assert spec.unit == "years"


class TestShiftMonths:
    """_shift_months 的日历算术单测，覆盖跨年 / 闰年 / 月末溢出。"""

    def test_basic_month(self):
        assert _shift_months(datetime(2026, 1, 15), 1) == datetime(2026, 2, 15)

    def test_month_end_clamp_non_leap(self):
        """Jan 31 + 1 month → Feb 28（非闰年）."""
        assert _shift_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)

    def test_month_end_clamp_leap(self):
        """2024 是闰年：Mar 31 + (-1) month → Feb 29。"""
        assert _shift_months(datetime(2024, 3, 31), -1) == datetime(2024, 2, 29)

    def test_year_wrap(self):
        """11 月 + 3 个月跨年。"""
        assert _shift_months(datetime(2026, 11, 10), 3) == datetime(2027, 2, 10)

    def test_multi_year(self):
        """超过 12 个月的偏移。"""
        assert _shift_months(datetime(2026, 6, 1), 14) == datetime(2027, 8, 1)

    def test_zero_months(self):
        """0 个月应原样返回（除时区外）。"""
        dt = datetime(2026, 6, 15)
        assert _shift_months(dt, 0) == dt

    def test_backward_across_year(self):
        """向前 / 向后都按日历月算。"""
        assert _shift_months(datetime(2026, 2, 1), -1) == datetime(2026, 1, 1)


class TestTimeOffsetFunction:
    """time_offset() 行为测试：months / years / direction / 单位校验。"""

    def test_returns_int(self):
        result = time_offset(unit="months", value=6, direction="future")
        assert isinstance(result, int)

    def test_months_forward_is_larger_than_now(self):
        before = int(datetime.now().timestamp())
        result = time_offset(unit="months", value=6, direction="future")
        assert result > before

    def test_years_forward_is_larger_than_now(self):
        before = int(datetime.now().timestamp())
        result = time_offset(unit="years", value=1, direction="future")
        assert result > before

    def test_past_smaller_than_future(self):
        future = time_offset(unit="months", value=6, direction="future")
        past = time_offset(unit="months", value=6, direction="past")
        assert future > past

    def test_invalid_unit_raises(self):
        with pytest.raises(ValueError):
            time_offset(unit="quarters", value=1)

    def test_years_value_one_roughly_365_days(self):
        """value=1 年应大致比现在多 365 天（允许 ±2 天差异，跨 2/29）。"""
        before = datetime.now()
        result = time_offset(unit="years", value=1, direction="future")
        after = datetime.fromtimestamp(result)
        delta_days = (after - before).total_seconds() / 86400
        assert 360 <= delta_days <= 370

    def test_months_value_six_roughly_180_days(self):
        """value=6 月应大致比现在多 180 天（允许 ±31 天差异，跨 2/29 与月长差）。"""
        before = datetime.now()
        result = time_offset(unit="months", value=6, direction="future")
        after = datetime.fromtimestamp(result)
        delta_days = (after - before).total_seconds() / 86400
        # 6 个日历月：最少 181 天 (Jul→Dec 都是 31)，最多 184 天；当前季节浮动
        assert 170 <= delta_days <= 195

    def test_default_unit_seconds(self):
        """不传 unit → 默认 seconds。"""
        before = int(datetime.now().timestamp())
        result = time_offset(value=60)
        assert before + 60 <= result <= before + 61

    def test_value_zero(self):
        """value=0 → 当前 unix 秒（允许 1 秒误差，跨 now() 调用）。"""
        before = int(datetime.now().timestamp())
        result = time_offset(value=0)
        assert abs(result - before) <= 1
