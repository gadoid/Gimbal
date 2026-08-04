"""fin.order.order_page —— 分页查询委托订单接口契约。在 scen_test_14 中出现3次。"""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)


ORDER_ORDER_PAGE = EndpointSpec(
    id="fin.order.order_page",
    system="fin",
    service="order",
    name="分页查询委托订单",
    description="由 Scenario_Test_14 提取: 分页查询委托订单",
    api=ApiSpec(service="order", method="POST", path="/api/order/order/orderPage", auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(
        body_type="json",
        fields=[
        IOFieldBinding(name='page_no', path='page_no', required=True, example=1, ui_kind='number'),
        IOFieldBinding(name='page_size', path='page_size', required=True, example=20, ui_kind='number'),
        IOFieldBinding(name='sort_field', path='sort_field', required=True, example='update_time', ui_kind='text'),
        IOFieldBinding(name='sort_order', path='sort_order', required=True, example='desc', ui_kind='text'),
        IOFieldBinding(name='params', path='params', required=True, example={}, ui_kind='json'),
        ],
        schema_={},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            fields=[
        IOFieldBinding(name='order_id', path='$.data.data[0].order_id', required=False, ui_kind="unknown"),
            ],
            assertable_fields=['$.data.data[0].order_id'],
        ),
    },
    version="1.0.0",
)
