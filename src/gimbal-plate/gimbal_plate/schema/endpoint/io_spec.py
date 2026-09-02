"""请求/响应形态:描述接口输入输出 body 的形状与字段元信息。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from ...utils import path as _path

# JSON Schema 原语词表(六原语);DeclarationEntry carry 通道条目校验用。
_PRIMITIVE_TYPES = ("string", "number", "integer", "boolean", "object", "array")


def _validate_path_name_enum(
    *,
    path: str,
    name: str,
    default: Any,
    example: Any,
    enum: list[Any] | None,
    owner: str,
) -> str:
    """path 合法性/归一化 + name==末段 + enum 成员一致性(返回归一化 path)。

    DeclarationEntry 条目级校验(owner 仅作报错文案前缀):
    - 双形态并存:短名合法,但非法 JSONPath / 空串直接拒;
    - 归一化统一收敛为 JSONPath 形态($.xxx),对已是 JSONPath 的 no-op;
    - name 与 path 末段:末段是 FIELD 时 name 必须等于该标识符;
      末段非 FIELD(根/INDEX/WILDCARD/...)时不约束 name —— 沿用现行
      行为(spec §5 引 utils/path.py ROOT 非 FIELD);
    - enum 非空时 default/example 必须在 enum 中(None/[] 跳过、
      严格 ==、default 与 example 同等)。
    """
    if not _path.is_valid_path(path):
        raise ValueError(
            f"{owner}.path={path!r} 不是合法 path"
            f"（须为 JSONPath 形式或合法短名）"
        )
    norm = _path.normalize(path)
    seg = _path.last_segment(norm)
    if seg is not None and name != seg:
        raise ValueError(
            f"{owner}.name={name!r} 与 path={norm!r} 的末段 {seg!r} 不一致"
        )
    if enum:
        for label, value in (("default", default), ("example", example)):
            if value is not None and not any(value == e for e in enum):
                raise ValueError(
                    f"{owner}.{label}={value!r} 不在 enum={enum!r} 中"
                )
    return norm


class DeclarationEntry(BaseModel):
    """统一声明条目(spec §3.1)—— declarations 清单的元素。

    通道-规格闭合(B7)在 RequestSpec/ResponseSpec 的 spec 级校验;
    此处只做条目级:path/name/enum 校验、carry 通道的 type 必填
    与禁值(B6)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    channel: Literal["binding", "carry", "view_only"]
    type: str | None = None          # 仅 carry 必填(§6 B5)
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
    # 与默认值推导。注意：这是值来源维度，与"是否在表单展示"(channel)是正交
    # 的两个维度 —— schema-only 字段(PRD §5.4 Type C)不生成声明条目,
    # 碰不到 source_kind;它们的"隐藏"属于平台侧渲染模型。
    # 详见 FIELD-UI-MAPPING.md / PRD §5.4。
    # - independent: 独立字面量，与上下文无关联，用户在表单直接填（默认）
    # - lookup:      可经接口/变量查询得到，如 ${var.xxx} / ${env.xxx}，表单只读展示
    # - generated:   运行时基于其他接口处理结果动态生成（如 Assign 时间戳），表单提示"由策略产出"
    source_kind: Literal["independent", "lookup", "generated"] = "independent"
    assertable: bool = False

    @model_validator(mode="after")
    def _validate_entry(self) -> "DeclarationEntry":
        # 末段非 FIELD(根/INDEX/WILDCARD)不约束 name
        self.path = _validate_path_name_enum(
            path=self.path, name=self.name, default=self.default,
            example=self.example, enum=self.enum,
            owner="DeclarationEntry",
        )
        if self.channel == "carry":
            # type 必填(§6 B5)且在六原语词表
            if self.type is None:
                raise ValueError(
                    f"DeclarationEntry: carry 通道条目 {self.path!r} "
                    f"type 必填(§6 B5)"
                )
            if self.type not in _PRIMITIVE_TYPES:
                raise ValueError(
                    f"DeclarationEntry.type={self.type!r} "
                    f"不在 JSON Schema 原语词表({'/'.join(_PRIMITIVE_TYPES)})"
                )
            # B6:D2 后门封死 —— 值只走 platform 值表,条目不携带
            if self.default is not None:
                raise ValueError(
                    f"DeclarationEntry: carry 通道条目 {self.path!r} "
                    f"禁带 default(值在 platform 值表,B6)"
                )
            if self.example is not None:
                raise ValueError(
                    f"DeclarationEntry: carry 通道条目 {self.path!r} "
                    f"禁带 example(值在 platform 值表,B6)"
                )
        return self


class RequestSpec(BaseModel):
    """接口请求 body 的形态定义。

    declarations 为唯一承重存储(spec §3.3),构造与 wire 同形:
    {body_type, declarations, schema?}。binding=表单面、carry=传递面,
    按通道从清单投影(spec §4)。
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    declarations: list[DeclarationEntry] = Field(default_factory=list)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def _validate(self) -> "RequestSpec":
        if self.body_type == "none":
            if self.schema_ is not None:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 schema_ 必须为 None,"
                    f"实际为 {self.schema_!r}"
                )
            # B4:none 即零声明(body 都不存在,无从声明字段,spec §6 B4)
            if self.declarations:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 declarations 必须为空"
                    f"(B4),实际 {len(self.declarations)} 条"
                )
        # 规则 B(model 机制退役后单轴):body_type != none 时 schema_ 必须非 None。
        # schema_={} 视为"已声明"(Q-A a2)。
        elif self.schema_ is None:
            raise ValueError(
                f"RequestSpec.body_type={self.body_type!r} 时 schema_ 必须非 None"
            )
        _check_declarations(self.declarations, "RequestSpec",
                            allowed_channels=("binding", "carry"))
        return self

    def json_schema(self) -> dict[str, Any] | None:
        """返回请求体的 JSON Schema(schema_ 为唯一结构真源),供跨进程传输使用。"""
        return self.schema_

    @classmethod
    def declare(
        cls,
        model: "type[BaseModel] | dict[str, Any]",
        *,
        body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json",
        bindings: "dict[str, dict[str, Any] | None] | list[str] | None" = None,
        carry: "dict[str, dict[str, Any] | None] | list[str] | None" = None,
    ) -> "RequestSpec":
        """declare() 糖(spec §3.4):pydantic 优先路线的瘦身入口。

        元数据从 schema 节点吸收,type 全通道吸收(与构造桥的
        "type 仅 carry 必填、其余 None"刻意不对称,spec §3.4 末节);
        未列出的属性不生成声明(Type C 语义不变)。
        """
        schema_ = model.model_json_schema() if isinstance(model, type) else model
        entries = _declare_entries(schema_, bindings, "binding",
                                   skip_default=False, require_node=True)
        entries += _declare_entries(schema_, carry, "carry",
                                    skip_default=True, require_node=False)
        return cls(body_type=body_type, schema_=schema_, declarations=entries)

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "body_type": self.body_type,
            "declarations": [e.model_dump(mode="json")
                             for e in self.declarations],
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        return out


def _check_declarations(
    declarations: list[DeclarationEntry], owner: str,
    allowed_channels: tuple[str, ...],
) -> None:
    """spec 级声明校验(spec §3.2/§5/§6):path 唯一 + B7 通道闭合。"""
    # path 全清单唯一:list[path 唯一]。旧 carry∩fields 交集检查的
    # 结构性继任 —— 跨通道同 path 即重复,互斥不再靠运行时对拍
    seen: set[str] = set()
    dup: list[str] = []
    for e in declarations:
        if e.path in seen and e.path not in dup:
            dup.append(e.path)
        seen.add(e.path)
    if dup:
        raise ValueError(f"{owner} declarations 内重复 path(含跨通道交集非空): {dup}")
    # B7 通道闭合:请求面 {binding, carry}(§3.5 无第三种落点),响应面 {view_only}
    for e in declarations:
        if e.channel not in allowed_channels:
            raise ValueError(
                f"{owner} 声明通道非法(B7 闭合): {e.channel!r}"
                f" 不在 {allowed_channels}"
            )


def _node_type(node: dict[str, Any]) -> str | None:
    """declare() 的节点 type 吸收:顶层 type;无则解析 anyOf/oneOf 的
    Optional[T] 形(成员剥掉 null 后唯一 type)。

    真实语料形态:`remark: str | None = None` 的 schema 节点是
    anyOf[{string},{null}] 无顶层 type —— spec §3.4 settlement 示例
    要求 carry=["remark"] 吸收得 "string"。
    """
    t = node.get("type")
    if t is not None:
        return t
    for combinator in ("anyOf", "oneOf"):
        members = node.get(combinator)
        if isinstance(members, list):
            types = {m.get("type") for m in members
                     if isinstance(m, dict) and m.get("type") != "null"}
            if len(types) == 1:
                (t,) = types
                return t
    return None


def _declare_entries(
    schema_: dict[str, Any],
    items: dict[str, dict[str, Any] | None] | list[str] | None,
    channel: str,
    *,
    skip_default: bool,
    require_node: bool,
    marked_paths: set[str] | None = None,
) -> list[DeclarationEntry]:
    """declare() 糖的节点吸收/覆写展开(spec §3.4,纯函数)。

    - 键仅顶层属性名(schema.properties 直查);含 '.'/'[' → 构造错误
      (嵌套/数组路径请手写 DeclarationEntry 或走构造桥);
    - 吸收:type/default(仅 binding 通道)/description/enum,
      required ← schema.required 成员;example 从不在吸收清单;
    - dict 值中的键作为覆写,优先于节点吸收值(junk 键由
      DeclarationEntry extra=forbid 拒,不静默);
    - carry(§6 B2 镜像,自持):跳过 default 吸收(B6 契约面不带值),
      节点无 type 且未显式给 → "carry 声明缺 type" 构造错误;
    - marked_paths(响应 assert_paths):命中的条目 assertable=True(B3)。
    """
    if items is None:
        return []
    if isinstance(items, list):
        items = {k: None for k in items}
    properties = schema_.get("properties") or {}
    required_names = set(schema_.get("required") or [])
    marked_paths = marked_paths or set()
    entries: list[DeclarationEntry] = []
    for key, override in items.items():
        if "." in key or "[" in key:
            raise ValueError(
                f"declare() {channel} 键 {key!r} 非法:仅接受顶层属性名"
                f"(schema.properties 直查,不含 '.' 或 '[';"
                f"嵌套/数组路径请手写 DeclarationEntry 或走构造桥)"
            )
        node = properties.get(key)
        if node is None and require_node:
            raise ValueError(
                f"declare() {channel} 键 {key!r} 不在 schema.properties 中"
                f"(防吸收落空静默生成全默认值垃圾条目)"
            )
        node = node or {}
        path = f"$.{key}"
        absorbed: dict[str, Any] = {
            "name": key,
            "path": path,
            "channel": channel,
            "type": _node_type(node),
            "required": key in required_names,
            "description": node.get("description") or "",
            "enum": node.get("enum"),
            "assertable": path in marked_paths,
        }
        if not skip_default:
            absorbed["default"] = node.get("default")
        override = override or {}
        if channel == "carry" and not (absorbed["type"] or override.get("type")):
            raise ValueError(
                f"declare() carry 键 {key!r} 无 schema 节点且未显式给"
                f" type(carry 声明缺 type)"
            )
        entries.append(DeclarationEntry(**{**absorbed, **override}))
    return entries


class ResponseSpec(BaseModel):
    """接口某状态码响应的形态定义。

    declarations 为唯一承重存储(spec §3.3),构造与 wire 同形:
    {status, description, declarations, schema?}。view_only 通道,
    assertable=True 标记断言面(§6 B3)。
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    status: int
    description: str = ""
    declarations: list[DeclarationEntry] = Field(default_factory=list)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def _validate(self) -> "ResponseSpec":
        if not (100 <= self.status <= 599):
            raise ValueError(f"ResponseSpec.status={self.status} 必须在 [100, 599]")
        _check_declarations(self.declarations, "ResponseSpec",
                            allowed_channels=("view_only",))
        return self

    def json_schema(self) -> dict[str, Any] | None:
        return self.schema_

    @classmethod
    def declare(
        cls,
        model: "type[BaseModel] | dict[str, Any]",
        *,
        status: int = 200,
        view_only: "dict[str, dict[str, Any] | None] | list[str] | None" = None,
        assert_paths: "list[str] | None" = None,
    ) -> "ResponseSpec":
        """declare() 糖(spec §3.4):默认通道 view_only,assert_paths 置
        assertable=True(B3)。吸收规则与 RequestSpec.declare 同款。"""
        schema_ = model.model_json_schema() if isinstance(model, type) else model
        marked = {_path.normalize(p) for p in (assert_paths or [])}
        entries = _declare_entries(schema_, view_only, "view_only",
                                   skip_default=False, require_node=True,
                                   marked_paths=marked)
        return cls(status=status, schema_=schema_, declarations=entries)

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "description": self.description,
            "declarations": [e.model_dump(mode="json")
                             for e in self.declarations],
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        return out
