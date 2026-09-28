"""protocols/builtin/http.py — http 协议执行器的规范化入口。

实现本体在 `gimbal/strategy/builtin/call.py` 的 CallExecutor（协议中立化
时原地升级为 ProtocolExecutor 第一员；kind 自残留 #2 起为 "call"）。
本模块只提供规范化别名，
供按 `gimbal.protocols.builtin` 路径引用的代码使用。

HttpCallParams（S-1）：http 协议 call 字段的参数模型 —— 编译期校验
step.call 的协议自有字段（未知键 CompileError），并经 ext 导出供平台
表单生成。字段面 = CallExecutor 实际读取的字段（call.py build_spec）。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from gimbal.strategy.builtin.call import CallExecutor as HttpProtocolExecutor


class HttpCallParams(BaseModel):
    """http 协议 call 字段模型（service/method/path/headers/timeout/user）。"""

    model_config = ConfigDict(extra="forbid")

    service: Optional[str] = Field(default=None, description="服务键；缺省走 service_base_url")
    method: str = Field(default="GET", description="HTTP 方法")
    path: str = Field(default="/", description="请求路径（以 / 开头）")
    headers: dict[str, str] = Field(default_factory=dict, description="附加请求头")
    timeout: float = Field(default=30.0, gt=0, le=600, description="超时秒数")
    user: Optional[str] = Field(default=None, description="认证标签；按 AuthRegistry 会话注入头")
    # 平台视图扩展(plate Call 同款声明):convert 正常会剥离,echo 桩等
    # 绕过 convert 的路径可能残留 —— 引擎侧容忍并忽略(endpoint 身份锚)
    view_hints: Optional[dict] = Field(default=None, description="平台扩展;执行忽略")


__all__ = ["HttpProtocolExecutor", "HttpCallParams"]
