"""PR-D2:FieldBinding 落地测试。

业务动机:FieldBinding 是声明性依赖,描述"端点 A 需要端点 B 的某个字段"。
本 PR 只验证类型/字段/校验,不验证批量化(那是 PR-D4)。

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
  1. 业务需求(声明性依赖的硬约束)
  2. 对应设计章节
  3. 业务影响(违反此约束的代价)
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import BaseModel, ConfigDict

from Plate.binding import FieldBinding, _KNOWN_TRANSFORMS
from Plate.spec import EndpointCategory, EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 共用 fixture
# ════════════════════════════════════════════════════════════════════════════


def _good_model(name: str) -> type[BaseModel]:
    """构造一个合规的 Pydantic 模型(extra=forbid)。"""
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def _make_spec(
    *,
    method: str = "POST",
    path: str = "/api/test/x",
    request: type[BaseModel] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
    bindings: tuple[FieldBinding, ...] = (),
    category: EndpointCategory = EndpointCategory.QUERY,
    mutates_state: bool = False,
) -> EndpointSpec:
    """构造一个最小合规的 EndpointSpec(便于 bindings 测试复用)。"""
    return EndpointSpec(
        method=method,
        path=path,
        category=category,
        mutates_state=mutates_state,
        request=request if request is not None else _good_model("Req"),
        responses=responses if responses is not None else {200: _good_model("Resp")},
        bindings=bindings,
    )


# ════════════════════════════════════════════════════════════════════════════
# FieldBinding 自身
# ════════════════════════════════════════════════════════════════════════════


def test_field_binding_default_required_true() -> None:
    """业务需求:FieldBinding 默认 ``required=True``(注入失败必须硬错)。

    对应设计:§2.2 required 默认值约定。
    业务影响:默认 False = 注入失败静默跳过,生产环境拿不到关键 ID 仍继续
             调用下游 = 真实事故。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    assert b.required is True
    assert b.transform is None


def test_field_binding_frozen() -> None:
    """业务需求:FieldBinding 不可变(frozen)。

    对应设计:§2.2 "@final + frozen=True"。
    业务影响:可写 = 多线程下 binding 被另一线程改写,跨端点依赖静默失真。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    with pytest.raises((FrozenInstanceError, AttributeError)):
        b.from_path = ("other",)  # type: ignore[misc]


def test_field_binding_hashable() -> None:
    """业务需求:FieldBinding 可作 set / dict key。

    对应设计:后续 spec dedup 用。
    业务影响:不可哈希 = 无法做"等价 binding 检测",review pipeline 难去重。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    s = {b}
    assert b in s
    # 同样的内容应 hash 相等(frozen dataclass 行为)
    b2 = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    assert b == b2
    assert hash(b) == hash(b2)


def test_field_binding_with_transform() -> None:
    """业务需求:FieldBinding 接受显式 ``transform`` 字符串(描述性)。

    对应设计:§2.2 transform 字段定义。
    业务影响:transform 缺 = binding 写"int->str" 时只能 str 字段,失去灵活性。
    """
    b = FieldBinding(
        from_path=("data", "id"),
        to_path=("order_id",),
        transform="int->str",
    )
    assert b.transform == "int->str"


def test_field_binding_with_required_false() -> None:
    """业务需求:FieldBinding 接受 ``required=False``(静默跳过)。

    对应设计:§2.2 required 字段定义。
    业务影响:某些 binding(如可选的审计字段)应静默跳过,无需硬错。
    """
    b = FieldBinding(
        from_path=("data", "audit_id"),
        to_path=("audit_id",),
        required=False,
    )
    assert b.required is False


# ════════════════════════════════════════════════════════════════════════════
# EndpointSpec 集成
# ════════════════════════════════════════════════════════════════════════════


def test_endpoint_spec_default_bindings_empty_tuple() -> None:
    """业务需求:EndpointSpec 默认 ``bindings=空 tuple``。

    对应设计:§2.3 字段默认值约定。
    业务影响:PR-D2 不要求存量端点必须标注,PR-D4 才批量化。
    """
    spec = _make_spec()
    assert spec.bindings == ()
    assert isinstance(spec.bindings, tuple)


def test_endpoint_spec_with_single_binding_constructs() -> None:
    """业务需求:EndpointSpec 接受单个 binding 构造。

    对应设计:§2.3 字段定义。
    业务影响:此约束是 PR-D4 批量化的前置;若构造失败,PR-D4 无法落地。
    """
    b = FieldBinding(from_path=("data", "order_id"), to_path=("order_id",))
    spec = _make_spec(bindings=(b,))
    assert len(spec.bindings) == 1
    assert spec.bindings[0] is b


def test_endpoint_spec_with_multiple_bindings_preserves_order() -> None:
    """业务需求:多 binding 时顺序保持。

    对应设计:§2.3 tuple 语义。
    业务影响:顺序乱 = "后注入的覆盖先注入的"风险。
    """
    b1 = FieldBinding(from_path=("a",), to_path=("x",))
    b2 = FieldBinding(from_path=("b",), to_path=("y",))
    spec = _make_spec(bindings=(b1, b2))
    assert spec.bindings[0] is b1
    assert spec.bindings[1] is b2


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝(注册期 fail-fast)
# ════════════════════════════════════════════════════════════════════════════


def test_binding_non_fieldbinding_type_raises() -> None:
    """业务需求:bindings 里塞非 FieldBinding 元素硬错。

    对应设计:§2.4 类型校验。
    业务影响:接受任意对象 = 序列化时崩溃,review pipeline 无法静态分析。
    """
    with pytest.raises(TypeError) as exc:
        _make_spec(bindings=("not-a-binding",))  # type: ignore[arg-type]
    assert "FieldBinding" in str(exc.value)


def test_binding_empty_to_path_raises() -> None:
    """业务需求:to_path 不能为空 tuple。

    对应设计:§2.4 "注入目标必须明确"。
    业务影响:允许空 to_path = 注入位置语义模糊(整个 body?覆盖?),
             消费者无法处理。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=())  # 空
    with pytest.raises(ValueError) as exc:
        _make_spec(bindings=(b,))
    assert "to_path" in str(exc.value)


def test_binding_empty_from_path_allowed() -> None:
    """业务需求:``from_path`` 允许为空 tuple(表示整个 body)。

    对应设计:§2.2 from_path 字段定义("空 tuple = 整个 body")。
    业务影响:整个 body 注入(如"对方返回啥我全收")是合法 use case,
             不允许空 = 这种场景无法表达。
    """
    b = FieldBinding(from_path=(), to_path=("payload",))
    spec = _make_spec(bindings=(b,))
    assert spec.bindings[0].from_path == ()


def test_binding_unknown_transform_raises() -> None:
    """业务需求:transform 必须在白名单内。

    对应设计:§2.5 白名单约定。
    业务影响:接受任意字符串 = review pipeline 无法静态校验"未实现 transform"。
    """
    b = FieldBinding(
        from_path=("data", "id"),
        to_path=("order_id",),
        transform="not-a-real-transform",
    )
    with pytest.raises(ValueError) as exc:
        _make_spec(bindings=(b,))
    assert "transform" in str(exc.value)


def test_binding_known_transform_constructs() -> None:
    """业务需求:白名单内 transform 应正常构造。

    对应设计:§2.5 白名单约定。
    业务影响:白名单过严 = PR-D4 标注 binding 时大量无法落地。
    """
    for t in (
        "identity",
        "int->str",
        "str->int",
        "iso8601->epoch",
        "epoch->iso8601",
    ):
        b = FieldBinding(
            from_path=("data", "id"),
            to_path=("order_id",),
            transform=t,
        )
        spec = _make_spec(bindings=(b,))
        assert spec.bindings[0].transform == t


def test_binding_transform_none_allowed() -> None:
    """业务需求:``transform=None`` 合法(无转换)。

    对应设计:§2.2 transform 字段默认 None。
    业务影响:多数 binding 实际不需要转换,None = "直接赋值"语义。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",), transform=None)
    spec = _make_spec(bindings=(b,))
    assert spec.bindings[0].transform is None


def test_binding_known_transforms_set_contents() -> None:
    """业务需求:``_KNOWN_TRANSFORMS`` 白名单内容(防止 review pipeline 漂移)。

    对应设计:§2.5 白名单初始集。
    业务影响:白名单内容变了 = review pipeline 误报/漏报。
    """
    assert _KNOWN_TRANSFORMS == frozenset(
        {
            "identity",
            "int->str",
            "str->int",
            "iso8601->epoch",
            "epoch->iso8601",
        }
    )


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式未破
# ════════════════════════════════════════════════════════════════════════════


def test_bindings_field_is_frozen() -> None:
    """业务需求:EndpointSpec.bindings 在 frozen 实例上不可写。

    对应设计:§2.3 frozen 不变式。
    业务影响:可写 = 多线程 race condition,依赖关系被静默改写。
    """
    spec = _make_spec(
        bindings=(FieldBinding(from_path=("a",), to_path=("b",)),),
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.bindings = ()  # type: ignore[misc]


def test_endpoint_spec_is_final() -> None:
    """业务需求:EndpointSpec 是 @final(不允许继承)。

    对应设计:拉式收集用 ``type(attr) is EndpointSpec`` 严格匹配。
    业务影响:可继承 = 子类绕过 __post_init__ 校验,review pipeline 失真。

    注:Python 3.14 起 ``@final`` 不再在子类化时抛 TypeError,改为静态检查器
    提示;运行时只能验证 ``__final__`` 标记存在(typing.final 的运行时副作用)。
    """
    # 1. @final 装饰器被应用(运行时 __final__ = True)
    assert getattr(EndpointSpec, "__final__", False) is True, (
        "EndpointSpec 应被 @final 装饰(Python 3.14 改为运行时标记,"
        "不再在子类化时抛错)"
    )
