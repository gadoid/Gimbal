"""ExternalEndpoint model — 外部接口登记目录(外部接口登记批 X1)。

external 步骤锚点(``ext:<alias>.<name>``)的结构定义来源:平台侧轻量
目录,URL 模式 + method + 可选 JSON Schema(OpenAPI 可导入)。登记的是
「接口形状」不是「版本」—— 无修订/冷化语义,第三方 API 版本体现在
path 或另建别名(设计 §8)。

* ``alias_name`` → service_aliases(登记前提:该别名 kind=external;
  plate 别名拒收,错误码 alias_not_external);
* ``request_schema`` 存**标准 JSON Schema**(draft-07 子集:object/
  string/number/integer/boolean/array + required + properties 嵌套),
  OpenAPI requestBody.schema 原样落库零转换;表单渲染用 declarations
  树由 services 层单一转换函数出(services/external_endpoints.py),
  不双写;
* ``auth`` 语义对齐 plate binding.auth 枚举(被测接口自身认证要求),
  保存校验提示与集成卡消费;执行侧凭证注入不读它(走既有
  service_bindings/credential_alias 链)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import JsonVar, UtcDateTime
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ExternalEndpoint(Base):
    __tablename__ = "external_endpoints"
    __table_args__ = (
        UniqueConstraint("alias_name", "name", name="uq_external_endpoint"),
        Index("ix_external_endpoint_alias", "alias_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 登记宿主:external 别名(kind=external;服务信息页同源管理)
    alias_name: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("service_aliases.alias_name",
                   ondelete="CASCADE"),
        nullable=False,
    )
    # 接口名(别名内唯一;锚点 ext:<alias>.<name> 的 name 段)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    # URL 模式;花括号段为路径参数(/orders/{id})
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    # 标准 JSON Schema(可空 = 无形状约束,表单自由编辑)
    request_schema: Mapped[dict | None] = mapped_column(JsonVar, nullable=True)
    # none|bearer|basic|cookie|custom —— 对齐 plate binding.auth 语义
    auth: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
