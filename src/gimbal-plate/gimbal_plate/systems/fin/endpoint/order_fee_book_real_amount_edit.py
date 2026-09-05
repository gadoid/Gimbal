"""fin.order_fee.book_real_amount_edit —— 订舱实收实付金额配置接口契约。在 scen_test_14 中出现2次。"""

from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_AUTHOR,
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)


ORDER_FEE_BOOK_REAL_AMOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_fee.book_real_amount_edit",
    system=FIN_SYSTEM,
    service="fin-service",
    name="订舱实收实付金额配置",
    description="由 Scenario_Test_14 提取: 订舱实收实付金额配置",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/orderFee/bookRealAmountEdit", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='action', path='action', type='string', required=True, example='check', ui_kind='text'),
        DeclarationEntry(name='order_id', path='order_id', type='string', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='discount_ratio', path='discount_ratio', type='string', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='service_project', path='service_project', type='string', required=True, example='booking_space', ui_kind='text'),
        DeclarationEntry(name='import_status', path='import_status', type='integer', required=True, example=0, ui_kind='number'),
        DeclarationEntry(name='to_customer', path='to_customer', type='object', required=True, example={'put_amount': {'standard_list': [{'order_fee_real_id': None, 'fee_type': 0, 'policy_sub_id': '470', 'service_project': 'booking_space', 'cost_id': '17', 'settle_object_id': '829', 'subsidy_category': '0', 'currency': 'USD', 'unit_price': '1', 'unit': 'box', 'specs': '40HQ', 'num': '1', 'remark': None, 'discount_ratio': 100, 'discount_amount': '1.00', 'discount_status': '0', 'policy_sub_status_name': '正常', 'pay_sync_status': 1, 'unique_id': '61abfbc5-106d-45e2-8a83-0fbacbd7c648', 'init_main_name': '成都易汇瀚供应链管理有限公司', 'main_name': '成都易汇瀚供应链管理有限公司', 'rowIndex': 0}]}}, ui_kind='json'),
        DeclarationEntry(name='to_supplier', path='to_supplier', type='object', required=True, example={'pay_amount': {'standard_list': [{'order_fee_real_id': None, 'fee_type': 0, 'policy_sub_id': '470', 'service_project': 'booking_space', 'cost_id': '17', 'settle_object_id': '1384', 'subsidy_category': '0', 'currency': 'USD', 'unit_price': '1', 'unit': 'box', 'specs': '40HQ', 'num': '1', 'remark': None, 'discount_ratio': 100, 'discount_amount': '1.00', 'discount_status': '0', 'policy_sub_status_name': '异常', 'pay_sync_status': 1, 'unique_id': '61abfbc5-106d-45e2-8a83-0fbacbd7c648', 'init_main_name': '—', 'main_name': '成都易汇瀚供应链管理有限公司', 'related_unique_id': '61abfbc5-106d-45e2-8a83-0fbacbd7c648', 'rowIndex': 0}]}}, ui_kind='json'),
        ],
        
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
