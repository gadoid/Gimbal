"""字段状态目录化 io_spec 模型纪律(2026-09-05 spec §2/§7②③)。

覆盖新校验族谱:模板纪律(children 仅容器/后代关系/全树 path 唯一/
name 顶层+同级唯一)、整传一致性(carry 容器 ⇒ 子孙 carry)、B4 存续、
declare() walker(children 树生成、states 盖戳、$ref/Optional 吸收、
无 type 构造错)、wire 形状(serializer 无 schema 键)。
"""
from __future__ import annotations

from typing import Optional

import pytest
from pydantic import BaseModel, ValidationError

from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    iter_declarations,
)


# ── 构造糖 ─────────────────────────────────────────────
def _leaf(**kw) -> DeclarationEntry:
    base = dict(name="x", path="$.x", type="string")
    base.update(kw)
    return DeclarationEntry(**base)


def _req(*entries: DeclarationEntry, body_type: str = "json") -> RequestSpec:
    return RequestSpec(body_type=body_type, declarations=list(entries))


# ── §7② 模板纪律 ───────────────────────────────────────
def test_children_only_on_container():
    """叶子带 children 拒(仅 object/array 可携带)。"""
    with pytest.raises(ValidationError, match="非容器"):
        _leaf(children=[_leaf(name="y", path="$.x.y", type="string")])


def test_children_must_be_non_empty():
    """children 空列表拒:要么 None 要么非空(防空壳树)。"""
    with pytest.raises(ValidationError, match="非空"):
        _leaf(type="object", children=[])


def test_child_path_must_be_template():
    """children 子树内 path 禁 [i](实例化归渲染器)。"""
    with pytest.raises(ValidationError, match="模板态"):
        _req(
            DeclarationEntry(
                name="sup", path="$.sup", type="array",
                children=[_leaf(name="id", path="$.sup[0].id", type="string")],
            )
        )


def test_child_path_must_be_descendant():
    """children path 须为父 path 的后代。"""
    with pytest.raises(ValidationError, match="后代"):
        _req(
            DeclarationEntry(
                name="sup", path="$.sup", type="object",
                children=[_leaf(name="id", path="$.other.id", type="string")],
            )
        )


def test_top_level_path_may_carry_index():
    """顶层条目路径形态自由(响应断言候选可带实例下标)。"""
    spec = ResponseSpec(
        status=200,
        declarations=[_leaf(name="first", path="$.supplier[0].id", type="string")],
    )
    assert spec.declarations[0].path == "$.supplier[0].id"


def test_path_unique_across_tree():
    """path 全树唯一(跨分支同 path 拒)。"""
    with pytest.raises(ValidationError, match="重复 path"):
        _req(
            DeclarationEntry(
                name="a", path="$.a", type="object",
                children=[_leaf(name="id", path="$.a.id", type="string")],
            ),
            _leaf(name="a_id", path="$.a.id", type="string"),
        )


def test_name_top_level_unique():
    """name 顶层全局唯一(fields_meta/表单键控面在顶层)。"""
    with pytest.raises(ValidationError, match="重复 name"):
        _req(_leaf(name="x", path="$.x"), _leaf(name="x", path="$.y"))


def test_name_cross_branch_same_allowed():
    """跨分支同名合法($.a.id / $.b.id)— 树内节点前端键是 path。"""
    spec = _req(
        DeclarationEntry(
            name="a", path="$.a", type="object",
            children=[_leaf(name="id", path="$.a.id", type="string")],
        ),
        DeclarationEntry(
            name="b", path="$.b", type="object",
            children=[_leaf(name="id", path="$.b.id", type="string")],
        ),
    )
    assert {e.name for e in spec.declarations} == {"a", "b"}


def test_name_sibling_unique_within_children():
    """同级 name 唯一(children 内部)。"""
    with pytest.raises(ValidationError, match="同级重复 name"):
        _req(
            DeclarationEntry(
                name="a", path="$.a", type="object",
                children=[
                    _leaf(name="id", path="$.a.id", type="string"),
                    _leaf(name="id", path="$.a.idx", type="string"),
                ],
            )
        )


# ── §7② 整传一致性(D3 单规则继任)─────────────────────
def test_carry_container_descendants_must_carry():
    """carry 容器 ⇒ 子孙必 carry(整容器传递,一树一主)。"""
    with pytest.raises(ValidationError, match="子孙必须 carry"):
        _req(
            DeclarationEntry(
                name="sup", path="$.sup", type="object", state="carry",
                children=[_leaf(name="id", path="$.sup.id", type="string")],
            )
        )


def test_carry_container_all_carry_descendants_ok():
    spec = _req(
        DeclarationEntry(
            name="sup", path="$.sup", type="object", state="carry",
            children=[
                _leaf(name="id", path="$.sup.id", type="string", state="carry"),
            ],
        )
    )
    assert spec.declarations[0].children[0].state == "carry"


def test_collapse_container_with_form_child_ok():
    """collapse 是纯布局,不约束子孙 state(区别于 carry 整传)。"""
    spec = _req(
        DeclarationEntry(
            name="sup", path="$.sup", type="object", state="collapse",
            children=[_leaf(name="id", path="$.sup.id", type="string")],
        )
    )
    assert spec.declarations[0].children[0].state == "form"


# ── B4 存续 + type 词表 ─────────────────────────────────
def test_b4_none_means_zero_declarations():
    with pytest.raises(ValidationError, match="B4"):
        _req(_leaf(), body_type="none")


def test_type_required_and_limited_to_primitives():
    """type 全条目必填(缺失拒)且限六原语词表外拒。"""
    with pytest.raises(ValidationError, match="Field required"):
        DeclarationEntry(name="x", path="$.x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="原语词表"):
        DeclarationEntry(name="x", path="$.x", type="string[]")


def test_state_default_form_fail_closed():
    """默认 form:目录残缺 = 全渲染零注入(fail-closed)。"""
    e = _leaf()
    assert e.state == "form"


# ── §7③ declare() walker ───────────────────────────────
class _OrderLine(BaseModel):
    sku: str
    qty: int


class _Order(BaseModel):
    order_id: str
    remark: Optional[str] = None
    lines: list[_OrderLine] = []
    extra: dict[str, str] = {}


class _Nested(BaseModel):
    order: _Order


def test_declare_children_tree():
    """嵌套 schema → children 树(object→properties、array→items)。"""
    spec = RequestSpec.declare(_Nested, body_type="json")
    top = {e.name: e for e in spec.declarations}
    assert top["order"].type == "object"
    kids = {c.name: c for c in top["order"].children or []}
    assert kids["order_id"].type == "string"
    assert kids["remark"].type == "string"          # Optional 剥 null吸收
    assert kids["lines"].type == "array"
    line_kids = {c.name: c for c in kids["lines"].children or []}
    assert line_kids["sku"].type == "string"
    assert line_kids["qty"].type == "integer"


def test_declare_open_dict_no_children():
    """开放字典(additionalProperties)无 children — KV 编辑器。"""
    spec = RequestSpec.declare(_Order, body_type="json")
    top = {e.name: e for e in spec.declarations}
    assert top["extra"].type == "object"
    assert top["extra"].children is None


def test_declare_states_stamping():
    """states={path 或顶层短名 → state} 盖戳(未列出 = form)。"""
    spec = RequestSpec.declare(
        _Order, body_type="json", states={"remark": "carry", "$.order_id": "collapse"}
    )
    top = {e.name: e for e in spec.declarations}
    assert top["remark"].state == "carry"
    assert top["order_id"].state == "collapse"
    assert top["lines"].state == "form"


def test_declare_required_from_schema():
    spec = RequestSpec.declare(_Order, body_type="json")
    top = {e.name: e for e in spec.declarations}
    assert top["order_id"].required is True
    assert top["remark"].required is False


def test_declare_ref_absorption():
    """$ref 单层解析(模型内嵌模型 → pydantic $defs 引用)。"""
    spec = RequestSpec.declare(_Nested, body_type="json")
    top = {e.name: e for e in spec.declarations}
    assert top["order"].children  # $ref 解开后递归出 properties


def test_declare_no_type_rejected():
    """节点无 type 可吸收 → 构造错(拒静默垃圾条目)。

    walker 在 cls() 构造前抛原生 ValueError(pydantic ValidationError
    亦为 ValueError 子类,此处直接锚定原生形态)。
    """
    with pytest.raises(ValueError, match="无 type 可吸收"):
        RequestSpec.declare({"properties": {"x": {"description": "no type"}}},
                            body_type="json")


def test_response_declare_assert_paths():
    """assert_paths 置 assertable(B3 保留);响应面不读 state。"""
    resp = ResponseSpec.declare(
        _Order, status=200, assert_paths=["$.order_id", "order_id"]
    )
    top = {e.name: e for e in resp.declarations}
    assert top["order_id"].assertable is True
    assert top["remark"].assertable is False


# ── iter_declarations 公共投影 ──────────────────────────
def test_iter_declarations_preorder():
    """先序展开(容器先于子孙)。"""
    spec = _req(
        DeclarationEntry(
            name="a", path="$.a", type="object",
            children=[
                _leaf(name="id", path="$.a.id", type="string"),
                DeclarationEntry(
                    name="deep", path="$.a.deep", type="array",
                    children=[_leaf(name="k", path="$.a.deep.k", type="string")],
                ),
            ],
        ),
        _leaf(name="top", path="$.top", type="string"),
    )
    order = [e.path for e in iter_declarations(spec.declarations)]
    assert order == ["$.a", "$.a.id", "$.a.deep", "$.a.deep.k", "$.top"]


# ── wire 形状(serializer)──────────────────────────────
def test_wire_shape_no_schema_key():
    """构造与 wire 同形 {body_type, declarations};schema 键退役。"""
    spec = _req(_leaf())
    dumped = spec.model_dump(mode="json")
    assert set(dumped.keys()) == {"body_type", "declarations"}
    resp = ResponseSpec(status=200, declarations=[_leaf()])
    assert set(resp.model_dump(mode="json").keys()) == {
        "status", "description", "declarations"
    }


def test_wire_entry_carries_state_children():
    spec = _req(
        DeclarationEntry(
            name="a", path="$.a", type="object", state="carry",
            children=[_leaf(name="id", path="$.a.id", type="string", state="carry")],
        )
    )
    e = spec.model_dump(mode="json")["declarations"][0]
    assert e["state"] == "carry"
    assert e["children"][0]["state"] == "carry"
    assert "channel" not in e
