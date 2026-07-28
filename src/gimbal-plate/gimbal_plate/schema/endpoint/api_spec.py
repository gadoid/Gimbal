"""接口坐标:描述一个 HTTP 接口的路由与方法。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiSpec(BaseModel):
    """被测接口的坐标与协议元信息。"""

    model_config = ConfigDict(extra="forbid")

    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 30.0

    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = "none"
    produces: list[str] = Field(default_factory=lambda: ["application/json"])
    consumes: list[str] = Field(default_factory=lambda: ["application/json"])

    @model_validator(mode="after")
    def _validate(self) -> "ApiSpec":
        if not self.service:
            raise ValueError("ApiSpec.service 不可为空")
        if not self.path.startswith("/"):
            raise ValueError(f"ApiSpec.path={self.path!r} 必须以 '/' 开头")
        if not (0 < self.timeout_seconds <= 600):
            raise ValueError(
                f"ApiSpec.timeout_seconds={self.timeout_seconds} 必须在 (0, 600]"
            )
        return self
