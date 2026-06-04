"""repository/models.py  —  资产仓库的不可变数据模型。

设计参考 Docker Registry v2：

    AssetRef     —— 资产引用（namespace/name:tag 或 namespace/name@digest）
    AssetRecord  —— 资产元数据（指向某个 digest，携带 size / media_type / created_at 等）
    AssetContent —— 资产内容（record + 原始 bytes / 已解析对象）

三个模型均为 frozen（不可变），保证 push/pull 流程中数据一致。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gimbal.exceptions import InvalidAssetRef


# ── 名称合法性规则（与 OCI distribution spec 保持一致） ─────────────────

# OCI 允许: [a-z0-9]+(?:[._-][a-z0-9]+)*  ——  我们放宽为更简单的 [a-z0-9._-]+
# 防止出现 ../ 路径穿越、特殊字符、Unicode 等。
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")

DEFAULT_TAG = "latest"


# ── AssetRef ────────────────────────────────────────────────────────────


class AssetRef(BaseModel):
    """资产引用。

    两种合法形式（互斥）：

      1. tag 形式：   ``{namespace}/{name}:{tag}``
         e.g. ``customs/declare:v1.2.0``
      2. digest 形式：``{namespace}/{name}@{digest}``
         e.g. ``customs/declare@sha256:abc...``

    namespace 可选（缺省 = "library"，类似 Docker Hub 的官方库）。
    """

    model_config = ConfigDict(frozen=True)

    namespace: str = "library"
    name: str
    tag: str = DEFAULT_TAG
    digest: str | None = None

    @field_validator("namespace", "name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise InvalidAssetRef(
                f"Invalid asset name component: {v!r}",
                value=v,
                rule="[a-z0-9][a-z0-9._-]{0,127}",
            )
        return v

    @field_validator("tag")
    @classmethod
    def _check_tag(cls, v: str) -> str:
        if not _TAG_RE.match(v):
            raise InvalidAssetRef(
                f"Invalid tag: {v!r}",
                value=v,
                rule="[A-Za-z0-9_][A-Za-z0-9._-]{0,127}",
            )
        return v

    @field_validator("digest")
    @classmethod
    def _check_digest(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _DIGEST_RE.match(v):
            raise InvalidAssetRef(
                f"Invalid digest: {v!r}",
                value=v,
                rule="sha256:[a-f0-9]{64}",
            )
        return v

    @model_validator(mode="after")
    def _check_mutually_exclusive(self) -> "AssetRef":
        # tag 形式 与 digest 形式 互斥
        if self.tag != DEFAULT_TAG and self.digest is not None:
            raise InvalidAssetRef(
                "AssetRef cannot specify both tag (non-default) and digest",
                tag=self.tag,
                digest=self.digest,
            )
        return self

    # ── 字符串互转 ──
    @classmethod
    def parse(cls, ref: str) -> "AssetRef":
        """从 ``namespace/name:tag`` 或 ``namespace/name@digest`` 解析。

        支持简写：
          - ``name:tag``        → namespace="library"
          - ``name``            → namespace="library", tag="latest"
          - ``name@digest``     → namespace="library", digest="..."
        """
        if not ref or not isinstance(ref, str):
            raise InvalidAssetRef(f"Asset reference must be a non-empty string: {ref!r}", value=str(ref))

        # 1) 先按 digest 切（@ 优先级高于 :）
        digest: str | None = None
        rest = ref
        if "@" in rest:
            rest, digest = rest.rsplit("@", 1)
            digest = digest.strip()

        # 2) 切 namespace/name
        if "/" in rest:
            namespace, name = rest.rsplit("/", 1)
        else:
            namespace, name = "library", rest

        # 3) 切 tag
        tag = DEFAULT_TAG
        if ":" in name:
            name, tag = name.rsplit(":", 1)

        # 去掉可能的多余空白
        namespace = namespace.strip()
        name = name.strip()
        tag = tag.strip()

        return cls(namespace=namespace, name=name, tag=tag, digest=digest)

    def __str__(self) -> str:  # pragma: no cover
        if self.digest:
            return f"{self.namespace}/{self.name}@{self.digest}"
        if self.tag == DEFAULT_TAG:
            return f"{self.namespace}/{self.name}"
        return f"{self.namespace}/{self.name}:{self.tag}"


# ── AssetRecord ─────────────────────────────────────────────────────────


class AssetRecord(BaseModel):
    """资产元数据。

    一个 record 指向一个唯一 digest（同 digest 视为同一资产的不同 tag 视图）。
    """

    model_config = ConfigDict(frozen=True)

    ref: AssetRef
    digest: str                                  # sha256:abc...，**不**带 algorithm prefix
    size: int = Field(ge=0)
    kind: Literal["suite", "scenario", "data", "blob"] = "blob"
    media_type: str = "application/octet-stream"
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("digest")
    @classmethod
    def _check_digest(cls, v: str) -> str:
        # 与 AssetRef 保持一致：统一接受 sha256:abc... 形式
        if not _DIGEST_RE.match(v):
            raise InvalidAssetRef(
                f"Invalid digest in AssetRecord: {v!r}",
                value=v,
                rule="sha256:[a-f0-9]{64}",
            )
        return v


# ── AssetContent ────────────────────────────────────────────────────────


class AssetContent(BaseModel):
    """资产内容（record + 原始 bytes / 解析后的对象）。

    字段：
        record —— 资产元数据
        raw    —— 原始 bytes（所有 kind 都有）
        parsed —— 解析后的对象（仅当 kind="suite" / "scenario" / "data" 时有意义）

    `parsed` 不在序列化中保存（model_config.exclude），它只是运行期便利。
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    record: AssetRecord
    raw: bytes
    parsed: Any = None

    @property
    def digest(self) -> str:
        return self.record.digest

    @property
    def size(self) -> int:
        return self.record.size
