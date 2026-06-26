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
    internal_modules = {pkg, f"{pkg}.core", f"{pkg}._aliases", f"{pkg}.spec",
                        f"{pkg}.binding", f"{pkg}.path_resolver",
                        f"{pkg}.doc", f"{pkg}.serialization",
                        f"{pkg}.version", f"{pkg}.manifest",
                        f"{pkg}.server", f"{pkg}.server.response",
                        f"{pkg}.server.router",
                        f"{pkg}.fin.dannotations"}
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
        and m.split(".")[1] not in {"core", "_aliases", "spec", "binding",
                                     "path_resolver", "doc",
                                     "serialization", "version", "manifest",
                                     "server", "router", "response",
                                     "fin", "dannotations"}
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
                        f"{_PKG}._aliases", f"{_PKG}.spec",
                        f"{_PKG}.binding", f"{_PKG}.path_resolver",
                        f"{_PKG}.doc", f"{_PKG}.serialization",
                        f"{_PKG}.version", f"{_PKG}.manifest",
                        f"{_PKG}.server", f"{_PKG}.server.response",
                        f"{_PKG}.server.router",
                        f"{_PKG}.fin.dannotations"}
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


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #7:fin 31 端点全部带 category 标注(PR-C / PLATE_DESIGN §3.4(c))
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_fin_endpoints_have_category():
    """业务不变量:fin 服务的 31 端点全部带 category 标注。

    对应设计:PR-C §2.4 端点 category 判定清单 + §3.4(c) review pipeline 强制规则。
    业务影响:任何端点漏标 = CT 主动探测可能误判业务写入,生产事故。

    注:与 test_every_fin_endpoint_has_category (test_fin_category_coverage.py)
    互补 —— 后者是"31 项精确路径全有标注",本不变量是"registry 中所有 fin
    端点全有标注"(对将来新增端点也生效)。
    """
    from Plate.spec import EndpointCategory

    pkg = importlib.import_module(_PKG)
    mr = pkg.registry

    no_label: list[str] = []
    for key, spec in mr._index.items():  # noqa: SLF001
        if key.service != "fin":
            continue
        if not isinstance(spec.category, EndpointCategory):
            no_label.append(f"{key.method} {key.path}")

    assert not no_label, f"fin 端点未标 category: {no_label}"


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #8:fin 服务的所有 QUERY/TOOL 端点 mutates_state=False(PR-C §2.4)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_fin_query_endpoints_do_not_mutate():
    """业务不变量:fin 服务的所有 QUERY/TOOL 端点 mutates_state=False。

    对应设计:PR-C §2.4 端点 category 判定清单 + PLATE_DESIGN §3.2 真实事故风险。
    业务影响:任何破坏 = CT 探测可触发业务写入,生产事故。
    """
    from Plate.spec import EndpointCategory

    pkg = importlib.import_module(_PKG)
    mr = pkg.registry

    violations: list[str] = []
    for key, spec in mr._index.items():  # noqa: SLF001
        if key.service != "fin":
            continue
        if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if spec.mutates_state is not False:
                violations.append(
                    f"{key.method} {key.path}: "
                    f"category={spec.category.value} 但 "
                    f"mutates_state={spec.mutates_state!r}"
                )

    assert not violations, (
        "fin 服务的 QUERY/TOOL 端点未保持 mutates_state=False:\n  "
        + "\n  ".join(violations)
    )


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #9:binding 的 from_path 不引用本 endpoint 自身(PR-D2 / PLATE_DESIGN §2.4)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_no_self_binding():
    """业务不变量:任何 FieldBinding 的 from_path 不引用其所属 endpoint 的响应。

    对应设计:PLATE_DESIGN §2.4 "from_path 描述另一端点的响应路径"
             + PR-D2 §2.4 跨端点约束。
    业务影响:违反 = binding 表达"用自己响应注入自己请求"是循环,
             runtime 注入时找不到"上一跳"端点,会静默失败或拿到 None。

    注:本测试只对**已 collect 进 registry** 的 spec 断言;fixture 中的瞬时 spec
    不参与此不变量(它们的合法性由 test_binding.py 单独覆盖)。
    """
    pkg = importlib.import_module(_PKG)
    mr = pkg.registry

    violations: list[tuple[str, str, str]] = []
    for key, spec in mr._index.items():  # noqa: SLF001
        # 防御:bindings 字段在 PR-D2 之前不存在;只在 spec 实际有 bindings 时检查
        bindings = getattr(spec, "bindings", ()) or ()
        for i, b in enumerate(bindings):
            # from_path 为空 tuple = "整个 body" → 仍指向"别的端点的 body"
            # 不算 self-binding(它表达"对方给啥我全收",是合法 use case)
            if not b.from_path:
                continue
            # 业务规则:from_path 的首段不能等于本 endpoint 的 path 字段名或
            # 整个 path。本质是"binding 不应引用自身 endpoint"。
            # 简化的硬护栏:from_path 出现在本 spec.responses 的字段树中 → 自指
            # (说明作者误把"自己响应的字段"当"另一端点的字段")。
            # 完整实现需要跨端点 lookup,本不变量只做"本 spec 内的自指"硬护栏。
            response_models = spec.responses or {}
            for status_code, resp_model in response_models.items():
                # 拿响应模型的字段名集合
                resp_fields = set(_model_field_names(resp_model))
                # from_path 第一段如果在响应模型字段里 → 自指风险
                if b.from_path[0] in resp_fields:
                    violations.append(
                        (
                            f"{key.service} {key.method} {key.path}",
                            f"bindings[{i}]",
                            f"from_path[0]={b.from_path[0]!r} 与本 endpoint "
                            f"{status_code} 响应模型 {resp_model.__name__} 字段重叠",
                        )
                    )

    assert not violations, (
        "binding 存在自指(从本 endpoint 响应取字段注入本 endpoint 请求):\n  "
        + "\n  ".join(f"{loc} {b}: {reason}" for loc, b, reason in violations)
    )


def _model_field_names(model: type | None) -> list[str]:
    """取 Pydantic 模型的字段名列表;非 BaseModel / None 返回空列表。"""
    if model is None:
        return []
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        return []
    return list(getattr(model, "model_fields", {}).keys())


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #10:L1/L2 对称性(PR-D3 / PLATE_DESIGN §4 L1/L2 物理解耦)
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_l1_l2_symmetry():
    """业务不变量:有 L2 doc 必有 L1 spec(单向对称)。

    对应设计:PLATE_DESIGN §4 + PR-D3 §2.5。
    业务影响:doc 写给幽灵 endpoint = 文档库腐化,AI 误导;
             doc 残留对应 spec 已删除 = 同样的"幽灵文档"问题。

    反向不强制:有 L1 spec 可以暂时无 L2 doc(PR-D3 §1.3 不强制存量,
    后续 PR 渐进补)。
    """
    pkg = importlib.import_module(_PKG)
    mr = pkg.registry

    # 已知 L2 doc 模块清单(PR-D3 阶段只有 fin;后续 PR 扩展)
    # 注:模块不存在 / 模块无 _DOCS = "此 service 还没建 dannotations 层",
    #     跳过该 service(等价于"全 service 无 L2 doc"的对称状态)。
    l2_modules: list[tuple[str, types.ModuleType]] = []
    for service in ("fin",):
        modname = f"{_PKG}.{service}.dannotations"
        try:
            mod = importlib.import_module(modname)
        except ImportError:
            continue  # 该 service 无 dannotations 模块,跳过
        if not hasattr(mod, "_DOCS"):
            continue
        l2_modules.append((service, mod))

    violations: list[str] = []
    for service, mod in l2_modules:
        docs: dict = getattr(mod, "_DOCS")
        # 收集该 service 在 registry 里的所有 path(PR-D3 暂只验 fin,
        # path 全局唯一性由 spec.py 保证,无需 service 前缀过滤)
        spec_paths = {
            key.path
            for key, _spec in mr._index.items()  # noqa: SLF001
            if key.service == service
        }

        # 有 L2 doc 但 registry 找不到对应 spec → 幽灵文档
        for doc_path in docs:
            if doc_path not in spec_paths:
                violations.append(
                    f"{service} dannotations._DOCS[{doc_path!r}]: "
                    f"registry 中找不到对应 spec(可能 spec 已删除但 doc 残留)"
                )

    assert not violations, (
        "L1/L2 对称性不变量被破坏(L2 引用了不存在的 L1):\n  "
        + "\n  ".join(violations)
    )


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #11:PlateManifest 字节级 pin(PR-2.0 / Phase 2 服务化基础)
# ════════════════════════════════════════════════════════════════════════════


def test_invariant_plate_manifest_byte_equal():
    """业务不变量:同 version + 同 services → 两次 build manifest 必须 byte-equal。

    对应设计:PR-2.0 §2.4(版本 pin 是硬前提)+ PLATE_DESIGN §7(契约保真)。
    业务影响:byte-equal 失守 = 服务化后客户端拉到的 manifest 与本地对比失败,
    执行可复现性破坏。

    字节级 pin 要求:
      - 同 version + 同 services → 同 checksum
      - dict 插入顺序无关(sort_keys=True)
      - list 端点顺序无关(按 (method, path) 排序)
      - checksum 是 SHA256 hex(64 字符)
    """
    import json

    from Plate.manifest import PlateManifest
    from Plate.version import PlateVersion

    version = PlateVersion(1, 0, 0)
    services_a = {"fin": [{"method": "GET", "path": "/a"},
                           {"method": "POST", "path": "/b"}]}
    services_b = {"fin": [{"method": "POST", "path": "/b"},
                           {"method": "GET", "path": "/a"}]}

    m1 = PlateManifest.from_services(version, services_a)
    m2 = PlateManifest.from_services(version, services_b)
    assert m1.checksum == m2.checksum, (
        f"byte-equal 失守:同输入产生不同 checksum"
        f"\n  m1={m1.checksum}\n  m2={m2.checksum}"
    )

    # 同一 manifest 序列化两次必须 byte-equal
    j1 = json.dumps(m1.to_dict(), sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(m2.to_dict(), sort_keys=True, separators=(",", ":"))
    assert j1 == j2


def test_invariant_plate_manifest_drift_detection():
    """业务不变量:篡改 services 后 verify() 必须抛 ValueError(漂移检测)。

    对应设计:PR-2.0 §2.4 verify() 语义。
    业务影响:漂移检测失守 = 客户端无法发现"远端被中间代理篡改",契约安全破坏。
    """
    from Plate.manifest import PlateManifest
    from Plate.version import PlateVersion

    m = PlateManifest.from_services(
        PlateVersion(1, 0, 0),
        {"fin": [{"method": "GET", "path": "/a"}]},
    )
    # 篡改内部 list(绕过 frozen 用可变 dict 内引用)
    m.services["fin"].append({"method": "GET", "path": "/evil"})

    from Plate.manifest import PlateManifest as _PM
    try:
        m.verify()
        raised = False
    except ValueError as e:
        raised = "checksum 不一致" in str(e)
    assert raised, (
        "verify() 应在篡改后抛 ValueError(checksum 不一致),"
        "实际未抛或错误信息不符"
    )
    _ = _PM  # 防止 unused 警告


# ════════════════════════════════════════════════════════════════════════════
# 不变量 #12:服务端协议响应 byte-equal(PR-2.3 / A2 + A5)
# ════════════════════════════════════════════════════════════════════════════


def test_invariant_server_protocol_byte_equal():
    """业务不变量:服务端 HTTP 响应 JSON 与本地 to_dict 字节级一致(协议可执行性)。

    对应设计:PR-2.1 §2 + PR-2.3 §3.2 + A5 协议先于实现。
    业务影响:服务端与本地序列化漂移 = SDK 端解析失败 / checksum 校验失败 /
    客户端永远拿不到正确数据 —— 这是"协议可执行"的硬护栏。

    字节级 pin 要求:
      - 服务端 manifest checksum == 本地 PlateManifest.from_services 算的 checksum
      - 服务端 /v1/spec/{service} 响应 JSON 字段 == 本地 spec.to_dict() 字段
      - 服务端单端点 spec 响应 == 本地 spec.to_dict()
    """
    import json
    import urllib.error
    import urllib.request

    from Plate import registry as _reg
    from Plate.manifest import PlateManifest as _PM
    from Plate.server import DEFAULT_VERSION as _DV
    from Plate.server import PlateServer as _PS

    # 隔离 registry + 启动独立 server(端口 0 动态分配)
    _reg.reset()
    server = _PS(port=0)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"

        # 1. /v1/manifest 的 checksum 与本地一致
        with urllib.request.urlopen(f"{base}/v1/manifest") as r:
            remote_manifest = json.loads(r.read().decode("utf-8"))
        _reg.collect("fin")
        local_specs = [
            s.to_dict() for k, s in _reg._index.items() if k.service == "fin"  # noqa: SLF001
        ]
        local_manifest = _PM.from_services(_DV, {"fin": local_specs})
        assert remote_manifest["checksum"] == local_manifest.checksum, (
            f"服务端 manifest checksum 与本地不一致(协议漂移):\n"
            f"  remote={remote_manifest['checksum']}\n"
            f"  local ={local_manifest.checksum}"
        )

        # 2. /v1/spec/fin 的 specs 与本地一致
        with urllib.request.urlopen(
            f"{base}/v1/spec/fin?version=1.0.0"
        ) as r:
            remote_specs = json.loads(r.read().decode("utf-8"))["specs"]
        local_sorted = sorted(
            local_specs, key=lambda s: (s["method"], s["path"])
        )
        assert remote_specs == local_sorted, (
            "服务端 /v1/spec/fin 响应与本地 spec 列表字段不一致(协议漂移)"
        )

        # 3. /v1/spec/fin/POST/... 单端点 spec 与本地一致
        try:
            with urllib.request.urlopen(
                f"{base}/v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0"
            ) as r:
                remote_endpoint = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            pytest.fail(
                f"服务端单端点 spec 拉取失败: {e.code} {e.read().decode()[:200]}"
            )
        local_endpoint = _reg.resolve(
            "fin", "POST", "/api/order/order/orderDetail"
        ).to_dict()
        assert remote_endpoint["spec"] == local_endpoint, (
            "服务端单端点 spec 与本地 spec.to_dict() 不一致(协议漂移)"
        )
    finally:
        server.stop()
        _reg.reset()
