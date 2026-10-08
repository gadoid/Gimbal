"""YAML 1.2 core 口径测试(修订十一;N1 回归钉)。

解析端在 PyYAML 上以自定义 resolver 实现 1.2 core 隐式类型(零新依赖):
- 留空的值必须是 null——不是 ''(评审 N1:首字符未按列表登记空串键时,
  ``a:`` / ``- `` 会静默变空串,进而进规范形/hash、``refers:`` 留空变
  指向 '');
- 1.1 专有隐式转换不再发生(on/yes→bool、12:30→750、日期→date);
- 1.2 core 数值形态照常(十进制/0o/0x/浮点/科学计数);
- 渲染歧义判定与解析同口径(双向:1.1 与 1.2 任一误读都加引号)。
"""
from __future__ import annotations

import pytest

from gimbal_plate.dialect.parser import DialectError, strict_yaml_load
from gimbal_plate.dialect.renderer import _is_ambiguous
from gimbal_plate.dialect import parse_markdown


class TestCoreScalars:
    def test_12_core_semantics(self) -> None:
        d = strict_yaml_load(
            "on: on\nyes: yes\ntime: 12:30\ndate: 2026-10-08\n"
            "oct: 0o10\nhex: 0x1F\nsci: 1e3\nlead_zero: 01\n"
            "keep: true\nnul: null\n",
            source="t.md", line=1)
        assert d["on"] == "on" and isinstance(d["on"], str)
        assert d["yes"] == "yes"
        assert d["time"] == "12:30"
        assert d["date"] == "2026-10-08"          # 1.1 会变 date 对象
        assert d["oct"] == 8 and d["hex"] == 31
        assert d["sci"] == 1000.0
        assert d["lead_zero"] == 1                # 1.2 core:十进制(1.1 是八进制)
        assert d["keep"] is True and d["nul"] is None

    def test_empty_values_are_null_not_empty_string(self) -> None:
        """评审 N1:留空的值必须是 None——映射值、序列项、行内留空皆然。"""
        d = strict_yaml_load("a:\nb: \nc: null\nd:\n  - \n  - x\ne: ~\n",
                             source="t.md", line=1)
        assert d == {"a": None, "b": None, "c": None,
                     "d": [None, "x"], "e": None}

    def test_refers_left_empty_is_none(self) -> None:
        """后果链守卫:``refers:`` 留空若变 '' 会通过 Optional[str] 校验,
        变成指向空串的悬空引用。"""
        md = ("---\ntype: dictionary\n---\n```gimbal:term\n"
              "- id: attr:a.b\n  label: B\n  refers:\n```\n")
        term = parse_markdown(md, source="t.md").blocks("term")[0].models()[0]
        assert term.refers is None

    def test_duplicate_keys_rejected(self) -> None:
        with pytest.raises(DialectError):
            strict_yaml_load("name: a\nname: b\n", source="t.md", line=1)


class TestRenderAmbiguity:
    @pytest.mark.parametrize("value", [
        "01", "08", "1e3", "0o10", "on", "off", "yes", "12:30",
        "null", "true", "200", "2026-10-08",
    ])
    def test_ambiguous_scalars_quoted(self, value: str) -> None:
        assert _is_ambiguous(value), value

    @pytest.mark.parametrize("value", [
        "abc", "user-role", "hello world", "GIMBAL-728", "1F",
    ])
    def test_plain_scalars_unquoted(self, value: str) -> None:
        assert not _is_ambiguous(value), value
