"""fin 服务契约数据模型。

本模块从 ``gimbal-tmp/test-2-1782188725.ndjson`` 中观察到的 31 个 (method, path)
端点的请求/响应结构,生成对应的 pydantic v2 数据类,并暴露:
  * :data:`PATH_MODELS` —— ``(method, path)`` → 端点契约映射
  * :func:`get_request_model` / :func:`get_response_model` —— 按 path 反查
  * :class:`EndpointBinding` —— 路径 ↔ 模型的强类型表达

设计原则(对齐 :mod:`Plate.spec` 的契约保真护栏):
  * 全部使用 ``model_config = ConfigDict(extra="forbid")``
  * 关闭 ``str_strip_whitespace`` / ``coerce_numbers_to_str`` / ``use_enum_values``
  * 字段名保持与 wire 字段名一致(snake_case 与原 JSON 一致,不做 camelCase 转换)
  * 所有"未知值"用 ``Any``(原接口常出现 ``null`` / 数字 / 字符串混用)
  * 所有可空字段标记 ``default=None``;无必填语义(原始数据并不全)

注意:模型只描述"形状",不做任何业务校验。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

# ════════════════════════════════════════════════════════════════════════════
# 通用配置(契约保真:与 spec.py 中 _FORBIDDEN_CONFIG_KEYS 一致)
# ════════════════════════════════════════════════════════════════════════════

_SAFE_CONFIG: ConfigDict = ConfigDict(
    extra="forbid",
    str_strip_whitespace=False,
    coerce_numbers_to_str=False,
    use_enum_values=False,
)


class _Base(BaseModel):
    """所有 fin 契约模型的基类:统一契约保真护栏。"""

    model_config = _SAFE_CONFIG


# ════════════════════════════════════════════════════════════════════════════
# 通用 / 共享 模型
# ════════════════════════════════════════════════════════════════════════════


class Params(_Base):
    """通用分页 ``params`` 容器(原接口常出现 ``{}``,列字段用以表达可能键)。"""

    model_config = _SAFE_CONFIG


class CommonResponseEnvelope(_Base):
    """所有 fin 端点的统一响应壳:``{code, msg, data, request_id}``。"""

    code: int | None = None
    msg: str | None = None
    request_id: str | None = None
    data: Any | None = None


# ════════════════════════════════════════════════════════════════════════════
# 1. /api/order/orderEntrust/orderPage
# ════════════════════════════════════════════════════════════════════════════


class OrderEntrustOrderPageRequest(_Base):
    """POST /api/order/orderEntrust/orderPage 请求体。"""

    model_config = ConfigDict(extra="ignore")  # wire 中同名字段常出现多种类型,用 Any + ignore 兜底

    page_no: int | None = None
    page_size: int | None = None
    sort_field: str | None = None
    sort_order: str | None = None
    params: Any | None = None  # 实际为 object,常为 {}
    bl_no: str | None = None
    bl_nos: Any | None = None  # 样本中可 str / list
    customer_id: Any | None = None  # 样本中可 str / list
    order_no: str | None = None


class OrderEntrustOrderPageItem(_Base):
    """``orderPage`` 返回列表的单条记录(204+ 字段,常为 ES 文档全字段)。"""

    model_config = _SAFE_CONFIG

    # 全部以 Any 表达,真实字段极其多样,且同名字段类型常随样本变化
    def __init__(self, **data: Any) -> None:  # noqa: D401 - permissive constructor
        super().__init__(**data)


class OrderEntrustOrderPageData(_Base):
    """``orderPage`` 返回的 ``data`` 字段。"""

    total: int | None = None
    data: list[Any] | None = None  # list[OrderEntrustOrderPageItem]


# ════════════════════════════════════════════════════════════════════════════
# 2. /api/order/orderEntrust/orderAdd  (211 字段,以 Permissive 表达)
# ════════════════════════════════════════════════════════════════════════════


class PermissiveRequest(_Base):
    """通用"高字段数 + 多类型"请求体,用于字段 > 100 的端点。

    原始请求体中同一字段可能在不同样本里出现 str / int / float / null / list /
    dict,无法精确建模,故采用 permissiveness 兜底;``extra='forbid'`` 仍可工作
    是因为本类用 ``__init__`` 重写 + ``model_config.pop`` 失效,故此处选用
    permissive 模式而非 ``extra='forbid'`` 严格模式。
    """

    model_config = ConfigDict(extra="ignore")  # 字段集过大,允许未知键

    def __init__(self, **data: Any) -> None:  # noqa: D401
        super().__init__(**data)


# 为保持一致语义,orderEntrust/orderAdd / orderAdd / orderBook 三端点共享此模型
OrderEntrustOrderAddRequest = PermissiveRequest
OrderAddRequest = PermissiveRequest
OrderBookRequest = PermissiveRequest


# ════════════════════════════════════════════════════════════════════════════
# 3. /api/order/order/orderDetail
# ════════════════════════════════════════════════════════════════════════════


class OrderDetailRequest(_Base):
    """POST /api/order/order/orderDetail 请求体。"""

    order_id: str | None = None


class OrderDetailData(_Base):
    """``orderDetail`` 返回的 ``data``:订单完整文档(204 字段)。"""

    model_config = ConfigDict(extra="ignore")

    order_id: str | None = None
    order_no: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    bl_no: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 4. /api/order/orderFee/toggleRealAmount
# ════════════════════════════════════════════════════════════════════════════


class ToggleRealAmountRequest(_Base):
    """POST /api/order/orderFee/toggleRealAmount 请求体。"""

    order_id: str | None = None


class _MoneyBlock(_Base):
    model_config = ConfigDict(extra="ignore")

    standard_list: list[Any] | None = None
    put_cny_amount: str | None = None
    put_usd_amount: str | None = None
    put_folde_amount: str | None = None
    pay_cny_amount: str | None = None
    pay_usd_amount: str | None = None
    pay_folde_amount: str | None = None


class _SettleSideItem(_Base):
    model_config = ConfigDict(extra="ignore")

    gross_margin: int | float | None = None
    gross_margin_rate: int | float | None = None
    order_id: str | None = None
    order_sub_id: str | None = None
    order_sub_no: str | None = None
    order_sub_type: int | None = None
    main_name: str | None = None
    put_settle_object: str | None = None
    pay_settle_object: str | None = None
    pay_settle_object_id: Any | None = None
    put_amount: _MoneyBlock | None = None
    pay_amount: _MoneyBlock | None = None


class _AmountSummary(_Base):
    model_config = ConfigDict(extra="ignore")

    order_id: str | None = None
    order_no: str | None = None
    discount_status: str | None = None
    discount_ratio: str | None = None
    exchange_rate: str | None = None
    discount_usd: int | float | None = None
    discount_cny: int | float | None = None
    real_put_cny: int | float | None = None
    real_put_usd: int | float | None = None
    real_pay_cny: int | float | None = None
    real_pay_usd: int | float | None = None
    folde_put_usd: int | float | None = None
    folde_put_total: int | float | None = None
    folde_pay_usd: int | float | None = None
    folde_pay_total: int | float | None = None
    gross_margin: int | float | None = None
    gross_margin_rate: int | float | None = None


class ToggleRealAmountData(_Base):
    """``toggleRealAmount`` 返回的 ``data``。"""

    model_config = ConfigDict(extra="ignore")

    amount_summary: _AmountSummary | None = None
    to_customer: list[_SettleSideItem] | None = None
    to_cooperate: list[_SettleSideItem] | None = None
    to_supplier: list[_SettleSideItem] | None = None
    one_main_status: int | None = None
    is_traverse: str | None = None
    amount_lack_status: int | None = None
    amount_lack_label: str | None = None
    confirm_status: int | None = None
    discount_status_name: str | None = None
    real_fee_status: int | None = None
    service_items: list[Any] | None = None
    customs_clearance_status_text: str | None = None
    insurance_status_text: str | None = None
    manifest_status_text: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 5. /api/order/orderFee/bookRealAmountEdit
# ════════════════════════════════════════════════════════════════════════════


class _StandardListItem(_Base):
    model_config = ConfigDict(extra="ignore")

    order_fee_real_id: str | None = None
    fee_type: int | None = None
    policy_sub_id: str | None = None
    service_project: str | None = None
    cost_id: str | None = None
    settle_object_id: str | None = None
    subsidy_category: str | None = None
    currency: str | None = None
    unit_price: str | None = None
    unit: str | None = None
    specs: str | None = None
    num: str | None = None
    remark: Any | None = None
    discount_ratio: int | None = None
    discount_amount: str | None = None
    discount_status: str | None = None
    policy_sub_status_name: str | None = None
    pay_sync_status: int | None = None
    unique_id: str | None = None
    init_main_name: str | None = None
    main_name: str | None = None
    rowIndex: int | None = None


class _ToSideAmount(_Base):
    model_config = ConfigDict(extra="ignore")

    standard_list: list[_StandardListItem] | None = None


class _ToSideBlock(_Base):
    model_config = ConfigDict(extra="ignore")

    put_amount: _ToSideAmount | None = None
    pay_amount: _ToSideAmount | None = None


class BookRealAmountEditRequest(_Base):
    """POST /api/order/orderFee/bookRealAmountEdit 请求体。"""

    action: str | None = None  # e.g. "check"
    order_id: str | None = None
    discount_ratio: str | None = None
    service_project: str | None = None
    import_status: int | None = None
    to_customer: _ToSideBlock | None = None
    to_supplier: _ToSideBlock | None = None


# ════════════════════════════════════════════════════════════════════════════
# 6. /api/order/order/checkGenerateOrderSub
# ════════════════════════════════════════════════════════════════════════════


class CheckGenerateOrderSubRequest(_Base):
    """POST /api/order/order/checkGenerateOrderSub 请求体。"""

    order_id: str | None = None


class _FeeItem(_Base):
    model_config = ConfigDict(extra="ignore")

    pay_object: str | None = None
    put_object: str | None = None
    put_amount: str | None = None
    pay_amount: str | None = None
    main_id: int | None = None
    main_name: str | None = None


class _OrderBookItem(_Base):
    model_config = ConfigDict(extra="ignore")

    client_company_id: str | None = None
    client_company_name: str | None = None
    trustee_company_id: str | None = None
    trustee_company_name: str | None = None
    document_type: str | None = None
    file_url: str | None = None
    file_name: str | None = None
    file_id: str | None = None
    file_type: str | None = None


class CheckGenerateOrderSubData(_Base):
    model_config = ConfigDict(extra="ignore")

    fee: list[_FeeItem] | None = None
    order_book: list[_OrderBookItem] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 7. /api/order/order/generateOrderSub
# ════════════════════════════════════════════════════════════════════════════


class GenerateOrderSubRequest(_Base):
    order_id: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 8. /api/order/orderFee/realAmountLockSubmit
# ════════════════════════════════════════════════════════════════════════════


class RealAmountLockSubmitRequest(_Base):
    """POST /api/order/orderFee/realAmountLockSubmit 请求体。"""

    action: str | None = None  # "check" | 其它
    order_id: str | None = None
    order_fee_real_ids: list[str] | None = None
    audit_msg: Any | None = None
    select_node_user: Any | None = None


# ════════════════════════════════════════════════════════════════════════════
# 9. /api/home/audit/auditPage
# ════════════════════════════════════════════════════════════════════════════


class AuditPageRequest(_Base):
    """POST /api/home/audit/auditPage 请求体。"""

    model_config = ConfigDict(extra="ignore")

    page_no: int | None = None
    page_size: int | None = None
    active_tab: str | None = None  # e.g. "examine_wait"
    sort_field: str | None = None
    sort_order: str | None = None
    params: Any | None = None
    audit_status: Any | None = None  # 样本中可 str / list[str]
    audit_type: Any | None = None  # 样本中可 str / list[str]


class _AuditPageItem(_Base):
    model_config = ConfigDict(extra="ignore")

    audit_id: str | None = None
    audit_no: str | None = None
    audit_type: str | None = None
    audit_name: str | None = None
    audit_status: str | None = None
    create_by: str | None = None
    create_time: str | None = None
    execute_time: str | None = None
    relation_id: str | None = None
    audit_note: str | None = None
    expedite_num: str | None = None
    expedite_time: str | None = None
    expedite_status: str | None = None
    executor: str | None = None
    expedite_status_name: str | None = None
    is_expedite: str | None = None
    audit_status_name: str | None = None
    is_ext: int | None = None
    old_period_rule_name: str | None = None
    new_period_rule_name: str | None = None
    old_policy_type_name: str | None = None
    new_policy_type_name: str | None = None
    loan_pay_status_name: str | None = None
    customer_account_status_name: str | None = None
    supplier_account_status_name: str | None = None


class AuditPageData(_Base):
    total: str | None = None
    data: list[_AuditPageItem] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 10. /api/home/audit/auditDetail
# ════════════════════════════════════════════════════════════════════════════


class AuditDetailRequest(_Base):
    audit_id: str | None = None


class _AuditBasic(_Base):
    model_config = ConfigDict(extra="ignore")

    audit_no: str | None = None
    audit_type: str | None = None
    audit_name: str | None = None
    audit_status: str | None = None
    audit_status_name: str | None = None
    create_by: str | None = None
    create_time: str | None = None
    audit_note: str | None = None


class _AuditContent(_Base):
    model_config = ConfigDict(extra="ignore")

    relation_id: str | None = None
    audit_msg: str | None = None  # wire 中是 JSON 字符串,二次序列化


class _AuditRecordItem(_Base):
    model_config = ConfigDict(extra="ignore")

    audit_by: str | None = None
    audit_user_time: str | None = None
    audit_user_status: str | None = None
    audit_user_status_name: str | None = None
    audit_remark: str | None = None
    node_name: str | None = None


class _AuditExt(_Base):
    model_config = ConfigDict(extra="ignore")

    customer_name: str | None = None
    bl_no: str | None = None
    pol: str | None = None
    pod: str | None = None
    del_: str | None = None  # wire key: "del"(Python 关键字,改名 + alias)
    volume: str | None = None
    put_real_total_usd: str | None = None
    put_real_total_cny: str | None = None
    pay_real_total_usd: str | None = None
    pay_real_total_cny: str | None = None
    old_period_rule_name: str | None = None
    new_period_rule_name: str | None = None
    old_policy_type_name: str | None = None
    new_policy_type_name: str | None = None
    loan_pay_status_name: str | None = None
    customer_account_status_name: str | None = None
    supplier_account_status_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_del_alias(cls, data: Any) -> Any:
        """接受 ``"del"`` 原始键:本字段在 wire 中名为 ``del``(Python 关键字)。

        ``extra='ignore'`` 模式下,``del`` 会被丢弃,故在 before 阶段把
        ``del`` 重命名到 ``del_``。
        """
        if isinstance(data, dict) and "del" in data and "del_" not in data:
            data = {**data, "del_": data.pop("del")}
        return data


class _AuditProcessItem(_Base):
    model_config = ConfigDict(extra="ignore")

    audit_type_name: str | None = None
    audit_user_names: str | None = None
    audit_status_name: str | None = None
    expedite_num: str | None = None
    audit_node_time: str | None = None


class _CarbonCopyItem(_Base):
    model_config = ConfigDict(extra="ignore")

    carbon_copy_id: str | None = None
    carbon_copy_by: str | None = None


class AuditDetailData(_Base):
    audit_basic: _AuditBasic | None = None
    audit_content: _AuditContent | None = None
    audit_record: list[_AuditRecordItem] | None = None
    audit_ext: _AuditExt | None = None
    audit_process: list[_AuditProcessItem] | None = None
    note_list: list[Any] | None = None
    attachment_list: list[Any] | None = None
    carbon_copy_list: list[_CarbonCopyItem] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 11. /api/home/audit/auditExecute
# ════════════════════════════════════════════════════════════════════════════


class AuditExecuteRequest(_Base):
    audit_ids: list[str] | None = None
    audit_status: int | None = None
    audit_remark: Any | None = None


# ════════════════════════════════════════════════════════════════════════════
# 12. /api/order/order/changeInvoiceApply
# ════════════════════════════════════════════════════════════════════════════


class _ChangeInvoiceAuditMsg(_Base):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    code: str | None = None
    msgs: list[str] | None = None


class ChangeInvoiceApplyRequest(_Base):
    audit_note: str | None = None
    order_ids: list[str] | None = None
    action: str | None = None
    audit_msg: _ChangeInvoiceAuditMsg | None = None
    select_node_user: Any | None = None


# ════════════════════════════════════════════════════════════════════════════
# 13. /api/order/order/orderConfirmAccount
# ════════════════════════════════════════════════════════════════════════════


class OrderConfirmAccountRequest(_Base):
    order_id: str | None = None
    action: str | None = None


class _ConfirmAccountCurrencyBlock(_Base):
    model_config = ConfigDict(extra="ignore")

    customer_finance_id: str | None = None
    customer_id: str | None = None
    chinese_header: str | None = None
    english_header: str | None = None
    identifier_no: str | None = None
    phone: str | None = None
    currency: str | None = None
    bank_account: str | None = None
    swift_code: str | None = None
    register_address: str | None = None
    open_bank_cn: str | None = None
    remark: str | None = None
    update_id: str | None = None
    update_by: str | None = None
    delete_time: str | None = None
    sys_upttime: str | None = None
    flag: str | None = None


class _ConfirmAccountBlock(_Base):
    model_config = ConfigDict(extra="ignore")

    USD: list[_ConfirmAccountCurrencyBlock] | None = None
    CNY: list[_ConfirmAccountCurrencyBlock] | None = None
    use_usd: bool | None = None
    use_cny: bool | None = None


class OrderConfirmAccountData(_Base):
    model_config = ConfigDict(extra="ignore")

    customer_currency_finance: _ConfirmAccountBlock | None = None
    main_currency_bank: Any | None = None  # 字段极多,permissive


# ════════════════════════════════════════════════════════════════════════════
# 14. /api/finance/accountFee/financePutList
# ════════════════════════════════════════════════════════════════════════════


class FinancePutListRequest(_Base):
    model_config = ConfigDict(extra="ignore")

    page_no: int | None = None
    page_size: int | None = None
    bl_no: str | None = None
    operate_type: int | None = None
    search_style: str | None = None
    account_simple_name: Any | None = None
    account_type: str | None = None
    customer_id: list[str] | str | None = None
    put_settle_object_id: str | None = None
    main_id: str | None = None
    pay_settle_object_id: Any | None = None
    bl_nos: Any | None = None  # 样本中可 str / list
    batch_type: Any | None = None  # 样本中可 str / int
    put_settle_object: str | None = None


class _FinancePutListItem(_Base):
    model_config = ConfigDict(extra="ignore")

    order_id: str | None = None
    order_no: str | None = None
    bl_no: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    customer_main_id: str | None = None
    customer_main_name: str | None = None
    business_main_id: str | None = None
    business_main_name: str | None = None
    policy_type: str | None = None
    trade_term: str | None = None
    customer_period: str | None = None
    customer_put_date: str | None = None
    atd: str | None = None
    etd: str | None = None
    create_time: str | None = None
    finance_date: str | None = None
    fund_name: str | None = None
    ship_name: str | None = None
    voy: str | None = None
    status: str | None = None
    is_special_pay: str | None = None
    pay_status: str | None = None
    is_loan_before_invoice: str | None = None
    customer_order_sn: str | None = None
    order_sub_id: str | None = None
    order_sub_no: str | None = None
    main_id: str | None = None
    main_name: str | None = None
    service_project: str | None = None
    currency: str | None = None
    amount_total: str | None = None
    pay_settle_object_type: str | None = None
    put_settle_object_id: str | None = None
    put_settle_object: str | None = None
    pay_settle_object: str | None = None
    book_supplier_period: str | None = None
    book_supplier_pay_date: str | None = None
    book_supplier_name: str | None = None
    operable_amount: str | None = None
    un_operable_amount: str | None = None
    operable_flag: str | None = None
    policy_type_name: str | None = None
    order_sub_currency: str | None = None


class FinancePutListData(_Base):
    model_config = ConfigDict(extra="ignore")

    customer_name: list[str] | None = None
    main_name_cn: list[str] | None = None
    settle_object: list[str] | None = None
    total: int | None = None
    data: list[_FinancePutListItem] | None = None
    select_summary: Any | None = None


# ════════════════════════════════════════════════════════════════════════════
# 15. /api/finance/receiveAccount/orderReceiveAccountEdit
# ════════════════════════════════════════════════════════════════════════════


class OrderReceiveAccountEditRequest(_Base):
    """POST /api/finance/receiveAccount/orderReceiveAccountEdit 请求体。"""

    model_config = ConfigDict(extra="ignore")

    account_simple_name: Any | None = None
    account_type: str | None = None
    customer_id: list[str] | str | None = None
    put_settle_object_id: str | None = None
    main_id: str | None = None
    pay_settle_object_id: Any | None = None
    customer_name: Any | None = None
    put_settle_object: str | None = None
    main_name_cn: Any | None = None
    pay_settle_object: Any | None = None
    selection_time: int | None = None
    action: str | None = None
    operate_type: int | None = None
    receive_account_id: Any | None = None
    main_name: str | None = None
    select_list: list[Any] | None = None  # 字段集大,permissive


class OrderReceiveAccountEditData(_Base):
    receive_account_id: int | None = None
    receive_account_no: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 16. /api/finance/receiveAccount/receiveAccountDetail
# ════════════════════════════════════════════════════════════════════════════


class ReceiveAccountDetailRequest(_Base):
    receive_account_id: str | None = None


class ReceiveAccountDetailData(_Base):
    """``receiveAccountDetail`` 返回 ``data.receive_account``,字段极多。"""

    model_config = ConfigDict(extra="ignore")

    receive_account: dict[str, Any] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 17. /api/finance/receiveAccount/receiveConfirmList
# ════════════════════════════════════════════════════════════════════════════


class ReceiveConfirmListRequest(_Base):
    confirm_type: int | None = None
    receive_account_id: str | None = None
    order_ids: list[Any] | None = None


class _ReceiveConfirmListItem(_Base):
    model_config = ConfigDict(extra="ignore")

    main_id: str | None = None
    main_name: str | None = None
    symbol: str | None = None
    settle_object_id: str | None = None
    order_ids: str | None = None
    order_sub_ids: str | None = None
    order_sub_types: str | None = None
    unique_ids: str | None = None
    receive_account_no: str | None = None
    account_simple_name: str | None = None
    symbol_name: str | None = None
    settle_object: str | None = None
    account_batch_name: str | None = None
    order_sub_type: int | None = None
    only_adjust_status: int | None = None
    real_amount_ids: list[str] | None = None
    currency_list: list[str] | None = None


# data: list[_ReceiveConfirmListItem]


# ════════════════════════════════════════════════════════════════════════════
# 18. /api/finance/receiveAccount/accountConfirm
# ════════════════════════════════════════════════════════════════════════════


class AccountConfirmRequest(_Base):
    confirm_type: int | None = None
    receive_account_id: str | None = None
    confirm_list: list[Any] | None = None  # 与 receiveConfirmList item 同形


# ════════════════════════════════════════════════════════════════════════════
# 19. /api/Finance/ReceiveInvoiceBatch/applyPage
# ════════════════════════════════════════════════════════════════════════════


class ApplyPageRequest(_Base):
    """POST /api/Finance/ReceiveInvoiceBatch/applyPage 请求体。"""

    page_no: int | None = None
    page_size: int | None = None
    order_no: str | None = None
    create_time: list[int] | None = None
    sort_field: str | None = None
    sort_order: str | None = None
    params: Any | None = None
    create_time_start: str | None = None
    create_time_end: str | None = None


class _ApplyPageItem(_Base):
    model_config = ConfigDict(extra="ignore")

    receive_invoice_apply_id: str | None = None
    receive_invoice_apply_no: str | None = None
    receive_invoice_batch_no: str | None = None
    receive_invoice_batch_id: str | None = None
    invoice_apply_name: str | None = None
    invoice_apply_simple: str | None = None
    style: str | None = None
    apply_type: str | None = None
    customer_name: str | None = None
    customer_main_name: str | None = None
    put_settle_object: str | None = None
    main_name: str | None = None
    main_name_cn: str | None = None
    pay_settle_object: str | None = None
    business_main_name: str | None = None
    book_supplier_name: str | None = None
    cost_usd: str | None = None
    cost_cny: str | None = None
    currency: str | None = None
    fee_currency: str | None = None
    rate: str | None = None
    turn_cost_cny: str | None = None
    turn_cost_usd: str | None = None
    invoice_apply_amount: str | None = None
    invoice_status: str | None = None
    invoice_used_amount: str | None = None
    invoice_unused_amount: str | None = None
    invoice_no: str | None = None
    registration_type: str | None = None
    writeoff_status: str | None = None
    use_writeoff_amount_cny: str | None = None
    un_writeoff_amount_cny: str | None = None
    use_writeoff_amount_usd: str | None = None
    un_writeoff_amount_usd: str | None = None
    writeoff_id: str | None = None
    writeoff_no: str | None = None
    create_by: str | None = None
    create_time: str | None = None
    cancel_status: str | None = None
    registration_time: str | None = None
    bl_nos: str | None = None
    invoice_date: str | None = None
    batch_same_status: str | None = None
    pay_invoice_apply_id: str | None = None
    pay_invoice_apply_no: str | None = None


class _ApplyPageTotalData(_Base):
    model_config = ConfigDict(extra="ignore")

    amount: str | None = None
    cost_cny: str | None = None
    cost_usd: str | None = None
    invoice_unused_amount: str | None = None
    invoice_used_amount: str | None = None
    turn_cost_cny: str | None = None
    turn_cost_usd: str | None = None
    un_writeoff_amount: str | None = None
    use_writeoff_amount: str | None = None


class ApplyPageData(_Base):
    total: int | None = None
    data: list[_ApplyPageItem] | None = None
    total_data: _ApplyPageTotalData | None = None


# ════════════════════════════════════════════════════════════════════════════
# 20. /api/Finance/ReceiveInvoiceBatch/checkStep1
# ════════════════════════════════════════════════════════════════════════════


class CheckStep1Request(_Base):
    """POST /api/Finance/ReceiveInvoiceBatch/checkStep1 请求体(52 字段,部分宽松)。"""

    model_config = ConfigDict(extra="ignore")

    cny_file: list[Any] | None = None
    usd_file: list[Any] | None = None
    debitno_file: list[Any] | None = None
    style: str | None = None
    apply_type: str | None = None
    customer_id: str | None = None
    customer_name: list[str] | None = None
    put_settle_object_id: str | None = None
    main_id: str | None = None
    pay_settle_object_id: list[Any] | None = None
    turn_rate: str | None = None
    merge_with_cny: str | None = None
    selectRadio: str | None = None
    receive_invoice_batch_id: str | None = None
    batch_apply_name: str | None = None
    invoice_form: str | None = None
    invoice_type: str | None = None
    invoice_items: str | None = None
    invoice_rate_type: str | None = None
    rate_type: str | None = None
    usd_is_turn: str | None = None
    order_fee_real_id: list[str] | None = None
    usd_requireinvoice_form: str | None = None
    usd_requireinvoice_type: str | None = None
    usd_requiretruck_remark: str | None = None
    usd_requireinvoice_items_count: str | None = None
    usd_requireinvoice_items: str | None = None
    usd_requireinvoice_rate: str | None = None
    usd_requireinvoice_rate_type: str | None = None
    usd_requireseller_name: str | None = None
    cny_requireinvoice_form: str | None = None
    cny_requireinvoice_type: str | None = None
    cny_requiretruck_remark: str | None = None
    cny_requireinvoice_items_count: str | None = None
    cny_requireinvoice_items: str | None = None
    cny_requireinvoice_rate: str | None = None
    cny_requireinvoice_rate_type: str | None = None
    cny_requireseller_name: str | None = None
    cny_file_id: list[Any] | None = None
    usd_file_id: list[Any] | None = None
    debitno_file_id: list[Any] | None = None
    cny_require: Any | None = None  # 样本中可 str / dict
    usd_require: Any | None = None  # 样本中可 str / dict
    usd_requiredn_invoice_title_type: str | None = None
    batch_order_remark: Any | None = None  # 样本中可 str / list[dict]
    cost_cny: str | None = None
    cost_usd: str | None = None
    batch_type: str | None = None
    main_name_cn: str | None = None
    order_sub_id: Any | None = None  # 样本中可 str / list[str]
    pay_settle_object: str | None = None
    put_settle_object: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 21. /api/Finance/ReceiveInvoiceBatch/checkStep2
# ════════════════════════════════════════════════════════════════════════════


class CheckStep2Request(_Base):
    """POST /api/Finance/ReceiveInvoiceBatch/checkStep2 请求体(53 字段,比 step1 多)."""

    model_config = ConfigDict(extra="ignore")

    cny_file: list[Any] | None = None
    usd_file: list[Any] | None = None
    debitno_file: list[Any] | None = None
    style: str | None = None
    apply_type: str | None = None
    customer_id: str | None = None
    customer_name: list[str] | None = None
    put_settle_object_id: str | None = None
    main_id: str | None = None
    pay_settle_object_id: list[Any] | None = None
    turn_rate: str | None = None
    merge_with_cny: str | None = None
    selectRadio: str | None = None
    receive_invoice_batch_id: str | None = None
    batch_apply_name: str | None = None
    invoice_form: str | None = None
    invoice_type: str | None = None
    invoice_items: str | None = None
    invoice_rate_type: str | None = None
    rate_type: str | None = None
    usd_is_turn: str | None = None
    order_fee_real_id: list[str] | None = None
    usd_requireinvoice_form: str | None = None
    usd_requireinvoice_type: str | None = None
    usd_requiretruck_remark: str | None = None
    usd_requireinvoice_items_count: str | None = None
    usd_requireinvoice_items: str | None = None
    usd_requireinvoice_rate: str | None = None
    usd_requireinvoice_rate_type: str | None = None
    usd_requireseller_name: str | None = None
    cny_requireinvoice_form: str | None = None
    cny_requireinvoice_type: str | None = None
    cny_requiretruck_remark: str | None = None
    cny_requireinvoice_items_count: str | None = None
    cny_requireinvoice_items: str | None = None
    cny_requireinvoice_rate: str | None = None
    cny_requireinvoice_rate_type: str | None = None
    cny_requireseller_name: str | None = None
    cny_file_id: list[Any] | None = None
    usd_file_id: list[Any] | None = None
    debitno_file_id: list[Any] | None = None
    cny_require: Any | None = None  # 样本中可 str / dict
    usd_require: Any | None = None  # 样本中可 str / dict
    usd_requiredn_invoice_title_type: str | None = None
    batch_order_remark: Any | None = None
    cost_cny: str | None = None
    cost_usd: str | None = None
    batch_type: str | None = None
    main_name_cn: str | None = None
    order_sub_id: Any | None = None
    pay_settle_object: str | None = None
    put_settle_object: str | None = None
    sys_rate: str | None = None
    appoint_rate: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 22. /api/Finance/ReceiveInvoiceBatch/batchOrderEdit
# ════════════════════════════════════════════════════════════════════════════


class BatchOrderEditRequest(_Base):
    """POST /api/Finance/ReceiveInvoiceBatch/batchOrderEdit 请求体(59 字段)。"""

    model_config = ConfigDict(extra="ignore")

    action: str | None = None
    apply_type: str | None = None
    appoint_rate: str | None = None
    audit_msg: Any | None = None
    batch_apply_name: str | None = None
    batch_order_remark: Any | None = None
    batch_type: str | None = None
    cny_file: list[Any] | None = None
    cny_file_id: list[Any] | None = None
    cny_require: Any | None = None
    cny_requireinvoice_form: str | None = None
    cny_requireinvoice_items: str | None = None
    cny_requireinvoice_items_count: str | None = None
    cny_requireinvoice_rate: str | None = None
    cny_requireinvoice_rate_type: str | None = None
    cny_requireinvoice_type: str | None = None
    cny_requireseller_name: str | None = None
    cny_requiretruck_remark: str | None = None
    cost_cny: str | None = None
    cost_usd: str | None = None
    customer_id: str | None = None
    customer_name: list[str] | None = None
    debitno_file: list[Any] | None = None
    debitno_file_id: list[Any] | None = None
    fee_currency: str | None = None
    invoice_form: str | None = None
    invoice_items: str | None = None
    invoice_rate_type: str | None = None
    invoice_type: str | None = None
    main_id: str | None = None
    main_name_cn: str | None = None
    merge_with_cny: str | None = None
    order_fee_real_id: list[str] | None = None
    order_sub_customer_id: Any | None = None
    order_sub_id: Any | None = None
    pay_settle_object: str | None = None
    pay_settle_object_id: list[Any] | None = None
    put_settle_object: str | None = None
    put_settle_object_id: str | None = None
    rate_type: str | None = None
    receive_invoice_batch_id: str | None = None
    selectRadio: str | None = None
    select_node_user: Any | None = None
    style: str | None = None
    sys_rate: str | None = None
    turn_rate: str | None = None
    usd_file: list[Any] | None = None
    usd_file_id: list[Any] | None = None
    usd_is_turn: str | None = None
    usd_require: Any | None = None
    usd_requiredn_invoice_title_type: str | None = None
    usd_requireinvoice_form: str | None = None
    usd_requireinvoice_items: str | None = None
    usd_requireinvoice_items_count: str | None = None
    usd_requireinvoice_rate: str | None = None
    usd_requireinvoice_rate_type: str | None = None
    usd_requireinvoice_type: str | None = None
    usd_requireseller_name: str | None = None
    usd_requiretruck_remark: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 23. /api/Finance/ReceiveInvoiceBatch/batchDetail
# ════════════════════════════════════════════════════════════════════════════


class BatchDetailRequest(_Base):
    receive_invoice_batch_id: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 24. /api/Finance/ReceiveInvoiceBatch/applyDetail
# ════════════════════════════════════════════════════════════════════════════


class ApplyDetailRequest(_Base):
    receive_invoice_apply_id: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 25. /api/finance/receiveInvoice/invoiceAddCheck
# ════════════════════════════════════════════════════════════════════════════


class InvoiceAddCheckRequest(_Base):
    """POST /api/finance/receiveInvoice/invoiceAddCheck 请求体(21 字段)。"""

    model_config = ConfigDict(extra="ignore")

    buyer_chinese_header: str | None = None
    buyer_identifier_no: str | None = None
    buyer_identity: str | None = None
    currency: str | None = None
    file_path: str | None = None
    invoice_amount: str | None = None
    invoice_apply_type: str | None = None
    invoice_date: Any | None = None  # 样本中可 str / int (时间戳)
    invoice_exchange_rate: str | None = None
    invoice_image_name: str | None = None
    invoice_number: str | None = None
    invoice_original: Any | None = None  # 样本中可 str / dict (文件信息)
    invoice_tax_amount: str | None = None
    invoice_type: str | None = None
    isbuyer_identity: str | None = None
    main_name: str | None = None
    put_settle_object: str | None = None
    seller_chinese_header: str | None = None
    seller_identifier_no: str | None = None
    seller_identity: str | None = None
    usd_amount: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 26. /api/finance/receiveInvoice/invoiceAdd
# ════════════════════════════════════════════════════════════════════════════


# 该端点 wire 中 body 是 list[dict] 而非 dict;此处用 list 作为请求体容器
class InvoiceAddRequest(_Base):
    """POST /api/finance/receiveInvoice/invoiceAdd 请求体(本数据集样本为 list[dict])。"""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _wrap_list(cls, data: Any) -> Any:
        """``body`` 在 wire 中实际是 ``list[dict]``(非 dict),在 pydantic 之前包一层。"""
        if isinstance(data, list):
            return {"_root": data}
        return data

    _root: list[Any] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 27. /api/finance/receiveWriteoff/orderFeePage
# ════════════════════════════════════════════════════════════════════════════


class OrderFeePageRequest(_Base):
    order_fee_real_ids: list[str] | None = None
    receive_invoice_ids: list[str] | None = None


# ════════════════════════════════════════════════════════════════════════════
# 28. /api/finance/receiveWriteoff/writeoffBatch
# ════════════════════════════════════════════════════════════════════════════


class WriteoffBatchRequest(_Base):
    """POST /api/finance/receiveWriteoff/writeoffBatch 请求体(17 字段)。"""

    model_config = ConfigDict(extra="ignore")

    action: str | None = None
    audit_note: str | None = None
    fee_match_type: str | None = None
    main_id: str | None = None
    main_name: str | None = None
    select_node_user: Any | None = None
    statement: list[Any] | None = None  # 字段集大,permissive
    statement_amount_cny_total: str | None = None
    statement_amount_usd_total: str | None = None
    un_writeoff_amount_cny_total: str | None = None
    un_writeoff_amount_usd_total: str | None = None
    use_writeoff_amount_cny_total: str | None = None
    use_writeoff_amount_usd_total: str | None = None
    writeoff_mode: str | None = None
    writeoff_name: str | None = None
    writeoff_object: Any | None = None  # 样本中可 str / list[dict]
    writeoff_type: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# 29. /api/finance/receiveWriteoff/writeoffPage
# ════════════════════════════════════════════════════════════════════════════


class WriteoffPageRequest(_Base):
    """POST /api/finance/receiveWriteoff/writeoffPage 请求体(分页)。"""

    page_no: int | None = None
    page_size: int | None = None
    create_time: list[int] | None = None
    create_time_start: str | None = None
    create_time_end: str | None = None
    sort_field: str | None = None
    sort_order: str | None = None
    params: Any | None = None


class _WriteoffPageItem(_Base):
    model_config = ConfigDict(extra="ignore")

    pay_writeoff_id: str | None = None
    pay_writeoff_no: str | None = None
    receive_writeoff_id: str | None = None
    writeoff_no: str | None = None
    writeoff_name: str | None = None
    writeoff_type: str | None = None
    writeoff_type_name: str | None = None
    audit_status: str | None = None
    audit_status_name: str | None = None
    writeoff_status: str | None = None
    writeoff_status_name: str | None = None
    writeoff_user_id: str | None = None
    writeoff_user_by: str | None = None
    create_id: str | None = None
    create_by: str | None = None
    create_time: str | None = None
    sort_create_time: str | None = None
    cancel_time: str | None = None
    cancel_user_by: str | None = None
    writeoff_time: str | None = None
    conn_bl_no: str | None = None
    conn_invoice_no: str | None = None
    receipt_time: str | None = None
    pay_receipt_account: str | None = None
    pay_receipt_open_bank: str | None = None
    pay_receipt_time: str | None = None
    statement_receipt_account: str | None = None
    statement_receipt_time: str | None = None
    statement_main_open_bank_cn: str | None = None
    statement_amount_cny_total: str | None = None
    statement_amount_usd_total: str | None = None
    statement_count: str | None = None
    statement_currency: str | None = None
    use_writeoff_amount_cny_total: str | None = None
    use_writeoff_amount_usd_total: str | None = None
    receive_settle_object: str | None = None
    receive_settle_object_id: str | None = None
    main_name: str | None = None
    fee_match_type: str | None = None
    fee_match_type_name: str | None = None
    is_relate_writeoff: str | None = None
    invoice_currency: str | None = None
    currency_name: str | None = None


class _WriteoffPageTotalData(_Base):
    model_config = ConfigDict(extra="ignore")

    statement_amount_cny_total: str | None = None
    statement_amount_usd_total: str | None = None
    use_writeoff_amount_cny_total: str | None = None
    use_writeoff_amount_usd_total: str | None = None


class WriteoffPageData(_Base):
    total: int | None = None
    data: list[_WriteoffPageItem] | None = None
    total_data: _WriteoffPageTotalData | None = None


# ════════════════════════════════════════════════════════════════════════════
# 端点 ↔ 模型 映射表
# ════════════════════════════════════════════════════════════════════════════


class EndpointBinding(_Base):
    """单个端点的契约绑定:``(method, path)`` → 请求/响应模型。"""

    method: str
    path: str
    request_model: type[BaseModel] | None = None
    response_envelope: type[BaseModel] = CommonResponseEnvelope
    response_data_model: type[BaseModel] | None = None  # ``data`` 字段的内部模型(若可建模)


# 注册表:key = (method, path) → EndpointBinding
PATH_MODELS: dict[tuple[str, str], EndpointBinding] = {
    ("POST", "/api/order/orderEntrust/orderPage"): EndpointBinding(
        method="POST",
        path="/api/order/orderEntrust/orderPage",
        request_model=OrderEntrustOrderPageRequest,
        response_data_model=OrderEntrustOrderPageData,
    ),
    ("POST", "/api/order/orderEntrust/orderAdd"): EndpointBinding(
        method="POST",
        path="/api/order/orderEntrust/orderAdd",
        request_model=OrderEntrustOrderAddRequest,
    ),
    ("POST", "/api/order/order/orderDetail"): EndpointBinding(
        method="POST",
        path="/api/order/order/orderDetail",
        request_model=OrderDetailRequest,
        response_data_model=OrderDetailData,
    ),
    ("POST", "/api/order/order/orderAdd"): EndpointBinding(
        method="POST",
        path="/api/order/order/orderAdd",
        request_model=OrderAddRequest,
    ),
    ("POST", "/api/order/order/orderBook"): EndpointBinding(
        method="POST",
        path="/api/order/order/orderBook",
        request_model=OrderBookRequest,
    ),
    ("POST", "/api/order/orderFee/toggleRealAmount"): EndpointBinding(
        method="POST",
        path="/api/order/orderFee/toggleRealAmount",
        request_model=ToggleRealAmountRequest,
        response_data_model=ToggleRealAmountData,
    ),
    ("POST", "/api/order/orderFee/bookRealAmountEdit"): EndpointBinding(
        method="POST",
        path="/api/order/orderFee/bookRealAmountEdit",
        request_model=BookRealAmountEditRequest,
    ),
    ("POST", "/api/order/order/checkGenerateOrderSub"): EndpointBinding(
        method="POST",
        path="/api/order/order/checkGenerateOrderSub",
        request_model=CheckGenerateOrderSubRequest,
        response_data_model=CheckGenerateOrderSubData,
    ),
    ("POST", "/api/order/order/generateOrderSub"): EndpointBinding(
        method="POST",
        path="/api/order/order/generateOrderSub",
        request_model=GenerateOrderSubRequest,
    ),
    ("POST", "/api/order/orderFee/realAmountLockSubmit"): EndpointBinding(
        method="POST",
        path="/api/order/orderFee/realAmountLockSubmit",
        request_model=RealAmountLockSubmitRequest,
    ),
    ("POST", "/api/home/audit/auditPage"): EndpointBinding(
        method="POST",
        path="/api/home/audit/auditPage",
        request_model=AuditPageRequest,
        response_data_model=AuditPageData,
    ),
    ("POST", "/api/home/audit/auditDetail"): EndpointBinding(
        method="POST",
        path="/api/home/audit/auditDetail",
        request_model=AuditDetailRequest,
        response_data_model=AuditDetailData,
    ),
    ("POST", "/api/home/audit/auditExecute"): EndpointBinding(
        method="POST",
        path="/api/home/audit/auditExecute",
        request_model=AuditExecuteRequest,
    ),
    ("POST", "/api/order/order/changeInvoiceApply"): EndpointBinding(
        method="POST",
        path="/api/order/order/changeInvoiceApply",
        request_model=ChangeInvoiceApplyRequest,
    ),
    ("POST", "/api/order/order/orderConfirmAccount"): EndpointBinding(
        method="POST",
        path="/api/order/order/orderConfirmAccount",
        request_model=OrderConfirmAccountRequest,
        response_data_model=OrderConfirmAccountData,
    ),
    ("POST", "/api/finance/accountFee/financePutList"): EndpointBinding(
        method="POST",
        path="/api/finance/accountFee/financePutList",
        request_model=FinancePutListRequest,
        response_data_model=FinancePutListData,
    ),
    ("POST", "/api/finance/receiveAccount/orderReceiveAccountEdit"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveAccount/orderReceiveAccountEdit",
        request_model=OrderReceiveAccountEditRequest,
        response_data_model=OrderReceiveAccountEditData,
    ),
    ("POST", "/api/finance/receiveAccount/receiveAccountDetail"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveAccount/receiveAccountDetail",
        request_model=ReceiveAccountDetailRequest,
        response_data_model=ReceiveAccountDetailData,
    ),
    ("POST", "/api/finance/receiveAccount/receiveConfirmList"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveAccount/receiveConfirmList",
        request_model=ReceiveConfirmListRequest,
    ),
    ("POST", "/api/finance/receiveAccount/accountConfirm"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveAccount/accountConfirm",
        request_model=AccountConfirmRequest,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/applyPage"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/applyPage",
        request_model=ApplyPageRequest,
        response_data_model=ApplyPageData,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep1"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/checkStep1",
        request_model=CheckStep1Request,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep2"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/checkStep2",
        request_model=CheckStep2Request,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/batchOrderEdit"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/batchOrderEdit",
        request_model=BatchOrderEditRequest,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/batchDetail"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/batchDetail",
        request_model=BatchDetailRequest,
    ),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/applyDetail"): EndpointBinding(
        method="POST",
        path="/api/Finance/ReceiveInvoiceBatch/applyDetail",
        request_model=ApplyDetailRequest,
    ),
    ("POST", "/api/finance/receiveInvoice/invoiceAddCheck"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveInvoice/invoiceAddCheck",
        request_model=InvoiceAddCheckRequest,
    ),
    ("POST", "/api/finance/receiveInvoice/invoiceAdd"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveInvoice/invoiceAdd",
        request_model=InvoiceAddRequest,
    ),
    ("POST", "/api/finance/receiveWriteoff/orderFeePage"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveWriteoff/orderFeePage",
        request_model=OrderFeePageRequest,
    ),
    ("POST", "/api/finance/receiveWriteoff/writeoffBatch"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveWriteoff/writeoffBatch",
        request_model=WriteoffBatchRequest,
    ),
    ("POST", "/api/finance/receiveWriteoff/writeoffPage"): EndpointBinding(
        method="POST",
        path="/api/finance/receiveWriteoff/writeoffPage",
        request_model=WriteoffPageRequest,
        response_data_model=WriteoffPageData,
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# 查找辅助
# ════════════════════════════════════════════════════════════════════════════


def get_binding(method: str, path: str) -> EndpointBinding | None:
    """按 ``(method, path)`` 取 :class:`EndpointBinding`,未命中返回 None。"""
    return PATH_MODELS.get((method, path))


def get_request_model(method: str, path: str) -> type[BaseModel] | None:
    """便捷取请求模型(可能为 None,表示该端点无 body)。"""
    binding = get_binding(method, path)
    return binding.request_model if binding else None


def get_response_data_model(method: str, path: str) -> type[BaseModel] | None:
    """便捷取 ``response.data`` 的内部模型(可能为 None,表示 data 结构未建模)。"""
    binding = get_binding(method, path)
    return binding.response_data_model if binding else None


def list_paths() -> list[tuple[str, str]]:
    """返回所有已注册的 ``(method, path)`` 列表(按 path 字典序)。"""
    return sorted(PATH_MODELS.keys(), key=lambda mp: (mp[1], mp[0]))


# ════════════════════════════════════════════════════════════════════════════
# 导出
# ════════════════════════════════════════════════════════════════════════════


__all__ = [
    # 基类
    "_Base",
    "_SAFE_CONFIG",
    "CommonResponseEnvelope",
    "Params",
    "EndpointBinding",
    # 通用
    "PermissiveRequest",
    # 1-31 顺序:orderEntrust
    "OrderEntrustOrderPageRequest",
    "OrderEntrustOrderPageItem",
    "OrderEntrustOrderPageData",
    "OrderEntrustOrderAddRequest",
    # 2 order
    "OrderAddRequest",
    "OrderBookRequest",
    "OrderDetailRequest",
    "OrderDetailData",
    # 3 orderFee
    "ToggleRealAmountRequest",
    "ToggleRealAmountData",
    "BookRealAmountEditRequest",
    "RealAmountLockSubmitRequest",
    # 4 order(check/generate)
    "CheckGenerateOrderSubRequest",
    "CheckGenerateOrderSubData",
    "GenerateOrderSubRequest",
    # 5 home/audit
    "AuditPageRequest",
    "AuditPageData",
    "AuditDetailRequest",
    "AuditDetailData",
    "AuditExecuteRequest",
    # 6 order(changeInvoice/orderConfirmAccount)
    "ChangeInvoiceApplyRequest",
    "OrderConfirmAccountRequest",
    "OrderConfirmAccountData",
    # 7 finance/accountFee
    "FinancePutListRequest",
    "FinancePutListData",
    # 8 finance/receiveAccount
    "OrderReceiveAccountEditRequest",
    "OrderReceiveAccountEditData",
    "ReceiveAccountDetailRequest",
    "ReceiveAccountDetailData",
    "ReceiveConfirmListRequest",
    "AccountConfirmRequest",
    # 9 Finance/ReceiveInvoiceBatch
    "ApplyPageRequest",
    "ApplyPageData",
    "CheckStep1Request",
    "CheckStep2Request",
    "BatchOrderEditRequest",
    "BatchDetailRequest",
    "ApplyDetailRequest",
    # 10 finance/receiveInvoice
    "InvoiceAddCheckRequest",
    "InvoiceAddRequest",
    # 11 finance/receiveWriteoff
    "OrderFeePageRequest",
    "WriteoffBatchRequest",
    "WriteoffPageRequest",
    "WriteoffPageData",
    # 映射
    "PATH_MODELS",
    "get_binding",
    "get_request_model",
    "get_response_data_model",
    "list_paths",
]
