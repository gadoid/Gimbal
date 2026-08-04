"""fin.order_fee.real_amount_lock_submit —— 费用实收实付锁定接口契约。在 scen_test_14 中出现3次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


ORDER_FEE_REAL_AMOUNT_LOCK_SUBMIT = EndpointSpec(
    id="fin.order_fee.real_amount_lock_submit",
    system="fin",
    service="order_fee",
    name="费用实收实付锁定",
    description="由 Scenario_Test_14 提取: 费用实收实付锁定",
    api=ApiSpec(service="order_fee", method="POST", path="/api/order/orderFee/realAmountLockSubmit", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='action', path='action', required=True, example='check', ui_kind='text'),
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text'),
        IOFieldBinding(name='order_fee_real_ids', path='order_fee_real_ids', required=True, example=[''], ui_kind='json'),
        IOFieldBinding(name='audit_msg', path='audit_msg', required=True, example={'title': '业务订单ID', 'code': '', 'msgs': ['费用锁定申请']}, ui_kind='json'),
        IOFieldBinding(name='select_node_user', path='select_node_user', required=True, example=[{'node_sort': '0', 'user_id': '828'}], ui_kind='json'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
        ),
    },
    version="1.0.0",
)
