"""fin.order_fee.real_amount_lock_submit —— 费用实收实付锁定接口契约。在 scen_test_14 中出现3次。"""

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


ORDER_FEE_REAL_AMOUNT_LOCK_SUBMIT: Final[EndpointSpec] = EndpointSpec(
    id="fin.order_fee.real_amount_lock_submit",
    system=FIN_SYSTEM,
    service="fin-service",
    name="费用实收实付锁定",
    description="由 Scenario_Test_14 提取: 费用实收实付锁定",
    api=ApiSpec(service="fin-service", method="POST", path="/api/order/orderFee/realAmountLockSubmit", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        declarations=[
        DeclarationEntry(name='action', path='action', channel='binding', required=True, example='check', ui_kind='text'),
        DeclarationEntry(name='order_id', path='order_id', channel='binding', required=True, example='', ui_kind='text'),
        DeclarationEntry(name='order_fee_real_ids', path='order_fee_real_ids', channel='binding', required=True, example=[''], ui_kind='json'),
        DeclarationEntry(name='audit_msg', path='audit_msg', channel='binding', required=True, example={'title': '业务订单ID', 'code': '', 'msgs': ['费用锁定申请']}, ui_kind='json'),
        DeclarationEntry(name='select_node_user', path='select_node_user', channel='binding', required=True, example=[{'node_sort': '0', 'user_id': '828'}], ui_kind='json'),
        ],
        schema_={},
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
