"""QueryView / ValueSource / query_safe 模型级校验(spec §3.1-§3.3)。"""
import pytest
from pydantic import ValidationError

from gimbal_plate.schema.endpoint import (
    ApiSpec, EndpointMetadata, EndpointSpec, RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry
from gimbal_plate.schema.endpoint.query_view import QueryView, ValueSource


def _spec(**kw) -> EndpointSpec:
    """最小合法端点(POST 版,便于测 query_safe)。"""
    base = dict(
        id="t.demo.ep", system="t", service="svc", name="demo",
        api=ApiSpec(service="svc", method="POST", path="/api/demo"),
        responses={200: ResponseSpec(status=200)},
    )
    base.update(kw)
    return EndpointSpec(**base)


class TestQueryViewShape:
    def test_ok(self):
        v = QueryView(name="cost_list", items="$.data[*]", label="cost_name")
        assert v.params is None

    @pytest.mark.parametrize("bad", [
        {"name": "cost list", "items": "$.d[*]", "label": "x"},   # name 非法字符
        {"name": "", "items": "$.d[*]", "label": "x"},            # name 空
        {"name": "v", "items": "data[*]", "label": "x"},          # items 不以 $. 开头
        {"name": "v", "items": "$.d[*]", "label": ""},            # label 空
    ])
    def test_rejected(self, bad):
        with pytest.raises(ValidationError):
            QueryView(**bad)


class TestValueSourceShape:
    def test_defaults(self):
        vs = ValueSource(view="cost_list")
        assert vs.column == "" and vs.group == ""

    def test_view_required(self):
        with pytest.raises(ValidationError):
            ValueSource(view="")


class TestEntryMutex:  # §3.3③
    def test_enum_and_value_source_rejected(self):
        with pytest.raises(ValidationError, match="互斥"):
            DeclarationEntry(name="a", path="a", type="string",
                             enum=["x"], value_source=ValueSource(view="v"))

    def test_value_source_alone_ok(self):
        e = DeclarationEntry(name="a", path="a", type="string",
                             value_source=ValueSource(view="v"))
        assert e.value_source.view == "v"


class TestQuerySafeAndClosure:  # §3.3④⑤
    def test_non_get_without_query_safe_rejected(self):
        with pytest.raises(ValidationError, match="query_safe"):
            _spec(query_views=[QueryView(name="v", items="$.d[*]", label="x")])

    def test_non_get_with_query_safe_ok(self):
        ep = _spec(metadata=EndpointMetadata(query_safe=True),
                   query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        assert ep.query_views[0].name == "v"

    def test_get_view_without_params_closure_ok(self):
        ep = _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
                   query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        assert ep.metadata.query_safe is False  # GET 不要求

    def test_required_key_double_none_rejected(self):
        decls = [DeclarationEntry(name="q", path="q", type="string", required=True)]
        with pytest.raises(ValidationError, match="必填键"):
            _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
                  request=RequestSpec(declarations=decls),
                  query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        # 可选键双 None → 合法(缺省不携带)
        decls_opt = [DeclarationEntry(name="q", path="q", type="string", required=False)]
        _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
              request=RequestSpec(declarations=decls_opt),
              query_views=[QueryView(name="v", items="$.d[*]", label="x")])

    def test_falsy_values_are_not_missing(self):
        # 空串/0/false 是合法值,不算缺(required 键 example='' 也闭合)
        decls = [DeclarationEntry(name="q", path="q", type="string",
                                  required=True, example="")]
        _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
              request=RequestSpec(declarations=decls),
              query_views=[QueryView(name="v", items="$.d[*]", label="x")])


class TestResolveViewParams:
    def test_merge_semantics(self):
        decls = [
            DeclarationEntry(name="a", path="a", type="string", required=True, default="DA"),
            DeclarationEntry(name="b", path="b", type="string", required=True, example="EB"),
            DeclarationEntry(name="c", path="c", type="string", required=False),
        ]
        ep = _spec(metadata=EndpointMetadata(query_safe=True),
                   request=RequestSpec(declarations=decls),
                   query_views=[QueryView(name="v", params={"a": "OV", "z": 1},
                                          items="$.d[*]", label="x")])
        from gimbal_plate.schema.endpoint.query_view import resolve_view_params
        merged, missing = resolve_view_params(ep, ep.query_views[0])
        assert merged == {"a": "OV", "b": "EB", "z": 1}   # 覆盖 a / 补 b / 追加 z / 丢 c
        assert missing == []


# ── §13.2 query_params 点击期参数面 ──────────────────────────────

def test_query_params_params_collision_rejected():
    """query_params × params 同名 = 构造期拒(静态身份与点击期变量分家)。"""
    with pytest.raises(ValidationError, match="同名冲突"):
        QueryView(name="v", params={"status": "2"}, query_params=["status"],
                  items="$.data[*]", label="n")


def test_query_params_dot_name_rejected():
    """名字禁点:预填只读顶层 '$.<name>',嵌套键不做预填源(§13.7)。"""
    with pytest.raises(ValidationError, match="不含"):
        QueryView(name="v", query_params=["a.b"], items="$.data[*]", label="n")


def test_query_params_default_none_ok():
    v = QueryView(name="v", items="$.data[*]", label="n")
    assert v.query_params is None   # 缺省无参 = 现状行为零变化


def test_closure_exempts_query_params_keys():
    """⑤ 豁免:必填键在 query_params → 构造期不拒(点击期供给 §13.2);
    索引仍透出 missing_required(backend 422 兜底)。"""
    ep = EndpointSpec(
        id="t.customer.part", system="t", service="t-service", name="part",
        api=ApiSpec(service="t-service", method="POST", path="/p", auth="none"),
        request=RequestSpec(body_type="json", declarations=[
            DeclarationEntry(name="customer_id", path="$.customer_id",
                             type="string", required=True, ui_kind="text"),
        ]),
        responses={200: ResponseSpec(status=200)},
        metadata=EndpointMetadata(query_safe=True),
        query_views=[QueryView(name="v_part", query_params=["customer_id"],
                               items="$.data", label="x")],
    )
    assert ep.query_views[0].query_params == ["customer_id"]   # 构造通过即豁免成立
