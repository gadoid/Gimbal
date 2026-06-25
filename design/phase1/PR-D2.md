# PR-D2: FieldBinding 落地(类型 + EndpointSpec 字段 + 构造期校验)

> **状态**:待执行
>
> **PR 范围**:新增 `FieldBinding` 数据类(类型层 + EndpointSpec 字段 + `__post_init__` 校验),**不批量化任何 endpoint**(那是 PR-D4 的事)。
>
> **前置依赖**:[PR-D1](PR-D1.md)(`resolve_logical_path` 可用) + [PR-B](PR-B.md)(`category` + `mutates_state` 已落) + [PR-C](PR-C.md)(fin 31 端点已显式标 category)。
>
> **关键设计**:FieldBinding 只描述"端点 A 依赖端点 B 的某个字段",不描述"如何注入/合并/调用顺序"——那是后续 PR 的事。
>
> **对应设计**:[PLATE_DESIGN.md §2.2 + §3.4 + §3.5](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:fin 服务有大量"先调 A 拿 ID,再把 ID 喂给 B"的串联调用(典型:`addOrder` → `orderDetail` → `cancelOrder`)。**这些依赖关系当前只在人脑里**,无法:
- 让 AI skill 知道"调 B 之前必须先调 A"
- 让 CT 主动保活排探测顺序
- 让 Mock server 自动按依赖注入请求体

**设计 §3.5**:
> `FieldBinding` 是**声明性**的依赖:消费者按 `bindings` 知道"我需要从哪个上游拿什么字段",注入策略由消费者自己决定。

### 1.2 字段设计

| 字段 | 类型 | 业务含义 |
|---|---|---|
| `from_path` | `tuple[str, ...]` | 上游响应体里要取的字段路径(logical schema path,空 tuple = 整个 body) |
| `to_path` | `tuple[str, ...]` | 下游请求体里要注入的字段路径 |
| `transform` | `str \| None` | 可选转换描述(如 `"identity"` / `"int->str"`),本 PR 只存不解析 |
| `required` | `bool` | True = 注入失败硬错;False = 注入失败静默跳过(本 PR 默认为 True) |

### 1.3 关键决策

- **声明性 vs 命令性**:FieldBinding 只描述"取哪儿→注入哪儿",**不描述**"如何注入""何时调用"。这避免和"调用编排"耦合。
- **logical path 复用 PR-D1**:FieldBinding 的 `from_path` / `to_path` 都是 logical schema path(不是 Python attribute 名),所以 PR-D1 的 `resolve_logical_path` 必装。
- **transform 暂不解析**:AI 消费者会按 `transform` 字符串理解,但代码层只做 key 校验、不做语义执行。

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/binding.py` | 新建:`FieldBinding` dataclass + 模块级 validator |
| `src/Plate/spec.py` | 加 `bindings: tuple[FieldBinding, ...]` 字段 + `__post_init__` 校验 |
| `src/Plate/__init__.py` | re-export `FieldBinding` |
| `tests/plate/test_binding.py` | 新建:本 PR 专属测试(≥12 个) |
| `tests/plate/test_invariants.py` | 加不变量:`bindings` 不指向 self(防自环) |

### 2.2 `FieldBinding` 数据类定义

```python
# src/Plate/binding.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import final


@final
@dataclass(frozen=True)
class FieldBinding:
    """声明性字段绑定:从 from_path 取出值,注入到 to_path。

    对应设计:PLATE_DESIGN.md §2.2

    关键约束:
    - from_path / to_path 是 logical schema path(空 tuple 表示整个 body)
    - 仅描述依赖关系,不规定调用顺序/注入时机
    - transform 是描述性字符串,本 PR 不解析语义
    """

    from_path: tuple[str, ...]
    to_path: tuple[str, ...]
    required: bool = True
    transform: str | None = None
```

**为什么 `tuple` 不用 `list`**:`FieldBinding` 是 `@final` + `frozen=True`,字段必须是 immutable(`tuple` 满足)。`list` 在 dataclass 里需要 `field(default_factory=list)`,且 hashable 要求下不可用。

### 2.3 `EndpointSpec` 新增字段

**位置**:紧随 `mutates_state` 之后(沿用 PR-B 的"分类"分组紧邻原则):

```python
# src/Plate/spec.py
from Plate.binding import FieldBinding

@final
@dataclass(frozen=True)
class EndpointSpec:
    # ... 前面字段不变 ...

    # —— 跨端点依赖(新增)——
    bindings: tuple[FieldBinding, ...] = ()

    # ... 后面字段不变 ...
```

**为什么用 `tuple[FieldBinding, ...]` 不用 `list[FieldBinding]`**:
- frozen=True 要求字段 immutable
- `tuple` 是 hashable,可让 `EndpointSpec` 整体作为 dict key(后续做 spec dedup 用)
- 序列化稳定(YAML / JSON 输出顺序确定)

### 2.4 `__post_init__` 校验(注册期 fail-fast)

```python
def __post_init__(self) -> None:
    # ... 原有检查(PR-B 的 category × mutates_state)...

    # (d-2) 新增:bindings 校验
    if self.bindings:
        for i, b in enumerate(self.bindings):
            # 类型校验
            if not isinstance(b, FieldBinding):
                raise TypeError(
                    f"EndpointSpec({self.path!r}): bindings[{i}] 不是 FieldBinding "
                    f"实例(类型={type(b).__name__})。"
                    f"对应设计:PLATE_DESIGN.md §2.2"
                )
            # 路径校验:to_path 不为空(注入位置必须明确)
            if not b.to_path:
                raise ValueError(
                    f"EndpointSpec({self.path!r}): bindings[{i}].to_path 不能为空 "
                    f"(注入目标必须明确,空 tuple 表示整个 body 但语义模糊,禁止)。"
                )
            # transform 必须是已知字符串或 None(白名单,防拼写错误)
            if b.transform is not None and b.transform not in _KNOWN_TRANSFORMS:
                raise ValueError(
                    f"EndpointSpec({self.path!r}): bindings[{i}].transform={b.transform!r} "
                    f"不在已知集合 {_KNOWN_TRANSFORMS} 中。"
                )

    # (d-3) bindings 不指向 self(防自环 / 自己的响应又塞回自己的请求)
    # 此项由 test_invariants.py 在所有 spec 注册后做聚合检查(本 PR 不在 __post_init__ 做)
```

### 2.5 `_KNOWN_TRANSFORMS` 白名单

```python
# src/Plate/binding.py
_KNOWN_TRANSFORMS: frozenset[str] = frozenset({
    "identity",          # 直接赋值,无转换
    "int->str",          # int → str(典型:order_id 注入到下游 string 字段)
    "str->int",          # str → int
    "iso8601->epoch",    # 时间戳转换
    "epoch->iso8601",    # 反向
})
```

**为什么白名单**:FieldBinding 是 L1 字段(可被 review pipeline 静态校验)。未在白名单的 `transform` 字符串 = "代码层不知道怎么处理",可能在生产静默失败。白名单让 review pipeline 可以 grep 出"未实现 transform"。

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
1. **业务需求**(声明性依赖的硬约束)
2. **对应设计章节**
3. **业务影响**(违反此约束的代价)

### 3.2 必测业务场景

```python
"""PR-D2:FieldBinding 落地测试。

业务动机:FieldBinding 是声明性依赖,描述"端点 A 需要端点 B 的某个字段"。
本 PR 只验证类型/字段/校验,不验证批量化(那是 PR-D4)。
"""


# ════════════════════════════════════════════════════════════════════════════
# FieldBinding 自身
# ════════════════════════════════════════════════════════════════════════════

def test_field_binding_default_required_true():
    """业务需求:FieldBinding 默认 required=True(注入失败必须硬错)。

    对应设计:§2.2 required 默认值约定。
    业务影响:默认 False = 注入失败静默跳过,生产环境拿不到关键 ID 仍继续调用下游 = 真实事故。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    assert b.required is True
    assert b.transform is None


def test_field_binding_frozen():
    """业务需求:FieldBinding 不可变(frozen)。

    对应设计:§2.2 "@final + frozen=True"。
    业务影响:可写 = 多线程下 binding 被另一线程改写,跨端点依赖静默失真。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    with pytest.raises((FrozenInstanceError, AttributeError)):
        b.from_path = ("other",)  # type: ignore[misc]


def test_field_binding_hashable():
    """业务需求:FieldBinding 可作 set / dict key。

    对应设计:后续 spec dedup 用。
    业务影响:不可哈希 = 无法做"等价 binding 检测",review pipeline 难去重。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=("order_id",))
    s = {b}
    assert b in s


# ════════════════════════════════════════════════════════════════════════════
# EndpointSpec 集成
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_spec_default_bindings_empty_tuple():
    """业务需求:EndpointSpec 默认 bindings=空 tuple。

    对应设计:§2.3 字段默认值约定。
    业务影响:PR-D2 不要求存量端点必须标注,PR-D4 才批量化。
    """
    spec = EndpointSpec(method="POST", path="/x", responses={200: M()})
    assert spec.bindings == ()
    assert isinstance(spec.bindings, tuple)


def test_endpoint_spec_with_single_binding_constructs():
    """业务需求:EndpointSpec 接受单个 binding 构造。

    对应设计:§2.3 字段定义。
    业务影响:此约束是 PR-D4 批量化的前置;若构造失败,PR-D4 无法落地。
    """
    b = FieldBinding(from_path=("data", "order_id"), to_path=("order_id",))
    spec = EndpointSpec(
        method="POST", path="/api/order/cancel",
        request=CancelRequest, responses={200: M()},
        bindings=(b,),
    )
    assert len(spec.bindings) == 1
    assert spec.bindings[0] is b


def test_endpoint_spec_with_multiple_bindings_preserves_order():
    """业务需求:多 binding 时顺序保持。

    对应设计:§2.3 tuple 语义。
    业务影响:顺序乱 = "后注入的覆盖先注入的"风险。
    """
    b1 = FieldBinding(from_path=("a",), to_path=("x",))
    b2 = FieldBinding(from_path=("b",), to_path=("y",))
    spec = EndpointSpec(
        method="POST", path="/x",
        request=R, responses={200: M()},
        bindings=(b1, b2),
    )
    assert spec.bindings[0] is b1
    assert spec.bindings[1] is b2


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝(注册期 fail-fast)
# ════════════════════════════════════════════════════════════════════════════

def test_binding_non_fieldbinding_type_raises():
    """业务需求:bindings 里塞非 FieldBinding 元素硬错。

    对应设计:§2.4 类型校验。
    业务影响:接受任意对象 = 序列化时崩溃,review pipeline 无法静态分析。
    """
    with pytest.raises(TypeError) as exc:
        EndpointSpec(
            method="POST", path="/x",
            request=R, responses={200: M()},
            bindings=("not-a-binding",),  # type: ignore[arg-type]
        )
    assert "FieldBinding" in str(exc.value)


def test_binding_empty_to_path_raises():
    """业务需求:to_path 不能为空 tuple。

    对应设计:§2.4 "注入目标必须明确"。
    业务影响:允许空 to_path = 注入位置语义模糊(整个 body?覆盖?),消费者无法处理。
    """
    b = FieldBinding(from_path=("data", "id"), to_path=())  # 空
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="POST", path="/x",
            request=R, responses={200: M()},
            bindings=(b,),
        )
    assert "to_path" in str(exc.value)


def test_binding_unknown_transform_raises():
    """业务需求:transform 必须在白名单内。

    对应设计:§2.5 白名单约定。
    业务影响:接受任意字符串 = review pipeline 无法静态校验"未实现 transform"。
    """
    b = FieldBinding(
        from_path=("data", "id"),
        to_path=("order_id",),
        transform="not-a-real-transform",
    )
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="POST", path="/x",
            request=R, responses={200: M()},
            bindings=(b,),
        )
    assert "transform" in str(exc.value)


def test_binding_known_transform_constructs():
    """业务需求:白名单内 transform 应正常构造。

    对应设计:§2.5 白名单约定。
    业务影响:白名单过严 = PR-D4 标注 binding 时大量无法落地。
    """
    for t in ("identity", "int->str", "str->int", "iso8601->epoch", "epoch->iso8601"):
        b = FieldBinding(
            from_path=("data", "id"),
            to_path=("order_id",),
            transform=t,
        )
        spec = EndpointSpec(
            method="POST", path="/x",
            request=R, responses={200: M()},
            bindings=(b,),
        )
        assert spec.bindings[0].transform == t


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式未破
# ════════════════════════════════════════════════════════════════════════════

def test_bindings_field_is_frozen():
    """业务需求:EndpointSpec.bindings 在 frozen 实例上不可写。

    对应设计:§2.3 frozen 不变式。
    业务影响:可写 = 多线程 race condition,依赖关系被静默改写。
    """
    spec = EndpointSpec(
        method="POST", path="/x",
        request=R, responses={200: M()},
        bindings=(FieldBinding(from_path=("a",), to_path=("b",)),),
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.bindings = ()  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# 不变量聚合(由 test_invariants.py 复用)
# ════════════════════════════════════════════════════════════════════════════

# 在 test_invariants.py 加:
# def test_invariant_no_self_binding():
#     """业务不变量:任何 binding 的 from_path 不引用本 endpoint 的响应。
#
#     对应设计:§2.4 自环防护(聚合检查)
#     业务影响:自环 binding = "自己响应喂回自己请求",典型循环引用 bug。
#     """
#     from Plate.core import registry
#     for key, spec in registry._index.items():
#         for i, b in enumerate(spec.bindings):
#             # 自环判断:本 binding 的 from_path 不能指向本 endpoint 的 path
#             # 注:本检查是简化版,精确版需要"binding from → 哪个 endpoint"反向索引
#             # PR-D4 会引入 BindingRegistry 做精确检查
#             assert isinstance(b.from_path, tuple)
#             assert isinstance(b.to_path, tuple)
#             assert b.to_path, f"{key.service} {key.path}: bindings[{i}].to_path 为空"
```

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| FieldBinding 默认值 | `test_field_binding_default_required_true` | 防静默跳过 |
| FieldBinding frozen + hashable | `test_field_binding_frozen` / `test_field_binding_hashable` | 线程安全 + dedup 可行 |
| EndpointSpec 集成 | `test_endpoint_spec_default_bindings_empty_tuple` / `..._with_single_binding_...` / `..._preserves_order` | PR-D4 前置 |
| 硬错拒绝 | `test_binding_non_fieldbinding_type_raises` / `..._empty_to_path_raises` / `..._unknown_transform_raises` | 注册期 fail-fast |
| 白名单正确性 | `test_binding_known_transform_constructs` | 防过严 + 防过松 |
| frozen 不变式 | `test_bindings_field_is_frozen` | 线程安全 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_binding.py -v

# 2. 跑不变量聚合
pytest tests/plate/test_invariants.py::test_invariant_no_self_binding -v

# 3. 跑全量基线
pytest tests/  # 应 ≥ 184 + 12 = 196 个测试全过

# 4. 故意制造"未知 transform"验证断言
python -c "
from Plate.spec import EndpointSpec
from Plate.binding import FieldBinding
from pydantic import BaseModel, ConfigDict
class R(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: str = ''
class M(BaseModel):
    model_config = ConfigDict(extra='forbid')
    y: str = ''
try:
    EndpointSpec(
        method='POST', path='/x',
        request=R, responses={200: M},
        bindings=(FieldBinding(from_path=('a',), to_path=('b',), transform='bogus'),)
    )
    print('FAIL: 应抛 ValueError')
except ValueError as e:
    print(f'OK: 拒绝未知 transform, 信息: {e}')
"

# 5. 验证 frozen + hashable
python -c "
from Plate.binding import FieldBinding
b = FieldBinding(from_path=('a',), to_path=('b',))
print(f'hash={hash(b)}, in_set={b in {b}}')  # 应不抛异常
try:
    b.from_path = ('c',)
    print('FAIL: 应抛 FrozenInstanceError')
except Exception as e:
    print(f'OK: frozen 拦截, {type(e).__name__}')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_binding.py` 测试数 | ≥ 12 |
| 失败 | 0 |
| 故意制造未知 transform | 输出 `OK: 拒绝未知 transform` |
| frozen 验证 | 输出 `OK: frozen 拦截` |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 白名单过严,PR-D4 无法落地 | 本 PR 测试覆盖已知 transform 全构造通过;白名单可扩展 |
| 自环检查未在 `__post_init__` 做 | 由 `test_invariants.py` 聚合;PR-D4 引入 BindingRegistry 做精确检查 |
| `bindings` 字段破坏 frozen 不变式 | 已用 `tuple` 不可变;测试 `test_bindings_field_is_frozen` 保证 |

---

## 5. 与后续 PR 的衔接

- **PR-D3**(`EndpointDoc` 物理解耦):与 `bindings` 同属 L1 字段,但 `EndpointDoc` 是 L2 注释,本 PR 不涉及
- **PR-D4**(`field_bindings` 批量化):本 PR 是前置;PR-D4 把 fin 31 端点的真实 binding 关系批量标注
- **PR-EOP**(收口 review pipeline):review pipeline 会扫描 `_KNOWN_TRANSFORMS` 出"未实现 transform"的 binding
- **Phase 2**(service 化):FieldBinding 是 service 编排"调用 A → 拿 B → 喂 C"的依据