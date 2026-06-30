# PR-4.1 资产仓库 (Asset Store) GC 与多 backend 补完

> Phase 4 / PR 1 of 9
> 优先级: 🔴 P0 (阻塞 PR-4.5)
> 估计工作量: 1.5 PD
> 阻塞: PR-4.5

## 一句话目标

把 `ContentStore` 协议补 `delete_blob`, 让 `AssetStore.remove()` 真能 gc; 并把 `mysql / python_module` 两个 backend 从"1 行 stub" 提升到至少文件系统 backend 的 80% 能力。

---

## 背景与动机

### 现状 finding (HIGHEST IMPACT — 数据债)

`src/gimbal/repository/store.py:228-233` 自承:

```python
def remove(self, ref: AssetRef) -> bool:
    ...
    # NOTE: ContentStore 没有 delete_blob, 所以 blob 永远不会被 GC.
    # 后续 PR 会补 delete_blob 让 blob GC 完整.
```

后果链:

1. 长期 push/remove 后, **`blobs/` 目录只增不减**, 1 周测试可能在 GB 级
2. README 承诺 "资产仓库提供 gc": 与实现脱节 (P0 文档债)
3. `MySQL` 与 `python_module` 两个 backend 仅 1 行 stub, **名义多后端**

### 同源问题面

- `AssetStore.remove(asset)` 只删 metadata, **不删 blob**
- `Asset.ref.digest` 与 `Asset.blob` 在 metadata 与文件系统是 **双源**, 删前者时后者无 anchor
- `Tag` 与 `Blob` 是 1:N, blob 仍可被其他 tag 引用 (`remove(tag)` 不应触发删 blob); 但**当前没有引用计数**
- `list()` 接口未提供 `namespace_prefix / name_glob` 等过滤
- `MySQL backend` 1 行 docstring, 实际 metadata 与 blob 都不在 mysql 里 —— 是历史空壳
- `python_module backend` 同上 (与 filesystem 不可区分)

## 范围与非目标

**In scope**:

- `ContentStore` 协议加 `delete_blob(digest)` 方法
- 三个 backend (`filesystem / mysql / python_module`) 各自实现 `delete_blob`
- `AssetStore` 加"无引用则真删 blob"语义(引入 `BlobRefCount`, dict-based 引用计数, 不引外部依赖)
- `AssetStore.list()` 加 `namespace_prefix / tag` 过滤
- 给 `store.py` 加单元测试(原 ~10 行覆盖, 扩到 30+)
- README 更新: gc 行为 / backend 选型表

**Out of scope**:

- 删 blob 的 GC 后台任务 (定时回收)
- 分布式 backend (S3 / MinIO)
- 多进程并发 push 的原子性 (locks)

---

## 设计

### 1. ContentStore 协议扩展

```python
class ContentStore(Protocol):
    def put(self, digest: str, content: bytes) -> None: ...
    def get(self, digest: str) -> bytes | None: ...
    def exists(self, digest: str) -> bool: ...
    def delete(self, digest: str) -> bool: ...        # ← 新增
    def iter_digests(self) -> Iterator[str]: ...     # ← 新增 (供 GC)
```

### 2. AssetStore.remove 语义重定义

新流程:

```
remove(ref):
  1. asset = self._metadata.find(ref)            # 失败返回 False
  2. for blob_digest in asset.blobs:
       refcount[blob_digest] -= 1
       if refcount[blob_digest] == 0:
         content_store.delete(blob_digest)
         logger.info("blob gc: {digest}")
  3. self._metadata.delete(asset.ref)
  4. return True
```

`put` 时同步:

```
put(ref, blobs):
  1. digest = sha256(content)
  2. if not content_store.exists(digest): put
     refcount[digest] += 1
  3. metadata put(ref → {digest, ...})
```

### 3. mysql backend 最小实现

```python
class MySQLContentStore:
    def __init__(self, dsn: str, table_prefix: str = "gimbal"):
        import pymysql  # optional dep
        self.conn = pymysql.connect(dsn=dsn, ...)
        self.prefix = table_prefix

    def put(self, digest, content):
        self.conn.execute(
            f"INSERT INTO {self.prefix}_blobs(digest, content) VALUES(%s, %s)",
            (digest, content),
        )
    def get(self, digest): ...
    def delete(self, digest):
        cursor = self.conn.execute(
            f"DELETE FROM {self.prefix}_blobs WHERE digest=%s", (digest,)
        )
        return cursor.rowcount > 0
```

metadata 同样走 mysql (`<prefix>_assets` 表).

> 若 reviewer 决定不引 `pymysql` 依赖, 则改用纯 SQLAlchemy 或留 docstring + TODOs.

### 4. python_module backend 补完

- 与 filesystem backend **一致语义**; 但存储路径改用 `<base>/python_modules/<digest>` 二进制 blob
- metadata 文件 `<base>/python_modules/index.json`, 内容是 `{ref.namespace/name:tag: {digest, content_type, ...}}`
- 与 filesystem 后端的差异: 用 `import importlib` 加载, 用 `inspect.getsource` 反查; 场景测试场景调用

> 注: 该 backend 主要面向"用 Python 模块沉淀资产"的实验场景, 与 asset_name 冲突较少.

### 5. list() 过滤

```python
def list(
    self,
    *,
    namespace_prefix: str | None = None,
    tag: str | None = None,
) -> Iterator[AssetRef]:
    for asset in metadata.scan():
        if namespace_prefix and not asset.ref.namespace.startswith(namespace_prefix):
            continue
        if tag and tag not in asset.tags:
            continue
        yield asset.ref
```

### 6. 测试矩阵

| 用例 | 覆盖 |
|---|---|
| push → list → assert exists | happy path |
| remove 后 blob 删除 | 1 个 ref 引用 → 删后 gc 命中 |
| remove 后 blob 保留 | 多 tag 引用同一 digest → 删一个 ref, blob 不动 |
| push 重复 digest 不重复存 | 同一内容 push 两次, content_store.put 只触发一次 |
| mysql crud (skip-if-no-mysql conftest) | 集成测试, no-op in CI |
| list 过滤 (namespace + tag) | 边界 |
| corrupt digest 拒 | 防伪 |

---

## 验收 (DoD)

### 必须

- [ ] `ContentStore` 协议加 `delete` + `iter_digests`
- [ ] 三个 backend 各实现上述两方法; `mysql` backend 至少 `connect / put / get / delete` 可用
- [ ] `AssetStore.remove()` 真触发 backend `delete`, 测试可见文件系统 size 减少
- [ ] `AssetStore` 引入 `BlobRefCount` (结构体或纯 dict), 行为可单测验证
- [ ] `AssetStore.list()` 实现 `namespace_prefix / tag` 过滤
- [ ] `tests/unit/test_local_fs_store.py` 扩到 30+ 用例
- [ ] `docs/repository.md`(或 README § Backend 选型表) 更新
- [ ] DECISIONS D29 登记

### 应有

- [ ] `tests/integration/test_mysql_backend.py`(skippable in CI without `pymysql`)
- [ ] 后台 GC 调度 TODO 列入 `phase5` roadmap

### Nice to have

- [ ] `iter_digests` 实现 background compaction(本 PR 不做)

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 删 blob 后, 已有相同 digest 被另一 tag 引用导致 0 引用仍误删 | refcount 强制只减不删, 双 tag remove 都 ≥0 才删 | 删除 `BlobRefCount`, 退回到"按 metadata ref 删除, 不动 blob" |
| mysql backend 引新依赖 `pymysql` 触发依赖审计 | conftest skip if missing | 改成纯 stdlib `mysql.connector` 或退 stub |
| 本 PR 改 ContentStore 协议, 第三方 plugin 自实现未跟进 | plugin loader 加 deprecation warning | protocol 加 `delete = None` 默认 |
| 大仓库 push → gc 触发 I/O | 异步 GC 待 phase5 | 同步 gc, 但加 `--no-gc` 配置 |

---

## 任务清单

- [ ] T1 扩展 `ContentStore` Protocol (`delete` + `iter_digests`)
- [ ] T2 `FilesystemContentStore` 实现 `delete` + `iter_digests`
- [ ] T3 `MySQLContentStore` 最小可用实现 + 元数据表
- [ ] T4 `PythonModuleContentStore` 与 Filesystem 对齐
- [ ] T5 `AssetStore` 加 `BlobRefCount` + 重写 `remove`
- [ ] T6 `AssetStore.list()` 过滤
- [ ] T7 测试 (`tests/unit/test_local_fs_store.py` 扩 + 新增 `test_mysql_backend.py`)
- [ ] T8 README / docs 更新
- [ ] T9 DECISIONS D29 / CHANGELOG

---

## 依赖与并行

- **依赖**: 无
- **被依赖**: PR-4.5 (repo 测试), PR-4.7 (docs)
- **可并行**: PR-4.2 (CLI 取消)
