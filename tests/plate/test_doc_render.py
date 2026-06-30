"""Plate API doc 渲染层测试(Phase 3 §4.1)。

对应设计:``design/phase3/PR-3.1.md`` §3.1。

测试策略:
  - 不依赖 ``Plate.fin`` 实际数据(避免被真实端点集合绑定)
  - 用 ``make_spec`` 工厂函数构造测试用 ``EndpointSpec``
  - 单元测试 12 个,覆盖 §3.1 全部场景
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from Plate.api_doc.render import render_endpoint, render_service
from Plate.binding import FieldBinding
from Plate.doc import EndpointDoc
from Plate.spec import EndpointCategory, EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 测试夹具工厂
# ════════════════════════════════════════════════════════════════════════════


class _ReqA(BaseModel):
    """最小请求模型 A(测试用)。"""
    model_config = ConfigDict(extra="forbid")


class _ReqB(BaseModel):
    """最小请求模型 B(测试用)。"""
    model_config = ConfigDict(extra="forbid")


class _Resp(BaseModel):
    """最小响应模型(测试用)。"""
    model_config = ConfigDict(extra="forbid")


def make_spec(
    *,
    method: str = "POST",
    path: str = "/api/test/x",
    category: EndpointCategory = EndpointCategory.BUSINESS,
    mutates_state: bool = True,
    summary: str = "",
    tags: list[str] | None = None,
    request: type[BaseModel] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
    bindings: tuple[FieldBinding, ...] = (),
) -> EndpointSpec:
    """工厂:用最宽松的 defaults 构造 EndpointSpec。

    mutates_state 强制与 category 一致(否则 EndpointSpec.__post_init__ 会拒绝):
      - BUSINESS: mutates_state=True
      - QUERY/TOOL: mutates_state=False
    """
    if category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
        mutates_state = False
    return EndpointSpec(
        method=method,
        path=path,
        category=category,
        mutates_state=mutates_state,
        summary=summary,
        tags=tags if tags is not None else [],
        request=request,
        responses=responses if responses is not None else {},
        bindings=bindings,
    )


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #1: BUSINESS 单 endpoint
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointBusiness:
    def test_business_endpoint_renders_method_path_header(self):
        spec = make_spec(path="/api/order/add", summary="创建订单")
        out = render_endpoint(spec)
        assert "### POST /api/order/add" in out
        assert "**summary**: 创建订单" in out
        assert "**category**: business (业务接口)" in out
        assert "**mutates_state**: True" in out

    def test_business_endpoint_tags_comma_separated(self):
        spec = make_spec(tags=["order", "write", "invoice"])
        out = render_endpoint(spec)
        assert "**tags**: order, write, invoice" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #2: QUERY endpoint
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointQuery:
    def test_query_endpoint_category_and_mutates_false(self):
        spec = make_spec(
            path="/api/order/detail",
            category=EndpointCategory.QUERY,
            summary="订单详情",
        )
        out = render_endpoint(spec)
        assert "**category**: query (查询接口)" in out
        assert "**mutates_state**: False" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #3: TOOL endpoint(预留)
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointTool:
    def test_tool_endpoint_label(self):
        spec = make_spec(
            path="/api/sys/captcha",
            category=EndpointCategory.TOOL,
            summary="获取验证码",
        )
        out = render_endpoint(spec)
        assert "**category**: tool (工具接口)" in out
        assert "**mutates_state**: False" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #4: L2 doc 缺失
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointL2Missing:
    def test_missing_l2_doc_shows_placeholder(self):
        spec = make_spec()
        out = render_endpoint(spec, doc=None)
        assert "**业务备注**: (无 L2 注释)" in out

    def test_missing_l2_doc_does_not_raise(self):
        spec = make_spec()
        # 不抛错 = 通过
        out = render_endpoint(spec, doc=None)
        assert isinstance(out, str)
        assert out.endswith("\n")


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #5/6: L2 doc 提供 summary / notes / requires / see_also
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointL2Present:
    def test_l2_summary_differs_from_spec_summary(self):
        spec = make_spec(summary="spec 版本")
        doc = EndpointDoc(summary="L2 版本")
        out = render_endpoint(spec, doc)
        assert "**L2 summary**: L2 版本" in out
        # spec.summary 也保留(因为不同)
        assert "**summary**: spec 版本" in out

    def test_l2_summary_same_as_spec_not_duplicated(self):
        spec = make_spec(summary="相同")
        doc = EndpointDoc(summary="相同")
        out = render_endpoint(spec, doc)
        # 不显示 L2 summary 行(spec.summary 已显示,避免重复)
        assert "**L2 summary**" not in out

    def test_l2_notes_rendered_as_list(self):
        spec = make_spec()
        doc = EndpointDoc(summary="x", notes=("限流 10 QPS", "时区 UTC+8"))
        out = render_endpoint(spec, doc)
        assert "**注意事项(notes)**:" in out
        assert "- 限流 10 QPS" in out
        assert "- 时区 UTC+8" in out

    def test_l2_requires_rendered(self):
        spec = make_spec()
        doc = EndpointDoc(summary="x", requires=("已登录", "订单属于当前用户"))
        out = render_endpoint(spec, doc)
        assert "**前置条件(requires)**:" in out
        assert "- 已登录" in out

    def test_l2_see_also_inline(self):
        spec = make_spec()
        doc = EndpointDoc(summary="x", see_also=("/api/order/add", "/api/order/detail"))
        out = render_endpoint(spec, doc)
        assert "**see_also**: /api/order/add, /api/order/detail" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #7: field_bindings 多条
# ════════════════════════════════════════════════════════════════════════════


class TestRenderEndpointBindings:
    def test_no_bindings_no_section(self):
        spec = make_spec()
        out = render_endpoint(spec)
        # 没有 bindings 时,"字段绑定(bindings)"标题不应出现
        assert "字段绑定" not in out

    def test_single_binding(self):
        spec = make_spec(
            bindings=(
                FieldBinding(
                    from_path=("data", "order_id"),
                    to_path=("order_id",),
                ),
            )
        )
        out = render_endpoint(spec)
        assert "**字段绑定(bindings)**:" in out
        assert "`order_id` ← `data.order_id`" in out

    def test_multiple_bindings_each_on_own_line(self):
        spec = make_spec(
            bindings=(
                FieldBinding(from_path=("data", "a"), to_path=("a",)),
                FieldBinding(from_path=("data", "b"), to_path=("b",)),
            )
        )
        out = render_endpoint(spec)
        # 两条独立行
        line_a = [ln for ln in out.splitlines() if "`a` ←" in ln]
        line_b = [ln for ln in out.splitlines() if "`b` ←" in ln]
        assert len(line_a) == 1
        assert len(line_b) == 1

    def test_binding_with_transform(self):
        spec = make_spec(
            bindings=(
                FieldBinding(
                    from_path=("data", "epoch"),
                    to_path=("ts",),
                    transform="epoch->iso8601",
                ),
            )
        )
        out = render_endpoint(spec)
        assert "[transform: epoch->iso8601]" in out

    def test_optional_binding_marked(self):
        spec = make_spec(
            bindings=(
                FieldBinding(from_path=("data", "x"), to_path=("x",), required=False),
            )
        )
        out = render_endpoint(spec)
        assert "[optional]" in out

    def test_body_level_binding(self):
        """``FieldBinding`` 不允许空 tuple(会被 ``__post_init__`` 拒绝);
        这里用单元素 tuple 表示"指向 body 顶层字段"。
        """
        spec = make_spec(
            bindings=(
                FieldBinding(from_path=("data",), to_path=("payload",)),
            )
        )
        out = render_endpoint(spec)
        assert "`payload` ← `data`" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #8/9: 排序(BUSINESS → QUERY → TOOL,同 category 内 path 字典序)
# ════════════════════════════════════════════════════════════════════════════


class TestRenderServiceOrdering:
    def test_category_order_business_query_tool(self):
        specs = [
            make_spec(path="/q/x", category=EndpointCategory.QUERY),
            make_spec(path="/t/x", category=EndpointCategory.TOOL),
            make_spec(path="/b/x", category=EndpointCategory.BUSINESS),
        ]
        out = render_service("test", specs, doc_lookup=None)
        b_pos = out.find("业务接口")
        q_pos = out.find("查询接口")
        t_pos = out.find("工具接口")
        assert b_pos < q_pos < t_pos

    def test_same_category_sorted_by_path(self):
        specs = [
            make_spec(path="/api/z", category=EndpointCategory.BUSINESS),
            make_spec(path="/api/a", category=EndpointCategory.BUSINESS),
            make_spec(path="/api/m", category=EndpointCategory.BUSINESS),
        ]
        out = render_service("test", specs, doc_lookup=None)
        a_pos = out.find("/api/a")
        m_pos = out.find("/api/m")
        z_pos = out.find("/api/z")
        assert a_pos < m_pos < z_pos

    def test_empty_category_section_skipped(self):
        # 只有 BUSINESS,无 QUERY/TOOL
        specs = [make_spec(category=EndpointCategory.BUSINESS)]
        out = render_service("test", specs, doc_lookup=None)
        assert "业务接口" in out
        assert "查询接口" not in out
        assert "工具接口" not in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #10: 空 spec 列表
# ════════════════════════════════════════════════════════════════════════════


class TestRenderServiceEmpty:
    def test_empty_specs_renders_header_with_zero(self):
        out = render_service("empty", [], doc_lookup=None)
        assert "# empty 服务 API 文档" in out
        assert "> 共 0 个端点,0 个有 L2 注释" in out

    def test_empty_specs_no_category_sections(self):
        out = render_service("empty", [], doc_lookup=None)
        assert "业务接口" not in out
        assert "查询接口" not in out
        assert "工具接口" not in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 #11/12: tags 边界
# ════════════════════════════════════════════════════════════════════════════


class TestTagsEdges:
    def test_empty_tags_no_tags_line(self):
        spec = make_spec(tags=[])
        out = render_endpoint(spec)
        assert "**tags**" not in out

    def test_tags_with_spaces(self):
        spec = make_spec(tags=["has space", "comma,inside"])
        out = render_endpoint(spec)
        # tags 直传,不处理空格/逗号嵌套(用户责任)
        assert "has space" in out
        assert "comma,inside" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 补:service 总览 + with_l2 计数
# ════════════════════════════════════════════════════════════════════════════


class TestServiceSummary:
    def test_total_count_in_overview(self):
        specs = [make_spec(path=f"/api/x/{i}") for i in range(5)]
        out = render_service("svc", specs, doc_lookup=None)
        assert "> 共 5 个端点,0 个有 L2 注释" in out

    def test_with_l2_count_via_lookup(self):
        specs = [
            make_spec(path="/api/has-doc"),
            make_spec(path="/api/no-doc"),
        ]

        def lookup(path: str) -> EndpointDoc | None:
            return EndpointDoc(summary="doc") if path == "/api/has-doc" else None

        out = render_service("svc", specs, doc_lookup=lookup)
        assert "> 共 2 个端点,1 个有 L2 注释" in out


# ════════════════════════════════════════════════════════════════════════════
# §3.1 补:request / responses 模型类名渲染
# ════════════════════════════════════════════════════════════════════════════


class TestRequestResponseModels:
    def test_request_model_class_name_shown(self):
        spec = make_spec(request=_ReqA)
        out = render_endpoint(spec)
        assert "**request**: `_ReqA`" in out

    def test_responses_models_each_on_own_line(self):
        spec = make_spec(responses={200: _Resp, 404: _Resp})
        out = render_endpoint(spec)
        assert "- `200`: `_Resp`" in out
        assert "- `404`: `_Resp`" in out

    def test_no_request_no_line(self):
        spec = make_spec(request=None)
        out = render_endpoint(spec)
        assert "**request**" not in out


# ════════════════════════════════════════════════════════════════════════════
# #1 不变量:零侵入(导入不触发 fin 加载)
# ════════════════════════════════════════════════════════════════════════════


class TestZeroInvasion:
    def test_importing_api_doc_does_not_load_fin(self):
        import sys

        # 清掉可能已加载的 fin
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("Plate.fin"):
                del sys.modules[mod_name]

        # 触发 api_doc 顶层 import
        import importlib

        if "Plate.api_doc" in sys.modules:
            importlib.reload(sys.modules["Plate.api_doc"])

        loaded = [m for m in sys.modules if m.startswith("Plate.fin")]
        assert loaded == [], (
            f"不变量 #1 违反:importing Plate.api_doc 触发了 {loaded} 加载。"
            f"render 层应该只 import Plate.spec / Plate.doc,不 import Plate.fin。"
        )