"""PlateVersion 单元测试(PR-2.0)。

业务承诺:
  * 解析合法 'major.minor.patch' 字符串
  * 拒绝非法格式(空、缺段、非数字、含点超过 3 个)
  * ``str(v)`` 与 ``parse(s)`` 互逆
  * ``to_dict`` / ``from_dict`` 互逆
  * frozen:修改字段抛 FrozenInstanceError
  * @final:运行时 ``__final__`` 标记 True(对应 D10)

对应设计:PR-2.0 §2.2 + PLATE_DESIGN §7 契约保真。
"""
from __future__ import annotations

import dataclasses

import pytest

from Plate.version import PlateVersion


# ════════════════════════════════════════════════════════════════════════════
# 解析
# ════════════════════════════════════════════════════════════════════════════


class TestPlateVersionParse:
    def test_parse_valid_1_0_0(self) -> None:
        """业务需求:标准 3 段版本可解析。"""
        v = PlateVersion.parse("1.0.0")
        assert v == PlateVersion(1, 0, 0)

    def test_parse_large_numbers(self) -> None:
        """业务需求:大版本号可解析(超过 1 位数字)。"""
        v = PlateVersion.parse("100.200.300")
        assert v == PlateVersion(100, 200, 300)

    def test_parse_invalid_empty(self) -> None:
        """业务需求:空字符串 → ValueError。"""
        with pytest.raises(ValueError, match="版本格式"):
            PlateVersion.parse("")

    def test_parse_invalid_two_segments(self) -> None:
        """业务需求:'1.2' 缺段 → ValueError。"""
        with pytest.raises(ValueError, match="版本格式"):
            PlateVersion.parse("1.2")

    def test_parse_invalid_four_segments(self) -> None:
        """业务需求:'1.2.3.4' 多段 → ValueError。"""
        with pytest.raises(ValueError, match="版本格式"):
            PlateVersion.parse("1.2.3.4")

    def test_parse_invalid_non_numeric(self) -> None:
        """业务需求:非数字段 → ValueError。"""
        with pytest.raises(ValueError, match="版本格式"):
            PlateVersion.parse("1.x.3")

    def test_parse_invalid_type(self) -> None:
        """业务需求:非字符串 → ValueError。"""
        with pytest.raises(ValueError, match="必须是 str"):
            PlateVersion.parse(123)  # type: ignore[arg-type]


# ════════════════════════════════════════════════════════════════════════════
# 字符串化
# ════════════════════════════════════════════════════════════════════════════


class TestPlateVersionStr:
    def test_str_format(self) -> None:
        """业务需求:str(v) 输出 'major.minor.patch'。"""
        v = PlateVersion(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_round_trip_str_parse(self) -> None:
        """业务需求:str(v) → parse(s) → v。"""
        v = PlateVersion(5, 7, 9)
        assert PlateVersion.parse(str(v)) == v


# ════════════════════════════════════════════════════════════════════════════
# 序列化
# ════════════════════════════════════════════════════════════════════════════


class TestPlateVersionToFromDict:
    def test_to_dict_keys(self) -> None:
        """业务需求:to_dict 键固定 major/minor/patch。"""
        v = PlateVersion(1, 2, 3)
        d = v.to_dict()
        assert d == {"major": 1, "minor": 2, "patch": 3}

    def test_from_dict_round_trip(self) -> None:
        """业务需求:to_dict → from_dict 互逆。"""
        v = PlateVersion(4, 5, 6)
        assert PlateVersion.from_dict(v.to_dict()) == v

    def test_from_dict_missing_key_raises(self) -> None:
        """业务需求:缺失 patch 字段 → ValueError(严格不容错)。"""
        with pytest.raises(ValueError, match="缺失字段"):
            PlateVersion.from_dict({"major": 1, "minor": 2})  # type: ignore[dict-item]

    def test_from_dict_non_dict_raises(self) -> None:
        """业务需求:非 dict 输入 → ValueError。"""
        with pytest.raises(ValueError, match="期望 dict"):
            PlateVersion.from_dict([1, 2, 3])  # type: ignore[arg-type]

    def test_from_dict_non_numeric_raises(self) -> None:
        """业务需求:字段非数字 → ValueError。"""
        with pytest.raises(ValueError, match="字段类型错"):
            PlateVersion.from_dict({"major": "x", "minor": 2, "patch": 3})


# ════════════════════════════════════════════════════════════════════════════
# 不变式
# ════════════════════════════════════════════════════════════════════════════


class TestPlateVersionImmutability:
    def test_frozen_modify_major_raises(self) -> None:
        """业务需求:frozen=True,改字段抛 FrozenInstanceError。"""
        v = PlateVersion(1, 0, 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.major = 2  # type: ignore[misc]

    def test_is_final_marker(self) -> None:
        """业务需求:@final 装饰器在运行时打 __final__ 标记(对应 D10)。"""
        # Python 3.14+:getattr 检测运行时标记
        assert getattr(PlateVersion, "__final__", False) is True, (
            "PlateVersion 应被 @final 装饰(Python 3.14 改为运行时标记)"
        )


# ════════════════════════════════════════════════════════════════════════════
# 比较
# ════════════════════════════════════════════════════════════════════════════


class TestPlateVersionEquality:
    def test_equal_same_numbers(self) -> None:
        """业务需求:同字段值 → 相等。"""
        assert PlateVersion(1, 2, 3) == PlateVersion(1, 2, 3)

    def test_not_equal_different(self) -> None:
        """业务需求:不同字段值 → 不等。"""
        assert PlateVersion(1, 2, 3) != PlateVersion(1, 2, 4)

    def test_hashable(self) -> None:
        """业务需求:frozen → 可哈希 → 可作 dict key。"""
        d = {PlateVersion(1, 0, 0): "v1"}
        assert d[PlateVersion(1, 0, 0)] == "v1"