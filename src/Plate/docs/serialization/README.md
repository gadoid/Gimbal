# serialization 模块(`Plate/serialization.py`)

> 本文档详细描述 `Plate/serialization.py` 中的**每一个公开/内部函数**,
> 以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模块的所
> 有行为细节与设计动机。

---

## 1. 模块定位

`serialization.py` 是 Plate 子系统的**L1 byte-equal 序列化工具集**。它
解决的核心问题:

> **当 `EndpointSpec` 内部持有 Pydantic 类对象 / Protocol hook 实例等
> 不可直接 JSON 序列化的对象时,如何把它们转成"可序列化 + 反序列化
> 时能重建"的字符串引用?**

它暴露 4 个工具函数:`_model_ref` / `_hook_ref` / `_sorted_responses` /
`_sorted_response_union`。这 4 个函数都是**纯函数**,无副作用,纯字
符串 / dict 转换。

`spec.py` 的 `EndpointSpec.to_dict()` 直接使用这 4 个函数。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
L1 序列化工具函数(PR-2.0 / PLATE_EVOLUTION §3)。

职责:
  * 端点/绑定/版本的 ``to_dict`` / ``from_dict`` 工具函数
  * byte-equal 保证(排序无关字段先排序)
  * BaseModel 引用处理(存"module.ClassName"字符串,反序列化留 None)

设计原则(对应 A2 不可变序列化):
  * 所有 list 输出用 ``sorted(...)`` 消除顺序漂移
  * 所有 dict 输出 ``sort_keys=True``
  * 反序列化严格不容错(契约不可容错)
```

---

## 3. 依赖关系

```python
from typing import Any

from pydantic import BaseModel
```

**为什么这么依赖:**
- `typing.Any` — 接受任何类型入参(因为 `_hook_ref` 接的是
  `Protocol` 实例,具体类型作者自定义)。
- `pydantic.BaseModel` — 类型标注(用于 `_model_ref` 和
  `_sorted_responses`)。

**重要的反向依赖约束:**
- `serialization.py` **不** import 任何其他 Plate 子模块。
- 这保证它是"叶子工具" — 可被 `spec` / `manifest` / 任何模块无副作用
  引用,且自身不引入循环依赖。

---

## 4. 公开函数详解

### 4.1 `_model_ref(model) -> str | None`

```python
def _model_ref(model: type[BaseModel] | None) -> str | None:
    """把 BaseModel 类转成可序列化字符串引用。

    格式:``"{module}.{qualname}"``,例如 ``"Plate.fin.models.AuditPageRequest"``。

    None → None(允许 None)。

    注:本 PR **不**反序列化此字段(留给 PR-2.1 协议 + PR-2.2 SDK 决定
    importlib 重建策略)。本函数只解决"to_dict 不挂"。
    """
    if model is None:
        return None
    return f"{model.__module__}.{model.__qualname__}"
```

**输入:**
- `model: type[BaseModel] | None` — Pydantic BaseModel 子类,**或**
  `None`。

**输出:**
- `None` → 返回 `None`。
- 类对象 → 返回 `f"{model.__module__}.{model.__qualname__}"`。

**字段语义:**
- `__module__` — 类定义所在的模块名(如 `"Plate.fin.models"`)。
- `__qualname__` — 类的"限定名",支持嵌套类(如 `("Outer", "Inner")`
  → `"Outer.Inner"`)。

**为什么用 `__qualname__` 而不是 `__name__`:**
- `__name__` 是类的"短名"(如 `"AuditPageRequest"`)。
- `__qualname__` 是类的"限定名",在嵌套类场景下保留父类信息。
- 用 `__qualname__` 重建时,`getattr(sys.modules["Plate.fin.models"],
  "AuditPageRequest")` 能正确找到类。

**为什么本函数不反序列化:**
- 反序列化涉及"知道在哪个 sys.modules 里找类"。
- 本期 `EndpointSpec.from_dict` 留 `request=None` / `responses={}`,
  由 PR-2.2 SDK 统一处理(可能走 `importlib.import_module` + `getattr`)。

**下划线前缀:** `_model_ref` 是模块私有(下划线开头),但**实际在
`spec.py` 中直接 import 使用**。与 `_KNOWN_TRANSFORMS` 类似 — 是
"下划线 = 私有"惯例的例外。业务代码不应直接 import;它们应构造
`EndpointSpec` 时让 `to_dict` 走这层。

### 4.2 `_hook_ref(hook) -> str | None`

```python
def _hook_ref(hook: Any) -> str | None:
    """hook 是 Protocol 实例或 None。本 PR 范围:存引用名,反序列化留 None。"""
    if hook is None:
        return None
    cls = type(hook)
    return f"{cls.__module__}.{cls.__qualname__}"
```

**输入:**
- `hook: Any` — Protocol 实例(具体类型由 `MockHook` / `ValidateHook` /
  `BuildRequestHook` 约束),**或** `None`。

**输出:**
- `None` → 返回 `None`。
- 实例 → 返回 `f"{type(hook).__module__}.{type(hook).__qualname__}"`。

**与 `_model_ref` 的差别:**
- `_model_ref` 接受的是**类**(因为 Pydantic 模型是"模板",在 spec
  里以"类"形式存在)。
- `_hook_ref` 接受的是**实例**(因为 hook 是"行为",必须先实例化才能
  调用)。

**为什么 type 用 `type(hook)` 而不是 `hook.__class__`:**
- 两者等价,但 `type(hook)` 是更"标准"的 Python 习惯。
- `type(hook)` 也用于 `isinstance` 检查之外的所有"获取类型"场景。

**为什么本函数不反序列化:** 与 `_model_ref` 同源(留给 PR-2.2 SDK)。

### 4.3 `_sorted_responses(responses) -> dict[str, str | None]`

```python
def _sorted_responses(responses: dict[int, type[BaseModel] | None]) -> dict[str, str | None]:
    """responses 是 ``{status: BaseModel}``,序列化按 status 排序。"""
    return {str(k): _model_ref(v) for k, v in sorted(responses.items(), key=lambda kv: kv[0])}
```

**输入:**
- `responses: dict[int, type[BaseModel] | None]` — `{状态码: Pydantic 类}`。

**输出:**
- `dict[str, str | None]` — `{状态码字符串: 模型引用字符串}`,按状态
  码升序排好。

**为什么 status 转 str:**
- JSON dict key 必须是字符串。
- `200` (int) 与 `"200"` (str) 在 Python `dict` 里是不同 key,序列化
  后 `json.dumps` 会把所有 int key 转 str(本身没问题),但**反序列化时
  `json.loads` 会保留 str**。
- 提前显式 str 化,让反序列化逻辑更明确。

**为什么排序:**
- byte-equal 保证 — `responses={200: A, 404: B}` 和 `responses={404: B,
  200: A}` 序列化结果必须一致。

**为什么用 `sorted(responses.items(), key=lambda kv: kv[0])` 而不是
`sorted(responses)`:**
- `sorted(dict)` 会按 key 排序并返回 key 列表,不是 item 列表。
- `sorted(dict.items(), key=...)` 返回排好序的 item 列表。

### 4.4 `_sorted_response_union(response_union) -> dict[str, list[str | None]]`

```python
def _sorted_response_union(
    response_union: dict[int, tuple[type[BaseModel], ...]],
) -> dict[str, list[str | None]]:
    """response_union 是 ``{status: (BaseModel, ...)}``。"""
    return {
        str(k): [_model_ref(m) for m in v]
        for k, v in sorted(response_union.items(), key=lambda kv: kv[0])
    }
```

**输入:**
- `response_union: dict[int, tuple[type[BaseModel], ...]]` — `{状态码:
  (多个 BaseModel 子类的元组)}`。

**输出:**
- `dict[str, list[str | None]]` — `{状态码字符串: 模型引用字符串列表}`。

**与 `_sorted_responses` 的差别:**
- 值的形态是 "元组 → 列表",且每元素都走 `_model_ref`。
- tuple 序列化时是 list(等价),但**内部用 tuple 表达"不可变的有序
  集合"** — 与 dataclass frozen 兼容。

**为什么不排序元组内的元素:**
- 元组顺序是有业务语义的(`(PrimaryError, FallbackError)` 不能任意
  排)。
- 本函数只排"外层 status",不排"内层模型"。

---

## 5. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `_model_ref` | function | `from Plate.serialization import _model_ref` (实际只在 spec.py 内部使用) |
| `_hook_ref` | function | `from Plate.serialization import _hook_ref` (实际只在 spec.py 内部使用) |
| `_sorted_responses` | function | `from Plate.serialization import _sorted_responses` (同上) |
| `_sorted_response_union` | function | `from Plate.serialization import _sorted_response_union` (同上) |

模块底部 `__all__`:

```python
__all__ = [
    "_model_ref",
    "_hook_ref",
    "_sorted_responses",
    "_sorted_response_union",
]
```

**所有 4 个函数都是模块"私有"(下划线开头)但**实际被跨模块使用** —
这是惯例违反,理由同 `_KNOWN_TRANSFORMS`。

---

## 6. 调用方典型代码示例

```python
# 1. _model_ref 用法
from Plate.serialization import _model_ref
from pydantic import BaseModel

class MyModel(BaseModel):
    pass

ref = _model_ref(MyModel)
print(ref)  # "__main__.MyModel" (取决于 import 上下文)

# 2. _hook_ref 用法
from Plate.serialization import _hook_ref

def my_hook(spec, request_payload):
    return None

ref = _hook_ref(my_hook)
print(ref)  # "__main__.my_hook"

# 3. _sorted_responses 用法
from Plate.serialization import _sorted_responses
from Plate.fin.models import CommonResponseEnvelope

d = _sorted_responses({200: CommonResponseEnvelope, 404: None, 500: None})
print(d)  # {"200": "Plate.fin.models.CommonResponseEnvelope", "404": None, "500": None}

# 4. _sorted_response_union 用法
from Plate.serialization import _sorted_response_union
from Plate.fin.models import OrderDetailData, AuditDetailData

d = _sorted_response_union({
    200: (OrderDetailData, AuditDetailData),  # 业务不可换序
    404: (),
})
print(d)  # 内部 list 是两个引用,保持业务顺序
```

---

## 7. 不变量总结(本模块承诺的不变式)

1. **纯函数**:4 个函数都无副作用,相同输入永远产相同输出。
2. **byte-equal 保证**:`_sorted_responses` / `_sorted_response_union`
   对 key 排序,序列化产物与 dict 插入顺序无关。
3. **None 容错**:4 个函数都接受 `None` 输入并返回 `None`,不抛错。
4. **不反序列化**:本模块只解决"to_dict 不挂",反序列化由 PR-2.2 SDK
   统一处理。
5. **无副作用 import**:本模块只 import stdlib + pydantic,不引入任何
   Plate 子模块依赖。

---

## 8. 设计权衡

| 决策 | 取舍 |
|---|---|
| 不反序列化引用 | 本期不实现"to_dict → from_dict 完整往返" — 等 PR-2.2 SDK 决定 importlib 重建策略 |
| 下划线前缀但跨模块 import | 历史例外 — 业务代码不应直接调用,应通过 `EndpointSpec.to_dict` 间接使用 |
| status 转 str | JSON 友好 + 反序列化逻辑明确 |
| 不排序 union 内部 | 业务语义不可换序,排序只对外层 status |
| 接受 `Any` 入参(尤其 `_hook_ref`) | Protocol 实例的具体类型由作者自定义,本函数不约束 |
