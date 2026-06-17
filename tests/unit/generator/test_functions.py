"""Unit tests for gimbal.generator.functions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import re
import string
import pytest
from datetime import datetime
from gimbal.generator import functions
from gimbal.generator.functions import (
    uuid, random_str, random_int, random_decimal,
    timestamp, now, seq, reset_seq_counter,
)


class TestUuid:
    def test_returns_32_hex_chars(self):
        """返回 32 位 hex 字符。"""
        val = uuid()
        assert len(val) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", val)

    def test_returns_different_values(self):
        """连续两次调用返回不同值。"""
        assert uuid() != uuid()


class TestRandomStr:
    def test_default_length_is_8(self):
        """默认长度 8。"""
        assert len(random_str()) == 8

    def test_custom_length(self):
        """自定义长度。"""
        assert len(random_str(length=20)) == 20

    def test_charset_alpha(self):
        """charset=alpha 时字符全在 ascii_letters 中。"""
        val = random_str(length=100, charset="alpha")
        for ch in val:
            assert ch in string.ascii_letters

    def test_charset_digit(self):
        """charset=digit 时字符全在 digits 中。"""
        val = random_str(length=100, charset="digit")
        for ch in val:
            assert ch in string.digits

    def test_charset_alnum_default(self):
        """charset=alnum（默认）时字符全在字母+数字中。"""
        val = random_str(length=100)
        for ch in val:
            assert ch in string.ascii_letters + string.digits

    def test_invalid_charset_raises(self):
        """非法 charset 抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid charset"):
            random_str(charset="emoji")

    def test_length_1(self):
        """length=1 也工作。"""
        val = random_str(length=1, charset="digit")
        assert val in string.digits


class TestRandomInt:
    def test_within_range(self):
        """1000 次抽样都在 [min, max] 内。"""
        for _ in range(1000):
            v = random_int(min=5, max=10)
            assert 5 <= v <= 10

    def test_degenerate_range(self):
        """min == max 时恒为该值。"""
        assert random_int(min=7, max=7) == 7

    def test_default_range(self):
        """默认 min=0, max=100。"""
        v = random_int()
        assert 0 <= v <= 100

    def test_min_greater_than_max_raises(self):
        """min > max 抛 ValueError。"""
        with pytest.raises(ValueError, match="min"):
            random_int(min=10, max=5)


class TestRandomDecimal:
    def test_within_range(self):
        """1000 次抽样都在 [min, max] 内。"""
        for _ in range(1000):
            v = random_decimal(min=10.0, max=20.0, places=2)
            assert 10.0 <= v <= 20.0

    def test_places_respected(self):
        """places=2 时小数位不超过 2。"""
        for _ in range(100):
            v = random_decimal(min=0.0, max=100.0, places=2)
            # 转 str 看小数位数
            s = str(v)
            if "." in s:
                decimals = s.split(".")[1]
                assert len(decimals) <= 2

    def test_places_zero(self):
        """places=0 返回无小数部分。"""
        v = random_decimal(min=10.0, max=20.0, places=0)
        assert v == float(int(v))

    def test_min_greater_than_max_raises(self):
        """min > max 抛 ValueError。"""
        with pytest.raises(ValueError, match="min"):
            random_decimal(min=20.0, max=10.0)


class TestTimestamp:
    def test_format_epoch_returns_int(self):
        """format=epoch 返回 int。"""
        v = timestamp(format="epoch")
        assert isinstance(v, int)
        # 应大致为当前时间（容差 5 秒）
        diff = abs(datetime.now().timestamp() - v)
        assert diff < 5

    def test_format_iso_returns_str(self):
        """format=iso 返回 ISO 格式字符串。"""
        v = timestamp(format="iso")
        assert isinstance(v, str)
        # ISO 格式可被 datetime.fromisoformat 解析
        datetime.fromisoformat(v)

    def test_format_compact(self):
        """format=compact 返回 YYYYMMDDHHMMSS 形式。"""
        v = timestamp(format="compact")
        assert isinstance(v, str)
        assert re.fullmatch(r"\d{14}", v)

    def test_invalid_format_raises(self):
        """非法 format 抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid format"):
            timestamp(format="xx")

    def test_offset_seconds_positive(self):
        """offset_seconds=+3600 约比 now 大 3600。"""
        now_ts = datetime.now().timestamp()
        future_ts = timestamp(format="epoch", offset_seconds=3600)
        assert abs((future_ts - now_ts) - 3600) < 2

    def test_offset_seconds_negative(self):
        """offset_seconds=-3600 约比 now 小 3600。"""
        now_ts = datetime.now().timestamp()
        past_ts = timestamp(format="epoch", offset_seconds=-3600)
        assert abs((now_ts - past_ts) - 3600) < 2


class TestNow:
    def test_now_matches_timestamp_with_zero_offset(self):
        """now() 与 timestamp(offset_seconds=0) 等价。"""
        v1 = now(format="epoch")
        v2 = timestamp(format="epoch", offset_seconds=0)
        # 两个调用间间隔可能 0~1 秒
        assert abs(v1 - v2) <= 1


class TestSeq:
    def setup_method(self):
        """每个测试前重置计数器，避免相互影响。"""
        reset_seq_counter()

    def test_default_first_value(self):
        """默认参数首次调用返回 000001。"""
        assert seq() == "000001"

    def test_increments_across_calls(self):
        """连续调用递增。"""
        assert seq() == "000001"
        assert seq() == "000002"
        assert seq() == "000003"

    def test_custom_width(self):
        """width=4 时首次返回 0001。"""
        assert seq(width=4) == "0001"

    def test_custom_prefix(self):
        """prefix='X' 时首次返回 X000001。"""
        assert seq(prefix="X") == "X000001"

    def test_custom_start(self):
        """start=100 时首次返回 000100。"""
        assert seq(start=100) == "000100"

    def test_prefix_and_start(self):
        """prefix='YWDD', start=100, width=6 → 'YWDD000100'。"""
        assert seq(prefix="YWDD", start=100) == "YWDD000100"

    def test_independent_sequences(self):
        """不同 prefix 是独立计数器。"""
        assert seq(prefix="A") == "A000001"
        assert seq(prefix="B") == "B000001"
        assert seq(prefix="A") == "A000002"


class TestResetSeqCounter:
    def test_reset_clears_state(self):
        """reset 后 seq 重新从 start 开始。"""
        seq()  # 000001
        seq()  # 000002
        reset_seq_counter()
        assert seq() == "000001"
