"""Plate sanity 测试:验证 pytest 基线可工作。

设计动机:
  这是 PR-0.1 的"绿点"。如果这个测试都跑不过,说明 pytest 收集链没建好。
  如果这个测试能跑过,后续 PR 才有"基线已绿"可对照。

本测试只验证 4 件事(都是 PR-0.1 的核心承诺):
  1. pytest 框架能识别本文件
  2. Plate 包可被 import
  3. 一个 EndpointSpec 实例能成功构造(基线数据契约)
  4. registry 在 import 后处于冷状态(按需加载承诺)
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

import Plate
from Plate.spec import EndpointSpec
from Plate.core import EndpointKey  # 类型引用,reload-safe


# ════════════════════════════════════════════════════════════════════════════
# 业务核心(面向业务需求,非功能验证):
#
# "从仓库根 import Plate 应可工作" 是后续所有业务测试的地基。
# 一旦这块出问题,所有 31 个 fin 端点、scenario 执行、contract check 全部断链。
# ════════════════════════════════════════════════════════════════════════════


def test_plate_importable() -> None:
    """业务需求:Plate 包可被 import。

    对应设计 §0 "数据契约":Plate 提供接口真值,所有消费方依赖此 import。
    破坏此约束 = 整个 GIMBAL 执行态不可用。
    """
    # 每次都通过 importlib 拿当前 sys.modules 中最新的 Plate(避免 test_invariants
    # 卸载重 import 后,模块级 `import Plate` 引用指向旧对象的问题)
    import importlib
    plate = importlib.import_module("Plate")
    plate_core = importlib.import_module("Plate.core")

    # 顶层只暴露 registry + BootstrapError(零侵入承诺,设计 §7)
    assert "registry" in plate.__all__
    assert "BootstrapError" in plate.__all__
    # registry 是进程级单例(通过 Plate.__init__ 拿到,与内部 registry 一致)
    assert plate.registry is plate_core.registry, (
        "Plate.__init__ 暴露的 registry 应与 Plate.core.registry 是同一对象"
    )
    assert plate.BootstrapError is plate_core.BootstrapError


def test_endpoint_spec_constructible() -> None:
    """业务需求:EndpointSpec 基础构造可工作。

    对应设计 §2.1:EndpointSpec 是契约描述的基础类型,
    所有 endpoint 必须能成功构造,否则 service 加载链断。
    """
    class Req(BaseModel):
        model_config = ConfigDict(extra="forbid")
        order_id: str | None = None

    class Resp(BaseModel):
        model_config = ConfigDict(extra="forbid")
        code: int | None = None

    spec = EndpointSpec(
        method="POST",
        path="/api/test/sanity",
        request=Req,
        responses={200: Resp},
    )
    assert spec.method == "POST"
    assert spec.path == "/api/test/sanity"
    assert spec.request is Req
    assert spec.responses[200] is Resp


def test_registry_cold_state_after_import() -> None:
    """业务需求:import 顶层后,registry 处于"冷"状态(按需加载承诺,设计 §7)。

    对应设计 §4:Registry 启动后不预加载任何 service,必须等到真的 resolve
    才触达对应子模块。如果 import 后就热加载,破坏零侵入承诺。
    """
    # 通过 Plate.registry 拿当前活跃实例(避免模块级引用指向被 reload 的旧对象)
    assert not Plate.registry.is_loaded("fin"), (
        "registry 应在未显式 resolve 前不预加载 fin"
    )


def test_endpoint_key_hashable() -> None:
    """业务需求:EndpointKey 可作 dict key / set element(frozen 配合)。

    对应设计 §2.4:EndpointKey 是 Registry 索引键,必须可哈希,
    否则 _index / _loaded 集合无法构建。
    """
    k = EndpointKey(service="fin", method="POST", path="/api/test")
    s = {k}
    d = {k: "value"}
    assert k in s
    assert d[k] == "value"


def test_bootstrap_error_is_runtime_error() -> None:
    """业务需求:BootstrapError 继承 RuntimeError(用于聚合多 service 失败)。

    对应设计 §4 / v3 §10.2:warm() 失败时抛 BootstrapError,
    调用方常用 isinstance(e, RuntimeError) 兜底捕获。
    """
    # 通过 Plate.BootstrapError 拿当前类型(避免模块级引用指向被 reload 的旧类型)
    BE = Plate.BootstrapError
    assert issubclass(BE, RuntimeError)
    err = BE("test")
    assert isinstance(err, RuntimeError)
    assert str(err) == "test"
