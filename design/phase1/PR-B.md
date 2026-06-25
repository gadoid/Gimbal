# PR-B: EndpointSpec 引入 category + mutates_state 字段

> **状态**:待执行
>
> **PR 范围**:在 `EndpointSpec` 上加 2 个新字段(`category: EndpointCategory` + `mutates_state: bool`),`__post_init__` 加交叉校验断言。
>
> **前置依赖**:[PR-0.2](PR-0.2.md)(`Plate` 重命名 + model_registry 测试 pytest 化)
>
> **关键设计**:字段给默认值兜底,存量 31 端点不动;注册期只拒绝"标错类目"硬错。
>
> **对应设计**:[PLATE_DESIGN.md §2.1 + §3.2 + §3.4(c)](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:CT(契约保活)主动探测**必须避免触发业务写入**。但当前 `EndpointSpec` 没有任何字段告诉消费者"这个接口是只读还是写"。

**设计 §3.2**:
> `category` 是消费者要用的分类标签,但它驱动一个有真实风险的决策——**CT 保活只能对 `QUERY` / `TOOL` 做主动探测**,标错类目意味着探测脚本可能在生产环境意外触发一次业务写入(真实事故风险)。

### 1.2 字段设计

| 字段 | 类型 | 默认值 | 业务含义 |
|---|---|---|---|
| `category` | `EndpointCategory` enum | `BUSINESS` | 接口在业务体系中的角色分类(BUSINESS/QUERY/TOOL) |
| `mutates_state` | `bool` | `True` | 是否产生"有业务意义"的状态变更(给 category 背书的可验证字段) |

### 1.3 关键决策

- **默认值兜底**:`BUSINESS` + `True` —— 所有现有调用保持行为不变;存量 31 个 `fin` 端点全过 `__post_init__`
- **强校**: `category in (QUERY, TOOL)` 时 `mutates_state is False`(用 `is False` 不用 `not`,防 `None` 滑过)
- **不强制存量标注**:本 PR 只加字段+断言,不要求 PR-C 之前的端点必须新标注

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/spec.py` | 加 `EndpointCategory` enum + 2 个新字段 + `__post_init__` 强校 |
| `src/Plate/__init__.py` | (可选)re-export `EndpointCategory` |
| `tests/plate/test_spec_category.py` | 新建:本 PR 专属测试 |
| `tests/plate/test_invariants.py` | 更新:加新不变量 |

### 2.2 `EndpointCategory` enum 定义

```python
from enum import Enum


class EndpointCategory(str, Enum):
    """接口在业务体系中的角色分类。给人 / AI 理解和决策用,不构成强约束。

    对应设计:PLATE_DESIGN.md §2.1
    """
    BUSINESS = "business"   # 主业务流程接口(有业务意义的状态变更)
    QUERY = "query"         # 查询接口(返回具体业务实体数据,无业务状态变更)
    TOOL = "tool"           # 工具型接口(系统级能力,与具体业务实体无关)
```

**设计选择 `str, Enum`**:让 `category` 可序列化(JSON / YAML),与外部系统(MCP、API doc)互通。

### 2.3 `EndpointSpec` 新增字段

**位置**:紧随必填字段 `method` / `path` 之后(按设计 §2.1 字段分组"分类(新增)"):

```python
@final
@dataclass(frozen=True)
class EndpointSpec:
    # —— 数据(必填)——
    method: str
    path: str

    # —— 分类(新增)——
    category: EndpointCategory = EndpointCategory.BUSINESS
    mutates_state: bool = True

    # —— 数据(可选)——
    request: type[BaseModel] | None = None
    responses: dict[int, type[BaseModel]] = field(default_factory=dict)
    # ...
```

### 2.4 `__post_init__` 强校(设计 §3.4(c))

```python
def __post_init__(self) -> None:
    # ... 原有检查 ...

    # (c) 新增:category × mutates_state 交叉校验
    if self.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
        if self.mutates_state is not False:  # 严格 is False,防 None 滑过
            raise ValueError(
                f"EndpointSpec({self.path!r}): category={self.category.value} "
                f"必须 mutates_state=False(否则 CT 主动探测会触发业务写入)。"
                f"实际 mutates_state={self.mutates_state!r}。"
                f"对应设计:PLATE_DESIGN.md §3.2"
            )
```

### 2.5 frozen=True 不变式保护

`EndpointSpec` 是 `@final` + `frozen=True` 的 dataclass。**新增字段不破坏 frozen 不变式**,因为:
- 字段有默认值,不强制位置参数
- 任何 `EndpointSpec(method="POST", path="/x")` 调用不变
- 现有调用者都用 `kwargs`,**无位置参数风险**

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
1. **业务需求**(CT 主动探测的硬约束)
2. **对应设计章节**
3. **业务影响**(违反此约束的代价)

### 3.2 必测业务场景

```python
"""PR-B:EndpointCategory + mutates_state 字段测试。

业务动机:CT 主动探测必须避免触发业务写入(设计 §3.2)。
EndpointSpec 引入 category + mutates_state 字段,允许消费者(CT / Mock server /
AI skill)在不知具体业务逻辑的情况下,判断"这个接口能不能主动探测"。
"""


# ════════════════════════════════════════════════════════════════════════════
# 默认值兜底
# ════════════════════════════════════════════════════════════════════════════

def test_default_category_is_business():
    """业务需求:未指定 category 时,默认 BUSINESS + mutates_state=True。

    对应设计:§2.1 字段默认值约定。
    业务影响:默认值必须与 31 个 fin 端点现状匹配(BUSINESS 是最常见),
             否则 PR-B 一上来就 break 所有现有 spec。
    """
    spec = EndpointSpec(method="GET", path="/x", responses={200: M()})
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


def test_existing_fin_endpoints_still_constructible():
    """业务需求:PR-0.2 之后所有 fin 端点仍能用默认 category 构造。

    对应设计:本 PR 不强制存量标注,仅加字段。
    业务影响:任何现有调用破坏 = 31 端点全部需要重写。
    """
    from Plate.fin.models import (
        OrderDetailRequest, CommonResponseEnvelope, OrderDetailData
    )
    # 等价于 fin 真实端点的简化构造
    spec = EndpointSpec(
        method="POST",
        path="/api/order/order/orderDetail",
        request=OrderDetailRequest,
        responses={200: CommonResponseEnvelope},
    )
    # 默认 BUSINESS + True(PR-C 会改成 QUERY + False)
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


# ════════════════════════════════════════════════════════════════════════════
# category 合法值
# ════════════════════════════════════════════════════════════════════════════

def test_category_business_may_mutate_state():
    """业务需求:BUSINESS 类接口可以 mutates_state=True(典型写操作)。

    对应设计:§3.2 "category 是结论,mutates_state 是事实"。
    业务影响:BUSINESS 不应被禁止 mutates_state=True,否则无法表达写操作。
    """
    spec = EndpointSpec(
        method="POST", path="/api/order/add",
        category=EndpointCategory.BUSINESS, mutates_state=True,
        responses={200: M()},
    )
    assert spec.category is EndpointCategory.BUSINESS
    assert spec.mutates_state is True


def test_category_query_must_not_mutate_state():
    """业务需求:QUERY 类接口必须 mutates_state=False。

    对应设计:§3.2 "category in (QUERY, TOOL) ⇒ mutates_state is False"。
    业务影响:QUERY 接口被 CT 主动探测,若 mutates_state=True 会触发业务写入(真实事故风险)。
    """
    spec = EndpointSpec(
        method="POST", path="/api/order/detail",
        category=EndpointCategory.QUERY, mutates_state=False,
        responses={200: M()},
    )
    assert spec.category is EndpointCategory.QUERY
    assert spec.mutates_state is False


def test_category_tool_must_not_mutate_state():
    """业务需求:TOOL 类接口必须 mutates_state=False(系统级能力,无状态变更)。

    对应设计:§3.2。
    业务影响:同 QUERY(CT 主动探测)。
    """
    spec = EndpointSpec(
        method="GET", path="/api/system/dict",
        category=EndpointCategory.TOOL, mutates_state=False,
        responses={200: M()},
    )
    assert spec.category is EndpointCategory.TOOL
    assert spec.mutates_state is False


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝(注册期 fail-fast)
# ════════════════════════════════════════════════════════════════════════════

def test_query_with_mutates_state_true_raises():
    """业务需求:QUERY + mutates_state=True 是硬错,注册期拒绝。

    对应设计:§3.4(c) review pipeline 强制规则 + §3.2 真实事故风险。
    业务影响:允许此组合 = CT 探测可能在生产触发业务写入。
    """
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="POST", path="/x",
            category=EndpointCategory.QUERY, mutates_state=True,
            responses={200: M()},
        )
    assert "category" in str(exc.value)
    assert "mutates_state" in str(exc.value)


def test_tool_with_mutates_state_true_raises():
    """业务需求:TOOL + mutates_state=True 是硬错。

    对应设计:§3.4(c)。
    业务影响:同 QUERY。
    """
    with pytest.raises(ValueError) as exc:
        EndpointSpec(
            method="GET", path="/x",
            category=EndpointCategory.TOOL, mutates_state=True,
            responses={200: M()},
        )
    assert "category" in str(exc.value)


def test_query_with_mutates_state_none_raises():
    """业务需求:QUERY + mutates_state=None 视为"未明确",硬错拒绝(防 None 滑过)。

    对应设计:本 PR §2.4 "用 is False 不用 not"(严格判断)。
    业务影响:用 `not mutates_state` 会被 None 滑过,留下静默不一致。
    """
    with pytest.raises(ValueError):
        EndpointSpec(
            method="POST", path="/x",
            category=EndpointCategory.QUERY, mutates_state=None,  # type: ignore[arg-type]
            responses={200: M()},
        )


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式未破
# ════════════════════════════════════════════════════════════════════════════

def test_category_field_is_frozen():
    """业务需求:category 字段在 frozen 实例上不可写。

    对应设计:§2.1 "@final + frozen=True"。
    业务影响:字段可写 = 多线程 race condition。
    """
    spec = EndpointSpec(
        method="POST", path="/x",
        category=EndpointCategory.QUERY, mutates_state=False,
        responses={200: M()},
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        spec.category = EndpointCategory.BUSINESS  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# 不变量聚合(由 test_invariants.py 复用)
# ════════════════════════════════════════════════════════════════════════════

# 在 test_invariants.py 加:
# def test_invariant_category_x_mutates_state_holds():
#     """业务不变量:任何 QUERY / TOOL 端点必须 mutates_state=False。
#
#     对应设计:§3.2 真实事故风险
#     业务影响:任何破坏 = CT 主动探测可触发业务写入
#     """
#     from Plate.core import registry
#     for key, spec in registry._index.items():
#         if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
#             assert spec.mutates_state is False, (
#                 f"{key.service} {key.method} {key.path}: "
#                 f"category={spec.category} 但 mutates_state={spec.mutates_state}"
#             )
```

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 默认值不破坏存量 | `test_default_category_is_business` | 31 端点全过 |
| | `test_existing_fin_endpoints_still_constructible` | 端点构造链不断 |
| category 合法值 | `test_category_business_may_mutate_state` | 写操作可表达 |
| | `test_category_query_must_not_mutate_state` | CT 探测安全 |
| | `test_category_tool_must_not_mutate_state` | 同上 |
| 硬错拒绝 | `test_query_with_mutates_state_true_raises` | 防止生产事故 |
| | `test_tool_with_mutates_state_true_raises` | 同上 |
| | `test_query_with_mutates_state_none_raises` | 防止 None 滑过 |
| frozen 不变式 | `test_category_field_is_frozen` | 线程安全 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_spec_category.py -v

# 2. 跑不变量聚合
pytest tests/plate/test_invariants.py::test_invariant_category_x_mutates_state_holds -v

# 3. 跑全量基线
pytest tests/  # 应 ≥ 184 个测试全过

# 4. 故意制造"QUERY + mutates_state=True" 验证断言
python -c "
from Plate.spec import EndpointSpec, EndpointCategory
from pydantic import BaseModel, ConfigDict
class M(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: str = ''
try:
    EndpointSpec(method='POST', path='/x', category=EndpointCategory.QUERY, mutates_state=True, responses={200: M})
    print('FAIL: 应抛 ValueError')
except ValueError as e:
    print(f'OK: 拒绝 QUERY+True, 信息: {e}')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_spec_category.py` 测试数 | ≥ 9 |
| 失败 | 0 |
| 故意制造错误的命令 | 输出 `OK: 拒绝 QUERY+True` |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 默认值导致 `BUSINESS` 端点过 `__post_init__`,但实际是 `QUERY` | 默认值是**短期**兜底;PR-C 推动业务标注后消除 |
| `@final` 不阻止运行时继承(只拦 mypy) | 由 `type(spec) is EndpointSpec` 严格匹配在 core.py 保证 |
| frozen 字段在子类被改 | `@final` + 现有 core.py 严格匹配,子类不参与 collect |

---

## 5. 与后续 PR 的衔接

- **PR-C**(fin 单轨化):31 端点全部显式标 `category` + `mutates_state`,本 PR 的默认值兜底逐步消除
- **PR-D2**(`FieldBinding` 落地):`category` 字段会被 `FieldBinding` 消费(AI skill 用 category 排调用顺序)
- **PR-D4**(`field_bindings` 批量化):referential integrity check 会用 `category` 区分"写操作"和"读操作"
- **Phase 4**(CT 主动保活):依赖本 PR 的 `category` + `mutates_state` 可靠(设计 §5)
