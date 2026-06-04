# Repository 模块

资产仓库（Asset Registry），仿 Docker Registry v2 的内容寻址存储。**详见** [docs/modules/repository.md](../../../docs/modules/repository.md)。

> 本 README 只列**当前实际存在的**符号与结构。前一版 README 中描述的 `AssetRepository` ABC / `AssetRouter` / `FileSystemBackend` / `MySQLBackend` / `PythonModuleBackend` 是早期 API 的残留描述，**与当前实现不符**，已被 `AssetStore` 门面 + `ContentStore` Protocol 取代。

## 目录结构（与代码一致）

```
gimbal/repository/
├── __init__.py                # 公共 API 导出
├── models.py                  # AssetRef / AssetRecord / AssetContent
├── store.py                   # AssetStore 门面（push/pull/inspect/list_tags/...）
├── exceptions.py              # 异常 re-export 兼容层
├── backends/
│   ├── __init__.py
│   ├── base.py                # ContentStore Protocol（骨架）
│   ├── filesystem.py          # LocalFsContentStore（本地 FS 实现）
│   ├── mysql.py               # 占位（39 字节，待实现）
│   └── python_module.py       # 占位（46 字节，待实现）
```

## 公共 API（`__init__.py` 导出）

| 符号 | 类别 | 说明 |
|------|------|------|
| `AssetRef` | frozen dataclass | 资产引用（`namespace/name:tag` 或 `@digest`）|
| `AssetContent` | dataclass | 资产内容（`raw` + `parsed` + `record`）|
| `AssetRecord` | frozen dataclass | 资产元数据 |
| `AssetStore` | class | 业务门面 |
| `LocalFsContentStore` | class | 本地 FS 后端 |
| `compute_digest` | function | sha256 工具 |

## AssetStore 方法（`store.py`）

| 方法 | 签名 | 异常 |
|------|------|------|
| `push` | `(ref, data, *, kind, media_type, metadata, overwrite=False)` | `AssetAlreadyExists` / `AssetDigestMismatch` |
| `pull` | `(ref, *, parse_json=True)` | `AssetNotFound` |
| `inspect` | `(ref)` | `AssetNotFound` |
| `list_tags` | `(namespace, name)` | — |
| `list_assets` | `(namespace=None)` | — |
| `find_by_digest` | `(digest)` | — |
| `tag` | `(src, dst, *, overwrite=False)` | `AssetNotFound` / `AssetAlreadyExists` |
| `remove` | `(ref, *, delete_blob_if_orphan=True)` | `AssetNotFound` |
| `backend_name` | `@property` | — |

详细参数与示例见 [docs/modules/repository.md](../../../docs/modules/repository.md)。

## 待实现

- [ ] `backends/base.py` 写完整的 `ContentStore` Protocol（目前 43 字节骨架）
- [ ] `backends/mysql.py` 实现 PostgreSQL / MySQL 后端（多机/生产用）
- [ ] `backends/python_module.py` 实现 Python 模块后端（动态资产）

## 集成点

- CLI `gimbal asset <subcmd>`：[cli/commands/asset.py](../cli/commands/asset.py)
- 外层资产解析：[core/asset_resolver.py](../core/asset_resolver.py)
- 内层引用物化：[core/asset_materializer.py](../core/asset_materializer.py)
