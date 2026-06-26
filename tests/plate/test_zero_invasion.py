"""A5 零侵入验证:Plate 顶层不 import 任何子包,不污染 sys.modules。

承诺(对应 v3 §A.5 验证阶段可观察事实):
  1. ``import Plate`` 之后,``Plate.<service>`` 任何子模块
     **都不应**出现在 ``sys.modules`` 中
  2. ``from Plate import registry`` 后,顶层只暴露 ``registry`` 和
     ``BootstrapError``,**不暴露** ``EndpointSpec``(spec.py 仍是子模块,按需导入)
  3. ``import gimbal`` / 跑现有 scenario 路径不破任何事
  4. registry 在 import 后是"冷"状态:``_index`` 空、``_loaded`` 空
  5. 真的需要某 service 时,``registry.resolve(s, m, p)`` 才触达该子模块

注:核心零侵入不变量已由 tests/plate/test_invariants.py 覆盖(5 个 invariant),
本文件作为"完整契约套件"补充,验证更多边角场景。
"""
from __future__ import annotations

import importlib
import sys
import types

import pytest
from pydantic import BaseModel, ConfigDict

import Plate
from Plate.core import EndpointKey
from Plate.spec import EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════════════════════════════

def _good_model(name: str) -> type[BaseModel]:
    return type(
        name, (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str}, "x": ""
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# 共享 fixture
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _restore_modules():
    """测试间隔离:每个测试前后清理 fake service + 卸载 Plate。

    业务影响:不隔离 = sys.modules 残留 fake service,后续测试误判"已加载"。
    """
    yield
    # 清理 fake service
    sys.modules.pop("Plate.zero_inv_svc", None)
    importlib.invalidate_caches()
    Plate.registry.reset()


# ════════════════════════════════════════════════════════════════════════════
# [1] 顶层 __init__ 不会引入 service 子包
# ════════════════════════════════════════════════════════════════════════════

def test_top_level_import_does_not_load_service_subpackages() -> None:
    """业务需求:import Plate 顶层不引入任何 service 子包(零侵入第一关)。

    对应设计:PLATE_DESIGN.md §7 承诺 1 "零侵入"。
    业务影响:违反 = 顶层 import 触发重型依赖加载,scenario 启动慢 10x;
             更严重的是"按需加载"被破坏,所有 service 都被 import,内存爆。
    """
    # 模拟"全新进程":卸载所有 Plate.*
    for m in [m for m in sys.modules if m == "Plate" or m.startswith("Plate.")]:
        del sys.modules[m]
    importlib.invalidate_caches()

    assert "Plate" not in sys.modules, "卸载后 Plate 应不在 sys.modules"
    importlib.import_module("Plate")

    loaded = sorted(
        m for m in sys.modules if m == "Plate" or m.startswith("Plate.")
    )
    # 内部实现模块(这些是必然加载的)
    INTERNAL_MODULES = {
        "Plate", "Plate.core", "Plate._aliases", "Plate.spec",
        "Plate.binding", "Plate.path_resolver",
        "Plate.doc", "Plate.serialization",
        "Plate.version", "Plate.manifest",
        "Plate.server", "Plate.server.response", "Plate.server.router",
        "Plate.fin.dannotations",
    }
    loaded_set = set(loaded)
    non_internal = loaded_set - INTERNAL_MODULES
    assert not non_internal, (
        f"顶层 import 触达了非预期的子包: {sorted(non_internal)}"
    )


# ════════════════════════════════════════════════════════════════════════════
# [2] 顶层只暴露 registry + BootstrapError
# ════════════════════════════════════════════════════════════════════════════

def test_top_level_all_only_exposes_registry_and_bootstrap_error() -> None:
    """业务需求:顶层 __all__ 仅含 registry 和 BootstrapError(零侵入第二关)。

    对应设计:§7 承诺 1 实现。
    业务影响:暴露更多 = 消费方依赖内部细节,后续重构(如 service 拆分)破坏 API。
    """
    assert set(Plate.__all__) == {"registry", "BootstrapError"}, (
        f"顶层 __all__ 应为 {{registry, BootstrapError}},"
        f"实际 {set(Plate.__all__)}"
    )
    # 这些名字应可用
    assert Plate.registry is not None
    assert Plate.BootstrapError is not None
    # EndpointSpec / Protocol 不应在顶层(它们是子模块的契约定义,按需 import)
    assert not hasattr(Plate, "EndpointSpec"), (
        "EndpointSpec 不应被顶层 re-export(spec.py 是按需 import 的子模块)"
    )
    assert not hasattr(Plate, "MockHook")
    assert not hasattr(Plate, "ValidateHook")
    assert not hasattr(Plate, "BuildRequestHook")


# ════════════════════════════════════════════════════════════════════════════
# [3] import 后 registry 处于"冷"状态
# ════════════════════════════════════════════════════════════════════════════

def test_registry_is_cold_after_top_level_import() -> None:
    """业务需求:import 顶层后,registry 是"冷"状态(_index 空, _loaded 空)。

    对应设计:§7 承诺 2 "按需加载"。
    业务影响:违反 = import 时就把所有 service 全 import,启动时间 / 内存都崩。
    """
    mr = Plate.registry
    assert mr._index == {}, f"_index 应空,实际 {mr._index}"  # noqa: SLF001
    assert mr._loaded == set(), f"_loaded 应空,实际 {mr._loaded}"  # noqa: SLF001
    assert mr.loaded_services() == []
    assert mr.is_loaded("anything") is False


# ════════════════════════════════════════════════════════════════════════════
# [4] 真的 resolve 才触达子包
# ════════════════════════════════════════════════════════════════════════════

def test_failed_resolve_does_not_pollute_modules() -> None:
    """业务需求:resolve 抛 LookupError 后,不应有 service 子包被加载(4a)。

    对应设计:§7 承诺 2 "按需加载"。
    业务影响:违反 = 用户敲错 path 也会触发 import,污染 sys.modules,后续
             卸载/重装 service 时被旧引用干扰,生产环境调试极难。
    """
    with pytest.raises(LookupError) as exc:
        Plate.registry.resolve(
            "definitely_not_a_real_service_for_zero_invasion", "GET", "/x"
        )
    assert "definitely_not_a_real_service_for_zero_invasion" in str(exc.value)

    # resolve 失败后,不应有任何 service 子包被加载
    loaded_after_404 = set(
        m for m in sys.modules if m == "Plate" or m.startswith("Plate.")
    )
    INTERNAL_MODULES = {
        "Plate", "Plate.core", "Plate._aliases", "Plate.spec",
        "Plate.binding", "Plate.path_resolver",
        "Plate.doc", "Plate.serialization",
        "Plate.version", "Plate.manifest",
        "Plate.server", "Plate.server.response", "Plate.server.router",
        "Plate.fin.dannotations",
    }
    new_subpkgs = loaded_after_404 - INTERNAL_MODULES
    assert not new_subpkgs, (
        f"resolve 失败不应触发任何非豁免子包加载,实际: {sorted(new_subpkgs)}"
    )


def test_resolve_triggers_on_demand_import_for_existing_service() -> None:
    """业务需求:resolve 真实存在的 service 时,registry 才触达子模块(4b)。

    对应设计:§7 承诺 2 "按需加载"。
    业务影响:不成立 = "按需"承诺崩,用户感知不到 service 何时被加载。
    """
    Resp = _good_model("Resp")
    spec = EndpointSpec(method="GET", path="/api/zero_inv", responses={200: Resp})
    fake = types.ModuleType("Plate.zero_inv_svc")
    fake.__file__ = "<test-fixture>/Plate/zero_inv_svc.py"
    fake.__package__ = "Plate.zero_inv_svc"
    fake.spec = spec
    sys.modules["Plate.zero_inv_svc"] = fake

    # 关键断言:resolve 之前,registry 还不知道这个 spec
    assert not Plate.registry.is_loaded("zero_inv_svc"), (
        "resolve 之前 service 不应被加载"
    )
    assert (
        EndpointKey("zero_inv_svc", "GET", "/api/zero_inv")
        not in Plate.registry._index  # noqa: SLF001
    )

    # resolve 后:找到了
    got = Plate.registry.resolve("zero_inv_svc", "GET", "/api/zero_inv")
    assert got is spec, "resolve 应返回 fixture 中声明的 spec"
    assert Plate.registry.is_loaded("zero_inv_svc"), (
        "resolve 之后 service 应被标记为已加载"
    )
    assert (
        EndpointKey("zero_inv_svc", "GET", "/api/zero_inv")
        in Plate.registry._index  # noqa: SLF001
    )


# ════════════════════════════════════════════════════════════════════════════
# [5] import gimbal 不破任何事
# ════════════════════════════════════════════════════════════════════════════

def test_importing_gimbal_does_not_load_plate() -> None:
    """业务需求:import gimbal 不应触发任何 Plate.* 加载(零侵入第三关)。

    对应设计:§7 承诺 1 "gimbal 与 Plate 完全解耦"。
    业务影响:违反 = 业务项目用 gimbal 时被强制引入 Plate,违背"按需消费"。
    """
    # 重新模拟"全新进程":卸载 Plate
    for m in [m for m in sys.modules if m == "Plate" or m.startswith("Plate.")]:
        del sys.modules[m]
    importlib.invalidate_caches()

    # 看看有没有 gimbal 这个包
    try:
        importlib.import_module("gimbal")
        has_gimbal = True
    except ImportError:
        has_gimbal = False
        pytest.skip("项目当前未发布 gimbal 包(本机未安装),跳过此断言")

    # gimbal 应正常 import,不依赖 Plate
    loaded = sorted(
        m for m in sys.modules if m == "Plate" or m.startswith("Plate.")
    )
    assert loaded == [], (
        f"import gimbal 不应触发任何 Plate.* 加载,实际: {loaded}"
    )
