"""M2 Call（M2 方案 v2.4 §3 M1；步骤 1 定义形态）。

与执行器 ``gimbal/schema/call.py`` 同构：**唯一保持开放（extra=allow）
的模型**（M1 的唯一例外）——协议自有字段由协议 ``params_model`` 校验
（http 已是 forbid）。Release 4.5：场景存储只存场景自有字段，binding
派生字段由 plate 投影（/convert 合并）；``protocol`` 必填。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Call(BaseModel):
    """协议中立调用外壳。"""

    model_config = ConfigDict(extra="allow")

    kind: Literal["call"] = "call"
    protocol: str = Field(
        ..., description="协议名（必填）；协议注册表的分派键")
    # G1 认证施加(集成 P2/Y1,gen2):被测接口自身的认证要求,由 plate
    # binding.auth 透传(四标准值);custom 时 auth_signer 携带签名器名
    # (缺省 md5sign —— 唯一具名签名器,第二个签名器随 MeterSphere/P4
    # 再上系统级声明)。none/缺省 = 不注入,旧行为不变。
    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = Field(
        default="none",
        description="认证施加方式（binding.auth 透传；none=不注入）")
    auth_signer: Optional[str] = Field(
        default=None,
        description="custom 时的签名器名（缺省 md5sign）")
