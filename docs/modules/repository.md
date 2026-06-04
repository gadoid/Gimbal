# Repository 模块

> 资产仓库（Asset Registry），仿 Docker Registry v2 的内容寻址存储。
>
> **当前**：本地文件系统实现（`LocalFsContentStore`）。
> **未来**：PostgreSQL 实现（`PostgresContentStore`，用于多机/生产）。

## 目录结构

```
gimbal/repository/
├── __init__.py                # 公共 API 导出
├── models.py                  # AssetRef / AssetRecord / AssetContent
├── store.py                   # ContentStore 协议 + AssetStore 门面
├── exceptions.py              # 异常 re-export（兼容层）
└── backends/
    ├── __init__.py
    ├── filesystem.py          # LocalFsContentStore（本地 FS 实现）
    ├── mysql.py               # 占位（未来 PG 替代）
    └── python_module.py       # 占位（未来 PG 替代）
```

> **注**：`core/asset_resolver.py` 是 CLI 桥接层（用 `AssetStore` 解析 ID → `ResolvedAsset`），
> 文档见 [core.md](core.md#asset_resolver)。

## 设计目标

| 目标              | 实现方式                                        |
| ----------------- | ----------------------------------------------- |
| 不可变内容        | blob 路径由 sha256 决定，相同内容物理去重       |
| tag 灵活          | tag 索引与 blob 分离，可重写/删除，blob 不变    |
| 引用统一          | `namespace/name:tag` 或 `namespace/name@digest` |
| backend 可插拔    | `ContentStore` Protocol，多实现可替换           |
| 通配解析          | `*` 和 `?` 支持，与 OCI 规范保持一致            |
| 后续 PG 迁移      | Protocol 设计兼容 SQL 表，迁移零成本             |

## 公共 API

```python
from gimbal.repository import (
    AssetRef,         # 资产引用（namespace/name:tag 或 @digest）
    AssetRecord,      # 资产元数据
    AssetContent,     # 资产内容（record + raw + parsed）
    ContentStore,     # 底层存储协议
    AssetStore,       # 业务门面（push/pull/list/...）
    LocalFsContentStore,  # 本地 FS 实现
    compute_digest,   # 工具：sha256(data) → "sha256:..."
)
```

## 核心模型

### AssetRef

资产引用，两种合法形式互斥：

| 形式            | 例子                       | 用途               |
| --------------- | -------------------------- | ------------------ |
| `ns/name:tag`   | `customs/declare:v1.0`     | 人类可读，最常用   |
| `ns/name@digest`| `customs/declare@sha256:abc...` | 不可变版本定位 |

```python
ref = AssetRef.parse("customs/declare:v1.0")
# ref.namespace = "customs"
# ref.name      = "declare"
# ref.tag       = "v1.0"
# ref.digest    = None

# digest 形式
ref2 = AssetRef.parse("library/hello@sha256:abc...64chars")
```

**合法性规则**（与 OCI distribution spec 对齐）：
- `namespace` / `name`：``[a-z0-9][a-z0-9._-]{0,127}``
- `tag`：``[A-Za-z0-9_][A-Za-z0-9._-]{0,127}``
- `digest`：`sha256:[a-f0-9]{64}`

非法引用 → 抛 `InvalidAssetRef`。

### AssetRecord

资产元数据，**指向某个具体 digest**：

```python
@dataclass (frozen)
class AssetRecord:
    ref: AssetRef
    digest: str
    size: int
    kind: Literal["suite", "scenario", "data", "blob"]
    media_type: str
    created_at: datetime
    updated_at: datetime
    metadata: dict
```

### AssetContent

资产内容（record + 原始 bytes + 解析后的对象）：

```python
@dataclass
class AssetContent:
    record: AssetRecord
    raw: bytes       # 原始字节
    parsed: Any      # 当 kind ∈ {suite, scenario, data} 时自动 json.loads
```

## ContentStore 协议

底层字节+索引的存储协议。**业务方不直接用**，只用于 backend 实现。

```python
class ContentStore(Protocol):
    # Blob（不可变、按 sha256 寻址）
    def push_blob(self, digest: str, data: bytes | BinaryIO) -> None
    def pull_blob(self, digest: str) -> bytes
    def has_blob(self, digest: str) -> bool

    # Tag 索引（可写、可删）
    def put_manifest(self, ref: AssetRef, digest: str, record_json: str) -> None
    def get_manifest(self, ref: AssetRef) -> tuple[str, str] | None
    def delete_manifest(self, ref: AssetRef) -> bool
    def list_tags(self, namespace: str, name: str) -> list[str]

    # 资产级查询
    def list_assets(self, namespace: str | None = None) -> list[AssetRecord]
    def find_by_digest(self, digest: str) -> list[AssetRecord]
```

### LocalFsContentStore

文件系统实现，目录布局（仿 Docker Registry v2）：

```
{root}/
├── blobs/
│   └── sha256/
│       └── {aa}/
│           └── {aabbcc...full-64-hex}/
│               └── content                # 不可变 blob
├── indexes/
│   └── {namespace}/
│       └── {name}/
│           ├── {tag1}.json                # tag → record
│           └── {tag2}.json
└── manifests/
    └── {namespace}/
        └── {name}/
            └── index.json                 # 该 name 下所有 tag 列表
```

**关键特性**：
- `blobs/sha256/{aa}/` 是 fan-out，避免单目录文件过多
- tag 索引可重写、删除，blob 本身不可变
- 原子写：`tempfile + os.replace`（Windows 兼容：先 close 再 replace）
- O(N) 扫盘 `list_assets`，万级以内可用

### 未来的 PostgresContentStore

接口兼容 Protocol，迁移时只需替换实现：

| LocalFs                  | Postgres                                |
| ------------------------ | --------------------------------------- |
| `blobs/sha256/...`       | `blobs (digest PK, content BYTEA)`       |
| `indexes/ns/name/tag.json` | `tags (ns, name, tag, digest, record_json)` |
| `manifests/.../index.json` | 同一 `tags` 表的 distinct 查询          |
| `rglob` 扫盘             | `SELECT ... FROM tags WHERE ...`        |

## AssetStore 门面

业务方唯一入口。把 ref ↔ record ↔ content 的逻辑集中在这里。

### 方法总览

| 方法 | 签名 | 返回 | 异常 |
|------|------|------|------|
| `push` | `(ref, data, *, kind, media_type, metadata, overwrite=False)` | `AssetRecord` | `AssetAlreadyExists` / `AssetDigestMismatch` |
| `pull` | `(ref, *, parse_json=True)` | `AssetContent` | `AssetNotFound` |
| `inspect` | `(ref)` | `AssetRecord`（不下载内容） | `AssetNotFound` |
| `list_tags` | `(namespace, name)` | `list[AssetRef]` | — |
| `list_assets` | `(namespace=None)` | `list[AssetRecord]` | — |
| `find_by_digest` | `(digest)` | `list[AssetRecord]` | — |
| `tag` | `(src, dst, *, overwrite=False)` | `AssetRecord` | `AssetNotFound` / `AssetAlreadyExists` |
| `remove` | `(ref, *, delete_blob_if_orphan=True)` | `bool` | `AssetNotFound` |
| `backend_name` | `@property` | `str`（如 `"LocalFsContentStore"`） | — |

### backend_name

```python
store = AssetStore(backend=LocalFsContentStore(root=Path("~/.gimbal/registry").expanduser()))
print(store.backend_name)   # 'LocalFsContentStore'
```

> 用于 CLI 日志 / 调试输出，**不要**用 `type(store._backend).__name__` 访问私有字段。

### push

```python
record = store.push(
    AssetRef.parse("customs/declare:v1.0"),
    data=b'{"name": "declare"}',
    kind="suite",
    media_type="application/json",
    metadata={"author": "alice"},
    overwrite=False,  # 默认不允许覆盖已存在的 tag
)
# record.digest  # sha256:abc...
# record.size    # N 字节
```

- 幂等：相同 content 自动去重（digest 相同 → 同一 blob）
- `overwrite=False` 时目标 tag 已存在 → 抛 `AssetAlreadyExists`
- 提供的 `data` 与 `ref.digest` 不一致 → 抛 `AssetDigestMismatch`

### pull

```python
content = store.pull(AssetRef.parse("customs/declare:v1.0"))
# content.digest   # sha256:abc...
# content.size     # N
# content.raw      # b'{"name": "declare"}'
# content.parsed   # {"name": "declare"}  (kind in {suite/scenario/data} 且 parse_json=True 时自动 json.loads)
```

`parse_json` 参数：
- `True`（默认）：当 `kind ∈ {suite, scenario, data}` 时自动 `json.loads` 到 `content.parsed`
- `False`：`content.parsed` 为 `None`，调用方拿到 raw bytes 自行处理

不存在 → 抛 `AssetNotFound`。

### inspect（不下载内容）

```python
record = store.inspect(AssetRef.parse("customs/declare:v1.0"))
# record.size, record.digest, record.metadata, ...
```

### list_tags / list_assets / find_by_digest

```python
# 列出某 name 下所有 tag
tags = store.list_tags("customs", "declare")
# → [AssetRef("customs/declare:v1.0"), AssetRef("customs/declare:latest"), ...]

# 列出某 namespace 下所有 asset
records = store.list_assets(namespace="customs")
# → [AssetRecord(...), AssetRecord(...), ...]

# 列出全库
all_records = store.list_assets()

# 按 digest 反查（不限于同一 ns/name）
hits = store.find_by_digest("sha256:abc...")
# → [AssetRecord(...), ...]
```

### tag（添加新 tag 到已有 digest）

```python
new_record = store.tag(
    src=AssetRef.parse("customs/declare:v1.0"),
    dst=AssetRef.parse("customs/declare:latest"),
    overwrite=False,
)
```

### remove（删除 tag）

```python
store.remove(AssetRef.parse("customs/declare:v1.0"))
# tag 索引被删除；
# 若 delete_blob_if_orphan=True 且 blob 无其它 tag 引用则同步删除（默认）
# 否则 blob 变孤儿，gc 时清理
```

`delete_blob_if_orphan` 参数：
- `True`（默认）：删除 tag 后若 blob 已无任何 tag 引用，**同步**删 blob
- `False`：保留孤儿 blob，等 `gc()` 阶段清理

### gc（清理孤儿 blob）

```python
removed = backend.gc()
# 遍历 blobs/，删除无 record 引用的 blob
```

> `gc()` 是 `ContentStore` 的方法（在 backend 实例上），**不是** `AssetStore` 的方法。
> `AssetStore` 不持有 gc 入口。CLI 走 `gimbal asset gc`（`asset.py:gc`）调用。

## CLI 入口

```
gimbal asset push     NAMESPACE/NAME:TAG -f FILE   # 上传
gimbal asset pull     NAMESPACE/NAME[:TAG]         # 下载
gimbal asset list     [NAMESPACE]                  # 列出
gimbal asset inspect  NAMESPACE/NAME[:TAG]         # 元数据
gimbal asset remove   NAMESPACE/NAME[:TAG]         # 删除 tag
gimbal asset tag      SRC  DST                     # 加 tag
gimbal asset gc                                     # 清理孤儿
```

全局选项：
- `--registry PATH`：本地注册表根目录（默认 `~/.gimbal/registry`）

## 异常层次

```
GimbalError
└── AssetError                          code=ASSET_ERROR
    ├── AssetNotFound                   code=ASSET_NOT_FOUND
    ├── AssetAlreadyExists              code=ASSET_ALREADY_EXISTS
    ├── AssetDigestMismatch             code=ASSET_DIGEST_MISMATCH
    ├── InvalidAssetRef                 code=ASSET_INVALID_REF
    ├── AssetMaterializationError       code=ASSET_MATERIALIZATION_ERROR
    └── AssetCycleError                 code=ASSET_CYCLE
```

完整定义见 `gimbal/exceptions.py`；`gimbal/repository/exceptions.py` 是 re-export 兼容层。

`AssetMaterializationError` / `AssetCycleError` 由 [`AssetMaterializer`](#assetmaterializer-结构化引用物化) 抛出（见下节）。

## AssetMaterializer（结构化引用物化）

> 实现位置：`gimbal/core/asset_materializer.py`
> 集成位置：[`ScenarioPreprocessor` Phase 0](preprocessor.md#0-引用物化phase-0asset-仓库引用还原)

仓库只解决 **byte-level 寻址**（pull 一个 ref → 拿到 bytes / parsed dict）。
但 scenario 中常常出现**结构化引用**（指向 step / api / request / strategy 或任意 dict 节点）。
把这种"引用"还原为**数据类对象**的过程，由 `AssetMaterializer` 完成。

### 设计：识别 Ref，而非替换字符串

引用还原是**结构化图遍历**（graph walk），**不是**字符串模板替换。
物化器从根节点出发递归遍历整个对象图：

- 凡是 `RefBase` 子类实例 → 拉取 → 反序列化 → 替换
- 凡是 dict 形如 `{"kind": "ref", "ref": "..."}` → 视为内联 Ref → 同上
- 凡是 Pydantic 模型 → 遍历所有字段递归处理
- 凡是 dict / list → 遍历所有值递归处理
- 其它标量 → 透传

替换后的子节点可能仍然包含 Ref → 递归处理直到不动点（fixed-point）。

### Ref 类型

`RefBase` 在 `gimbal/schema/ref.py` 中定义：

| 类                | 出现位置                                            | 替换后              | 适配器（RunUnion 等）|
| ----------------- | --------------------------------------------------- | ------------------- | -------------------- |
| `StepRef`         | `Scenario.steps: list[StepUnion]`                  | `Step`              | `StepUnion`          |
| `ApiRef`          | `Step.api: ApiUnion`                                | `Api`               | `ApiUnion`           |
| `RequestRef`      | `Step.request: RequestUnion`                        | `Request`           | `RequestUnion`       |
| `StrategyRef`     | `Step.strategy: list[StrategyUnion]`                | `Extract` / `Assign` / `Assertion` | `StrategyUnion` |
| `ScenarioRef`     | 顶层（资产可指向整个 scenario）                     | `Scenario`          | `RunUnion`（discriminator `kind="scenario_ref"`）|
| `SuiteRef`        | 顶层（资产可指向整个 suite）                        | `Suite`             | `RunUnion`（discriminator `kind="suite_ref"`）|
| `Ref`（通用内联） | `Request.body: dict` 等 free-form dict / list 中    | 任意对象（看仓库内容）| — |

通用 `Ref` 用 dict 形式表达：`{"kind": "ref", "ref": "smoke/cart-line-template:v1"}`。
识别依据：`obj.get("kind") == "ref" and isinstance(obj.get("ref"), str)`。

> 为何需要通用 `Ref`？
> `Request.body: dict[str, Any]` 在 Pydantic v2 验证时**不递归**到值，
> 所以一个 `{"kind": "ref", "ref": "..."}` 会保持为 raw dict，
> 不会被自动转为 Pydantic `Ref` 实例。物化器必须**结构化识别**才能捕获。

### 用法

```python
from gimbal.core.asset_materializer import AssetMaterializer

materializer = AssetMaterializer(asset_store, max_depth=8)
materializer.materialize(scenario_schema)   # 原地改 schema，Ref 节点被替换
```

- `asset_store`：`AssetStore` 实例
- `max_depth`：递归深度兜底（默认 8），超过即 `AssetCycleError`
- 返回值：被访问的 ref 个数（统计用）

### 算法：fixed-point + 环检测

```
_walk(obj):
    if obj is RefBase instance:
        return _materialize_ref(obj)
    if obj is dict and _looks_like_ref_dict(obj):
        return _materialize_ref(_coerce_to_ref(obj))
    if obj is Pydantic BaseModel:
        for each field:
            replace field.value = _walk(field.value, ...)
        return obj
    if obj is dict / list / tuple:
        return container with each element _walk'd
    return obj  # scalar

_materialize_ref(ref):
    ref_key = (type(ref).__name__, ref.ref)
    if ref_key in self._seen:
        raise AssetCycleError(...)            # 环
    if depth >= max_depth:
        raise AssetCycleError(...)            # 深度兜底
    push ref_key → _seen
    try:
        content = self._store.pull(ref.ref)
        node    = self._deserialize(ref, content)   # typed Ref → TypeAdapter；通用 Ref → raw
        return _walk(node, depth+1)                # 递归到不动点
    finally:
        pop ref_key ← _seen                        # 兄弟分支隔离
```

**环检测**：push-pop 模式（`self._seen = previous_seen`）保证：

- 同一 ref 在**祖先路径**上重复出现 → 报错（真环）
- 同一 ref 在**兄弟分支**上重复出现 → 不报错（共享子图）

**反序列化**：使用 `Pydantic TypeAdapter` 加载对应的 `Union` 类型（`StepUnion` / `ApiUnion` / `RequestUnion` / `StrategyUnion`），
让 Pydantic 自己的 **discriminator** 决定最终实例化哪个子类。通用 `Ref` 不走 TypeAdapter，直接返回 `content.parsed`（或 `raw.decode()`）。

### 典型错误

| 错误                              | 触发                                                |
| --------------------------------- | --------------------------------------------------- |
| `AssetCycleError`                 | ref 出现真环，或递归深度超 `max_depth`              |
| `AssetMaterializationError`       | 仓库中找不到 ref，或内容无法被对应 TypeAdapter 接受 |

### 与 CLI / Resolver 的分层

| 层级              | 关注点                                       | 模块                              |
| ----------------- | -------------------------------------------- | --------------------------------- |
| **外层**（CLI）   | "拿一个完整 scenario 文件"                   | `core/asset_resolver.py`（`AssetResolver`）|
| **内层**（执行前）| "把 scenario 中所有 Ref 还原为数据类对象"    | `core/asset_materializer.py`（`AssetMaterializer`）|

外层只管"拉下来"，不管内容是什么；内层只管"还原" Ref，不管从哪里来。
Scenario 文件本身可以是 ref（外层处理），文件内容里也可以再含 ref（内层处理），
两层互不耦合。

### AssetResolver（外层：CLI/Suite 拉取完整资产）

> 实现位置：`gimbal/core/asset_resolver.py`

```python
from gimbal.core.asset_resolver import AssetResolver, AssetKind

resolver = AssetResolver(
    kind=AssetKind.SCENARIO,    # 限制只匹配该 kind
    asset_store=asset_store,
    source="auto",              # auto / local / remote
    registry=None,              # 自定义 registry 根；None = 用默认 ~/.gimbal/registry
)
matched = resolver.resolve([
    "payment/sc-001:v1",     # 单 ref
    "payment/sc-*",          # 命名空间 + 通配
    "library/*:latest",      # 多命名空间
])
# → list[ResolvedAsset(ref, content: AssetContent)]
```

`AssetKind` 枚举：

| 值 | 含义 |
|----|------|
| `SUITE` | `kind=suite` 的资产 |
| `SCENARIO` | `kind=scenario` 的资产 |
| `STEP` / `API` / `REQUEST` / `STRATEGY` | 结构化小粒度资产（物化后被内层用） |
| `DATA` | 通用数据资产 |

`resolve()` 行为：
- 通配展开（`*` 在 namespace / name / tag 任何位置）
- 不存在的 ref → 跳过（warning 日志），不抛异常
- 去重：相同 digest 多次匹配只保留一份
- 返回 `list[ResolvedAsset]`，调用方遍历消费

> `AssetResolver` 与 `AssetMaterializer` 的边界：前者**只决定"拉哪些资产"**，后者**只决定"还原图里的 Ref 节点"**。两者都用 `AssetStore` 但职责正交。

## 典型用法

### 推送一个 suite

```python
import json
from pathlib import Path
from gimbal.repository import AssetRef, AssetStore, LocalFsContentStore

backend = LocalFsContentStore(root=Path("~/.gimbal/registry").expanduser())
store = AssetStore(backend=backend)

suite_data = json.dumps({"name": "declare", "steps": [...]}, ensure_ascii=False).encode()
ref = AssetRef.parse("customs/declare:v1.0")
store.push(ref, suite_data, kind="suite", media_type="application/json")
```

### 拉取 + 消费

```python
content = store.pull(AssetRef.parse("customs/declare:v1.0"))
suite_dict = content.parsed        # 已自动 json.loads
# 或者：
raw_bytes = content.raw
```

### 通配拉取

```python
from gimbal.core.asset_resolver import AssetResolver, AssetKind

resolver = AssetResolver(kind=AssetKind.SUITE, asset_store=store)
matches = resolver.resolve([
    "customs/*:v1.0",       # 命名空间 + tag 通配
    "payment/*:latest",     # 多命名空间
    "library/foo:1.2.3",    # 单 ref
])
for m in matches:
    print(m.ref, m.content.digest)
```

## 设计原则

1. **内容不可变**：blob 一旦写入永不修改，digest 即身份
2. **tag 可变**：tag 索引可重写，可删除
3. **去重自动**：相同 content → 同一 digest → 同一 blob 文件
4. **backend 解耦**：`ContentStore` Protocol；业务方只见 `AssetStore`
5. **OCI 兼容**：命名/tag 规则与 OCI distribution spec 对齐，可未来对接 Harbor/Distribution
6. **CLI 友好**：`gimbal asset` 子命令集与 Docker 完全对齐
7. **未来 PG**：LocalFs 写完即视为协议参考实现，PG backend 是另一实现，不动业务代码

## 与 Archive 的区别

| 维度     | Archive（`gimbal.context.archive`）        | Repository（`gimbal.repository`）        |
| -------- | ----------------------------------------- | ---------------------------------------- |
| 目的     | 保存**执行历史**（framework/suite/step）  | 保存**可复用资产**（suite/scenario/data）|
| 寻址     | `suite_id` / `scenario_id` / `step_id`   | `namespace/name:tag` 或 `@digest`        |
| 内容     | 运行时 Context 对象（含 state / scratch） | 静态资产字节流（Suite JSON / 数据文件）  |
| 持久性   | 进程内（InMemory）/ DB                    | 本地 FS / 远端 registry                  |
| 生命周期 | 一次 run 即丢弃                           | 长期保留，多 run 共享                    |

两者完全独立：ContextManager 不依赖 Repository，Repository 不依赖 ContextManager。
