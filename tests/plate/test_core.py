"""Unit tests for Plate.core (Registry 主体 + 线程安全)。

覆盖场景:
  [1] 基础 collect / resolve:首次访问触发 import
  [2] resolve 失败:列出已注册端点 + 修复提示
  [3] 重复 collect:幂等,不重复 import
  [4] 多 service 隔离:同 (method, path) 不同 service 视为不同 key
  [5] warm() 正常:返回该批 service 的全部 EndpointSpec
  [6] warm() 部分失败 → BootstrapError 聚合所有错误
  [7] warm() 全部失败 → BootstrapError 含全部信息
  [8] 拉式收集 type 严格匹配
  [9] is_loaded / loaded_services introspection
  [10] reset() 仅清空状态(测试间隔离)
  [11] resolve 返回的 EndpointSpec 在锁外仍可用(frozen 配合)
  [12] path 末尾斜杠:不做规范化(契约保真,严格按作者声明收集)
"""
from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict

import Plate
from Plate.core import BootstrapError, EndpointKey
from Plate.spec import EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 辅助:动态造可 import 的 service 子包
# ════════════════════════════════════════════════════════════════════════════

def _good_model(name: str) -> type[BaseModel]:
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
    """造一个可被 ``importlib.import_module('Plate.<dir>')`` 解析的模块。

    业务动机:测试不依赖真实 service 子包,纯内存构造,测试结束自动清理。
    """
    full_name = f"Plate.{service_dir}"
    mod = types.ModuleType(full_name)
    mod.__file__ = f"<test-fixture>/Plate/{service_dir}.py"
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
        sys.modules.pop(f"Plate.{d}", None)
    importlib.invalidate_caches()


# ════════════════════════════════════════════════════════════════════════════
# 共享 fixture:测试间隔离
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolate_registry():
    """测试间隔离:每个测试前后 reset + 卸载所有 fake module。

    业务影响:不隔离 = 后续测试拿到上一轮的 loaded services,误判"未加载"。
    """
    yield
    # 清理所有可能残留的 fake service module(以 conc_/demo_/hint_/idem_/... 开头)
    fake_keys = [k for k in sys.modules if k.startswith("Plate.")]
    for k in fake_keys:
        sys.modules.pop(k, None)
    importlib.invalidate_caches()
    Plate.registry.reset()


# 共享数据模型
Req = _good_model("Req")
Resp = _good_model("Resp")


# ════════════════════════════════════════════════════════════════════════════
# [1] 基础 collect / resolve
# ════════════════════════════════════════════════════════════════════════════

def test_first_resolve_triggers_collect_and_returns_spec() -> None:
    """业务需求:首次 resolve 触发 import + collect,返回的就是模块里那个 spec 实例。

    对应设计:§"按需加载 + 拉式收集"。
    业务影响:违反 = import 后没预加载,resolve 时也触发不了 → 真用时 service 找不到。
    """
    spec = EndpointSpec(method="POST", path="/api/test", request=Req, responses={200: Resp})
    _make_service_module("demo_service", {"order_add": spec})

    got = Plate.registry.resolve("demo_service", "POST", "/api/test")
    assert got is spec, "resolve 返回的就是模块里那个 spec 实例"
    assert isinstance(got, EndpointSpec)
    assert got.method == "POST"
    assert got.path == "/api/test"
    # EndpointKey 也对
    assert EndpointKey("demo_service", "POST", "/api/test") in Plate.registry._index  # noqa: SLF001


# ════════════════════════════════════════════════════════════════════════════
# [2] resolve 失败:列出已注册端点 + 修复提示
# ════════════════════════════════════════════════════════════════════════════

def test_resolve_failure_includes_registered_paths_and_hint() -> None:
    """业务需求:resolve 失败时,错误信息应含已注册端点列表 + 修复路径提示。

    对应设计:§"按需加载的失败模式友好性"。
    业务影响:违反 = 作者敲错 path 调试时只看 LookupError 不知有哪些可用的,体验差。
    """
    spec_a = EndpointSpec(method="GET", path="/api/a", responses={200: Resp})
    spec_b = EndpointSpec(method="POST", path="/api/b", request=Req, responses={200: Resp})
    _make_service_module("hint_service", {"a": spec_a, "b": spec_b})

    with pytest.raises(LookupError) as exc:
        Plate.registry.resolve("hint_service", "DELETE", "/api/nope")
    msg = str(exc.value)
    assert "hint_service" in msg
    assert "DELETE /api/nope" in msg
    assert "/api/a" in msg, "应列出 GET /api/a"
    assert "/api/b" in msg, "应列出 POST /api/b"
    assert "Plate/hint_service/" in msg, "应给出修复提示"


# ════════════════════════════════════════════════════════════════════════════
# [3] 重复 collect:幂等
# ════════════════════════════════════════════════════════════════════════════

def test_repeated_collect_only_imports_once() -> None:
    """业务需求:重复 collect 只 import 一次(幂等保证)。

    对应设计:§_Registry._collect_locked 幂等实现。
    业务影响:违反 = 每次 collect 都重新 import,慢且可能引入副作用;
             更严重的是重复的 spec 会覆盖 index,丢失先前状态。
    """
    spec_x = EndpointSpec(method="GET", path="/api/x", responses={200: Resp})
    _make_service_module("idem_service", {"x": spec_x})

    # 手动计数 import 次数:用一个标记函数
    core_mod = importlib.import_module("Plate.core")
    orig_import_module = core_mod.importlib.import_module
    import_calls: list[str] = []

    def counting_import(name: str, *a, **kw):
        import_calls.append(name)
        return orig_import_module(name, *a, **kw)

    core_mod.importlib.import_module = counting_import
    try:
        Plate.registry.collect("idem_service")
        Plate.registry.collect("idem_service")
        Plate.registry.collect("idem_service")
        assert import_calls == ["Plate.idem_service"], (
            f"幂等 collect 只应 import 一次,实际 {import_calls}"
        )
    finally:
        core_mod.importlib.import_module = orig_import_module


# ════════════════════════════════════════════════════════════════════════════
# [4] 多 service 隔离:同 (method, path) 不同 service 视为不同 key
# ════════════════════════════════════════════════════════════════════════════

def test_same_path_different_service_creates_distinct_keys() -> None:
    """业务需求:同 (method, path) 在不同 service 下视为不同 key。

    对应设计:§EndpointKey 包含 service 字段。
    业务影响:违反 = 跨 service 的同名 endpoint 互相覆盖,scenario 串台。
    """
    spec_a1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
    spec_b1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
    _make_service_module("svc_alpha", {"a": spec_a1})
    _make_service_module("svc_beta", {"b": spec_b1})

    got_a = Plate.registry.resolve("svc_alpha", "GET", "/api/orders")
    got_b = Plate.registry.resolve("svc_beta", "GET", "/api/orders")
    assert got_a is spec_a1
    assert got_b is spec_b1
    assert got_a is not got_b, "不同 service 的同名 endpoint 是两个独立 spec"
    assert len(Plate.registry._index) == 2  # noqa: SLF001


# ════════════════════════════════════════════════════════════════════════════
# [5] warm() 正常
# ════════════════════════════════════════════════════════════════════════════

def test_warm_returns_all_specs_of_batch_services() -> None:
    """业务需求:warm() 返回该批 service 的全部 EndpointSpec。

    对应设计:§_Registry.warm 实现。
    业务影响:违反 = contract check 拿不到完整 spec 集合,部分 endpoint 漏检。
    """
    w1 = EndpointSpec(method="GET", path="/api/w1", responses={200: Resp})
    w2 = EndpointSpec(method="GET", path="/api/w2", responses={200: Resp})
    v1 = EndpointSpec(method="GET", path="/api/v1", responses={200: Resp})
    _make_service_module("warm_a", {"w1": w1, "w2": w2})
    _make_service_module("warm_b", {"v1": v1})

    result = Plate.registry.warm(["warm_a", "warm_b"])
    returned_ids = {id(s) for s in result}
    assert {id(w1), id(w2), id(v1)} == returned_ids, (
        f"warm 返回的应是这两个 service 的所有 spec,实际 {returned_ids}"
    )
    # 已加载
    assert Plate.registry.is_loaded("warm_a")
    assert Plate.registry.is_loaded("warm_b")
    assert sorted(Plate.registry.loaded_services()) == ["warm_a", "warm_b"]


# ════════════════════════════════════════════════════════════════════════════
# [6] warm() 部分失败 → BootstrapError 聚合错误
# ════════════════════════════════════════════════════════════════════════════

def test_warm_partial_failure_aggregates_errors() -> None:
    """业务需求:warm() 部分 service 失败 → BootstrapError 聚合所有错误信息。

    对应设计:§_Registry.warm 错误聚合。
    业务影响:违反 = 作者一次只能看到一个错,反复 warm 反复改,迭代慢;
             已成功的 service 也不应被记入 issues。
    """
    good_spec = EndpointSpec(method="GET", path="/api/good", responses={200: Resp})
    _make_service_module("mix_good", {"g": good_spec})
    # 第二个 service 不造模块 → collect 时 ImportError
    with pytest.raises(BootstrapError) as exc:
        Plate.registry.warm(["mix_good", "mix_missing"])
    msg = str(exc.value)
    assert "mix_missing" in msg, f"失败的 service 应在 issues 列表: {msg}"
    assert "No module named" in msg or "import" in msg.lower(), (
        f"错误信息应附原始原因: {msg}"
    )
    # 已成功的 service 不应被记入 issues
    assert "mix_good" not in msg, f"成功的 service 不应出现在错误里: {msg}"
    # 已成功的 service 也应保留(失败不污染已成功的状态)
    assert Plate.registry.is_loaded("mix_good"), "部分失败不污染已成功 service"
    assert not Plate.registry.is_loaded("mix_missing")


# ════════════════════════════════════════════════════════════════════════════
# [7] warm() 全部失败 → BootstrapError 含全部信息
# ════════════════════════════════════════════════════════════════════════════

def test_warm_full_failure_lists_all_services() -> None:
    """业务需求:warm() 全部 service 失败 → BootstrapError 含全部失败的 service 名。

    对应设计:§_Registry.warm 错误聚合。
    业务影响:违反 = 作者只看到第一个失败名,反复 fix 后才看到下一个,调试慢。
    """
    with pytest.raises(BootstrapError) as exc:
        Plate.registry.warm(["ghost1", "ghost2", "ghost3"])
    msg = str(exc.value)
    for s in ["ghost1", "ghost2", "ghost3"]:
        assert s in msg, f"错误信息应含 {s}: {msg}"
    # 一个都不应被标记为 loaded
    for s in ["ghost1", "ghost2", "ghost3"]:
        assert not Plate.registry.is_loaded(s)


# ════════════════════════════════════════════════════════════════════════════
# [8] 拉式收集 type 严格匹配
# ════════════════════════════════════════════════════════════════════════════

def test_collect_strict_type_match_excludes_subclasses() -> None:
    """业务需求:继承 EndpointSpec 的子类不被收集(防恶意/误用污染 index)。

    对应设计:v3 §3.4 "拉式收集用 type(x) is 而不是 isinstance(x)"。
    业务影响:违反 = 任何继承自 EndpointSpec 的类都自动被收进 index,
             可能引入与作者意图不符的 endpoint,scenario 行为不可预测。
    """
    class EvilSubclass(EndpointSpec):  # type: ignore[misc]
        """@final 拦不住运行时继承(只拦 mypy),但 type(x) is 严格匹配会拦。"""
        pass

    real_spec = EndpointSpec(method="GET", path="/api/real", responses={200: Resp})
    fake_spec = EvilSubclass(method="GET", path="/api/fake", responses={200: Resp})
    _make_service_module("strict_service", {"real": real_spec, "fake": fake_spec})

    got = Plate.registry.resolve("strict_service", "GET", "/api/real")
    assert got is real_spec
    # 关键的:fake_spec 没被收进去 → resolve 它会抛 LookupError
    with pytest.raises(LookupError) as exc:
        Plate.registry.resolve("strict_service", "GET", "/api/fake")
    assert "/api/fake" in str(exc.value)


def test_collect_strict_type_match_excludes_non_endpoint_spec_objects() -> None:
    """业务需求:非 EndpointSpec 实例(BaseModel/dataclass/str)不被收集。

    对应设计:§_Registry._collect_locked 严格 type 匹配。
    业务影响:违反 = 模块里随便一个常量都可能污染 index,registry 行为不可预测。
    """
    real_spec_8b = EndpointSpec(method="GET", path="/api/real", responses={200: Resp})
    make_model = _good_model("NoiseModel")

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

    Plate.registry.collect("noise_service")
    # 噪声全被过滤
    assert len(Plate.registry._index) == 1  # noqa: SLF001
    assert EndpointKey("noise_service", "GET", "/api/real") in Plate.registry._index  # noqa: SLF001


# ════════════════════════════════════════════════════════════════════════════
# [9] is_loaded / loaded_services
# ════════════════════════════════════════════════════════════════════════════

def test_is_loaded_and_loaded_services_reflect_state() -> None:
    """业务需求:is_loaded / loaded_services 正确反映 registry 状态。

    对应设计:§"introspection API"。
    业务影响:违反 = 报告工具(contract check / mock 启动)无法判断当前已加载 service。
    """
    assert Plate.registry.is_loaded("never_touched") is False
    assert Plate.registry.loaded_services() == []

    s1 = EndpointSpec(method="GET", path="/a", responses={200: Resp})
    s2 = EndpointSpec(method="GET", path="/b", responses={200: Resp})
    _make_service_module("info_a", {"a": s1})
    _make_service_module("info_b", {"b": s2})

    Plate.registry.collect("info_a")
    assert Plate.registry.is_loaded("info_a") and not Plate.registry.is_loaded("info_b")
    assert Plate.registry.loaded_services() == ["info_a"]

    # 一次性 warm 两个
    Plate.registry.warm(["info_b"])
    assert sorted(Plate.registry.loaded_services()) == ["info_a", "info_b"]


# ════════════════════════════════════════════════════════════════════════════
# [10] reset()
# ════════════════════════════════════════════════════════════════════════════

def test_reset_clears_index_and_loaded() -> None:
    """业务需求:reset() 清空 _index 与 _loaded 集合(测试间隔离)。

    对应设计:§_Registry.reset。
    业务影响:违反 = 测试间状态污染,后续测试可能拿到"已加载"假象,
             误判"按需加载"行为。
    """
    r_spec = EndpointSpec(method="GET", path="/api/r", responses={200: Resp})
    _make_service_module("reset_svc", {"r": r_spec})
    Plate.registry.collect("reset_svc")
    assert len(Plate.registry._index) == 1  # noqa: SLF001
    assert Plate.registry.is_loaded("reset_svc")

    Plate.registry.reset()
    assert len(Plate.registry._index) == 0  # noqa: SLF001
    assert Plate.registry.loaded_services() == []
    assert Plate.registry.is_loaded("reset_svc") is False


# ════════════════════════════════════════════════════════════════════════════
# [11] resolve 返回 frozen spec 在锁外仍可用
# ════════════════════════════════════════════════════════════════════════════

def test_resolved_frozen_spec_is_safe_to_read_outside_lock() -> None:
    """业务需求:resolve 返回的 frozen spec 在锁外仍可读(frozen 配合)。

    对应设计:§_Registry.resolve 锁外可用性。
    业务影响:违反 = 锁外读到一半被改,TOCTOU 风险,scenario 拿到不一致数据。
    """
    f_spec = EndpointSpec(method="POST", path="/api/f", request=Req, responses={200: Resp})
    _make_service_module("frozen_svc", {"f": f_spec})

    got = Plate.registry.resolve("frozen_svc", "POST", "/api/f")
    # frozen=True → 实例不可变
    with pytest.raises(Exception):  # FrozenInstanceError 或 AttributeError
        got.method = "GET"  # type: ignore[misc]
    # 但读、辅助方法都正常
    assert got.has_request() is True
    assert got.response_models() == {200: Resp}


# ════════════════════════════════════════════════════════════════════════════
# [12] path 末尾斜杠:不做规范化
# ════════════════════════════════════════════════════════════════════════════

def test_path_trailing_slash_not_normalized() -> None:
    """业务需求:path 末尾斜杠不做规范化(契约保真,严格按作者声明收集)。

    对应设计:§"契约保真" — 不做隐式归一化。
    业务影响:违反 = `/api/orders` 和 `/api/orders/` 被合并,
             实际服务可能对两个 path 行为不同,wire 格式被破坏。
    """
    p1 = EndpointSpec(method="GET", path="/api/orders", responses={200: Resp})
    p2 = EndpointSpec(method="GET", path="/api/orders/", responses={200: Resp})
    _make_service_module("path_svc", {"no_slash": p1, "with_slash": p2})

    g1 = Plate.registry.resolve("path_svc", "GET", "/api/orders")
    g2 = Plate.registry.resolve("path_svc", "GET", "/api/orders/")
    assert g1 is p1
    assert g2 is p2
    assert g1 is not g2, "末尾斜杠差异被视为不同 endpoint(契约保真,不自动归一化)"
