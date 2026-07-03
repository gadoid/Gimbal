# facade 子包(`Plate/facade/`)

> 本文档详细描述 `Plate/facade/` 子包下的**每一个模块、类、函数、方法、
> 异常、枚举**,以及"为什么这么设计"。读者在阅读完本文档后,应能完整
> 解释该子包的所有行为细节与设计动机。

---

## 1. 子包定位

`facade` 是 Plate 子系统的**对外门面**。它解决的核心问题:

> **业务代码不应该直接调 `registry`,因为:
> 1. `registry` 只支持本地模式(直接读内存 dict),无远端能力;
> 2. 未来业务可能需要走 SDK(拉远端 + 缓存);
> 3. 旧 API `from Plate import registry` 仍有依赖者(不能 break)。
>
> 需要一个**统一入口**,既能向后兼容(默认行为 = LOCAL_ONLY),又能
> 渐进式切到新模式(HYBRID / REMOTE_FIRST / LOCAL_FALLBACK)。**

`facade` 暴露的核心是 `PlateFacade` 类 + `PlateClient` 类 +
`PlateMode` 枚举 + `OfflineError` 异常 + `CacheStats` 类。
底层 `decide_resolve` 纯函数 + `legacy.warn_legacy_once` 桥接是实现
细节。

---

## 2. 模块组成

| 文件 | 职责 |
|---|---|
| `__init__.py` | 统一 re-export,定义 `PlateFacade` 类(门面核心) |
| `errors.py` | 共享类型:`PlateMode` 枚举 / `OfflineError` 异常 / `DEFAULT_VERSION` 常量 |
| `client.py` | `PlateClient` 类(同进程占位 SDK) + `CacheStats` 类(缓存统计) |
| `switch.py` | `decide_resolve` 纯函数(按 mode 路由) |
| `legacy.py` | `warn_legacy_once` 桥接(旧 API 迁移提示) |

---

## 3. 子包依赖关系

```
errors.py     ← (无依赖,叶子)
                ↑
client.py     ← errors.py + Plate.registry + Plate.manifest
                ↑
switch.py     ← errors.py + client.py + Plate.registry
                ↑
__init__.py   ← errors.py + client.py + switch.py + legacy.py
                + Plate.registry + Plate.manifest + Plate.version
```

**为什么 `errors.py` 是叶子:**
- `PlateMode` / `OfflineError` / `DEFAULT_VERSION` 是被多个模块引用
  的"基础类型"。
- 抽到独立文件避免循环依赖(`client.py` 需要 `OfflineError` re-export,
  `__init__.py` 也需要,但 `__init__.py` 不应被 `client.py` import)。

---

## 4. `errors.py` 模块详解

### 4.1 `PlateMode` 枚举

```python
class PlateMode(str, Enum):
    """Plate 数据源模式(对应 A4 本地优先 + A6 向后兼容)。"""

    HYBRID = "hybrid"
    REMOTE_FIRST = "remote-first"
    LOCAL_FALLBACK = "local-fallback"
    LOCAL_ONLY = "local-only"
```

**字段语义(四个 mode):**

| Mode | 行为 | 失败时 | 业务场景 |
|---|---|---|---|
| `HYBRID` | 先 SDK,失败静默 fallback 本地 | 静默 fallback | 日常运行(默认推荐) |
| `REMOTE_FIRST` | 先 SDK,失败上抛 | 上抛 `OfflineError` | 强一致要求(必须用最新契约) |
| `LOCAL_FALLBACK` | 先 SDK,失败读缓存,仍失败上抛 | 上抛 `OfflineError` | 离线优先 + 缓存兜底 |
| `LOCAL_ONLY` | 直接走本地 registry | N/A(本地永远能 resolve) | 旧 API 兼容 / 单测 |

**为什么四种 mode:**
- `LOCAL_ONLY` — 向后兼容(让旧 `from Plate import registry` 行为不变)。
- `HYBRID` — 最常用场景(默认 mode),SDK 优先 + 本地兜底,业务无感。
- `REMOTE_FIRST` — 强一致场景(契约漂移检测、生产联调)。
- `LOCAL_FALLBACK` — 离线场景(断网时仍能用本地缓存)。

**为什么 `str, Enum`:**
- 与 `EndpointCategory` 同源 — 序列化友好(直接产 `"hybrid"` 等字符串)。
- 可哈希、可作 dict key。

### 4.2 `OfflineError` 异常

```python
class OfflineError(RuntimeError):
    """网络不可达 + 本地缓存也不命中时上抛(对应 REMOTE_FIRST / LOCAL_FALLBACK)。"""
```

**字段语义:**
- `RuntimeError` 子类。
- 业务触发:网络不可达 + 本地缓存也不命中,且 mode 是 `REMOTE_FIRST`
  或 `LOCAL_FALLBACK`(这两种 mode 拒绝静默 fallback)。

**为什么 `RuntimeError` 而非自定义异常基类:**
- `RuntimeError` 是 Python 惯例 — "运行时环境问题" 用 `RuntimeError`。
- 业务上"网络不可达"是**调用时才知道的**情况,符合"运行时"语义。
- 调用方 try/except `RuntimeError` 或 `OfflineError` 即可。

### 4.3 `DEFAULT_VERSION` 常量

```python
DEFAULT_VERSION: PlateVersion = PlateVersion(1, 0, 0)
```

**字段语义:**
- 默认版本(1.0.0)。
- 业务上"未指定 version"时使用。
- 当前对应 `server` 端 `SUPPORTED_VERSIONS = (DEFAULT_VERSION,)` 的
  唯一版本。

**为什么在 `errors.py` 而不是 `version.py` 定义:**
- `version.py` 是"叶子工具",只放 `PlateVersion` 数据类。
- `DEFAULT_VERSION` 是"业务常量",依赖 `PlateVersion`,放在 facade
  内部更合理。
- `errors.py` 是 facade 子包的"基础类型文件",放 `DEFAULT_VERSION`
  自然。

---

## 5. `legacy.py` 模块详解

### 5.1 `LEGACY_MIGRATION_HINT` 常量

```python
LEGACY_MIGRATION_HINT = (
    "[Plate] ``from Plate import registry`` 是遗留路径。"
    "请迁移到 ``from Plate.facade import PlateFacade`` "
    "(默认 mode = LOCAL_ONLY,行为与旧 API 一致;新代码用 PlateFacade.from_url(...) 走 SDK)。"
    "本 PR(2.4)周期内仍可用,Phase 3 收尾前保留。"
)
```

**字段语义:**
- 给旧 API 用户的迁移提示字符串。
- 在 `warn_legacy_once` 里以 `DeprecationWarning` 发出。

### 5.2 `_warned` 模块级状态

```python
_warned = False
```

**字段语义:**
- 进程级"已发过警告"标志。
- 整个进程期内最多发一次(避免污染日志)。

### 5.3 `warn_legacy_once() -> None`

```python
def warn_legacy_once() -> None:
    """发一次 DeprecationWarning(整个进程期内)。"""
    global _warned
    if not _warned:
        warnings.warn(LEGACY_MIGRATION_HINT, DeprecationWarning, stacklevel=3)
        _warned = True
```

**核心行为:**
1. 检查 `_warned` 标志,True 直接返回。
2. False → 发 `DeprecationWarning` + 把 `_warned` 置 True。
3. 整个进程期内只发一次。

**为什么用 `DeprecationWarning` 而不是 `print` / `logging`:**
- `DeprecationWarning` 是 Python 标准警告类别,易于被测试框架捕获。
- 静默(默认 warning filter 不显示),不污染正常日志。
- 可被 CI 配置 `-W error::DeprecationWarning` 转成 fail-fast。

**为什么用模块级 `_warned` 标志:**
- `warnings.warn` 默认会按 message 字符串去重,但**某些情况**(如
  message 里有动态内容)不会去重。
- 显式标志是"业务层"的去重保证,跨各种 Python 版本都生效。

**为什么 `stacklevel=3`:**
- `warn_legacy_once` 被 `PlateFacade.__init__` 调,后者被业务代码
  调。
- `stacklevel=3` 让警告指向"业务代码的位置",而不是
  `PlateFacade.__init__` 的内部行号。
- 这给用户最直接的"我该改哪里"信号。

### 5.4 `reset_warn_flag() -> None`

```python
def reset_warn_flag() -> None:
    """测试用:重置 _warned 标志(单测隔离)。"""
    global _warned
    _warned = False
```

**用途:** 单测需要"测完一次警告后,下次还能再测"。
**为什么"测试用":** 同 `core._Registry.reset()`,生产代码不应调。

---

## 6. `client.py` 模块详解

### 6.1 `CacheStats` 类

```python
class CacheStats:
    """缓存命中统计(可观测性)。"""
```

**字段:**
- `_lock: threading.Lock` — 保护 `_hit` / `_miss` / `_last_sync_at`。
- `_hit: int` — 命中次数。
- `_miss: int` — 未命中次数。
- `_last_sync_at: float` — 最后一次 sync 的 unix timestamp(`time.time()`)。

**为什么用 `threading.Lock`:**
- 缓存统计是"高频写"操作(每次 `resolve` 都 `record_hit` 或
  `record_miss`)。
- 多线程并发累加时,Python `int += 1` 不是原子的(读 + 加 + 写三
  步),需要锁保护。
- 单锁简单(性能上单点累加有竞争,但场景下 QPS 不高,可接受)。

#### 6.1.1 `record_hit() -> None`

```python
def record_hit(self) -> None:
    with self._lock:
        self._hit += 1
        self._last_sync_at = time.time()
```

**核心行为:**
- 持锁 → `_hit += 1` → 更新 `_last_sync_at`。
- 命中时同时更新 `last_sync_at` — 反映"最近一次成功从缓存/远端拿
  到数据的时间"。

#### 6.1.2 `record_miss() -> None`

```python
def record_miss(self) -> None:
    with self._lock:
        self._miss += 1
```

**核心行为:**
- 持锁 → `_miss += 1`。
- **不**更新 `_last_sync_at`(未命中不算"sync")。

#### 6.1.3 `snapshot() -> dict[str, Any]`

```python
def snapshot(self) -> dict[str, Any]:
    with self._lock:
        return {
            "hit": self._hit,
            "miss": self._miss,
            "last_sync_at": self._last_sync_at,
        }
```

**核心行为:**
- 持锁 → 返回三个字段的 dict 副本(快照)。

**为什么返回 dict 副本(而非内部状态引用):**
- 调用方拿到的是"这一刻"的快照,后续并发修改不影响该副本。
- 让 snapshot 在多线程间传递安全。

#### 6.1.4 `reset() -> None`

```python
def reset(self) -> None:
    with self._lock:
        self._hit = 0
        self._miss = 0
        self._last_sync_at = 0.0
```

**用途:** 单测隔离。

### 6.2 `PlateClient` 类

```python
class PlateClient:
    """Plate SDK(同进程占位实现,Phase 3 替换为真 HTTP)。

    离线检测:本会话用 "显式 offline=True" 模拟(便于单测);
    Phase 3 替换为 URLError / TimeoutError 捕获 + retries。
    """
```

**字段:**
- `base_url: str` — 服务端地址。
- `version: PlateVersion` — 期望的协议版本。
- `cache_dir: Optional[str]` — 落盘缓存目录(本期未实现)。
- `_offline: bool` — 显式 offline 标志(测试用,模拟网络抖动)。
- `_stats: CacheStats` — 缓存命中统计。
- `_cache: dict[tuple[str, str, str], Any]` — 内存缓存(`(service,
  method, path)` → `EndpointSpec`)。
- `_manifest_cache: Optional[dict]` — manifest 缓存(整版本只算一次)。

#### 6.2.1 `__init__`

```python
def __init__(
    self,
    *,
    base_url: str,
    version: PlateVersion,
    cache_dir: Optional[str] = None,
    offline: bool = False,
) -> None:
    self.base_url = base_url
    self.version = version
    self.cache_dir = cache_dir
    self._offline = offline
    self._stats = CacheStats()
    self._cache: dict[tuple[str, str, str], Any] = {}
    self._manifest_cache: Optional[dict] = None
```

**为什么全部 keyword-only 参数:**
- 强制调用方写 `base_url=...` / `version=...`,可读性高。
- 防止位置参数顺序错乱(`base_url` 和 `version` 都是位置都合理)。

**为什么 `offline` 默认 `False`:**
- 真实业务场景下"在线"是默认;测试场景下手动开 `offline=True`。

**为什么 `_cache` 和 `_manifest_cache` 内存而非落盘:**
- 本期(Phase 2)是**同进程占位实现**,模拟"远端权威"语义。
- 落盘缓存是 Phase 3 的事(`cache_dir` 参数已经留好,实装是加
  `pickle` / `json` 落盘逻辑)。

#### 6.2.2 `set_offline(offline: bool) -> None`

```python
def set_offline(self, offline: bool) -> None:
    """测试用:切换 offline 状态(模拟网络抖动)。"""
    self._offline = offline
```

**用途:** 测试场景下模拟"网络突然断了"。业务代码不应调。

**为什么不在 `__init__` 之后提供"再切回 online":**
- 测试需要"在线 → 离线 → 在线"循环。
- `set_offline(False)` 即可切回。

#### 6.2.3 `resolve(service, method, path) -> Any`

```python
def resolve(self, service: str, method: str, path: str) -> Any:
    """按 (service, method, path) 拿 EndpointSpec。"""
    key = (service, method.upper(), path)
    # 1. 查缓存
    if key in self._cache:
        self._stats.record_hit()
        return self._cache[key]
    # 2. 拉"远端"(本会话:同进程 registry)
    if self._offline:
        self._stats.record_miss()
        raise OfflineError(f"PlateClient offline + cache miss: {key}")
    # 3. 本会话走本地 registry 模拟"远端权威"
    _legacy_registry.collect(service)
    spec = _legacy_registry.resolve(service, method, path)
    self._cache[key] = spec
    self._stats.record_miss()
    return spec
```

**算法步骤:**

1. **key 构造**:`(service, method.upper(), path)` — `method` 统一
   大写,防调用方传 `"post"` vs `"POST"` 撞不同 key。
2. **查缓存**:
   - 命中 → `record_hit` + 返回缓存。
   - 未命中 → 继续。
3. **offline 检测**:
   - offline → `record_miss` + `raise OfflineError`(因为没缓存且
     offline 没法拉远端)。
4. **拉"远端"**(本会话走 `_legacy_registry`):
   - `collect(service)` 触发 service 子包 import。
   - `resolve(service, method, path)` 拿到 spec。
   - 写缓存 + `record_miss`。
5. **返回 spec**。

**为什么 `method.upper()`:**
- 业务场景下 HTTP method 通常大写(`POST` / `GET` 等),但调用方可能
  传 `"post"`。
- 显式大写统一,避免"同一端点两次请求 key 不同"导致缓存命中率下降。

**为什么 offline + miss 抛 `OfflineError`:**
- 这是 `REMOTE_FIRST` / `LOCAL_FALLBACK` 模式下业务可见的"网络断了"
  信号。
- `decide_resolve` 收到这个错后,根据 mode 决定"静默 fallback"还是
  "上抛"。

**为什么"未命中算 miss 而非算 hit":**
- `record_hit` 是"直接从缓存拿到"(`fast path`)。
- `record_miss` 是"必须真正去拉一次"(`slow path`)。
- 命中率 = `hit / (hit + miss)` — 反映 SDK 缓存效果。

#### 6.2.4 `manifest() -> dict`

```python
def manifest(self) -> dict:
    """返回 manifest dict。"""
    if self._manifest_cache is not None:
        self._stats.record_hit()
        return dict(self._manifest_cache)
    if self._offline:
        self._stats.record_miss()
        raise OfflineError("PlateClient offline + no manifest cache")
    # 构造 manifest — 走 SUPPORTED_SERVICES 风格的固定列表(本会话只支持 fin)
    services: dict[str, list[dict]] = {}
    for svc in ("fin",):
        try:
            _legacy_registry.collect(svc)
        except LookupError:
            continue
        services[svc] = [
            s.to_dict() for k, s in _legacy_registry._index.items()
            if k.service == svc
        ]
    m = PlateManifest.from_services(self.version, services)
    self._manifest_cache = m.to_dict()
    self._stats.record_miss()
    return dict(self._manifest_cache)
```

**算法步骤:**
1. **查 manifest 缓存** — 命中 → `record_hit` + 返回。
2. **offline 检测** — offline + 无缓存 → `OfflineError`。
3. **构造 manifest**:
   - 遍历 `("fin",)`(本会话固定列表 — Phase 3 替换为从远端
     `/v1/version` 拉)。
   - 每个 service 调 `collect` + 提取该 service 的所有 `to_dict()`。
   - `PlateManifest.from_services` 自动算 checksum + 排序。
4. **写 manifest 缓存** + `record_miss`。
5. **返回** `dict(...)`(副本,防调用方误改缓存)。

**为什么 manifest 缓存与 resolve 缓存分开:**
- `resolve` 按 `(service, method, path)` 粒度缓存,空间大。
- `manifest` 是"全版本快照",粒度大但变化少(同一版本内基本不变)。
- 分开缓存可让 manifest 缓存"长寿命",resolve 缓存"短寿命"(L1)。

**为什么"本会话只支持 fin":**
- 当前的 `_legacy_registry._index` 仅有 fin service。
- Phase 3 替换为真 HTTP 后,这一步改为"调 `/v1/version` 拿支持列表"。

#### 6.2.5 `cache_stats() -> dict[str, Any]`

```python
def cache_stats(self) -> dict[str, Any]:
    return self._stats.snapshot()
```

**用途:** 可观测性 — 让 `PlateFacade.cache_stats()` 透传。

#### 6.2.6 `reset_cache() -> None`

```python
def reset_cache(self) -> None:
    self._cache.clear()
    self._manifest_cache = None
    self._stats.reset()
```

**用途:** 单测隔离(清缓存 + 重置统计)。

---

## 7. `switch.py` 模块详解

### 7.1 `decide_resolve` 纯函数

```python
def decide_resolve(
    *,
    mode: PlateMode,
    client: Optional[PlateClient],
    service: str,
    method: str,
    path: str,
    fallback_log: Optional[Callable[[str], None]] = None,
) -> Any:
    """按 mode 决定 resolve 路径(纯函数,无副作用)。

    参数:
      - mode:PlateMode 枚举
      - client:PlateClient 实例(LOCAL_ONLY 时可为 None)
      - fallback_log:HYBRID fallback 时调用的日志函数(可注入测试 spy)

    返回:EndpointSpec 实例
    抛:OfflineError(REMOTE_FIRST / LOCAL_FALLBACK 模式下,SDK 拉不到)
    """
    if mode == PlateMode.LOCAL_ONLY or client is None:
        return _legacy_registry.resolve(service, method, path)
    if mode == PlateMode.HYBRID:
        try:
            return client.resolve(service, method, path)
        except OfflineError as e:
            if fallback_log is not None:
                fallback_log(f"SDK 不可达,fallback 本地: {e}")
            return _legacy_registry.resolve(service, method, path)
    # REMOTE_FIRST / LOCAL_FALLBACK:不静默 fallback
    return client.resolve(service, method, path)
```

**核心行为 — 按 mode 决策表:**

| Mode | 决策 |
|---|---|
| `LOCAL_ONLY` | 走 `_legacy_registry.resolve`(本地永远能 resolve) |
| `client is None` | 走 `_legacy_registry.resolve`(与 LOCAL_ONLY 同) |
| `HYBRID` | 先 `client.resolve`,`OfflineError` 时**静默** fallback 本地(可记录日志) |
| `REMOTE_FIRST` / `LOCAL_FALLBACK` | 直接 `client.resolve`,失败上抛(由 `client` 内部决定) |

**为什么用纯函数:**
- 决策逻辑是"业务规则",无副作用,适合纯函数。
- 单测可独立覆盖每个分支(无需构造 `PlateFacade`)。
- 避免循环依赖(`PlateFacade` 调 `decide_resolve`,反向不能 import
  `PlateFacade`)。

**为什么 `fallback_log` 是可注入回调:**
- 默认 None = 不记录。
- `PlateFacade` 注入一个 `lambda msg: _log.debug(...)` 把 fallback
  行为记到日志。
- 单测可以注入一个 mock spy,验证"发生了 fallback"。

**为什么不 `import Plate` 顶层:**
- 本函数 import `_legacy_registry`(同进程占位),`PlateFacade.__init__`
  也 import 同样的东西 — 不会循环。
- 但保持 `_legacy_registry` 是"私有别名"(`import ... as _`),
  表达"这是内部依赖,不要在业务代码里这样 import"。

---

## 8. `__init__.py` 模块详解(门面核心)

### 8.1 `PlateFacade` 类

```python
class PlateFacade:
    """Plate 子系统业务入口(对应 PR-2.4 §2.2 GIMBAL → 重命名为 PlateFacade)。

    3 个工厂:
      - ``from_default()``:从环境变量读 mode + base_url,缺省 LOCAL_ONLY
      - ``from_local()``:永远只走本地 registry
      - ``from_url(url)``:走 SDK,可选 mode(HYBRID/REMOTE_FIRST/LOCAL_FALLBACK)

    业务方法:
      - ``resolve(service, method, path)``:按 mode 路由
      - ``manifest()``:返回 manifest dict
      - ``cache_stats()``:缓存命中统计
    """
```

#### 8.1.1 `__init__`

```python
def __init__(
    self,
    *,
    mode: PlateMode,
    version: PlateVersion,
    base_url: Optional[str] = None,
    cache_dir: Optional[str] = None,
    client: Optional[PlateClient] = None,
) -> None:
    self._mode = mode
    self._version = version
    self._base_url = base_url
    self._cache_dir = cache_dir
    if client is not None:
        self._client = client
    elif mode in (PlateMode.HYBRID, PlateMode.REMOTE_FIRST, PlateMode.LOCAL_FALLBACK):
        if not base_url:
            raise ValueError(
                f"[PlateFacade] mode={mode} requires base_url"
            )
        self._client = PlateClient(
            base_url=base_url,
            version=version,
            cache_dir=cache_dir,
        )
    else:
        self._client = None  # LOCAL_ONLY

    # 首次通过 facade 入口访问时,触发一次 legacy 迁移提示
    warn_legacy_once()
```

**字段语义:**
- `_mode` — 模式。
- `_version` — 版本。
- `_base_url` — 远端地址(None = 不连远端)。
- `_cache_dir` — 落盘缓存目录(本期未实现)。
- `_client` — SDK 实例(LOCAL_ONLY 时为 None)。

**算法步骤:**

1. 存基本字段。
2. 决定 `_client`:
   - 显式传 `client=...` → 用调用方提供的(便于测试注入 mock)。
   - 否则如果 mode 是 HYBRID / REMOTE_FIRST / LOCAL_FALLBACK(需要
     SDK) → 构造 `PlateClient`(要求 `base_url`)。
   - 否则(`LOCAL_ONLY`)→ `_client = None`。
3. 触发一次 `warn_legacy_once()`(进程级只发一次)。

**为什么 `client` 优先级最高:**
- 单测可注入 mock client(模拟各种网络情况)。
- 业务场景几乎不会显式传 `client`(都是 `from_default` / `from_url`
  工厂)。

**为什么 `base_url` 在某些 mode 下必填:**
- HYBRID / REMOTE_FIRST / LOCAL_FALLBACK 都依赖 SDK,SDK 必连远端。
- `LOCAL_ONLY` 不连远端,`base_url` 无意义。
- 显式 `raise ValueError` 让错误信息明确,而不是构造 `PlateClient`
  时神秘失败。

**为什么 `__init__` 末尾调 `warn_legacy_once`:**
- "facade 入口被首次使用"是发警告的最佳时机。
- 业务代码调 `PlateFacade()` 这一刻,作者可能正在从 `registry` 迁来
  — 给一个明确提示。
- 进程级只发一次,不污染。

#### 8.1.2 `from_default` 工厂

```python
@classmethod
def from_default(cls) -> "PlateFacade":
    """默认入口:从环境变量读 mode + base_url,缺省走 LOCAL_ONLY。"""
    mode_str = os.environ.get("GIMBAL_PLATE_MODE", "local-only")
    try:
        mode = PlateMode(mode_str)
    except ValueError:
        mode = PlateMode.LOCAL_ONLY
    base_url = os.environ.get("GIMBAL_PLATE_URL")
    version_str = os.environ.get("GIMBAL_PLATE_VERSION", "1.0.0")
    try:
        version = PlateVersion.parse(version_str)
    except ValueError:
        version = DEFAULT_VERSION
    if mode == PlateMode.LOCAL_ONLY or not base_url:
        return cls(mode=PlateMode.LOCAL_ONLY, version=version)
    return cls(mode=mode, version=version, base_url=base_url)
```

**环境变量约定:**

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `GIMBAL_PLATE_MODE` | `"local-only"` | mode 字符串(枚举值) |
| `GIMBAL_PLATE_URL` | `None` | 远端地址 |
| `GIMBAL_PLATE_VERSION` | `"1.0.0"` | 版本号 |

**容错策略:**
- `mode` 字符串非法 → 降级到 `LOCAL_ONLY`(不抛错)。
- `version` 字符串非法 → 降级到 `DEFAULT_VERSION`(不抛错)。
- `mode` 是远端 mode 但 `base_url` 没设 → 降级到 `LOCAL_ONLY`(不抛
  错)。

**为什么环境变量容错:**
- 业务环境千差万别 — 旧 CI 脚本可能没设新环境变量,直接走
  `LOCAL_ONLY` 不破坏测试。
- 容错原则:环境变量配置错不能让 CI 红,只能让 facade 退回到最保守
  行为。

**为什么用 `GIMBAL_` 前缀(而非 `PLATE_`):**
- 命名历史 — Plate 原本叫 GIMBAL,后改名为 Plate,环境变量保留
  `GIMBAL_` 前缀以向后兼容(老 CI 脚本可能仍用旧名)。

#### 8.1.3 `from_local` 工厂

```python
@classmethod
def from_local(
    cls, version: PlateVersion = DEFAULT_VERSION
) -> "PlateFacade":
    """显式本地模式:不连远端,纯本地 registry。"""
    return cls(mode=PlateMode.LOCAL_ONLY, version=version)
```

**用途:** 单测 / 开发场景,明确"我不连远端"。

**为什么 `version` 默认 `DEFAULT_VERSION`:**
- 单测通常不关心版本,给一个默认值减少样板。
- 业务场景可显式 `from_local(version=PlateVersion.parse("1.0.0"))`。

#### 8.1.4 `from_url` 工厂

```python
@classmethod
def from_url(
    cls,
    base_url: str,
    version: PlateVersion = DEFAULT_VERSION,
    cache_dir: Optional[str] = None,
    mode: PlateMode = PlateMode.HYBRID,
) -> "PlateFacade":
    """显式远端模式:可指定 HYBRID / REMOTE_FIRST / LOCAL_FALLBACK。"""
    return cls(
        mode=mode,
        version=version,
        base_url=base_url,
        cache_dir=cache_dir,
    )
```

**默认 mode = `HYBRID`:**
- HYBRID 是"日常运行推荐 mode"(SDK 优先 + 本地兜底)。
- 业务显式调 `from_url(...)` 时,大概率是想"用 SDK",HYBRID 风险
  最低。

#### 8.1.5 `resolve` 业务方法

```python
def resolve(self, service: str, method: str, path: str) -> Any:
    """按 (service, method, path) 拿 EndpointSpec。

    行为依赖 mode(委托 ``gimbal._switch.decide_resolve``):
      - LOCAL_ONLY:直接 ``registry.resolve()``
      - HYBRID:SDK 拉远端 → 失败 fallback 本地
      - REMOTE_FIRST:SDK 拉远端 → 失败 → OfflineError 上抛
      - LOCAL_FALLBACK:SDK 拉远端 → 失败 → 读缓存 → 仍失败 → OfflineError
    """
    return decide_resolve(
        mode=self._mode,
        client=self._client,
        service=service,
        method=method,
        path=path,
        fallback_log=lambda msg: _log.debug("[PlateFacade] %s", msg),
    )
```

**委托给 `decide_resolve`:**
- 业务方法本身只做"委托 + 注入 fallback_log"。
- 决策逻辑在 `switch.py`(纯函数,单测覆盖)。

**为什么 `fallback_log` 是 lambda:**
- 把"[PlateFacade]"前缀加在日志里,便于日志过滤。
- `lambda` 闭包捕获 `self`,无需显式传 method 之类的参数。

#### 8.1.6 `manifest` 业务方法

```python
def manifest(self) -> dict:
    """返回 manifest dict(走 SDK 或本地,取决于 mode)。"""
    if self._mode == PlateMode.LOCAL_ONLY or self._client is None:
        services: dict[str, list[dict]] = {}
        for svc in ("fin",):
            try:
                _legacy_registry.collect(svc)
            except LookupError:
                continue
            services[svc] = [
                s.to_dict() for k, s in _legacy_registry._index.items()
                if k.service == svc
            ]
        return PlateManifest.from_services(self._version, services).to_dict()
    return self._client.manifest()
```

**算法:**
- LOCAL_ONLY 或 `_client is None` → 本地构造 manifest。
- 否则 → 委托 `client.manifest()`(走 SDK)。

**为什么 LOCAL_ONLY 时不直接用 `client`:**
- LOCAL_ONLY 是"无 SDK"模式,`_client` 永远是 None。
- 显式分两个分支让"本地构造"和"SDK 构造"逻辑清晰。

#### 8.1.7 `cache_stats` 业务方法

```python
def cache_stats(self) -> dict[str, Any]:
    """缓存命中统计。"""
    if self._client is None:
        return {"mode": "local-only", "hit": 0, "miss": 0}
    return self._client.cache_stats()
```

**算法:**
- LOCAL_ONLY → 返回固定的"零统计"dict(本地无缓存)。
- 否则 → 委托 `client.cache_stats()`。

#### 8.1.8 三个只读 property

```python
@property
def mode(self) -> PlateMode:
    return self._mode

@property
def version(self) -> PlateVersion:
    return self._version

@property
def base_url(self) -> Optional[str]:
    return self._base_url
```

**用途:** introspection — 业务代码可"读 facade 的状态"用于日志 /
调试。

### 8.2 模块级 logger

```python
_log = logging.getLogger("plate.facade")
```

**字段语义:**
- 命名为 `"plate.facade"`(不是 `"Plate.facade"`),符合 logging 惯例
  (logger 名用小写 + 点分)。
- `PlateFacade.resolve` 的 fallback_log 走这个 logger。

### 8.3 公开 API 一览(`__all__`)

```python
__all__ = [
    "PlateMode",
    "PlateClient",
    "PlateFacade",
    "OfflineError",
    "CacheStats",
    "DEFAULT_VERSION",
]
```

| 名称 | 来自 | 类型 |
|---|---|---|
| `PlateMode` | `errors.py` | 枚举 |
| `PlateClient` | `client.py` | 类 |
| `PlateFacade` | `__init__.py` | 类 |
| `OfflineError` | `errors.py` | 异常 |
| `CacheStats` | `client.py` | 类 |
| `DEFAULT_VERSION` | `errors.py` | 常量 |

`switch.py` / `legacy.py` 不在 `__all__`(内部使用,业务不应直接
import)。

---

## 9. 调用方典型代码示例

```python
# 1. 默认入口(从环境变量读 mode + base_url)
from Plate.facade import PlateFacade
pf = PlateFacade.from_default()
spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")

# 2. 显式本地
pf = PlateFacade.from_local()
spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")

# 3. 显式远端
pf = PlateFacade.from_url("http://plate.internal:8080")
spec = pf.resolve("fin", "POST", "/api/order/order/orderDetail")

# 4. 强一致(REMOTE_FIRST)
from Plate.facade import PlateMode
pf = PlateFacade.from_url(
    "http://plate.internal:8080",
    mode=PlateMode.REMOTE_FIRST,
)

# 5. 拿 manifest
m = pf.manifest()
print(m["version"], m["services"])

# 6. 缓存命中统计
stats = pf.cache_stats()
print(stats)
# {"hit": 5, "miss": 2, "last_sync_at": 1234567890.123}

# 7. introspection
print(pf.mode, pf.version, pf.base_url)
```

---

## 10. 不变量总结(本子包承诺的不变式)

1. **默认 mode 行为 = 旧 API**:`from_default()` 走 LOCAL_ONLY 时,
   行为与 `from Plate import registry` 一致 — 向后兼容。
2. **HYBRID 静默 fallback**:SDK 不可达时,业务无感,降级本地。
3. **REMOTE_FIRST / LOCAL_FALLBACK 显式失败**:SDK 不可达时
   `OfflineError` 上抛,业务必须处理。
4. **进程级一次 legacy 警告**:`from Plate import registry` 路径
   仍可用,但首次通过 `PlateFacade()` 时会发 `DeprecationWarning`。
5. **环境变量容错**:`from_default()` 不会因配置错而 raise,只降
   级到 `LOCAL_ONLY` + `DEFAULT_VERSION`。
6. **mode 决策纯函数化**:`decide_resolve` 是无状态纯函数,单测
   可独立覆盖每个分支。

---

## 11. 设计权衡

| 决策 | 取舍 |
|---|---|
| `PlateFacade` 与 `from Plate import registry` 并存 | 业务迁移期需要;完全破坏兼容性是禁忌 |
| 3 个工厂(`from_default` / `from_local` / `from_url`) | 显式优于隐式;每个工厂职责单一 |
| 环境变量用 `GIMBAL_` 前缀 | 历史兼容,新代码可改 `PLATE_` 但要同时支持旧的 |
| `decide_resolve` 纯函数化 | 单测可独立覆盖;避免循环依赖 |
| `client` 参数可注入 | 单测可 mock 各种网络情况 |
| `cache_dir` 参数预留 | Phase 3 落盘缓存的接口,本期不实装 |
| `offline` 是显式状态(非网络真实检测) | 本期同进程占位;Phase 3 替换为 URLError 捕获 |
| `_warned` 标志 + `DeprecationWarning` | 警告只发一次;`DeprecationWarning` 是 Python 惯例 |
| `manifest` 缓存与 `resolve` 缓存分开 | 不同生命周期;manifest 缓存可长寿命 |
| `_legacy_registry` 私有别名 | 表达"这是 facade 内部对 registry 的引用" |
