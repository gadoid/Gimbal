"""请求/响应形态:描述接口输入输出 body 的形状与字段元信息。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from ...utils import path as _path


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

    # 字段来源语义（provenance），回答"这个值从哪来"，决定平台前端的渲染方式
    # 与默认值推导。注意：这是值来源维度，与"是否在表单展示"是正交的两个维度——
    # 没有 IOFieldBinding 的 schema-only 字段（PRD §5.4 Type C）压根不会出现在
    # fields[] 里，因此碰不到 source_kind；它们的"隐藏"属于平台侧渲染模型，
    # 不应混入来源语义。详见 FIELD-UI-MAPPING.md / PRD §5.4。
    # - independent: 独立字面量，与上下文无关联，用户在表单直接填（默认）
    # - lookup:      可经接口/变量查询得到，如 ${var.xxx} / ${env.xxx}，表单只读展示
    # - generated:   运行时基于其他接口处理结果动态生成（如 Assign 时间戳），表单提示"由策略产出"
    source_kind: Literal["independent", "lookup", "generated"] = "independent"

    @model_validator(mode="after")
    def _validate(self) -> "IOFieldBinding":
        # path 合法性（双形态并存：短名合法，但非法 JSONPath / 空串直接拒）
        if not _path.is_valid_path(self.path):
            raise ValueError(
                f"IOFieldBinding.path={self.path!r} 不是合法 path"
                f"（须为 JSONPath 形式或合法短名）"
            )
        # 归一化：统一收敛为 JSONPath 形态（$.xxx）。request/response 的
        # IOFieldBinding.path 与 strategy[*].target、ResponseSpec.assertable_fields
        # 保持一致;避免 request_fields / response_fields 在 platform dict 中出现
        # 短名 vs JSONPath 混用。normalize() 对已经是 JSONPath 的 path 是 no-op。
        self.path = _path.normalize(self.path)
        # name 与 path 末段：末段是 FIELD 时 name 必须等于该标识符
        seg = _path.last_segment(self.path)
        if seg is not None and self.name != seg:
            raise ValueError(
                f"IOFieldBinding.name={self.name!r} 与 path={self.path!r} 的末段 {seg!r} 不一致"
            )
        # enum 成员一致性：enum 非空时 default / example 必须在 enum 中
        #   Q2=a:enum 为 None 或 [] 视为"未声明可选值清单",跳过校验(填空风格自由)
        #   Q1=b:严格 ==(Pythonic 默认,bool/int 互认由用户负责语义)
        #   Q4=a:default 与 example 同等严格
        #   Q3=b:enum 元素可以是任意类型(含 list/dict),直接用 == 比对
        if self.enum:
            for label, value in (("default", self.default), ("example", self.example)):
                if value is not None and not any(value == e for e in self.enum):
                    raise ValueError(
                        f"IOFieldBinding.{label}={value!r} 不在 enum={self.enum!r} 中"
                    )
        return self


class RequestSpec(BaseModel):
    """接口请求 body 的形态定义。"""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    model: type[BaseModel] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "RequestSpec":
        # 规则 A:body_type="none" 时 model 与 schema_ 必须都为 None
        if self.body_type == "none":
            if self.model is not None:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 model 必须为 None,"
                    f"实际为 {self.model.__name__}"
                )
            if self.schema_ is not None:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 schema_ 必须为 None,"
                    f"实际为 {self.schema_!r}"
                )
        # 规则 B:body_type != "none" 时 model 或 schema_ 至少一个非 None
        # 注:此处 schema_ 是空 dict {} 视为"已声明"(类型非 None),
        #     即使内容为空也算"声明了 schema";空 dict 与 None 等价的语义
        #     仅在规则 A 的"必须为空"上下文中不强制(见 Q-A a2)。
        else:
            has_model = self.model is not None
            has_schema = self.schema_ is not None
            if not (has_model or has_schema):
                raise ValueError(
                    f"RequestSpec.body_type={self.body_type!r} 时 model 或 schema_"
                    f" 至少一个非空"
                )
        # 规则 C(model 与 schema_ 可并存)不强制:见 V2 §2.2 决策 Q3 b。
        # model 优先语义已在 validate_body() 中隐含(model 非 None 时
        # 只用 model 校验,schema_ 仅作序列化/展示补充);见 V1 §4.1。
        return self

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

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

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
        # assertable_fields 中每个 path 归一后必须在 fields[*].path 归一集合里
        if self.assertable_fields:
            known = {_path.normalize(f.path) for f in self.fields}
            missing: list[str] = []
            for raw in self.assertable_fields:
                try:
                    norm = _path.normalize(raw)
                except ValueError as exc:
                    raise ValueError(
                        f"ResponseSpec[status={self.status}].assertable_fields"
                        f" 中存在非法 path {raw!r}: {exc}"
                    ) from exc
                if norm not in known:
                    missing.append(raw)
            if missing:
                raise ValueError(
                    f"ResponseSpec[status={self.status}].assertable_fields"
                    f" 中存在未声明字段: {missing}"
                )
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
