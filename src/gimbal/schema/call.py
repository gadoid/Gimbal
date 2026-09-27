"""schema/call.py — 协议中立调用描述。

`step.call = {protocol: "http", ...协议自有字段}` 是所有协议统一的调用表达；
`step.api` 是 HTTP 的永久语法糖（存量用例零迁移），在 Step 校验期归一化为
call{protocol:"http"}（见 schema/step.py 的 model_validator）。

设计要点：
  - 开放模型：`protocol` 之外的字段由各协议执行器自行解释校验
    （gimbal/protocols/），注册新协议不需要改本文件；
  - 每种协议的请求体数据结构定义在协议侧（执行器 + plate 侧的
    RequestSpec.declarations JSONPath 树），Call 只负责承载；
  - 协议内字段查询统一走 JSONPath（gimbal/utils/jsonpath.py），与
    Extract/Assertion/Assign 同一套查询语言。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Call(BaseModel):
    """协议中立调用。

    用法（HTTP 归一化产物 / 显式声明）::

        Call(protocol="http", service="fin", method="POST", path="/api/x")
        Call(protocol="grpc", service="user", method="GetUser")   # 自定义协议

    HTTP 专属字段（service/method/path/headers/timeout）不在此处声明类型：
    http 协议执行器（protocols/builtin/http.py）负责读取与校验，
    extra="allow" 让它们原样通过并可用属性访问。
    """

    model_config = ConfigDict(extra="allow")

    kind: Literal["call"] = "call"
    # v2.1 批次 F：协议显式必填（拼写错误在编译期暴露，不再缺省 http）
    protocol: str = Field(..., description="协议名（必填）；执行器注册表（ProtocolRegistry）的分派键")

    # ── HTTP 常用字段的类型提示（仅为可读性；真正的校验在 http 协议执行器）──
    # 通过 model_extra 访问：call.service / call.method / call.path / call.headers / call.timeout

    @property
    def call_protocol(self) -> str:
        """协议名（与 protocol 字段同值；保留属性形式方便与 Step.call_protocol 对齐）。"""
        return self.protocol

    def extra_fields(self) -> dict[str, Any]:
        """返回 protocol/kind 之外的协议自有字段快照。"""
        return {k: v for k, v in self.model_extra.items()} if self.model_extra else {}


if __name__ == "__main__":
    c = Call(protocol="http", service="fin", method="POST", path="/x")
    print(f"Call 测试: protocol={c.protocol} service={c.service} method={c.method}")
