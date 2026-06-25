"""PR-B:EndpointCategory + mutates_state 字段测试。

业务动机:CT 主动探测必须避免触发业务写入(PLATE_DESIGN §3.2)。
EndpointSpec 引入 category + mutates_state 字段,允许消费者(CT / Mock server /
AI skill)在不知具体业务逻辑的情况下,判断"这个接口能不能主动探测"。

测试用例面向业务需求,docstring 三段式:
  1. 业务需求
  2. 对应设计章节
  3. 业务影响(违反此约束的代价)
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import BaseModel, ConfigDict

from Plate.spec import EndpointCategory, EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 共享 fixture:合规 Pydantic 模型(extra="forbid")
# ════════════════════════════════════════════════════════════════════════════


def _good_model() -> type[BaseModel]:
    """构造一个合规的 Pydantic 模型(extra=forbid,字段最小)。"""
    return type(
        "Resp",
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# 默认值兜底(PR-B §2.3)
# ════════════════════════════════════════════════════════════════════════════


def test_default_category_is_business() -> None:
    """业务需求:未指定 category 时,默认 BUSINESS + mutates_state=True。

    对应设计:PLATE_DESIGN.md §2.1 字段默认值约定。
    业务影响:默认值必须与 31 个 fin 端点现状匹配(BUSINESS 是最常见),
             否则 PR-B 一上来就 break 所有现有 spec。
    """
    spec = EndpointSpec(method="GET", path="/x", responses={200: _good_model()})
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


def test_existing_fin_endpoints_still_constructible() -> None:
    """业务需求:PR-0.2 之后所有 fin 端点仍能用默认 category 构造。

    对应设计:PR-B §1.3 "不强制存量标注,仅加字段"。
    业务影响:任何现有调用破坏 = 31 端点全部需要重写。
    """
    # 等价于 fin 真实端点的简化构造,验证默认值兜底对真实路径不破
    spec = EndpointSpec(
        method="POST",
        path="/api/order/order/orderDetail",
        request=_good_model(),
        responses={200: _good_model()},
    )
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


# ════════════════════════════════════════════════════════════════════════════
# category 合法值(PLATE_DESIGN §3.3 + §3.2)
# ════════════════════════════════════════════════════════════════════════════


def test_category_business_may_mutate_state() -> None:
    """业务需求:BUSINESS 类接口可以 mutates_state=True(典型写操作)。

    对应设计:PLATE_DESIGN.md §3.2 "category 是结论,mutates_state 是事实"。
    业务影响:BUSINESS 不应被禁止 mutates_state=True,否则无法表达写操作。
    """
    spec = EndpointSpec(
        method="POST",
        path="/api/order/add",
        category=EndpointCategory.BUSINESS,
        mutates_state=True,
        responses={200: _good_model()},
    )
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


def test_category_query_must_not_mutate_state() -> None:
    """业务需求:QUERY 类接口可以 mutates_state=False(典型只读查询)。

    对应设计:PLATE_DESIGN.md §3.2 "category in (QUERY, TOOL) ⇒ mutates_state is False"。
    业务影响:QUERY 接口被 CT 主动探测,若 mutates_state=True 会触发业务写入(真实事故风险)。
    """
    spec = EndpointSpec(
        method="POST",
        path="/api/order/detail",
        category=EndpointCategory.QUERY,
        mutates_state=False,
        responses={200: _good_model()},
    )
    assert spec.category is EndpointCategory.QUERY
    assert spec.mutates_state is False


def test_category_tool_must_not_mutate_state() -> None:
    """业务需求:TOOL 类接口可以 mutates_state=False(系统级能力,无状态变更)。

    对应设计:PLATE_DESIGN.md §3.2。
    业务影响:同 QUERY(CT 主动探测)。
    """
    spec = EndpointSpec(
        method="GET",
        path="/api/system/dict",
        category=EndpointCategory.TOOL,
        mutates_state=False,
        responses={200: _good_model()},
    )
    assert spec.category is EndpointCategory.TOOL
    assert spec.mutates_state is False


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝(注册期 fail-fast,PR-B §2.4)
# ════════════════════════════════════════════════════════════════════════════


def test_query_with_mutates_state_true_raises() -> None:
    """业务需求:QUERY + mutates_state=True 是硬错,注册期拒绝。

    对应设计:PLATE_DESIGN.md §3.2 + §3.4(c) review pipeline 强制规则。
    业务影响:允许此组合 = CT 探测可能在生产触发业务写入(真实事故风险)。
    """
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="POST",
            path="/x",
            category=EndpointCategory.QUERY,
            mutates_state=True,
            responses={200: _good_model()},
        )
    assert "category" in str(exc.value)
    assert "mutates_state" in str(exc.value)


def test_tool_with_mutates_state_true_raises() -> None:
    """业务需求:TOOL + mutates_state=True 是硬错。

    对应设计:PLATE_DESIGN.md §3.4(c)。
    业务影响:同 QUERY — CT 主动探测会触发业务写入。
    """
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="GET",
            path="/x",
            category=EndpointCategory.TOOL,
            mutates_state=True,
            responses={200: _good_model()},
        )
    assert "category" in str(exc.value)


def test_query_with_mutates_state_none_raises() -> None:
    """业务需求:QUERY + mutates_state=None 视为"未明确",硬错拒绝(防 None 滑过)。

    对应设计:PR-B §2.4 "用 ``is False`` 不用 ``not``"(严格判断)。
    业务影响:用 ``not mutates_state`` 会被 None 滑过,留下静默不一致;
             用 ``is False`` 强制作者显式表态(True/False 二选一)。
    """
    with pytest.raises(ValueError):
        EndpointSpec(
            method="POST",
            path="/x",
            category=EndpointCategory.QUERY,
            mutates_state=None,  # type: ignore[arg-type]
            responses={200: _good_model()},
        )


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式未破(PLATE_DESIGN §2.1)
# ════════════════════════════════════════════════════════════════════════════


def test_category_field_is_frozen() -> None:
    """业务需求:category 字段在 frozen 实例上不可写。

    对应设计:PLATE_DESIGN.md §2.1 "@final + frozen=True"。
    业务影响:字段可写 = 多线程 race condition,锁外拿到的 spec snapshot 被改。
    """
    spec = EndpointSpec(
        method="POST",
        path="/x",
        category=EndpointCategory.QUERY,
        mutates_state=False,
        responses={200: _good_model()},
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.category = EndpointCategory.BUSINESS  # type: ignore[misc]


def test_mutates_state_field_is_frozen() -> None:
    """业务需求:mutates_state 字段在 frozen 实例上不可写。

    对应设计:PLATE_DESIGN.md §2.1 "@final + frozen=True"。
    业务影响:同 test_category_field_is_frozen —— 锁外 snapshot 失守。
    """
    spec = EndpointSpec(
        method="POST",
        path="/x",
        category=EndpointCategory.QUERY,
        mutates_state=False,
        responses={200: _good_model()},
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.mutates_state = True  # type: ignore[misc]