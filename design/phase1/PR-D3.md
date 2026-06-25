# PR-D3: EndpointDoc L2 物理解耦

> **状态**:待执行
>
> **PR 范围**:新增 `EndpointDoc` 数据类 + **L1/L2 物理分文件存储**(spec 自动生成,dannotations 人工写)。**不要求存量 endpoint 必须补注释**(后续 PR 渐进补)。
>
> **前置依赖**:[PR-D2](PR-D2.md)(FieldBinding 落地) + [PR-C](PR-C.md)(fin 已显式标 category)。
>
> **关键设计**:L1(spec)与 L2(dannotations)**物理分离但逻辑配对**——同一个 endpoint 有两个文件,review pipeline 能 detect 不配对。
>
> **对应设计**:[PLATE_DESIGN.md §2.3 + §4 + §7](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:当前 fin endpoint 的"业务注释"(用途 / 注意事项 / 限流规则 / 调用前置条件)写在 docstring 里。问题是:
- docstring 跟着代码进 git,代码重构时注释被 IDE 误改
- docstring 是"散文",AI 无法结构化消费
- spec.py 是 L1(机器可再生),注释是 L2(必须人确认)——**混在一起 = L1 重生成时把 L2 也冲掉**

**设计 §4**:
> L1 与 L2 必须**物理分离**——L1 可被代码 review pipeline 自动重生,L2 必须人工写且独立 review。

### 1.2 字段设计(`EndpointDoc`)

| 字段 | 类型 | 业务含义 |
|---|---|---|
| `summary` | `str` | 一句话用途(必填, ≤120 字符) |
| `notes` | `tuple[str, ...]` | 注意事项(限流 / 时序 / 单位等) |
| `requires` | `tuple[str, ...]` | 前置条件(调此端点前必须满足的状态,字符串描述) |
| `see_also` | `tuple[str, ...]` | 相关端点 path(供 AI 导航) |

### 1.3 关键决策

- **物理分文件**:`fin/__init__.py` 用 `from .specs import *` 自动收集 L1;L2 写在 `fin/dannotations/__init__.py`(dannotations = **doc annotations**,与 spec 物理分离)。
- **不强制存量**:`dannotations/__init__.py` 文件可空,review pipeline 只在"声明了 dannotation 但 spec 找不到对应 endpoint"时报错(对称性)。
- **summary 长度上限 120**:超长 = AI 总结时被截,失去意义。`__post_init__` 强校。

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/doc.py` | 新建:`EndpointDoc` 数据类 + 模块级 validator |
| `src/Plate/__init__.py` | re-export `EndpointDoc` |
| `src/Plate/fin/dannotations/__init__.py` | 新建:L2 注释存储(本 PR 只建空壳,内容由后续 PR 补) |
| `tests/plate/test_doc.py` | 新建:本 PR 专属测试(≥10 个) |
| `tests/plate/test_invariants.py` | 加不变量:L1/L2 对称性(有 spec 无 doc 不报错;有 doc 无 spec 报错) |

### 2.2 `EndpointDoc` 数据类定义

```python
# src/Plate/doc.py
from __future__ import annotations
from dataclasses import dataclass
from typing import final

_SUMMARY_MAX_LEN = 120


@final
@dataclass(frozen=True)
class EndpointDoc:
    """端点的人类注释(L2 字段)。

    对应设计:PLATE_DESIGN.md §2.3

    关键约束:
    - 物理上与 spec.py 分离(spec 是 L1 自动生成,doc 是 L2 人工写)
    - summary ≤ 120 字符(强制,超长 AI 截断失真)
    - 所有 list-like 字段用 tuple(满足 frozen 不可变)
    """

    summary: str
    notes: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    see_also: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # summary 强校
        if not self.summary or not self.summary.strip():
            raise ValueError("EndpointDoc: summary 不能为空或全空白")
        if len(self.summary) > _SUMMARY_MAX_LEN:
            raise ValueError(
                f"EndpointDoc: summary 长度 {len(self.summary)} 超过上限 "
                f"{_SUMMARY_MAX_LEN}(防止 AI 总结时被截断失真)。"
                f"实际内容: {self.summary!r}"
            )
        # 字段类型校验(tuple 而非 list)
        for fname in ("notes", "requires", "see_also"):
            v = getattr(self, fname)
            if not isinstance(v, tuple):
                raise TypeError(
                    f"EndpointDoc.{fname} 必须是 tuple, 实际 {type(v).__name__}"
                )
```

### 2.3 `fin/dannotations/` 目录结构

```
src/Plate/fin/
├── __init__.py            # 现有:自动收集 spec(L1)
├── models.py              # 现有:Pydantic 模型
├── specs/                 # 现有或将由 review pipeline 生成:L1 spec 落地
│   └── ...
└── dannotations/          # 新建:L2 人工注释
    ├── __init__.py        # 暴露 _DOCS: dict[str, EndpointDoc] by path
    └── ...
```

### 2.4 `dannotations/__init__.py` 设计

```python
# src/Plate/fin/dannotations/__init__.py
"""fin 服务的人工注释(L2)。

与 spec(L1,自动生成)物理分离。
key 是 EndpointSpec.path(全路径,如 "/api/order/order/orderDetail")。

PR-D3 本文件为空壳;后续 PR 按 endpoint 渐进补注释。
PR-EOP review pipeline 会校验"L1/L2 对称性"(有 spec 无 doc 允许;有 doc 无 spec 报错)。
"""
from __future__ import annotations
from Plate.doc import EndpointDoc

# 结构: path → EndpointDoc
_DOCS: dict[str, EndpointDoc] = {
    # 例(后续 PR 补):
    # "/api/order/order/orderDetail": EndpointDoc(
    #     summary="按订单 ID 查询订单详情,返回订单全字段快照",
    #     notes=("限流:每用户 10 QPS", "时区:所有时间字段为 UTC+8"),
    #     requires=("已登录", "订单属于当前用户"),
    #     see_also=("/api/order/order/addOrder",),
    # ),
}

# 暴露给 review pipeline / AI 消费
__all__ = ["EndpointDoc", "_DOCS"]


def get_doc(path: str) -> EndpointDoc | None:
    """按 path 查 L2 doc;不存在返回 None。"""
    return _DOCS.get(path)
```

### 2.5 不变量(对称性检查)

```python
# 在 tests/plate/test_invariants.py 加:
def test_invariant_l1_l2_symmetry():
    """业务不变量:有 L2 doc 必有 L1 spec。

    对应设计:§4 L1/L2 物理解耦
    业务影响:doc 写给幽灵 endpoint = 文档库腐化,AI 误导。
    """
    from Plate.fin.dannotations import _DOCS
    from Plate.core import registry

    # 收集所有 fin endpoint path
    fin_paths = {
        key.path
        for key in registry._index
        if key.service == "fin"
    }

    # 对称性检查:doc 里的 path 必须在 spec 里
    for doc_path in _DOCS:
        assert doc_path in fin_paths, (
            f"dannotations 里有 {doc_path!r} 但 fin registry 找不到对应 spec。"
            f"可能 spec 已删除但 doc 残留。"
        )

    # 反向不强制:spec 里有 doc 不一定(本 PR 允许 spec 先有 doc 后补)
```

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
1. **业务需求**(L1/L2 分离的硬约束)
2. **对应设计章节**
3. **业务影响**(违反此约束的代价)

### 3.2 必测业务场景

```python
"""PR-D3:EndpointDoc L2 物理解耦测试。

业务动机:L1(spec,机器可再生)与 L2(doc,人工写)物理分离,防止 L1 重生成冲掉 L2。
本 PR 只验证 doc 类型 + dannotations 目录结构 + 对称性,不要求存量补注释。
"""


# ════════════════════════════════════════════════════════════════════════════
# EndpointDoc 自身
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_doc_minimal_constructs():
    """业务需求:只填 summary 可构造。

    对应设计:§2.2 字段默认值约定。
    业务影响:其他字段都必填 = 写注释成本太高,没人愿意写。
    """
    doc = EndpointDoc(summary="按订单 ID 查询订单详情")
    assert doc.summary == "按订单 ID 查询订单详情"
    assert doc.notes == ()
    assert doc.requires == ()
    assert doc.see_also == ()


def test_endpoint_doc_full_constructs():
    """业务需求:4 个字段都填时构造正常。

    对应设计:§2.2 字段定义。
    业务影响:此约束是 review pipeline 校验的前提。
    """
    doc = EndpointDoc(
        summary="按订单 ID 查询详情",
        notes=("限流:每用户 10 QPS", "时区:UTC+8"),
        requires=("已登录",),
        see_also=("/api/order/order/addOrder",),
    )
    assert len(doc.notes) == 2
    assert len(doc.requires) == 1
    assert len(doc.see_also) == 1


# ════════════════════════════════════════════════════════════════════════════
# summary 长度强校
# ════════════════════════════════════════════════════════════════════════════

def test_summary_too_long_raises():
    """业务需求:summary 长度 > 120 字符硬错。

    对应设计:§2.2 summary 长度上限。
    业务影响:超长 summary = AI 总结时被截,语义失真,后续看到残片误调用。
    """
    with pytest.raises(ValueError) as exc:
        EndpointDoc(summary="x" * 121)
    assert "120" in str(exc.value)


def test_summary_at_limit_constructs():
    """业务需求:summary 正好 120 字符可通过。

    对应设计:§2.2 边界值约定。
    业务影响:边界值误判(< 而非 ≤) = 卡死临界长度。
    """
    doc = EndpointDoc(summary="x" * 120)
    assert len(doc.summary) == 120


def test_summary_empty_or_whitespace_raises():
    """业务需求:summary 不能为空或全空白。

    对应设计:§2.2 summary 必填。
    业务影响:空 summary = 等于没注释,浪费一个文件。
    """
    with pytest.raises(ValueError):
        EndpointDoc(summary="")
    with pytest.raises(ValueError):
        EndpointDoc(summary="   \t\n  ")


# ════════════════════════════════════════════════════════════════════════════
# list-like 字段必须 tuple
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("field_name", ["notes", "requires", "see_also"])
def test_list_field_must_be_tuple(field_name):
    """业务需求:list-like 字段必须是 tuple(满足 frozen 不可变)。

    对应设计:§2.2 frozen 不变式。
    业务影响:接受 list = 可被外部 .append(),doc 被静默改写。
    """
    with pytest.raises(TypeError) as exc:
        EndpointDoc(summary="x", **{field_name: ["a", "b"]})  # type: ignore[arg-type]
    assert "tuple" in str(exc.value)


# ════════════════════════════════════════════════════════════════════════════
# frozen + @final 不变式
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_doc_frozen():
    """业务需求:EndpointDoc 不可写。

    对应设计:§2.2 frozen 约定。
    业务影响:可写 = 多线程下 doc 被静默改,误导 AI 消费。
    """
    doc = EndpointDoc(summary="x")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        doc.summary = "y"  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# dannotations 目录结构
# ════════════════════════════════════════════════════════════════════════════

def test_fin_dannotations_module_importable():
    """业务需求:fin/dannotations 模块可被 import(空壳)。

    对应设计:§2.3 物理分离约定。
    业务影响:目录不存在 = L2 注释无处存放,PR-D4 之后的注释补全无落地点。
    """
    import Plate.fin.dannotations
    assert hasattr(Plate.fin.dannotations, "_DOCS")
    assert isinstance(Plate.fin.dannotations._DOCS, dict)


def test_fin_dannotations_empty_initially():
    """业务需求:dannotations/_DOCS 初始为空(本 PR 不强制存量)。

    对应设计:本 PR 不强制存量标注。
    业务影响:若初始就预填所有 endpoint = 本 PR 范围爆炸,违背"渐进"原则。
    """
    from Plate.fin.dannotations import _DOCS
    # 本 PR 允许为空;后续 PR 渐进补
    # 这里不强 assert == 0(防 PR-D4 之前有补内容),只校验类型
    assert isinstance(_DOCS, dict)


def test_get_doc_returns_none_for_missing():
    """业务需求:get_doc 找不到时返回 None(不抛错)。

    对应设计:§2.4 get_doc 契约。
    业务影响:抛 KeyError = 消费方必须 try/except,API 难用。
    """
    from Plate.fin.dannotations import get_doc
    assert get_doc("/non/existent/path") is None


# ════════════════════════════════════════════════════════════════════════════
# 不变量聚合(L1/L2 对称性)
# ════════════════════════════════════════════════════════════════════════════

# 在 test_invariants.py 加(详见 §2.5):
# def test_invariant_l1_l2_symmetry():
#     ...
```

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 默认值兜底 | `test_endpoint_doc_minimal_constructs` | 写注释成本可控 |
| summary 长度强校 | `test_summary_too_long_raises` / `..._at_limit_...` / `..._empty_...` | 防 AI 截断失真 |
| tuple 约束 | `test_list_field_must_be_tuple` | 防 list 被外部改写 |
| frozen 不变式 | `test_endpoint_doc_frozen` | 线程安全 |
| 物理分离 | `test_fin_dannotations_module_importable` / `..._empty_initially_...` / `test_get_doc_returns_none_for_missing` | L1/L2 不混淆 |
| L1/L2 对称性 | `test_invariant_l1_l2_symmetry` | doc 不指向幽灵 endpoint |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_doc.py -v

# 2. 跑不变量聚合
pytest tests/plate/test_invariants.py::test_invariant_l1_l2_symmetry -v

# 3. 跑全量基线
pytest tests/  # 应 ≥ 196 + 10 = 206 个测试全过

# 4. 故意制造"summary 超长"验证断言
python -c "
from Plate.doc import EndpointDoc
try:
    EndpointDoc(summary='x' * 121)
    print('FAIL: 应抛 ValueError')
except ValueError as e:
    print(f'OK: 拒绝超长 summary, 信息: {e}')
"

# 5. 验证 L1/L2 物理分离
python -c "
from Plate.fin.dannotations import _DOCS, get_doc
print(f'_DOCS 类型: {type(_DOCS).__name__}, 大小: {len(_DOCS)}')
print(f'get_doc 缺失返回: {get_doc(\"/no/such\")}')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_doc.py` 测试数 | ≥ 10 |
| 失败 | 0 |
| 故意制造 summary 超长 | 输出 `OK: 拒绝超长 summary` |
| `dannotations` 目录存在 | 是 |
| `_DOCS` 是 dict | 是 |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| L1 重生成时误删 L2 | L1/L2 物理分文件;review pipeline 校验"有 doc 无 spec"报错 |
| 存量 31 端点无注释 | 本 PR 允许为空,后续 PR 渐进补 |
| summary 长度 120 字符不够 | 后续可调,本 PR 先立规 |

---

## 5. 与后续 PR 的衔接

- **PR-D4**(首批 binding 批量化):与本 PR 并行;D4 改 spec 字段,D3 改 doc 字段,两者互不阻塞
- **PR-EOP**(收口 review pipeline):review pipeline 强制扫描 `dannotations/_DOCS` 对称性
- **Phase 2**(service 化):AI skill 用 `get_doc(path)` 拿 L2 注释作为提示词补充
- **Phase 4**(CT 主动保活):CT 探测时可读 L2 `requires` 字段,跳过"前置不满足"的端点