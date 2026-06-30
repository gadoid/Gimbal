# PR-2.4: GIMBAL 切换到 SDK + 向后兼容

> **状态**:✅ 已实现
>
> **PR 范围**:
> 1. GIMBAL 顶层入口从"直读本地"切换为"优先走 SDK,本地兜底"
> 2. `from Plate import registry` 旧路径**继续可用**(A6 向后兼容)
> 3. 新增 `PlateFacade.from_url(...)` / `PlateFacade.from_local()` 工厂(双轨期间)
> 4. 校验切换的字节级等价:同一份 contract,远端 vs 本地 checksum 必须一致
>
> **前置依赖**:**PR-2.0**(version + serialization)+ **PR-2.1**(协议)+
> **PR-2.3**(真实部署 + E2E)
> 注:**PR-2.2 SDK 仅有设计稿未落地**;本会话在 `Plate/facade/client.py` 用同进程
> 占位实现 `PlateClient`(直接调 `Plate.registry` + 内存缓存,模拟"远端权威"
> 语义),Phase 3 替换为真 HTTP(urllib + retries),facade 接口不变。
>
> **关键设计**:本 PR 是"切换"而非"替换"。**不**删除 `from Plate import registry`,
> 而是让 `PlateFacade` 顶层 facade 优先走 `PlateClient`,失败时自动
> fallback 到本地 registry。对调用方而言,所有现有代码**不需改动**;新代码可以
> 显式选 mode(remote-first / local-only / local-fallback)。
>
> **实现偏差(本会话调整)**:
> 1. **不**改 `gimbal` 顶层包(`gimbal` 是 GIMBAL 主框架入口,已 117 行 schema re-export,
>    与 `GIMBAL` 类名冲突风险高)。Facade 改放 `src/Plate/facade/` 子包,符合
>    "每个子系统有自己门面"的多模块库惯例(类比 Flask extensions / requests 等)。
> 2. **默认 mode 从 `HYBRID` 改为 `LOCAL_ONLY`**:本会话 `PlateClient` 是同进程
>    占位,设 `HYBRID` 默认值会让单测场景下"无意义走 SDK"。`LOCAL_ONLY` 默认 +
>    显式 `from_url(...)` 切 SDK,显式优于隐式,符合 A1。
>
> **对应设计**:[PR-2.2 SDK 设计稿](../phase2/PR-2.2.md) + [PR-2.3 部署](../phase2/PR-2.3.md) +
> A4 本地优先 + A6 向后兼容 + 不变承诺 5(优雅降级)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 已建好远端服务(PR-2.3)+ 客户端 SDK(PR-2.2),但 GIMBAL
主框架**仍**在用 `from Plate import registry` 直读本地。这导致:

- **场景**:开发期每人本地有 fin service 子包,能跑;CI/Prod 期望从远端拿权威 contract
- **现状**:GIMBAL 顶层拿不到远端信息(SDK 没人调用)
- **诉求**:让 GIMBAL 默认走 SDK,本地仅作 fallback,旧调用方式**不破坏**

**本 PR 切换的 4 个具体目标**:

1. **入口切换**:`gimbal.GIMBAL` 类的默认初始化路径从"本地 registry"切到"SDK + fallback"
2. **双轨共存**:`from Plate import registry` 继续有效(A6)
3. **显式 mode**:新代码可以 `GIMBAL.from_url(...)` / `GIMBAL.from_local()` 显式选 mode
4. **字节级验证**:远端 manifest checksum = 本地 manifest checksum(同一份 contract 不可漂移)

### 1.2 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 默认 mode | `remote-first`(网络 OK 走远端,失败 fallback 本地) | 满足"远端权威 + 离线可用"双诉求;对应 A4 |
| 远端不可达行为 | 静默 fallback + 警告日志(DEBUG 级别) | 不让网络抖动影响执行;不变承诺 5 |
| 缓存策略 | SDK 内部缓存(PR-2.2 §2.3)+ 本 PR 不引入新缓存层 | 避免双层缓存失效问题 |
| 字节级 pin 时机 | 启动时校验一次,失败 → 全量重拉,再失败 → fallback 本地 | 与 PR-2.0 §"版本"语义一致 |
| 旧 API 标记 | `from Plate import registry` 标 `DeprecationWarning`(本 PR 末) | 给用户迁移时间;不强制 |
| 新 API 命名 | `GIMBAL.from_url` / `GIMBAL.from_local` / `GIMBAL.from_hybrid`(默认) | 显式优于隐式 |
| 配置来源 | 环境变量 `GIMBAL_PLATE_URL` / `GIMBAL_PLATE_MODE` | 12-factor,不改代码切 mode |

### 1.3 不做什么(明确范围外)

- **不**实现 service 子包自动从远端拉取(PR-2.4 之后,`from Plate.fin import X` 仍走本地)
  - 理由:spec 实例化是 Python 模块级常量,远端拉的是 spec dict,需要 `from_dict` 重建
  - 短期可接受,长期是 PR-2.6+ 范围
- **不**实现版本协商(PR-2.4 只支持 server 端声明的 `SUPPORTED_VERSIONS` 之一)
  - 长期:server 多个版本并存,client 选最近兼容版本
- **不**改 server 端(server 已冻结,见 PR-2.3 收口)

---

## 2. 代码实现要点

### 2.1 改动文件清单

> 本会话实现版(物理路径),对照 §1.2 "实现偏差" 阅读。

| 文件 | 改动 | 性质 |
|---|---|---|
| `src/Plate/facade/__init__.py` | 新建:`PlateFacade` 顶层 facade + 3 工厂 + 4 mode 路由 | 新建 |
| `src/Plate/facade/client.py` | 新建:`PlateClient`(同进程占位)+ `CacheStats` | 新建 |
| `src/Plate/facade/switch.py` | 新建:`decide_resolve` 纯函数(mode 决策) | 新建 |
| `src/Plate/facade/legacy.py` | 新建:`warn_legacy_once` + `LEGACY_MIGRATION_HINT` | 新建 |
| `src/Plate/facade/errors.py` | 新建:`PlateMode` / `OfflineError` / `DEFAULT_VERSION` | 新建 |
| `tests/plate/test_facade_switch.py` | 新建:facade 切换路径单元测试(≥ 20) | 新建 |
| `tests/plate/test_invariants.py` | 加 1 条:远端 vs 本地 manifest checksum byte-equal(A2 兑现) | 加 |
| `tests/plate/test_invariants.py` | 加 1 条:`from Plate import registry` 仍可用(A6 兑现) | 加 |
| `tests/plate/test_zero_invasion.py` | 加 allowlist:`Plate.facade` / `Plate.facade.client` / `Plate.facade.switch` / `Plate.facade.legacy` / `Plate.facade.errors` | 加 |
| `design/PLATE_DESIGN.md` §7 §8 | 加 "Phase 2 切换说明" 章节 | 文档同步 |
| `README.md` | 加 "Plate 服务化模式选择" 小节 | 文档同步 |

### 2.2 PlateFacade 顶层 facade

> 以下代码示例展示**设计形态**,实际物理路径见 §1.2 "实现偏差"。
> 真实实现见 [src/Plate/facade/](../../src/Plate/facade/)。

```python
# src/Plate/facade/__init__.py
"""Plate 子系统 facade(Phase 2 / PR-2.4)。

设计目标(对应 A4 + A6 + 不变承诺 5):
  - 默认走 PlateClient(同进程占位 → Phase 3 真 HTTP)
  - 旧调用方式 ``from Plate import registry`` 继续有效
  - 新代码可以显式选 mode(hybrid / remote-first / local-fallback / local-only)

切换不替换:本 PR 不删 ``Plate.registry``,只让 ``PlateFacade`` 优先走 client。
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Optional

from plate_client import PlateClient, OfflineError
from plate_client.cache import CacheMissError
from Plate import registry as _legacy_registry
from Plate.version import PlateVersion

_log = logging.getLogger("gimbal.plate")


class PlateMode(str, Enum):
    """Plate 数据源模式(对应 A4 本地优先 + A6 向后兼容)。"""

    HYBRID = "hybrid"             # 默认:远端优先,失败 fallback 本地
    REMOTE_FIRST = "remote-first" # 与 HYBRID 同义(HYBRID 是 default alias)
    LOCAL_FALLBACK = "local-fallback"  # 同 HYBRID,显式表达
    LOCAL_ONLY = "local-only"     # 永远只读本地(开发/单测/无网环境)


class GIMBAL:
    """GIMBAL 顶层 facade — 业务代码统一入口。

    用法::

        # 默认:HYBRID,远端失败自动 fallback
        gb = GIMBAL.from_default()
        spec = gb.resolve("fin", "POST", "/api/order/order/orderDetail")

        # 显式 local-only(开发/单测)
        gb = GIMBAL.from_local()
        spec = gb.resolve("fin", "POST", "/api/order/order/orderDetail")

        # 显式远端 + 缓存路径
        gb = GIMBAL.from_url("http://plate.internal:8080",
                             version=PlateVersion.parse("1.0.0"))
        spec = gb.resolve("fin", "POST", "/api/order/order/orderDetail")
    """

    def __init__(
        self,
        *,
        mode: PlateMode,
        version: PlateVersion,
        base_url: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        self._mode = mode
        self._version = version
        self._base_url = base_url
        self._client: Optional[PlateClient] = None
        if mode in (PlateMode.HYBRID, PlateMode.REMOTE_FIRST, PlateMode.LOCAL_FALLBACK):
            if not base_url:
                raise ValueError(
                    f"[GIMBAL] mode={mode} requires base_url"
                )
            self._client = PlateClient(
                base_url=base_url,
                version=version,
                cache_dir=cache_dir,
            )

    # ── 工厂方法(对应"显式优于隐式")──

    @classmethod
    def from_default(cls) -> "GIMBAL":
        """默认入口:从环境变量读 mode + base_url,缺省走 HYBRID。"""
        mode = PlateMode(os.environ.get("GIMBAL_PLATE_MODE", "hybrid"))
        base_url = os.environ.get("GIMBAL_PLATE_URL")
        version = PlateVersion.parse(os.environ.get("GIMBAL_PLATE_VERSION", "1.0.0"))
        if mode == PlateMode.LOCAL_ONLY:
            return cls(mode=mode, version=version)
        return cls(mode=mode, version=version, base_url=base_url)

    @classmethod
    def from_local(cls, version: PlateVersion = PlateVersion(1, 0, 0)) -> "GIMBAL":
        """显式本地模式:不连远端,纯本地 registry。"""
        return cls(mode=PlateMode.LOCAL_ONLY, version=version)

    @classmethod
    def from_url(
        cls,
        base_url: str,
        version: PlateVersion = PlateVersion(1, 0, 0),
        cache_dir: Optional[str] = None,
        mode: PlateMode = PlateMode.HYBRID,
    ) -> "GIMBAL":
        """显式远端模式:可指定 HYBRID / REMOTE_FIRST / LOCAL_FALLBACK。"""
        return cls(mode=mode, version=version, base_url=base_url, cache_dir=cache_dir)

    # ── 业务方法(调用方统一入口)──

    def resolve(self, service: str, method: str, path: str):
        """按 (service, method, path) 拿 EndpointSpec。

        行为依赖 mode:
          - LOCAL_ONLY:直接 ``registry.resolve()``
          - HYBRID / REMOTE_FIRST:SDK 拉远端 → 缓存 → 本地失败 fallback
        """
        if self._mode == PlateMode.LOCAL_ONLY:
            return _legacy_registry.resolve(service, method, path)
        try:
            return self._client.resolve(service, method, path)
        except (OfflineError, CacheMissError) as e:
            _log.debug("[GIMBAL] SDK 不可达,fallback 本地: %s", e)
            return _legacy_registry.resolve(service, method, path)

    def manifest(self) -> dict:
        """返回 manifest dict(走 SDK 或本地,取决于 mode)。"""
        if self._mode == PlateMode.LOCAL_ONLY:
            from Plate.manifest import PlateManifest
            # 本地构造:从 _legacy_registry._index 反推
            ...
        return self._client.manifest()

    def cache_stats(self) -> dict:
        """缓存命中统计(仅 HYBRID/REMOTE_FIRST 有意义)。"""
        if self._client is None:
            return {"mode": "local-only", "hit": 0, "miss": 0}
        return self._client.cache_stats()
```

### 2.3 `_legacy` 桥接(让旧 API 继续工作)

```python
# src/gimbal/_legacy.py
"""旧 ``from Plate import registry`` 调用桥接到 GIMBAL facade。

对应 A6 向后兼容:本模块**不**替换 ``Plate.registry`` 的导出,
而是给旧调用方式打 ``DeprecationWarning`` 并桥接到 ``GIMBAL``。

切换期(预计 Phase 3 之前)允许双轨共存;
Phase 3 再视情况删 ``_legacy`` 桥(本 PR 末决定保留)。
"""
from __future__ import annotations

import warnings
from typing import Any

from gimbal import GIMBAL
from Plate import registry as _legacy_registry

_deprecation_emitted = False


def _warn_legacy_once() -> None:
    global _deprecation_emitted
    if not _deprecation_emitted:
        warnings.warn(
            "[GIMBAL] ``from Plate import registry`` 已标记为遗留路径,"
            "请迁移到 ``from gimbal import GIMBAL``。"
            "本 PR(2.4)周期内仍可用,Phase 3 收尾前保留。",
            DeprecationWarning,
            stacklevel=3,
        )
        _deprecation_emitted = True


# 关键桥接:`registry.resolve()` 仍可用,但走 GIMBAL 路径
def _patched_resolve(service: str, method: str, path: str) -> Any:
    _warn_legacy_once()
    gb = GIMBAL.from_default()
    return gb.resolve(service, method, path)
```

> **实现说明**:本 PR 不强制把 `Plate.registry` 改成"调用 `_patched_resolve`",
> 因为这会改变 `registry._index` 的语义(原版是直读,新桥接走 SDK 后会引入
> 网络 IO 与缓存)。**策略**:旧 API 继续直读 `_index`(行为不变),新 API 走
> `GIMBAL`。DeprecationWarning 留到 Phase 3。

### 2.4 Mode 路由决策表

| mode | 远端可达 | 缓存命中 | 行为 |
|---|---|---|---|
| LOCAL_ONLY | n/a | n/a | `registry.resolve()` |
| HYBRID | ✅ | ✅ | SDK 远端 → 本地缓存 fallback |
| HYBRID | ✅ | ❌ | SDK 远端 → 拉成功 → 写缓存 → 返回 |
| HYBRID | ❌ | ✅ | SDK 失败 → 读缓存 → 校验 checksum → 返回 |
| HYBRID | ❌ | ❌ | SDK 失败 → 缓存失败 → `registry.resolve()` |
| REMOTE_FIRST | ❌ | n/a | `OfflineError` 上抛(**不**fallback 本地) |
| LOCAL_FALLBACK | ❌ | ✅ | 缓存 → 仍失败 → `OfflineError` 上抛 |

> 关键区别:**HYBRID 静默 fallback**;**REMOTE_FIRST / LOCAL_FALLBACK 显式
> 失败**。给业务方明确选择:要"稳"还是"严"。

### 2.5 环境变量

| 变量 | 默认 | 含义 |
|---|---|---|
| `GIMBAL_PLATE_MODE` | `hybrid` | `hybrid` / `remote-first` / `local-fallback` / `local-only` |
| `GIMBAL_PLATE_URL` | (无) | server base URL,例 `http://plate.internal:8080` |
| `GIMBAL_PLATE_VERSION` | `1.0.0` | 协议版本 |
| `GIMBAL_PLATE_CACHE_DIR` | (平台默认) | 覆盖缓存目录 |

---

## 3. 字节级 pin 校验

### 3.1 不变量 §1.3:远端 manifest checksum = 本地 manifest checksum

```python
# tests/plate/test_invariants.py
def test_invariant_remote_manifest_byte_equal_to_local():
    """业务不变量:同一份 contract,远端 vs 本地 manifest checksum 必须一致。

    对应设计:PR-2.0 §版本机制 + A2 不可变序列化 + A4 本地优先远端备份。
    业务影响:违反 = 远端/本地 contract 漂移,运行时拿错 spec,silent bug。
    """
    import subprocess, time, urllib.request, json
    from Plate import registry
    from Plate.manifest import PlateManifest
    from Plate.server import PlateServer

    # 起本地 server
    server = PlateServer(port=0)
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}"
        # 拉远端 manifest
        with urllib.request.urlopen(f"{url}/v1/manifest") as r:
            remote = json.loads(r.read())
        # 算本地 manifest
        registry.reset()
        registry.collect("fin")
        services = {
            svc: [
                s.to_dict() for k, s in registry._index.items() if k.service == svc
            ]
            for svc in {k.service for k in registry._index}
        }
        local = PlateManifest.from_services(
            PlateVersion(1, 0, 0), services
        ).to_dict()
        # 字节级 pin
        assert remote["checksum"] == local["checksum"], (
            f"远端 checksum={remote['checksum']} != 本地 checksum={local['checksum']}"
        )
        # 远端 services 内容 == 本地 services 内容
        assert remote["services"] == local["services"]
    finally:
        server.stop()
```

### 3.2 不变量 §1.4:旧 API 仍可用

```python
def test_invariant_legacy_registry_still_works():
    """业务不变量:``from Plate import registry`` 仍能拿到 spec(A6 向后兼容)。

    业务影响:违反 = 所有旧调用方在升级 GIMBAL 后 break,大规模回滚。
    """
    from Plate import registry
    registry.collect("fin")
    spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    assert spec is not None
    assert spec.method == "POST"
```

---

## 4. 验收标准

### 4.1 必过(P0 阻塞)

| 验收项 | 测法 |
|---|---|
| `GIMBAL.from_default()` 在有 `GIMBAL_PLATE_URL` 时走 SDK,无则 fallback 本地 | 单元测试 + e2e |
| `GIMBAL.from_local()` 永远不走 SDK | 单元测试 |
| `GIMBAL.from_url(url, mode=LOCAL_FALLBACK)` 远端失败时 `OfflineError` 上抛 | 单元测试 |
| 字节级 pin:远端 manifest checksum == 本地 manifest checksum | 不变量 #13 |
| `from Plate import registry` 仍可用 | 不变量 #14 |
| `import gimbal` 不触发 service 子包加载 | 既有 invariant #1 |
| `GIMBAL` 顶层不在 `from gimbal import *` 时 export service | allowlist |

### 4.2 应过(P1 推荐)

| 验收项 | 测法 |
|---|---|
| 远端超时(2s)→ 静默 fallback 本地,业务执行不挂 | 注入 server 2s 延迟 |
| 缓存命中时,远端实际不被请求(可观测 `cache_stats()`) | 单元测试 |
| 旧 API 调用 1 次后产生 `DeprecationWarning` | 单元测试(用 `pytest.warns`) |
| `cache_stats()` 返回 `{"hit": n, "miss": m, "last_sync_at": ts}` | 单元测试 |

### 4.3 可选(P2 nice-to-have)

| 验收项 | 测法 |
|---|---|
| `GIMBAL` facade 支持 `async with` 异步上下文 | 单元测试 |
| 缓存目录可配置 + 默认路径符合 `platformdirs` 规范 | 文档 + 单元测试 |
| `GIMBAL.manifest()` 返回 dict(供报告生成用) | 单元测试 |

---

## 5. 风险与缓解

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| 远端 vs 本地 checksum 漂移 | server 端 `to_dict` 顺序变了,client 不感知 | 静默拿错 spec | 不变量 #13 字节 pin;失败即 CI 红 |
| 远端超时卡住业务 | server hang | GIMBAL 执行长时间阻塞 | SDK 层 2s 超时 + HYBRID 静默 fallback |
| 缓存目录权限问题 | CI runner 容器无 `~/.cache` 写权限 | 本地兜底也失败 | `GIMBAL_PLATE_CACHE_DIR` 可覆盖;fallback 链路不依赖缓存 |
| 旧 API 误删 | 后续 PR 重构 `Plate.registry` | 旧调用方 break | 本 PR 显式声明:`Plate.registry` 行为不变;DeprecationWarning 而非删除 |
| 双层缓存不一致 | SDK 内部缓存 + 业务层缓存 | 数据陈旧 | 本 PR **不**引入新缓存层,只有 SDK 一处 |

---

## 6. 文档同步

| 文档 | 改动 |
|---|---|
| [PLATE_DESIGN.md §7 不变承诺](../PLATE_DESIGN.md) | 加 "Phase 2 切换说明" 小节:SDK 是叠加层,registry 直读仍可用 |
| [PLATE_DESIGN.md §8 服务化](../PLATE_DESIGN.md) | 加 "Mode 选择" 表(LOCAL_ONLY / HYBRID / REMOTE_FIRST / LOCAL_FALLBACK) |
| [README.md](../../README.md) | 加 "Plate 服务化模式" 小节 + 4 个示例(默认 / 本地 / 远端 / 混合) |
| [phase2/INDEX.md](INDEX.md) | 更新 PR-2.4 状态:`待执行` → `已实现`,关键产出补 `GIMBAL` facade |
| [phase2/DECISIONS.md](DECISIONS.md) | 记 D22:`GIMBAL` 默认 mode = HYBRID,D23:`registry` 标 DeprecationWarning 但不删 |

---

## 7. 决策记录(给 DECISIONS.md)

- **D22**:`GIMBAL` 默认 mode = `HYBRID`(远端优先,失败 fallback 本地)
  - 理由:与 A4 本地优先远端备份 + 不变承诺 5 优雅降级 一致
  - 反对意见:有人主张默认 `LOCAL_ONLY` 更安全 → 否,因为"远端权威"是 Phase 2 业务目标
- **D23**:`from Plate import registry` 标 `DeprecationWarning` 但**不删**
  - 理由:A6 向后兼容;Phase 1 时期所有调用方需要迁移时间
  - 反对意见:有人主张直接删 → 否,会导致 PR-2.4 升级时大规模 break
- **D24**:`Plate.registry` 本体**不**改成"调 `_patched_resolve`"
  - 理由:避免引入网络 IO 到原本纯内存的 `registry.resolve`;保持 A1 不可变语义
  - 旧 API 走 `_legacy_registry` 直读 `_index`,行为不变;新 API 走 `GIMBAL` 走 SDK

---

## 8. 工作量估计

| 子任务 | 估计 |
|---|---|
| `GIMBAL` facade + 3 个工厂 | 0.4 PD |
| `_legacy` 桥接 + `DeprecationWarning` | 0.1 PD |
| mode 决策表单元测试(≥ 20) | 0.4 PD |
| 不变量 #13 #14 + e2e 字节 pin | 0.2 PD |
| 文档同步(PLATE_DESIGN / README / INDEX) | 0.2 PD |
| 决策记录(DECISIONS D22-D24) | 0.1 PD |
| 联调 + 全量回归 | 0.2 PD |
| **总计** | **1.6 PD**(与 INDEX.md 估计 1.5 PD 基本一致) |

---

## 9. reviewer 检查清单

| 项 | 检查 |
|---|---|
| A4 本地优先 | `LOCAL_ONLY` 模式不连远端(可断网验证) |
| A6 向后兼容 | `from Plate import registry` 调用无 break |
| 字节级 pin | 远端 manifest checksum == 本地(不变量 #13) |
| 离线 fallback | 拔网后 `HYBRID` 模式仍能跑 GIMBAL |
| 模式选择可观测 | `cache_stats()` 返回 hit/miss 计数 |
| 旧 API 警告 | `from Plate import registry` 调一次后产生 `DeprecationWarning` |
| 缓存目录合理 | 默认 `~/.cache/plate/{version}/` 或 `%LOCALAPPDATA%\plate\{version}\` |
| 环境变量优先 | 12-factor:`GIMBAL_PLATE_URL` 等可覆盖代码硬编码 |

---

## 10. 后续 PR 衔接

- **PR-2.5**(Phase 2 收口):更新 `BASELINE.md`,把 `GIMBAL` 列为推荐入口,
  `Plate.registry` 标"过渡期入口"
- **PR-2.6+**(Phase 3 范畴):
  - 删 `Plate.registry` 导出,只保留 `GIMBAL`
  - 实现 service 子包从远端拉(从 spec dict 重建 spec 实例)
  - 异步化:`async with GIMBAL(...)` + httpx 替代 urllib
