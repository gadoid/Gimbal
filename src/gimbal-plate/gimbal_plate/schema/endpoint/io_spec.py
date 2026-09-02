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


class CarryEntry(BaseModel):
    """非绑定传递字段:不进表单,值随 platform 配置走(spec §2.1)。

    与 IOFieldBinding 正交(fields[] = 表单面,carry = 传递面):
    无 value / 无 ui_kind / 无 source_kind —— 值在 platform 两张值表,
    path 复用外层 dict 的键,不在 entry 内重复。
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    # JSON Schema 原语词表;materialize 注入时按此做宽松类型转换。
    # 自持 —— 不依赖 schema_ 反查,端点没有 schema_ 也能声明 carry。
    type: str = "string"

    @model_validator(mode="after")
    def _validate(self) -> "CarryEntry":
        if self.type not in (
            "string", "number", "integer", "boolean", "object", "array",
        ):
            raise ValueError(
                f"CarryEntry.type={self.type!r} 不在 JSON Schema 原语词表"
                f"(string/number/integer/boolean/object/array)"
            )
        return self


class RequestSpec(BaseModel):
    """接口请求 body 的形态定义。"""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)
    carry: dict[str, CarryEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "RequestSpec":
        if self.body_type == "none":
            if self.schema_ is not None:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 schema_ 必须为 None,"
                    f"实际为 {self.schema_!r}"
                )
        # 规则 B(model 机制退役后单轴):body_type != none 时 schema_ 必须非 None。
        # schema_={} 视为"已声明"(Q-A a2)。
        elif self.schema_ is None:
            raise ValueError(
                f"RequestSpec.body_type={self.body_type!r} 时 schema_ 必须非 None"
            )
        # carry 键:归一化 JSONPath,且与 fields[].path 互斥(一个字段
        # 不得同时出现在表单面与传递面,spec §2.1)
        if self.carry:
            normalized: dict[str, CarryEntry] = {}
            for raw, entry in self.carry.items():
                if not _path.is_valid_path(raw):
                    raise ValueError(
                        f"RequestSpec.carry 键 {raw!r} 不是合法 path"
                        f"(须为 JSONPath 形式或合法短名)"
                    )
                norm = _path.normalize(raw)
                if norm in normalized:
                    raise ValueError(f"RequestSpec.carry 归一后重复键 {norm!r}")
                normalized[norm] = entry
            overlap = {f.path for f in self.fields} & set(normalized)
            if overlap:
                raise ValueError(
                    f"carry 键与 fields[].path 交集非空: {sorted(overlap)}"
                )
            self.carry = normalized
        return self

    def json_schema(self) -> dict[str, Any] | None:
        """返回请求体的 JSON Schema(schema_ 为唯一结构真源),供跨进程传输使用。"""
        return self.schema_

    def declarations_view(self) -> list[dict[str, Any]]:
        """§3.1 形状条目(纯派生,不动存储)。键序:binding 在前、carry 在后。"""
        out: list[dict[str, Any]] = []
        for f in self.fields:
            out.append({"name": f.name, "path": f.path, "channel": "binding",
                        "type": None, "required": f.required, "default": f.default,
                        "example": f.example, "description": f.description,
                        "enum": f.enum, "ui_kind": f.ui_kind,
                        "source_kind": f.source_kind, "assertable": False})
        for path, c in self.carry.items():
            # 根路径 "$" 的 last_segment 为 None → name="$"(根兜底;
            # 2026-09-02 起无现网实例,规则保留)
            out.append({"name": _path.last_segment(path) or "$", "path": path,
                        "channel": "carry", "type": c.type, "required": True,
                        "default": None, "example": None,
                        "description": c.description, "enum": None,
                        "ui_kind": "unknown", "source_kind": "independent",
                        "assertable": False})
        return out

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "body_type": self.body_type,
            "fields": [f.model_dump(mode="json") for f in self.fields],
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        if self.carry:
            out["carry"] = {k: v.model_dump(mode="json")
                            for k, v in self.carry.items()}
        decls = self.declarations_view()
        if decls:
            out["declarations"] = decls
        return out


class ResponseSpec(BaseModel):
    """接口某状态码响应的形态定义。"""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    status: int
    description: str = ""
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)
    assertable_fields: list[str] = Field(default_factory=list)

    def json_schema(self) -> dict[str, Any] | None:
        return self.schema_

    def declarations_view(self) -> list[dict[str, Any]]:
        """§3.1 形状条目(纯派生,不动存储);channel 恒 view_only。"""
        out: list[dict[str, Any]] = []
        assertable = set(self.assertable_fields)
        for f in self.fields:
            out.append({"name": f.name, "path": f.path, "channel": "view_only",
                        "type": None, "required": f.required, "default": f.default,
                        "example": f.example, "description": f.description,
                        "enum": f.enum, "ui_kind": f.ui_kind,
                        "source_kind": f.source_kind,
                        "assertable": f.path in assertable})
        return out

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
        out: dict[str, Any] = {
            "status": self.status,
            "description": self.description,
            "fields": [f.model_dump(mode="json") for f in self.fields],
            "assertable_fields": list(self.assertable_fields),
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        decls = self.declarations_view()
        if decls:
            out["declarations"] = decls
        return out
