"""fin.order.order_notice —— 应收核销通知接口契约。在 scen_test_14 中出现2次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


ORDER_ORDER_NOTICE = EndpointSpec(
    id="fin.order.order_notice",
    system="fin",
    service="order",
    name="应收核销通知",
    description="由 Scenario_Test_14 提取: 应收核销通知",
    api=ApiSpec(service="order", method="POST", path="/api/order/order/orderNotice", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text'),
        IOFieldBinding(name='action', path='action', required=True, example='check', ui_kind='text'),
        IOFieldBinding(name='finance_ids', path='finance_ids', required=True, example=['${var.finance_id_0}', '${var.finance_id_1}'], ui_kind='json'),
        IOFieldBinding(name='bank_ids', path='bank_ids', required=True, example=['${var.bank_id_0}', '${var.bank_id_1}'], ui_kind='json'),
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
