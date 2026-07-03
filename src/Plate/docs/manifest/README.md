# manifest 模块(`Plate/manifest.py`)

> 本文档详细描述 `Plate/manifest.py` 中的**每一个公开/内部类、函数、方
> 法**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整解释该模块
> 的所有行为细节与设计动机。

---

## 1. 模块定位

`manifest.py` 是 Plate 子系统的**版本快照**。它解决的核心问题:

> **如何让客户端在不连接服务端的情况下,也能"知道"自己要用哪个版本的契
> 约,且能在收到服务端响应后用"字节级一致"的方式验证内容未被篡改?**

它暴露一个核心类 `PlateManifest`:
- 聚合"某版本下的所有 service + 端点"的完整描述;
- 计算 SHA256 校验和(基于规范 JSON 序列化);
- 提供 `verify()` 检测漂移。

`client.py` / `server/router.py` / `facade/switch.py` 都依赖这个模块。

---

## 2. 模块文档字符串(开发者注释原文翻译)

```text
Plate 服务化版本的快照(聚合 + 校验和)。

对应设计:PR-2.0 §2.4 + PLATE_EVOLUTION §3 Phase 2。

职责:
  * ``PlateManifest`` 聚合"某版本下的所有服务 + 端点 + 校验和"
  * ``compute_checksum`` SHA256(基于规范 JSON 序列化)
  * ``verify`` 检测漂移

业务价值:
  * 客户端拉取 manifest 后,用 checksum 验证字节级一致(防中间代理篡改)
  * 不同版本的 manifest checksum 不同(协议升级硬前提)
  * 服务列表增删 → checksum 变化(契约漂移检测)
```

---

## 3. 依赖关系

```python
import hashlib
import json
from dataclasses import dataclass, field
from typing import final

from Plate.version import PlateVersion
```

**为什么这么依赖:**
- `hashlib` — SHA256 计算。
- `json` — `dumps(sort_keys=True, separators=(",", ":"))` 是 byte-equal
  的关键。
- `dataclasses` — 定义 `PlateManifest` 不可变数据类。
- `Plate.version.PlateVersion` — manifest 必须带版本号。

**重要的反向依赖约束:**
- `manifest.py` 只依赖 `version` 模块,**不**依赖 `spec` / `core` /
  `facade` / `server` / `api_doc`。
- 这保证 manifest 是一个"独立可序列化"的数据结构,可以被网络层 /
  缓存层 / 校验层无副作用地处理。

---

## 4. 核心数据类:`PlateManifest`

### 4.1 类声明与字段

```python
@final
@dataclass(frozen=True)
class PlateManifest:
    """某版本 Plate 的完整快照。

    字段语义:
      version: 此 manifest 的版本(必填)
      services: 服务名 → 该服务的端点 to_dict() 列表
      checksum: SHA256 字符串,空字符串 = 未计算
    """

    version: PlateVersion
    services: dict[str, list[dict]] = field(default_factory=dict)
    checksum: str = ""
```

**字段详解:**

- `version: PlateVersion` — 此 manifest 的版本(必填)。没有默认值 —
  构造时必须显式传入。
- `services: dict[str, list[dict]]` — 服务名 → 该服务所有端点 `to_dict()`
  后的 dict 列表。**约定:列表内端点按 `(method, path)` 排序**(本类
  不强制,由 `from_services` 等调用方负责)。
- `checksum: str` — SHA256 hex digest 字符串。空字符串 `""` = 未计算。
  字段本身**不**参与自身的 checksum 计算(它是"标记"非"数据")。

**为什么 `@final`:**
- `PlateManifest` 是数据描述层,无继承需求。
- `final` 防止业务代码"扩展"manifest 字段,保持语义稳定。

**为什么 `@dataclass(frozen=True)`:**
- 不可变:让 manifest 可哈希、可作 dict key、可在多线程间安全共享。
- 不可变:让 `verify()` 的"expected vs actual"对比中,manifest 自身不
  会被并发修改导致 TOCTOU。

### 4.2 `to_dict() -> dict`

```python
def to_dict(self) -> dict:
    """序列化为 dict。

    注:services 内的端点 list 已按 (method, path) 排序 —— 见
    ``compute_checksum`` 和 ``from_services`` 调用方约定。
    checksum 字段**不**参与自身的 checksum 计算,它是"标记"非"数据"。
    """
    return {
        "version": self.version.to_dict(),
        "services": self.services,  # 假定已排序(调用方责任)
        "checksum": self.checksum,
    }
```

**字段语义:**
- `version` 走 `PlateVersion.to_dict()` 链式序列化。
- `services` 直传(假定调用方已排序 — 这是调用方契约,本方法不重复排
  序以避免开销)。
- `checksum` 直传(它是"标记"字段,不参与自身 checksum 计算)。

**为什么不内部排序:**
- `compute_checksum` 已经排序一次,结果存进 `services`。
- `to_dict` 是"读"操作,频繁调用;内部排序是 O(n log n),在频繁调用
  时累计开销大。
- 排序是构造期责任(`from_services` / 调用 `compute_checksum` 的代码
  负责),不是读期责任。

**为什么 `checksum` 不参与自身计算:**
- 这是一个"自我引用"的语义问题 — manifest 包含 checksum,checksum
  又是 manifest 的散列,会让 `compute_checksum(manifest) ==
  manifest.checksum` 永远 False(因为计算时 checksum 是空,产物是非空)。
- 解决方案:把 checksum 字段**排除**在 checksum 计算范围外 — 计算时
  显式构造 `{"version": ..., "services": ...}`(无 checksum 字段)的
  payload,见 `compute_checksum` 实现。

### 4.3 `compute_checksum` — classmethod

```python
@classmethod
def compute_checksum(
    cls,
    version: PlateVersion,
    services: dict[str, list[dict]],
) -> str:
    """计算 SHA256 校验和。

    算法:
      1. services 按 service 名排序
      2. 每个 service 内的端点按 (method, path) 排序
      3. ``json.dumps(sort_keys=True, separators=(",", ":"))``
      4. SHA256 → hex digest

    byte-equal 保证:
      - sort_keys=True:dict 键顺序无关
      - 排序 services 与端点:list 顺序无关
      - 固定 separators:空格无关
    """
    sorted_services: dict[str, list[dict]] = {}
    for svc_name in sorted(services.keys()):
        specs = services[svc_name]
        sorted_services[svc_name] = sorted(
            specs, key=lambda s: (s.get("method", ""), s.get("path", ""))
        )
    payload = {
        "version": version.to_dict(),
        "services": sorted_services,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**算法步骤:**

1. **services 按 service 名排序** — `for svc_name in sorted(services.keys())`。
2. **每个 service 内的端点按 `(method, path)` 排序** — `sorted(specs,
   key=lambda s: (s.get("method", ""), s.get("path", "")))`。
3. **构造 payload** — 显式不含 `checksum` 字段。
4. **canonical JSON 序列化** — `json.dumps(payload, sort_keys=True,
   separators=(",", ":"))`:
   - `sort_keys=True` — dict 键按字母序,抹平 `{"a": 1, "b": 2}` 和
     `{"b": 2, "a": 1}` 的差异。
   - `separators=(",", ":")` — 紧凑 JSON(无空格),抹平 `"a": 1, "b": 2`
     和 `"a": 1,"b": 2` 的差异。
5. **SHA256** — `hashlib.sha256(canonical.encode("utf-8")).hexdigest()`。

**为什么用 `(method, path)` 作为排序键:**
- `EndpointKey` 的"自然序"是 `(service, method, path)`(因为 `service`
  已是外层 dict key)。
- 内层 list 只剩 `(method, path)`,这是端点的"主键后缀"。

**为什么 `getattr` 用 `get("method", "")` 而不是 `["method"]`:**
- 防御性:防止某个端点 dict 缺少 `method` 字段(理论上不应该,但 L1
  校验是构造期,这里再次兜底)。
- 默认 `""` 让 `sorted` 仍然有序(空字符串小于任何非空字符串)。

**byte-equal 三件套:**
| 保证 | 实现 |
|---|---|
| dict 键顺序无关 | `sort_keys=True` |
| list 顺序无关 | 显式 `sorted(...)` |
| 空白字符无关 | `separators=(",", ":")`(无空格) |

**为什么用 classmethod 而非 staticmethod:**
- 未来若要给 `compute_checksum` 加"继承自 `PlateManifest` 的子类也
  支持"的能力,classmethod 更灵活。
- 实际目前不依赖 `cls`,但保留 classmethod 形式更符合"这是 manifest
  类的操作"的语义。

### 4.4 `from_services` — classmethod

```python
@classmethod
def from_services(
    cls,
    version: PlateVersion,
    services: dict[str, list[dict]],
) -> "PlateManifest":
    """从 version + services 构造 manifest,自动计算 checksum。

    调用方**不**需预先排序 —— 本方法内部排序。
    """
    chk = cls.compute_checksum(version, services)
    # 排序后存入(保证 to_dict 的产物与 checksum 一致)
    sorted_services: dict[str, list[dict]] = {}
    for svc_name in sorted(services.keys()):
        sorted_services[svc_name] = sorted(
            services[svc_name],
            key=lambda s: (s.get("method", ""), s.get("path", ""))
        )
    return cls(version=version, services=sorted_services, checksum=chk)
```

**核心行为:**
1. 调 `compute_checksum` 算 SHA256(内部已排序)。
2. **重新构造** sorted_services(因为 `compute_checksum` 算出的
   `sorted_services` 是局部变量,需要把排序后的版本**存进 self**)。
3. 返回 `cls(version=..., services=sorted_services, checksum=chk)`。

**为什么 `compute_checksum` 不直接返回 `(checksum, sorted_services)`
元组:**
- `compute_checksum` 是"纯函数",职责单一 — 给定 version + services,
  算 checksum,返回字符串。让它返回元组会破坏单一职责。
- `from_services` 显式做"算 + 排序并存入"两步,职责清晰。

**为什么"调用方不需预先排序":**
- API 友好性 — 调用方通常拿到的是"按 import 顺序"的 services,排序
  是 manifest 内部的责任。
- 内部排序 + 存入,保证 `to_dict()` 产物与 `checksum` 计算产物 byte
  一致。

### 4.5 `verify() -> None`

```python
def verify(self) -> None:
    """校验 checksum,不符抛 ValueError(检测漂移)。"""
    expected = self.compute_checksum(self.version, self.services)
    if expected != self.checksum:
        raise ValueError(
            f"PlateManifest: checksum 不一致,可能漂移或被篡改。"
            f"expected={expected!r}, actual={self.checksum!r}"
        )
```

**算法步骤:**
1. 用 `self.version` 和 `self.services` 重新算 expected checksum。
2. 与 `self.checksum` 字段比对。
3. 不一致 → raise `ValueError`(带 expected / actual 调试信息)。

**为什么 `ValueError` 而不是自定义异常:**
- `ValueError` 是 Python 惯例 — "值错"用 `ValueError`。
- 调用方用 `try/except ValueError` 即可捕获,不需要 import 新异常类型。

**业务场景:**
- 客户端从服务端拉取 manifest(JSON 形式),反序列化成 `PlateManifest`。
- 调 `verify()` 确认收到的 manifest 字节级一致。
- 不一致 → 可能是:
  1. 网络中间代理改了 JSON(极少见,但会触发)。
  2. 服务端的 manifest 与本地的 spec 不一致(契约漂移,严重 bug)。
  3. 序列化 / 反序列化逻辑 bug(本地发现)。

**为什么 `self.services` 传回去仍能算出相同 checksum:**
- `from_services` 已经把 `self.services` 排好序,`to_dict` 假定已排序。
- 所以 `compute_checksum(self.version, self.services)` 的输入已经
  是"排序后"的版本,与原始 `from_services` 调用时算 checksum 的
  输入是**同一份**排序后的数据。

---

## 5. 公开 API 一览

| 名称 | 类型 | 模块导出 |
|---|---|---|
| `PlateManifest` | `@final @dataclass(frozen=True)` | `from Plate.manifest import PlateManifest` |

模块底部 `__all__`:

```python
__all__ = ["PlateManifest"]
```

---

## 6. 调用方典型代码示例

```python
# 1. 构造 manifest(从 version + services)
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion
from Plate import registry

registry.collect("fin")
specs = [
    s.to_dict() for k, s in registry._index.items() if k.service == "fin"
]
m = PlateManifest.from_services(PlateVersion(1, 0, 0), {"fin": specs})
print(m.checksum)  # 64 字符 hex string
print(m.to_dict())  # 完整 dict 形态

# 2. 验证(漂移检测)
m.verify()  # OK — 不抛
# 篡改:
m_tampered = PlateManifest(
    version=PlateVersion(1, 0, 0),
    services=m.services,
    checksum="0" * 64,  # 假 checksum
)
m_tampered.verify()  # raise ValueError

# 3. 单独算 checksum(不构造 manifest)
checksum = PlateManifest.compute_checksum(
    PlateVersion(1, 0, 0), {"fin": specs}
)
print(checksum)
```

---

## 7. 不变量总结(本模块承诺的不变式)

1. **不可变**:`frozen=True` 让 manifest 实例在构造后无法被修改。
2. **不可继承**:`@final` 装饰器禁止任何类继承 `PlateManifest`。
3. **byte-equal checksum**:`compute_checksum` 的算法三件套(`sort_keys=True`
   + 显式排序 + 紧凑分隔符)保证"同 services 算出的 checksum 一致"。
4. **checksum 排除自身**:`compute_checksum` 的 payload 显式不含
   `checksum` 字段,避免"自我引用"的悖论。
5. **to_dict 不重新排序**:`to_dict` 假定 services 已排序,这是调用方
   契约(由 `from_services` 满足)。
6. **错误信息调试友好**:`verify` 失败时带 expected/actual hex 字符串。

---

## 8. 设计权衡(为什么有些事"不做")

| 不做的事 | 原因 |
|---|---|
| 内部排序 `to_dict` 输出 | 性能(频繁调)+ 职责单一(排序是构造期责任) |
| 缓存 checksum | checksum 已经是 O(n) 一次性计算,缓存不带来可观测的性能增益,且增加状态管理复杂度 |
| 加密签名(而非仅 SHA256) | SHA256 用于"检测漂移",不用于"防篡改"(后者需要私钥签名);防篡改由 HTTPS / mTLS 层负责 |
| 增量 checksum(每个 service 单独) | 未来 PR 可能加;本期全量足够,业务用例每次拉全量 |
| 异步 IO 校验 | 本模块纯计算,无 IO |
