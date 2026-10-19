"""b2-2|ref 分类器契约测试(归一方案 v1.0 D-K/实施计划 v1.1 b2-2)。

两侧各自对照同一份 fixture 独立断言(plate 侧见 tests/plate/
test_ext_unify_b1.py;不在运行时互相调用):
- 声明域:tests/fixtures/ref-decl-domain.json(仓库根,两侧同源);
- 记录域:frontend/src/types/__fixtures__/ref-record-domain.json
  (后端 record_category 与前端判定函数共享,前后端同源)。
生产代码不读 fixture;分类器若漂移,两侧测试同时红。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.run_semantics import (
    INTEGRATION,
    INVALID,
    PIN,
    UNDECLARED,
    WORKING,
    invalid_reason,
    record_category,
    ref_category,
)

REPO = Path(__file__).resolve().parents[4]
DECL_FIXTURE = REPO / "tests" / "fixtures" / "ref-decl-domain.json"
RECORD_FIXTURE = (REPO / "src" / "gimbal-platform" / "frontend" / "src"
                  / "types" / "__fixtures__" / "ref-record-domain.json")


_CANON = {"WORKING": WORKING, "INTEGRATION": INTEGRATION, "PIN": PIN,
          "UNDECLARED": UNDECLARED, "INVALID": INVALID}


def test_declaration_domain_matches_fixture() -> None:
    data = json.loads(DECL_FIXTURE.read_text(encoding="utf-8"))
    for case in data["valid"]:
        assert ref_category(case["ref"]) == _CANON[case["category"]], case
    for case in data["invalid"]:
        assert ref_category(case["ref"]) == INVALID, case
        assert invalid_reason(case["ref"]) == case["reason"], case
    for case in data["declaration_only"]:
        # 平台声明域:裸线拒(missing_revision);plate 取数域合法由 plate 侧断言
        assert ref_category(case["ref"]) == INVALID, case
        assert invalid_reason(case["ref"]) == case["declaration_reason"], case


def test_undeclared() -> None:
    assert ref_category("") == UNDECLARED
    assert ref_category(None) == UNDECLARED  # type: ignore[arg-type]


def test_record_domain_matches_fixture() -> None:
    for case in json.loads(RECORD_FIXTURE.read_text(encoding="utf-8"))["cases"]:
        assert record_category(case["value"]) == _CANON[case["category"]], case


def test_categories_exported() -> None:
    for sym in (WORKING, INTEGRATION, PIN, INVALID, UNDECLARED):
        assert isinstance(sym, str)
