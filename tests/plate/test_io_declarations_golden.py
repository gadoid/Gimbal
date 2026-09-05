# tests/plate/test_io_declarations_golden.py
"""IO 声明 golden(spec §8 ②)。

P2 存储翻转后 wire 只剩 declarations(legacy fields/carry/assertable_fields
键与 pre_p1 基线已随桥退役),declarations 快照即唯一 golden。

fixture 纪律:基线物化提交进库;corpus 漂移 = 红,强制 diff 可见的
意识性 re-baseline(改 fixture 必须单开 commit 说明原因)。
"""
import json
import os
from pathlib import Path

import pytest

from gimbal_plate.http.views import EndpointDetailView
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, RequestSpec
from gimbal_plate.systems.fin.endpoint import (
    ALL_ENDPOINTS, SETTLEMENT_CREATE_ORDER,
)
from gimbal_plate.systems.fin.models import CreateOrderRequest

FIXTURE_DECL = Path(__file__).parent / "fixtures" / "io_declarations_p1.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))


def _full_dict(ep) -> dict:
    return EndpointDetailView.from_spec(ep).model_dump(mode="json", exclude_none=True)


def _decl_payloads() -> dict:
    """declarations 快照:从 _full_dict 里摘取 declarations 键。

    必须与比对走同一序列化出口(EndpointDetailView.model_dump(mode="json",
    exclude_none=True))。若另走旁路捕获,exclude_none 对嵌套 dict 的裁剪
    行为差异会爆成假红;同出口捕获,任何裁剪两侧自然抵消。
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
    """golden:live declarations == 基线;corpus 漂移必须 diff 可见。"""
    live = _decl_payloads()
    # 捕获只补缺,从不覆写:fixture 提交后,任何 CAPTURE 运行都落进
    # 比对分支 —— 基线不可能被后续改动静默污染
    if CAPTURE and not FIXTURE_DECL.exists():
        FIXTURE_DECL.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_DECL.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        pytest.skip("declarations baseline captured")
    base = json.loads(FIXTURE_DECL.read_text(encoding="utf-8"))
    assert live == base, "declarations 漂移(golden 基线)"


def test_baseline_state_counts() -> None:
    """基线计数权威(2026-09-05 目录化 re-baseline):fixture 实测。

    旧 901 = 570 binding/view_only + 331 carry 为 channel 轴口径,已退役;
    新口径为 state 轴(form/collapse/carry,响应面条目默认 form)。
    children 树内条目不在顶层 declarations 快照内,另行累计。
    """
    base = json.loads(FIXTURE_DECL.read_text(encoding="utf-8"))
    states: dict[str, int] = {}
    for ep in base.values():
        for e in ep.get("request") or []:
            states[e["state"]] = states.get(e["state"], 0) + 1
        for r in ep.get("responses", {}).values():
            for e in r:
                states[e["state"]] = states.get(e["state"], 0) + 1
    total = sum(states.values())
    assert states.get("form", 0) + states.get("collapse", 0) > 0, (
        "form/collapse 面应非空(响应面 + 请求表单面)"
    )
    assert states.get("carry", 0) > 300, (
        f"carry 面 {states.get('carry', 0)} 条(09-05 口径 ≈ 旧 331;"
        "若红:深实例缩并/端点增删后以 fixture 实测意识性重钉)"
    )
    assert "binding" not in states and "view_only" not in states, (
        "channel 轴键不得出现在 state 基线"
    )


class TestSettlementDeclare:
    """declare() 糖(spec §8 ③):手写字面量与 declare() 输出全键相等。"""

    def test_handwritten_equals_declare(self) -> None:
        # 手写反填:字面量来自 declare() 输出实测,并对模型源码抽查锚定
        # (order_id: str 无默认 → required=True/default=None;
        #  amount: int gt 0 无默认 → required=True/ui_kind=number 自 type 推断;
        #  currency: str = "CNY" → default="CNY"/required=False;
        #  remark 的 description 来自模型字段串,states 盖戳 carry)
        handwritten = RequestSpec(
            body_type="json",
            declarations=[
                DeclarationEntry(name="order_id", path="$.order_id",
                                 type="string",
                                 required=True, description="业务订单号",
                                 ui_kind="text"),
                DeclarationEntry(name="amount", path="$.amount",
                                 type="integer",
                                 required=True, description="结算金额,单位分",
                                 ui_kind="number"),
                DeclarationEntry(name="currency", path="$.currency",
                                 type="string",
                                 required=False, default="CNY",
                                 description="币种", ui_kind="text"),
                DeclarationEntry(name="remark", path="$.remark",
                                 state='carry', type="string", required=False,
                                 description="订单备注(carry 传递字段)",
                                 ui_kind="text"),
            ],
        )
        sugared = RequestSpec.declare(
            CreateOrderRequest,
            states={"remark": "carry"},
        )
        assert handwritten.declarations == sugared.declarations
        assert handwritten.model_dump(mode="json") == sugared.model_dump(mode="json")
