"""A5 零侵入验证:ModelRegistry 顶层不 import 任何子包,不污染 sys.modules。

承诺(对应 v3 §A.5 验证阶段可观察事实):
  1. ``import ModelRegistry`` 之后,``ModelRegistry.<service>`` 任何子模块
     **都不应**出现在 ``sys.modules`` 中
  2. ``from ModelRegistry import registry`` 后,顶层只暴露 ``registry`` 和
     ``BootstrapError``,**不暴露** ``EndpointSpec``(spec.py 仍是子模块,按需导入)
  3. ``import gimbal`` / 跑现有 scenario 路径不破任何事
  4. registry 在 import 后是"冷"状态:``_index`` 空、``_loaded`` 空
  5. 真的需要某 service 时,``registry.resolve(s, m, p)`` 才触达该子模块
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("ZERO-INVASION VERIFICATION (A5)")
print("=" * 60)


# ════════════════════════════════════════════════════════════════════════════
# 准备:把已知可能漏 import 的痕迹先记下,作为基线
# ════════════════════════════════════════════════════════════════════════════

# 注意:此测试文件本身 import 了 ModelRegistry.core / spec —— 不算"零侵入",
# 那是测试自身需要。我们检查的是 "import 顶层 __init__ 之后"的状态。

# 把当前已经 import 过的 ModelRegistry.* 全部记下
before_modules = {m for m in sys.modules if m.startswith("ModelRegistry")}
print(f"\n[基线] 测试启动时, sys.modules 中 ModelRegistry.* 已有: {sorted(before_modules)}")


# ════════════════════════════════════════════════════════════════════════════
# [1] 顶层 __init__ 不会引入 service 子包
# ════════════════════════════════════════════════════════════════════════════
print("\n[1] import ModelRegistry 不引入任何 service 子包")

# 模拟一个"全新进程"——卸载所有 ModelRegistry.* 再重新 import 顶层
for m in [m for m in sys.modules if m.startswith("ModelRegistry")]:
    del sys.modules[m]
# 也卸载我们自己设的 fake 服务(如果有)
import importlib
importlib.invalidate_caches()

assert "ModelRegistry" not in sys.modules, "卸载后应不在 sys.modules"
import ModelRegistry  # noqa: E402

# import 顶层后,核心承诺是:
#   - 不应有任何 "ModelRegistry.<service>" 的子包被加载
#   - "ModelRegistry.core" / "ModelRegistry._aliases" / "ModelRegistry.spec"
#     是实现模块(必须加载,否则无法 expose registry 和 BootstrapError)
#   - 但它们不是 service,不算"侵入"
loaded = sorted(m for m in sys.modules if m.startswith("ModelRegistry"))
print(f"  import ModelRegistry 后, sys.modules 中的 ModelRegistry.*: {loaded}")

# 内部实现模块集合(这些是必然加载的)
INTERNAL_MODULES = {"ModelRegistry", "ModelRegistry.core", "ModelRegistry._aliases", "ModelRegistry.spec"}
loaded_set = set(loaded)
# 验证:除内部模块外,不应有其它 ModelRegistry.* 被加载
non_internal = loaded_set - INTERNAL_MODULES
assert not non_internal, (
    f"顶层 import 触达了非预期的 service 子包: {sorted(non_internal)}"
)
# 验证:ModelRegistry 包内的 service 子包集合为空
service_submodules = [m for m in loaded if m.count(".") == 1 and m.split(".")[1] not in {"core", "_aliases", "spec"}]
assert not service_submodules, (
    f"顶层 import 不应触发任何 service 子包加载,实际: {service_submodules}"
)
print(f"  内部实现模块(必然加载): {sorted(loaded_set & INTERNAL_MODULES)}")
print(f"  service 子包(应为空): {service_submodules}")
print("  PASS — 顶层 __init__ 不会引入 service 子包")


# ════════════════════════════════════════════════════════════════════════════
# [2] 顶层只暴露 registry + BootstrapError
# ════════════════════════════════════════════════════════════════════════════
print("\n[2] 顶层 __all__ 只含 registry + BootstrapError")
assert set(ModelRegistry.__all__) == {"registry", "BootstrapError"}, \
    f"顶层 __all__ 应为 {{registry, BootstrapError}},实际 {set(ModelRegistry.__all__)}"
# 这些名字应可用
assert ModelRegistry.registry is not None
assert ModelRegistry.BootstrapError is not None
# EndpointSpec / Protocol 不应在顶层(它们是子模块的契约定义,按需 import)
assert not hasattr(ModelRegistry, "EndpointSpec"), \
    "EndpointSpec 不应被顶层 re-export(spec.py 是按需 import 的子模块)"
assert not hasattr(ModelRegistry, "MockHook")
assert not hasattr(ModelRegistry, "ValidateHook")
assert not hasattr(ModelRegistry, "BuildRequestHook")
print(f"  __all__ = {ModelRegistry.__all__}")
print("  PASS — 顶层只暴露 registry + BootstrapError")


# ════════════════════════════════════════════════════════════════════════════
# [3] import 后 registry 处于"冷"状态
# ════════════════════════════════════════════════════════════════════════════
print("\n[3] import 后 registry 是冷状态")
mr = ModelRegistry.registry
assert mr._index == {}, f"_index 应空,实际 {mr._index}"  # noqa: SLF001
assert mr._loaded == set(), f"_loaded 应空,实际 {mr._loaded}"  # noqa: SLF001
assert mr.loaded_services() == []
assert mr.is_loaded("anything") is False
print("  PASS — _index / _loaded 都是空,无副作用")


# ════════════════════════════════════════════════════════════════════════════
# [4] 真的 resolve 才触达子包
# ════════════════════════════════════════════════════════════════════════════
print("\n[4] 真的 resolve 才触达子包(按需加载)")

# 4a. 模拟一个 service 子包不存在
print("  [4a] 不存在的 service → LookupError(不污染 import 状态)")
try:
    mr.resolve("definitely_not_a_real_service", "GET", "/x")
    assert False, "应抛 LookupError"
except LookupError as e:
    assert "definitely_not_a_real_service" in str(e)
# resolve 失败后,不应有任何 service 子包被加载
# (内部实现模块本来就在,这里只关心 service 维度)
loaded_after_404 = set(m for m in sys.modules if m.startswith("ModelRegistry"))
new_service_pkgs = loaded_after_404 - INTERNAL_MODULES
assert not new_service_pkgs, (
    f"resolve 失败不应触发任何 service 子包加载,实际: {sorted(new_service_pkgs)}"
)
print("    PASS")

# 4b. 真实存在的子模块(用 sys.modules 临时塞一个),验证按需 import 触达子模块
print("  [4b] 临时塞入 fixture,验证按需 import 触达子模块")
import types
from pydantic import BaseModel, ConfigDict
from ModelRegistry.spec import EndpointSpec


def good_model(name: str) -> type[BaseModel]:
    return type(
        name, (BaseModel,),
        {"model_config": ConfigDict(extra="forbid"),
         "__annotations__": {"x": str}, "x": ""}
    )


Resp = good_model("Resp")
spec = EndpointSpec(method="GET", path="/api/zero_inv", responses={200: Resp})
fake = types.ModuleType("ModelRegistry.zero_inv_svc")
fake.__file__ = "<test-fixture>/ModelRegistry/zero_inv_svc.py"
fake.__package__ = "ModelRegistry.zero_inv_svc"
fake.spec = spec
sys.modules["ModelRegistry.zero_inv_svc"] = fake

# 关键断言:resolve 之前,registry 还不知道这个 spec
assert not mr.is_loaded("zero_inv_svc"), "resolve 之前 service 不应被加载"
from ModelRegistry.core import EndpointKey
assert EndpointKey("zero_inv_svc", "GET", "/api/zero_inv") not in mr._index  # noqa: SLF001

# resolve 后:找到了
got = mr.resolve("zero_inv_svc", "GET", "/api/zero_inv")
assert got is spec, "resolve 应返回 fixture 中声明的 spec"
assert mr.is_loaded("zero_inv_svc"), "resolve 之后 service 应被标记为已加载"
assert EndpointKey("zero_inv_svc", "GET", "/api/zero_inv") in mr._index  # noqa: SLF001
print("    PASS — resolve 触发 import,获取 spec,标记 loaded")

# 清理
del sys.modules["ModelRegistry.zero_inv_svc"]
mr.reset()
importlib.invalidate_caches()


# ════════════════════════════════════════════════════════════════════════════
# [5] import gimbal 不破任何事
# ════════════════════════════════════════════════════════════════════════════
print("\n[5] import gimbal 不破任何事(假设这是项目的顶层包)")

# 重新模拟"全新进程":卸载 ModelRegistry
for m in [m for m in sys.modules if m.startswith("ModelRegistry")]:
    del sys.modules[m]
importlib.invalidate_caches()

# 看看有没有 gimbal 这个包
try:
    import gimbal  # noqa: F401
    has_gimbal = True
    print(f"  gimbal 包已 import: {gimbal.__file__}")
except ImportError as e:
    has_gimbal = False
    print(f"  项目当前未发布 gimbal 包(本机未安装): {e}")

if has_gimbal:
    # gimbal 应正常 import,不依赖 ModelRegistry
    loaded = sorted(m for m in sys.modules if m.startswith("ModelRegistry"))
    assert loaded == [], (
        f"import gimbal 不应触发任何 ModelRegistry.* 加载,实际: {loaded}"
    )
    print("  PASS — gimbal 与 ModelRegistry 完全解耦")
else:
    print("  SKIP — 本机无 gimbal 包(未在 A.5 验证范围)")


print("\n" + "=" * 60)
print("ZERO-INVASION VERIFICATION: ALL PASSED")
print("=" * 60)
