"""gimbal_plate.endpoint —— 被测接口的全量描述。

``EndpointSpec`` 同时承载:
    - 坐标 (``ApiSpec``:service / method / path / headers / timeout)
    - 请求/响应体形状 (直接持有 Pydantic 类引用)
    - 业务自然语言信息 (``EndpointInfo``,不进产物)

提供四个输出方法:
    - ``to_api()``              编译为 Gimbal Api 字段
    - ``to_request(values)``    编译为 Gimbal Request 字段
    - ``request_schema()``      返回请求 JSON Schema(给 Platform)
    - ``response_schema(status)`` 返回指定状态码的响应 JSON Schema
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ApiSpec(BaseModel):
    """接口坐标,对应 gimbal 的 Api。"""
    model_config = ConfigDict(extra="forbid")

    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float = 30


class EndpointInfo(BaseModel):
    """业务自然语言信息,人和 agent 读,不进产物。"""
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    businessModule: str = ""
    preconditions: list[str] = Field(default_factory=list)
    successCriteria: str = ""


class EndpointSpec(BaseModel):
    """一个接口的全量描述:坐标 + 请求/响应体形状 + 业务信息。"""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: str                                    # 稳定标识,如 "settlement.order.add"
    name: str                                  # 接口短名,如 "新增订单"
    api: ApiSpec
    RequestBody: type[BaseModel] | None = None
    ResponseBody: dict[str, type[BaseModel]] = Field(default_factory=dict)   # 状态码 -> 模型,如 {"200": ..., "400": ...}
    info: EndpointInfo = Field(default_factory=EndpointInfo)

    def to_api(self) -> dict[str, Any]:
        return {"kind": "api", **self.api.model_dump()}

    def to_request(self, values: str | dict[str, Any] | list[Any]) -> dict[str, Any]:
        if self.RequestBody is None or isinstance(values, str):
            body = values          # str 形态(XML/text)或未声明结构,原样透传
        elif isinstance(values, list):
            body = values          # list 形态,本期不做逐项校验
        else:
            body = self.RequestBody(**values).model_dump()
        return {"kind": "request", "body": body}

    def request_schema(self) -> dict[str, Any] | None:
        return self.RequestBody.model_json_schema() if self.RequestBody else None

    def response_schema(self, status: str = "200") -> dict[str, Any] | None:
        model = self.ResponseBody.get(status)
        return model.model_json_schema() if model else None