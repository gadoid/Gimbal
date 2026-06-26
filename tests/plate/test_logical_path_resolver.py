"""PR-D1:逻辑 schema 路径解析器测试。

业务动机:91% 真值血缘路径穿过 list(PLATE_DESIGN §2.2)。
解析器必须能"透明穿过 ``list[X]`` / ``dict[str, V]`` / ``Optional[T]``",
否则 PR-D2 ``FieldBinding`` 静态校验全失效。

每个测试对应**一个解析规则的边界 case**,docstring 写明:
  1. 业务需求(透明穿越 list/dict 的契约)
  2. 对应设计章节(§2.2 表格行)
  3. 业务影响(破坏此规则 = 91% 真值血缘不可校验)
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Union

import pytest
from pydantic import BaseModel

from Plate.path_resolver import Resolved, resolve_logical_path


# ════════════════════════════════════════════════════════════════════════════
# 基础:空路径、简单字段、嵌套
# ════════════════════════════════════════════════════════════════════════════


def test_empty_path_resolves_to_root() -> None:
    """业务需求:空路径解析为根类型。

    对应设计:§2.2 路径格式"空字符串 = 解析根类型本身"。
    业务影响:任何调用方期望"传 '' 得到 root"的语义破坏,基础契约失守。
    """
    class M(BaseModel):
        x: str = ""

    resolved = resolve_logical_path(M, "")
    assert resolved.target_type is M
    assert resolved.hit_any is False
    assert resolved.error is None


def test_simple_field() -> None:
    """业务需求:解析单层字段,返回字段类型。

    对应设计:§3.4(d) 解析器须进入 BaseModel 字段。
    业务影响:基本功能,1 行 case 必须对。
    """
    class M(BaseModel):
        x: str = ""

    resolved = resolve_logical_path(M, "x")
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


def test_nested_3_levels() -> None:
    """业务需求:解析 3 层嵌套字段。

    对应设计:§3.4(d) 解析器递归。
    业务影响:基本功能,确保递归不丢层。
    """
    class Leaf(BaseModel):
        val: int = 0

    class Mid(BaseModel):
        leaf: Leaf = Leaf()

    class Root(BaseModel):
        mid: Mid = Mid()

    resolved = resolve_logical_path(Root, "mid.leaf.val")
    assert resolved.target_type is int
    assert resolved.hit_any is False
    assert resolved.error is None


# ════════════════════════════════════════════════════════════════════════════
# 透明穿越 list / dict / Optional(§2.2 核心规则)
# ════════════════════════════════════════════════════════════════════════════


def test_path_transparently_passes_through_list() -> None:
    """业务需求:``list[X]`` 透明穿越,返回 X 类型(不带下标)。

    对应设计:§2.2 表格"取哪个元素 → scenario 决定,Plate 不固化下标"。
    业务影响:91% 真值血缘穿过 list,不透明穿越 = 91% binding 不可校验。
    """
    class Item(BaseModel):
        order_id: str = ""

    class Container(BaseModel):
        items: List[Item] = []

    resolved = resolve_logical_path(Container, "items.order_id")
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


def test_path_transparently_passes_through_dict() -> None:
    """业务需求:``dict[str, V]`` 透明穿越,返回 V 类型(不带具体键)。

    对应设计:§2.2 表格"键的语义 → field_notes / model description,Plate 不固化键"。
    业务影响:``main_currency_bank.CNY[0]`` 之类路径必须能解析到 V。
    """
    class Block(BaseModel):
        bank_account: str = ""

    class Container(BaseModel):
        main_currency_bank: Dict[str, Block] = {}

    resolved = resolve_logical_path(Container, "main_currency_bank.bank_account")
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


def test_path_passes_through_4_layers_including_2_lists() -> None:
    """业务需求:4 层嵌套(含 2 层 list)能完整解析(终点是 Any → 软降级)。

    对应设计:§2.2 端到端示例
              ``"data.to_customer.put_amount.standard_list.order_fee_real_id"``。
    业务影响:真实场景核心 case;破坏 = 关键 binding 全部无法校验。
    注:实际 ToggleRealAmountData 的 ``MoneyBlock.standard_list: list[Any]`` 是
        permissive 表达(permissive 字段),所以路径末段落在 Any 区域 → 软降级。
        这是设计 §2.2 Any 限制的**预期行为**,不是 bug。
    """
    class Item(BaseModel):
        order_fee_real_id: str = ""

    class Amount(BaseModel):
        standard_list: List[Item] = []

    class ToSide(BaseModel):
        put_amount: Amount = Amount()

    class ToggleData(BaseModel):
        to_customer: List[ToSide] = []

    # 严格 4 层 list 嵌套(都精确建模):解析到 str
    resolved = resolve_logical_path(
        ToggleData,
        "to_customer.put_amount.standard_list.order_fee_real_id",
    )
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None

    # 同样路径,但把 standard_list 换成 list[Any](permissive 兜底):
    # 落在 Any 区域 → 软降级(target_type=None, hit_any=True)
    class PermissiveAmount(BaseModel):
        standard_list: List[Any] = []

    class PermissiveToggleData(BaseModel):
        to_customer: List[ToSide] = []
        amount: PermissiveAmount = PermissiveAmount()

    resolved_any = resolve_logical_path(
        PermissiveToggleData,
        "amount.standard_list.order_fee_real_id",
    )
    assert resolved_any.hit_any is True
    assert resolved_any.target_type is None
    assert resolved_any.error is None  # 软提示


def test_path_passes_through_optional() -> None:
    """业务需求:``Optional[T]`` 透明穿越,返回 T 类型。

    对应设计:§2.2 表格"``Optional[T]`` → 进入 T"。
    业务影响:多数 fin 字段是 ``str | None = None``,不透明穿越 = 多数 binding 失败。
    """
    class M(BaseModel):
        order_id: Optional[str] = None

    resolved = resolve_logical_path(M, "order_id")
    # Optional[str] 解析后是 str(Union[T, None] 简化为 T)
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


def test_path_passes_through_optional_with_pipe_syntax() -> None:
    """业务需求:``T | None``(PEP 604)透明穿越,返回 T 类型。

    对应设计:§2.2 表格 + Python 3.10+ PEP 604 兼容。
    业务影响:实际代码大量使用 ``str | None``(比 ``Optional[str]`` 更简洁),
             不支持 = 大量 binding 解析失败。
    """
    class M(BaseModel):
        order_id: str | None = None

    resolved = resolve_logical_path(M, "order_id")
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


def test_path_passes_through_annotated() -> None:
    """业务需求:``Annotated[T, ...]`` 透明取 T。

    对应设计:Pydantic v2 + typing 兼容。
    业务影响:Annotated 大量用于 ``Field(..., description=...)``。
    """
    class M(BaseModel):
        order_id: Annotated[str, "description=订单号"] = ""

    resolved = resolve_logical_path(M, "order_id")
    assert resolved.target_type is str
    assert resolved.hit_any is False
    assert resolved.error is None


# ════════════════════════════════════════════════════════════════════════════
# Any 降级(§2.2 限制 + §5.3 表格)
# ════════════════════════════════════════════════════════════════════════════


def test_path_entering_any_is_soft_fail() -> None:
    """业务需求:路径终点是 Any 时,标记 ``hit_any=True``,不报错。

    对应设计:§2.2 Any 限制 + §5.3 表格"Any 区域降级为软提示"。
    业务影响:fin 的 ``CommonResponseEnvelope.data: Any`` 几乎覆盖所有
             ``source_field_path``,不降级 = 所有跨端点 binding 不可校验。
    """
    class Envelope(BaseModel):
        data: Any = None

    resolved = resolve_logical_path(Envelope, "data.order_id")
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None  # 软提示,不是 error


def test_path_passing_through_any_is_soft_fail() -> None:
    """业务需求:路径穿过 Any 字段后再有子路径,也按 ``hit_any=True`` 处理。

    对应设计:§2.2 Any 限制。
    业务影响:同 ``test_path_entering_any_is_soft_fail``,中间 Any 也算。
    """
    class Container(BaseModel):
        data: Any = None

    resolved = resolve_logical_path(Container, "data.sub.field")
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


def test_path_to_any_field_directly_is_soft_fail() -> None:
    """业务需求:路径直接落到 ``Any`` 字段(如 ``"data"``),也按 ``hit_any=True`` 处理。

    对应设计:§2.2 Any 限制。
    业务影响:``envelope.data`` 路径直接给消费者"我知道这里是 Any"的语义,
             便于 binding 校验报告降级。
    """
    class Envelope(BaseModel):
        data: Any = None

    resolved = resolve_logical_path(Envelope, "data")
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


# ════════════════════════════════════════════════════════════════════════════
# 硬错误拒绝
# ════════════════════════════════════════════════════════════════════════════


def test_nonexistent_field_returns_error() -> None:
    """业务需求:字段名拼错时返回 error(不是 hit_any)。

    对应设计:§3.4(d) 解析器须报"字段不存在"。
    业务影响:FieldBinding 拼错路径 = CI fail,防止"指向不存在字段的假 binding"。
    """
    class M(BaseModel):
        order_id: str = ""

    resolved = resolve_logical_path(M, "ordr_id")  # typo
    assert resolved.error is not None
    assert "ordr_id" in resolved.error
    assert resolved.hit_any is False
    assert resolved.target_type is None


def test_polymorphic_union_rejected() -> None:
    """业务需求:``Union[A, B]``(非 Optional)多态路径不可静态选,返回原 annotation。

    对应设计:§2.2 表格"``Union[A, B]`` 不支持"。
    业务影响:多态路径不可静态选,只能走 scenario 动态选择。
              解析器对多态 Union **原样返回**(不报错但 target_type 是 Union 类型,
              由 PR-D2 FieldBinding 校验时识别并拒绝)。
    """
    class M(BaseModel):
        item: Union[int, str] = 0  # 多态,非 Optional

    resolved = resolve_logical_path(M, "item")
    # 多态 Union 不被简化(只有 Optional[T, None] 才被简化) → 原样返回
    # 实际语义:target_type 是 Union[int, str],需要 PR-D2 在 binding 校验时识别
    import typing
    origin = typing.get_origin(resolved.target_type)
    assert origin is Union, (
        f"多态 Union 应原样返回(get_origin=Union),实际 {resolved.target_type!r}"
    )


def test_descend_into_scalar_returns_error() -> None:
    """业务需求:路径进入标量(int/str)后再有子路径,返回 error。

    对应设计:§3.4(d) 解析器期望 BaseModel 节点。
    业务影响:路径拼错(如 ``order_id.sub``)应被发现。
    """
    class M(BaseModel):
        order_id: str = ""

    resolved = resolve_logical_path(M, "order_id.sub")
    assert resolved.error is not None
    assert resolved.hit_any is False
    assert resolved.target_type is None


# ════════════════════════════════════════════════════════════════════════════
# 真实 fin 端点样本(端到端)
# ════════════════════════════════════════════════════════════════════════════


def test_resolves_fin_toggle_real_amount_real_id() -> None:
    """业务需求:能解析 fin.toggleRealAmount 的 order_fee_real_id 路径(Any 软降级)。

    对应设计:§2.2 端到端示例
              ``"to_customer.put_amount.standard_list.order_fee_real_id"``。
    业务影响:realAmountLockSubmit 的 binding 依赖此解析。
    注:``MoneyBlock.standard_list: list[Any]``(permissive 兜底)使路径落在 Any
        区域 → 软降级(hit_any=True);**不是** strict 解析失败。
        这正是 §2.2 Any 限制的设计意图(无法证伪就放行,让 L2 review 处理)。
    """
    from Plate.fin.models import ToggleRealAmountData

    resolved = resolve_logical_path(
        ToggleRealAmountData,
        "to_customer.put_amount.standard_list.order_fee_real_id",
    )
    # 实际:ToggleRealAmountData → to_customer (list[_SettleSideItem]) → unwrap
    # → _SettleSideItem → put_amount (_MoneyBlock) → standard_list (list[Any])
    # → 命中 Any → hit_any=True
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


def test_resolves_fin_toggle_real_amount_amount_summary() -> None:
    """业务需求:能解析 fin.toggleRealAmount 的 amount_summary.order_id(精确建模)。

    对应设计:§2.2 + §3.4(d) 路径解析器透明穿 Optional。
    业务影响:demonstrates "stricter" end-to-end case(toggle 里有精确建模的字段)。
    """
    from Plate.fin.models import ToggleRealAmountData

    resolved = resolve_logical_path(ToggleRealAmountData, "amount_summary.order_id")
    # amount_summary 是 _AmountSummary(BaseModel,精确建模)→ unwrap Optional
    # → _AmountSummary.order_id (str) → strict 解析成功
    assert resolved.hit_any is False
    assert resolved.target_type is str
    assert resolved.error is None


def test_resolves_fin_order_confirm_account_main_currency_bank() -> None:
    """业务需求:能解析 fin.orderConfirmAccount 的 main_currency_bank 路径(Any 软降级)。

    对应设计:§2.2 main_currency_bank.CNY[0].bank_account 案例。
    业务影响:orderReceiveAccountEdit 的 binding 依赖此解析。
    注:``OrderConfirmAccountData.main_currency_bank: Any``(permissive 兜底)
        → 命中 Any → hit_any=True。
    """
    from Plate.fin.models import OrderConfirmAccountData

    resolved = resolve_logical_path(
        OrderConfirmAccountData,
        "main_currency_bank.bank_account",
    )
    assert resolved.hit_any is True
    assert resolved.target_type is None
    assert resolved.error is None


def test_resolves_fin_audit_page_data_audit_id() -> None:
    """业务需求:能解析 fin.auditPage 的 data.audit_id 路径(精确建模)。

    对应设计:§2.2 简例"data[0].audit_id"。
    业务影响:auditDetail / auditExecute 的 binding 依赖此解析。
    """
    from Plate.fin.models import AuditPageData

    resolved = resolve_logical_path(
        AuditPageData,
        "data.audit_id",
    )
    # AuditPageData.data: list[_AuditPageItem] → unwrap → _AuditPageItem
    # → audit_id: str | None → unwrap Optional → str
    assert resolved.hit_any is False
    assert resolved.target_type is str
    assert resolved.error is None


# ════════════════════════════════════════════════════════════════════════════
# 边界:Result dataclass 行为
# ════════════════════════════════════════════════════════════════════════════


def test_resolved_is_frozen() -> None:
    """业务需求:``Resolved`` 是 frozen dataclass(不可变 — 解析结果是事实)。

    对应设计:frozen dataclass 标准实践。
    业务影响:解析结果作为契约证据,被多处共享;可变 = 风险(误改破坏一致性)。
    """
    r = Resolved(target_type=str, hit_any=False, path="x", error=None)
    with pytest.raises((AttributeError, TypeError)):
        r.path = "y"  # type: ignore[misc]


def test_resolved_state_space_exhaustive() -> None:
    """业务需求:``Resolved`` 状态空间有 3 个互斥分支(成功 / Any 软降级 / 硬错)。

    对应设计:本模块 docstring 状态空间表。
    业务影响:状态空间漏分支 = 上层 (PR-D2 binding 校验)逻辑出错。
    """
    from Plate.fin.models import AuditPageData, CommonResponseEnvelope

    # 1. 成功
    r1 = resolve_logical_path(AuditPageData, "data.audit_id")
    assert r1.target_type is not None and not r1.hit_any and r1.error is None
    # 2. Any 软降级
    r2 = resolve_logical_path(CommonResponseEnvelope, "data.sub")
    assert r2.target_type is None and r2.hit_any and r2.error is None
    # 3. 硬错
    r3 = resolve_logical_path(AuditPageData, "nonexistent")
    assert r3.target_type is None and not r3.hit_any and r3.error is not None


# ════════════════════════════════════════════════════════════════════════════
# 边界:路径是基本类型(field 不存在 vs path 是空字符串)
# ════════════════════════════════════════════════════════════════════════════


def test_path_with_only_dots_is_treated_as_explicit_empty_segments() -> None:
    """业务需求:``.``/``.x``/``x.`` 等边界 — 视为"空字段名",返回字段不存在错。

    对应设计:§3.4(d) 解析器逐段 ``model_fields`` 查找,空段不可能存在。
    业务影响:边界 case 行为统一,不出现"路径诡异但侥幸解析成功"。
    """
    class M(BaseModel):
        x: str = ""

    # 末段为空 → 字段名 "" 不在 model_fields
    r = resolve_logical_path(M, "x.")
    assert r.error is not None
    # 首段为空 → 字段名 "" 不在 model_fields
    r = resolve_logical_path(M, ".x")
    assert r.error is not None


def test_descend_into_optional_scalar_via_pipe_returns_error() -> None:
    """业务需求:对 ``str | None`` 字段再做子路径(``"order_id.sub"``)→ error。

    对应设计:§3.4(d) 解析器透明解 Optional 后期望 BaseModel。
    业务影响:``str | None`` 解 Optional 后是 ``str``,再 descend → 期望 BaseModel
             失败 → 报"路径期望 BaseModel,实际 type"——明确告诉调用方"这字段
             已经到叶子,不能继续走子路径"。
    """
    class M(BaseModel):
        order_id: str | None = None

    r = resolve_logical_path(M, "order_id.sub")
    assert r.error is not None
    assert r.hit_any is False
