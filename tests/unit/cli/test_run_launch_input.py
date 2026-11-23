"""run_launch 输入归一测试(2026-11-23,收尾批次 4-1)。

此前 `.txt`/`.text` 输入静默落入 `_parse_text` 占位,产出无人消费的
``__raw_text__`` 标记 dict(fail-silent);本批收口:
* `.txt`/`.text` 与未知扩展名同走内容嗅探 —— txt 装 json/yaml 可用;
* 真不可解析文本 → 显式 InputError;
* `_parse_text` 转防御性显式报错(auto 嗅探后不应残留)。
"""
from __future__ import annotations

import json

import pytest

from gimbal.cli.commands.run_launch import (
    InputError,
    _detect_format,
    _parse_text,
    normalize_input,
)
from gimbal.cli.common import InputFormat

JSON_BODY = json.dumps({"scenarioId": "sc-in-1", "steps": []})
YAML_BODY = "scenarioId: sc-in-2\nsteps: []\n"
FREE_TEXT = "这不是结构化用例,只是普通文本。\n第二行。\n"


# ── _detect_format:扩展名与嗅探 ────────────────────────────────────
def test_detect_explicit_passthrough() -> None:
    assert _detect_format(InputFormat.json, "{}", None) is InputFormat.json
    assert _detect_format(InputFormat.yaml, "a: 1", None) is InputFormat.yaml


def test_detect_by_extension() -> None:
    assert _detect_format(InputFormat.auto, "{}", ".json") is InputFormat.json
    assert _detect_format(InputFormat.auto, "a: 1", ".yaml") is InputFormat.yaml
    assert _detect_format(InputFormat.auto, "a: 1", ".yml") is InputFormat.yaml


def test_detect_txt_falls_through_to_sniff() -> None:
    """`.txt` 不再返回 auto 残值(旧径直落 _parse_text 占位)。"""
    assert _detect_format(InputFormat.auto, JSON_BODY, ".txt") is InputFormat.json
    assert _detect_format(InputFormat.auto, YAML_BODY, ".text") is InputFormat.yaml


def test_detect_empty_input_rejected() -> None:
    with pytest.raises(InputError, match="输入内容为空"):
        _detect_format(InputFormat.auto, "   \n", None)


# ── normalize_input:文件源全链 ───────────────────────────────────
@pytest.mark.parametrize(
    ("content", "expect_id"),
    [(JSON_BODY, "sc-in-1"), (YAML_BODY, "sc-in-2")],
)
def test_normalize_txt_file_parses_structured_content(
        tmp_path, content: str, expect_id: str) -> None:
    f = tmp_path / "case.txt"
    f.write_text(content, encoding="utf-8")
    payload = normalize_input(str(f), None, InputFormat.auto)
    assert payload["scenarioId"] == expect_id


def test_normalize_txt_free_text_fails_closed(tmp_path) -> None:
    """真不可解析文本 → 显式 InputError(fail-closed,不再静默)。"""
    f = tmp_path / "case.txt"
    f.write_text(FREE_TEXT, encoding="utf-8")
    with pytest.raises(InputError, match="顶层必须是"):
        # 自由文本被 yaml 解析成 str,顶层非 dict → 明确报错
        normalize_input(str(f), None, InputFormat.auto)


def test_parse_text_defensive_raises() -> None:
    """占位退役:被调到即上游契约破裂,显式报错不产 __raw_text__。"""
    with pytest.raises(InputError, match="自由文本"):
        _parse_text("anything")
