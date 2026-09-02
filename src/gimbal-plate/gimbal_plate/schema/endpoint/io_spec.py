"""请求/响应形态:描述接口输入输出 body 的形状与字段元信息。"""
from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from ...utils import path as _path

# JSON Schema 原语词表(六原语);CarryEntry.type 与 DeclarationEntry
# carry 通道条目共用同一词表对象(不复制两份)。
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

    IOFieldBinding 与 DeclarationEntry 共用(owner 仅作报错文案前缀):
    - 双形态并存:短名合法,但非法 JSONPath / 空串直接拒;
    - 归一化统一收敛为 JSONPath 形态($.xxx),对已是 JSONPath 的 no-op;
    - name 与 path 末段:末段是 FIELD 时 name 必须等于该标识符;
      末段非 FIELD(根/INDEX/WILDCARD/...)时不约束 name —— 沿用现行
      行为(spec §5 引 utils/path.py ROOT 非 FIELD;根 "$" 条目在
      桥编译/declare 派生时落兜底名 "$",非条目级强制);
    - enum 非空时 default/example 必须在 enum 中(None/[] 跳过、
      严格 ==、default 与 example 同等 —— IOFieldBinding 现行裁定)。
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
        # 校验逻辑与 DeclarationEntry 共享(模块级 _validate_path_name_enum)
        self.path = _validate_path_name_enum(
            path=self.path, name=self.name, default=self.default,
            example=self.example, enum=self.enum, owner="IOFieldBinding",
        )
        return self


class DeclarationEntry(BaseModel):
    """统一声明条目(spec §3.1)—— declarations 清单的元素。

    通道-规格闭合(B7)在 RequestSpec/ResponseSpec 的 spec 级校验;
    此处只做条目级:path/name/enum 与 IOFieldBinding 同款、carry
    通道的 type 必填与禁值(B6)。
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
    source_kind: Literal["independent", "lookup", "generated"] = "independent"
    assertable: bool = False

    @model_validator(mode="after")
    def _validate_entry(self) -> "DeclarationEntry":
        # path/name/enum 与 IOFieldBinding 同款(末段非 FIELD 不约束 name)
        self.path = _validate_path_name_enum(
            path=self.path, name=self.name, default=self.default,
            example=self.example, enum=self.enum,
            owner="DeclarationEntry",
        )
        if self.channel == "carry":
            # type 必填(§6 B5)且在六原语词表(与 CarryEntry 同源常量)
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
        if self.type not in _PRIMITIVE_TYPES:
            raise ValueError(
                f"CarryEntry.type={self.type!r} 不在 JSON Schema 原语词表"
                f"({'/'.join(_PRIMITIVE_TYPES)})"
            )
        return self


class RequestSpec(BaseModel):
    """接口请求 body 的形态定义。

    declarations 为唯一承重存储(spec §3.3);fields/carry 为按通道的
    派生投影(@property,现算新实例)。构造仍接受旧参数(fields=/
    carry=)—— 构造桥在存储前编译进清单,与 declarations= 二选一
    (spec §9 读写不对称:wire 形态两种键都发,构造形态只收一种)。
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    declarations: list[DeclarationEntry] = Field(default_factory=list)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="before")
    @classmethod
    def _bridge_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        decls = data.get("declarations")
        legacy = {"fields", "carry", "assertable_fields"} & data.keys()
        if decls is not None and legacy:
            raise ValueError("declarations 与旧参数(fields/carry/"
                             "assertable_fields)二选一,不得同传")
        if decls is not None or not legacy:
            return data
        # mode=before 拿到的可能是调用方(model_validate)持有的 dict
        # 引用 —— 浅拷贝后再 pop,不污染调用方
        data = dict(data)
        # 构造参数可能是模型实例(端点文件传 IOFieldBinding/CarryEntry)
        # 也可能是 dict(测试)。归一路由:实例直接 dump;dict 过对应模型
        # model_validate —— 默认值填充(含 CarryEntry.type="string" 默认)、
        # extra=forbid 拒 junk 键、词表校验,与今日裸 dict 构造同路同文案。
        # 两路 model_dump() 后键集完整,编译只补通道标记,零 .get() 兜底
        # —— 缺键在校验层自然炸,不在桥里静默
        compiled: list[dict[str, Any]] = []
        for f in (data.pop("fields", None) or []):
            fd = f.model_dump() if isinstance(f, IOFieldBinding) \
                else IOFieldBinding.model_validate(f).model_dump()
            fd["channel"] = "binding"
            compiled.append(fd)
        # 旧 carry 键规则原样保留:合法性(文案不变)→ 归一 → 查重;
        # carry∩fields 互斥由 spec 级 path 全清单唯一继任(结构化)
        normalized: dict[str, dict[str, Any]] = {}
        for raw, c in (data.pop("carry", None) or {}).items():
            if not _path.is_valid_path(raw):
                raise ValueError(
                    f"RequestSpec.carry 键 {raw!r} 不是合法 path"
                    f"（须为 JSONPath 形式或合法短名）"
                )
            norm = _path.normalize(raw)
            if norm in normalized:
                raise ValueError(f"RequestSpec.carry 归一后重复键 {norm!r}")
            cd = c.model_dump() if isinstance(c, CarryEntry) \
                else CarryEntry.model_validate(c).model_dump()
            # 根路径 "$" 的 last_segment 为 None → name="$"(根兜底;2026-09-02 起无现网实例,规则保留)
            cd.update(name=_path.last_segment(norm) or "$", path=norm,
                      channel="carry")
            normalized[norm] = cd
        compiled.extend(normalized.values())
        data["declarations"] = compiled
        return data

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

    @property
    def fields(self) -> list[IOFieldBinding]:
        """表单面派生投影:binding 条目 → IOFieldBinding 形状(spec §4.1)。"""
        return [IOFieldBinding(name=e.name, path=e.path, required=e.required,
                               default=e.default, example=e.example,
                               description=e.description, enum=e.enum,
                               ui_kind=e.ui_kind, source_kind=e.source_kind)
                for e in self.declarations if e.channel == "binding"]

    @property
    def carry(self) -> dict[str, CarryEntry]:
        # e.type 非 None 由 B5(carry 必填 type)保证;cast 只安抚类型
        # 检查,不做值兜底 —— 意外缺失应在校验层炸,不在派生层静默
        return {e.path: CarryEntry(description=e.description,
                                   type=cast(str, e.type))
                for e in self.declarations if e.channel == "carry"}

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
            "fields": [f.model_dump(mode="json") for f in self.fields],
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        if self.carry:
            out["carry"] = {k: v.model_dump(mode="json")
                            for k, v in self.carry.items()}
        if self.declarations:
            out["declarations"] = [e.model_dump(mode="json")
                                   for e in self.declarations]
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

    declarations 为唯一承重存储(spec §3.3);fields/assertable_fields
    为 view_only 通道的派生投影;构造桥同 RequestSpec(fields →
    view_only,assertable_fields 按 path 匹配置 assertable=True)。
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    status: int
    description: str = ""
    declarations: list[DeclarationEntry] = Field(default_factory=list)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="before")
    @classmethod
    def _bridge_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        decls = data.get("declarations")
        legacy = {"fields", "carry", "assertable_fields"} & data.keys()
        if decls is not None and legacy:
            raise ValueError("declarations 与旧参数(fields/carry/"
                             "assertable_fields)二选一,不得同传")
        if decls is not None or not legacy:
            return data
        data = dict(data)
        # 归一路由与 RequestSpec 桥同款:实例 dump / dict 过 model_validate
        compiled: list[dict[str, Any]] = []
        for f in (data.pop("fields", None) or []):
            fd = f.model_dump() if isinstance(f, IOFieldBinding) \
                else IOFieldBinding.model_validate(f).model_dump()
            fd["channel"] = "view_only"
            compiled.append(fd)
        # assertable_fields:归一后匹配编译条目路径(短名/JSONPath 双形态
        # 等价);未声明/非法 path 沿用今日文案整批拒 —— 不能静默丢标记
        known = {fd["path"] for fd in compiled}
        marked: set[str] = set()
        missing: list[str] = []
        for raw in (data.pop("assertable_fields", None) or []):
            try:
                norm = _path.normalize(raw)
            except ValueError as exc:
                raise ValueError(
                    f"ResponseSpec[status={data.get('status')}].assertable_fields"
                    f" 中存在非法 path {raw!r}: {exc}"
                ) from exc
            if norm in known:
                marked.add(norm)
            else:
                missing.append(raw)
        if missing:
            raise ValueError(
                f"ResponseSpec[status={data.get('status')}].assertable_fields"
                f" 中存在未声明字段: {missing}"
            )
        for fd in compiled:
            if fd["path"] in marked:
                fd["assertable"] = True
        data["declarations"] = compiled
        return data

    @model_validator(mode="after")
    def _validate(self) -> "ResponseSpec":
        if not (100 <= self.status <= 599):
            raise ValueError(f"ResponseSpec.status={self.status} 必须在 [100, 599]")
        _check_declarations(self.declarations, "ResponseSpec",
                            allowed_channels=("view_only",))
        return self

    @property
    def fields(self) -> list[IOFieldBinding]:
        """响应展示面派生投影:view_only 条目 → IOFieldBinding 形状(spec §4.1)。"""
        return [IOFieldBinding(name=e.name, path=e.path, required=e.required,
                               default=e.default, example=e.example,
                               description=e.description, enum=e.enum,
                               ui_kind=e.ui_kind, source_kind=e.source_kind)
                for e in self.declarations if e.channel == "view_only"]

    @property
    def assertable_fields(self) -> list[str]:
        """断言面派生投影:view_only 且 assertable=True 的 paths(§6 B3)。"""
        return [e.path for e in self.declarations
                if e.channel == "view_only" and e.assertable]

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
            "fields": [f.model_dump(mode="json") for f in self.fields],
            "assertable_fields": list(self.assertable_fields),
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        if self.declarations:
            out["declarations"] = [e.model_dump(mode="json")
                                   for e in self.declarations]
        return out
