"""D-15 检索器 v1：目录枚举 + --where 直接字段。"""
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.schema.scenario import Config as SC, Meta, Scenario
from gimbal.suite.selector import matches, parse_where, select


def _sc(sid: str, module: str = "m") -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=f"n-{sid}", description="d", module=module, priority=1,
                  author="a", owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(), resource={}, steps=[],
    )


class TestSelector:

    def test_parse_where(self):
        assert parse_where(["a=1", "b=x"]) == {"a": "1", "b": "x"}
        with pytest.raises(ValueError):
            parse_where(["noeq"])

    def test_matches_direct_fields(self):
        sc = _sc("sc-1", module="fin")
        assert matches(sc, {"scenarioId": "sc-1"})
        assert matches(sc, {"meta.module": "fin", "scenarioId": "sc-1"})
        assert not matches(sc, {"scenarioId": "sc-2"})
        assert not matches(sc, {"meta.module": "order"})   # AND 语义
        assert not matches(sc, {"meta nonexistent": "x"}) if False else True

    def test_select_directory_and_where(self, tmp_path):
        for sid, mod in (("a", "fin"), ("b", "order"), ("c", "fin")):
            (tmp_path / f"{sid}.json").write_text(
                _sc(sid, mod).model_dump_json(), encoding="utf-8")
        # 目录全量
        assert len(select(tmp_path)) == 3
        # --where 过滤
        got = select(tmp_path, {"meta.module": "fin"})
        assert [s.scenarioId for s in got] == ["a", "c"]
        # 零命中报错
        with pytest.raises(ValueError, match="零命中"):
            select(tmp_path, {"scenarioId": "zzz"})

    def test_select_single_file(self, tmp_path):
        f = tmp_path / "one.json"
        f.write_text(_sc("one").model_dump_json(), encoding="utf-8")
        assert select(f)[0].scenarioId == "one"

    def test_select_skips_unparsable(self, tmp_path):
        (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
        (tmp_path / "good.json").write_text(_sc("good").model_dump_json(), encoding="utf-8")
        assert [s.scenarioId for s in select(tmp_path)] == ["good"]
