"""接口坐标:描述一个接口的路由、方法与协议判别。

2026-09-27 协议中立化（总案 P1）：新增 `protocol` 判别字段，additive、默认
"http"，存量端点定义迁移量恒为零。开放 str（不锁 Literal）—— 协议注册是
gimbal 执行器侧事务（ProtocolRegistry），plate 只承载判别字段与声明式契约；
新协议（grpc/sql/mqtt/...）来时各自扩展 ApiSpec 变体（阶段 7）。

分派纪律：消费 ApiSpec 的代码按 protocol 分派 —— http 专属消费（by_route
三元组索引、method 过滤、状态码响应索引）只对 protocol=="http" 生效；
非 http 端点当前无生产者，校验放行、消费端按协议守卫。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOL_HTTP = "http"


class ApiSpec(BaseModel):
    """被测接口的坐标与协议元信息。"""

    model_config = ConfigDict(extra="forbid")

    # 协议判别字段：默认 http；执行器侧 ProtocolRegistry 以同名协议分派
    protocol: str = Field(default=PROTOCOL_HTTP, description="接口协议判别；默认 http")
    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 30.0

    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = "none"
    produces: list[str] = Field(default_factory=lambda: ["application/json"])
    consumes: list[str] = Field(default_factory=lambda: ["application/json"])

    @property
    def is_http(self) -> bool:
        """是否 http 协议（http 专属消费的分派守卫）。"""
        return self.protocol == PROTOCOL_HTTP

    @model_validator(mode="after")
    def _validate(self) -> "ApiSpec":
        if not self.protocol:
            raise ValueError("ApiSpec.protocol 不可为空")
        if not self.service:
            raise ValueError("ApiSpec.service 不可为空")
        if not self.path.startswith("/"):
            raise ValueError(f"ApiSpec.path={self.path!r} 必须以 '/' 开头")
        if not (0 < self.timeout_seconds <= 600):
            raise ValueError(
                f"ApiSpec.timeout_seconds={self.timeout_seconds} 必须在 (0, 600]"
            )
        return self
