"""fin.order.generate_order_sub —— 生成应收应付子订单接口契约。在 scen_test_14 中出现1次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


ORDER_GENERATE_ORDER_SUB = EndpointSpec(
    id="fin.order.generate_order_sub",
    system="fin",
    service="order",
    name="生成应收应付子订单",
    description="由 Scenario_Test_14 提取: 生成应收应付子订单",
    api=ApiSpec(service="order", method="POST", path="/api/order/order/generateOrderSub", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='order_id', path='order_id', required=True, example='', ui_kind='text'),
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
