"""请求/响应形态:接口字段目录(身份元数据 + children 结构树 + state 共识默认)。

2026-09-05 字段状态目录化定稿(取代 channel 三分类):
- ``state``(form|collapse|carry)取代 channel:条目携带**共识级默认呈现**,
  场景侧以 step.field_states 稀疏增量覆盖(platform 侧,不进目录);
  响应面无表单/值表之分,state 不被读取;
- ``children`` 内联树取代 ``schema_``,成为唯一结构真源:object/array 容器
  直接挂子条目,child.path 为父 path 的模板态后代(无 ``[i]``);
- ``type`` 全条目必填且限六原语 —— 任何字段都可能被划入 carry 面,注入
  需要类型(原 B5 carry 专属规则的无条件化);
- 深实例下标(``[i]``)是渲染器实例化的产物,不进目录(children 子树内
  path 一律模板态;顶层条目路径形态自由,响应断言候选可带下标)。

校验族谱:B4(body_type=none ⇒ 零声明)保留;B5/B6/B7/D2/D3 随 channel
消亡 —— B6 化为消费纪律(注入只读 path/type,不读 default/example),
D2/D3 的配置侧继任在 platform(配置编辑校验);新增模板纪律:children
仅容器 / 后代关系 / 全树 path 唯一(顶层 name 唯一 + 同级 name 唯一)/
整传一致性(carry 容器 ⇒ 子孙 carry)。
"""
from __future__ import annotations

import re
from typing import Any, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from ...utils import path as _path

# JSON Schema 原语词表(六原语):全条目 type 词表(注入宽松类型转换依赖)。
_PRIMITIVE_TYPES = ("string", "number", "integer", "boolean", "object", "array")

# state 词表:请求面共识默认呈现。form=表单直渲染 / collapse=折叠面板
# (纯布局,值仍在 body)/ carry=不渲染,值表注入。响应面无视此键。
_STATE_VALUES = ("form", "collapse", "carry")

# DeclarationEntry.name 标识符规则(D1 name 别名制):name 作显示别名与前端键,
# 须为 ASCII 标识符;path 是寻址真源,name↔path 解绑(2026-09-03 spec D1)。
# 树化修订:name 唯一性收敛为「顶层全局唯一 + 同级唯一」—— 跨分支同名
# ($.a.id / $.b.id)天然合法,树内节点的前端键是 path。
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _validate_path_enum(
    *,
    path: str,
    default: Any,
    example: Any,
    enum: list[Any] | None,
    owner: str,
) -> str:
    """path 合法性/归一化 + enum 一致性(返回归一化 path)。

    DeclarationEntry 条目级校验(owner 仅作报错文案前缀):
    - 双形态并存:短名合法,但非法 JSONPath / 空串直接拒;
    - 归一化统一收敛为 JSONPath 形态($.xxx),对已是 JSONPath 的 no-op;
    - enum 非空时 default/example 必须在 enum 中(None/[] 跳过、
      严格 ==、default 与 example 同等)。
    """
    if not _path.is_valid_path(path):
        raise ValueError(
            f"{owner}.path={path!r} 不是合法 path"
            f"（须为 JSONPath 形式或合法短名）"
        )
    norm = _path.normalize(path)
    if enum:
        for label, value in (("default", default), ("example", example)):
            if value is not None and not any(value == e for e in enum):
                raise ValueError(
                    f"{owner}.{label}={value!r} 不在 enum={enum!r} 中"
                )
    return norm


class DeclarationEntry(BaseModel):
    """统一目录条目 —— declarations 清单的元素(叶子或容器)。

    - type:六原语之一,全条目必填;
    - state:请求面共识默认呈现(响应面无视);场景侧 field_states 增量覆盖;
    - children:仅 object/array 容器可带;child.path 须为父 path 的模板态
      后代(children 子树内禁 ``[i]``,实例化归渲染器);
    - default/example:表单角色元数据,全条目合法;注入侧不消费(消费纪律,
      原 B6 存储禁值的软化:值仍不回流,保证点在消费端)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    type: str                      # 全条目必填,限六原语
    state: Literal["form", "collapse", "carry"] = "form"
    required: bool = True
    default: Any | None = None
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: Literal[
        "text", "number", "boolean", "select",
        "textarea", "json", "file", "binary", "unknown",
    ] = "unknown"
    # 字段来源语义(provenance),回答"这个值从哪来"。
    # - independent: 独立字面量,用户在表单直接填(默认)
    # - lookup:      可经接口/变量查询得到,如 ${var.xxx} / ${env.xxx},表单只读展示
    # - generated:   运行时基于其他接口处理结果动态生成(如 Assign 时间戳)
    source_kind: Literal["independent", "lookup", "generated"] = "independent"
    assertable: bool = False       # 仅响应侧有意义
    children: "list[DeclarationEntry] | None" = None

    @model_validator(mode="after")
    def _validate_entry(self) -> "DeclarationEntry":
        # D1 name 别名制:name 须为 ASCII 标识符(显示别名/前端键),
        # 与 path 末段解绑(寻址真源是 path)。
        # 根路径条目 name='$' 为既有惯例,放行特例
        # ("$" 是归一化不动点,path=='$' 判定与归一化先后无关)
        is_root_entry = self.name == "$" and self.path == "$"
        if not is_root_entry and not _NAME_RE.match(self.name):
            raise ValueError(
                f"DeclarationEntry.name={self.name!r} 须为 ASCII 标识符"
                f"([A-Za-z_][A-Za-z0-9_]*,作显示别名与前端键)"
            )
        self.path = _validate_path_enum(
            path=self.path, default=self.default,
            example=self.example, enum=self.enum,
            owner="DeclarationEntry",
        )
        if self.type not in _PRIMITIVE_TYPES:
            raise ValueError(
                f"DeclarationEntry.type={self.type!r} "
                f"不在 JSON Schema 原语词表({'/'.join(_PRIMITIVE_TYPES)})"
            )
        if self.children is not None:
            if self.type not in ("object", "array"):
                raise ValueError(
                    f"DeclarationEntry: {self.path!r} type={self.type!r} "
                    f"非容器(object/array),禁带 children"
                )
            if not self.children:
                raise ValueError(
                    f"DeclarationEntry: {self.path!r} children 为空列表 — "
                    f"容器要么不带(None),要么非空"
                )
        return self


def iter_declarations(
    entries: "list[DeclarationEntry]",
) -> Iterator[DeclarationEntry]:
    """深度优先展开 children 树(含容器自身)—— 树 → 平面的公共投影。

    field_defaults / export / 前端投影共用的唯一展开入口;顺序为
    先序(容器先于子孙),与目录文件里的书写序一致。
    """
    for e in entries:
        yield e
        yield from iter_declarations(e.children or [])


def _iter_tree(
    entries: "list[DeclarationEntry]",
    ancestor: "DeclarationEntry | None" = None,
) -> Iterator[tuple["DeclarationEntry", "DeclarationEntry | None"]]:
    """带父指针的展开((entry, parent),顶层 parent=None)— 校验专用。

    注意:pydantic BaseModel 本身可迭代(产出 (key, value) 元组),子孙
    递归必须传 ``e.children`` 列表,不能误迭代单个条目。
    """
    for e in entries:
        yield e, ancestor
        if e.children:
            yield from _iter_tree(e.children, e)


def _is_template_path(path: str) -> bool:
    """模板态 path:节点全为 FIELD(无 INDEX/WILDCARD/递归)。"""
    nodes = _path.parse_nodes(path)
    return nodes is not None and all(n.kind.name == "FIELD" for n in nodes)


def _check_sibling_names(
    entries: "list[DeclarationEntry]", owner: str,
) -> None:
    """同级 name 唯一(递归全树);顶层全局唯一由 _check_declarations 保证。"""
    seen: set[str] = set()
    for e in entries:
        if e.name in seen:
            raise ValueError(
                f"{owner} declarations 同级重复 name: {e.name!r}"
                f"(树内节点的前端键是 path,同级撞名才是冲突)"
            )
        seen.add(e.name)
    for e in entries:
        if e.children:
            _check_sibling_names(e.children, owner)


def _check_declarations(
    declarations: list[DeclarationEntry], owner: str,
) -> None:
    """spec 级目录校验:唯一性 + 模板纪律 + 整传一致性。"""
    # ① path 全树唯一;顶层 name 全局唯一(fields_meta/表单键控面)
    seen_paths: set[str] = set()
    dup: list[str] = []
    top_names: set[str] = set()
    dup_names: list[str] = []
    for e, parent in _iter_tree(declarations):
        if e.path in seen_paths and e.path not in dup:
            dup.append(e.path)
        seen_paths.add(e.path)
        if parent is None:
            if e.name in top_names and e.name not in dup_names:
                dup_names.append(e.name)
            top_names.add(e.name)
    if dup:
        raise ValueError(f"{owner} declarations 内重复 path(全树): {dup}")
    if dup_names:
        raise ValueError(f"{owner} declarations 内重复 name(顶层): {dup_names}")
    # ② 同级 name 唯一(递归)
    _check_sibling_names(declarations, owner)
    # ③ 模板纪律:children 子树内 path 须模板态且为父链后代
    #    (顶层条目路径形态自由 — 响应断言候选可带实例下标)
    for e, parent in _iter_tree(declarations):
        if parent is None:
            continue
        if not _is_template_path(e.path):
            raise ValueError(
                f"{owner} children 子树 path 须为模板态"
                f"(仅字段节点,禁 [i]/通配 — 实例化归渲染器):{e.path!r}"
            )
        if not e.path.startswith(parent.path + "."):
            raise ValueError(
                f"{owner} children path 须为父 path 后代:"
                f"{e.path!r} 不在 {parent.path!r} 之下"
            )
    # ④ 整传一致性:carry 容器 ⇒ 子孙必 carry
    #    (容器整传注入与子孙表单值/折叠展示不能并存 — 原 D3 的单规则继任)
    for e in iter_declarations(declarations):
        if e.children and e.state == "carry":
            for d in iter_declarations(e.children):
                if d.state != "carry":
                    raise ValueError(
                        f"{owner} carry 容器 {e.path!r} 的子孙必须 carry"
                        f"(整容器传递,一树一主):{d.path!r} state={d.state!r}"
                    )


class RequestSpec(BaseModel):
    """接口请求 body 的目录定义。

    declarations 为唯一承重存储(身份 + children 结构 + state 共识默认),
    构造与 wire 同形:{body_type, declarations}。结构真源是 children
    内联树(schema_ 已退役);面划分(state)是共识默认,场景侧可覆盖。
    """

    model_config = ConfigDict(extra="forbid")

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    declarations: list[DeclarationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "RequestSpec":
        # B4:none 即零声明(body 都不存在,无从声明字段)
        if self.body_type == "none":
            if self.declarations:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 declarations 必须为空"
                    f"(B4),实际 {len(self.declarations)} 条"
                )
        _check_declarations(self.declarations, "RequestSpec")
        return self

    @classmethod
    def declare(
        cls,
        model: "type[BaseModel] | dict[str, Any]",
        *,
        body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json",
        states: "dict[str, str] | None" = None,
    ) -> "RequestSpec":
        """declare() 糖(P7 重写):schema → 全量目录,零通道参数。

        - 递归走 properties:顶层成条目,嵌套 object/array 生成 children 树
          (array 取 items 的 properties);
        - states:{path 或顶层短名 → state} 盖戳(共识默认,如 remark→carry),
          未列出 = form;键归一化后匹配;
        - 节点无 type 可吸收即构造错误(目录 type 必备,拒绝静默垃圾条目)。
        """
        schema_ = model.model_json_schema() if isinstance(model, type) else model
        st = {_path.normalize(k): v for k, v in (states or {}).items()}
        entries = _walk_schema_properties(schema_, prefix="$", states=st)
        return cls(body_type=body_type, declarations=entries)

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        return {
            "body_type": self.body_type,
            "declarations": [e.model_dump(mode="json")
                             for e in self.declarations],
        }


def _deref(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    """单层 $ref 解析("#/$defs/X");解析失败原样返回(由 type 吸收报错)。"""
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return node
    target: Any = root
    for part in ref.lstrip("#/").split("/"):
        target = target.get(part) if isinstance(target, dict) else None
        if target is None:
            return node
    merged = {k: v for k, v in node.items() if k != "$ref"}
    merged.update(target if isinstance(target, dict) else {})
    return merged


def _node_type(node: dict[str, Any]) -> str | None:
    """节点 type 吸收:顶层 type;无则解析 anyOf/oneOf 的 Optional[T] 形
    (成员剥掉 null 后唯一 type)。"""
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


def _ui_kind_of(t: str, enum: list[Any] | None) -> str:
    """type(enum)→ ui_kind 基线:枚举下拉、数值/布尔控件、其余文本。"""
    if enum:
        return "select"
    return {"integer": "number", "number": "number",
            "boolean": "boolean"}.get(t, "text")


def _walk_schema_properties(
    node: dict[str, Any],
    *,
    prefix: str,
    states: dict[str, str],
    root: dict[str, Any] | None = None,
    marked: set[str] | None = None,
) -> list[DeclarationEntry]:
    """schema properties → 目录条目(+children 递归)。declare() 的生成核。

    - type 从节点吸收(_node_type),吸收不到即构造错误;
    - object → 递归 properties 为 children;array → items(object)递归,
      items 为原语则无 children(开放字典 additionalProperties 同理无 children);
    - states 盖戳(归一化 path 命中);marked 命中置 assertable(响应 B3)。
    """
    if root is None:
        root = node
    marked = marked or set()
    properties = node.get("properties") or {}
    required_names = set(node.get("required") or [])
    entries: list[DeclarationEntry] = []
    for key, raw in properties.items():
        if not isinstance(raw, dict):
            continue
        sub = _deref(raw, root)
        t = _node_type(sub)
        if t is None:
            raise ValueError(
                f"declare(): {prefix}.{key} 节点无 type 可吸收 — "
                f"目录 type 必备,请补节点或手写条目"
            )
        path = _path.normalize(f"{prefix}.{key}")
        kwargs: dict[str, Any] = {
            "name": key,
            "path": path,
            "type": t,
            "state": states.get(path, "form"),
            "required": key in required_names,
            "default": sub.get("default"),
            "description": sub.get("description") or "",
            "enum": sub.get("enum"),
            # ui_kind 基线自 type 推断(§2.1:目录携带无语境时的缺省渲染提示)
            "ui_kind": _ui_kind_of(t, sub.get("enum")),
            "assertable": path in marked,
        }
        if t in ("object", "array"):
            sub_node = sub if t == "object" else (sub.get("items") or {})
            sub_node = _deref(sub_node, root) if isinstance(sub_node, dict) else {}
            kids = _walk_schema_properties(
                sub_node, prefix=path, states=states, root=root, marked=marked)
            if kids:
                kwargs["children"] = kids
        entries.append(DeclarationEntry(**kwargs))
    return entries


class ResponseSpec(BaseModel):
    """接口某状态码响应的目录定义。

    构造与 wire 同形:{status, description, declarations}。响应面无
    form/carry 之分(state 不被读取);assertable=True 标记断言面(§6 B3)。
    """

    model_config = ConfigDict(extra="forbid")

    status: int
    description: str = ""
    declarations: list[DeclarationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "ResponseSpec":
        if not (100 <= self.status <= 599):
            raise ValueError(f"ResponseSpec.status={self.status} 必须在 [100, 599]")
        _check_declarations(self.declarations, "ResponseSpec")
        return self

    @classmethod
    def declare(
        cls,
        model: "type[BaseModel] | dict[str, Any]",
        *,
        status: int = 200,
        description: str = "",
        assert_paths: "list[str] | None" = None,
    ) -> "ResponseSpec":
        """declare() 糖(P7 重写):schema → 全量目录,assert_paths 置
        assertable=True(B3)。生成规则与 RequestSpec.declare 同款(全 form,
        响应面不读 state)。"""
        schema_ = model.model_json_schema() if isinstance(model, type) else model
        marked = {_path.normalize(p) for p in (assert_paths or [])}
        entries = _walk_schema_properties(schema_, prefix="$", states={},
                                          marked=marked)
        return cls(status=status, description=description, declarations=entries)

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "description": self.description,
            "declarations": [e.model_dump(mode="json")
                             for e in self.declarations],
        }


# 递归前向引用解析(children: list["DeclarationEntry"])
DeclarationEntry.model_rebuild()
