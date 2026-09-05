"""深层路径声明:2026-09-05 目录化后的存活钉子。

原 2026-09-03 设计(D2 通道形态边界 / D3 包含四格)随 channel 退役:
- D2 的 carry 深下标拒/binding 深下标放行 → 模板纪律继任(children 子树
  FIELD-only,顶层条目路径自由 — 全量用例见 test_field_state_catalog.py);
- D3 四格 → 整传一致性单规则继任(carry 容器 ⇒ 子孙 carry,经 children
  树表达,不再有平铺兄弟包含判定)。

本文件保留:D1 name 别名制边界(标识符/唯一性/根 $ 惯例)— 它们
不依赖通道轴,目录化后原样存活。
"""
import pytest
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, RequestSpec


def _build(*entries):
    return RequestSpec(body_type="json", declarations=list(entries))


def _decl(**kw):
    base = dict(name="x", path="$.x", type="string")
    base.update(kw)
    return DeclarationEntry(**base)


# ── D1 别名制(存活)─────────────────────────────────────
def test_alias_name_accepted():
    """name≠末段 通过(name=显示别名,path=寻址真源)。"""
    _build(
        _decl(name="supplier_id", path="$.supplier.order_supplier_id"),
        _decl(name="order_id_relate_supplier", path="$.supplier.order_id"),
        _decl(name="order_id", path="$.order_id"),
    )


def test_duplicate_name_rejected():
    with pytest.raises(ValueError, match="重复 name"):
        _build(_decl(name="order_id", path="$.order_id"),
               _decl(name="order_id", path="$.supplier.order_id"))


def test_non_identifier_name_rejected():
    with pytest.raises(ValueError, match="标识符"):
        _decl(name="订单ID", path="$.order_id")


def test_trailing_newline_name_rejected():
    # 评审 R2 finding 2:`$` 锚会放行尾部换行(re.match("x\n") 为真),
    # name 作前端键不安全 — 改 `\Z` 锚收紧(brief 原文正则的有意偏离)。
    with pytest.raises(ValueError, match="标识符"):
        _decl(name="x\n", path="$.x")


def test_root_entry_name_dollar_convention_accepted():
    """根路径条目 name='$' 为 spec §3.1 既有惯例,D1 标识符规则放行特例。"""
    DeclarationEntry(name="$", path="$", type='string')


# ── 旧 D3 → 整传一致性(children 树表达)──────────────────
def test_carry_container_children_must_carry():
    """carry 容器的子孙必须 carry(整传一致性,单规则取代旧四格)。"""
    with pytest.raises(ValueError, match="整传|carry"):
        _build(_decl(name="supplier", path="$.supplier", type="array",
                     state="carry",
                     children=[dict(name="sid", path="$.supplier.sid",
                                    type="string")]))


def test_carry_container_carry_children_ok():
    _build(_decl(name="supplier", path="$.supplier", type="array",
                 state="carry",
                 children=[dict(name="sid", path="$.supplier.sid",
                                type="string", state="carry")]))


def test_form_container_mixed_children_ok():
    """form/collapse 容器子孙状态自由(整传一致性只约束 carry 容器)。"""
    _build(_decl(name="cfg", path="$.cfg", type="object",
                 children=[
                     dict(name="timeout", path="$.cfg.timeout",
                          type="string"),
                     dict(name="owner", path="$.cfg.owner",
                          type="string", state="carry"),
                 ]))
