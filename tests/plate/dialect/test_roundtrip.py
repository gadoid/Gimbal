"""规范形往返测试（A1 首交付物之一，第 5 节「无损往返 = 语义等价」）。

锁死三件事,后续构件 / 适配戳 / diff 都依赖:
1. 语义等价往返:parse → render → parse 后,frontmatter / 块载荷 / 信封 /
   片段原文全部相等;
2. 规范形幂等:render(parse(render(parse(x)))) 与 render(parse(x)) 字节相等;
3. 块外散文原样保留(含行内 [[term-id]] 约定文本)。
"""
from __future__ import annotations

import pytest

from gimbal_plate.dialect import (
    Deliverable,
    EndpointSpec,
    Statement,
    Term,
    parse_markdown,
    render,
)

from ._samples import DICTIONARY_SAMPLE, ENDPOINTS_SAMPLE, PRD_SAMPLE


def _roundtrip_once(text: str) -> tuple[Deliverable, str, Deliverable]:
    d1 = parse_markdown(text, source="sample.md")
    rendered = render(d1)
    d2 = parse_markdown(rendered, source="rendered.md")
    return d1, rendered, d2


def _assert_nodes_equal(d1: Deliverable, d2: Deliverable) -> None:
    """语义等价:节点序列的载荷 / 信封 / 散文逐一相等(规范形可丢默认值)。"""
    assert len(d1.nodes) == len(d2.nodes), "节点数漂移"
    for n1, n2 in zip(d1.nodes, d2.nodes):
        assert type(n1) is type(n2), f"节点类型漂移: {type(n1)} vs {type(n2)}"
        if hasattr(n1, "text"):  # Prose
            assert n1.text == n2.text, "块外散文漂移"
            continue
        assert n1.type == n2.type, "块类型漂移"
        assert n1.review == n2.review, "块信封漂移"
        p1 = n1.payload if isinstance(n1.payload, list) else [n1.payload]
        p2 = n2.payload if isinstance(n2.payload, list) else [n2.payload]
        assert len(p1) == len(p2)
        for a, b in zip(p1, p2):
            if hasattr(a, "model_dump"):
                assert a.model_dump(mode="json") == b.model_dump(mode="json"), (
                    f"块载荷语义漂移: {a!r} vs {b!r}"
                )
            else:
                assert a == b


@pytest.mark.parametrize("sample", [PRD_SAMPLE, ENDPOINTS_SAMPLE, DICTIONARY_SAMPLE],
                         ids=["prd", "endpoints", "dictionary"])
def test_roundtrip_semantic_equal(sample: str) -> None:
    d1, _rendered, d2 = _roundtrip_once(sample)
    assert d1.frontmatter.model_dump() == d2.frontmatter.model_dump()
    _assert_nodes_equal(d1, d2)


@pytest.mark.parametrize("sample", [PRD_SAMPLE, ENDPOINTS_SAMPLE, DICTIONARY_SAMPLE],
                         ids=["prd", "endpoints", "dictionary"])
def test_render_idempotent_bytes(sample: str) -> None:
    """规范形幂等:再渲染一次,字节不动。"""
    r1 = render(parse_markdown(sample))
    r2 = render(parse_markdown(r1))
    assert r1 == r2


def test_prose_and_inline_convention_preserved() -> None:
    """块外散文原样保留;[[term-id]] 是普通文本(纯约定,不解析)。"""
    d1, rendered, _ = _roundtrip_once(PRD_SAMPLE)
    assert "[[cap:user.update]]" in rendered, "行内约定文本丢失"
    prose = [n.text for n in d1.nodes if hasattr(n, "text")]
    assert any("普通段落" in p for p in prose)


def test_statement_text_derived_from_following_prose() -> None:
    """片段原文 = 块后紧跟段落,直到下一个块或标题;render 后再派生一致。"""
    d1, _, d2 = _roundtrip_once(PRD_SAMPLE)
    st1 = {s.id: s for s in d1.statements()}
    assert st1["st.user-mgmt.last-admin"].text == "不能降级最后一个管理员。"
    # 第二个片段的原文跨一个空行段落 + 被普通段落截断(非标题,同属紧跟散文)
    assert "禁用管理员账户" in st1["st.user-mgmt.disable"].text
    st2 = {s.id: s for s in d2.statements()}
    for sid, s in st1.items():
        assert s.text == st2[sid].text, f"片段原文漂移: {sid}"


def test_envelope_review_roundtrip() -> None:
    """reviewed 信封往返保留;draft 缺省(渲染不写、解析补缺省)。"""
    d1, rendered, d2 = _roundtrip_once(PRD_SAMPLE)
    blocks1 = {b.line: b for b in d1.blocks()}
    reviewed = [b for b in d1.blocks() if b.review == "reviewed"]
    assert reviewed, "样本应含 reviewed 信封"
    assert "review: reviewed" in rendered
    # dictionary 列表块:信封逐对象写、解析后归一
    dd1, dr, dd2 = _roundtrip_once(DICTIONARY_SAMPLE)
    terms1 = dd1.blocks("term")[0].models()
    assert all(isinstance(t, Term) for t in terms1)
    assert dd1.blocks("term")[0].review == "reviewed"
    assert dd2.blocks("term")[0].review == "reviewed"
    _ = (blocks1, dd1, dr)


def test_endpoint_payload_semantics_after_roundtrip() -> None:
    """endpoints 样本:Binding / outcome 字符串键 / capability 往返不变。"""
    d2 = parse_markdown(render(parse_markdown(ENDPOINTS_SAMPLE)))
    (block,) = d2.blocks("endpoint")
    ep = block.payload
    assert isinstance(ep, EndpointSpec)
    assert ep.binding.method == "POST"
    assert ep.binding.protocol == "http"
    assert ep.binding.auth == "bearer"
    assert set(ep.responses) == {"200", "409"}
    assert ep.responses["200"].description == "更新成功"
    assert ep.capability == "cap:user.update"
    assert ep.consumes == ["attr:user.role"]
    # spec_path 锚点片段往返不变
    sts = {s.id: s for s in d2.statements()}
    assert sts["st.users.update-409"].anchor.startswith("platform.user.update ")
    assert isinstance(sts["st.users.update-409"], Statement)


def test_statement_text_absorbed_prose_not_duplicated() -> None:
    """片段原文所在散文仍是文档节点(渲染回写一次,不重复)。"""
    rendered = render(parse_markdown(ENDPOINTS_SAMPLE))
    assert rendered.count("409 时 data.user_id") == 1
