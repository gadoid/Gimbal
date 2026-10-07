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

from gimbal_plate.dialect import EndpointSpec, RequestSpec, ResponseSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == 'fin']

from gimbal_plate.schema.endpoint.io_spec import (
    DeclarationEntry,
    iter_declarations,
)


# ── 构造糖 ─────────────────────────────────────────────
def _leaf(**kw) -> DeclarationEntry:
    base = dict(name="x", path="$.x", type="string")
    base.update(kw)
    return DeclarationEntry(**base)


def _req(*entries: DeclarationEntry, body_type: str = "json") -> RequestSpec:
    # body_type 已移入 binding(6.2);参数保留以兼容旧调用,值被忽略
    _ = body_type
    return RequestSpec(declarations=list(entries))


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
    with pytest.raises(ValidationError, match="path"):
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
    spec = ResponseSpec(declarations=[_leaf(name="first", path="$.supplier[0].id", type="string")],
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


# §7③ declare() walker 已随 X5 退役(语法糖拆除);
# 树纪律由 _check_declarations 承接,walker 测试随之删除。
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
    assert set(dumped.keys()) == {"declarations"}
    resp = ResponseSpec(declarations=[_leaf()])
    assert set(resp.model_dump(mode="json").keys()) == {
        "description", "declarations"
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


# ── 目录级决策回归 ─────────────────────────────────────
def test_sys_upttime_form_across_catalog():
    """2026-09-06 拍板:全目录 sys_upttime 由 carry 提升 form(审计字段进表单)。

    防回归:后续 curl 重导入/手工编辑不得把任何 sys_upttime 路径
    (含 $.supplier.sys_upttime 等容器内)翻回 carry。
    """
    offenders: list[str] = []
    for ep in ALL_ENDPOINTS:
        for d in iter_declarations((ep.request.declarations if ep.request else None) or []):
            if d.name == "sys_upttime" and d.state != "form":
                offenders.append(f"{ep.id} request {d.path} state={d.state}")
        for resp in ep.responses.values():
            for d in iter_declarations(resp.declarations or []):
                if d.name == "sys_upttime" and d.state != "form":
                    offenders.append(f"{ep.id} response[{resp.status}] {d.path} state={d.state}")
    assert not offenders, "\n".join(offenders)
