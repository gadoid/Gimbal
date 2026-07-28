"""请求/响应形态:描述接口输入输出 body 的形状与字段元信息。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class IOFieldBinding(BaseModel):
    """请求或响应 body 中的一个字段元信息。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    required: bool = True
    default: Any | None = None
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: Literal[
        "text", "number", "boolean", "select",
        "textarea", "json", "file", "binary", "unknown",
    ] = "unknown"


class RequestSpec(BaseModel):
    """接口请求 body 的形态定义。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    model: type[BaseModel] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)

    def json_schema(self) -> dict[str, Any] | None:
        """返回请求体的 JSON Schema,供跨进程传输与平台渲染使用。

        优先从 ``model`` 派生;否则使用 ``schema_``;都没有则返回 None。
        """
        if self.model is not None:
            return self.model.model_json_schema()
        return self.schema_

    def validate_body(self, values: Any) -> Any:
        """用声明的 Pydantic 模型校验并序列化 body;无模型时按原样返回。"""
        if self.model is None:
            return values
        if isinstance(values, dict):
            return self.model(**values).model_dump()
        return values

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """JSON 模式序列化时,把 ``model`` 类引用替换为内嵌 JSON Schema。"""
        out: dict[str, Any] = {
            "body_type": self.body_type,
            "fields": [f.model_dump(mode="json") for f in self.fields],
        }
        if self.model is not None:
            out["model_schema"] = self.model.model_json_schema()
            out["model_name"] = self.model.__name__
        if self.schema_ is not None:
            out["schema"] = self.schema_
        return out


class ResponseSpec(BaseModel):
    """接口某状态码响应的形态定义。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: int
    description: str = ""
    model: type[BaseModel] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)
    assertable_fields: list[str] = Field(default_factory=list)

    def json_schema(self) -> dict[str, Any] | None:
        if self.model is not None:
            return self.model.model_json_schema()
        return self.schema_

    @model_validator(mode="after")
    def _validate(self) -> "ResponseSpec":
        if not (100 <= self.status <= 599):
            raise ValueError(f"ResponseSpec.status={self.status} 必须在 [100, 599]")
        return self

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """JSON 模式序列化时,把 ``model`` 类引用替换为内嵌 JSON Schema。"""
        out: dict[str, Any] = {
            "status": self.status,
            "description": self.description,
            "fields": [f.model_dump(mode="json") for f in self.fields],
            "assertable_fields": list(self.assertable_fields),
        }
        if self.model is not None:
            out["model_schema"] = self.model.model_json_schema()
            out["model_name"] = self.model.__name__
        if self.schema_ is not None:
            out["schema"] = self.schema_
        return out
