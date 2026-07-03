# core 模块(`Plate/core.py`)

> 本文档详细描述 `Plate/core.py` 中的**每一个公开/内部类、函数、方法**,
> 以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模块的所有
> 行为细节与设计动机。

---

## 1. 模块定位

`core.py` 是 Plate 子系统的**单例注册中心**(Registry)。它解决的核心问题:

> **如何让业务代码通过 `(service, method, path)` 这三个字符串,O(1) 拿到
> 对应的 `EndpointSpec` 实例,且不让"加载所有 service"这件事拖慢启动
> 或占用内存?**

它对外只暴露一个对象 — 模块级单例 `registry`。`Plate/__init__.py` 直接
`from .core import BootstrapError, registry`,业务代码最常见的写法是:

```python
from Plate import registry
spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
```

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
Registry 核心:collect / resolve / warm,线程安全。

设计要点(对应 v3 文档 §3.3 / §10.2):
  - 拉式收集:遍历 service 子包模块命名空间,用 ``type(attr) is EndpointSpec``
    严格匹配(排除继承,配合 ``@final``)
  - 线程安全:``threading.Lock`` 保护 ``_index`` / ``_loaded`` 的修改;
    "collect + dict 读取/迭代"必须在同一把锁内,避免锁外迭代被并发的
    collect 触发 ``RuntimeError: dictionary changed size during iteration``
  - 共用 ``warm()``:`contract check` 与 mock server 启动都走这一入口
  - 按需加载:scenario 加载器和 mock 启动都"按需",未引用的 service
    一个字节都不 import
```

---

## 3. 依赖关系

```python
import importlib
import threading
from dataclasses import dataclass

from ._aliases import resolve_dir_name   # service 名 → 合法 Python 目录名
from .spec import EndpointSpec           # 契约模型本体
```

**为什么这么依赖:**
- `importlib` — 运行时按 service 名动态 import 子包(`importlib.import_module`),
  这是按需加载的核心机制。
- `threading` — 提供 `Lock` 保护 `_index` / `_loaded` 共享状态。
- `dataclasses` — 用来定义 `EndpointKey`(frozen=True,作为 dict key)。
- `_aliases.resolve_dir_name` — service 名可能是 `"fin"`,也可能是
  `"tidb-test-service"`(含连字符);后者必须先查 alias 表转成合法
  Python 包名,才能 import。
- `spec.EndpointSpec` — registry 索引的值;`type(attr).__name__ ==
  "EndpointSpec"` 是收集判定。

**重要的反向依赖约束**:
- `core.py` **不** import `facade` / `server` / `api_doc` / 任何 service
  子包。这保证"零侵入"承诺:任何 `import Plate` 的代码都不会拖入这些
  模块。

---

## 4. 公开类型

### 4.1 `EndpointKey`

```python
@dataclass(frozen=True)
class EndpointKey:
    """Registry 索引键。frozen=True 保证可作 dict key / set element。"""
    service: str
    method: str
    path: str
```

**字段:**
- `service: str` — service 名(如 `"fin"`)。
- `method: str` — HTTP 方法(如 `"POST"`)。**注意:不强制大写**,由调用方
  保证大小写一致;`registry.resolve` 不做规范化。
- `path: str` — 端点路径(如 `"/api/order/order/orderDetail"`)。**不**做
  URL 编码/解码。

**为什么是 dataclass + frozen:**
- `dataclass` 自动生成 `__init__` / `__repr__` / `__eq__`,省样板代码。
- `frozen=True` 使实例不可变,Python `dict` 行为依赖键的 hash 不变;
  frozen 自动禁用 `__setattr__` / `__delattr__`,hash 也由 frozen 自动
  生成,等价于"可哈希的 namedtuple"。

**为什么用 dataclass 而不是 namedtuple:**
- dataclass 可读性更好(`EndpointKey(service="fin", method="POST",
  path="/x")` 比 `EndpointKey("fin", "POST", "/x")` 清楚)。
- 后续若想加方法(如归一化方法大小写),可以无痛扩展。

### 4.2 `BootstrapError`

```python
class BootstrapError(RuntimeError):
    """``warm()`` 失败时的聚合错误——多 service 异常合并抛出,便于一次性 fail-fast。"""
```

**设计动机:**
- `warm()` 会一次预热一批 service。如果 5 个 service 中 3 个失败,
  行为应该是 "一次抛 3 个错误",而不是"第 1 个失败就 return,后两个静默
  漏掉"。
- 用 `RuntimeError` 而不是 `ValueError`,因为 bootstrap 阶段失败是"运行
  时环境问题",不是"调用方参数错"。

---

## 5. 内部类 `_Registry`

> 进程级单例。线程安全、按需加载、拉式收集。

### 5.1 `__init__`

```python
def __init__(self) -> None:
    self._index: dict[EndpointKey, EndpointSpec] = {}
    self._loaded: set[str] = set()
    self._lock = threading.Lock()
```

**字段语义:**
- `_index: dict[EndpointKey, EndpointSpec]` — 已 collect 的所有 endpoint
  的主索引。`Key=(service, method, path)`,值是 `EndpointSpec` 实例。
  `_index` 在线程间共享,所有修改都在 `_lock` 内。
- `_loaded: set[str]` — 已成功 collect 的 service 名集合。用 set 是 O(1)
  查询。
- `_lock: threading.Lock` — 互斥锁。`resolve` / `warm` / `loaded_services`
  / `is_loaded` / `reset` 全部入口都拿这把锁。

**为什么用 `threading.Lock` 而不是 `RLock`:**
- 本类的所有"持锁"代码段都设计为"短小、不递归、不回调",`Lock` 性能更
  好(非可重入),不会出现误用导致死锁。

### 5.2 `_collect_locked(service: str) -> None`

```python
def _collect_locked(self, service: str) -> None:
    """import service 包,遍历模块命名空间,拉式收集所有 ``EndpointSpec`` 实例。

    匹配规则(对应 PR-2.3 P0-1 修复):
      - 用 ``type(attr).__name__ == "EndpointSpec"`` + ``hasattr(method/path)``
        判定(而不是 ``type(attr) is EndpointSpec``)。原因:测试场景下
        invariant 测试可能 del ``Plate.*`` 触发 spec 实例的 ``type()``
        指向"老"EndpointSpec 类,与当前模块里 ``EndpointSpec`` 不是同一
        对象 —— ``is`` / ``isinstance`` 会 False,但 ``__name__`` 仍然一致。
      - ``@final`` 保证没有继承链污染,``__name__`` 匹配足够安全。
    收集到 0 条时,主动 raise + 回滚 ``_loaded`` —— 不允许"空 service
    标 loaded"导致后续 collect 早退、错误被永久掩盖。
    """
```

**签名含义:** `_locked` 后缀是约定 — **调用方必须已持有 `self._lock`**
(本方法是 "锁内版本",供 `collect` / `resolve` / `warm` 等公开方法在
自己的 `with self._lock:` 块内调用)。

**算法步骤:**

1. **幂等性检查**:如果 `service in self._loaded`,直接 return(已 collect
   过的 service 不会被重新 import 触发重复副作用)。
2. **目录名解析**:`dir_name = resolve_dir_name(service)`。这一步把
   `"tidb-test-service"` 这类名字转成 `"tidb_test_service"`,若不在
   alias 表里则抛 `ValueError`。
3. **缓存失效**:`importlib.invalidate_caches()` — 处理"开发期改文件
   后 Python 仍 import 旧版本"问题。无副作用,可放心调。
4. **动态 import**:`module = importlib.import_module(f"Plate.{dir_name}")`。
   失败 → `LookupError`(wrap `ImportError`,附上更有用的错误信息)。
5. **遍历命名空间**:`for attr in vars(module).values()`。
6. **类型过滤**:`type(attr).__name__ == "EndpointSpec"` — 见下面"为什么
   用 `__name__` 而不是 `is`"。
7. **形态校验**:`getattr(attr, "method", None)` 和 `getattr(attr, "path",
   None)` 都要真值,否则跳过。
8. **构建索引 key**:`EndpointKey(service, method, path)`。
9. **写入 `_index`**:`self._index[key] = attr`(同 key 后写覆盖前写)。
10. **零条数防御**:如果 `collected == 0`,**主动 raise** `LookupError`
    且不把 service 加进 `_loaded`(回滚)。这是为了避免"空 service 标
    loaded"导致后续 collect 早退、错误被永久掩盖。
11. **标记已加载**:`self._loaded.add(service)`。

**为什么用 `type(attr).__name__ == "EndpointSpec"` 而不是 `type(attr) is
EndpointSpec`:**

```text
测试场景下 invariant 测试可能 del ``Plate.*`` 触发 spec 实例的 ``type()``
指向"老"EndpointSpec 类,与当前模块里 ``EndpointSpec`` 不是同一
对象 —— ``is`` / ``isinstance`` 会 False,但 ``__name__`` 仍然一致。
```

具体说:Python 的 `del sys.modules["Plate"]` 会清除模块缓存,但已存在的
`EndpointSpec` 实例仍指向"老"的类对象(原 `class EndpointSpec` 的代码对象)。
当 `_collect_locked` 重新 `importlib.import_module("Plate.fin")`,会创建
一个"新"的 `EndpointSpec` 类对象。此时 `_index` 里的老实例的 `type()`
是新老两个不同的对象,`is` 比较是 False。但**类对象的 `__name__` 属性**是
字符串,内容都是 `"EndpointSpec"`,所以 `__name__` 比较仍能匹配。

**`@final` 的角色:** `EndpointSpec` 用 `@final` 装饰,语法上禁止继承。
所以"所有 `__name__ == "EndpointSpec"` 的对象"在程序里只有"老 / 新"
两类,**不可能**有一个"继承自 EndpointSpec 的子类"被错误收集进来。
两者结合,既解决了 invariant 测试的"老 class"问题,又防住了继承污染。

**零条数 raise + 回滚:**

> "不允许"空 service 标 loaded"导致后续 collect 早退、错误被永久掩盖。"

如果不 raise 且标 loaded,后续 `resolve` 会以为这个 service 已经处理过,
直接走到 "key not in _index" 分支报 "endpoint not found",作者看到错误
会以为是 endpoint 写错,实际上根本是"这个 service 子包没有任何
EndpointSpec" — 一个完全不同的根因。**主动 raise + 不标 loaded** 强制
让"空 service"在第一次 collect 就暴露,作者从错误信息里立刻知道要查
"service 名拼错" / "endpoints.py 未导出 spec" / "模块结构被外部破坏"。

**抛错类型选择:**
- `ImportError` 被 `except ImportError as e` 捕获后 `raise LookupError(...)
  from e` — 用 `LookupError` 是因为这是"找不到 spec"语义,不是"模块
  编码问题"。`from e` 保留原始堆栈供调试。

### 5.3 `_check_no_duplicate_paths_locked(service: str) -> None`

```python
def _check_no_duplicate_paths_locked(self, service: str) -> None:
    """同 service 内 (method, path) 唯一性检查(内部一致性)。

    实际去重由 ``_index`` 的 dict 语义保证:同 key 会被后者覆盖。
    此方法作为契约:在 service collect 完后跑一次,发现"被覆盖"则报错。
    留给 ``warm()`` 在断言模式下调用;单 ``collect`` 不强制(允许同 path
    在不同 service 下出现)。
    """
```

**算法:**
1. 遍历 `_index`,把每个 key 拆出 `(method, path)` 组成 `sub_key`,
   value 是 "第一次出现这个 sub_key 的 service 名"。
2. 第二次见到同 sub_key:如果两次的 service 相同,说明**同 service 内**
   `(method, path)` 撞了 → raise `ValueError`。
3. 不同 service 的同 sub_key 不算错(因为 `EndpointKey` 含 service,
   不会真的在 `_index` 撞)。

**为什么有这个方法:**
- `_index` 的 dict 语义本身保证唯一性(同 key 后写覆盖前写),所以**实际
  没有"撞 path"的可能性**。
- 但**同 service 写两个相同 `(method, path)` 的 EndpointSpec** 几乎
  肯定是 author 笔误(比如复制粘贴忘改 path)。这个方法作为弱提示。

**为什么"留给 `warm()` 在断言模式下调用":**
- `collect` 单独调用是"按需",可能只 collect 一个 service,此时 `_index`
  还没装其他 service 的内容,做"跨 service 查重"没意义。
- `warm()` 是一次性预热,正是跑这种"全量一致性校验"的合适时机。

### 5.4 `collect(service: str) -> None` — 公开 API

```python
def collect(self, service: str) -> None:
    """import 该 service 包,拉式收集所有 ``EndpointSpec`` 实例。幂等。"""
    with self._lock:
        self._collect_locked(service)
```

**调用方契约:** 业务代码可自由调,不需要关心锁。**幂等** — 多次调
同一个 service 不会重复 import(由 `_collect_locked` 里的 `if service
in self._loaded: return` 兜底)。

**使用场景:**
- 明确"我接下来要用 fin 的所有 endpoint",希望预热。
- 测试间隔离(配合 `reset()`)。

### 5.5 `resolve(service: str, method: str, path: str) -> EndpointSpec`

```python
def resolve(self, service: str, method: str, path: str) -> EndpointSpec:
    """按 ``(service, method, path)`` 拿 ``EndpointSpec``。首次访问触发 collect。

    整个 collect + dict 读取都在同一把锁内:避免并发的 collect 修改
    ``_index`` 时,本线程在锁外迭代 ``_index`` 触发
    ``RuntimeError("dictionary changed size during iteration")``。
    ``EndpointSpec`` 是 ``frozen=True`` 的 dataclass,锁内取出后到锁外用
    是安全的(无 TOCTOU 风险)。
    """
    key = EndpointKey(service, method, path)
    with self._lock:
        self._collect_locked(service)
        if key not in self._index:
            registered = sorted(
                f"  {k.method} {k.path}" for k in self._index if k.service == service
            )
            hint = (
                f"\n请在 Plate/{resolve_dir_name(service)}/ 下建对应 endpoint 文件,"
                f"或修正 scenario 中 path 的拼写。"
            )
            raise LookupError(
                f"[Plate] 未找到 {service} {method} {path}。\n"
                f"该 service 已注册端点:\n" + "\n".join(registered) + hint
            )
        return self._index[key]
```

**核心行为:**
1. 构造 key。
2. **取锁**。
3. 在锁内调 `_collect_locked(service)` — 第一次访问自动 import 并收集。
4. 在锁内查 `_index` — 因为是同一把锁内,没有"被并发改"的竞态。
5. 命中 → 返回 spec(**锁内返回**,调用方拿到的是 immutable 实例,锁外用安全)。
6. 未命中 → 构造一个**带修复建议**的错误信息,raise `LookupError`。

**为什么"collect + dict 读取"必须在同一锁内:**

> 避免并发的 collect 修改 ``_index`` 时,本线程在锁外迭代 ``_index`` 触发
> ``RuntimeError("dictionary changed size during iteration")``。

Python 的 `dict` 在迭代过程中被并发修改会抛这个错。两种典型坑:
- 线程 A:在 `for k in self._index` 迭代;线程 B:在 `self._index[key] =
  attr` 写入。**会报这个错**。
- 线程 A:在 `key in self._index` 后准备 `self._index[key]`,线程 B 写入
  后再读;此时 key 一定在,但读到的是 B 写的新值,这是**安全**的(只要
  我们**不依赖值不变**)。

本方法**只在锁内读**一次 `_index[key]`,锁外不再访问。所以即使有 TOCTOU
窗口(`if key not in self._index` 到 `return self._index[key]` 之间),
也没事 — 因为整段都在锁内。

**`EndpointSpec` 锁外用安全 — 为什么:**
- `EndpointSpec` 是 `@final @dataclass(frozen=True)`,实例不可变。
- 取出后**只读**,所以并发线程改 `_index` 不会让已取出的实例内容变化。
- Python 引用计数 + GIL 也保证"取出的实例对象本身"不会被 free。

**错误信息的"作者友好":**

```python
f"[Plate] 未找到 {service} {method} {path}。\n"
f"该 service 已注册端点:\n" + "\n".join(registered) + hint
```

`registered` 是同 service 下**所有已注册端点**的列表(排序后),让作者一眼
看出"我打错了哪个字符"。"hint" 给出修复建议(在哪建文件 / 改 scenario)。

### 5.6 `warm(services: list[str]) -> list[EndpointSpec]`

```python
def warm(self, services: list[str]) -> list[EndpointSpec]:
    """共用的预热逻辑。``contract check`` 与 mock server 启动都走这里。

    返回该批 service 收集到的全部 ``EndpointSpec`` 实例(顺序按
    ``_index`` 插入序);收集过程中任一 service 失败,抛 ``BootstrapError``
    并附所有错误(便于作者一次性看到全部问题)。

    整个 collect + 列表构造都在锁内,避免锁外迭代 ``_index`` 时被
    并发的 collect 触发 ``"dictionary changed size"``。
    """
    issues: list[str] = []
    collected_specs: list[EndpointSpec] = []
    with self._lock:
        for s in services:
            try:
                self._collect_locked(s)
            except Exception as e:
                issues.append(f"  - {s}: {e}")
        if issues:
            raise BootstrapError(
                f"[Plate] 预热失败,以下 service 异常:\n" + "\n".join(issues)
            )
        for k, spec in self._index.items():
            if k.service in services:
                collected_specs.append(spec)
    return collected_specs
```

**核心行为:**
1. 一次性预热一批 service(用于"contract check"和"mock server 启动")。
2. **聚合所有错误**到一个 `BootstrapError`,不"第一个失败就 raise"。
   这是为了作者改完一个错,再跑还是失败,再改... 的痛苦循环。
3. 锁内迭代 `_index` 收集结果(`collected_specs`),锁外用。

**为什么用 `in services` 而不是 set:**
- `services` 长度通常很小(< 10),list 的 `in` 操作 O(n) 没问题。
- list 有序,理论上可预测性强;但本方法的 spec 输出顺序实际上是"按
  `_index` 插入序",与 `services` 顺序无关。

**为什么 `for k, spec in self._index.items()` 在锁内:**
- 同样是为避免 "dictionary changed size during iteration"。
- 假设 warm 跑的时候,另一个线程又触发了某个 service 的 collect(比如
  scenario 解析时调了 `resolve` 触发 collect),_index 就会被并发修改。

### 5.7 `loaded_services() -> list[str]`

```python
def loaded_services(self) -> list[str]:
    """返回已 collect 的 service 列表(快照,用于 introspection / 报告)。"""
    with self._lock:
        return sorted(self._loaded)
```

**用途:**
- introspection(测试 / 调试时查看"我已经加载了哪些 service")。
- 报告(contract check 输出报告时,告诉用户"我处理了哪些 service")。

**为什么返回 sorted 列表:** 给调用方一个稳定的输出,便于做"diff"。

### 5.8 `is_loaded(service: str) -> bool`

```python
def is_loaded(self, service: str) -> bool:
    with self._lock:
        return service in self._loaded
```

**用途:** 测试断言("service fin 应当被预热了")。

**为什么需要显式取锁:** 读 `_loaded` 集合本身在 CPython 是 GIL 保护的
(单步操作),但保持"所有 `_loaded` 访问都持锁"是规约,避免某天有人
把 `is_loaded` 改成"读 + 计算"后引入 bug。

### 5.9 `reset() -> None`

```python
def reset(self) -> None:
    """清空 index 与 loaded 集合。**仅供测试使用** —— 生产代码不应调。"""
    with self._lock:
        self._index.clear()
        self._loaded.clear()
```

**为什么"仅供测试使用":**
- 测试间需要隔离("上一个测试 collect 的 service 不能影响下一个测试")。
- 生产代码调 reset 会**清掉已 collect 的所有 spec**,后续 `resolve` 会
  重新 import(可能慢 + 副作用),且**丢失**之前 collect 时跑的零条数校验。
- 文档里明确写 "仅供测试使用",review 时会拒绝生产路径的 reset 调用。

---

## 6. 全局单例

```python
registry = _Registry()
```

**为什么用模块级单例而不是 DI 注入:**
- 测试 / scenario 启动时已经默认存在一个"系统级"registry 概念。
- 单例让"业务代码调 `registry.resolve(...)`" 与 "被测代码调
  `registry.resolve(...)`" 看到的是同一份状态 — 不会出现"业务代码
  collect 了 fin,被测代码看不到"的诡异行为。
- 测试隔离用 `reset()`(而非新建 registry 实例)— 简单且不会污染调用方
  代码的 "from Plate import registry" 习惯。

---

## 7. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `EndpointKey` | dataclass(frozen=True) | `from Plate import EndpointKey` |
| `BootstrapError` | exception | `from Plate import BootstrapError` |
| `registry` | `_Registry` 单例 | `from Plate import registry` |

`Plate/__init__.py` 里写的:

```python
from .core import BootstrapError, registry

__all__ = ["registry", "BootstrapError"]
```

**为什么 `EndpointKey` 不在 `__all__`:**
- 业务代码很少需要直接构造 `EndpointKey`(`registry.resolve` 帮你包好)。
- 内部模块(`server/router.py` 等)用 `from Plate.core import
  EndpointKey`,绕开 `__all__` 即可,不影响 API 稳定性。

---

## 8. 调用方典型代码示例

```python
# 1. 普通场景:按需 resolve
from Plate import registry
spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
print(spec.request.__name__)  # "OrderDetailRequest"

# 2. 显式预热(后续 resolve 不会再触发 import)
from Plate import registry
registry.collect("fin")
print(registry.loaded_services())  # ["fin"]

# 3. 一次性预热多个 + 拿到所有 spec
from Plate import registry
specs = registry.warm(["fin"])
print(len(specs))  # 31

# 4. 错误处理:endpoint 不存在
try:
    registry.resolve("fin", "POST", "/api/wrong/path")
except LookupError as e:
    print(e)  # 列出已注册端点 + 修复建议

# 5. 测试隔离
from Plate import registry
def test_xxx():
    registry.reset()
    # ... 测试体 ...
```

---

## 9. 不变量总结(本模块承诺的不变式)

1. **零侵入**:`import Plate` 不会触发任何 service 子包的 import。
2. **幂等 collect**:对同一 service 多次 `collect` 副作用一致。
3. **按需加载**:未引用的 service 一个字节都不 import。
4. **线程安全**:所有 `_index` / `_loaded` 访问在锁内,不会触发
   `dictionary changed size`。
5. **零条数 fail-fast**:空 service 在 collect 阶段就抛错,不会留下
   "标 loaded 但实际为空"的脏状态。
6. **to_dict 键稳定**:同 spec 多次 `to_dict` 产物 byte-equal(由
   `EndpointSpec` 保证,见 spec.md)。
7. **错误信息作者友好**:resolve 失败时列出"同 service 已注册端点"
   + 修复建议。

---

## 10. 历史踩坑与防御

| 坑 | 防御 |
|---|---|
| 用 `type(attr) is EndpointSpec` 匹配,invariant 测试 del 模块后失效 | 改用 `type(attr).__name__ == "EndpointSpec"` + `@final` 保证 |
| resolve 在锁内 collect,锁外迭代 → `RuntimeError` | collect + dict 读取/迭代全在锁内 |
| 空 service 标 loaded → 错误被永久掩盖 | 零条数主动 raise + 不标 loaded |
| warm 第一个失败就 raise,后续错误看不到 | 用 `issues` list 聚合,最后 `BootstrapError` 一次性 raise |
| `dict` 插入顺序影响 to_dict 产物 | 序列化时显式 sort(见 serialization.md) |
