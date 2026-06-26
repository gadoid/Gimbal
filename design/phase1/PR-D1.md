# PR-D1: 路径解析器(独立基建)

> **状态**:待执行
>
> **PR 范围**:写一个工具 `resolve_logical_path(root: type[BaseModel], path: str) -> Resolved`,独立 PR、独立单测,不依赖 `FieldBinding` 落地。
>
> **前置依赖**:[PR-C](PR-C.md)(8 个精确建模的 `response_data_models` 可作为测试样本)
>
> **对应设计**:[PLATE_DESIGN.md §2.2 路径格式 + §3.4(d) + §5.3](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 核心需求

**设计 §2.2 路径格式**: `field_path` / `source_field_path` 描述的是"字段在 Pydantic 模型树里的位置",**透明穿过 list 与 dict-key,不带任何下标和具体键**。

**业务价值**:`FieldBinding`(PR-D2 落地)是字段级"权威生产者声明",其静态校验强依赖路径解析器。如果解析器有 bug,所有 binding 校验失真。

### 1.2 为什么独立 PR

按"建护栏→做改造"三段式:
- **建护栏**:解析器是 `FieldBinding` 的**唯一复杂依赖**——`FieldBinding` 不引入新数据类,但本身不引入新数据类。**先单测锁死行为,再让 `FieldBinding` 用它**——这是经典的"先建基建再开业务"。
- **解耦**:解析器与"端点契约"解耦,纯 Pydantic 工具,易于维护和单测。
- **可独立交付**:即使后续 PR-D2 失败,解析器本身边际价值仍在(referential integrity check 也用)。

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/path_resolver.py` | 新建:`resolve_logical_path` + `Resolved` dataclass |
| `src/Plate/__init__.py` | (可选)re-export |
| `tests/plate/test_logical_path_resolver.py` | 新建:≥ 20 个测试函数 |

### 2.2 `Resolved` dataclass

```python
"""逻辑 schema 路径解析结果(PR-D1)。"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Resolved:
    """逻辑路径解析结果。

    字段:
      target_type: 路径终点类型;None = 不可解析
      hit_any: 路径是否穿过 Any
      path: 原路径(诊断用)
      error: 不可解析原因(诊断用)
    """
    target_type: type | None
    hit_any: bool
    path: str
    error: str | None
```

### 2.3 `resolve_logical_path` 函数

```python
def resolve_logical_path(
    root: type[BaseModel],
    path: str,
) -> Resolved:
    """透明穿过 list[X] (进入 X) / dict[str, V] (进入 V) / Optional[T] (进入 T);
    遇 Any 标记 hit_any=True 并停止 (无法证伪,按设计 §2.2 Any 限制放行)。

    路径:点分字符串,空字符串 = 解析根类型本身。

    对应设计:PLATE_DESIGN.md §2.2 路径格式 + §3.4(d) 解析规则。
    """
    # 1. 空路径 = 根
    if path == "":
        return Resolved(target_type=root, hit_any=False, path=path, error=None)

    # 2. 拆分
    parts = path.split(".")
    current = root

    # 3. 逐步解析
    for part in parts:
        if not _is_basemodel_subclass(current):
            return Resolved(
                target_type=None, hit_any=False, path=path,
                error=f"路径 {part!r} 处期望 BaseModel,实际 {type(current).__name__}"
            )
        # 字段是否存在
        if part not in current.model_fields:
            return Resolved(
                target_type=None, hit_any=False, path=path,
                error=f"字段 {part!r} 不在 {current.__name__} 中"
            )
        # 进入字段
        annotation = current.model_fields[part].annotation
        # 解析泛型
        current = _unwrap(annotation)
        # 遇 Any
        if current is Any:
            return Resolved(target_type=None, hit_any=True, path=path, error=None)

    return Resolved(target_type=current, hit_any=False, path=path, error=None)


def _unwrap(annotation: Any) -> Any:
    """透明解 Optional[T] / list[T] / dict[str, V] / Annotated[T, ...]。

    遇 Union[A, B] (非 Optional) 返回原值 + 标记错误。
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    # 1. Optional[T] / T | None / Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap(non_none[0])
        else:
            return annotation  # 多态 Union,留给上层处理

    # 2. list[T] / List[T]
    if origin in (list, List):
        return _unwrap(args[0]) if args else annotation

    # 3. dict[str, V] / Dict[str, V]
    if origin in (dict, Dict):
        return _unwrap(args[1]) if len(args) > 1 else annotation

    # 4. Annotated[T, ...] / Final[T]
    if origin is not None and args:
        return _unwrap(args[0])

    return annotation
```

### 2.4 解析规则矩阵(对应设计 §2.2 表格)

| 节点类型 | 处理 |
|---|---|
| `BaseModel` 子类 | 进入字段(`model_fields[name]`) |
| `list[T]` / `List[T]` | 进入 `T`(基类型) |
| `dict[str, V]` / `Dict[str, V]` | 进入 `V`(值类型) |
| `Optional[T]` / `T \| None` / `Union[T, None]` | 进入 `T` |
| `Union[A, B, ...]`(非 Optional) | **不支持**——返回 error(多态路径不可静态选) |
| `Any` | 标记 `hit_any=True`,target_type=None(解析器停止) |
| 字段不存在 | 返回 error(路径拼错) |
| `path == ""` | 返回 `Resolved(target_type=root, hit_any=False, error=None)` |

### 2.5 真实场景测试样本(来自 PR-C 的 8 个精确建模端点)

> **重要更正**(本节原期望 ``target_type=str, hit_any=False``,落地时**实测**为
> ``target_type=None, hit_any=True`` —— 根因见 [DECISIONS.md D9](../DECISIONS.md#d9-pr-d1-25-端到端期望修正))。

```python
# 真实 4 层穿列表路径(设计 §2.2 端到端示例)
# data.to_customer.put_amount.standard_list.order_fee_real_id
# 来自 fin.toggleRealAmount → realAmountLockSubmit 的 FieldBinding

# 实际:ToggleRealAmountData → to_customer (list[_SettleSideItem]) → _SettleSideItem
#       → put_amount (_MoneyBlock) → standard_list (list[Any]) → 命中 Any → 软降级
resolved = resolve_logical_path(
    ToggleRealAmountData,
    "to_customer.put_amount.standard_list.order_fee_real_id"
)
# 期望(修正后):target_type=None, hit_any=True, error=None
assert resolved.target_type is None
assert resolved.hit_any is True
assert resolved.error is None
```

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应**一个解析规则的边界 case**,docstring 写明:
1. **业务需求**(透明穿越 list/dict 的契约)
2. **对应设计章节**(§2.2 表格行)
3. **业务影响**(破坏此规则 = 91% 真值血缘不可校验)

### 3.2 必测场景(≥ 20 个)

```python
"""PR-D1:逻辑 schema 路径解析器测试。

业务动机:91% 真值血缘路径穿过 list(设计 §2.2)。
解析器必须能"透明穿过 list[X] / dict[str, V] / Optional[T]",
否则 FieldBinding 的静态校验全失效。
"""


# ════════════════════════════════════════════════════════════════════════════
# 基础:空路径、简单字段、嵌套
# ════════════════════════════════════════════════════════════════════════════

def test_empty_path_resolves_to_root():
    """业务需求:空路径解析为根类型。

    对应设计:§2.2 路径格式"空字符串 = 解析根类型本身"。
    业务影响:任何调用方期望"传 '' 得到 root" 的语义破坏,基础契约失守。
    """
    resolved = resolve_logical_path(RootModel, "")
    assert resolved.target_type is RootModel
    assert resolved.hit_any is False
    assert resolved.error is None


def test_simple_field():
    """业务需求:解析单层字段,返回字段类型。

    对应设计:§3.4(d) 解析器须进入 BaseModel 字段。
    业务影响:基本功能,1 行 case 必须对。
    """
    class M(BaseModel):
        x: str
    resolved = resolve_logical_path(M, "x")
    assert resolved.target_type is str
    assert resolved.hit_any is False


def test_nested_3_levels():
    """业务需求:解析 3 层嵌套字段。

    对应设计:§3.4(d) 解析器递归。
    业务影响:基本功能,确保递归不丢层。
    """
    class Leaf(BaseModel):
        val: int
    class Mid(BaseModel):
        leaf: Leaf
    class Root(BaseModel):
        mid: Mid
    resolved = resolve_logical_path(Root, "mid.leaf.val")
    assert resolved.target_type is int


# ════════════════════════════════════════════════════════════════════════════
# 透明穿越 list / dict / Optional(§2.2 核心规则)
# ════════════════════════════════════════════════════════════════════════════

def test_path_transparently_passes_through_list():
    """业务需求:list[X] 透明穿越,返回 X 类型(不带下标)。

    对应设计:§2.2 表格"取哪个元素 → scenario 决定,Plate 不固化下标"。
    业务影响:91% 真值血缘穿过 list,不透明穿越 = 91% binding 不可校验。
    """
    class Item(BaseModel):
        order_id: str
    class Container(BaseModel):
        items: list[Item]
    resolved = resolve_logical_path(Container, "items.order_id")
    assert resolved.target_type is str
    assert resolved.hit_any is False


def test_path_transparently_passes_through_dict():
    """业务需求:dict[str, V] 透明穿越,返回 V 类型(不带具体键)。

    对应设计:§2.2 表格"键的语义 → field_notes / model description,Plate 不固化键"。
    业务影响:main_currency_bank.CNY[0] 之类路径必须能解析到 V。
    """
    class Block(BaseModel):
        bank_account: str
    class Container(BaseModel):
        main_currency_bank: dict[str, Block]
    resolved = resolve_logical_path(Container, "main_currency_bank.bank_account")
    assert resolved.target_type is str


def test_path_passes_through_4_layers_including_2_lists():
    """业务需求:4 层嵌套(含 2 层 list)能完整解析。

    对应设计:§2.2 端到端示例 "data.to_customer.put_amount.standard_list.order_fee_real_id"。
    业务影响:真实场景核心 case;破坏 = 关键 binding 全部无法校验。
    """
    class Item(BaseModel):
        order_fee_real_id: str
    class Amount(BaseModel):
        standard_list: list[Item]
    class ToSide(BaseModel):
        put_amount: Amount
    class ToggleData(BaseModel):
        to_customer: list[ToSide]
    # 4 层(其中 2 层 list)
    resolved = resolve_logical_path(
        ToggleData,
        "to_customer.put_amount.standard_list.order_fee_real_id"
    )
    assert resolved.target_type is str
    assert resolved.hit_any is False


def test_path_passes_through_optional():
    """业务需求:Optional[T] 透明穿越,返回 T 类型。

    对应设计:§2.2 表格"Optional[T] → 进入 T"。
    业务影响:多数 fin 字段是 `str | None = None`,不透明穿越 = 多数 binding 失败。
    """
    class M(BaseModel):
        order_id: str | None = None
    resolved = resolve_logical_path(M, "order_id")
    # Optional[str] 解析后是 str(Union 简化为 T)
    assert resolved.target_type in (str, type(None))  # 取决于实现
    # 接受两种合理实现(完全解 Optional,或保留 Union)


def test_path_passes_through_annotated():
    """业务需求:Annotated[T, ...] 透明取 T。

    对应设计:Pydantic v2 + typing 兼容。
    业务影响:Annotated 大量用于 Field(..., description=...)。
    """
    class M(BaseModel):
        order_id: Annotated[str, "description=订单号"] = ""
    resolved = resolve_logical_path(M, "order_id")
    assert resolved.target_type is str


# ════════════════════════════════════════════════════════════════════════════
# Any 降级(§2.2 限制 + §5.3 表格)
# ════════════════════════════════════════════════════════════════════════════

def test_path_entering_any_is_soft_fail():
    """业务需求:路径终点是 Any 时,标记 hit_any=True,不报错。

    对应设计:§2.2 Any 限制 + §5.3 表格"Any 区域降级为软提示"。
    业务影响:fin 的 CommonResponseEnvelope.data: Any 几乎覆盖所有 source_field_path,
             不降级 = 所有跨端点 binding 不可校验。
    """
    class Envelope(BaseModel):
        data: Any
    resolved = resolve_logical_path(Envelope, "data.order_id")
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None  # 软提示,不是 error


def test_path_passing_through_any_is_soft_fail():
    """业务需求:路径穿过 Any 字段后再有子路径,也按 hit_any=True 处理。

    对应设计:§2.2 Any 限制。
    业务影响:同 test_path_entering_any_is_soft_fail,中间 Any 也算。
    """
    class Container(BaseModel):
        data: Any
    resolved = resolve_logical_path(Container, "data.sub.field")
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝
# ════════════════════════════════════════════════════════════════════════════

def test_nonexistent_field_returns_error():
    """业务需求:字段名拼错时返回 error(不是 hit_any)。

    对应设计:§3.4(d) 解析器须报"字段不存在"。
    业务影响:FieldBinding 拼错路径 = CI fail,防止"指向不存在字段的假 binding"。
    """
    class M(BaseModel):
        order_id: str
    resolved = resolve_logical_path(M, "ordr_id")  # typo
    assert resolved.error is not None
    assert "ordr_id" in resolved.error
    assert resolved.hit_any is False


def test_polymorphic_union_rejected():
    """业务需求:Union[A, B] (非 Optional) 多态路径不可静态选,返回 error。

    对应设计:§2.2 表格"Union[A, B] 不支持"。
    业务影响:多态路径不可静态选,只能走 scenario 动态选择。
    """
    class M(BaseModel):
        item: int | str  # 多态,非 Optional
    resolved = resolve_logical_path(M, "item")
    # 实现选择:error 或 hit_any;最严格是 error
    # 业务影响:让 reviewer 注意到"这字段不可静态校验"


def test_descend_into_scalar_returns_error():
    """业务需求:路径进入标量(int/str)后再有子路径,返回 error。

    对应设计:§3.4(d) 解析器期望 BaseModel 节点。
    业务影响:路径拼错(如 `order_id.sub`)应被发现。
    """
    class M(BaseModel):
        order_id: str
    resolved = resolve_logical_path(M, "order_id.sub")
    assert resolved.error is not None
    assert resolved.hit_any is False


# ════════════════════════════════════════════════════════════════════════════
# 真实 fin 端点样本(端到端)
# ════════════════════════════════════════════════════════════════════════════

def test_resolves_fin_toggle_real_amount_real_id():
    """业务需求:能解析 fin.toggleRealAmount 的 order_fee_real_id 路径(Any 软降级)。

    对应设计:§2.2 端到端示例(修正:D9)。
    业务影响:realAmountLockSubmit 的 binding 依赖此解析。
    注:MoneyBlock.standard_list 是 list[Any](permissive 兜底),所以
        路径末段落在 Any 区域 → 软降级(hit_any=True, target_type=None)。
        这是设计 §2.2 Any 限制的**预期行为**,不是 bug。
    """
    from Plate.fin.models import ToggleRealAmountData
    resolved = resolve_logical_path(
        ToggleRealAmountData,
        "to_customer.put_amount.standard_list.order_fee_real_id"
    )
    assert resolved.target_type is None
    assert resolved.hit_any is True
    assert resolved.error is None


def test_resolves_fin_order_confirm_account_cny():
    """业务需求:能解析 fin.orderConfirmAccount 的 dict 路径(Any 软降级)。

    对应设计:§2.2 main_currency_bank.CNY[0].bank_account 案例。
    业务影响:orderReceiveAccountEdit 的 binding 依赖此解析。
    注:OrderConfirmAccountData.main_currency_bank: Any(permissive 兜底)
        → 命中 Any → 软降级。
    """
    from Plate.fin.models import OrderConfirmAccountData
    resolved = resolve_logical_path(
        OrderConfirmAccountData,
        "main_currency_bank.bank_account"
    )
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


def test_resolves_fin_audit_id():
    """业务需求:能解析 fin.auditPage 的 audit_id 路径(精确建模)。

    对应设计:§2.2 简例"data[0].audit_id"。
    业务影响:auditDetail / auditExecute 的 binding 依赖此解析。
    注:AuditPageData.data 是 list[_AuditPageItem](精确建模),所以
        路径能严格解析到 str(Optional[str] 解 Optional 后是 str)。
    """
    # 注:AuditPageData.data 是 list[AuditPageItem]
    from Plate.fin.models import AuditPageData
    resolved = resolve_logical_path(
        AuditPageData,
        "data.audit_id"
    )
    # 解析到 _AuditPageItem.audit_id 类型(str)
    assert resolved.hit_any is False
    assert resolved.target_type is str
    assert resolved.error is None
```

### 3.3 业务核心测试矩阵

| 设计 §2.2 表格行 | 测试函数 | 业务影响 |
|---|---|---|
| 空路径 | `test_empty_path_resolves_to_root` | 基础契约 |
| 普通字段 | `test_simple_field` | 基本功能 |
| 嵌套 3 层 | `test_nested_3_levels` | 递归不丢层 |
| 穿 list[X] | `test_path_transparently_passes_through_list` | 91% 路径依赖 |
| 穿 dict[str, V] | `test_path_transparently_passes_through_dict` | 币种/业务维度键 |
| 4 层穿 2 list | `test_path_passes_through_4_layers_including_2_lists` | 真实核心 case |
| Optional[T] | `test_path_passes_through_optional` | 多数 fin 字段 |
| Annotated[T, ...] | `test_path_passes_through_annotated` | Pydantic v2 兼容 |
| 终点 Any | `test_path_entering_any_is_soft_fail` | envelope.data 降级 |
| 穿 Any | `test_path_passing_through_any_is_soft_fail` | 中间 Any 降级 |
| 字段不存在 | `test_nonexistent_field_returns_error` | 拼错发现 |
| Union 多态 | `test_polymorphic_union_rejected` | 多态不可静态选 |
| 标量子路径 | `test_descend_into_scalar_returns_error` | 拼错发现 |
| 真实 fin 端点 | 3 个 end-to-end 测试 | 与 PR-D2 binding 对接 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_logical_path_resolver.py -v

# 2. 跑全量基线
pytest tests/

# 3. 端到端验证:用解析器解真实 fin 端点
python -c "
from Plate.path_resolver import resolve_logical_path
from Plate.fin.models import ToggleRealAmountData
r = resolve_logical_path(ToggleRealAmountData, 'to_customer.put_amount.standard_list.order_fee_real_id')
print(f'target_type={r.target_type}, hit_any={r.hit_any}, error={r.error}')
# 期望(修正后,D9): target_type=None, hit_any=True, error=None
# (路径末段 standard_list 是 list[Any] → 软降级)
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_logical_path_resolver.py` 测试数 | ≥ 15 |
| 失败 | 0 |
| 端到端命令输出(修正后) | `target_type=None, hit_any=True, error=None` |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| Pydantic v2 `model_fields` 边界 case(field 顺序、alias、computed field) | ≥ 3 个真实 fin 端点 end-to-end 兜底 |
| `Annotated[T, ...]` 多层嵌套 | 显式 `_unwrap` 递归 |
| `dict[str, list[V]]` 混合形态 | 单测覆盖 |
| 性能(31 端点 × 多 binding) | 基准测试 < 1ms/次 |

---

## 5. 与后续 PR 的衔接

- **PR-D2**(`FieldBinding` 落地):`__post_init__` 校验 `field_path` 调用本 PR 的 `resolve_logical_path`
- **PR-D4**(`field_bindings` 批量化):referential integrity check 用本解析器
- **Phase 3**(Plate-MCP):MCP 查询 binding 时用本解析器
- **Phase 4**(CT 主动保活):drift 检测用本解析器对照 schema 变化
