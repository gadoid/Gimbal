"""资产解析器。

职责：根据 --source 策略，从本地缓存或远端 registry 解析出实际可执行的资产对象。
支持命名空间通配（含 / 分隔符的 ID 模式）。

这是 CLI 层和执行层之间的桥梁。后续可独立测试、独立扩展。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from gimbal.log import get_logger

logger = get_logger(__name__)


class AssetKind(str, Enum):
    SUITE = "suite"
    SCENARIO = "scenario"
    LOCAL = "local"  # 本地未注册文件


@dataclass
class ResolvedAsset:
    """解析后的资产引用，足以驱动执行层。"""

    id: str
    kind: AssetKind
    version: str | None = None
    source_path: str | None = None  # 本地路径或远端 URI
    metadata: dict[str, Any] = field(default_factory=dict)


class AssetResolver:
    """资产解析器。

    占位实现，演示接口。实际实现应：
      - 接入资产库（MongoDB + 对象存储）
      - 支持命名空间通配展开（customs/* → customs/declare, customs/inspect, ...）
      - 处理本地缓存与远端拉取的协调
      - 拒绝跨分隔符通配（避免 customs-* 这种自由通配混入）
    """

    def __init__(
        self,
        kind: AssetKind,
        source: str = "auto",
        registry: str | None = None,
        version: str | None = None,
    ) -> None:
        self.kind = kind
        self.source = source
        self.registry = registry
        self.version = version
        logger.debug("[AssetResolver] Initialized: kind={} source={} registry={} version={}",
                    kind, source, registry, version)

    def resolve(self, ids: list[str]) -> list[ResolvedAsset]:
        """将一组 ID（含通配）解析为具体的资产列表。"""
        logger.info("[AssetResolver] Resolving assets: kind={} ids={}", self.kind, ids)
        resolved: list[ResolvedAsset] = []
        for raw_id in ids:
            if self._is_namespace_wildcard(raw_id):
                logger.debug("[AssetResolver] Expanding namespace wildcard: pattern={}", raw_id)
                resolved.extend(self._expand_namespace(raw_id))
            else:
                asset = self._resolve_single(raw_id)
                if asset:
                    resolved.append(asset)
        # 去重
        seen: set[str] = set()
        unique: list[ResolvedAsset] = []
        for a in resolved:
            if a.id not in seen:
                seen.add(a.id)
                unique.append(a)
        logger.info("[AssetResolver] Resolution complete: requested={} resolved={}", len(ids), len(unique))
        return unique

    def _is_namespace_wildcard(self, raw_id: str) -> bool:
        """命名空间通配：含 * 且只在分隔符之间。"""
        if "*" not in raw_id:
            return False
        # 简单校验：不允许 *xxx* 这种自由通配，必须紧贴分隔符
        # 真正实现可以更严格
        return "/" in raw_id or ":" in raw_id

    def _expand_namespace(self, pattern: str) -> list[ResolvedAsset]:
        """展开命名空间通配。占位实现。"""
        # TODO: 接入资产库做实际查询
        return []

    def _resolve_single(self, raw_id: str) -> ResolvedAsset | None:
        """解析单个 ID。占位实现。"""
        # TODO: 接入资产库
        return ResolvedAsset(
            id=raw_id,
            kind=self.kind,
            version=self.version,
            source_path=f"<{self.source}>/{raw_id}",
        )