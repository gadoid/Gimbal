"""Plate 服务化版本的快照(聚合 + 校验和)。

对应设计:PR-2.0 §2.4 + PLATE_EVOLUTION §3 Phase 2。

职责:
  * ``PlateManifest`` 聚合"某版本下的所有服务 + 端点 + 校验和"
  * ``compute_checksum`` SHA256(基于规范 JSON 序列化)
  * ``verify`` 检测漂移

业务价值:
  * 客户端拉取 manifest 后,用 checksum 验证字节级一致(防中间代理篡改)
  * 不同版本的 manifest checksum 不同(协议升级硬前提)
  * 服务列表增删 → checksum 变化(契约漂移检测)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import final

from Plate.version import PlateVersion


@final
@dataclass(frozen=True)
class PlateManifest:
    """某版本 Plate 的完整快照。

    字段语义:
      version: 此 manifest 的版本(必填)
      services: 服务名 → 该服务的端点 to_dict() 列表
      checksum: SHA256 字符串,空字符串 = 未计算
    """

    version: PlateVersion
    services: dict[str, list[dict]] = field(default_factory=dict)
    checksum: str = ""

    def to_dict(self) -> dict:
        """序列化为 dict。

        注:services 内的端点 list 已按 (method, path) 排序 —— 见
        ``compute_checksum`` 和 ``from_services`` 调用方约定。
        checksum 字段**不**参与自身的 checksum 计算,它是"标记"非"数据"。
        """
        return {
            "version": self.version.to_dict(),
            "services": self.services,  # 假定已排序(调用方责任)
            "checksum": self.checksum,
        }

    @classmethod
    def compute_checksum(
        cls,
        version: PlateVersion,
        services: dict[str, list[dict]],
    ) -> str:
        """计算 SHA256 校验和。

        算法:
          1. services 按 service 名排序
          2. 每个 service 内的端点按 (method, path) 排序
          3. ``json.dumps(sort_keys=True, separators=(",", ":"))``
          4. SHA256 → hex digest

        byte-equal 保证:
          - sort_keys=True:dict 键顺序无关
          - 排序 services 与端点:list 顺序无关
          - 固定 separators:空格无关
        """
        sorted_services: dict[str, list[dict]] = {}
        for svc_name in sorted(services.keys()):
            specs = services[svc_name]
            sorted_services[svc_name] = sorted(
                specs, key=lambda s: (s.get("method", ""), s.get("path", ""))
            )
        payload = {
            "version": version.to_dict(),
            "services": sorted_services,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_services(
        cls,
        version: PlateVersion,
        services: dict[str, list[dict]],
    ) -> "PlateManifest":
        """从 version + services 构造 manifest,自动计算 checksum。

        调用方**不**需预先排序 —— 本方法内部排序。
        """
        chk = cls.compute_checksum(version, services)
        # 排序后存入(保证 to_dict 的产物与 checksum 一致)
        sorted_services: dict[str, list[dict]] = {}
        for svc_name in sorted(services.keys()):
            sorted_services[svc_name] = sorted(
                services[svc_name],
                key=lambda s: (s.get("method", ""), s.get("path", "")),
            )
        return cls(version=version, services=sorted_services, checksum=chk)

    def verify(self) -> None:
        """校验 checksum,不符抛 ValueError(检测漂移)。"""
        expected = self.compute_checksum(self.version, self.services)
        if expected != self.checksum:
            raise ValueError(
                f"PlateManifest: checksum 不一致,可能漂移或被篡改。"
                f"expected={expected!r}, actual={self.checksum!r}"
            )


__all__ = ["PlateManifest"]