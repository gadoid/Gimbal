# PR-0.2: model_registry 4 测试 pytest 化 + 改名

> **状态**:待执行
>
> **PR 范围**:把 `tests/model_registry/` 4 个 print+assert 脚本转 pytest 函数,合并入 `tests/plate/`(实现 PR-A 重命名 + 测试 pytest 化),完成 Phase 1 业务核心的 pytest 化。
>
> **前置依赖**:[PR-0.1](PR-0.1.md) ✅
>
> **合并**:原计划 [PR-A](PR-A.md) 纯重命名,按用户决策 D2=A 合并入本 PR。

---

## 1. 背景与动机

### 1.1 业务需求

**当前问题**:`tests/model_registry/` 下 4 个 print+assert 脚本(`test_zero_invasion.py` / `test_spec.py` / `test_core.py` / `test_aliases.py`)+ 1 个并发测试(`test_concurrent_resolve.py`)是 ModelRegistry 业务核心的护栏,但被 PR-0.1 的 `collect_ignore_glob` 暂排除出 pytest,只能手动跑。

**业务影响**:
- 后续 PR(改名、加 category、FieldBinding、EndpointDoc)改了核心代码,这些"护栏"在 CI 看不到,无法及时发现回归
- 22 个 unit 脚本 pytest 化是 PR-0.3 的工作;本 PR 只动 model_registry 这 5 个核心测试,先解锁"业务核心可被 CI 验证"

### 1.2 关键决策

- **D1=A**(全部转 pytest 函数)
- **D2=A**(先改名,再写测试)—— 改名与测试 pytest 化在**同一 PR** 完成
- **D3=B**(含 unit/)—— 拆分:本 PR 只动 model_registry;unit 脚本留给 PR-0.3

### 1.3 与 PR-0.1 的边界

- PR-0.1 已建:`tests/plate/` 目录(空)、`tests/plate/conftest.py`、`tests/plate/test_sanity.py`(5 个测试)
- PR-0.2 收:把 5 个 model_registry 测试迁到 `tests/plate/`,加新 `test_invariants.py` 聚合入口,删 `tests/model_registry/`

---

## 2. 代码实现要点

### 2.1 改动文件清单

#### A. 重命名(PR-A 范畴)

| 操作 | 路径 |
|---|---|
| `git mv` | `src/ModelRegistry/` → `src/Plate/` |
| 改字符串 | `src/Plate/__init__.py`, `core.py`, `_aliases.py`, `spec.py`, `fin/__init__.py`, `fin/models.py` |
| 改字符串 | `pyproject.toml`(若有 `packages` 列表) |
| 改字符串 | `tests/plate/test_sanity.py`(用 `from Plate import ...`) |

**改动面盘点**(实际执行时再 `grep -rn "ModelRegistry"`):
- 5 个源文件 import/importlib/错误信息
- 5 个 model_registry 测试文件(本次 pytest 化时改)
- `pyproject.toml` 的 `[tool.hatch.build]`(若有 packages 列表)
- 仓库根 `README.md`(若有引用)
- 任何 e2e / scripts / skill 中的引用

#### B. 测试 pytest 化(PR-0.2 主工作)

| 操作 | 路径 |
|---|---|
| 改 | `test_zero_invasion.py` → `tests/plate/test_zero_invasion.py`(pytest 化) |
| 改 | `test_spec.py` → `tests/plate/test_spec.py`(pytest 化) |
| 改 | `test_core.py` → `tests/plate/test_core.py`(pytest 化) |
| 改 | `test_concurrent_resolve.py` → `tests/plate/test_concurrent_resolve.py`(pytest 化) |
| 改 | `test_aliases.py` → `tests/plate/test_aliases.py`(pytest 化) |
| 删 | `tests/model_registry/`(5 文件 + conftest) |
| 删 | `pyproject.toml` 的 `tests/model_registry` testpath 项 |
| 加 | `tests/plate/test_invariants.py`(聚合入口,见 §3) |

#### C. `tests/plate/conftest.py` 更新

PR-0.1 留的 `tests/plate/conftest.py` 是空文件,本 PR 加共享 fixtures:

```python
# 共享:清理 registry 状态
@pytest.fixture(autouse=False)
def clean_registry():
    from Plate.core import registry
    registry.reset()
    yield
    registry.reset()

# 共享:合规 Pydantic 模型工厂
@pytest.fixture
def good_model_factory():
    def make(name="M", extra="forbid"):
        ...
    return make

# 共享:动态造可 import 的 service 子模块
@pytest.fixture
def make_service_module():
    ...
```

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

延续 PR-0.1 原则:**测试用例面向业务需求,不在验证功能是否可用**。

每个 pytest 函数命名采用 `test_<业务承诺>` 格式,docstring 写明:
1. **业务需求是什么**(对应设计哪一条)
2. **业务影响是什么**(破坏这条的后果)
3. **对应设计文档章节**

### 3.2 pytest 化结构(以 `test_core.py` 为例)

原 print+assert 脚本(12 个 print 分块)转 pytest 函数:

```python
# 原:[1] 基础 collect / resolve
# 改为:
def test_resolve_triggers_collect_for_unloaded_service(...):
    """业务需求:首次 resolve 触发对应 service 包 import + 拉式收集。

    对应设计:PLATE_DESIGN.md §4 "Registry 核心 / 按需加载"
    业务影响:破坏此承诺 = 启动时一次性 import 所有 service,启动慢,零侵入失守。
    """
    # arrange
    spec = make_endpoint_spec(...)
    install_fake_service("test_svc", spec)
    # act
    got = registry.resolve("test_svc", "POST", "/x")
    # assert
    assert got is spec
    assert registry.is_loaded("test_svc")
```

### 3.3 业务核心测试矩阵(对应设计 §7 不变承诺)

| 业务承诺 | 测试函数 | 来源(原 print+assert 脚本) |
|---|---|---|
| **零侵入** | `test_import_does_not_load_unreferenced_services` | `test_zero_invasion.py [1]` |
| | `test_top_level_exposes_only_registry_and_bootstrap_error` | `test_zero_invasion.py [2]` |
| | `test_import_gimbal_does_not_load_model_registry` | `test_zero_invasion.py [5]` |
| **按需加载** | `test_resolve_triggers_collect_for_unloaded_service` | `test_core.py [1]` |
| | `test_resolve_failure_does_not_load_service` | `test_zero_invasion.py [4a]` |
| | `test_collect_is_idempotent` | `test_core.py [3]` |
| | `test_warm_part_failure_does_not_pollute_succeeded` | `test_core.py [6]` |
| | `test_warm_total_failure_aggregates_all_errors` | `test_core.py [7]` |
| **线程安全** | `test_concurrent_resolve_no_runtime_error` | `test_concurrent_resolve.py [2]` |
| | `test_concurrent_collect_no_duplicate_indexing` | `test_concurrent_resolve.py [3]` |
| **契约保真** | `test_endpoint_spec_constructible` | `test_spec.py [1]` |
| | `test_get_request_none_is_allowed` | `test_spec.py [2]` |
| | `test_request_must_be_basemodel_subclass` | `test_spec.py [3a]` |
| | `test_response_value_must_be_basemodel_subclass` | `test_spec.py [3c]` |
| | `test_missing_model_config_raises` | `test_spec.py [4a]` |
| | `test_extra_must_be_forbid` | `test_spec.py [4b]` |
| | `test_forbidden_config_keys_all_rejected` | `test_spec.py [4c-4e]` |
| | `test_safe_model_guard_extends_to_responses` | `test_spec.py [4f]` |
| | `test_endpoint_spec_is_frozen` | `test_spec.py [6]` |
| **EndpointSpec 形态** | `test_response_models_returns_shallow_copy` | `test_spec.py [7a]` |
| | `test_has_request_reflects_none_state` | `test_spec.py [7b]` |
| **Protocol hooks** | `test_runtime_checkable_protocol_recognizes_callables` | `test_spec.py [8a-8c]` |
| | `test_inspect_signature_catches_malformed_hooks` | `test_spec.py [8e]` |
| **拉式收集 type 严格匹配** | `test_subclass_of_endpoint_spec_not_collected` | `test_core.py [8a]` |
| | `test_non_endpoint_spec_objects_filtered_out` | `test_core.py [8b]` |
| **多 service 隔离** | `test_same_path_different_service_are_distinct` | `test_core.py [4]` |
| **错误信息友好** | `test_resolve_failure_lists_registered_endpoints_with_hint` | `test_core.py [2]` |
| **path 不归一化** | `test_path_trailing_slash_not_normalized` | `test_core.py [12]` |
| **aliases 解析** | `test_valid_identifier_passes_through` | `test_aliases.py [1]` |
| | `test_hyphenated_service_resolves_via_alias_table` | `test_aliases.py [2]` |
| | `test_numeric_or_dotted_name_rejected` | `test_aliases.py [3]` |
| | `test_python_keyword_rejected_without_alias` | `test_aliases.py [4]` |
| | `test_invalid_alias_value_rejected` | `test_aliases.py [6]` |

### 3.4 新增 `test_invariants.py` 聚合入口

按 PR-0.1 计划,新增**"业务不变量聚合入口"**,不重复测试逻辑,只跑**"全表"** 性质的不变量检查:

```python
"""业务不变量聚合:Phase 1 已建立的不变量一次性验证。

设计 §7 的 5 条不变承诺,每条对应一个不变量,每个不变量用一个测试函数。
这些测试不验证具体功能(由 test_spec.py / test_core.py 等覆盖),只验证
"承诺是否被破坏"。
"""


def test_invariant_zero_invasion_holds():
    """业务不变量:import Plate 顶层不加载任何 service 子包。

    对应设计:PLATE_DESIGN.md §7 不变承诺 1 "零侵入"
    业务影响:任何 service 子包泄漏到 import 顶层 = 破坏零侵入,
             后续 Phase 2 服务化时无法按需加载。
    """
    # 重新模拟"全新进程",卸载 Plate.*
    for m in [m for m in sys.modules if m.startswith("Plate")]:
        del sys.modules[m]
    importlib.invalidate_caches()

    import Plate

    # 内部实现模块(必然加载)
    INTERNAL = {"Plate", "Plate.core", "Plate._aliases", "Plate.spec"}
    loaded = {m for m in sys.modules if m.startswith("Plate")}
    assert loaded <= INTERNAL, f"非内部模块被加载: {loaded - INTERNAL}"


def test_invariant_ondemand_loading_holds():
    """业务不变量:未 resolve 之前,registry 不预加载任何 service。

    对应设计:PLATE_DESIGN.md §7 不变承诺 2 "按需加载"
    业务影响:任何 service 被预加载 = 启动变慢,资源浪费。
    """
    from Plate.core import registry
    # 全清,然后 import
    registry.reset()
    import Plate
    assert registry.loaded_services() == []
    # 真的 resolve 才触达
    spec = make_endpoint_spec(...)
    install_fake_service("test_invariant_ondemand", spec)
    registry.resolve("test_invariant_ondemand", "POST", "/x")
    assert registry.is_loaded("test_invariant_ondemand")


def test_invariant_endpoint_spec_frozen_holds():
    """业务不变量:所有 EndpointSpec 实例 frozen,锁内取出到锁外用无 TOCTOU 风险。

    对应设计:PLATE_DESIGN.md §2.1 "@final + frozen=True"
    业务影响:任何 spec 可变 = 多线程下 race condition,snapshot 失效。
    """
    from Plate.spec import EndpointSpec
    spec = EndpointSpec(method="GET", path="/x", responses={200: GoodModel()})
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.method = "POST"  # type: ignore[misc]


def test_invariant_top_level_exports_minimal():
    """业务不变量:Plate 顶层 __all__ 只含 registry + BootstrapError。

    对应设计:PLATE_DESIGN.md §7 不变承诺 1 "零侵入"
    业务影响:任何 spec / hook 暴露到顶层 = 调用方可能误用,
             破坏"按需 import 子模块"的边界。
    """
    import Plate
    assert set(Plate.__all__) == {"registry", "BootstrapError"}


def test_invariant_contract_fidelity_holds():
    """业务不变量:所有契约模型的 model_config 满足 extra=forbid + 禁用清单全关。

    对应设计:PLATE_DESIGN.md §3.1 "契约保真护栏"
    业务影响:任何契约模型默许 wire 改写 = 数据验证失效,测试与生产不一致。

    注:此测试遍历 Plate.fin.models 的所有 _Base 子类,对 extra=forbid 的
    严格模型断言配置合规;permissive 模型(extra=ignore)按设计 §3.1 豁免。
    """
    from Plate.fin import models as fin_models
    from pydantic import BaseModel

    violations = []
    for name in dir(fin_models):
        obj = getattr(fin_models, name)
        if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
            continue
        cfg = getattr(obj, "model_config", None)
        if cfg is None:
            continue
        if cfg.get("extra") == "forbid":
            # 严格契约模型:必须满足禁用清单
            for forbidden in ("str_strip_whitespace", "coerce_numbers_to_str", "use_enum_values"):
                if cfg.get(forbidden):
                    violations.append(f"{name}.{forbidden}={cfg.get(forbidden)}")

    assert not violations, f"契约保真护栏被破坏: {violations}"
```

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 单跑 plate 测试(应 ≥ 50 个测试函数)
pytest tests/plate/ -v

# 2. 跑全量(应 ≥ 184 个测试,5 个 model_registry 测试加入)
pytest tests/

# 3. 检查零侵入(从全新进程视角)
python -c "
import sys, importlib
for m in [m for m in sys.modules if m.startswith('Plate') or m.startswith('ModelRegistry')]:
    del sys.modules[m]
importlib.invalidate_caches()
import Plate
internal = {'Plate', 'Plate.core', 'Plate._aliases', 'Plate.spec'}
loaded = {m for m in sys.modules if m.startswith('Plate')}
assert loaded <= internal, f'零侵入被破坏: {loaded - internal}'
print('ZERO-INVASION OK')
"
```

### 4.2 验收标准

| 项 | 值 |
|---|---|
| `pytest tests/plate/` 测试数 | ≥ 50 |
| `pytest tests/` 总测试数 | ≥ 184 |
| 失败 | 0 |
| 错误 | 0 |
| 零侵入命令 | OK |
| 5 个旧脚本残留 grep | 0 |
| `pyproject.toml` 残留 `ModelRegistry` 字面 | 0 |

### 4.3 风险点

| 风险 | 缓解 |
|---|---|
| 旧脚本 pytest 化时漏改边界 case(顶层 assert 在 `try/except` 里时) | 逐个 `print` 分块映射到 `def test_` 后,显式断言异常信息 |
| 并发测试 `test_concurrent_resolve.py` pytest 化时随机性导致 flaky | 用 `pytest -p no:randomly` 显式排序;并发测试加 timeout |
| 重命名漏改某文件导致 import 失败 | `grep -rn "ModelRegistry"` 完整盘点;CI 跑 zero-invasion 命令 |

---

## 5. 与后续 PR 的衔接

- **PR-B**(`category` 字段):加在 `EndpointSpec` 上,`test_invariants.py` 的 `test_invariant_endpoint_spec_frozen_holds` 等仍需绿
- **PR-C**(fin 单轨化):`test_invariants.py` 新增 `test_invariant_fin_endpoints_have_category` 验证 31 端点都有 `category`
- **PR-D1**(路径解析器):`test_invariants.py` 新增 `test_invariant_logical_path_resolver_works` 验证解析器覆盖核心场景
