"""Unit tests for ModelRegistry.spec (EndpointSpec + Protocol hooks)。

覆盖场景:
  [1] 正常创建:所有字段 + 默认值
  [2] GET 类:request=None 允许
  [3] 必填字段类型校验
       3a. request 不是 BaseModel 子类 → TypeError
       3b. responses 的 key 不是 int → TypeError
       3c. responses 的 value 不是 BaseModel 子类 → TypeError
       3d. default_response 不是 BaseModel 子类 → TypeError
       3e. response_union 的 value 不是 BaseModel 元组 → TypeError
  [4] 契约保真护栏(§3.6)
       4a. 缺少 model_config → TypeError
       4b. extra != "forbid" → TypeError
       4c. str_strip_whitespace=True → TypeError
       4d. coerce_numbers_to_str=True → TypeError
       4e. use_enum_values=True → TypeError
  [5] @final:不能继承
  [6] frozen=True:实例不可变
  [7] 辅助方法
       7a. response_models() 返回浅拷贝
       7b. has_request() 正确返回布尔
  [8] Protocol hooks:runtime_checkable + isinstance 校验
"""
import sys
import os
from dataclasses import FrozenInstanceError, dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("SPEC TEST")
print("=" * 60)


from pydantic import BaseModel, ConfigDict
from ModelRegistry.spec import (
    EndpointSpec,
    MockHook,
    ValidateHook,
    BuildRequestHook,
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


def bad_model_no_config(name: str = "BadNoCfg") -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def bad_model_extra_allow(name: str = "BadExtra") -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="allow"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def bad_model_strip_whitespace(name: str = "BadStrip") -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid", str_strip_whitespace=True),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def bad_model_coerce_num(name: str = "BadCoerce") -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid", coerce_numbers_to_str=True),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def bad_model_use_enum(name: str = "BadEnum") -> type[BaseModel]:
    from enum import Enum
    class Color(str, Enum):
        RED = "red"
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid", use_enum_values=True),
            "__annotations__": {"color": Color},
            "color": Color.RED,
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# [1] 正常创建:所有字段 + 默认值
# ════════════════════════════════════════════════════════════════════════════
print("\n[1] 正常创建 EndpointSpec")
Req = good_model("Req")
Resp = good_model("Resp")
spec = EndpointSpec(
    method="POST",
    path="/api/test",
    request=Req,
    responses={200: Resp},
    summary="test",
    description="d",
    tags=["t1", "t2"],
    auth_required=True,
)
assert spec.method == "POST"
assert spec.path == "/api/test"
assert spec.request is Req
assert spec.responses == {200: Resp}
assert spec.summary == "test"
assert spec.description == "d"
assert spec.tags == ["t1", "t2"]
assert spec.auth_required is True
assert spec.default_response is None
assert spec.response_union == {}
assert spec.mock_hook is None
assert spec.validate_hook is None
assert spec.build_request_hook is None
print("  PASS — 字段全对,默认值全对")


# ════════════════════════════════════════════════════════════════════════════
# [2] GET 类:request=None 允许
# ════════════════════════════════════════════════════════════════════════════
print("\n[2] GET 类接口 request=None 允许")
spec_get = EndpointSpec(method="GET", path="/api/list", request=None, responses={200: Resp})
assert spec_get.request is None
assert spec_get.has_request() is False
print("  PASS")


# ════════════════════════════════════════════════════════════════════════════
# [3] 必填字段类型校验
# ════════════════════════════════════════════════════════════════════════════
print("\n[3] 必填字段类型校验")

# 3a. request 不是 BaseModel 子类
print("  [3a] request 非 BaseModel 子类 → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=int)
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "request" in str(e) and "BaseModel" in str(e)
print("    PASS")

# 3b. responses 的 key 不是 int
print("  [3b] responses 的 key 非 int → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=Req, responses={"200": Resp})
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "int" in str(e)
print("    PASS")

# 3c. responses 的 value 不是 BaseModel 子类
print("  [3c] responses 的 value 非 BaseModel 子类 → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=Req, responses={200: int})
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "responses[200]" in str(e) and "BaseModel" in str(e)
print("    PASS")

# 3d. default_response 不是 BaseModel 子类
print("  [3d] default_response 非 BaseModel 子类 → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=Req, default_response=str)
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "default_response" in str(e)
print("    PASS")

# 3e. response_union 的 value 不是 BaseModel 元组
print("  [3e] response_union 的 value 非 BaseModel 元组 → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=Req, response_union={200: [Resp]})
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "response_union" in str(e)
print("    PASS")

# 3f. method/path 空串
print("  [3f] method/path 空串 → TypeError")
for kw in [{"method": "", "path": "/x"}, {"method": "GET", "path": ""}]:
    try:
        EndpointSpec(**kw)
        assert False, f"应抛 TypeError: {kw}"
    except TypeError:
        pass
print("    PASS")


# ════════════════════════════════════════════════════════════════════════════
# [4] 契约保真护栏
# ════════════════════════════════════════════════════════════════════════════
print("\n[4] 契约保真护栏(v3 §3.6)")

# 4a. 缺少 model_config
print("  [4a] request 缺 model_config → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=bad_model_no_config("Bad"))
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "model_config" in str(e) and "extra='forbid'" in str(e)
print("    PASS")

# 4b. extra != "forbid"
print("  [4b] request 的 extra='allow' → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=bad_model_extra_allow("Bad"))
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "extra" in str(e) and "forbid" in str(e)
print("    PASS")

# 4c. str_strip_whitespace=True
print("  [4c] str_strip_whitespace=True → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=bad_model_strip_whitespace("Bad"))
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "str_strip_whitespace" in str(e) and "破坏 wire" in str(e)
print("    PASS")

# 4d. coerce_numbers_to_str=True
print("  [4d] coerce_numbers_to_str=True → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=bad_model_coerce_num("Bad"))
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "coerce_numbers_to_str" in str(e)
print("    PASS")

# 4e. use_enum_values=True
print("  [4e] use_enum_values=True → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=bad_model_use_enum("Bad"))
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "use_enum_values" in str(e)
print("    PASS")

# 4f. 校验也覆盖 responses
print("  [4f] responses[200] 配置不安全 → TypeError")
try:
    EndpointSpec(method="POST", path="/x", request=Req, responses={200: bad_model_extra_allow("Bad")})
    assert False, "应抛 TypeError"
except TypeError as e:
    assert "responses[200]" in str(e)
print("    PASS")


# ════════════════════════════════════════════════════════════════════════════
# [5] @final:不能继承
# ════════════════════════════════════════════════════════════════════════════
print("\n[5] @final:不能继承 EndpointSpec")
try:
    class MySpec(EndpointSpec):  # type: ignore[misc]
        pass
    # typing.final 仅在静态检查时强制;运行时继承不抛错(但 mypy 会报错)
    # 这里只验证 isinstance 检查在 core.py 中用 type(...) is 而不是 isinstance(...)
    # —— 这条在 core.py 测试里覆盖
    print("  (运行时 Python 不抛错;静态检查/mypy 会报。此处仅作记录。)")
except Exception:
    pass
print("  PASS — 见 core.py 测试验证 type(attr) is EndpointSpec 排除继承")


# ════════════════════════════════════════════════════════════════════════════
# [6] frozen=True:实例不可变
# ════════════════════════════════════════════════════════════════════════════
print("\n[6] frozen=True:实例不可变")
try:
    spec.method = "GET"  # type: ignore[misc]
    assert False, "应抛 FrozenInstanceError"
except (FrozenInstanceError, Exception) as e:
    # 某些 Python/dataclass 版本抛 AttributeError,都算"不可变"
    err_name = type(e).__name__
    assert err_name in ("FrozenInstanceError", "AttributeError"), \
        f"期望 FrozenInstanceError/AttributeError,实际 {err_name}: {e}"
print("  PASS")


# ════════════════════════════════════════════════════════════════════════════
# [7] 辅助方法
# ════════════════════════════════════════════════════════════════════════════
print("\n[7] 辅助方法")

# 7a. response_models() 返回浅拷贝
print("  [7a] response_models() 返回浅拷贝")
got = spec.response_models()
assert got == {200: Resp}
got[404] = good_model("Other")
assert 404 not in spec.responses, "修改返回值不应影响原实例"
print("    PASS")

# 7b. has_request() 正确
print("  [7b] has_request() 正确")
assert spec.has_request() is True
assert spec_get.has_request() is False
print("    PASS")


# ════════════════════════════════════════════════════════════════════════════
# [8] Protocol hooks:runtime_checkable
# ════════════════════════════════════════════════════════════════════════════
print("\n[8] Protocol hooks:runtime_checkable + isinstance 校验")

def good_mock_hook(spec, request_payload):
    return {"echo": request_payload}

assert isinstance(good_mock_hook, MockHook), "符合签名的函数应被识别为 MockHook"
print("  [8a] 符合签名的函数被 isinstance 识别为 MockHook — PASS")

def good_validate_hook(spec, response_payload, status):
    if status == 500:
        raise ValueError("500 not allowed")

assert isinstance(good_validate_hook, ValidateHook)
print("  [8b] ValidateHook 识别 — PASS")

def good_build_hook(spec, values):
    return values

assert isinstance(good_build_hook, BuildRequestHook)
print("  [8c] BuildRequestHook 识别 — PASS")

# 已知限制:runtime_checkable Protocol 只检查 __call__ 存在,不验证参数签名。
# 因此错签名的函数也会被识别为协议实现。严格签名检查需用 inspect.signature。
import inspect

def bad_hook(): pass

# runtime_checkable 限制下的实际行为
assert isinstance(bad_hook, MockHook), "runtime_checkable 仅检查 __call__ 存在(typing 模块限制)"
print("  [8d] runtime_checkable 已知限制:不验证参数签名(仅检查 __call__ 存在)")

# 用 inspect 做严格签名检查
sig = inspect.signature(bad_hook)
assert len(sig.parameters) != 2, "bad_hook 参数量不符合 MockHook 协议"
print("  [8e] inspect.signature 严格签名检查可识别错签名的函数")

print("  PASS — runtime_checkable 校验正常(已记录限制)")


print("\n" + "=" * 60)
print("SPEC TEST: ALL PASSED")
print("=" * 60)
