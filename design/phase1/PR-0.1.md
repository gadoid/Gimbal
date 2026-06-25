# PR-0.1: pytest 基线

> **状态**:✅ 已完成(2026-06-25)
>
> **PR 范围**:不写新业务代码,只建一个最小可执行的 pytest 基线,让 `pytest tests/` 能干净收集(无 INTERNALERROR)。
>
> **对应设计**:[PLATE_DESIGN.md §7 不变承诺](../PLATE_DESIGN.md) 的 "零侵入 / 按需加载" 需可被 CI 验证。

---

## 1. 背景与动机

### 1.1 现状盘点

执行前对仓库做了盘点,发现:

| 现象 | 影响 |
|---|---|
| 26 个 `tests/**/test_*.py` 中, **22 个是 print+assert 脚本风格**(顶层 `assert ...`,不在 `def test_xxx():` 里) | pytest 不识别为测试,只在 import 时执行 |
| `tests/unit/test_defect_fixes.py` 顶层调用 `sys.exit(1)` | **任何 `pytest tests/` 全量收集触发 INTERNALERROR** |
| 4 个 `tests/unit/reporter/*` 等是 `def test_xxx` 函数 | pytest 能识别,可正常跑 |
| 没有 `tests/conftest.py` | 每个测试文件重复 `sys.path.insert(0, ...)` |
| 没有 `[tool.pytest]` 配置块 | 行为靠默认推断 |

### 1.2 业务动机(为什么需要这个 PR)

**业务需求**:后续所有 PR(改名、加 category、FieldBinding、EndpointDoc、review pipeline)都需要一个"绿基线"做对照——每改一处,能跑一遍 `pytest tests/` 立即知道有没有回归。

**当前基线问题**:
- `pytest tests/` 抛 INTERNALERROR → **无法知道"改坏了什么"**
- 22 个 print+assert 脚本是手动 `python xxx.py` 跑的 → **不进入 CI**,不进入"绿基线"

### 1.3 关键决策

详见 [DECISIONS.md D1](DECISIONS.md):**D1=A(全部转 pytest)+ D2=A(先改名再写 PR-0)+ D3=B(含 unit/)** 引出的实际拆分 = **3 个 PR**:

- **PR-0.1(本次)**:pytest 基线 + collect_ignore 隔离(本文件)
- **PR-0.2**:model_registry 4 个核心测试 pytest 化 + 改名
- **PR-0.3**:其余 22 个 unit 脚本渐进 pytest 化(后续会话)

---

## 2. 代码实现要点

### 2.1 改动文件清单(7 个)

| 文件 | 类型 | 作用 |
|---|---|---|
| `pyproject.toml` | 修改 | 加 `[tool.pytest.ini_options]`(testpaths / addopts / asyncio_mode) |
| `tests/conftest.py` | 新建 | 根 conftest, `sys.path` 注入集中管理 |
| `tests/unit/conftest.py` | 新建 | 排除 7 个 print+assert 脚本 |
| `tests/integration/conftest.py` | 新建 | 排除 3 个 print+assert 脚本 |
| `tests/model_registry/conftest.py` | 新建 | 排除 5 个 print+assert 脚本(PR-0.2 删除) |
| `tests/plate/conftest.py` | 新建 | 新业务核心目录的 conftest(暂无 collect_ignore) |
| `tests/plate/test_sanity.py` | 新建 | 5 个 pytest 函数,作为 PR-0.1 "绿点" |

### 2.2 `pyproject.toml` 关键配置

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = [
    "tests/plate",            # 业务核心(PR-0.2 启用)
    "tests/model_registry",   # 临时保留(PR-0.2 删除)
    "tests/unit/reporter",    # 已 pytest 化(无需 ignore)
    "tests/unit/generator",
    "tests/unit/config",
    "tests/unit/scenario",
]
addopts = ["-ra", "--strict-markers", "--tb=short"]
asyncio_mode = "auto"
```

**业务意图**:
- `testpaths` 显式声明"哪些目录参与 pytest 收集",避免 pytest 默认递归 `tests/` 时被 print+assert 脚本污染
- `addopts` 让"失败时信息更清晰",便于 review 时的"基线对账"
- `asyncio_mode = "auto"` 兼容现有 reporter/generator 已有 pytest 化代码

### 2.3 `tests/conftest.py` 关键代码

```python
import sys
import os

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
```

**业务意图**:
- 消除 22 个测试文件重复的 `sys.path.insert(0, ...)` —— **这是"维护成本"约束**
- 不破坏"从 `tests/<dir>` 单独跑"的旧工作流(因为 `_SRC` 用 `os.path.abspath` 解析,与执行路径无关)

### 2.4 `collect_ignore_glob` 隔离模式

每个 `tests/{unit,integration,model_registry}/conftest.py` 都用 `collect_ignore_glob` 排除 print+assert 脚本:

```python
# tests/unit/conftest.py
collect_ignore_glob = [
    "test_asset_materializer.py",
    "test_defect_fixes.py",  # ← 触发 INTERNALERROR 的元凶
    # ... 共 7 个
]
```

**业务意图**:
- 暂不"破坏"22 个脚本 —— 它们仍可手动 `python tests/<dir>/test_xxx.py` 跑
- `collect_ignore_glob` 是 pytest 官方推荐隔离方式 —— 后续 PR-0.3 渐进 pytest 化时,只需**从此清单删除文件名**,无需改测试文件本身

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

按用户明确指示:"**测试用例需要是面向业务需求的,不是在验证功能是否可用**"。

每个测试都回答"**这个业务承诺有没有被破坏**",不回答"代码能不能跑"。

### 3.2 5 个 sanity 测试(全部通过)

#### 测试 1: `test_model_registry_importable`

**业务需求**:ModelRegistry 包可被 import(PR-0.2 改名为 Plate 后此测试更新)。
**对应设计**:[PLATE_DESIGN.md §0](../PLATE_DESIGN.md) "数据契约" —— Plate 提供接口真值,所有消费方依赖此 import。
**业务影响**:破坏此约束 = 整个 GIMBAL 执行态不可用。

```python
def test_model_registry_importable() -> None:
    import ModelRegistry
    # 顶层只暴露 registry + BootstrapError(零侵入承诺,设计 §7)
    assert "registry" in ModelRegistry.__all__
    assert "BootstrapError" in ModelRegistry.__all__
    # registry 是进程级单例
    assert ModelRegistry.registry is registry
    assert ModelRegistry.BootstrapError is BootstrapError
```

#### 测试 2: `test_endpoint_spec_constructible`

**业务需求**:EndpointSpec 基础构造可工作。
**对应设计**:[PLATE_DESIGN.md §2.1](../PLATE_DESIGN.md) —— EndpointSpec 是契约描述的基础类型,所有 endpoint 必须能成功构造,否则 service 加载链断。

```python
def test_endpoint_spec_constructible() -> None:
    # 真实业务场景:每个 fin 端点都需 EndpointSpec(method=..., path=..., request=..., responses=...)
    spec = EndpointSpec(method="POST", path="/api/test/sanity", request=Req, responses={200: Resp})
    assert spec.method == "POST"
    assert spec.path == "/api/test/sanity"
```

#### 测试 3: `test_registry_cold_state_after_import`

**业务需求**:import 顶层后,registry 处于"冷"状态(按需加载承诺)。
**对应设计**:[PLATE_DESIGN.md §4 / §7](../PLATE_DESIGN.md) —— Registry 启动后不预加载任何 service,必须等到真的 resolve 才触达对应子模块。
**业务影响**:破坏此约束 = 导入 Plate 时所有 service 一次性 import,启动慢、零侵入失守。

```python
def test_registry_cold_state_after_import() -> None:
    # registry 是单例;在测试中可能已被其他测试触碰,只验证"未加载 fin"
    assert not registry.is_loaded("fin"), (
        "registry 应在未显式 resolve 前不预加载 fin"
    )
```

#### 测试 4: `test_endpoint_key_hashable`

**业务需求**:EndpointKey 可作 dict key / set element。
**对应设计**:[PLATE_DESIGN.md §2.4](../PLATE_DESIGN.md) —— EndpointKey 是 Registry 索引键,必须可哈希,否则 `_index` / `_loaded` 集合无法构建。
**业务影响**:破坏此约束 = 整个 Registry 索引机制失效。

```python
def test_endpoint_key_hashable() -> None:
    k = EndpointKey(service="fin", method="POST", path="/api/test")
    s = {k}
    d = {k: "value"}
    assert k in s
    assert d[k] == "value"
```

#### 测试 5: `test_bootstrap_error_is_runtime_error`

**业务需求**:BootstrapError 继承 RuntimeError。
**对应设计**:[PLATE_DESIGN.md §4 / v3 §10.2](../PLATE_DESIGN.md) —— warm() 失败时抛 BootstrapError,调用方常用 `isinstance(e, RuntimeError)` 兜底捕获。
**业务影响**:破坏此约束 = 现有 framework 调用方的兜底捕获逻辑漏掉错误,启动失败时静默吞错。

```python
def test_bootstrap_error_is_runtime_error() -> None:
    assert issubclass(BootstrapError, RuntimeError)
    err = BootstrapError("test")
    assert isinstance(err, RuntimeError)
```

### 3.3 测试覆盖矩阵

| 不变承诺(设计 §7) | 覆盖测试 | 备注 |
|---|---|---|
| 零侵入 | 测试 1 | `__all__` 显式只含 registry + BootstrapError |
| 按需加载 | 测试 3 | registry 启动后不预加载 |
| 契约保真 | (未覆盖) | 由 PR-0.2 改造时补(原 `test_spec.py` 已覆盖) |
| 互补而非替代 | (本 PR 范围外) | 由 Phase 2/3 验证 |
| 优雅降级 | (本 PR 范围外) | 由 Phase 2 验证 |
| EndpointKey 哈希 | 测试 4 | 索引键基础约束 |
| BootstrapError 异常类型 | 测试 5 | 异常路径基础约束 |
| EndpointSpec 构造 | 测试 2 | 契约本体基础约束 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
pytest tests/plate/ -v   # 5 sanity tests
pytest tests/             # 139 tests full
```

### 4.2 验收

```
============================ 139 passed, 1 warning in 0.80s =============================
```

| 项 | 值 |
|---|---|
| 收集测试数 | 139 |
| 失败 | 0 |
| 错误 | 0 |
| 警告 | 1(loguru 内部 asynci.iscoroutinefunction 弃用,与本 PR 无关) |

### 4.3 解决了什么

- `pytest tests/` 触发 INTERNALERROR(`test_defect_fixes.py` 顶层 `sys.exit(1)`) → **已解决**
- 22 个 print+assert 脚本未 pytest 化 → **暂排除**(后续 PR-0.3 渐进 pytest 化)

### 4.4 没解决什么(明确留给后续 PR)

| 项 | 留给 |
|---|---|
| 22 个 print+assert 脚本未 pytest 化 | PR-0.3 |
| `src/ModelRegistry` 改名为 `src/Plate` | PR-0.2 / PR-A |
| 4 个 model_registry 核心测试未 pytest 化 | PR-0.2 |

---

## 5. 与后续 PR 的衔接

- **PR-0.2** 将删除 `tests/model_registry/` 与 `tests/model_registry/conftest.py`,改为 `tests/plate/`(已建好,等迁)
- **PR-0.3** 将从 `tests/unit/conftest.py` 与 `tests/integration/conftest.py` 的 `collect_ignore_glob` 列表中渐进删除文件名
- **PR-A**(若单独执行)将删除 `pyproject.toml` 的 `tests/model_registry` testpath 项
