"""fin 系统所有 endpoint 契约的聚合入口。

每接口独立一个文件 <interface_id>.py,只导出一个 EndpointSpec 实例常量。
本模块聚合所有实例供 PlateRegistry 一键注册。
"""
from gimbal_plate.systems.fin.endpoint.settlement_create_order import (
    SETTLEMENT_CREATE_ORDER,
)
from gimbal_plate.systems.fin.endpoint.account_query_balance import (
    ACCOUNT_QUERY_BALANCE,
)
from gimbal_plate.systems.fin.endpoint.order_entrust_check_order_customer_container import (
    ORDER_ENTRUST_CHECK_ORDER_CUSTOMER_CONTAINER,
)
from gimbal_plate.systems.fin.endpoint.order_entrust_order_add import (
    ORDER_ENTRUST_ORDER_ADD,
)
from gimbal_plate.systems.fin.endpoint.order_entrust_order_confirm import (
    ORDER_ENTRUST_ORDER_CONFIRM,
)
from gimbal_plate.systems.fin.endpoint.order_entrust_order_dispatch import (
    ORDER_ENTRUST_ORDER_DISPATCH,
)
from gimbal_plate.systems.fin.endpoint.order_entrust_order_page import (
    ORDER_ENTRUST_ORDER_PAGE,
)
from gimbal_plate.systems.fin.endpoint.order_order_add import (
    ORDER_ORDER_ADD,
)
from gimbal_plate.systems.fin.endpoint.order_order_detail import (
    ORDER_ORDER_DETAIL,
)
from gimbal_plate.systems.fin.endpoint.order_order_page import (
    ORDER_ORDER_PAGE,
)
from gimbal_plate.systems.fin.endpoint.order_order_book import (
    ORDER_ORDER_BOOK,
)
from gimbal_plate.systems.fin.endpoint.order_check_generate_order_sub import (
    ORDER_CHECK_GENERATE_ORDER_SUB,
)
from gimbal_plate.systems.fin.endpoint.order_generate_order_sub import (
    ORDER_GENERATE_ORDER_SUB,
)
from gimbal_plate.systems.fin.endpoint.order_order_notice import (
    ORDER_ORDER_NOTICE,
)
from gimbal_plate.systems.fin.endpoint.order_fee_toggle_real_amount import (
    ORDER_FEE_TOGGLE_REAL_AMOUNT,
)
from gimbal_plate.systems.fin.endpoint.order_fee_book_real_amount_edit import (
    ORDER_FEE_BOOK_REAL_AMOUNT_EDIT,
)
from gimbal_plate.systems.fin.endpoint.order_fee_real_amount_lock_submit import (
    ORDER_FEE_REAL_AMOUNT_LOCK_SUBMIT,
)
from gimbal_plate.systems.fin.endpoint.order_fee_asset_push import (
    ORDER_FEE_ASSET_PUSH,
)
from gimbal_plate.systems.fin.endpoint.audit_audit_page import (
    AUDIT_AUDIT_PAGE,
)
from gimbal_plate.systems.fin.endpoint.audit_audit_execute import (
    AUDIT_AUDIT_EXECUTE,
)
from gimbal_plate.systems.fin.endpoint.audit_audit_detail import (
    AUDIT_AUDIT_DETAIL,
)


ALL_ENDPOINTS = [
    SETTLEMENT_CREATE_ORDER,
    ACCOUNT_QUERY_BALANCE,
    ORDER_ENTRUST_CHECK_ORDER_CUSTOMER_CONTAINER,
    ORDER_ENTRUST_ORDER_ADD,
    ORDER_ENTRUST_ORDER_CONFIRM,
    ORDER_ENTRUST_ORDER_DISPATCH,
    ORDER_ENTRUST_ORDER_PAGE,
    ORDER_ORDER_ADD,
    ORDER_ORDER_DETAIL,
    ORDER_ORDER_PAGE,
    ORDER_ORDER_BOOK,
    ORDER_CHECK_GENERATE_ORDER_SUB,
    ORDER_GENERATE_ORDER_SUB,
    ORDER_ORDER_NOTICE,
    ORDER_FEE_TOGGLE_REAL_AMOUNT,
    ORDER_FEE_BOOK_REAL_AMOUNT_EDIT,
    ORDER_FEE_REAL_AMOUNT_LOCK_SUBMIT,
    ORDER_FEE_ASSET_PUSH,
    AUDIT_AUDIT_PAGE,
    AUDIT_AUDIT_EXECUTE,
    AUDIT_AUDIT_DETAIL,
]

__all__ = [
    "SETTLEMENT_CREATE_ORDER",
    "ACCOUNT_QUERY_BALANCE",
    "ORDER_ENTRUST_CHECK_ORDER_CUSTOMER_CONTAINER",
    "ORDER_ENTRUST_ORDER_ADD",
    "ORDER_ENTRUST_ORDER_CONFIRM",
    "ORDER_ENTRUST_ORDER_DISPATCH",
    "ORDER_ENTRUST_ORDER_PAGE",
    "ORDER_ORDER_ADD",
    "ORDER_ORDER_DETAIL",
    "ORDER_ORDER_PAGE",
    "ORDER_ORDER_BOOK",
    "ORDER_CHECK_GENERATE_ORDER_SUB",
    "ORDER_GENERATE_ORDER_SUB",
    "ORDER_ORDER_NOTICE",
    "ORDER_FEE_TOGGLE_REAL_AMOUNT",
    "ORDER_FEE_BOOK_REAL_AMOUNT_EDIT",
    "ORDER_FEE_REAL_AMOUNT_LOCK_SUBMIT",
    "ORDER_FEE_ASSET_PUSH",
    "AUDIT_AUDIT_PAGE",
    "AUDIT_AUDIT_EXECUTE",
    "AUDIT_AUDIT_DETAIL",
    "ALL_ENDPOINTS",
]
