# binding 模块(`Plate/binding.py`)

> 本文档详细描述 `Plate/binding.py` 中的**每一个公开/内部常量、类、函数、
> 方法**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模
> 块的所有行为细节与设计动机。

---

## 1. 模块定位

`binding.py` 是 Plate 子系统的**跨端点字段绑定**描述层。它解决的核心问题:

> **如何让一个端点的请求体自动注入"来自另一个端点响应"的字段,而不绑
> 定到具体的调用执行模型?**

它暴露的核心是 `FieldBinding` 数据类 + `_KNOWN_TRANSFORMS` 白名单。
本模块**只**定义数据 + 校验,不规定"如何注入 / 调用顺序" — 那是
service 编排层(PR-D4)的事。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
字段绑定(PR-D2 / PLATE_DESIGN §2.2 + §3.5)。

职责:声明性字段绑定,描述"端点 A 依赖端点 B 的某个字段"。
本模块**只**定义数据类 + 校验,不规定"如何注入/调用顺序"——那是 PR-D4
及 service 编排的事。

设计要点(对应 PLATE_DESIGN §2.2 + §3.5):
  * **声明性 vs 命令性**:只描述"取哪儿→注入哪儿",不描述"如何注入"
    "何时调用"。这避免和"调用编排"耦合。
  * **logical path 复用 PR-D1**:`from_path` / `to_path` 都是 logical schema
    path(空 tuple 表示整个 body)。PR-D1 的 ``resolve_logical_path`` 必装。
  * **transform 暂不解析**:`transform` 是描述性字符串,本模块**不**做语义
    执行;只通过 ``_KNOWN_TRANSFORMS`` 白名单防拼写错误。
  * **@final + frozen=True** + ``tuple`` 字段:不可变 + 可哈希,可让
    ``EndpointSpec`` 整体作 dict key(后续 spec dedup 用)。

业务价值:
  * 让 AI skill 知道"调 B 之前必须先调 A"
  * 让 CT 主动保活排探测顺序
  * 让 Mock server 自动按依赖注入请求体
```

---

## 3. 依赖关系

```python
from dataclasses import dataclass
from typing import final
```

**为什么这么依赖:**
- `dataclasses.dataclass` — 构造 `FieldBinding` 不可变数据类。
- `typing.final` — 给 `FieldBinding` 加 `@final` 防继承。

**重要的反向依赖约束:**
- `binding.py` **不** import `spec` / `core` / `facade` / `server` /
  `api_doc` / 任何 service 子包。
- 这保证 binding 是"纯数据"模块,可以被任何上下文无副作用地 import。

---

## 4. 模块级常量:`_KNOWN_TRANSFORMS`

```python
_KNOWN_TRANSFORMS: frozenset[str] = frozenset(
    {
        "identity",          # 直接赋值,无转换
        "int->str",          # int → str(典型:order_id 注入到下游 string 字段)
        "str->int",          # str → int
        "iso8601->epoch",    # 时间戳转换
        "epoch->iso8601",    # 反向
    }
)
```

**字段语义:**
- 这是一个**白名单**,所有 `FieldBinding.transform` 的取值必须在此集合内。
- 5 个值对应"最常见的 5 种转换场景":
  - `identity` — 直接赋值,无转换(默认场景)。
  - `int->str` — 整数转字符串(典型:`order_id=123` 注入到下游要求字符串的
    字段)。
  - `str->int` — 反向(少见,但偶尔有)。
  - `iso8601->epoch` — ISO 8601 时间字符串转 epoch 毫秒。
  - `epoch->iso8601` — 反向。

**为什么是 `frozenset`:**
- `frozenset` 不可变(防止"运行时往里塞未知 transform 值")。
- `frozenset` 的 `in` 操作 O(1)。
- 类型标注为 `frozenset[str]`,让作者在静态检查时就知道"只能查、不能
  改"。

**为什么用字符串字面值(而不是 Enum):**
- 字符串可以无成本地序列化(JSON / YAML / dict 都能直接 dump),Enum
  要么转成字面值,要么走 `__str__`,都更繁琐。
- 字符串字面值便于"在 spec review pipeline 里 grep",reviewer 看到
  `int->str` 一眼就知道是转换名,不需要查 Enum 文档。

**为什么不解析 transform 语义:**
> 转换是描述性字符串,本模块**不**做语义执行,只通过白名单防拼写
> 错误。

具体执行(把"int 123 转成 str '123'")是 Mock server / CT 主动保活 /
AI skill 编排的责任,本模块不掺和"何时执行 / 如何执行"的细节 —
保持**声明性 vs 命令性**的边界。

**下划线前缀:** `_KNOWN_TRANSFORMS` 是模块私有(下划线开头),但**实际
是 `spec.py` 在 `EndpointSpec.__post_init__` 里直接 import 使用的**(通
过 `from Plate.binding import FieldBinding, _KNOWN_TRANSFORMS`)。**这
是一个违反"下划线 = 私有"惯例的特例**,原因:

> spec.py 需要校验 transform 在白名单内,必须能看到这个常量。如果把它
> 改成 `KNOWN_TRANSFORMS`(去掉下划线),会暗示"业务代码也可 import 这
> 个常量";但实际业务代码不应该直接 import — 它们应该构造 `FieldBinding`
> 时让 `__post_init__` 兜底校验。

**目前没有更好的方案**(比如把校验抽到一个 helper function,让 spec 调用),
所以保留这个例外。

---

## 5. 核心数据类:`FieldBinding`

### 5.1 类声明

```python
@final
@dataclass(frozen=True)
class FieldBinding:
    """声明性字段绑定:从 ``from_path`` 取出值,注入到 ``to_path``。"""
```

**为什么 `@final`:** `FieldBinding` 是描述性数据类,无继承需求;`@final`
防止业务代码"扩展"出奇怪的子类,污染 registry 收集的判定逻辑。

**为什么 `@dataclass(frozen=True)`:**
- 不可变 — 与 `EndpointSpec` 对齐(都是 frozen dataclass)。
- 可哈希 — 后续 spec dedup 可用 `set(FieldBinding instances)`。
- `__eq__` / `__hash__` 自动生成。

### 5.2 字段详解

```python
from_path: tuple[str, ...]
to_path: tuple[str, ...]
required: bool = True
transform: str | None = None
```

#### 5.2.1 `from_path: tuple[str, ...]`

- "源字段路径",是 **logical schema path**。
- 例:`("data", "audit_id")` 表示"响应的 `data.audit_id` 字段"。
- **空 tuple** `()` — 表示"整个 body"。

**为什么用 `tuple` 而不是 `list`:** tuple 不可变,与 `frozen=True` 兼
容;JSON 序列化时 list 跟 tuple 都是数组,无差别。

**为什么用 logical schema path 而不是 JSON Pointer / jq 语法:**
- 我们的 Pydantic 模型有显式的 `model_fields`(结构化元数据),
  `path_resolver.resolve_logical_path` 可以在模型树里**静态**走路径,
  找到终点类型。
- JSON Pointer(`/data/audit_id`)需要实际数据才能解析,无法静态校验
  binding 是否合法。
- jq 语法太复杂,作者学习成本高。
- 简单"点分路径"是最自然的中间形态。

#### 5.2.2 `to_path: tuple[str, ...]`

- "目标字段路径"。
- 例:`("audit_id",)` 表示"请求体的 `audit_id` 字段"。
- **空 tuple** — 在 `__post_init__` 校验里被禁止(语义模糊,见下)。

**为什么禁止空 `to_path`:**

> 注入目标必须明确,空 tuple 语义模糊,禁止。

`from_path=()` 表示"整个 body"是合理的(比如"把整个响应作为请求的
body")。但 `to_path=()` 表示"把值注入到 body 的哪里"语义模糊 — 是
覆盖整个 body?还是与 body merge?还是追加为某个 list 的元素?每种解释
都对应不同实现,作者必须显式表态。

#### 5.2.3 `required: bool = True`

- `True` (默认) — 注入失败硬错(`from_path` 拿不到值,raise)。
- `False` — 静默跳过(`from_path` 拿不到值,不注入,继续执行)。

**为什么默认 `True`:** fail-fast 是"声明性"语义 — 作者写一个 binding
就是希望它生效;如果拿不到值,通常意味着上游数据缺失,继续走可能
产生无效请求。

**为什么提供 `False`:** 有时 binding 是"可选增强"(比如"如果上游返
回了备注,带过去"),这种场景 `required=False` 让编排层容错。

#### 5.2.4 `transform: str | None = None`

- 默认 `None` — 等价于 `"identity"`(不转换,直接赋值)。
- 取值必须 ∈ `_KNOWN_TRANSFORMS`(由 `EndpointSpec.__post_init__`
  强校)。

**为什么用 `str | None` 而不是 `str`:** `None` 表达"无转换"语义最清
楚,序列化时也方便(JSON `null` 比空字符串 `""` 含义明确)。

### 5.3 序列化方法

#### 5.3.1 `to_dict() -> dict`

```python
def to_dict(self) -> dict:
    """序列化为 dict。

    字段约定:
      from_path/to_path 是 list(不是 tuple,JSON 不区分)
      其余字段直传
    """
    return {
        "from_path": list(self.from_path),
        "to_path": list(self.to_path),
        "required": self.required,
        "transform": self.transform,
    }
```

**字段语义:**
- `from_path` / `to_path` 是 `tuple[str, ...]`(内部不可变),序列化时
  转 `list`(JSON 数组)。
- `required` 直传 bool。
- `transform` 直传 str 或 None。

**为什么 `tuple → list` 转换:** JSON 没有"tuple"概念,`json.dumps`
对 tuple 的处理是转成数组(行为等同 list)。但**在 Python 数据结构
层面**,作者可能想"明确知道这是不可变路径" — 内部 tuple,序列化
list。这种"内不可变 / 外 JSON 友好"是常见模式。

#### 5.3.2 `from_dict(d: dict) -> "FieldBinding"` — classmethod

```python
@classmethod
def from_dict(cls, d: dict) -> "FieldBinding":
    """从 dict 反序列化。严格不容错。"""
    if not isinstance(d, dict):
        raise TypeError(...)
    for required in ("from_path", "to_path"):
        if required not in d:
            raise KeyError(...)
    from_path = d["from_path"]
    to_path = d["to_path"]
    if not isinstance(from_path, (list, tuple)):
        raise TypeError(...)
    if not isinstance(to_path, (list, tuple)):
        raise TypeError(...)
    return cls(
        from_path=tuple(from_path),
        to_path=tuple(to_path),
        required=bool(d.get("required", True)),
        transform=d.get("transform"),
    )
```

**校验逻辑:**
1. `d` 必须是 dict,否则 `TypeError`。
2. 必填字段 `from_path` / `to_path` 缺失 → `KeyError`。
3. `from_path` / `to_path` 必须是 list 或 tuple,否则 `TypeError`。
4. 构造时 `from_path=tuple(from_path)` — list 转 tuple,确保内部不
   可变。
5. `required` 默认 `True`,`transform` 默认 `None`(实际 JSON 里不传
   `transform` 时,`d.get("transform")` 返 `None`)。

**为什么 "严格不容错":**
> 序列化产物是契约,容错 = 接受坏契约。

(与 `EndpointSpec.from_dict` 同源。)

**为什么不校验 `to_path` 非空:**
- `EndpointSpec.__post_init__` 在 bindings 校验里已经强校 `to_path` 非空
  (见 spec.md §7.3.4)。
- `FieldBinding.from_dict` 是**纯反序列化**,不重复强校(避免双重
  错误信息)。

---

## 6. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `FieldBinding` | `@final @dataclass(frozen=True)` | `from Plate.binding import FieldBinding` |
| `_KNOWN_TRANSFORMS` | `frozenset[str]`(内部使用) | 实际在 spec.py 中被 import;业务代码不应直接 import |

模块底部 `__all__`:

```python
__all__ = [
    "FieldBinding",
    "_KNOWN_TRANSFORMS",
]
```

---

## 7. 调用方典型代码示例

```python
# 1. 构造一个简单 binding
from Plate.binding import FieldBinding

# audit_id from 响应的 data.audit_id → 注入到请求的 audit_id
binding = FieldBinding(
    from_path=("data", "audit_id"),
    to_path=("audit_id",),
)

# 2. 配合 EndpointSpec
from Plate.spec import EndpointSpec
from Plate.fin.models import AuditDetailRequest, CommonResponseEnvelope

audit_detail = EndpointSpec(
    method="POST",
    path="/api/home/audit/auditDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=AuditDetailRequest,
    responses={200: CommonResponseEnvelope},
    bindings=(
        FieldBinding(
            from_path=("data", "audit_id"),
            to_path=("audit_id",),
            required=True,
        ),
    ),
)

# 3. 序列化
d = binding.to_dict()
# {"from_path": ["data", "audit_id"], "to_path": ["audit_id"], "required": True, "transform": None}

# 4. 反序列化
b = FieldBinding.from_dict(d)
assert b.from_path == ("data", "audit_id")
assert b.to_path == ("audit_id",)
```

---

## 8. 不变量总结(本模块承诺的不变式)

1. **不可变**:`frozen=True` 让 binding 实例在构造后无法被修改。
2. **不可继承**:`@final` 装饰器禁止任何类继承 `FieldBinding`。
3. **路径不可变**:`from_path` / `to_path` 是 `tuple[str, ...]`,无法
   整体或元素修改。
4. **transform 限定白名单**:取值必须 ∈ `_KNOWN_TRANSFORMS`(由
   `EndpointSpec.__post_init__` 强校,本模块的 `from_dict` 不重复校)。
5. **`to_path` 非空**:由 `EndpointSpec.__post_init__` 强校,本模块
   的 `from_dict` 不重复校。
6. **byte-equal 序列化**:`to_dict` 产物 path 走 list(非 tuple),字段顺序
   固定;`from_dict` 严格不容错。

---

## 9. 设计权衡

| 决策 | 取舍 |
|---|---|
| 不在 `FieldBinding` 内部校验 `to_path` 非空 | 单一职责 — 业务校验集中在 `EndpointSpec.__post_init__`,本模块只负责数据形状 |
| 不解析 transform 语义 | 声明性 vs 命令性 — 转换执行是编排层的事,本模块只描述 |
| `transform` 用字符串字面值 | 序列化友好 + grep 友好 + 静态检查可见 |
| `_KNOWN_TRANSFORMS` 下划线开头但被跨模块 import | 历史例外;重构时考虑改成 `FieldBinding.assert_valid_transform()` helper |
| 不在 `FieldBinding` 做"自环检查"(本 binding 的 from_path 指向本 endpoint) | 需要精确反向索引,留到 PR-D4 + `test_invariants.py` 聚合 |
