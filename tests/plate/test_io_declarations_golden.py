# tests/plate/test_io_declarations_golden.py
"""IO 声明归一化 golden 三角(spec §8 ①②③)。

fixture 纪律:基线物化提交进库;corpus 漂移 = 红,强制 diff 可见的
意识性 re-baseline(改 fixture 必须单开 commit 说明原因)。
"""
import json
import os
from pathlib import Path

import pytest

from gimbal_plate.http.views import EndpointDetailView
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS

FIXTURE = Path(__file__).parent / "fixtures" / "io_full_pre_p1.json"
FIXTURE_DECL = Path(__file__).parent / "fixtures" / "io_declarations_p1.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))
LEGACY_REQUEST_KEYS = {"body_type", "fields", "schema", "carry"}
LEGACY_RESPONSE_KEYS = {"status", "description", "fields", "assertable_fields", "schema"}


def _full_dict(ep) -> dict:
    return EndpointDetailView.from_spec(ep).model_dump(mode="json", exclude_none=True)


def _ep_payloads() -> dict:
    return {ep.id: _full_dict(ep) for ep in ALL_ENDPOINTS}


def _decl_payloads() -> dict:
    """declarations 快照:从 _full_dict 里摘取 declarations 键。

    必须与 Task 9 ② 的比对走同一序列化出口(EndpointDetailView.
    model_dump(mode="json", exclude_none=True))。若另走
    declarations_view() 旁路捕获,exclude_none 对嵌套 dict 的裁剪
    行为差异会在 ② 处爆成假红;同出口捕获,任何裁剪两侧自然抵消。
    """
    out = {}
    for ep in ALL_ENDPOINTS:
        full = _full_dict(ep)
        d: dict = {}
        if (full.get("request") or {}).get("declarations"):
            d["request"] = full["request"]["declarations"]
        resp = {str(code): r["declarations"]
                for code, r in full.get("responses", {}).items()
                if r.get("declarations")}
        if resp:
            d["responses"] = resp
        if d:
            out[ep.id] = d
    return out


def test_capture_or_equal() -> None:
    """① 前半:capture 模式写盘;断言模式锁既有键,新增仅 declarations。"""
    live = _ep_payloads()
    # 捕获只补缺,从不覆写:fixture 提交后,任何 CAPTURE 运行(含 Task 4
    # 的第二基线捕获)都落进比对分支 —— pre_p1 不可能被 P1 末态静默污染
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        pytest.skip("baseline captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(live) == set(base), "端点集合漂移"
    for ep_id in base:
        _assert_request(base[ep_id], live[ep_id])
        for code in base[ep_id].get("responses", {}):
            _assert_response(base[ep_id]["responses"][code],
                             live[ep_id]["responses"][code])


def _assert_request(base: dict, live: dict) -> None:
    if base.get("request") is None:
        assert live.get("request") is None
        return
    lr, lv = base["request"], live["request"]
    for k in LEGACY_REQUEST_KEYS & lr.keys():
        assert lv.get(k) == lr[k], f"request.{k} 漂移"
    assert set(lv) - set(lr) <= {"declarations"}, "新增键超出 declarations"


def _assert_response(base: dict, live: dict) -> None:
    for k in LEGACY_RESPONSE_KEYS & base.keys():
        assert live.get(k) == base[k], f"response.{k} 漂移"
    assert set(live) - set(base) <= {"declarations"}, "新增键超出 declarations"


def test_capture_or_equal_declarations() -> None:
    """P1 末 declarations 快照(② 的比对基线)。"""
    live = _decl_payloads()
    # 捕获只补缺,不覆写(与 pre_p1 同款守卫)
    if CAPTURE and not FIXTURE_DECL.exists():
        FIXTURE_DECL.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        pytest.skip("declarations baseline captured")
    base = json.loads(FIXTURE_DECL.read_text(encoding="utf-8"))
    assert live == base, "declarations 漂移(P1 末基线,Task 9 ② 依赖)"


def test_baseline_counts() -> None:
    """基线计数权威:667 = 568 + 99(fixture 实测;2026-09-02 执行日重钉)。

    计划/spec 原钉 631 = 532 + 99 为 grep 出现级计数 —— 两个 *_order_page
    端点的响应面由 _ROW_FIELDS 推导式各生成 19 条(grep 不可见),fixture
    实测 568 条 fields;fixture 捕获为最终权威(计划 Global Constraints)。
    """
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bindings = sum(len((b.get("request") or {}).get("fields") or [])
                   for b in base.values())
    views = sum(len(r.get("fields") or [])
                for b in base.values()
                for r in b.get("responses", {}).values())
    carries = sum(len((b.get("request") or {}).get("carry") or {})
                  for b in base.values())
    assert bindings + views == 568, (
        f"binding/view_only 总数 {bindings + views} != 568"
        "(若红:以 fixture 实测重新核对 spec §0.3 并意识性更新)"
    )
    assert carries == 99
