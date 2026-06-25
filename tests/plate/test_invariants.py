"""Plate 业务不变量聚合。

本文件**不**与单 endpoint 测试重叠,只放"跨 PR 适用"的硬约束。
每个不变量都是面向业务需求的护栏:

  业务核心(零侵入 / 按需加载 / 契约保真)→ 必须长期成立
  注册期 fail-fast                   → 错误前置到 import 时,不在运行时静默吞错
  frozen + @final                    → 线程安全 + 类型严格匹配的运行时保障

测试名直接读出业务承诺,docstring 写明:
  1. 业务需求(不变量保护什么承诺)
  2. 对应设计章节
  3. 业务影响(违反此约束的代价)
"""
from __future__ import annotations

import importlib
import sys
import types

import pytest
from pydantic import BaseModel, ConfigDict

_PKG: str = "Plate"


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


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #1:零侵入承诺(对应设计 §7 承诺 1)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_top_level_does_not_load_service_subpackages():
    """业务不变量:import 顶层包不触达任何 service 子包。

    对应设计:PLATE_DESIGN.md §7 承诺 1 "零侵入"。
    业务影响:违反 = 顶层 import 触发重型依赖加载,scenario 启动慢 10x;
             更严重的是"按需加载"被破坏,所有 service 都被 import,内存爆。
    """
    # 模拟"全新进程":卸载所有 <pkg>.*
    pkg = _PKG
    for m in [m for m in sys.modules if m == pkg or m.startswith(pkg + ".")]:
        del sys.modules[m]
    importlib.invalidate_caches()

    assert pkg not in sys.modules, f"卸载后 {pkg} 应不在 sys.modules"
    importlib.import_module(pkg)

    # import 顶层后,核心承诺是:
    #   - 不应有任何 "<pkg>.<service>" 的子包被加载
    #   - "<pkg>.core" / "<pkg>._aliases" / "<pkg>.spec"
    #     是实现模块(必须加载,否则无法 expose registry 和 BootstrapError)
    #   - 但它们不是 service,不算"侵入"
    loaded = sorted(m for m in sys.modules if m == pkg or m.startswith(pkg + "."))
    # 内部实现模块集合(这些是必然加载的)
    internal_modules = {pkg, f"{pkg}.core", f"{pkg}._aliases", f"{pkg}.spec"}
    loaded_set = set(loaded)
    non_internal = loaded_set - internal_modules
    assert not non_internal, (
        f"顶层 import 触达了非预期的子包: {sorted(non_internal)}"
    )

    # 防御性:没有 "<pkg>.<service>" 形式的子包被加载
    # (service 子包通常以 service 名结尾,不是 core/_aliases/spec)
    service_submodules = [
        m for m in loaded
        if m.count(".") == 1
        and m.split(".")[1] not in {"core", "_aliases", "spec", "fin", "dannotations"}
        # 注:本测试关心"零侵入",但 fin/ 是真实存在的 service 子包;
        # 此处只验证"顶层 import 不主动 import fin",如果其他 PR 引入新 service
        # 子包,需扩展豁免列表(防御性,而非开放)。
    ]
    # 严格:不应有除豁免外的 service 子包被加载
    assert not service_submodules, (
        f"顶层 import 不应触发任何非豁免 service 子包加载,实际: {service_submodules}"
    )


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #2:顶层只暴露 registry + BootstrapError(对应设计 §7 承诺 1)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_top_level_all_only_registry_and_bootstrap_error():
    """业务不变量:顶层 __all__ 仅含 registry 和 BootstrapError。

    对应设计:PLATE_DESIGN.md §7 承诺 1 + §1 "零侵入" 实现。
    业务影响:暴露更多 = 消费方依赖内部细节,后续重构(如 service 拆分)破坏 API。
    """
    pkg = importlib.import_module(_PKG)
    assert set(pkg.__all__) == {"registry", "BootstrapError"}, (
        f"顶层 __all__ 应为 {{registry, BootstrapError}},"
        f"实际 {set(pkg.__all__)}"
    )
    # 验证:这些名字都可用
    assert pkg.registry is not None
    assert pkg.BootstrapError is not None
    # 反向:EndpointSpec / Protocol 不应在顶层(它们是子模块的契约定义,按需 import)
    assert not hasattr(pkg, "EndpointSpec"), (
        "EndpointSpec 不应被顶层 re-export(spec.py 是按需 import 的子模块)"
    )
    assert not hasattr(pkg, "MockHook")
    assert not hasattr(pkg, "ValidateHook")
    assert not hasattr(pkg, "BuildRequestHook")


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #3:import 后 registry 处于"冷"状态(对应设计 §7 承诺 2 按需加载)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_registry_is_cold_after_import():
    """业务不变量:import 顶层后,registry 是"冷"状态(_index 空, _loaded 空)。

    对应设计:PLATE_DESIGN.md §7 承诺 2 "按需加载"。
    业务影响:违反 = import 时就把所有 service 全 import,启动时间 / 内存都崩。
    """
    pkg = importlib.import_module(_PKG)
    mr = pkg.registry
    assert mr._index == {}, f"_index 应空,实际 {mr._index}"  # noqa: SLF001
    assert mr._loaded == set(), f"_loaded 应空,实际 {mr._loaded}"  # noqa: SLF001
    assert mr.loaded_services() == []
    assert mr.is_loaded("anything") is False


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #4:resolve 失败不污染 import 状态(对应设计 §7 承诺 2)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_failed_resolve_does_not_pollute_modules():
    """业务不变量:resolve 抛 LookupError 后,不应有 service 子包被加载。

    对应设计:PLATE_DESIGN.md §7 承诺 2 "按需加载"。
    业务影响:违反 = 用户敲错 path 也会触发 import,污染 sys.modules,后续
             卸载/重装 service 时被旧引用干扰,生产环境调试极难。
    """
    pkg = importlib.import_module(_PKG)
    mr = pkg.registry
    # 4a. 不存在的 service → LookupError(不污染 import 状态)
    with pytest.raises(LookupError) as exc:
        mr.resolve("definitely_not_a_real_service_for_invariant", "GET", "/x")
    assert "definitely_not_a_real_service_for_invariant" in str(exc.value)

    # resolve 失败后,不应有任何 service 子包被加载
    loaded_after_404 = {
        m for m in sys.modules
        if m == _PKG or m.startswith(_PKG + ".")
    }
    internal_modules = {_PKG, f"{_PKG}.core",
                        f"{_PKG}._aliases", f"{_PKG}.spec"}
    new_subpkgs = loaded_after_404 - internal_modules
    assert not new_subpkgs, (
        f"resolve 失败不应触发任何非豁免子包加载,实际: {sorted(new_subpkgs)}"
    )


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #5:fake service 子包能被发现(按需 import 触达)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_resolve_triggers_on_demand_import():
    """业务不变量:真正 resolve 时,registry 才会触达子包(按需加载成立)。

    对应设计:PLATE_DESIGN.md §7 承诺 2 "按需加载"。
    业务影响:不成立 = 整个"按需"承诺崩;用户感知不到 service 何时被加载,
             不能信任"未引用的 service 一个字节都不 import"的承诺。
    """
    pkg = importlib.import_module(_PKG)
    core = importlib.import_module(f"{_PKG}.core")
    spec_mod = importlib.import_module(f"{_PKG}.spec")

    Resp = _good_model("Resp")
    spec_inst = spec_mod.EndpointSpec(
        method="GET", path="/api/invariant_on_demand", responses={200: Resp}
    )
    fake_name = f"{_PKG}.invariant_on_demand_svc"
    fake = types.ModuleType(fake_name)
    fake.__file__ = f"<test-fixture>/{_PKG}/invariant_on_demand_svc.py"
    fake.__package__ = fake_name
    fake.spec = spec_inst
    sys.modules[fake_name] = fake

    try:
        mr = pkg.registry
        # 关键断言:resolve 之前,registry 还不知道这个 spec
        assert not mr.is_loaded("invariant_on_demand_svc"), (
            "resolve 之前 service 不应被加载"
        )
        assert (
            core.EndpointKey("invariant_on_demand_svc", "GET",
                             "/api/invariant_on_demand") not in mr._index  # noqa: SLF001
        )

        # resolve 后:找到了
        got = mr.resolve("invariant_on_demand_svc", "GET", "/api/invariant_on_demand")
        assert got is spec_inst, "resolve 应返回 fixture 中声明的 spec"
        assert mr.is_loaded("invariant_on_demand_svc"), (
            "resolve 之后 service 应被标记为已加载"
        )
        assert (
            core.EndpointKey("invariant_on_demand_svc", "GET",
                             "/api/invariant_on_demand") in mr._index  # noqa: SLF001
        )
    finally:
        # 清理
        sys.modules.pop(fake_name, None)
        mr.reset()
        importlib.invalidate_caches()


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #6:category × mutates_state 交叉一致(PR-B / PLATE_DESIGN §3.2)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_category_x_mutates_state_holds():
    """业务不变量:任何 QUERY / TOOL 端点必须 mutates_state=False。

    对应设计:PLATE_DESIGN.md §3.2 + §3.4(c) 真实事故风险。
    业务影响:任何破坏 = CT 主动探测可触发业务写入(生产事故)。

    注:本测试只对已 collect 进 registry 的 spec 断言;fixture 中的瞬时 spec 不
    参与此不变量(它们的合法性由 test_spec_category.py 单独覆盖)。
    """
    from Plate.spec import EndpointCategory

    pkg = importlib.import_module(_PKG)
    mr = pkg.registry

    violations: list[str] = []
    for key, spec in mr._index.items():  # noqa: SLF001
        if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if spec.mutates_state is not False:
                violations.append(
                    f"{key.service} {key.method} {key.path}: "
                    f"category={spec.category.value} 但 "
                    f"mutates_state={spec.mutates_state!r}"
                )

    assert not violations, (
        "category × mutates_state 不变量被破坏:\n  "
        + "\n  ".join(violations)
    )