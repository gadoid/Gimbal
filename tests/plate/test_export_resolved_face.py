"""导出面基准切解析链(2026-09-07 spec §3.3)—— #6 穿线的行为面。

`_render_request_view` 面基准从 entry.state(共识默认)换
resolve_state(path, entry.state, step.field_states)(解析态):
- carry 面(解析态)= 不补默认 + 仅透传 body 已有字面量;
- form/collapse 面 = 补全链不变(body → default → example → None,D7);
- fields_meta 登记面 = 解析态非 carry 顶层条目,条目 state = 解析态;
- 端点级 request_fields 无场景语境,维持 entry.state 读穿;
- 存量零漂:field_states=None 时输出与切换前逐键相等(读穿等价)。
"""
from __future__ import annotations

from datetime import UTC, datetime

from gimbal_plate.export.platform import (
    PlatformScenarioExporter,
    _render_endpoint_view,
    _render_request_view,
)
from gimbal_plate.schema.api import Api
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.request import Request
from gimbal_plate.schema.scenario import Config, Meta, Scenario as ScenarioModel
from gimbal_plate.schema.step import Step


# ── 构造糖 ─────────────────────────────────────────────

def _leaf(**kw) -> DeclarationEntry:
    base = dict(name="x", path="$.x", type="string")
    base.update(kw)
    return DeclarationEntry(**base)


def _ep(declarations: list[DeclarationEntry]) -> EndpointSpec:
    return EndpointSpec(
        id="tst.resolved_face", system="tst", service="tst-service",
        name="resolved_face", description="解析链导出面测试端点",
        api=ApiSpec(service="tst-service", method="POST", path="/resolved-face"),
        request=RequestSpec(body_type="json", declarations=declarations),
        responses={200: ResponseSpec(status=200)},
    )


def _meta() -> Meta:
    return Meta(
        name="resolved-face", description="导出解析链", module="plate",
        priority=1, author="t", owner="t", tags=[], version="1",
        createTime=datetime.now(UTC), expire=False, requirementRef=[],
    )


# 语料:form 叶(带默认)+ carry 叶(共识)+ carry 容器(子孙 carry 共识)
_FORM_LEAF = _leaf(
    name="order_id", path="$.order_id", default="DEF-O",
)
_CARRY_LEAF = _leaf(
    name="remark", path="$.remark", state="carry",
)
_CARRY_CONTAINER = DeclarationEntry(
    name="supplier", path="$.supplier", type="array", state="carry",
    children=[_leaf(
        name="order_supplier_id", path="$.supplier.order_supplier_id",
        state="carry",
    )],
)

_EP = _ep([_FORM_LEAF, _CARRY_LEAF, _CARRY_CONTAINER])


# ── ① form→carry 增量:不补默认 / 不进 fields_meta / 透传字面量 ──────


def test_form_to_carry_increment():
    out = _render_request_view(
        Request(body={"remark": "literal-remark"}),
        _EP,
        {"$.order_id": "carry", "$.remark": "carry"},
    )
    # order_id(共识 form,增量 carry):默认 DEF-O 不补;无字面量即无键
    assert "order_id" not in out["body"]
    # remark 透传 body 已有字面量
    assert out["body"]["remark"] == "literal-remark"
    # fields_meta 登记面:两条解析态 carry 均不登记
    assert "order_id" not in out["fields_meta"]
    assert "remark" not in out["fields_meta"]


# ── ② carry→form 增量:补默认 + 登记 + state='form' ─────────────────


def test_carry_to_form_increment():
    out = _render_request_view(
        Request(body={}),
        _EP,
        {"$.remark": "form"},
    )
    # 共识 carry、增量 form:进补全面(default 链)—— remark 无 default → None 平铺占位
    assert out["body"]["remark"] is None
    # 登记 + 条目 state = 解析态(合成态诚实)
    assert out["fields_meta"]["remark"]["state"] == "form"
    # 共识面不受扰动:order_id 照常补默认
    assert out["body"]["order_id"] == "DEF-O"


# ── ③ 容器整 sink:整树不补(级联批量增量的规范形态)────────────────


def test_container_sink_whole_tree_skipped():
    """sink 级联(§2.3)落盘形态 = 容器 + 子孙同 carry 增量。
    导出面逐条读解析态:容器与子孙全部不补,仅透传容器字面量。"""
    out = _render_request_view(
        Request(body={"supplier": [{"order_supplier_id": "S-9"}]}),
        _EP,
        {"$.supplier": "carry", "$.supplier.order_supplier_id": "carry"},
    )
    assert out["body"]["supplier"] == [{"order_supplier_id": "S-9"}]
    assert "supplier" not in out["fields_meta"]


# ── ④ 深层 surface(祖先增量随行):补叶子 ──────────────────────────


def test_deep_surface_no_default_no_skeleton():
    """surface 后深叶解析 form 但无 default/example → D7 深层不落 None
    骨架(容器 collapse 不挡该纪律);顶层登记面照常(state=collapse)。"""
    ep = _ep([_FORM_LEAF, _CARRY_CONTAINER])
    out = _render_request_view(
        Request(body={}),
        ep,
        {
            "$.supplier.order_supplier_id": "form",
            "$.supplier": "collapse",
        },
    )
    assert "supplier" not in out["body"]  # D7:无值不造骨架
    assert out["fields_meta"]["supplier"]["state"] == "collapse"


def test_deep_surface_fills_leaf_with_default():
    """深叶带默认:surface 增量(form)后默认落嵌套(容器 collapse 不挡)。"""
    ep = _ep([_FORM_LEAF, DeclarationEntry(
        name="supplier", path="$.supplier", type="object", state="carry",
        children=[_leaf(
            name="order_supplier_id", path="$.supplier.order_supplier_id",
            state="carry", default="DEF-SID",
        )],
    )])
    out = _render_request_view(
        Request(body={}),
        ep,
        {
            "$.supplier.order_supplier_id": "form",
            "$.supplier": "collapse",
        },
    )
    assert out["body"]["supplier"]["order_supplier_id"] == "DEF-SID"
    # 登记条目 state = 解析态(collapse),树内子叶 state 同步解析(form)
    assert out["fields_meta"]["supplier"]["state"] == "collapse"
    child = out["fields_meta"]["supplier"]["children"][0]
    assert child["state"] == "form"


# ── ⑤ 存量零漂:无增量输出与读穿逐键相等 ───────────────────────────


def test_no_increment_read_through_equivalence():
    """field_states=None ↔ 不传参(旧行为)输出逐键相等 —— M1 读穿等价。"""
    req = Request(body={"order_id": "O-1", "supplier": [{"order_supplier_id": "S-1"}]})
    assert _render_request_view(req, _EP, None) == _render_request_view(req, _EP)
    # 全量字面:共识面产物(form 补默认 / carry 透传 / 容器字面量打底)
    out = _render_request_view(req, _EP, None)
    assert out == {
        "kind": "request",
        "body": {
            "order_id": "O-1",
            "supplier": [{"order_supplier_id": "S-1"}],
        },
        "fields_meta": {
            "order_id": {
                "name": "order_id", "path": "$.order_id", "type": "string",
                "state": "form", "required": False, "default": "DEF-O",
                "description": "", "ui_kind": "unknown",
                "source_kind": "independent", "assertable": False,
            },
        },
    }


# ── ⑥ 端点级 request_fields 不受场景增量影响(共识默认领地)─────────


def test_endpoint_request_fields_ignores_scenario_increments():
    sc = ScenarioModel(
        scenarioId="sc-resolved-face",
        meta=_meta(), config=Config(), resource={},
        steps=[Step(
            api=Api(service="tst-service", method="POST", path="/resolved-face"),
            request=Request(body={}),
            field_states={"$.order_id": "carry"},
        )],
    )
    exporter = PlatformScenarioExporter(sc, endpoints=[_EP])
    view = exporter.to_view()
    ep_view = view.endpoints[0]
    names = {f["name"]: f["state"] for f in ep_view.request_fields}
    # 端点级读穿共识:order_id 仍 form(场景增量 carry 不污染端点聚合面)
    assert names["order_id"] == "form"
    # 步级导出面已按解析态:order_id(解析 carry)不进 fields_meta
    step_req = view.steps[0].request
    assert "order_id" not in step_req["fields_meta"]


# ── 端到端:调用点穿线(scenario → view 全链)───────────────────────


def test_exporter_threads_field_states_end_to_end():
    """platform.py:592 调用点穿 s.field_states —— #6 缺口的完整修复链。"""
    sc = ScenarioModel(
        scenarioId="sc-resolved-face-e2e",
        meta=_meta(), config=Config(), resource={},
        steps=[Step(
            api=Api(service="tst-service", method="POST", path="/resolved-face"),
            request=Request(body={}),
            field_states={"$.order_id": "carry"},
        )],
    )
    view = PlatformScenarioExporter(sc, endpoints=[_EP]).to_view()
    req = view.steps[0].request
    # 解析 carry:默认不补、不登记
    assert "order_id" not in req["body"]
    assert "order_id" not in req["fields_meta"]


def test_render_endpoint_view_signature_stable():
    """_render_endpoint_view 无场景语境参数 —— 端点视图函数签名零漂。"""
    import inspect
    sig = inspect.signature(_render_endpoint_view)
    assert list(sig.parameters) == ["ep", "body_samples"]
