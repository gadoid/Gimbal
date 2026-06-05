"""Unit tests for ModelRegistry.core (Registry 主体 + 线程安全)。

覆盖场景:
  [1] 基础 collect / resolve:首次访问触发 import
  [2] resolve 失败:列出已注册端点 + 修复提示
  [3] 重复 collect:幂等,不重复 import
  [4] 多 service 隔离:同 (method, path) 不同 service 视为不同 key
  [5] warm() 正常:返回该批 service 的全部 EndpointSpec
  [6] warm() 部分失败 → BootstrapError 聚合所有错误
  [7] warm() 全部失败 → BootstrapError 含全部信息
  [8] 拉式收集 type 严格匹配
       8a. 继承 EndpointSpec 的子类不被收集(@final 配合 type(x) is 严格匹配)
       8b. 普通 dataclass / Pydantic model 实例不被收集
  [9] is_loaded / loaded_services introspection
  [10] reset() 仅清空状态(测试间隔离)
  [11] resolve 返回的 EndpointSpec 在锁外仍可用(frozen 配合)
  [12] path 末尾斜杠:不做规范化(契约保真,严格按作者声明收集)
"""
import sys
import os
import types
from dataclasses import dataclass
from typing import Iterator  # noqa: F401  # 保留给将来 pytest 化用

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("CORE TEST")
print("=" * 60)


from pydantic import BaseModel, ConfigDict
from ModelRegistry.core import (
    BootstrapError,
    EndpointKey,
    registry,
)
from ModelRegistry.spec import EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 辅助:动态造可 import 的 service 子包
# ════════════════════════════════════════════════════════════════════════════

def good_model(name: str) -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


def _make_service_module(
    service_dir: str,
    specs: dict[str, EndpointSpec] | None = None,
    extra_attrs: dict | None = None,
) -> types.ModuleType:
    """造一个可被 ``importlib.import_module('ModelRegistry.<dir>')`` 解析的模块。

    - 自动注册到 ``sys.modules['ModelRegistry.<dir>']`` 与 ``ModelRegistry.<dir>`` 父包
    - 不写盘,纯内存;测试结束由 ``_uninstall_service_modules`` 清理
    """
    # 确保父包 ModelRegistry 在 sys.modules(测试一启动 ModelRegistry/__init__.py 已被 import)
    full_name = f"ModelRegistry.{service_dir}"
    mod = types.ModuleType(full_name)
    mod.__file__ = f"<test-fixture>/ModelRegistry/{service_dir}.py"
    mod.__package__ = full_name
    if specs:
        for k, v in specs.items():
            setattr(mod, k, v)
    if extra_attrs:
        for k, v in extra_attrs.items():
            setattr(mod, k, v)
    sys.modules[full_name] = mod
    return mod


def _uninstall_service_modules(*dirs: str) -> None:
    """清理本测试安装的 fake service 子模块,避免污染其他测试。"""
    for d in dirs:
        sys.modules.pop(f"ModelRegistry.{d}", None)
        # 清掉 importlib 缓存(否则 importlib.import_module 还会返回旧引用)
        import importlib
        importlib.invalidate_caches()


# 本项目用 print + assert 风格,直接手写 setup/teardown
def _setup() -> None:
    registry.reset()


def _teardown(*dirs: str) -> None:
    _uninstall_service_modules(*dirs)
    registry.reset()


# ════════════════════════════════════════════════════════════════════════════
# [1] 基础 collect / resolve
# ════════════════════════════════════════════════════════════════════════════
print("\n[1] 基础 collect / resolve")
_setup()
Req = good_model("Req")
Resp = good_model("Resp")
spec = EndpointSpec(method="POST", path="/api/test", request=Req, responses={200: Resp})
_make_service_module("demo_service", {"order_add": spec})

# 首次 resolve → 触发 import + collect
got = registry.resolve("demo_service", "POST", "/api/test")
assert got is spec, "resolve 返回的就是模块里那个 spec 实例"
assert isinstance(got, EndpointSpec)
assert got.method == "POST"
assert got.path == "/api/test"
# EndpointKey 也对
assert EndpointKey("demo_service", "POST", "/api/test") in registry._index  # noqa: SLF001
print("  PASS — resolve 触发 collect 并返回原 spec")
_teardown("demo_service")


# ════════════════════════════════════════════════════════════════════════════
# [2] resolve 失败:列出已注册端点 + 修复提示
# ════════════════════════════════════════════════════════════════════════════
print("\n[2] resolve 失败 → LookupError 含已注册端点列表 + 修复提示")
_setup()
spec_a = EndpointSpec(method="GET", path="/api/a", responses={200: Resp})
spec_b = EndpointSpec(method="POST", path="/api/b", request=Req, responses={200: Resp})
_make_service_module("hint_service", {"a": spec_a, "b": spec_b})

try:
    registry.resolve("hint_service", "DELETE", "/api/nope")
    assert False, "应抛 LookupError"
except LookupError as e:
    msg = str(e)
    assert "hint_service" in msg
    assert "DELETE /api/nope" in msg
    assert "/api/a" in msg, "应列出 GET /api/a"
    assert "/api/b" in msg, "应列出 POST /api/b"
    assert "ModelRegistry/hint_service/" in msg, "应给出修复提示"
print("  PASS — 错误信息含已注册端点 + 修复路径")
_teardown("hint_service")


# ════════════════════════════════════════════════════════════════════════════
# [3] 重复 collect:幂等
# ════════════════════════════════════════════════════════════════════════════
print("\n[3] 重复 collect:幂等")
_setup()
spec_x = EndpointSpec(method="GET", path="/api/x", responses={200: Resp})
_make_service_module("idem_service", {"x": spec_x})

# 手动计数 import 次数:用一个标记函数
import ModelRegistry.core as core_mod
orig_import_module = core_mod.importlib.import_module
import_calls: list[str] = []

def counting_import(name: str, *a, **kw):
    import_calls.append(name)
    return orig_import_module(name, *a, **kw)

core_mod.importlib.import_module = counting_import
try:
    registry.collect("idem_service")
    registry.collect("idem_service")
    registry.collect("idem_service")
    assert import_calls == ["ModelRegistry.idem_service"], \
        f"幂等 collect 只应 import 一次,实际 {import_calls}"
finally:
    core_mod.importlib.import_module = orig_import_module
print("  PASS — 重复 collect 只 import 一次")
_teardown("idem_service")


# ════════════════════════════════════════════════════════════════════════════
# [4] 多 service 隔离:同 (method, path) 不同 service 视为不同 key
# ════════════════════════════════════════════════════════════════════════════
print("\n[4] 多 service 隔离:同 (method, path) 不同 service 视为不同 key")
_setup()
spec_a1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
spec_b1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
_make_service_module("svc_alpha", {"a": spec_a1})
_make_service_module("svc_beta",  {"b": spec_b1})

got_a = registry.resolve("svc_alpha", "GET", "/api/orders")
got_b = registry.resolve("svc_beta",  "GET", "/api/orders")
assert got_a is spec_a1
assert got_b is spec_b1
assert got_a is not got_b, "不同 service 的同名 endpoint 是两个独立 spec"
# registry 里有两个 key
assert len(registry._index) == 2  # noqa: SLF001
print("  PASS — 同 path 不同 service 不冲突")
_teardown("svc_alpha", "svc_beta")


# ════════════════════════════════════════════════════════════════════════════
# [5] warm() 正常:返回该批 service 的全部 EndpointSpec
# ════════════════════════════════════════════════════════════════════════════
print("\n[5] warm() 正常:返回该批 service 的全部 spec")
_setup()
w1 = EndpointSpec(method="GET", path="/api/w1", responses={200: Resp})
w2 = EndpointSpec(method="GET", path="/api/w2", responses={200: Resp})
v1 = EndpointSpec(method="GET", path="/api/v1", responses={200: Resp})
_make_service_module("warm_a", {"w1": w1, "w2": w2})
_make_service_module("warm_b", {"v1": v1})

result = registry.warm(["warm_a", "warm_b"])
returned_ids = {id(s) for s in result}
assert {id(w1), id(w2), id(v1)} == returned_ids, \
    f"warm 返回的应是这两个 service 的所有 spec,实际 {returned_ids}"
# 已加载
assert registry.is_loaded("warm_a")
assert registry.is_loaded("warm_b")
assert sorted(registry.loaded_services()) == ["warm_a", "warm_b"]
print("  PASS — warm 返回全部 spec 并标记为已加载")
_teardown("warm_a", "warm_b")


# ════════════════════════════════════════════════════════════════════════════
# [6] warm() 部分失败 → BootstrapError 聚合错误
# ════════════════════════════════════════════════════════════════════════════
print("\n[6] warm() 部分失败 → BootstrapError 聚合所有错误")
_setup()
good_spec = EndpointSpec(method="GET", path="/api/good", responses={200: Resp})
_make_service_module("mix_good", {"g": good_spec})
# 第二个 service 不造模块 → collect 时 ImportError
try:
    registry.warm(["mix_good", "mix_missing"])
    assert False, "应抛 BootstrapError"
except BootstrapError as e:
    msg = str(e)
    # 失败的 service 名应在错误信息里(issues 列表)
    assert "mix_missing" in msg, f"失败的 service 应在 issues 列表: {msg}"
    assert "No module named" in msg or "import" in msg.lower(), \
        f"错误信息应附原始原因: {msg}"
    # 已成功的 service 不应被记入 issues
    assert "mix_good" not in msg, f"成功的 service 不应出现在错误里: {msg}"
    # 已成功的 service 也应保留(失败不污染已成功的状态)
    assert registry.is_loaded("mix_good"), "部分失败不污染已成功 service"
    assert not registry.is_loaded("mix_missing")
print("  PASS — 部分失败聚合抛错,不污染成功项")
_teardown("mix_good")


# ════════════════════════════════════════════════════════════════════════════
# [7] warm() 全部失败 → BootstrapError 含全部信息
# ════════════════════════════════════════════════════════════════════════════
print("\n[7] warm() 全部失败 → BootstrapError 含全部")
_setup()
try:
    registry.warm(["ghost1", "ghost2", "ghost3"])
    assert False, "应抛 BootstrapError"
except BootstrapError as e:
    msg = str(e)
    for s in ["ghost1", "ghost2", "ghost3"]:
        assert s in msg, f"错误信息应含 {s}: {msg}"
    # 一个都不应被标记为 loaded
    for s in ["ghost1", "ghost2", "ghost3"]:
        assert not registry.is_loaded(s)
print("  PASS — 全部失败聚合抛错,无副作用")
_teardown()


# ════════════════════════════════════════════════════════════════════════════
# [8] 拉式收集 type 严格匹配
# ════════════════════════════════════════════════════════════════════════════
print("\n[8] 拉式收集 type 严格匹配(@final 配合)")

# 8a. 继承 EndpointSpec 的子类不被收集
print("  [8a] 继承 EndpointSpec 的子类 → 不被收集")
_setup()


class EvilSubclass(EndpointSpec):  # type: ignore[misc]
    """@final 拦不住运行时继承(只拦 mypy),但 type(...) is 严格匹配会拦。"""
    pass


# 但 spec.py 用了 @final,Python 运行时不会真禁止继承。
# 这里只是验证 "如果真有人继承,Registry 不会把它收进去"——
# 这是 v3 §3.4 的关键安全护栏:拉式收集用 type(...) is 而不是 isinstance(...)。
real_spec = EndpointSpec(method="GET", path="/api/real", responses={200: Resp})
fake_spec = EvilSubclass(method="GET", path="/api/fake", responses={200: Resp})
_make_service_module("strict_service", {"real": real_spec, "fake": fake_spec})

got = registry.resolve("strict_service", "GET", "/api/real")
assert got is real_spec
# 关键的:fake_spec 没被收进去 → resolve 它会抛 LookupError
try:
    registry.resolve("strict_service", "GET", "/api/fake")
    assert False, "子类 spec 不应被收集"
except LookupError as e:
    assert "/api/fake" in str(e)
print("    PASS — 子类不污染 registry")
_teardown("strict_service")


# 8b. 普通 dataclass / Pydantic BaseModel 实例不被收集
print("  [8b] 非 EndpointSpec 类型不混入 index")
_setup()
real_spec_8b = EndpointSpec(method="GET", path="/api/real", responses={200: Resp})
# 混进非 EndpointSpec 的"噪声"
make_model = good_model("NoiseModel")


@dataclass(frozen=True)
class PlainDataclass:
    x: int = 0


_make_service_module(
    "noise_service",
    {
        "real": real_spec_8b,
        "model_inst": make_model(x="hi"),  # BaseModel 实例(非 type)
        "dc_inst": PlainDataclass(x=1),   # 普通 dataclass 实例
        "str_const": "not a spec",         # 字符串
    },
)

registry.collect("noise_service")
# 噪声全被过滤
assert len(registry._index) == 1  # noqa: SLF001
assert EndpointKey("noise_service", "GET", "/api/real") in registry._index  # noqa: SLF001
print("    PASS — 仅 EndpointSpec 实例被收入,其他类型全过滤")
_teardown("noise_service")


# ════════════════════════════════════════════════════════════════════════════
# [9] is_loaded / loaded_services
# ════════════════════════════════════════════════════════════════════════════
print("\n[9] is_loaded / loaded_services")
_setup()
assert registry.is_loaded("never_touched") is False
assert registry.loaded_services() == []

s1 = EndpointSpec(method="GET", path="/a", responses={200: Resp})
s2 = EndpointSpec(method="GET", path="/b", responses={200: Resp})
_make_service_module("info_a", {"a": s1})
_make_service_module("info_b", {"b": s2})

registry.collect("info_a")
assert registry.is_loaded("info_a") and not registry.is_loaded("info_b")
assert registry.loaded_services() == ["info_a"]

# 一次性 warm 两个
registry.warm(["info_b"])
assert sorted(registry.loaded_services()) == ["info_a", "info_b"]
print("  PASS — introspection 正确")
_teardown("info_a", "info_b")


# ════════════════════════════════════════════════════════════════════════════
# [10] reset():清空状态(测试间隔离)
# ════════════════════════════════════════════════════════════════════════════
print("\n[10] reset() — 测试间隔离")
_setup()
r_spec = EndpointSpec(method="GET", path="/api/r", responses={200: Resp})
_make_service_module("reset_svc", {"r": r_spec})
registry.collect("reset_svc")
assert len(registry._index) == 1  # noqa: SLF001
assert registry.is_loaded("reset_svc")

registry.reset()
assert len(registry._index) == 0  # noqa: SLF001
assert registry.loaded_services() == []
assert registry.is_loaded("reset_svc") is False
print("  PASS — reset 后完全清空")
_teardown("reset_svc")


# ════════════════════════════════════════════════════════════════════════════
# [11] resolve 返回 frozen spec 在锁外仍可用
# ════════════════════════════════════════════════════════════════════════════
print("\n[11] resolve 返回 frozen spec,锁外仍可读")
_setup()
f_spec = EndpointSpec(method="POST", path="/api/f", request=Req, responses={200: Resp})
_make_service_module("frozen_svc", {"f": f_spec})

got = registry.resolve("frozen_svc", "POST", "/api/f")
# frozen=True → 实例不可变
try:
    got.method = "GET"  # type: ignore[misc]
    assert False, "frozen 不可变"
except Exception:
    pass
# 但读、辅助方法都正常
assert got.has_request() is True
assert got.response_models() == {200: Resp}
print("  PASS — 锁外读 frozen 实例安全")
_teardown("frozen_svc")


# ════════════════════════════════════════════════════════════════════════════
# [12] path 末尾斜杠:不做规范化
# ════════════════════════════════════════════════════════════════════════════
print("\n[12] path 末尾斜杠:不做规范化(契约保真)")
_setup()
p1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
p2 = EndpointSpec(method="GET", path="/api/orders/", responses={200: Resp})
_make_service_module("path_svc", {"no_slash": p1, "with_slash": p2})

g1 = registry.resolve("path_svc", "GET", "/api/orders")
g2 = registry.resolve("path_svc", "GET", "/api/orders/")
assert g1 is p1
assert g2 is p2
assert g1 is not g2, "末尾斜杠差异被视为不同 endpoint(契约保真,不自动归一化)"
print("  PASS — 路径不做隐式规范化")
_teardown("path_svc")


print("\n" + "=" * 60)
print("CORE TEST: ALL PASSED")
print("=" * 60)
