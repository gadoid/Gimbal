"""core/asset_resolver.py

资产解析器（CLI 层 ↔ 仓库层 ↔ 执行层之间的桥梁）。

职责：
    1. 把 CLI 传入的 ID 列表（含通配，如 ``customs/*:v1.*``）解析为具体 AssetRef。
    2. 通过 `AssetStore` 拉取对应的 `AssetContent`。
    3. 把 `AssetContent` 包装成 `ResolvedAsset`，返回给执行层。

使用：
    resolver = AssetResolver(
        kind=AssetKind.SCENARIO,
        asset_store=AssetStore(backend=LocalFsContentStore(root=...)),
    )
    assets = resolver.resolve(["customs/declare:v1.0", "customs/*:latest"])
    for a in assets:
        # a.content 是 AssetContent（raw bytes / parsed dict / record）
        # a.ref 是 AssetRef
        # 执行层可读 a.content.parsed 或 a.content.raw
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from gimbal.exceptions import AssetNotFound
from gimbal.log import get_logger
from gimbal.repository import AssetContent, AssetRef, AssetStore

logger = get_logger(__name__)


class AssetKind(str, Enum):
    SUITE = "suite"
    SCENARIO = "scenario"
    LOCAL = "local"  # 本地未注册文件（不走仓库）


@dataclass
class ResolvedAsset:
    """解析后的资产，足以驱动执行层。

    字段：
        id           —— CLI 原始 ID 字符串（用于日志 / 去重）
        ref          —— 规范化后的 AssetRef（仓库用的引用）
        kind         —— 资产类型
        version      —— 业务用的版本字符串（可与 ref.tag 不同）
        content      —— 资产内容（来自 AssetStore.pull）
        metadata     —— 额外上下文（registry URL、namespace 等）
    """

    id: str
    ref: AssetRef
    kind: AssetKind
    content: AssetContent
    version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AssetResolver:
    """资产解析器（接入 AssetStore 的真实实现）。

    解析策略：
        - 单 ref 形式（``namespace/name:tag`` / ``namespace/name@digest``）→ 直接 pull
        - 命名空间通配（``namespace/*`` / ``namespace/*:tag``）→ 展开为所有 name，逐一 pull
        - 完全通配（``*``）→ 展开为所有 namespace/name，逐一 pull

    失败容错：
        - 单个 ref 不存在时记录 warning 并跳过，不中断整个 batch
        - 其它异常（IO / 解析错误）也走 warn-and-skip
    """

    def __init__(
        self,
        kind: AssetKind,
        asset_store: AssetStore,
        *,
        source: str = "auto",
        registry: str | None = None,
    ) -> None:
        self.kind = kind
        self._store = asset_store
        self.source = source
        self.registry = registry
        logger.debug(
            "[AssetResolver] Initialized: kind={} source={} registry={} store={}",
            kind, source, registry, type(asset_store).__name__,
        )

    # ── 公开 API ──

    def resolve(self, ids: list[str]) -> list[ResolvedAsset]:
        """将一组 ID（含通配）解析为具体资产列表。"""
        logger.info("[AssetResolver] Resolving assets: kind={} ids={}", self.kind, ids)
        resolved: list[ResolvedAsset] = []
        for raw_id in ids:
            try:
                if self._is_wildcard(raw_id):
                    logger.debug("[AssetResolver] Expanding wildcard: pattern={}", raw_id)
                    resolved.extend(self._expand_wildcard(raw_id))
                else:
                    asset = self._resolve_single(raw_id)
                    if asset is not None:
                        resolved.append(asset)
            except Exception as e:  # noqa: BLE001
                logger.warning("[AssetResolver] Failed to resolve id={!r}: {}", raw_id, e)

        # 去重（按 ref 的字符串形式）
        seen: set[str] = set()
        unique: list[ResolvedAsset] = []
        for a in resolved:
            key = str(a.ref)
            if key not in seen:
                seen.add(key)
                unique.append(a)

        logger.info(
            "[AssetResolver] Resolution complete: requested={} resolved={} (after dedup)",
            len(ids), len(unique),
        )
        return unique

    # ── 内部 ──

    def _is_wildcard(self, raw_id: str) -> bool:
        return "*" in raw_id or "?" in raw_id

    def _expand_wildcard(self, pattern: str) -> list[ResolvedAsset]:
        """展开通配模式。

        支持的形式：
            ``*``                    —— 全部
            ``namespace/*``          —— 该 namespace 下全部 name
            ``namespace/*:tag``      —— 该 namespace 下全部 name 的指定 tag
            ``*/*:tag``              —— 全库指定 tag
        """
        results: list[ResolvedAsset] = []

        # 解析 pattern: 切出 namespace 部分 与 name:tag 部分
        namespace, _, name_pattern = pattern.partition("/")
        if not name_pattern:
            # 形式 "namespace"（无 /）—— 不算通配，已在 _is_wildcard 前过滤
            return results

        # 切出 tag（如果有）
        if ":" in name_pattern:
            name_pat, _, tag_pat = name_pattern.partition(":")
        else:
            name_pat, tag_pat = name_pattern, "latest"

        # 列出该 namespace 下的所有 asset
        records = self._store.list_assets(namespace=namespace if namespace != "*" else None)

        # 按 name 通配 + tag 通配（如果需要）筛选
        for rec in records:
            if not fnmatch.fnmatch(rec.ref.name, name_pat):
                continue
            if not fnmatch.fnmatch(rec.ref.tag, tag_pat):
                continue
            # 构造完整 raw_id 走 _resolve_single 复用 pull 逻辑
            raw_id = f"{rec.ref.namespace}/{rec.ref.name}:{rec.ref.tag}"
            asset = self._resolve_single(raw_id)
            if asset is not None:
                results.append(asset)

        return results

    def _resolve_single(self, raw_id: str) -> ResolvedAsset | None:
        """解析单个 ref。"""
        try:
            ref = AssetRef.parse(raw_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[AssetResolver] Invalid ref id={!r}: {}", raw_id, e)
            return None

        if not self._store.exists(ref):
            raise AssetNotFound(f"Asset not found: {ref}", ref=str(ref))

        try:
            content = self._store.pull(ref)
        except AssetNotFound:
            logger.warning("[AssetResolver] Asset not found in store: {}", ref)
            return None

        return ResolvedAsset(
            id=raw_id,
            ref=ref,
            kind=self.kind,
            content=content,
            version=ref.tag,
            metadata={
                "source": self.source,
                "registry": self.registry,
                "digest": content.digest,
                "size": content.size,
            },
        )
