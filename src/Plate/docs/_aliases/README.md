# _aliases 模块(`Plate/_aliases.py`)

> 本文档详细描述 `Plate/_aliases.py` 中的**每一个公开/内部常量、函数**,
> 以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模块的所
> 有行为细节与设计动机。

---

## 1. 模块定位

`_aliases.py` 是 Plate 子系统的**service 名 → 合法 Python 目录名**反
向映射层。它解决的核心问题:

> **业务上的 service 标识(如 `"tidb-test-service"`)可能不是合法的
> Python 包名(连字符、数字开头等),但 `importlib.import_module` 要求
> 是合法包名。需要一个集中维护的映射表。**

它暴露一个核心 `resolve_dir_name` 函数 + 一个集中维护的字典
`SERVICE_ALIASES`。

下划线开头表示"模块私有",但**实际被 `core.py` 直接 import 使用** —
这是惯例违反,理由见下。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
service 名 → 合法 Python 目录名 的反向映射。

本表是 service 命名不一致时的唯一兜底。任何 service 名变更,
先改这里(而不是改目录名 + 所有 scenario)。

约定(主路径):service 名本身就是合法 Python 标识符(字母数字下划线、
不以数字开头、不是关键字)→ 直接用作目录名。

兜底(辅路径):service 名含连字符、点、数字开头等 Python 标识符不
允许的字符 → 在 SERVICE_ALIASES 中显式声明映射。

维护规则:
  1. 仅在 service 名不符合 Python 包名规范时,才在 SERVICE_ALIASES 加一行
  2. value 必须是合法 Python 包名(以供 importlib.import_module 使用)
  3. 修改本表前请确认:scenario 侧 service 字段未改、目录名未改 —— 本表
     是连接"真实 service 标识"与"Python 包名"的唯一桥梁
```

---

## 3. 依赖关系

```python
import keyword
```

**为什么这么依赖:**
- `keyword.iskeyword(s)` — 防止 service 名是 Python 关键字(如
  `"class"` / `"return"` 等),关键字虽然 `isidentifier()` 是 True,
  但**作为包名是禁止的**(importlib 行为未定义)。

**重要的反向依赖约束:**
- `_aliases.py` **不** import 任何其他 Plate 子模块。
- 这是"叶子工具" — 可被 `core` 无副作用引用。

---

## 4. 模块级常量:`SERVICE_ALIASES`

```python
SERVICE_ALIASES: dict[str, str] = {
    # "tidb-test-service": "tidb_test_service",  # 示例:连字符 → 下划线
    # "3pl-service": "three_pl_service",        # 示例:数字开头走 alias
}
```

**字段语义:**
- 集中维护的 alias 表(按 service 名字母序)。
- 键 — 真实 service 标识(可能含连字符、点、数字开头等)。
- 值 — 合法 Python 包名(目录名 = import 路径的最后一段)。

**为什么字典为空(目前):**
- 当前所有 service 都符合 Python 标识符规范(都是 `"fin"` / 未来
  `"auth"` / `"order"` 等)。
- 字典保持为空,留待"出现不合规 service 名"时启用。

**注释里有示例:**
- `"tidb-test-service": "tidb_test_service"` — 连字符 → 下划线。
- `"3pl-service": "three_pl_service"` — 数字开头走 alias(因为
  Python 标识符不能数字开头)。

**为什么"主路径 = 不走 alias":**
- 90% 情况下 service 名是合法标识符,直接用。
- alias 只在"业务标识与 Python 包名不一致"时启用,集中维护可避免
  散落各处的 if/else。

---

## 5. 核心函数:`resolve_dir_name`

```python
def resolve_dir_name(service: str) -> str:
    """解析 service 名 → 目录名(可作 import 路径最后一段)。

    解析规则(按优先级):
      1. 是合法 Python 标识符(且不是关键字)→ 直接返回
      2. 在 SERVICE_ALIASES 中 → 返回 alias
      3. 都不行 → fail-fast 抛 ValueError

    Args:
        service: scenario 中引用的 service 标识

    Returns:
        合法 Python 包名,可拼到 ``Plate.`` 之后作 import 路径

    Raises:
        ValueError: service 名不符合 Python 包名规范,且不在 alias 表中
    """
    if not isinstance(service, str) or not service:
        raise ValueError(
            f"[Plate] service 名必须是非空字符串,实际 {type(service).__name__}: {service!r}"
        )
    if service.isidentifier() and not keyword.iskeyword(service):
        return service
    if service in SERVICE_ALIASES:
        alias = SERVICE_ALIASES[service]
        if not alias.isidentifier() or keyword.iskeyword(alias):
            raise ValueError(
                f"[Plate] SERVICE_ALIASES[{service!r}] = {alias!r} 不是合法 Python 包名。"
                f"alias 值必须满足 isidentifier() 且不是 Python 关键字。"
            )
        return alias
    raise ValueError(
        f"[Plate] service 名 {service!r} 不符合 Python 包名规范,"
        f"也不在 SERVICE_ALIASES 中。请在 Plate/_aliases.py 添加映射后重试。\n"
        f"  提示:连字符用下划线替代(如 'tidb-test-service' → 'tidb_test_service'),"
        f"数字开头用英文单词替代(如 '3pl-service' → 'three_pl_service')。"
    )
```

### 5.1 算法步骤详解

**Step 1: 入参校验**

```python
if not isinstance(service, str) or not service:
    raise ValueError(...)
```

- `isinstance(service, str)` — 必须字符串。
- `not service` — 必须非空(`""` 是空字符串)。
- 任一为真 → `ValueError`(带实际类型 + 值,便于调试)。

**为什么用 `ValueError` 而不是 `TypeError`:**
- 与 `PlateVersion.parse` 同源 — 业务上"非字符串"几乎都是值错(调用
  方传 None / 数字等),统一 `ValueError` 让 try/except 简单。

**Step 2: 主路径(直接走)**

```python
if service.isidentifier() and not keyword.iskeyword(service):
    return service
```

- `service.isidentifier()` — 满足 Python 标识符规范(字母数字下划线、
  不以数字开头)。
- `not keyword.iskeyword(service)` — 不是 Python 关键字。
- 同时满足 → 直接返回(无需查 alias)。

**为什么"identifier 但不是 keyword":**
- Python 关键字(`class` / `return` 等)虽然 `isidentifier()` 是 True,
  但作为包名 import 时行为未定义(可能 importlib 直接抛
  `ModuleNotFoundError`,或更糟糕的"以关键字为名建包"导致的 import
  行为奇怪)。
- 显式 `not keyword.iskeyword` 拦截,让调用方明确收到 ValueError
  而非 import 时的神秘错误。

**Step 3: 辅路径(查 alias)**

```python
if service in SERVICE_ALIASES:
    alias = SERVICE_ALIASES[service]
    if not alias.isidentifier() or keyword.iskeyword(alias):
        raise ValueError(
            f"[Plate] SERVICE_ALIASES[{service!r}] = {alias!r} 不是合法 Python 包名。"
            ...
        )
    return alias
```

- 查表 — 命中 → 取 alias。
- **alias 自身也必须合法**(`isidentifier()` 且 `not iskeyword`)。
  否则 `ValueError`(这是"作者在 alias 表里写错"的内错,不应静默
  通过)。
- alias 合法 → 返回。

**为什么 "alias 自身也要合法":**
> alias 值必须满足 isidentifier() 且不是 Python 关键字。

这是**第二层防御** — 即使作者在 alias 表里写了 `"foo-bar"` 这样的
值,这里也拦截,不让错误蔓延到 importlib 阶段(importlib 阶段的错
误信息对调用方非常不友好)。

**Step 4: fail-fast**

```python
raise ValueError(
    f"[Plate] service 名 {service!r} 不符合 Python 包名规范,"
    f"也不在 SERVICE_ALIASES 中。请在 Plate/_aliases.py 添加映射后重试。\n"
    f"  提示:连字符用下划线替代(如 'tidb-test-service' → 'tidb_test_service'),"
    f"数字开头用英文单词替代(如 '3pl-service' → 'three_pl_service')。"
)
```

- 三种情况到这里:
  1. service 名不合法,alias 表里没有。
  2. service 名合法但 `iskeyword()` 是 True(很少见)。
  3. service 名合法,alias 表里没有(几乎不可能,因为合法就直接
     返回了)。
- 实际**绝大多数**情况是情况 1。
- 错误信息**作者友好**:
  - 说"在哪改"(`Plate/_aliases.py`)。
  - 给出"怎么改"的示例(连字符 → 下划线 / 数字开头 → 英文单词)。

**为什么不 fallback 到 "把非法字符替换成下划线":**
- 静默替换会让作者失去"我命名错误"的反馈(下次改 scenario 还会再
  撞)。
- 强制让作者**显式声明映射**,把所有"业务名 → Python 名"的对应关
  系集中到一个文件,可审计。

### 5.2 边界情况

- `service=None` → `ValueError`(Step 1)。
- `service=""` → `ValueError`(Step 1)。
- `service="fin"`(合法标识符)→ 直接返回 `"fin"`(Step 2)。
- `service="class"`(Python 关键字)→ `ValueError`(Step 4,因为
  `keyword.iskeyword` 拦截)。
- `service="tidb-test-service"`(连字符)→ `ValueError`(Step 4,如
  果没在 alias 表里)。
- `service="3pl-service"`(数字开头)→ `ValueError`(Step 4)。

---

## 6. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `SERVICE_ALIASES` | `dict[str, str]`(集中维护的映射表) | 实际在 `Plate/_aliases.py` 顶部直接维护 |
| `resolve_dir_name` | function | `from Plate._aliases import resolve_dir_name` |

模块底部:

```python
# 注意:本文件没有 __all__ 声明
# 因为模块级别无显式 __all__ = [...],但 Python 默认导出所有非下划线开头的名字
```

(实际 `_aliases.py` 没有 `__all__` 声明,`SERVICE_ALIASES` 和
`resolve_dir_name` 都通过 `from ._aliases import` 直接访问。)

---

## 7. 调用方典型代码示例

```python
# 1. 主路径(合法标识符)
from Plate._aliases import resolve_dir_name
print(resolve_dir_name("fin"))  # "fin"

# 2. 辅路径(命中 alias)
# 假设 SERVICE_ALIASES = {"tidb-test-service": "tidb_test_service"}
print(resolve_dir_name("tidb-test-service"))  # "tidb_test_service"

# 3. 失败
try:
    resolve_dir_name("not-valid-identifier")
except ValueError as e:
    print(e)  # "service 名 'not-valid-identifier' 不符合 Python 包名规范,
             #  也不在 SERVICE_ALIASES 中..."

# 4. 配合 registry.collect
from Plate._aliases import resolve_dir_name
import importlib

service = "fin"
module = importlib.import_module(f"Plate.{resolve_dir_name(service)}")
```

---

## 8. 不变量总结(本模块承诺的不变式)

1. **不修改 service 名**:主路径直接返回入参,无副作用。
2. **集中映射**:所有"业务名 → Python 名"的对应关系在
   `SERVICE_ALIASES` 一处维护。
3. **fail-fast**:服务名不合法 + 没在 alias 表 → `ValueError`(带
   修复提示),不让错误蔓延到 importlib 阶段。
4. **alias 自身也合法**:第二层防御,作者写错 alias 时立即暴露。
5. **关键字拦截**:`isidentifier()` 是 True 但 `keyword.iskeyword`
   也是 True 时 fail-fast,避免 importlib 阶段的神秘错误。

---

## 9. 设计权衡

| 决策 | 取舍 |
|---|---|
| 主路径 = `isidentifier()` 直接返回 | 90% 场景无开销;无需查表 |
| 辅路径 = 集中 alias 表 | 审计简单;不会出现"散落各处的 if/else 转换" |
| alias 表当前为空 | YAGNI — 真要不合规名时再加 |
| 不 fallback 静默替换 | 强制作者显式表态,所有映射集中可审计 |
| `keyword.iskeyword` 拦截 | 防止 `service="class"` 这种"看似合法实际危险"的情况 |
| 下划线开头但跨模块 import | 历史例外 — 业务代码不应直接调用,应通过 `core.collect` 间接使用 |
