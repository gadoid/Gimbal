"""深层路径声明(D1-D3):name 别名制、通道形态边界、包含四格。
设计依据:docs/superpowers/specs/2026-09-03-deep-path-declarations-design.md"""
import pytest
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, RequestSpec

_SCHEMA = {"type": "object", "properties": {}}

def _build(*entries):
    return RequestSpec(body_type="json", schema=_SCHEMA,
                       declarations=list(entries))

def _decl(**kw):
    base = dict(name="x", path="$.x", channel="binding")
    base.update(kw)
    return DeclarationEntry(**base)

# ── D1 别名制 ─────────────────────────────────────────────
def test_alias_name_accepted():
    """dispatch 原样案例:name≠末段 通过(name=显示别名,path=寻址真源)。"""
    _build(
        _decl(name="supplier_id", path="$.supplier[0].order_supplier_id"),
        _decl(name="order_id_relate_supplier", path="$.supplier[0].order_id"),
        _decl(name="order_id", path="$.order_id"),
    )

def test_duplicate_name_rejected():
    with pytest.raises(ValueError, match="重复 name"):
        _build(_decl(name="order_id", path="$.order_id"),
               _decl(name="order_id", path="$.supplier[0].order_id"))

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
    DeclarationEntry(name="$", path="$", channel="view_only")

# ── D2 通道形态(spec 级:_check_declarations;brief 勘误:两条拒绝用例
#    需 _build() 包裹 — 通道形态校验在清单级,裸 DeclarationEntry 不经过) ──
def test_carry_deep_index_rejected():
    with pytest.raises(ValueError, match="carry 通道 path"):
        _build(_decl(name="x", path="$.supplier[0].order_supplier_id",
                     channel="carry", type="string"))

def test_carry_dot_nested_accepted():
    # spec 级钉子(评审 R2):carry 多 FIELD 段在清单校验层放行不回归
    _build(_decl(name="b", path="$.a.b", channel="carry", type="string"))

def test_binding_wildcard_rejected():
    with pytest.raises(ValueError, match="具体路径"):
        _build(_decl(name="sku", path="$.supplier[*].order_supplier_id"))

def test_binding_deep_index_accepted():
    # spec 级钉子(评审 R2):binding 深下标在清单校验层放行不回归
    _build(_decl(name="sku0", path="$.supplier[0].order_supplier_id"))

# ── D3 包含四格 ───────────────────────────────────────────
def test_carry_contains_binding_ok():
    """dispatch 主案例:carry 容器 + binding 深层叶子 = 分层覆写。"""
    _build(_decl(name="supplier", path="$.supplier", channel="carry", type="array"),
           _decl(name="supplier_id", path="$.supplier[0].order_supplier_id"))

def test_carry_contains_carry_rejected():
    with pytest.raises(ValueError, match="carry 声明不允许嵌套"):
        _build(_decl(name="supplier", path="$.supplier", channel="carry", type="array"),
               _decl(name="leaf", path="$.supplier.x", channel="carry", type="string"))

def test_binding_contains_binding_ok():
    _build(_decl(name="cfg", path="$.cfg", ui_kind="json"),
           _decl(name="timeout", path="$.cfg.timeout"))

def test_binding_contains_carry_rejected():
    with pytest.raises(ValueError, match="binding 容器内不允许 carry"):
        _build(_decl(name="cfg", path="$.cfg", ui_kind="json"),
               _decl(name="owner", path="$.cfg.owner", channel="carry", type="string"))
