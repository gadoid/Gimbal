"""hash golden 测试（A1 首交付物之二，7.1 / 7.2 / 修订九）。

锁死:
1. golden:样本对象的 object_hash / shape_hash 钉死在 fixture(漂移必须
   diff 可见,意识性重钉);
2. P8 属性:新增带默认值的字段不改变未使用它的对象的 hash
   (exclude_defaults 序列化纪律——防适配风暴与跨版本去重失效);
3. shape_hash 只看形状:改 description / capability / metadata /
   consumes 不变;改 binding / 声明树必变;responses 键序无关。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.dialect import (
    EndpointSpec,
    HttpBinding,
    RequestSpec,
    ResponseSpec,
    object_hash,
    parse_markdown,
    render,
    shape_hash,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry

from ._samples import ENDPOINTS_SAMPLE

FIXTURE = Path(__file__).parent / "fixtures" / "dialect_hash_golden.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))


def _sample_endpoint(**overrides) -> EndpointSpec:
    base = dict(
        id="fin.order.order_add",
        system="fin",
        service="fin-service",
        name="委托订舱下单",
        capability="cap:order.create",
        binding=HttpBinding(method="POST", path="/api/order/order/orderAdd",
                            auth="bearer"),
        request=RequestSpec(declarations=[
            DeclarationEntry(name="bl_no", path="$.bl_no", type="string",
                             required=True),
        ]),
        responses={
            "200": ResponseSpec(description="下单成功", declarations=[
                DeclarationEntry(name="order_id", path="$.data.order_id",
                                 type="string"),
            ]),
            "409": ResponseSpec(description="重复下单"),
        },
    )
    base.update(overrides)
    return EndpointSpec.model_validate(base)


def _hash_table() -> dict[str, dict[str, str]]:
    ep = _sample_endpoint()
    no_defaults = _sample_endpoint(capability=None, responses={"200": ResponseSpec()})
    from ._samples import PRD_SAMPLE

    parsed = parse_markdown(ENDPOINTS_SAMPLE)
    doc_ep = parsed.blocks("endpoint")[0].payload
    # PRD 样本里的两个片段对象
    prd = parse_markdown(PRD_SAMPLE)
    stmts = prd.statements()

    table: dict[str, dict[str, str]] = {
        "fin.order.order_add": {
            "object_hash": object_hash(ep),
            "shape_hash": shape_hash(ep),
        },
        "bare_no_defaults": {
            "object_hash": object_hash(no_defaults),
            "shape_hash": shape_hash(no_defaults),
        },
        "doc.platform.user.update": {
            "object_hash": object_hash(doc_ep),
            "shape_hash": shape_hash(doc_ep),
        },
    }
    for s in stmts:
        table[f"statement:{s.id}"] = {"object_hash": object_hash(s)}
    return table


def test_hash_golden() -> None:
    """golden:hash 钉死;漂移 = 红(除非经评审重钉)。"""
    live = _hash_table()
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(
            json.dumps(live, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8",
        )
        pytest.skip("dialect hash golden captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert live == base, "dialect hash 漂移(规范序列化纪律被破坏?)"


def test_p8_additive_field_keeps_hash() -> None:
    """P8 属性:加一个带默认值的新字段,未使用它的对象 hash 不变。

    模拟 M2 演进(如将来给 EndpointSpec 加 `deprecated_at: str | None`)。
    """

    class EndpointSpecVNext(EndpointSpec):
        model_config = ConfigDict(extra="forbid")

        deprecated_at: str | None = None
        retry_budget: int = 3

    ep = _sample_endpoint()
    ep_next = EndpointSpecVNext.model_validate(ep.model_dump())
    assert ep_next.deprecated_at is None and ep_next.retry_budget == 3
    assert object_hash(ep_next) == object_hash(ep), (
        "P8 加法演进破坏 hash 稳定性:新增默认字段改变了未使用它的对象"
    )


def test_shape_hash_ignores_semantic_fields() -> None:
    """语义标注不触发适配:改 capability / description / metadata / consumes
    / query_safe 标志,shape_hash 不变。"""
    ep = _sample_endpoint()
    base = shape_hash(ep)
    annotated = _sample_endpoint(
        capability="cap:order.place",
        description="完全不同的描述",
        consumes=["attr:order.period"],
        produces=["outcome:order.created"],
    )
    annotated.metadata = annotated.metadata.model_copy(
        update={"module": "other", "query_safe": True, "priority": 1}
    )
    assert shape_hash(annotated) == base


def test_shape_hash_tracks_shape_changes() -> None:
    """binding / 声明树变化必变;responses 键序无关。"""
    base = shape_hash(_sample_endpoint())
    assert shape_hash(_sample_endpoint(binding=HttpBinding(
        method="POST", path="/api/order/order/orderAddV2"))) != base
    assert shape_hash(_sample_endpoint(request=RequestSpec(declarations=[
        DeclarationEntry(name="bl_no", path="$.bl_no", type="string",
                         required=True),
        DeclarationEntry(name="container", path="$.container", type="object"),
    ]))) != base
    assert shape_hash(_sample_endpoint(responses={
        "409": ResponseSpec(description="重复下单"),
        "200": ResponseSpec(description="下单成功", declarations=[
            DeclarationEntry(name="order_id", path="$.data.order_id",
                             type="string"),
        ]),
    })) == base, "responses 声明序不应影响 shape_hash"


def test_p8_nested_model_defaults_keeps_hashes() -> None:
    """P8 扩展(评审 P0-7):嵌套模型(Binding)加默认字段,hash 不变。"""

    class BindingVNext(HttpBinding.__class__):
        pass

    # 直接构造:给 binding 显式写默认值 vs 不写 —— object/shape 全等
    ep_min = _sample_endpoint()
    ep_explicit = _sample_endpoint(binding=HttpBinding(
        method="POST", path="/api/order/order/orderAdd", auth="bearer",
        timeout_seconds=30.0, body_type="json", headers={},
    ))
    assert object_hash(ep_explicit) == object_hash(ep_min)
    assert shape_hash(ep_explicit) == shape_hash(ep_min)


def test_dict_key_order_irrelevant() -> None:
    """评审 P0-8:responses/headers 书写序不产生不同 hash。"""
    ep_a = _sample_endpoint(responses={
        "200": ResponseSpec(declarations=[
            DeclarationEntry(name="order_id", path="$.data.order_id", type="string")]),
        "409": ResponseSpec(description="dup"),
    })
    ep_b = _sample_endpoint(responses={
        "409": ResponseSpec(description="dup"),
        "200": ResponseSpec(declarations=[
            DeclarationEntry(name="order_id", path="$.data.order_id", type="string")]),
    })
    assert object_hash(ep_a) == object_hash(ep_b)
    assert shape_hash(ep_a) == shape_hash(ep_b)


def test_shape_excludes_decl_presentational_fields() -> None:
    """评审 P0-11:description/ui_kind 改动不改 shape;default/example 改动改。"""
    ep = _sample_endpoint()
    base = shape_hash(ep)
    desc_changed = _sample_endpoint(request=RequestSpec(declarations=[
        DeclarationEntry(name="bl_no", path="$.bl_no", type="string",
                         required=True, description="改了", ui_kind="textarea"),
    ]))
    assert shape_hash(desc_changed) == base, "description/ui_kind 不应进 shape"
    value_changed = _sample_endpoint(request=RequestSpec(declarations=[
        DeclarationEntry(name="bl_no", path="$.bl_no", type="string",
                         required=True, default="BL-001"),
    ]))
    assert shape_hash(value_changed) != base, "default 影响用例取值,应进 shape"


def test_canonical_excludes_defaults() -> None:
    """规范序列化排除默认值:显式写出的默认 == 缺省(语义等价,hash 相同)。"""
    explicit = _sample_endpoint(binding=HttpBinding(
        method="POST", path="/api/order/order/orderAdd", auth="bearer",
        timeout_seconds=30.0, body_type="json", headers={},
    ))
    assert object_hash(explicit) == object_hash(_sample_endpoint())
    # render 同一纪律:规范形不含默认值键
    d = parse_markdown(ENDPOINTS_SAMPLE)
    rendered = render(d)
    assert "timeout_seconds" not in rendered, "默认值 30.0 不应出现在规范形"
    assert "body_type" not in rendered, "默认值 json 不应出现在规范形"
