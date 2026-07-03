# path_resolver 模块(`Plate/path_resolver.py`)

> 本文档详细描述 `Plate/path_resolver.py` 中的**每一个公开/内部类型、
> 函数、方法**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整
> 解释该模块的所有行为细节与设计动机。

---

## 1. 模块定位

`path_resolver.py` 是 Plate 子系统的**逻辑 schema 路径解析器**。它解
决的核心问题:

> **给一个 Pydantic 模型树和一个点分路径(如 `"a.b.c"`),如何静态地走
> 到路径的终点类型?遇到 `list[T]` / `dict[str, V]` / `Optional[T]`
> 这类"容器型"注解时,该如何处理?**

它暴露的核心是 `resolve_logical_path` 函数 + `Resolved` 结果类。是
`FieldBinding` 静态校验(PR-D2)的唯一复杂依赖。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
逻辑 schema 路径解析器(PR-D1 / PLATE_DESIGN §2.2 + §3.4(d))。

职责:解析形如 ``"a.b.c"`` 的点分路径,在给定 Pydantic 模型树中找到终点类型。
本解析器是 ``FieldBinding`` 静态校验(PR-D2)的唯一复杂依赖,故独立 PR、单测锁死行为。

设计要点(对应 PLATE_DESIGN §2.2 + §3.4(d)):
  * **透明穿过 list[X]** — 进入 ``X``,不带下标(91% 真值血缘穿过 list)
  * **透明穿过 dict[str, V]** — 进入 ``V``,不带具体键(币种/业务维度键)
  * **透明穿过 Optional[T] / T | None** — 进入 ``T``
  * **透明穿过 Annotated[T, ...]** — 进入 ``T``
  * **Any 区域降级** — 遇 Any 标记 ``hit_any=True``,**不**报错(无法证伪)
  * **Union[A, B, ...] 多态** — 解析器无法静态选,返回 ``error``
  * **空路径** = 根类型本身

业务价值:
  * PR-D2 ``FieldBinding`` 静态校验:每条 ``field_path`` 必须能在本接口
    ``request`` 模型树中解析到
  * PR-D4 referential integrity check:``source_field_path`` 跨端点对照
  * Phase 3 Plate-MCP:binding 查询时验证路径
  * Phase 4 CT 主动保活:drift 检测对照 schema 变化
```

---

## 3. 依赖关系

```python
from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
```

**为什么这么依赖:**
- `dataclasses.dataclass` — 构造 `Resolved` 不可变结果类。
- `typing.Any` / `Union` / `get_args` / `get_origin` — 类型注解的"拆
  卸"工具:
  - `get_origin(annotation)` — 获取泛型的"原始类型"(如 `list` /
    `dict` / `Union`)。
  - `get_args(annotation)` — 获取泛型的"类型参数"(如 `[T]` 或
    `[K, V]`)。
- `pydantic.BaseModel` — 类型标注(本解析器只走 BaseModel 模型树)。

**重要的反向依赖约束:**
- `path_resolver.py` **不** import `spec` / `binding` / `core` /
  `facade` / `server` / `api_doc` / 任何 service 子包。
- 这保证 path_resolver 是"叶子工具",可被 binding 校验、MCP 服务、
  CT 主动保活等多个上下文无副作用引用。

---

## 4. 解析结果类:`Resolved`

```python
@dataclass(frozen=True)
class Resolved:
    """逻辑路径解析结果。

    字段语义:
      target_type: 路径终点类型;None = 不可解析(Any 区域或出错)
      hit_any: 路径是否穿过 Any(软提示 — Any 区域无法证伪,降级放行)
      path: 原路径(诊断用)
      error: 不可解析原因(诊断用);None = 无错

    状态空间:
      (target_type=T,  hit_any=False, error=None)  → 严格解析成功
      (target_type=None, hit_any=True, error=None) → Any 区域软降级
      (target_type=None, hit_any=False, error="…")  → 硬错误(路径错/类型不支持)
    """

    target_type: type | None
    hit_any: bool
    path: str
    error: str | None
```

**字段详解:**

- `target_type: type | None` — 路径终点类型。`None` 表示"不可解析"
  (Any 区域或硬错)。
- `hit_any: bool` — 路径是否穿过 `Any`。是 `True` 时表示"路径走入了
  一个 `Any` 标注的字段,无法静态证伪" — 这是软降级,不是错。
- `path: str` — 原路径(诊断用 — 错误信息可以引用)。
- `error: str | None` — 不可解析原因(诊断用)。`None` = 无错。

**为什么三态空间 `(target_type, hit_any, error)`:**

| 状态 | 含义 | 业务处理 |
|---|---|---|
| `(T, False, None)` | 严格解析成功 | binding 校验通过 |
| `(None, True, None)` | Any 区域软降级 | binding 校验"放行 + 警告"(因为 Any 区域无法证伪) |
| `(None, False, "…")` | 硬错误(路径错/类型不支持) | binding 校验失败 |

**为什么需要 `hit_any` 而不是只有"成功 / 失败":**
- `Any` 是 Python 类型系统的"黑洞" — 一旦 `model.some_field: Any`,
  你无法静态知道 `some_field` 下面有什么。
- 路径穿过 `Any` 后,继续走路径是"基于未验证假设",**严格说**应该
  报错。但作者可能故意用 `Any` 表示"我知道这里不严谨,放行吧"。
- 显式 `hit_any=True` 给调用方一个"软提示",让上层决定是 fail-fast
  还是 warn-and-continue。

**为什么是 `frozen=True`:** 解析结果是一次性快照,无继承需求;`frozen`
让结果可哈希、可在多线程间安全共享。

---

## 5. 公开 API:`resolve_logical_path`

```python
def resolve_logical_path(
    root: type[BaseModel],
    path: str,
) -> Resolved:
    """在 ``root`` 模型树中按 ``path``(点分)解析终点类型。

    解析规则(对应 PLATE_DESIGN §2.2 表格):
      * 空路径 = 根类型本身
      * BaseModel 节点:进入 ``model_fields[name]``
      * ``list[T]`` / ``List[T]``:进入 ``T``
      * ``dict[str, V]`` / ``Dict[str, V]``:进入 ``V``
      * ``Optional[T]`` / ``T | None`` / ``Union[T, None]``:进入 ``T``
      * ``Annotated[T, ...]`` / ``Final[T]``:进入 ``T``
      * ``Union[A, B, ...]``(非 Optional):返回 ``error``(多态不可静态选)
      * ``Any``:标记 ``hit_any=True``,**不**报错(软降级)
      * 字段不存在 / 期望 BaseModel 收到非 BaseModel:返回 ``error``
    """
```

**输入:**
- `root: type[BaseModel]` — 入口 Pydantic 模型类。
- `path: str` — 点分路径(如 `"data.audit_id"`)。空字符串 = 根类型
  本身。

**输出:** `Resolved` 实例。

### 5.1 算法步骤详解

#### 5.1.1 空路径 = 根

```python
if path == "":
    return Resolved(target_type=root, hit_any=False, path=path, error=None)
```

**为什么空路径合法:** 业务场景需要"绑定整个 body"(`from_path=()`),
而 `from_path` 转 str 是 `""`(空字符串拼接)。`FieldBinding` 校验可
以传 `from_path=""` 来代表"整个响应"。

#### 5.1.2 拆分

```python
parts = path.split(".")
current: Any = root
```

**为什么用 `"."` 切分:** 业务惯例。`data.audit_id` 比 `/data/audit_id`
或 `data/audit_id` 更紧凑(在 JSON 里 `.` 不需要转义)。

#### 5.1.3 逐步解析

```python
for part in parts:
    # 3a. 期望 BaseModel,实际不是 → 硬错
    if not _is_basemodel_subclass(current):
        return Resolved(
            target_type=None,
            hit_any=False,
            path=path,
            error=(...),
        )
    # 3b. 字段不存在 → 硬错
    if part not in current.model_fields:
        return Resolved(
            target_type=None,
            hit_any=False,
            path=path,
            error=(...),
        )
    # 3c. 进入字段
    annotation = current.model_fields[part].annotation
    current = _unwrap(annotation)
    # 3d. 遇 Any → 软降级
    if current is Any:
        return Resolved(
            target_type=None, hit_any=True, path=path, error=None
        )

return Resolved(target_type=current, hit_any=False, path=path, error=None)
```

**3a — 期望 BaseModel,实际不是:**

> 当 `current` 是 `int` / `str` / `list` 等"叶子类型"时,试图在它
> 下面找 `part` 是无意义的(叶子类型没有字段)。

**为什么 `isinstance(current, type) and issubclass(current, BaseModel)`:**
- `current` 可能是任意类型(从 `_unwrap` 出来的 `int` / `str` /
  `list` / `dict` / `Union` / `Any` / 嵌套 Pydantic 类)。
- 只有 Pydantic 类才有 `model_fields`;其他类型没有。

**3b — 字段不存在:**

> Pydantic 模型在静态阶段(类对象)有 `model_fields`(一个 dict)。
> 业务代码写的字段名拼错,会到这里被检测到。

**为什么 `part not in current.model_fields` 而不是 `getattr`:**
- `getattr(current_instance, part, default)` 是"实例层",不能用于
  "类层"字段。
- Pydantic v2 用 `model_fields`(类属性 dict)暴露字段元数据。

**3c — 进入字段并解包:**

```python
annotation = current.model_fields[part].annotation
current = _unwrap(annotation)
```

- `current.model_fields[part]` 是 `FieldInfo` 对象(Pydantic v2)。
- `FieldInfo.annotation` 是字段的原始类型注解(可能是 `str` /
  `int` / `list[X]` / `Optional[X]` / `Union[A, B]` / `Any` 等)。
- `_unwrap(annotation)` 解包泛型,见 §6。

**3d — 遇 Any 软降级:**

```python
if current is Any:
    return Resolved(target_type=None, hit_any=True, path=path, error=None)
```

**为什么 `current is Any` 而不是 `current == Any`:**
- `Any` 是单例,`is` 比较更严格(避免作者误用 `==` 时被 `__eq__` 兜
  底)。
- `is None` 是 Python 惯例(`Any` 类似 `None` 这种"单例 sentinel")。

**为什么 `hit_any=True` 时 `error=None`:**
- "无法证伪"不是"错"。错误信息会让 author 误以为 binding 真的坏了。
- 上层(PR-D2 校验)看到 `hit_any=True` 时,可以选择"放行 + 警告"而
  不是"硬错"。

### 5.2 边界情况

- **路径在中间断裂**(如 `a.b.c` 但 `a` 不是 BaseModel): 3a 分支
  → 硬错。
- **字段拼写错**(如 `audi_id` 而不是 `audit_id`): 3b 分支
  → 硬错。
- **多态 Union**(如 `Union[A, B]`): `_unwrap` 不解包,返回原
  `Union[A, B]`,但循环里 `current` 既不是 `BaseModel` 也不是
  `Any`,**下次循环**会走 3a 分支 → 硬错("期望 BaseModel,实际
  Union")。
- **List[Union[A, B]]**:`_unwrap` 先进 `list` → `Union[A, B]`,
  然后 3a 硬错。

---

## 6. 内部辅助

### 6.1 `_is_basemodel_subclass(obj) -> bool`

```python
def _is_basemodel_subclass(obj: Any) -> bool:
    """判断 obj 是不是 BaseModel 子类(type 且 issubclass)。"""
    return isinstance(obj, type) and issubclass(obj, BaseModel)
```

**为什么 `isinstance(obj, type)` 先判:** `issubclass` 对非类对象会
抛 `TypeError`,必须先确认 `obj` 是 type。

**与 `spec._is_basemodel_subclass` 重复:** 是的 — 这两个函数实现相
同。重复是为了让 `path_resolver` 不依赖 `spec`(叶子工具的依赖约
束)。后续重构时考虑把 `is_basemodel_subclass` 抽到公共位置(比如
`Plate._typing.py`)。

### 6.2 `_unwrap(annotation) -> Any`

```python
def _unwrap(annotation: Any) -> Any:
    """透明解 ``Optional[T]`` / ``list[T]`` / ``dict[str, V]`` / ``Annotated[T, ...]``。

    业务规则(对应 PLATE_DESIGN §2.2 表格):
      * ``Union[T, None]`` (Optional):取 T(单值)
      * ``Union[A, B, ...]`` (多态):**原样返回**(解析器不会处理,留给上层)
      * ``list[T]`` / ``List[T]``:取 T(元素)
      * ``dict[str, V]`` / ``Dict[str, V]``:取 V(值)
      * ``Annotated[T, ...]`` / ``Final[T]``:取 T(忽略 metadata)
      * 空参数(如 ``list`` 无 ``[T]``)原样返回
      * ``Any`` 不被解包 —— 由 ``resolve_logical_path`` 单独标记
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    # 1. Optional[T] / T | None / Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap(non_none[0])
        # 多态 Union[A, B, ...] → 原样返回(不可静态选)
        return annotation

    # 2. list[T] / List[T](Python 3.8+ get_origin 统一返回 list)
    if origin is list:
        return _unwrap(args[0]) if args else annotation

    # 3. dict[str, V] / Dict[str, V](同上,统一返回 dict)
    if origin is dict:
        return _unwrap(args[1]) if len(args) > 1 else annotation

    # 4. Annotated[T, ...] / Final[T] / 其他带 origin 的泛型
    if origin is not None and args:
        return _unwrap(args[0])

    return annotation
```

**算法步骤:**

1. **`Union[T, None]` (Optional) 探测:**
   - `get_origin(Union[T, None])` → `Union`(Python typing 约定)
   - `non_none` = 过滤掉 `type(None)` 后的列表
   - 如果 `len(non_none) == 1`(确实是 Optional)→ 递归 `_unwrap`
     那个非 None 类型
   - 否则(多态 Union)→ 原样返回(让上层 `resolve_logical_path` 在下
     次循环 3a 检测到"期望 BaseModel,实际 Union")

2. **`list[T]` 探测:**
   - `get_origin(list[T])` → `list`
   - 取 `args[0]` 递归 `_unwrap`
   - 空 args(如 `list` 无 `[T]`)→ 原样返回

3. **`dict[str, V]` 探测:**
   - `get_origin(dict[str, V])` → `dict`
   - 取 `args[1]`(value 类型)递归 `_unwrap`
   - 空 args → 原样返回

4. **其他泛型(`Annotated` / `Final`):**
   - `get_origin(Annotated[T, ...])` → `Annotated` 之类的 origin
   - `args[0]` 递归 `_unwrap`(忽略 metadata)

5. **回退:** 如果 `origin is None` 且没匹配到上述分支,原样返回
   (这是叶子类型 `int` / `str` / Pydantic 类等的路径)。

**为什么 `list` 而不是 `List`:**
- Python 3.8+ 的 `typing.get_origin(List[T])` 也返回 `list`(PEP 585)。
- `from __future__ import annotations` 让所有注解变成字符串,运行时
  拿 `list[T]` 的 origin 是 `list`。

**为什么"多态 Union 原样返回":**
- 解析器无法静态选"A 还是 B"。
- 让上层 `resolve_logical_path` 在下次循环走 3a(因为 `current` 不是
  BaseModel 也不是 Any)→ 硬错。
- 这是"明确告诉调用方"多态路径不可静态走。

**为什么 `Any` 不被解包:**
- `get_origin(Any)` → `None`(没有 origin)。
- `get_args(Any)` → `()`(没有 args)。
- 走 5 号分支"原样返回",上层 `resolve_logical_path` 在 3d 检测
  `current is Any` → 软降级。

**为什么递归 `_unwrap`:**
- 嵌套类型如 `Optional[list[Optional[X]]]` 需要多层解包。
- 递归让代码扁平(`_unwrap(args[0])` 内层继续解)。

---

## 7. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `Resolved` | `@dataclass(frozen=True)` | `from Plate.path_resolver import Resolved` |
| `resolve_logical_path` | function | `from Plate.path_resolver import resolve_logical_path` |

模块底部 `__all__`:

```python
__all__ = [
    "Resolved",
    "resolve_logical_path",
]
```

---

## 8. 调用方典型代码示例

```python
# 1. 简单路径解析
from Plate.path_resolver import resolve_logical_path
from Plate.fin.models import OrderDetailRequest, OrderDetailData, AuditDetailData
from pydantic import BaseModel, ConfigDict

class Resp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: int
    data: OrderDetailData

# 严格解析成功
r = resolve_logical_path(Resp, "data.order_id")
print(r.target_type)  # <class 'str'>
print(r.hit_any)  # False
print(r.error)  # None

# 2. 字段拼错 → 硬错
r = resolve_logical_path(Resp, "data.wrong_field")
print(r.target_type)  # None
print(r.error)  # "字段 'wrong_field' 不在 OrderDetailData 中"

# 3. 期望 BaseModel 收到 int → 硬错
r = resolve_logical_path(Resp, "data.order_id.sub")
print(r.error)  # "路径 'sub' 处期望 BaseModel,实际 str"

# 4. 空路径 = 根
r = resolve_logical_path(Resp, "")
print(r.target_type)  # Resp 类本身

# 5. 配合 FieldBinding 校验(PR-D2)
from Plate.binding import FieldBinding
from Plate.spec import EndpointSpec

binding = FieldBinding(
    from_path=("data", "audit_id"),
    to_path=("audit_id",),
)

# 假设 auditDetail 的 request 是 AuditDetailRequest
endpoint = EndpointSpec(...)  # 假设构造好了
r = resolve_logical_path(endpoint.request, "audit_id")
assert r.target_type is str and not r.hit_any  # 严格解析成功
```

---

## 9. 不变量总结(本模块承诺的不变式)

1. **不可变结果**:`Resolved` 是 `frozen=True` dataclass。
2. **纯函数**:`resolve_logical_path` 无副作用,相同输入永远产相同
   `Resolved`。
3. **三态空间**:`(target_type, hit_any, error)` 完整覆盖"成功 /
   Any 降级 / 硬错"。
4. **透明穿过容器**:`list[T]` / `dict[str, V]` / `Optional[T]` /
   `Annotated[T, ...]` 都自动解包,作者不需要写特殊路径。
5. **多态不可静态走**:`Union[A, B, ...]` 不会被解包,让上层做
   硬错处理。
6. **无副作用 import**:本模块只 import stdlib + pydantic,不引入任何
   Plate 子模块依赖。

---

## 10. 设计权衡

| 决策 | 取舍 |
|---|---|
| `Any` 软降级不报错 | 作者有时故意用 `Any` 表达"宽容";硬错会误伤 |
| 多态 Union 硬错 | 解析器无法静态选 A 还是 B,只能 fail-fast |
| 不递归 `list[Union[A, B]]` | 多态 Union 内部遇到同样问题,无法静态选 |
| `Optional` 解包 | 业务中 99% 的 Optional 字段"非 None 时"是单类型 |
| `dict[K, V]` 只取 V 不取 K | 业务上 K 通常是业务维度(币种/语言),无法穷举 |
| `Annotated[T, ...]` 解包忽略 metadata | metadata 是 Pydantic Field 描述,不影响类型 |
| `Resolved` 不存储 `root` | 一次解析的快照,不需要回查;调用方持有 root |
| 重复 `_is_basemodel_subclass` | path_resolver 不依赖 spec,保持叶子工具;后续可抽公共 |
