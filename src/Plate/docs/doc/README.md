# doc 模块(`Plate/doc.py`)

> 本文档详细描述 `Plate/doc.py` 中的**每一个公开/内部常量、类、函数、
> 方法**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该
> 模块的所有行为细节与设计动机。

---

## 1. 模块定位

`doc.py` 是 Plate 子系统的**L2 字段**(人类注释)描述层。它解决的核心
问题:

> **契约模型除了"机器可读的 L1 字段"(method / path / request 模型等)
> 之外,还有"只有人才能写的 L2 字段"(限流、时区、前置条件)。这
> 两类数据应该物理解耦,review pipeline 应该分开。**

它暴露的核心是 `EndpointDoc` 数据类。每个 service 子包的
`dannotations/__init__.py` 里以 `path → EndpointDoc` 字典的形式存储
该 service 的所有 L2 注释。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
Plate 端点的人类注释(L2 字段,文档元数据)。

对应设计:PLATE_DESIGN.md §2.3 + PR-D3 §2.2。

关键约束(对应设计 §4 "L1/L2 物理解耦"):
- L1 = ``Plate.spec.EndpointSpec``(机器可再生,本文件**不**依赖 spec 即可 import)
- L2 = ``Plate.doc.EndpointDoc``(人工写,独立 review)
- 物理上与 spec 分离:``Plate.spec`` 不 import ``Plate.doc``;反之亦然
- summary ≤ 120 字符(强制,超长 AI 截断失真)
- 所有 list-like 字段用 tuple(满足 frozen 不可变,见 §2.2)
```

---

## 3. 依赖关系

```python
from dataclasses import dataclass
from typing import final
```

**为什么这么依赖:**
- `dataclasses.dataclass` — 构造 `EndpointDoc` 不可变数据类。
- `typing.final` — 给 `EndpointDoc` 加 `@final` 防继承。

**重要的反向依赖约束:**
- `doc.py` **不** import `spec` / `core` / `binding` / `facade` /
  `server` / `api_doc` / 任何 service 子包。
- 反过来 `spec.py` 也不 import `doc.py`。
- 这保证 L1 / L2 物理解耦 — 修改 L1 不会污染 L2,反之亦然。

---

## 4. 模块级常量:`_SUMMARY_MAX_LEN`

```python
_SUMMARY_MAX_LEN: int = 120
```

**为什么 120:**
> summary ≤ 120 字符(强制,超长 AI 截断失真)

- 经验值:120 字符是大多数 LLM 摘要窗口的"安全长度"(超过 120 字符
  的 summary 在 AI 总结时容易在 100-200 字符处被截断)。
- 给作者一个明确的硬约束,防止"我写了一大段,AI 只截了一半"。

**为什么下划线开头:** 模块私有(下划线开头),但**实际在 `__post_init__`
里被使用**。惯例违反(同 `_KNOWN_TRANSFORMS` / `_model_ref` 等) —
业务代码不应直接 import 这个常量,应通过构造 `EndpointDoc` 时让
`__post_init__` 兜底校验。

---

## 5. 核心数据类:`EndpointDoc`

### 5.1 类声明

```python
@final
@dataclass(frozen=True)
class EndpointDoc:
    """端点的人类注释(L2 字段)。"""
```

**为什么 `@final`:** `EndpointDoc` 是 L2 描述层,无继承需求;`@final`
防止业务代码"扩展"出奇怪的子类,污染渲染层(渲染层做 `isinstance(obj,
EndpointDoc)` 时不期望子类)。

**为什么 `@dataclass(frozen=True)`:**
- 不可变 — L2 注释是"事实",无修改需求。
- 可哈希 — 后续 L2 cache / dedup 可能用 set。
- 字段全部用 `tuple`(见下)— 进一步强化不可变。

### 5.2 字段详解

```python
summary: str
notes: tuple[str, ...] = ()
requires: tuple[str, ...] = ()
see_also: tuple[str, ...] = ()
```

#### 5.2.1 `summary: str`

- 一句话用途(必填,非空非空白,≤ 120 字符)。
- 喂 AI 总结 / Mock server / API doc 渲染。

**为什么必填:**
- L2 注释的"最小有效信息"是 summary。没有 summary 的 L2 注释等于
  没说。

**为什么 ≤ 120 字符:**
> 防止 AI 总结时被截断失真。

实测 LLM 摘要窗口在 100-200 字符处有截断风险。120 是经验值。

**为什么非空非空白:** 空白 summary 等于没写,直接 fail-fast。

#### 5.2.2 `notes: tuple[str, ...] = ()`

- 注意事项(限流 / 时序 / 单位 / 时区等)。
- 默认空 tuple。
- 列表性内容,每条是独立的 string。

**为什么用 `tuple` 而不是 `list`:**
- `frozen=True` 兼容(否则 tuple 中元素可改)。
- 序列化友好(JSON 数组)。
- 业务语义:"一组并行的注意事项",无顺序语义 — tuple 比 list 更
  严格地表达"作者承诺不变"。

**典型内容:**
```python
notes=(
    "限流:每用户 10 QPS",
    "时区:所有时间字段为 UTC+8",
    "单位:金额单位是分,展示时除以 100",
)
```

#### 5.2.3 `requires: tuple[str, ...] = ()`

- 前置条件(调此端点前必须满足的状态)。
- 默认空 tuple。

**典型内容:**
```python
requires=(
    "已登录",
    "订单属于当前用户",
    "已通过实名校验",
)
```

**为什么与 `notes` 分开:**
- `notes` 是"如何用"的提示;`requires` 是"能不能用"的硬条件。
- 渲染层可以分别渲染"注意事项"和"前置条件",让消费者一眼看到"哪些
  我必须先做完"。

#### 5.2.4 `see_also: tuple[str, ...] = ()`

- 相关端点 path 列表(供 AI 导航 / 知识图谱构建)。
- 默认空 tuple。
- 元素是 path 字符串(如 `"/api/order/order/orderDetail"`)。

**为什么是 path 字符串而不是 spec 引用:**
- L2 与 L1 物理解耦,L2 不直接持有 L1 对象(否则 L1 改 class 名
  / module 名时 L2 也要改)。
- 字符串引用允许 L2 在没有 L1 时也能存在(后续 service 接入"L2 先
  于 L1"也是允许的)。

### 5.3 `__post_init__` — 构造期校验

```python
def __post_init__(self) -> None:
    # 1. summary 强校
    if not self.summary or not self.summary.strip():
        raise ValueError("EndpointDoc: summary 不能为空或全空白")
    if len(self.summary) > _SUMMARY_MAX_LEN:
        raise ValueError(
            f"EndpointDoc: summary 长度 {len(self.summary)} 超过上限 "
            f"{_SUMMARY_MAX_LEN}(防止 AI 总结时被截断失真)。"
            f"实际内容: {self.summary!r}"
        )
    # 2. list-like 字段必须是 tuple(对应设计 §2.2 frozen 不变式)
    for fname in ("notes", "requires", "see_also"):
        v = getattr(self, fname)
        if not isinstance(v, tuple):
            raise TypeError(
                f"EndpointDoc.{fname} 必须是 tuple,实际 {type(v).__name__}"
            )
```

**算法步骤:**

1. **summary 必填校验:**
   - `not self.summary` — 空字符串(最常见情况)。
   - `not self.summary.strip()` — 全空白(`"   "` / `"\n\t"` 等)。
   - 任一为真 → `ValueError`。

2. **summary 长度校验:**
   - `len(self.summary) > _SUMMARY_MAX_LEN` → `ValueError`(带"防止
     AI 总结时被截断失真" + 实际内容,便于作者修)。

3. **list-like 字段类型校验:**
   - 遍历 `("notes", "requires", "see_also")` 三个字段名。
   - `isinstance(v, tuple)` — 必须是 tuple,否则 `TypeError`。
   - 这步专门防"作者用 list 而不是 tuple"的情况(frozen 不变式要求
     tuple)。

**为什么 summary 长度校验放在这里(`EndpointDoc`)而不是 L1 字段:
- L1(`EndpointSpec.summary`)的"长度"是文档元数据,无强约束(可能
  写长段描述)。
- L2(`EndpointDoc.summary`)是 AI 总结的"直接输入",长度敏感。
- 两个 summary 字段语义不同,各自校验。

**为什么用 `len(self.summary)` 而不是 `len(self.summary.encode("utf-8"))`:**
- Python 3 的 `str.len()` 是字符数(unicode code points),不是字节数。
- 字符数 vs 字节数:
  - 字符数:用户感知的"长度"(中文 1 字 = 1 字符)。
  - 字节数:存储层的"长度"(中文 1 字 = 3 bytes UTF-8)。
- AI 总结时按 token 计,与字符数 / 字节数都不直接对应(中文 1 字 ≈
  1-2 token,英文 1 word ≈ 1-2 token)。
- 选字符数 = 最接近"用户感知"的长度。

**为什么 tuple 校验在 `__post_init__` 而不是 dataclass 类型标注:**
- dataclass 的类型标注是"静态层"(给 IDE / mypy 看),**运行时**不
  强制。
- `__post_init__` 是"运行时层",业务代码绕过类型标注直接传 list 也
  会被这里兜住。

### 5.4 序列化(本期不实现)

L2 的 to_dict / from_dict 本期**没有**。理由:

- L1 的 `EndpointSpec` 有 `to_dict` — 因为 L1 走 manifest / 网络 /
  跨进程传输,需要序列化。
- L2 是"热数据"(对应 A3 冷热分层),只在 server 进程内用
  `dict[str, EndpointDoc]` 形态,不需要序列化。

未来如果需要把 L2 持久化或传输,再加 `to_dict` / `from_dict`。

---

## 6. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `EndpointDoc` | `@final @dataclass(frozen=True)` | `from Plate.doc import EndpointDoc` |
| `_SUMMARY_MAX_LEN` | `int = 120`(内部使用) | 实际在 `EndpointDoc.__post_init__` 里被使用 |

模块底部 `__all__`:

```python
__all__ = ["EndpointDoc", "_SUMMARY_MAX_LEN"]
```

---

## 7. 调用方典型代码示例

```python
# 1. 构造 L2 doc
from Plate.doc import EndpointDoc

doc = EndpointDoc(
    summary="按订单 ID 查询订单详情,返回订单全字段快照",
    notes=(
        "限流:每用户 10 QPS",
        "时区:所有时间字段为 UTC+8",
    ),
    requires=("已登录", "订单属于当前用户"),
    see_also=("/api/order/order/orderAdd",),
)

# 2. 与 service 的 dannotations 配合
# (Plate.fin.dannotations.__init__.py)
from Plate.doc import EndpointDoc

_DOCS: dict[str, EndpointDoc] = {
    "/api/order/order/orderDetail": EndpointDoc(
        summary="按订单 ID 查询订单详情,返回订单全字段快照",
        notes=("限流:每用户 10 QPS", "时区:所有时间字段为 UTC+8"),
        requires=("已登录",),
        see_also=("/api/order/order/orderAdd",),
    ),
}

# 3. summary 过长报错
EndpointDoc(summary="a" * 200)
# ValueError: EndpointDoc: summary 长度 200 超过上限 120
```

---

## 8. 不变量总结(本模块承诺的不变式)

1. **不可变**:`frozen=True` 让 doc 实例在构造后无法被修改。
2. **不可继承**:`@final` 装饰器禁止任何类继承 `EndpointDoc`。
3. **summary 必填非空白**:`__post_init__` 强校,空 / 全空白 → raise。
4. **summary ≤ 120 字符**:`__post_init__` 强校,超长 → raise(带
   "防止 AI 总结时被截断失真" 提示)。
5. **list-like 字段必须是 tuple**:`__post_init__` 强校,list → raise
   (防 frozen 不变式被破坏)。
6. **L1/L2 物理解耦**:`doc.py` 不 import `spec.py`,反之亦然。

---

## 9. 设计权衡

| 决策 | 取舍 |
|---|---|
| summary 长度上限 120 | 经验值 — LLM 摘要窗口的安全长度;过长会失真 |
| list-like 字段用 tuple | frozen 不变式 + 序列化友好 + "作者承诺不变"语义 |
| 字符数 vs 字节数 | 字符数更接近"用户感知";字节数更精确但作者无感 |
| 不做 to_dict / from_dict | L2 是热数据,不需要序列化;未来按需加 |
| summary 与 L1 的 summary 独立 | L1 是文档元数据(可长),L2 是 AI 总结直接输入(限长) |
| 物理独立于 L1 | 防止 L1 重新生成时覆盖 L2 注释 |
