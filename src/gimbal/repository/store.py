"""repository/store.py  —  ContentStore 协议 + AssetStore 门面。

分层：

    ContentStore (Protocol)
        ├── LocalFsContentStore   （本地文件系统实现）
        └── PostgresContentStore  （未来：PostgreSQL 实现）

    AssetStore (facade)
        └── 组合一个 ContentStore，提供 push/pull/list/inspect/remove/tag 等
            业务级 API（包含 digest 校验、tag 解析、metadata 管理等）。

设计原则：
    - ContentStore 关心"字节+索引"，接口尽量贴近 Docker Registry v2：
      push_bytes / pull_bytes / exists / list_tags / get_manifest / put_manifest
    - AssetStore 关心"用户语义"：ref（namespace/name:tag）↔ record 转换、
      解析为 AssetContent 供 resolver 消费。
    - 业务方只依赖 AssetStore，不知道底层是 LocalFs 还是 Postgres。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, BinaryIO, Protocol, runtime_checkable

from .models import (
    AssetContent,
    AssetRecord,
    AssetRef,
)
from gimbal.exceptions import (
    AssetAlreadyExists,
    AssetDigestMismatch,
    AssetNotFound,
)


# ════════════════════════════════════════════════════════════════════════════
# ContentStore Protocol
# ════════════════════════════════════════════════════════════════════════════


@runtime_checkable
class ContentStore(Protocol):
    """底层字节+索引存储协议。

    实现方需保证：
      - 相同 content → 相同 digest（sha256）
      - 不可变性：digest 一旦写入，其内容永不变化
      - 幂等 push：相同 content 多次 push 不会产生副作用（实现内部去重）
    """

    # ── Blob 操作 ──
    def push_blob(self, digest: str, data: bytes | BinaryIO) -> None:
        """写入一个 blob。digest 必须 == sha256(data)。"""
        ...

    def pull_blob(self, digest: str) -> bytes:
        """按 digest 读取 blob。"""
        ...

    def has_blob(self, digest: str) -> bool:
        ...

    # ── Tag 索引操作 ──
    def put_manifest(self, ref: AssetRef, digest: str, record_json: str) -> None:
        """把 digest + record 绑定到 ref（通常以 tag 为粒度）。"""
        ...

    def get_manifest(self, ref: AssetRef) -> tuple[str, str] | None:
        """返回 (digest, record_json) 或 None。"""
        ...

    def delete_manifest(self, ref: AssetRef) -> bool:
        """删除一个 tag 索引。返回是否存在并被删除。"""
        ...

    def list_tags(self, namespace: str, name: str) -> list[str]:
        """列出某个 name 下的所有 tag。"""
        ...

    # ── 资产级查询（跨多个 tag 的聚合） ──
    def list_assets(self, namespace: str | None = None) -> list[AssetRecord]:
        """列出某个 namespace 下（或全库）的所有 asset record。"""
        ...

    def find_by_digest(self, digest: str) -> list[AssetRecord]:
        """查找指向某个 digest 的所有 record（多个 tag 可能指向同一 digest）。"""
        ...


# ════════════════════════════════════════════════════════════════════════════
# AssetStore facade
# ════════════════════════════════════════════════════════════════════════════


class AssetStore:
    """资产仓库门面。

    业务方唯一入口。把 ref ↔ record ↔ content 的逻辑放在这里，
    ContentStore 只需要关心字节与索引。
    """

    def __init__(self, backend: ContentStore) -> None:
        """初始化 AssetStore，注入底层 ContentStore 并创建命名 logger。"""
        self._backend = backend
        from gimbal.log import get_logger
        self._logger = get_logger(self.__class__.__name__)
        self._logger.debug("AssetStore initialized: backend={}", type(backend).__name__)

    @property
    def backend_name(self) -> str:
        """后端实现类名（如 'LocalFsContentStore'），用于日志/CLI 输出。"""
        return type(self._backend).__name__

    # ── 推 / 拉 ──
    def push(
        self,
        ref: AssetRef,
        data: bytes,
        *,
        kind: str = "blob",
        media_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> AssetRecord:
        """推送一个资产。

        流程：
            1. 计算 sha256(data)
            2. 与 ref.digest 比对（如果提供了）
            3. 写入 blob（去重）
            4. 构造 AssetRecord，写入 tag 索引
        """
        if ref.digest is not None:
            actual = _sha256(data)
            if actual != ref.digest:
                raise AssetDigestMismatch(
                    f"Content digest mismatch: declared={ref.digest} actual={actual}",
                    declared=ref.digest,
                    actual=actual,
                )
        digest = ref.digest or _sha256(data)

        # 检查 tag 是否已存在（除非 overwrite=True）
        if not overwrite and self._backend.get_manifest(ref) is not None:
            raise AssetAlreadyExists(
                f"Ref already exists: {ref}",
                ref=str(ref),
            )

        # 写 blob
        self._backend.push_blob(digest, data)
        size = len(data)

        # 构造 record + 写 manifest
        now = datetime.now(timezone.utc)
        record = AssetRecord(
            ref=ref,
            digest=digest,
            size=size,
            kind=kind,                              # type: ignore[arg-type]
            media_type=media_type,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        record_json = record.model_dump_json()
        self._backend.put_manifest(ref, digest, record_json)
        self._logger.info(
            "Pushed asset: ref={} digest={} size={}B kind={}",
            ref, digest, size, kind,
        )
        return record

    def pull(self, ref: AssetRef, *, parse_json: bool = True) -> AssetContent:
        """拉取一个资产。

        参数：
            ref        —— 资产引用（tag 或 digest 形式）
            parse_json —— 当 kind 是 suite/scenario/data 时，自动 json.loads
        """
        manifest = self._backend.get_manifest(ref)
        if manifest is None:
            raise AssetNotFound(f"Asset not found: {ref}", ref=str(ref))
        digest, record_json = manifest
        record = AssetRecord.model_validate_json(record_json)
        raw = self._backend.pull_blob(digest)

        parsed: Any = None
        if parse_json and record.kind in ("suite", "scenario", "data"):
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None  # 容错：raw bytes 仍是有效结果
        return AssetContent(record=record, raw=raw, parsed=parsed)

    def inspect(self, ref: AssetRef) -> AssetRecord:
        """查看资产元数据（不下载内容）。"""
        manifest = self._backend.get_manifest(ref)
        if manifest is None:
            raise AssetNotFound(f"Asset not found: {ref}", ref=str(ref))
        _, record_json = manifest
        return AssetRecord.model_validate_json(record_json)

    def remove(self, ref: AssetRef, *, delete_blob_if_orphan: bool = True) -> bool:
        """删除一个 tag 索引（不删除 blob 除非无其它 tag 引用）。

        参数：
            delete_blob_if_orphan —— 如果该 digest 不再被任何 tag 引用，连带删除 blob。
                                     默认 True，避免孤儿 blob 占空间。
        """
        manifest = self._backend.get_manifest(ref)
        if manifest is None:
            raise AssetNotFound(f"Asset not found: {ref}", ref=str(ref))
        digest, _ = manifest

        existed = self._backend.delete_manifest(ref)
        if not existed:
            # race condition: 已被并发删除
            return False

        if delete_blob_if_orphan:
            # 查找是否还有其它 record 指向同一 digest
            remaining = self._backend.find_by_digest(digest)
            if not remaining:
                # ContentStore 没有显式 delete_blob（blob 不可变），需要扩展协议
                # 当前实现保留 blob（孤儿），后续 PG backend 可加 delete_blob
                self._logger.debug(
                    "Blob now orphan: digest={} (no delete_blob in protocol; kept on disk)",
                    digest,
                )

        return existed

    def list_tags(self, namespace: str, name: str) -> list[AssetRef]:
        """列出 (namespace, name) 下所有 tag 对应的 AssetRef（按字母序）。"""
        tags = self._backend.list_tags(namespace, name)
        return [AssetRef(namespace=namespace, name=name, tag=t) for t in sorted(tags)]

    def list_assets(self, namespace: str | None = None) -> list[AssetRecord]:
        """列出指定 namespace（或全库，None）下的所有 AssetRecord。"""
        return self._backend.list_assets(namespace=namespace)

    def exists(self, ref: AssetRef) -> bool:
        """判断 ref 对应的 tag 索引是否存在（不下载 blob）。"""
        return self._backend.get_manifest(ref) is not None

    def tag(self, src: AssetRef, dst: AssetRef, *, overwrite: bool = False) -> AssetRecord:
        """给已有的 digest 添加一个新 tag。"""
        manifest = self._backend.get_manifest(src)
        if manifest is None:
            raise AssetNotFound(f"Source ref not found: {src}", ref=str(src))
        digest, record_json = manifest
        if not overwrite and self._backend.get_manifest(dst) is not None:
            raise AssetAlreadyExists(f"Target ref already exists: {dst}", ref=str(dst))

        # 复用原 record 但更新 ref + updated_at
        record = AssetRecord.model_validate_json(record_json)
        new_record = record.model_copy(update={
            "ref": dst,
            "updated_at": datetime.now(timezone.utc),
        })
        self._backend.put_manifest(dst, digest, new_record.model_dump_json())
        self._logger.info("Tagged: src={} dst={} digest={}", src, dst, digest)
        return new_record


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _sha256(data: bytes) -> str:
    """计算 bytes 的 sha256 摘要并加上 'sha256:' 前缀。"""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def compute_digest(data: bytes) -> str:
    """对外暴露的 sha256 摘要计算工具，CLI / 外部推送场景使用。"""
    return _sha256(data)
