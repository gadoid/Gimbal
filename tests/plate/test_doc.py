"""PR-D3:EndpointDoc L2 物理解耦测试。

业务动机:L1(spec,机器可再生)与 L2(doc,人工写)物理分离,防止 L1 重生成冲掉 L2。
本 PR 只验证 doc 类型 + dannotations 目录结构 + 对称性,不要求存量补注释。

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
  1. 业务需求(L1/L2 分离的硬约束)
  2. 对应设计章节
  3. 业务影响(违反此约束的代价)
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from Plate.doc import EndpointDoc, _SUMMARY_MAX_LEN


# ════════════════════════════════════════════════════════════════════════════
# EndpointDoc 自身
# ════════════════════════════════════════════════════════════════════════════


def test_endpoint_doc_minimal_constructs() -> None:
    """业务需求:只填 summary 可构造。

    对应设计:PR-D3 §2.2 字段默认值约定。
    业务影响:其他字段都必填 = 写注释成本太高,没人愿意写。
    """
    doc = EndpointDoc(summary="按订单 ID 查询订单详情")
    assert doc.summary == "按订单 ID 查询订单详情"
    assert doc.notes == ()
    assert doc.requires == ()
    assert doc.see_also == ()


def test_endpoint_doc_full_constructs() -> None:
    """业务需求:4 个字段都填时构造正常。

    对应设计:PR-D3 §2.2 字段定义。
    业务影响:此约束是 review pipeline 校验的前提。
    """
    doc = EndpointDoc(
        summary="按订单 ID 查询详情",
        notes=("限流:每用户 10 QPS", "时区:UTC+8"),
        requires=("已登录",),
        see_also=("/api/order/order/addOrder",),
    )
    assert len(doc.notes) == 2
    assert len(doc.requires) == 1
    assert len(doc.see_also) == 1
    assert "限流" in doc.notes[0]


# ════════════════════════════════════════════════════════════════════════════
# summary 长度强校
# ════════════════════════════════════════════════════════════════════════════


def test_summary_too_long_raises() -> None:
    """业务需求:summary 长度 > 120 字符硬错。

    对应设计:PR-D3 §2.2 summary 长度上限。
    业务影响:超长 summary = AI 总结时被截,语义失真,后续看到残片误调用。
    """
    with pytest.raises(ValueError) as exc:
        EndpointDoc(summary="x" * 121)
    assert "120" in str(exc.value)


def test_summary_at_limit_constructs() -> None:
    """业务需求:summary 正好 120 字符可通过。

    对应设计:PR-D3 §2.2 边界值约定。
    业务影响:边界值误判(< 而非 ≤) = 卡死临界长度。
    """
    doc = EndpointDoc(summary="x" * _SUMMARY_MAX_LEN)
    assert len(doc.summary) == _SUMMARY_MAX_LEN


def test_summary_empty_or_whitespace_raises() -> None:
    """业务需求:summary 不能为空或全空白。

    对应设计:PR-D3 §2.2 summary 必填。
    业务影响:空 summary = 等于没注释,浪费一个文件。
    """
    with pytest.raises(ValueError):
        EndpointDoc(summary="")
    with pytest.raises(ValueError):
        EndpointDoc(summary="   \t\n  ")


# ════════════════════════════════════════════════════════════════════════════
# list-like 字段必须 tuple
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("field_name", ["notes", "requires", "see_also"])
def test_list_field_must_be_tuple(field_name: str) -> None:
    """业务需求:list-like 字段必须是 tuple(满足 frozen 不可变)。

    对应设计:PR-D3 §2.2 frozen 不变式。
    业务影响:接受 list = 可被外部 .append(),doc 被静默改写。
    """
    with pytest.raises(TypeError) as exc:
        EndpointDoc(summary="x", **{field_name: ["a", "b"]})  # type: ignore[arg-type]
    assert "tuple" in str(exc.value)


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式
# ════════════════════════════════════════════════════════════════════════════


def test_endpoint_doc_frozen() -> None:
    """业务需求:EndpointDoc 不可写。

    对应设计:PR-D3 §2.2 frozen 约定。
    业务影响:可写 = 多线程下 doc 被静默改,误导 AI 消费。
    """
    doc = EndpointDoc(summary="x")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        doc.summary = "y"  # type: ignore[misc]


def test_endpoint_doc_is_final() -> None:
    """业务需求:EndpointDoc 是 @final(不允许继承)。

    对应设计:PR-D3 §2.2 复用 PLATE_DESIGN 拉式收集原则(类比 EndpointSpec)。
    业务影响:可继承 = 子类绕过 __post_init__ 校验,review pipeline 失真。

    注:Python 3.14 起 ``@final`` 不再子类化抛错(D10),运行时验证
    ``__final__`` 标记存在。
    """
    assert getattr(EndpointDoc, "__final__", False) is True, (
        "EndpointDoc 应被 @final 装饰(D10:Python 3.14 改为运行时标记)"
    )


# ════════════════════════════════════════════════════════════════════════════
# dannotations 目录结构
# ════════════════════════════════════════════════════════════════════════════


def test_fin_dannotations_module_importable() -> None:
    """业务需求:fin/dannotations 模块可被 import(空壳)。

    对应设计:PR-D3 §2.3 物理分离约定。
    业务影响:目录不存在 = L2 注释无处存放,PR-D4 之后的注释补全无落地点。
    """
    import Plate.fin.dannotations
    assert hasattr(Plate.fin.dannotations, "_DOCS")
    assert isinstance(Plate.fin.dannotations._DOCS, dict)


def test_fin_dannotations_empty_initially() -> None:
    """业务需求:dannotations/_DOCS 初始可为空(本 PR 不强制存量)。

    对应设计:PR-D3 §1.3 "不强制存量"。
    业务影响:若初始就预填所有 endpoint = 本 PR 范围爆炸,违背"渐进"原则。

    注:不强 assert == 0(防 PR-D4 之前有补内容),只校验类型。
    """
    from Plate.fin.dannotations import _DOCS
    assert isinstance(_DOCS, dict)


def test_get_doc_returns_none_for_missing() -> None:
    """业务需求:get_doc 找不到时返回 None(不抛错)。

    对应设计:PR-D3 §2.4 get_doc 契约。
    业务影响:抛 KeyError = 消费方必须 try/except,API 难用。
    """
    from Plate.fin.dannotations import get_doc
    assert get_doc("/non/existent/path") is None
