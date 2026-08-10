"""EndpointSpec:被测系统一个接口的完整契约。"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .api_spec import ApiSpec
from .io_spec import RequestSpec, ResponseSpec
from .metadata import EndpointMetadata


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.\-]{1,63}$")
# EndpointSpec.version (plate 契约版本) semver:纯 x.y.z 三段,不含 pre-release / build metadata。
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class EndpointSpec(BaseModel):
    """被测系统的一个接口契约。

    一期承担:
        C1 结构定义(系统-服务-接口-字段层级)
        C2 用例导出(由 ``EndpointCaseExporter`` 消费)

    一期不做:
        C3 平台渲染视图 — 前端直接 ``model_dump()`` 即可。
    """

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    # ── 唯一标识 ──
    id: str
    system: str
    service: str
    name: str
    description: str = ""

    # ── 接口坐标 ──
    api: ApiSpec

    # ── 输入输出形态 ──
    request: RequestSpec | None = None
    responses: dict[int, ResponseSpec] = Field(default_factory=dict)

    # ── 业务元信息 ──
    metadata: EndpointMetadata = Field(default_factory=EndpointMetadata)

    # ── 完整性 ──
    version: str = "1.0.0"
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_integrity(self) -> "EndpointSpec":
        # id
        if not self.id:
            raise ValueError("EndpointSpec.id 不可为空")
        if not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"EndpointSpec.id={self.id!r} 不合法(需匹配 ^[a-z][a-z0-9_.\\-]{{1,63}}$)"
            )
        # system / service
        if not self.system:
            raise ValueError("EndpointSpec.system 不可为空")
        if not self.service:
            raise ValueError("EndpointSpec.service 不可为空")
        if self.api.service != self.service:
            raise ValueError(
                f"EndpointSpec.service={self.service!r} 与 api.service="
                f"{self.api.service!r} 不一致"
            )
        # name
        if not self.name:
            raise ValueError("EndpointSpec.name 不可为空")
        # version — plate 契约版本,semver x.y.z 三段
        if not _SEMVER_PATTERN.match(self.version):
            raise ValueError(
                f"EndpointSpec.version={self.version!r} 不合法"
                f"(需匹配 ^\\d+\\.\\d+\\.\\d+$)"
            )
        # 200 响应必填(业务约定)
        if 200 not in self.responses:
            raise ValueError("EndpointSpec.responses 必须包含 200 状态码")
        # updated_at 与 version 一致性
        if self.updated_at is None:
            self.updated_at = datetime.now(UTC)
        # id 必须以 system 字段作为 prefix,确保 id 与 system 字段保持契约一致。
        # 这样客户系统拿到 endpoint id 后无需先拉 system 列表就能反查其归属。
        if not self.id.startswith(f"{self.system}."):
            raise ValueError(
                f"EndpointSpec.id={self.id!r} 必须以 system 字段 "
                f"'{self.system}' 作为 prefix,"
                f"完整期望 prefix='{self.system}.'"
            )
        return self
