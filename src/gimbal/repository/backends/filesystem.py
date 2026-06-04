"""repository/backends/filesystem.py  —  本地文件系统 asset 仓库。

设计：仿照 Docker Registry v2 的内容寻址存储（CAS）模型：

    布局::

        {root}/
        ├── blobs/sha256/{aa}/{aabbcc...}/content    # 实际内容（不可变）
        ├── indexes/{namespace}/{name}/{tag}.json    # tag → digest + record 索引
        └── manifests/{namespace}/{name}/index.json  # name 下所有 tag 列表（list 用）

每个 blob 路径由 sha256 决定，相同内容只存一份（自动去重）。
tag 索引单独存，可重写、可删除，但内容本身不可变（immutability）。

后续会加 `PostgresContentStore` 作为远程 backend，协议见
`gimbal.repository.store.ContentStore`。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from gimbal.exceptions import AssetNotFound
from gimbal.log import get_logger

from ..models import AssetRecord, AssetRef

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# LocalFsContentStore
# ════════════════════════════════════════════════════════════════════════════


class LocalFsContentStore:
    """ContentStore 的本地文件系统实现。

    用法：
        store = LocalFsContentStore(root=Path("~/.gimbal/registry").expanduser())
        # 后续可包装进 AssetStore：
        asset_store = AssetStore(backend=store)

    目录布局参见本模块 docstring。

    线程安全：单进程内单实例是线程安全的（用 os.replace 实现原子写），
    但**不**支持跨进程并发写同一 ref（filesystem lock 未实现）。
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        logger.debug("[LocalFsContentStore] Initialized: root={}", self.root)

    # ── 内部路径计算 ──

    def _blob_path(self, digest: str) -> Path:
        """``{root}/blobs/sha256/{aa}/{full}/content``  —— fan-out 避免单目录文件过多。"""
        if not digest.startswith("sha256:") or len(digest) != 7 + 64:
            raise ValueError(f"Invalid digest format: {digest!r}")
        hex_ = digest[len("sha256:"):]
        return self.root / "blobs" / "sha256" / hex_[:2] / hex_ / "content"

    def _manifest_path(self, ref: AssetRef) -> Path:
        """``{root}/indexes/{namespace}/{name}/{tag}.json``"""
        return (
            self.root
            / "indexes"
            / ref.namespace
            / ref.name
            / f"{ref.tag}.json"
        )

    def _tag_index_path(self, namespace: str, name: str) -> Path:
        """``{root}/manifests/{namespace}/{name}/index.json`` —— 该 name 下所有 tag 的清单。"""
        return self.root / "manifests" / namespace / name / "index.json"

    # ── Blob 操作 ──

    def push_blob(self, digest: str, data: bytes | BinaryIO) -> None:
        path = self._blob_path(digest)
        if path.exists():
            # 幂等：相同 digest 视为同一内容，不重新写
            logger.debug("[LocalFsContentStore] Blob already exists: digest={}", digest)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写：tmp + close + os.replace（Windows 上 file handle 仍打开时无法 rename）
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".tmp_", delete=False
            ) as tmp:
                if isinstance(data, (bytes, bytearray)):
                    tmp.write(data)
                else:
                    shutil.copyfileobj(data, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            # 离开 with 块后 file handle 已关闭，再 rename（Windows 要求）
            os.replace(tmp_path, path)
            tmp_path = None
        except Exception:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
        logger.info("[LocalFsContentStore] Blob written: digest={} path={}", digest, path)

    def pull_blob(self, digest: str) -> bytes:
        path = self._blob_path(digest)
        if not path.exists():
            raise AssetNotFound(f"Blob not found: {digest}", digest=digest)
        return path.read_bytes()

    def has_blob(self, digest: str) -> bool:
        return self._blob_path(digest).exists()

    # ── Tag 索引操作 ──

    def put_manifest(self, ref: AssetRef, digest: str, record_json: str) -> None:
        manifest_path = self._manifest_path(ref)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写 manifest（先 close 再 replace，Windows 要求）
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=manifest_path.parent, prefix=".tmp_", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                tmp.write(record_json)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            os.replace(tmp_path, manifest_path)
            tmp_path = None
        except Exception:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

        # 同步更新 tag 清单（append-only，按需去重）
        tag_index = self._tag_index_path(ref.namespace, ref.name)
        tag_index.parent.mkdir(parents=True, exist_ok=True)
        if tag_index.exists():
            tags = json.loads(tag_index.read_text(encoding="utf-8"))
        else:
            tags = []
        if ref.tag not in tags:
            tags.append(ref.tag)
            tags.sort()
        tmp_path2: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=tag_index.parent, prefix=".tmp_", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                json.dump(tags, tmp, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path2 = tmp.name
            os.replace(tmp_path2, tag_index)
            tmp_path2 = None
        except Exception:
            if tmp_path2 is not None:
                try:
                    os.unlink(tmp_path2)
                except OSError:
                    pass
            raise

        logger.info(
            "[LocalFsContentStore] Manifest written: ref={} digest={}",
            ref, digest,
        )

    def get_manifest(self, ref: AssetRef) -> tuple[str, str] | None:
        manifest_path = self._manifest_path(ref)
        if not manifest_path.exists():
            return None
        text = manifest_path.read_text(encoding="utf-8")
        data = json.loads(text)
        # manifest 文件存储的是 record 完整 JSON（含 digest 字段）
        return data["digest"], text

    def delete_manifest(self, ref: AssetRef) -> bool:
        manifest_path = self._manifest_path(ref)
        if not manifest_path.exists():
            return False

        manifest_path.unlink()
        logger.info("[LocalFsContentStore] Manifest deleted: ref={}", ref)

        # 从 tag 清单中移除
        tag_index = self._tag_index_path(ref.namespace, ref.name)
        if tag_index.exists():
            try:
                tags = json.loads(tag_index.read_text(encoding="utf-8"))
                if ref.tag in tags:
                    tags.remove(ref.tag)
                    if tags:
                        tag_index.write_text(
                            json.dumps(tags, ensure_ascii=False),
                            encoding="utf-8",
                        )
                    else:
                        # 没有任何 tag 了，删除清单文件
                        tag_index.unlink()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "[LocalFsContentStore] Failed to clean tag_index: path={} err={}",
                    tag_index, e,
                )

        return True

    def list_tags(self, namespace: str, name: str) -> list[str]:
        tag_index = self._tag_index_path(namespace, name)
        if not tag_index.exists():
            return []
        try:
            return json.loads(tag_index.read_text(encoding="utf-8"))
        except Exception:
            return []

    # ── 资产级查询 ──

    def list_assets(self, namespace: str | None = None) -> list[AssetRecord]:
        """枚举 indexes/ 目录下的所有 asset record。

        性能：O(N) 扫盘。当 registry 很大时（>10k records）应改用索引数据库
        （Postgres backend 解决此问题）。
        """
        results: list[AssetRecord] = []
        index_root = self.root / "indexes"
        if not index_root.exists():
            return results

        if namespace:
            namespaces: list[Path] = [index_root / namespace]
            if not namespaces[0].exists():
                return results
        else:
            namespaces = [p for p in index_root.iterdir() if p.is_dir()]

        for ns_dir in namespaces:
            for name_dir in ns_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                for tag_file in name_dir.glob("*.json"):
                    try:
                        data = json.loads(tag_file.read_text(encoding="utf-8"))
                        # data 是完整 record JSON（含 ref 字段）
                        results.append(AssetRecord.model_validate(data))
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "[LocalFsContentStore] Skipped corrupt manifest: path={} err={}",
                            tag_file, e,
                        )
        return results

    def find_by_digest(self, digest: str) -> list[AssetRecord]:
        """遍历所有 record，找 digest 匹配的。O(N)，仅在 remove / gc 路径用。"""
        return [r for r in self.list_assets() if r.digest == digest]

    # ── 工具方法 ──

    def stats(self) -> dict[str, Any]:
        """统计：blob 数、总大小、namespace 数等。"""
        blob_root = self.root / "blobs"
        n_blobs = 0
        total_size = 0
        if blob_root.exists():
            for content_file in blob_root.rglob("content"):
                if content_file.is_file():
                    n_blobs += 1
                    try:
                        total_size += content_file.stat().st_size
                    except OSError:
                        pass

        manifest_root = self.root / "manifests"
        n_manifests = 0
        if manifest_root.exists():
            for f in manifest_root.rglob("*.json"):
                if f.name != "index.json":
                    n_manifests += 1

        return {
            "root": str(self.root),
            "n_blobs": n_blobs,
            "n_manifests": n_manifests,
            "total_blob_bytes": total_size,
        }

    def gc(self) -> int:
        """清理孤儿 blob（无任何 record 引用）。

        返回删除的 blob 数。
        """
        all_digests: set[str] = set()
        for record in self.list_assets():
            all_digests.add(record.digest)

        blob_root = self.root / "blobs"
        if not blob_root.exists():
            return 0

        removed = 0
        for content_file in blob_root.rglob("content"):
            # 从路径反推 digest: blobs/sha256/aa/{full-64-hex}/content
            try:
                parts = content_file.relative_to(blob_root).parts
                # parts = ('sha256', 'aa', 'aabbcc...', 'content')
                if len(parts) != 4 or parts[0] != "sha256" or parts[3] != "content":
                    continue
                # parts[2] 已是完整 64-char hash；parts[1] 只是 fan-out 用的 2 字符前缀
                digest = f"sha256:{parts[2]}"
            except Exception:
                continue

            if digest not in all_digests:
                try:
                    content_file.unlink()
                    # 清理可能为空的父目录
                    parent = content_file.parent
                    try:
                        parent.rmdir()  # 仅当空
                    except OSError:
                        pass
                    removed += 1
                except OSError as e:
                    logger.warning("[LocalFsContentStore] GC failed: path={} err={}", content_file, e)
        logger.info("[LocalFsContentStore] GC removed {} orphan blobs", removed)
        return removed
