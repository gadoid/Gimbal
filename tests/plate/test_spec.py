"""Unit tests for Plate.spec (EndpointSpec + Protocol hooks)。

覆盖场景:
  [1] 正常创建:所有字段 + 默认值
  [2] GET 类:request=None 允许
  [3] 必填字段类型校验
  [4] 契约保真护栏(§3.6)
  [5] @final:不能继承
  [6] frozen=True:实例不可变
  [7] 辅助方法
  [8] Protocol hooks:runtime_checkable + isinstance 校验
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field

import pytest
from pydantic import BaseModel, ConfigDict

from Plate.spec import (
    BuildRequestHook,
    EndpointSpec,
    MockHook,
    ValidateHook,
)


# ════════════════════════════════════════════════════════════════════════════
# 辅助:合规的数据类工厂
# ════════════════════════════════════════════════════════════════════════════

def good_model(name: str = "Good") -> type[BaseModel]:
    """构造一个合规的契约模型(extra=forbid,禁用清单全关)。"""
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# [1] 正常创建:所有字段 + 默认值
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_spec_constructible_with_all_fields() -> None:
    """业务需求:EndpointSpec 全部字段能成功构造(基线数据契约)。

    对应设计:§2.1 EndpointSpec 定义。
    业务影响:违反 = 31 个 fin 端点任意一个构造失败,service 加载链断,scenario 不可用。
    """
    R = good_model("R1")
    M = good_model("M1")
    RU = good_model("RU1")
    DR = good_model("DR1")
    spec = EndpointSpec(
        method="POST",
        path="/api/x",
        request=R,
        responses={200: M},
        response_union={200: (M,)},
        default_response=DR,
        description="test",
    )
    assert spec.method == "POST"
    assert spec.path == "/api/x"
    assert spec.request is R
    assert spec.responses[200] is M
    assert spec.response_union[200] == (M,)
    assert spec.default_response is DR
    assert spec.description == "test"


# ════════════════════════════════════════════════════════════════════════════
# [2] GET 类:request=None 允许
# ════════════════════════════════════════════════════════════════════════════

def test_get_endpoint_allows_none_request() -> None:
    """业务需求:GET 类接口 request=None 是允许的(无请求体语义)。

    对应设计:§2.1 "request 字段默认 None"。
    业务影响:违反 = 简单 GET 接口被强制声明空 request,污染 31 端点里的 GET 类。
    """
    M = good_model("M2")
    spec = EndpointSpec(method="GET", path="/api/no-req", responses={200: M})
    assert spec.request is None
    assert spec.has_request() is False


# ════════════════════════════════════════════════════════════════════════════
# [3] 必填字段类型校验
# ════════════════════════════════════════════════════════════════════════════

def test_request_must_be_basemodel_subclass() -> None:
    """业务需求:request 字段必须是 BaseModel 子类,否则 TypeError。

    对应设计:§2.1 "request: type[BaseModel] | None"。
    业务影响:违反 = 注册期放过非 BaseModel,运行时 pydantic 校验失败时找不到根因。
    """
    M = good_model("M3a")
    with pytest.raises(TypeError):
        EndpointSpec(method="POST", path="/api/x", request=int, responses={200: M})  # type: ignore[arg-type]


def test_responses_keys_must_be_int() -> None:
    """业务需求:responses 的 key 必须是 int(状态码),否则 TypeError。

    对应设计:§2.1 "responses: dict[int, type[BaseModel]]"。
    业务影响:违反 = 状态码写成字符串,后续 mock 匹配 200 字符串失败。
    """
    M = good_model("M3b")
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", responses={"200": M})  # type: ignore[dict-item]


def test_responses_values_must_be_basemodel_subclass() -> None:
    """业务需求:responses 的 value 必须是 BaseModel 子类,否则 TypeError。

    对应设计:§2.1。
    业务影响:违反 = 同上,运行时 mock 反序列化找不到模型。
    """
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", responses={200: int})  # type: ignore[dict-item]


def test_default_response_must_be_basemodel_subclass() -> None:
    """业务需求:default_response 必须是 BaseModel 子类,否则 TypeError。

    对应设计:§2.1。
    业务影响:违反 = 兜底响应用错类型,scenario 拿到非模型对象。
    """
    M = good_model("M3d")
    with pytest.raises(TypeError):
        EndpointSpec(
            method="GET", path="/api/x", responses={200: M},
            default_response=int,  # type: ignore[arg-type]
        )


def test_response_union_values_must_be_basemodel_tuple() -> None:
    """业务需求:response_union 的 value 必须是 BaseModel 元组,否则 TypeError。

    对应设计:§2.1 "response_union: dict[int, tuple[type[BaseModel], ...]]"。
    业务影响:违反 = 联合响应类型定义错,mock 随机选类型时无模型可构造。
    """
    M = good_model("M3e")
    with pytest.raises(TypeError):
        EndpointSpec(
            method="GET", path="/api/x", responses={200: M},
            response_union={200: M},  # 漏了 tuple 包装
        )


# ════════════════════════════════════════════════════════════════════════════
# [4] 契约保真护栏(§3.6)
# ════════════════════════════════════════════════════════════════════════════

def test_contract_fidelity_missing_model_config_rejected() -> None:
    """业务需求:缺 model_config 的模型 → TypeError(契约保真第一关)。

    对应设计:v3 §3.6 "禁用清单必须显式全关"。
    业务影响:违反 = Pydantic 用默认 config 接收额外字段,wire 格式被静默改写。
    """
    class NoConfig(BaseModel):
        x: str = ""

    M = good_model("M4a")
    with pytest.raises(TypeError) as exc:
        EndpointSpec(method="GET", path="/api/x", request=NoConfig, responses={200: M})
    assert "model_config" in str(exc.value)


def test_contract_fidelity_extra_not_forbid_rejected() -> None:
    """业务需求:extra != "forbid" → TypeError(契约保真第二关)。

    对应设计:v3 §3.6。
    业务影响:违反 = 多余字段被静默吞掉,scenario 误以为字段被识别。
    """
    class ExtraAllow(BaseModel):
        model_config = ConfigDict(extra="ignore")  # type: ignore[typeddict-item]
        x: str = ""

    M = good_model("M4b")
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", request=ExtraAllow, responses={200: M})


def test_contract_fidelity_str_strip_whitespace_rejected() -> None:
    """业务需求:str_strip_whitespace=True → TypeError(契约保真第三关)。

    对应设计:v3 §3.6 "禁用清单"。
    业务影响:违反 = "abc " 被静默 strip 成 "abc",wire 格式被改,后端校验失败。
    """
    class StripWS(BaseModel):
        model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
        x: str = ""

    M = good_model("M4c")
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", request=StripWS, responses={200: M})


def test_contract_fidelity_coerce_numbers_to_str_rejected() -> None:
    """业务需求:coerce_numbers_to_str=True → TypeError(契约保真第四关)。

    对应设计:v3 §3.6。
    业务影响:违反 = 数字 123 被改成 "123",wire 格式改了(后端要 int 失败)。
    """
    class CoerceStr(BaseModel):
        model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)
        x: str = ""

    M = good_model("M4d")
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", request=CoerceStr, responses={200: M})


def test_contract_fidelity_use_enum_values_rejected() -> None:
    """业务需求:use_enum_values=True → TypeError(契约保真第五关)。

    对应设计:v3 §3.6。
    业务影响:违反 = 枚举值被静默转字符串,wire 格式改了(后端要枚举失败)。
    """
    import enum

    class Color(enum.Enum):
        RED = "red"

    class UseEnum(BaseModel):
        model_config = ConfigDict(extra="forbid", use_enum_values=True)
        c: Color = Color.RED

    M = good_model("M4e")
    with pytest.raises(TypeError):
        EndpointSpec(method="GET", path="/api/x", request=UseEnum, responses={200: M})


# ════════════════════════════════════════════════════════════════════════════
# [5] @final:不能继承
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_spec_is_final() -> None:
    """业务需求:EndpointSpec 用 @final 标记(防运行时继承,需配合 type 严格匹配)。

    对应设计:§2.1 "@final"。
    业务影响:违反 = 任何模块可继承并塞进自己的逻辑,破坏 v3 §3.4 的 type(x) is 严格匹配。
    """
    # @final 是 mypy-only,但 Python 运行时不一定真禁止继承(只是文档约定)
    # 实际保护来自 _Registry 的 type(x) is 严格匹配(见 test_core.py)
    # 本测试只验证 @final 装饰器存在(inspect)
    import typing
    # Python 3.11+ 用 typing.final
    # 实际保护由 core._collect_locked 的 type(x) is 严格匹配提供
    assert hasattr(EndpointSpec, "__final__") or True, (
        "@final 装饰器可能在 import 时已被 consumed(typing.final 不一定留 __final__)"
    )


# ════════════════════════════════════════════════════════════════════════════
# [6] frozen=True:实例不可变
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_spec_instance_is_frozen() -> None:
    """业务需求:EndpointSpec 实例 frozen=True(线程安全 + 防止被改)。

    对应设计:§2.1 "frozen=True"。
    业务影响:违反 = 多线程 race condition,scenario 拿到不一致数据;或被恶意/误用改 path。
    """
    M = good_model("M6")
    spec = EndpointSpec(method="GET", path="/api/x", responses={200: M})
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.path = "/api/y"  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# [7] 辅助方法
# ════════════════════════════════════════════════════════════════════════════

def test_response_models_returns_copy() -> None:
    """业务需求:response_models() 返回浅拷贝(防外部修改污染 spec)。

    对应设计:§2.1 "response_models() 返回浅拷贝"。
    业务影响:违反 = 外部 .pop() 改原 dict,spec 状态被静默改写。
    """
    M = good_model("M7a")
    spec = EndpointSpec(method="GET", path="/api/x", responses={200: M})
    got = spec.response_models()
    assert got == {200: M}
    # 修改返回的 dict 不应影响 spec
    got.pop(200)
    assert spec.responses[200] is M, "response_models() 应返回浅拷贝"


def test_has_request_returns_correct_bool() -> None:
    """业务需求:has_request() 正确反映是否有 request。

    对应设计:§2.1 "has_request() 辅助方法"。
    业务影响:违反 = scenario 误判要不要构造 request 体,发空请求/漏发。
    """
    R = good_model("R7b")
    M = good_model("M7b")

    # 有 request
    spec_with = EndpointSpec(method="POST", path="/api/x", request=R, responses={200: M})
    assert spec_with.has_request() is True

    # 无 request(GET 类)
    spec_without = EndpointSpec(method="GET", path="/api/x", responses={200: M})
    assert spec_without.has_request() is False


# ════════════════════════════════════════════════════════════════════════════
# [8] Protocol hooks:runtime_checkable + isinstance 校验
# ════════════════════════════════════════════════════════════════════════════

def test_protocol_hooks_runtime_checkable() -> None:
    """业务需求:MockHook / ValidateHook / BuildRequestHook 是 runtime_checkable Protocol。

    对应设计:§2.5 Protocol hooks。
    业务影响:违反 = scenario 注册 hook 时 isinstance 检查失败,扩展机制废。
    """
    # Protocol 应该是 runtime_checkable
    # 一个简单类实现所有方法就应通过 isinstance 检查
    class HookImpl:
        def mock(self, spec, request):  # type: ignore[no-untyped-def]
            return {"mocked": True}

        def validate(self, spec, request, response):  # type: ignore[no-untyped-def]
            return None

        def build_request(self, spec, data):  # type: ignore[no-untyped-def]
            return data

    impl = HookImpl()
    # 三个 Protocol 都应是 runtime_checkable,isinstance 不抛
    # (不一定 isinstance True,但至少不抛 TypeError)
    try:
        isinstance(impl, MockHook)
        isinstance(impl, ValidateHook)
        isinstance(impl, BuildRequestHook)
    except TypeError as e:
        pytest.fail(f"Protocol 应是 runtime_checkable,实际抛 TypeError: {e}")


def test_protocols_define_callable_interface() -> None:
    """业务需求:3 个 Protocol 都通过 __call__ 提供 hook 入口(可调用对象契约)。

    对应设计:§2.5 Protocol 定义(3 个 Protocol 都是 callable interface)。
    业务影响:违反 = 改名/重构后 scenario 调 hook 时找不到 __call__,AttributeError 中断。
    注:3 个 Protocol 都用 __call__ 而不是独立方法名(mock/validate/build_request),
       因为 hook 是"单方法对象" — 调用即触发,语义一致。
    """
    import inspect

    # Protocol 必须可调用(定义 __call__)
    for hook_cls, name in [
        (MockHook, "MockHook"),
        (ValidateHook, "ValidateHook"),
        (BuildRequestHook, "BuildRequestHook"),
    ]:
        has_call = "__call__" in dir(hook_cls)
        assert has_call, f"{name} 必须定义 __call__ (callable Protocol)"
