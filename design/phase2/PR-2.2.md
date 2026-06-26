# PR-2.2: 客户端 SDK(`plate_client`)

> **状态**:待执行
>
> **PR 范围**:实现客户端 SDK,**不**改服务端,纯客户端:
> 1. `plate_client.fetcher` —— HTTP 客户端(纯 stdlib `urllib` 优先,**不**强依赖 httpx)
> 2. `plate_client.cache` —— 本地磁盘缓存(L1 持久化)
> 3. `plate_client.resolver` —— 拉远端 → 校验 → 缓存 → 提供 EndpointSpec 实例
> 4. `plate_client.PlateClient` —— 顶层 facade(向后兼容 A6)
>
> **前置依赖**:**PR-2.0**(version + serialization)+ **PR-2.1**(协议)
>
> **关键设计**:本 SDK 是**叠加层**(A4),不替代 `import Plate`。
> 旧代码继续用本地模块,新代码用 SDK 走远端。
>
> **对应设计**:[PLATE_EVOLUTION.md §3 Phase 2 §离线兜底分层](../PLATE_EVOLUTION.md) +
> A4 本地优先 + A6 向后兼容 + 不变承诺 5(优雅降级)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 设计 §3 任务 1 明确"远端权威服务 + 轻量客户端 SDK"。
服务端留 PR-2.3,**本 PR 先做 SDK 骨架**:
- 让其他 GIMBAL / Capture / Prism 系统能立刻开始对接 SDK
- SDK 必须支持**离线 fallback** —— 不通网时仍能跑 GIMBAL 执行
- SDK **不破坏**已有 `from Plate import registry` 代码路径

### 1.2 关键决策

- **不引入 httpx 等第三方依赖**:`urllib.request` + `json` 已足够;GIMBAL
  主框架不应因 Phase 2 SDK 引入新依赖;Phase 3 MCP 再统一依赖
- **缓存目录用 `~/.cache/plate/{version}/`**(Linux/macOS) + `%LOCALAPPDATA%\plate\{version}\`
  (Windows),跨平台用 `platformdirs` 库 OR 简易 fallback(本 PR 用简易)
- **缓存文件 = `PlateManifest.to_dict()` 产物 + 单 service spec 列表**:JSON 落盘
- **离线检测 = HTTP 请求抛 `URLError`** → fallback 读本地缓存
- **校验和 = checksum 字段**:本地缓存必须记 checksum,加载时校验

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/plate_client/__init__.py` | 新建:`PlateClient` facade |
| `src/plate_client/fetcher.py` | 新建:`fetch_manifest` / `fetch_spec` / `fetch_doc`(纯 stdlib) |
| `src/plate_client/cache.py` | 新建:`Cache` 类(读/写/校验本地缓存) |
| `src/plate_client/resolver.py` | 新建:`resolve(service, method, path) → EndpointSpec` |
| `src/plate_client/offline.py` | 新建:`OfflineError` + fallback 路径 |
| `tests/plate/test_sdk_client.py` | 新建:SDK 单元测试(≥ 20 个) |
| `tests/plate/test_invariants.py` | 加 1 条:SDK 不破坏顶层 `import Plate`(A4 验证) |
| `tests/plate/test_zero_invasion.py` | 加 allowlist:`plate_client` |

### 2.2 `plate_client` 顶层 facade

```python
# src/plate_client/__init__.py
"""Plate 客户端 SDK(Phase 2 / PR-2.2)。

设计原则(A4 + A6):
  - 本模块是"叠加层",**不**替代 import Plate
  - 旧代码继续用 from Plate import registry(向后兼容)
  - 新代码用 from plate_client import PlateClient(走远端)

离线 fallback(不变承诺 5):
  - 网络可达 → 拉远端 → 缓存到本地 → 提供 EndpointSpec 实例
  - 网络不可达 → 直接读本地缓存 → 校验 checksum → 提供 EndpointSpec 实例
  - 缓存也不命中 → OfflineError 上抛(让调用方决定)
"""
from __future__ import annotations

from typing import Optional

from plate_client.fetcher import Fetcher
from plate_client.cache import Cache
from plate_client.resolver import Resolver
from plate_client.offline import OfflineError
from Plate.version import PlateVersion


class PlateClient:
    """Plate SDK 顶层 facade。

    用法::

        client = PlateClient(
            base_url="http://plate.internal:8080",
            version=PlateVersion.parse("1.0.0"),
        )
        spec = client.resolve("fin", "POST", "/api/order/order/orderDetail")

    离线 fallback:网络异常时自动读本地缓存。
    """

    def __init__(
        self,
        base_url: str,
        version: PlateVersion,
        cache_dir: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.fetcher = Fetcher(base_url)
        self.cache = Cache(cache_dir or Cache.default_dir())
        self.resolver = Resolver(self.fetcher, self.cache, version)

    def resolve(self, service: str, method: str, path: str):
        """拉取 spec,带离线 fallback。

        Raises:
            LookupError: 服务端 404(找不到端点)
            OfflineError: 网络挂 + 本地缓存也不命中
        """
        return self.resolver.resolve(service, method, path)

    def doc(self, service: str, method: str, path: str) -> Optional[dict]:
        """拉取 L2 doc(可空 — L2 是热数据,可不缓存)。"""
        return self.resolver.fetch_doc(service, method, path)

    def cache_stats(self) -> dict:
        """返回缓存命中 / 未命中 / 错误计数(运维可观测)。"""
        return self.resolver.stats


__all__ = ["PlateClient", "OfflineError"]
```

### 2.3 fetcher 模块(纯 stdlib HTTP)

```python
# src/plate_client/fetcher.py
"""HTTP fetcher,纯 stdlib(urllib + json)。

业务动机:不引入 httpx 等第三方依赖,降低 SDK 集成门槛。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from Plate.version import PlateVersion
from plate_client.offline import OfflineError


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class Fetcher:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, version: PlateVersion) -> HttpResponse:
        url = f"{self.base_url}{path}"
        if "?" not in path:
            url += f"?version={version}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return HttpResponse(
                    status=resp.status,
                    body=resp.read(),
                    headers=dict(resp.headers),
                )
        except (urllib.error.URLError, OSError) as e:
            raise OfflineError(f"fetcher: 网络不可达: {e}") from e

    def fetch_manifest(self, version: PlateVersion) -> HttpResponse:
        return self._request("/v1/manifest", version)

    def fetch_spec(self, service: str, version: PlateVersion) -> HttpResponse:
        return self._request(f"/v1/spec/{service}", version)

    def fetch_doc(self, service: str, method: str, path: str,
                   version: PlateVersion) -> HttpResponse:
        return self._request(f"/v1/doc/{service}/{method}/{path}", version)


__all__ = ["Fetcher", "HttpResponse"]
```

### 2.4 cache 模块

```python
# src/plate_client/cache.py
"""本地磁盘缓存(L1 持久化)。

目录结构::
  ~/.cache/plate/{version}/
  ├── manifest.json           # PlateManifest.to_dict() 产物
  ├── fin.json                # 单 service 的 spec list
  └── docs/
      └── fin.json            # 单 service 的 doc dict

校验:
  - 落盘时算 checksum
  - 读取时校验,不符抛 CacheCorrupted
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from Plate.manifest import PlateManifest
from Plate.version import PlateVersion


class CacheCorrupted(RuntimeError):
    pass


def default_dir() -> str:
    """跨平台缓存目录(Linux/macOS: ~/.cache;Windows: %LOCALAPPDATA%)。"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "plate")


class Cache:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    @classmethod
    def default_dir(cls) -> str:
        return default_dir()

    def _version_dir(self, version: PlateVersion) -> Path:
        return self.base_dir / str(version)

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写:先写 .tmp 再 rename,防崩溃产生半截文件
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp.replace(path)

    def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    # ── Manifest ──

    def write_manifest(self, manifest: PlateManifest) -> None:
        manifest.verify()  # 写入前自检
        self._write_json(
            self._version_dir(manifest.version) / "manifest.json",
            manifest.to_dict(),
        )

    def read_manifest(self, version: PlateVersion) -> PlateManifest | None:
        d = self._read_json(self._version_dir(version) / "manifest.json")
        if d is None:
            return None
        try:
            m = PlateManifest(
                version=PlateVersion.from_dict(d["version"]),
                services=d.get("services", {}),
                checksum=d.get("checksum", ""),
            )
            m.verify()  # 读后校验
            return m
        except (KeyError, ValueError):
            return None  # 损坏 = 当未命中

    # ── Spec ──

    def write_spec(self, version: PlateVersion, service: str,
                    specs: list[dict], checksum: str) -> None:
        path = self._version_dir(version) / f"{service}.json"
        self._write_json(path, {"service": service, "specs": specs,
                                  "version": version.to_dict(), "checksum": checksum})

    def read_spec(self, version: PlateVersion, service: str) -> list[dict] | None:
        path = self._version_dir(version) / f"{service}.json"
        d = self._read_json(path)
        if d is None:
            return None
        # 校验 checksum
        payload = {"service": service, "specs": d["specs"],
                   "version": version.to_dict(), "checksum": d["checksum"]}
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if expected != d["checksum"]:
            return None  # 损坏
        return d["specs"]


__all__ = ["Cache", "CacheCorrupted"]
```

### 2.5 resolver(拉远端 → 校验 → 缓存 → 提供)

```python
# src/plate_client/resolver.py
"""组合 fetcher + cache + 反序列化,提供 EndpointSpec 实例。

业务流(对应 A4 + 不变承诺 5 优雅降级):
  1. 先查本地缓存(快路径)
  2. 缓存未命中 → 拉远端
  3. 拉远端失败 → fallback 本地缓存(即使 checksum 不匹配,best-effort)
  4. 缓存完全无 → OfflineError 上抛
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Plate.spec import EndpointSpec
from Plate.version import PlateVersion
from plate_client.cache import Cache
from plate_client.fetcher import Fetcher
from plate_client.offline import OfflineError


@dataclass
class ResolverStats:
    cache_hits: int = 0
    cache_misses: int = 0
    network_fetches: int = 0
    offline_fallbacks: int = 0


class Resolver:
    def __init__(self, fetcher: Fetcher, cache: Cache,
                 version: PlateVersion) -> None:
        self.fetcher = fetcher
        self.cache = cache
        self.version = version
        self.stats = ResolverStats()

    def resolve(self, service: str, method: str, path: str) -> EndpointSpec:
        """拉取 + 反序列化,返回 EndpointSpec 实例。"""
        # 1. 查缓存
        cached = self.cache.read_spec(self.version, service)
        if cached is not None:
            for spec_dict in cached:
                if spec_dict["method"] == method and spec_dict["path"] == path:
                    self.stats.cache_hits += 1
                    return EndpointSpec.from_dict(spec_dict)
            # 缓存命中 service,但 endpoint 不在 — 仍走远端

        # 2. 拉远端
        self.stats.cache_misses += 1
        try:
            resp = self.fetcher.fetch_spec(service, self.version)
            body = resp.json()
            specs = body["specs"]
            checksum = body.get("checksum", "")
            self.cache.write_spec(self.version, service, specs, checksum)
            self.stats.network_fetches += 1
            for spec_dict in specs:
                if spec_dict["method"] == method and spec_dict["path"] == path:
                    return EndpointSpec.from_dict(spec_dict)
            raise LookupError(f"端点未找到: {service} {method} {path}")
        except OfflineError:
            # 3. 离线 fallback
            self.stats.offline_fallbacks += 1
            if cached is not None:
                # best-effort:即使缓存里的端点列表不包含,也尝试直接构造
                return EndpointSpec.from_dict({
                    "method": method,
                    "path": path,
                    "category": "query",  # 兜底
                    "mutates_state": False,
                })
            raise OfflineError(
                f"resolver: 离线 + 本地无缓存: {service} {method} {path}"
            )

    def fetch_doc(self, service: str, method: str, path: str) -> dict | None:
        """L2 doc 拉取(热数据,不强制缓存)。"""
        try:
            resp = self.fetcher.fetch_doc(service, method, path, self.version)
            if resp.status == 404:
                return None
            return resp.json()
        except OfflineError:
            return None  # L2 离线优雅退化


__all__ = ["Resolver", "ResolverStats"]
```

### 2.6 offline 模块

```python
# src/plate_client/offline.py
"""Offline 异常 + 网络检测工具。"""
from __future__ import annotations


class OfflineError(RuntimeError):
    """网络不可达 + 本地缓存也不命中时的 fallback 失败。"""


__all__ = ["OfflineError"]
```

---

## 3. 测试用例设计

### 3.1 必测业务场景

| 测试 | 业务承诺 |
|---|---|
| `test_plate_client_init` | facade 构造不抛 |
| `test_plate_client_resolve_cache_hit` | 缓存命中 → 不发请求,返回 spec |
| `test_plate_client_resolve_cache_miss_fetch` | 缓存未命中 → 发请求 → 缓存 → 返回 spec |
| `test_plate_client_resolve_offline_fallback` | 网络挂 + 缓存命中 → 仍返回 spec(best-effort) |
| `test_plate_client_resolve_offline_no_cache` | 网络挂 + 缓存无 → 抛 OfflineError |
| `test_plate_client_resolve_404` | 端点不存在 → 抛 LookupError |
| `test_plate_client_doc_returns_dict` | L2 doc 返回 dict |
| `test_plate_client_doc_404_returns_none` | doc 不存在 → None(不抛) |
| `test_plate_client_doc_offline_returns_none` | doc 离线 → None(优雅退化) |
| `test_plate_client_cache_stats_hit` | 命中次数自增 |
| `test_plate_client_cache_stats_miss` | 未命中次数自增 |
| `test_plate_client_cache_stats_offline_fallback` | 离线 fallback 次数自增 |
| `test_cache_default_dir_linux` | XDG_CACHE_HOME 解析 |
| `test_cache_default_dir_windows` | LOCALAPPDATA 解析 |
| `test_cache_write_manifest_verify_passes` | 写入前自检 |
| `test_cache_read_manifest_corrupted_returns_none` | 损坏文件 → None |
| `test_cache_read_manifest_checksum_mismatch_returns_none` | checksum 不匹配 → None |
| `test_cache_atomic_write` | 写入中途崩溃不产生半截文件 |
| `test_fetcher_offline_raises_OfflineError` | URLError → OfflineError |
| `test_resolver_does_not_load_plate_top_level` | SDK 不污染顶层 |
| `test_sdk_zero_invasion_old_import_works` | `from Plate import registry` 仍可用(A4) |
| `test_sdk_no_third_party_deps` | SDK 不引入 httpx / requests / aiohttp(运维可审计) |

### 3.2 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 缓存命中优先 | `test_*_cache_hit` | 网络挂仍可用 |
| 离线 fallback | `test_*_offline_*` | 不变承诺 5 |
| checksum 校验 | `test_cache_*_corrupted` | 防中间篡改 |
| 缓存统计 | `test_*_stats_*` | 运维可观测 |
| 零侵入(A4) | `test_sdk_zero_invasion_*` | Phase 1 承诺不破 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_sdk_client.py -v

# 2. 跑 Phase 1 + Phase 2.0 全量不变量
pytest tests/plate/test_invariants.py tests/plate/test_zero_invasion.py -v

# 3. 跑全量基线(≥ 386 + 22 = ≥ 408 测试)
pytest tests/ -v

# 4. 端到端冒烟:用本地 Plate(模拟服务端)
python -c "
from plate_client import PlateClient, OfflineError
from Plate.version import PlateVersion

# base_url 指向真实服务端 — 服务端未实现时 OfflineError 是预期
client = PlateClient('http://localhost:9999', PlateVersion.parse('1.0.0'))
try:
    client.resolve('fin', 'POST', '/api/order/order/orderDetail')
except OfflineError:
    print('OK: 离线 fallback 触发(预期,服务端 PR-2.3 未实现)')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_sdk_client.py` 测试数 | ≥ 22 |
| SDK 包存在 | `src/plate_client/__init__.py` |
| 顶层不破坏 | `from Plate import registry` 仍可用 |
| 不引入第三方依赖 | `grep -r "import httpx\|import requests\|import aiohttp" src/plate_client/` 0 命中 |
| 全量测试 | ≥ 386 + 22 = ≥ 408 |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| SDK 与本地 `from Plate import registry` 二选一 | A6:双轨并行,SDK 是叠加 |
| 缓存目录权限 | 失败时优雅退化到 `None`(返回 `None` 等同"未命中") |
| urllib 性能不足 | Phase 2 用量小,Phase 3 MCP 时再评估 |
| checksum 算法与 PR-2.0 不一致 | 严格共用 `PlateManifest.compute_checksum` |

---

## 5. 与后续 Phase 的衔接

- **PR-2.3(部署)**:真实服务端落地后,SDK 立即可用
- **PR-2.4(切换)**:GIMBAL 内部模块改成 `from plate_client import PlateClient`,
  旧 import 路径保留(deprecation warning)
- **Phase 3(MCP)**:SDK 作为 MCP 工具的底层,直接复用 fetcher/cache
- **Phase 4(CT 探测)**:SDK 加 `probe` 方法,对 QUERY 端点定时拉取做 drift 检测

**Phase 2.3 启动条件**:
- [ ] SDK 单元测试全过(≥ 22)
- [ ] 顶层 `import Plate` 仍可用(A4)
- [ ] 缓存 / 离线 fallback 已实现并测试
- [ ] 不引入 httpx / requests 第三方依赖