"""Asset repository module — Docker-like content-addressable store.

Public API:
    AssetRef        —— 资产引用（namespace/name:tag 或 @digest）
    AssetRecord     —— 资产元数据
    AssetContent    —— 资产内容（record + raw + parsed）
    ContentStore    —— 底层存储协议（Protocol）
    AssetStore      —— 业务门面（push/pull/inspect/list/tag/remove）
    LocalFsContentStore —— 本地文件系统实现

未来会加:
    PostgresContentStore —— PG 远程实现

典型用法::

    from pathlib import Path
    from gimbal.repository import AssetStore, AssetRef, LocalFsContentStore

    backend = LocalFsContentStore(root=Path("~/.gimbal/registry"))
    store = AssetStore(backend=backend)

    ref = AssetRef.parse("customs/declare:v1.0")
    store.push(ref, b'{"name": "declare"}', kind="suite")
    content = store.pull(ref)
    print(content.parsed, content.digest)
"""
from .models import AssetContent, AssetRecord, AssetRef
from .store import AssetStore, ContentStore, compute_digest
from .backends.filesystem import LocalFsContentStore

__all__ = [
    "AssetRef",
    "AssetRecord",
    "AssetContent",
    "ContentStore",
    "AssetStore",
    "LocalFsContentStore",
    "compute_digest",
]
