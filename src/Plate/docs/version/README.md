# version 模块(`Plate/version.py`)

> 本文档详细描述 `Plate/version.py` 中的**每一个公开/内部常量、类、函数、
> 方法**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模
> 块的所有行为细节与设计动机。

---

## 1. 模块定位

`version.py` 是 Plate 子系统的**版本类型**。它解决的核心问题:

> **如何在 Plate 内部用一份强类型、可哈希、byte-equal 的数据,表达
> "major.minor.patch"形式的语义化版本?**

它暴露的核心是 `PlateVersion` 数据类。这是 `manifest` / `facade` /
`server` 等多个模块的"版本"概念的源头。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
版本类型(语义化版本,major.minor.patch)。

对应设计:PR-2.0 §2.2 + PLATE_EVOLUTION §3 Phase 2。

职责:定义 + 解析 + 序列化 + 字符串化。
本模块**不**依赖 spec / binding / core,纯数据类型。

业务价值:
  * 客户端 pin 某版本,保证执行可复现(同一份 scenario 在不同时间跑,依赖同一份契约字节)
  * 服务端按版本路由:老客户端请求旧版本仍可服务
  * MCP 协议升级的硬前提(Phase 3)
```

---

## 3. 依赖关系

```python
import re
from dataclasses import dataclass
from typing import final
```

**为什么这么依赖:**
- `re` — 用正则解析 `"major.minor.patch"` 字符串。
- `dataclasses.dataclass` — 构造 `PlateVersion` 不可变数据类。
- `typing.final` — 给 `PlateVersion` 加 `@final` 防继承。

**重要的反向依赖约束:**
- `version.py` 是"叶子工具",**不** import 任何其他 Plate 子模块。
- 这保证 `version` 可以被 `manifest` / `facade` / `server` / 任何
  模块无副作用引用,自身不引入循环依赖。

---

## 4. 模块级常量:`_VERSION_RE`

```python
_VERSION_RE: re.Pattern[str] = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
```

**字段语义:**
- 严格匹配 `major.minor.patch`,三段都必须是非负整数。
- 用 `^` 和 `$` 锚定(整串匹配,不是子串匹配)。
- 编译一次,模块级缓存(`re.compile` 的结果自动缓存,但显式 `compile`
  更明确)。

**为什么不接受更宽松的格式(如 `v1.2.3` / `1.2.3-rc1` / `1.2`):**
- Plate 的版本号用于 manifest 校验、协议路由等"硬契约"场景。
- `v` 前缀、pre-release 标签、缺段都是"不严谨"信号 — 一律 fail-fast。
- semver 完整规范(带 pre-release / build metadata)目前用不到,不做
  YAGNI 扩展。

**为什么不限制位数(如 `0-999`):**
- 业务上 minor / patch 超过 999 已经非常少见,真要超了再加。
- 简单的 `\d+` 比 `(\d{1,3})` 更通用,作者心智负担小。

---

## 5. 核心数据类:`PlateVersion`

### 5.1 类声明

```python
@final
@dataclass(frozen=True)
class PlateVersion:
    """语义化版本。frozen=True 保证 byte-equal / 可哈希。"""
```

**为什么 `@final`:** `PlateVersion` 是版本号,无继承需求;`@final` 防
止业务代码"扩展"出奇怪的子类(否则 `isinstance(v, PlateVersion)` 检查
会污染)。

**为什么 `@dataclass(frozen=True)`:**
- 不可变 — 版本号是"事实",无修改需求。
- 可哈希 — 后续 set / dict key 都需要。
- byte-equal — `frozen=True` 的 dataclass `__eq__` 默认逐字段比较
  (三个 int 字段,Python int 比对稳定)。

### 5.2 字段详解

```python
major: int
minor: int
patch: int
```

**字段语义(对应 semver):**
- `major: int` — 破坏性变更(协议升级,需客户端主动升级)。
- `minor: int` — 兼容性新增(端点新增、字段新增)。
- `patch: int` — 兼容性修复(注释、默认值调整)。

**为什么只有三段、不接受 pre-release / build metadata:**
- 简单 — Plate 当前用途不需要 semver 完整规范。
- YAGNI — 真要 pre-release 标签(如 `1.0.0-rc1`)再加,本期不加。

**为什么都是 `int` 而不是 `str`:**
- 数值比较直观(`1.0.0 < 1.1.0 < 2.0.0`)。
- 序列化产物更简洁(`{"major": 1}` vs `{"major": "1"}`)。
- 业务上"版本号"是数字,不是字符串。

### 5.3 `parse(s: str) -> "PlateVersion"` — classmethod

```python
@classmethod
def parse(cls, s: str) -> "PlateVersion":
    """解析 ``'major.minor.patch'`` 字符串。

    Raises:
        ValueError: 格式错(空、非字符串、缺段、非数字)
    """
    if not isinstance(s, str):
        raise ValueError(
            f"PlateVersion: 版本字符串必须是 str,实际 {type(s).__name__}: {s!r}"
        )
    m = _VERSION_RE.match(s)
    if not m:
        raise ValueError(
            f"PlateVersion: 版本格式必须 'major.minor.patch'(纯数字),"
            f"实际 {s!r}"
        )
    return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))
```

**输入:**
- `s: str` — 形如 `"1.2.3"` 的版本字符串。

**输出:**
- `PlateVersion(1, 2, 3)` 实例。

**校验逻辑:**
1. `isinstance(s, str)` — 必须字符串,否则 `ValueError`。
2. `_VERSION_RE.match(s)` — 正则匹配。
3. 失败 → `ValueError`(带"格式必须 'major.minor.patch'"提示)。
4. 成功 → `cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))`。
   - 用 `int(...)` 强转(Pydantic 风格的防御性,虽然正则保证是数字)。

**为什么"必须字符串"用 `ValueError`:**
- 类型错用 `TypeError`,值错用 `ValueError` — Python 惯例。
- 但本方法不返 `TypeError`,返 `ValueError` — 因为业务上"非字符串
  的版本号"几乎一定是 "值错" 而非"类型错"(`None` / 数字等)。
- 单 `ValueError` 让调用方 try/except 更简单。

**为什么不返回 None(容错):**
> 解析失败 = 接受坏契约。Plate 的版本号是"硬契约",必须 fail-fast。

### 5.4 `__str__(self) -> str`

```python
def __str__(self) -> str:
    return f"{self.major}.{self.minor}.{self.patch}"
```

**输入:** `self`。

**输出:** `"major.minor.patch"` 字符串。

**字段语义:**
- 这是 `str(plate_version)` 的 Python 惯例实现。
- 与 `parse` 互逆:`PlateVersion.parse(str(v)) == v` 对任何 v 成立。

**为什么 `__str__` 而不是 `__repr__`:**
- `__repr__` 默认由 `@dataclass` 自动生成,产出 `PlateVersion(major=1,
  minor=2, patch=3)`(调试用,详细)。
- `__str__` 是"用户层"字符串,简单 `"1.2.3"`,与 `parse` 互逆。
- 二者分工:debug 调 `repr`,业务调 `str`。

### 5.5 `to_dict() -> dict[str, int]`

```python
def to_dict(self) -> dict[str, int]:
    """序列化为 dict。键固定:``major`` / ``minor`` / ``patch``。

    注:不调 ``dataclasses.asdict``(避免引入额外 dict 拷贝),直接构造。
    """
    return {"major": self.major, "minor": self.minor, "patch": self.patch}
```

**输入:** `self`。

**输出:** `{"major": 1, "minor": 2, "patch": 3}` 字典。

**字段语义:**
- 键固定三个(`major` / `minor` / `patch`),值是 int。
- 用于 `manifest.to_dict()` 内嵌(版本号是 manifest 的一个子字段)。

**为什么不调 `dataclasses.asdict`:**
- `asdict(self)` 也会产出同样 dict,但有额外的递归拷贝(对 frozen
  dataclass 没必要)。
- 显式构造让序列化形态**完全可预测**(review 起来一目了然)。

**为什么不排序键(像 `manifest` 那样):**
- 三个键的顺序在 Python 3.7+ 的 `dict` 是"插入序",且 `to_dict` 产出
  的是**完整 dict** — 消费者自己 `json.dumps(sort_keys=True)` 即可。
- 本类内部不排序,职责单一(只产出 dict)。

### 5.6 `from_dict(d: dict) -> "PlateVersion"` — classmethod

```python
@classmethod
def from_dict(cls, d: dict) -> "PlateVersion":
    """从 dict 反序列化。缺失键 / 类型错抛 ValueError。

    不容错:序列化产物是契约,容错 = 接受坏契约。
    """
    if not isinstance(d, dict):
        raise ValueError(
            f"PlateVersion.from_dict: 期望 dict,实际 {type(d).__name__}"
        )
    missing = [k for k in ("major", "minor", "patch") if k not in d]
    if missing:
        raise ValueError(
            f"PlateVersion.from_dict: 缺失字段 {missing},实际 {d!r}"
        )
    try:
        return cls(
            major=int(d["major"]),
            minor=int(d["minor"]),
            patch=int(d["patch"]),
        )
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"PlateVersion.from_dict: 字段类型错,实际 {d!r}: {e}"
        ) from e
```

**输入:**
- `d: dict` — `{"major": int, "minor": int, "patch": int}`。

**输出:** `PlateVersion(major, minor, patch)` 实例。

**校验逻辑:**
1. `isinstance(d, dict)` — 必须 dict,否则 `ValueError`。
2. 检查三个必填字段 — 缺失则 `ValueError`(带"缺失字段 [...]"提
   示)。
3. `int(d["major"])` 等强转 — 失败则 `ValueError`(`from e` 保留原
   堆栈)。

**为什么"严格不容错":**
> 序列化产物是契约,容错 = 接受坏契约。

(与 `EndpointSpec.from_dict` / `FieldBinding.from_dict` 同源。)

**为什么 `try/except (TypeError, ValueError)`:**
- `int("abc")` 抛 `ValueError`(字符串→int 失败)。
- `int(None)` 抛 `TypeError`(NoneType→int 失败)。
- 两种都要捕获,统一 `raise ValueError` 让上层 try/except 简单。

---

## 6. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `PlateVersion` | `@final @dataclass(frozen=True)` | `from Plate.version import PlateVersion` |

模块底部 `__all__`:

```python
__all__ = ["PlateVersion"]
```

---

## 7. 调用方典型代码示例

```python
# 1. 解析
from Plate.version import PlateVersion

v = PlateVersion.parse("1.2.3")
print(v)  # "1.2.3"
print(v.major, v.minor, v.patch)  # 1 2 3

# 2. 解析失败
try:
    PlateVersion.parse("v1.2.3")
except ValueError as e:
    print(e)  # "版本格式必须 'major.minor.patch'(纯数字),实际 'v1.2.3'"

# 3. 构造
v = PlateVersion(1, 0, 0)

# 4. 序列化 / 反序列化
d = v.to_dict()
# {"major": 1, "minor": 0, "patch": 0}
v2 = PlateVersion.from_dict(d)
assert v == v2

# 5. 容器
versions = {PlateVersion(1, 0, 0), PlateVersion(1, 1, 0)}
print(PlateVersion(1, 0, 0) in versions)  # True
```

---

## 8. 不变量总结(本模块承诺的不变式)

1. **不可变**:`frozen=True` 让 version 实例在构造后无法被修改。
2. **不可继承**:`@final` 装饰器禁止任何类继承 `PlateVersion`。
3. **byte-equal**:`frozen=True` 的 dataclass 逐字段比较,`v == w`
   当且仅当三个 int 字段全等。
4. **格式严格**:`parse` 只接受 `^\d+\.\d+\.\d+$`,其他格式 fail-fast。
5. **不依赖其他 Plate 模块**:`version.py` 是叶子工具,无循环依赖风险。

---

## 9. 设计权衡

| 决策 | 取舍 |
|---|---|
| 只支持三段(major.minor.patch) | 简单;YAGNI 不实现 pre-release / build metadata |
| 不限制 minor/patch 位数 | `\d+` 通用;真要限制再加 |
| `__str__` 与 `parse` 互逆 | 业务常用模式 — `str(PlateVersion(...))` 后再 `parse` 仍得原值 |
| 显式 `to_dict` 而非 `asdict` | 序列化形态完全可预测,review 友好 |
| 强转 `int(...)` 防御性 | 正则保证是数字,但 `int(...)` 兜底防止"假阳" |
| `parse` 用 `ValueError` 而非 `TypeError` | 调用方 try/except 简单;业务上"非字符串"是值错 |
